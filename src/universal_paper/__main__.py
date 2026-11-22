"""Command-line interface:  python -m universal_paper <command> ...  (or `up <command>` once installed)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .canon import content_hash
from .engine import Bundle, Evaluator, agreement_issues
from .render import render_agreement
from .report import snapshot
from .simulate import simulate
from .trace import make_trace


class InputError(Exception):
    pass


def _pairs(pairs: list) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise InputError(f"duplicate object key {k!r} (I-JSON, RFC 7493, forbids duplicates)")
        out[k] = v
    return out


def _constant(name: str):
    raise InputError(f"{name} is not valid JSON")


def loads(text: str):
    """Strict JSON: no duplicate keys and no NaN or Infinity (RFC 8785 relies on I-JSON)."""
    return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)


def _load(p: str):
    try:
        text = Path(p).read_text(encoding="utf-8")
    except OSError as e:
        raise InputError(f"cannot read {p}: {e.strerror or e}") from None
    except UnicodeDecodeError:
        raise InputError(f"{p} is not UTF-8 text") from None
    try:
        return loads(text)
    except json.JSONDecodeError as e:
        raise InputError(f"{p} is not valid JSON: {e}") from None


def _out(obj, path: str | None = None) -> None:
    text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path:
        Path(path).write_text(text)
    else:
        sys.stdout.write(text)


def _latest(b: Bundle) -> str:
    times = [E["at"] for ch in b.chain_list for E in ch if isinstance(E, dict) and isinstance(E.get("at"), str)]
    if not times:
        raise InputError("the bundle has no events")
    return max(times)


def _pos(b: Bundle, chain: str | None) -> list[int]:
    if chain is None:
        return list(range(len(b.chain_list)))
    if chain.isdigit() and int(chain) < len(b.chain_list):
        return [int(chain)]
    if chain in b.chain_pos:
        return [b.chain_pos[chain]]
    raise InputError(f"no chain {chain!r} in the bundle")


def cmd_validate(a) -> int:
    b = Bundle(_load(a.bundle))
    ev = Evaluator(b)
    bad = 0
    for pos, ch in enumerate(b.chain_list):
        cid = content_hash(ch[0])
        label = ch[0].get("body", {}).get("agreement", {}).get("label", f"chain {pos}")
        print(f"chain {pos}: {label}\n  id {cid}")
        for st in ev.run(cid):
            mark = "ok      " if st.accepted else "REJECTED"
            print(f"  [{mark}] #{st.index} {st.event['kind']:<7} {st.event['at']}  {st.reason if not st.accepted else ''}")
            bad += not st.accepted
        S = ev.state_at(cid)
        if S:
            print(f"  state {content_hash(S)}  status at latest event: {ev.status(cid, _latest(b))}")
    for h, ag in sorted(b.agreements.items()):
        for rule, why in agreement_issues(b, ag):
            print(f"agreement {h}: {rule}: {why}")
    for cid in sorted(set(b.forks)):
        print(f"INVALID BUNDLE: chain {cid} appears more than once (two versions of one chain)")
    print(f"\n{bad} event(s) rejected." if bad else "\nEvery event is valid.")
    return 2 if bad or b.forks else 0


def cmd_apply(a) -> int:
    data = _load(a.bundle)
    E = _load(a.event)
    b = Bundle(data)
    if "chain" in E:
        pos = b.chain_pos.get(E["chain"])
        if pos is None:
            print("unknown chain", file=sys.stderr)
            return 1
        S = Evaluator(b).state_at(E["chain"])
    else:
        S = None
        if isinstance(E, dict) and content_hash(E) in b.chains:
            print("this genesis event already starts a chain in the bundle", file=sys.stderr)
            return 2
    S2, checks, reason = Evaluator(b).apply(S, E)
    _out({"accepted": S2 is not None, "reason": reason, "checks": [c.to_json() for c in checks],
          "state": S2, "state_hash": content_hash(S2) if S2 else None})
    if S2 is not None and a.write:
        if S is None:
            data["chains"].append([E])
        else:
            data["chains"][pos].append(E)
        _out(data, a.bundle)
    return 0 if S2 is not None else 2


def cmd_derive(a) -> int:
    b = Bundle(_load(a.bundle))
    _out(snapshot(Evaluator(b), a.at or _latest(b)))
    return 0


def cmd_simulate(a) -> int:
    _out(simulate(_load(a.bundle), _load(a.events), a.at), a.output)
    return 0


def cmd_render(a) -> int:
    b = Bundle(_load(a.bundle))
    if a.hashes_only:
        b.disclosures = {}
    ev = Evaluator(b)
    for pos in _pos(b, a.chain):
        S = ev.state_at(content_hash(b.chain_list[pos][0]))
        ag = ev.agreement(S) or b.chain_list[pos][0]["body"]["agreement"]
        sys.stdout.write(render_agreement(b, ag) + "\n")
    return 0


def cmd_trace(a) -> int:
    data = _load(a.bundle)
    if a.config:
        cfg = _load(a.config)
        evals = [{**e, "data": _load(e["bundle"]) if "bundle" in e else data} for e in cfg["evaluators"]]
        meta = cfg.get("meta", {})
    else:
        evals = [{"id": f"evaluator-{i + 1}", "name": f"Evaluator {i + 1}", "data": data} for i in range(a.evaluators)]
        meta = {"title": Path(a.bundle).stem}
    _out(make_trace(data, evals, meta, a.at or _latest(Bundle(data))), a.output)
    return 0


def cmd_hash(a) -> int:
    print(content_hash(_load(a.file)))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="up", description="Universal Paper reference interpreter (UP/0.1-draft)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("validate", help="check every agreement and event in a bundle against the axioms")
    s.add_argument("bundle"); s.set_defaults(f=cmd_validate)
    s = sub.add_parser("apply", help="apply one event to its chain's current state; reject invalid transitions")
    s.add_argument("bundle"); s.add_argument("event"); s.add_argument("--write", action="store_true", help="append the event to the bundle file if valid")
    s.set_defaults(f=cmd_apply)
    s = sub.add_parser("derive", help="derive states, statuses, tiers, prices, and obligations at a time")
    s.add_argument("bundle"); s.add_argument("--at"); s.set_defaults(f=cmd_derive)
    s = sub.add_parser("simulate", help="run hypothetical events forward and report the results")
    s.add_argument("bundle"); s.add_argument("events"); s.add_argument("--at"); s.add_argument("-o", "--output")
    s.set_defaults(f=cmd_simulate)
    s = sub.add_parser("render", help="render agreements as human-readable text")
    s.add_argument("bundle"); s.add_argument("--chain"); s.add_argument("--hashes-only", action="store_true", help="ignore disclosures")
    s.set_defaults(f=cmd_render)
    s = sub.add_parser("trace", help="write a trace file of every event, check, and evaluator state hash")
    s.add_argument("bundle"); s.add_argument("-o", "--output"); s.add_argument("--at")
    s.add_argument("--evaluators", type=int, default=3); s.add_argument("--config", help="JSON file naming evaluators and their bundle copies")
    s.set_defaults(f=cmd_trace)
    s = sub.add_parser("hash", help="print the content hash of a JSON object"); s.add_argument("file"); s.set_defaults(f=cmd_hash)
    a = p.parse_args(argv)
    try:
        return a.f(a)
    except InputError as e:
        print(f"up: error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # malformed input must never end in a traceback
        if os.environ.get("UP_DEBUG"):
            raise
        print(f"up: error: the input could not be processed ({type(e).__name__}: {e}). "
              "Set UP_DEBUG=1 to see the traceback.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
