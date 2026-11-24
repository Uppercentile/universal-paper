"""Simulation: the inference rules run forward over hypothetical events (spec/04-inference.md §8)."""
from __future__ import annotations

import copy

from . import SPEC
from .canon import content_hash
from .engine import Bundle, Evaluator
from .report import snapshot


def simulate(data: dict, hypothetical: list[dict], at: str | None = None) -> dict:
    """Each hypothetical event: {chain: position|ChainId|null, kind, by, at, body, cosigners?: [keys], agent?: {key, mandate}}.

    Signatures are not checked for hypothetical events, but Mandate coverage is.
    """
    data, unverified, results = run_hypothetical(data, hypothetical)
    final_at = at or (hypothetical[-1]["at"] if hypothetical else None)
    final = snapshot(Evaluator(Bundle(data), unverified), final_at) if final_at else None
    return {"type": "Simulation", "spec": SPEC, "hypothetical": True, "steps": results, "final": final, "at": final_at}


def run_hypothetical(data: dict, hypothetical: list[dict]) -> tuple[dict, set[str], list[dict]]:
    """Append hypothetical events to a copy of the bundle: (new bundle data, unverified event hashes, per-step results).

    Build an Evaluator(Bundle(data), unverified) over the result to ask further questions of the hypothetical state.
    """
    data = copy.deepcopy(data)
    unverified: set[str] = set()
    results = []
    for h in hypothetical:
        b = Bundle(data)
        ev = Evaluator(b, unverified)
        E = {"type": "Event", "spec": SPEC, "kind": h["kind"], "at": h["at"], "by": h["by"], "body": h["body"]}
        ch = h.get("chain")
        if isinstance(ch, int):
            pos = ch
        elif isinstance(ch, str):
            pos = b.chain_pos[ch]
        else:
            pos = None
        if pos is not None:
            cid = content_hash(data["chains"][pos][0])
            E["chain"] = cid
            E["prev"] = content_hash(ev.state_at(cid))
        sigs = []
        if h.get("agent"):
            sigs.append({"key": h["agent"]["key"], "mandate": h["agent"]["mandate"]})
        else:
            sigs.append({"key": h["by"]})
        sigs += [{"key": k} for k in h.get("cosigners", [])]
        E["sigs"] = sorted(sigs, key=lambda s: s["key"])
        unverified.add(content_hash(E))
        if pos is None:
            data["chains"].append([E])
            pos = len(data["chains"]) - 1
        else:
            data["chains"][pos].append(E)
        b = Bundle(data)
        ev = Evaluator(b, unverified)
        cid = content_hash(data["chains"][pos][0])
        step = ev.run(cid)[-1]
        results.append({"hypothetical": True, "chain": pos, "at": h["at"], "kind": h["kind"],
                        "accepted": step.accepted, "reason": step.reason,
                        "checks": [c.to_json() for c in step.checks],
                        "state_hash": content_hash(step.state) if step.state else None,
                        "derived": snapshot(ev, h["at"])})
    return data, unverified, results
