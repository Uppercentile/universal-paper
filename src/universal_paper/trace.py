"""Trace files: every event, every check, and each evaluator's independently computed state hash.

A trace is what the Explorer plays back. The Explorer never computes anything
itself; everything it shows comes from this file (see schema/trace.schema.json).
"""
from __future__ import annotations

from . import SPEC, __version__
from .canon import content_hash
from .engine import Bundle, Evaluator
from .report import snapshot

FORMAT = "up-trace/0.1"


def _names(b: Bundle) -> dict[str, str]:
    names = {}
    for ag in b.agreements.values():
        for p in ag.get("parties", []):
            names[p["party"]["key"]] = p["party"].get("name", p["party"]["key"][:16])
    for m in b.mandates.values():
        names.setdefault(m["agent"], f"Agent of {names.get(m['principal'], m['principal'][:16])}")
    return names


def describe(E: dict, b: Bundle, names: dict[str, str], chain_label: str) -> str:
    who = names.get(E.get("by"), E.get("by", "?")[:16])
    agent = next((s for s in E.get("sigs", []) if "mandate" in s), None)
    via = f" (through its agent)" if agent else ""
    kind, body = E.get("kind"), E.get("body", {})
    if kind == "propose":
        ag = body.get("agreement", {})
        if "supersedes" in body:
            return f"{who}{via} proposes an amendment to “{chain_label}”."
        return f"{who}{via} proposes “{ag.get('label', 'an agreement')}”."
    if kind == "accept":
        return f"{who}{via} signs or acknowledges an earlier event in “{chain_label}”."
    claim = body.get("claim", {})
    ctype = claim.get("type", "")
    nice = {
        "UP:Sales-Reporting/report": "reports sales for the period",
        "UP:Admin-Fee/paid": "attests payment of the administrative fee",
        "UP:Tier-Selection/selects": f"attests qualification for tier {claim.get('data', {}).get('option', '?')}",
        "UP:Fee-Disclosure/disclosed": "discloses administrative fees received",
        "UP:Audit/request": "requests an audit",
        "UP:Audit/available": "makes records available for audit",
        "UP:Termination-Convenience/notice": "gives notice of termination",
        "UP:Renewing-Term/optout": "gives notice of non-renewal",
    }.get(ctype, f"attests {ctype}")
    return f"{who}{via} {nice} under “{chain_label}”."


def _accept_target_label(E, b: Bundle, chain) -> str:
    return ""


def make_trace(reference: dict, evaluators: list[dict], meta: dict, final_at: str) -> dict:
    """reference: the bundle that defines the event order and the narrative.
    evaluators: [{id, name, data, tampered?, hashes_only?}], each evaluating its own copy independently."""
    ref = Bundle(reference)
    names = _names(ref)
    ref_ev = Evaluator(ref)
    order = sorted(((E["at"], pos, i) for pos, ch in enumerate(ref.chain_list) for i, E in enumerate(ch)))
    labels = {}
    for pos, ch in enumerate(ref.chain_list):
        labels[pos] = ch[0].get("body", {}).get("agreement", {}).get("label", f"Chain {pos}")

    evs = []
    for e in evaluators:
        b = Bundle(e["data"])
        ev = Evaluator(b)
        runs = [ev.run(content_hash(ch[0])) if ch else [] for ch in b.chain_list]
        evs.append((e, b, ev, runs))

    processed: dict[int, int] = {}
    steps = []
    for n, (at, pos, i) in enumerate(order):
        E = ref.chain_list[pos][i]
        processed[pos] = i
        agent_sig = next((s for s in E.get("sigs", []) if "mandate" in s), None)
        event = {
            "chain": pos, "chain_label": labels[pos], "index": i, "kind": E["kind"], "at": E["at"],
            "by": E["by"], "by_name": names.get(E["by"], E["by"][:16]),
            "prev": E.get("prev"), "hash": content_hash(E),
            "description": describe(E, ref, names, labels[pos]),
            "signers": [{"key": s["key"], "name": names.get(s["key"], s["key"][:16]), "mandate": s.get("mandate")}
                        for s in E.get("sigs", [])],
            "body": E.get("body"),
        }
        if agent_sig:
            m = ref.mandates.get(agent_sig["mandate"])
            if m:
                event["mandate"] = {"hash": agent_sig["mandate"], "principal": m["principal"],
                                    "principal_name": names.get(m["principal"], ""), "agent": m["agent"],
                                    "not_before": m["not_before"], "expires": m["expires"], "scope": m["scope"]}
        results = {}
        for e, b, ev, runs in evs:
            st = runs[pos][i] if pos < len(runs) and i < len(runs[pos]) else None
            chain_hashes = []
            for p in range(len(ref.chain_list)):
                h = None
                if p in processed and p < len(runs):
                    acc = [s for s in runs[p][: processed[p] + 1] if s.accepted]
                    h = content_hash(acc[-1].state) if acc else None
                chain_hashes.append(h)
            results[e["id"]] = {
                "event_hash": st.event_hash if st else None,
                "accepted": bool(st and st.accepted),
                "reason": (st.reason if st else "This evaluator's copy has no such event."),
                "checks": [c.to_json() for c in st.checks] if st else [],
                "chain_state_hash": chain_hashes[pos],
                "world_hash": content_hash({"chains": [h or "none" for h in chain_hashes]}),
                "derived": snapshot(ev, E["at"], positions=sorted(processed)),
            }
        world = {r["world_hash"] for r in results.values()}
        steps.append({"step": n, "event": event, "results": results, "consensus": len(world) == 1,
                      "reference_accepted": results[evaluators[0]["id"]]["accepted"] if not evaluators[0].get("tampered") else
                      next((r["accepted"] for e2, r in zip(evaluators, results.values()) if not e2.get("tampered")), None)})

    final = {e["id"]: snapshot(ev, final_at) for e, b, ev, runs in evs}
    return {
        "type": "Trace", "format": FORMAT, "spec": SPEC, "generated_by": f"universal-paper reference interpreter {__version__}",
        "title": meta.get("title", ""), "description": meta.get("description", ""),
        "hypothetical": True,
        "evaluators": [{"id": e["id"], "name": e["name"], "hashes_only": bool(e.get("hashes_only")),
                        "tampered": e.get("tampered")} for e in evaluators],
        "parties": names,
        "chains": [{"position": p, "label": labels[p], "chain_id": content_hash(ref.chain_list[p][0])} for p in labels],
        "steps": steps,
        "final": {"at": final_at, "by_evaluator": final},
    }
