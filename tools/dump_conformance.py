"""Write the inputs and Python outputs that the JavaScript engine must reproduce.

Usage: python tools/dump_conformance.py OUT.json
Runs examples/build_examples.py in memory (writing nothing to examples/), recording every
make_trace call, plus renders, simulations, and a known signature.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "examples")]

import universal_paper.trace as trace_mod  # noqa: E402
from universal_paper.canon import content_hash  # noqa: E402
from universal_paper.crypto import Key  # noqa: E402
from universal_paper.engine import Bundle, Evaluator, agreement_issues  # noqa: E402
from universal_paper.render import render_agreement  # noqa: E402
from universal_paper.simulate import simulate  # noqa: E402

import build_examples  # noqa: E402


def main(out: str) -> None:
    traces, bundles = [], {}
    real = trace_mod.make_trace

    def recording(reference, evaluators, meta, final_at):
        t = real(reference, evaluators, meta, final_at)
        traces.append({"reference": reference, "evaluators": evaluators, "meta": meta, "final_at": final_at, "expected": t})
        return t

    def write(path, obj):
        if path.name.startswith("bundle"):
            bundles[f"{path.parent.name}/{path.name}"] = obj

    trace_mod.make_trace = recording
    build_examples.write = write
    saved = Path.write_text
    Path.write_text = lambda self, s, *a, **k: None  # skip the overlay text file
    try:
        build_examples.main()
    finally:
        Path.write_text = saved

    renders = []
    for name, data in bundles.items():
        b = Bundle(data)
        ev = Evaluator(b)
        for pos, ch in enumerate(b.chain_list):
            S = ev.state_at(content_hash(ch[0]))
            ag = ev.agreement(S) or ch[0]["body"]["agreement"]
            renders.append({"bundle": name, "chain": pos, "agreement_hash": content_hash(ag),
                            "text": render_agreement(b, ag), "issues": [list(x) for x in agreement_issues(b, ag)]})
    sims = []
    w, actors, _ = build_examples.conventional()
    d = w.data()
    sims.append({"data": d, "events": [
        {"chain": 2, "kind": "attest", "by": actors["m2"].pub, "at": "2027-05-01T00:00:00Z",
         "body": {"claim": {"type": "UP:Tier-Selection/selects", "clause": "tier", "data": {"option": "C", "basis": "what if"}}},
         "cosigners": [actors["sup"].pub]},
        {"chain": 0, "kind": "attest", "by": actors["agg"].pub, "at": "2027-05-03T00:00:00Z",
         "body": {"claim": {"type": "UP:Nope/x", "clause": "fee", "data": {}}}}], "at": "2027-05-04T00:00:00Z"})
    w, actors, _ = build_examples.generative()
    d = w.data()
    m = d["mandates"][1]
    sims.append({"data": d, "events": [
        {"chain": 3, "kind": "attest", "by": actors["hosp"].pub, "at": "2027-02-10T00:00:00Z",
         "body": {"claim": {"type": "UP:Tier-Selection/selects", "clause": "tier", "data": {"option": "C", "basis": "x"}}},
         "agent": {"key": m["agent"], "mandate": content_hash(m)}}], "at": None})
    for sim in sims:
        sim["expected"] = simulate(sim["data"], sim["events"], sim["at"])
    k = Key.from_seed("conformance")
    sig = {"seed": "conformance", "public": k.public, "object": {"type": "X", "n": 1, "s": "é\n\"q\""},
           "sig": k.sign_obj({"type": "X", "n": 1, "s": "é\n\"q\""})["sig"]}
    Path(out).write_text(json.dumps({"traces": traces, "bundles": bundles, "renders": renders, "simulations": sims, "signature": sig}, ensure_ascii=False))
    print(f"{len(traces)} traces, {len(bundles)} bundles, {len(renders)} renders -> {out}")


if __name__ == "__main__":
    main(sys.argv[1])
