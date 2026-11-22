"""The JavaScript engine used by the Explorer must reproduce the Python reference exactly."""
import copy
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")


def _term_scenarios():
    """One trace per claim type of every Term: valid attestation, acknowledgments, and an ill-typed attempt.

    The examples use twelve of the sixteen Terms. These scenarios make the JavaScript engine reproduce
    Python on all sixteen, including the rejection reasons for ill-typed data.
    """
    from universal_paper.canon import content_hash
    from universal_paper.engine import agreement_issues
    from universal_paper.render import render_agreement
    from universal_paper.trace import make_trace

    from helpers import AGG, MEM, SUP, ev, raw
    from test_terms import CLAIMS, TERMS, _claim_data, _world_with

    actors = {"aggregator": AGG, "supplier": SUP, "member": MEM}
    traces, renders, bundles = [], [], {}
    done_terms = set()
    for tid, ctype in CLAIMS + [(t, None) for t in sorted(TERMS) if not TERMS[t]["claims"]]:
        r = random.Random(f"conformance {tid} {ctype}")
        w, pos, A = _world_with(tid, r)
        if ctype:
            e = ev(w)
            attest_roles, ack_roles = e._claim_rules(A, "x")
            author = actors[sorted(attest_roles[ctype])[0]]
            data = _claim_data(tid, ctype, r, w, pos)
            bad = copy.deepcopy(data)
            if bad:
                f = sorted(bad)[0]
                bad[f] = {"unit": "day", "count": 0}
            raw(w, pos, "attest", author, "2027-01-15T00:00:00Z", {"claim": {"type": ctype, "clause": "x", "data": bad}})
            w.chains[pos].pop()
            st = raw(w, pos, "attest", author, "2027-02-01T00:00:00Z", {"claim": {"type": ctype, "clause": "x", "data": data}})
            if st.accepted:
                for role in sorted(ack_roles.get(ctype, set())):
                    acker = actors[role]
                    if acker is not author and acker.pub in {p["party"]["key"] for p in A["parties"]}:
                        raw(w, pos, "accept", acker, "2027-02-02T00:00:00Z", {"target": st.event_hash})
            w.chains[pos].append({**w.chains[pos][-1], "at": "2027-02-03T00:00:00Z"})  # an altered copy: rejected
        d = w.data()
        name = f"{tid} {ctype or ''}".strip()
        traces.append({"reference": d, "evaluators": [{"id": "e1", "name": "E1", "data": d}], "meta": {"title": name},
                       "final_at": "2027-03-01T00:00:00Z",
                       "expected": make_trace(d, [{"id": "e1", "name": "E1", "data": d}], {"title": name}, "2027-03-01T00:00:00Z")})
        if tid not in done_terms:
            done_terms.add(tid)
            bundles[name] = d
            b = ev(w).b
            renders.append({"bundle": name, "chain": pos, "agreement_hash": content_hash(A), "text": render_agreement(b, A),
                            "issues": [list(x) for x in agreement_issues(b, A)]})
    return traces, renders, bundles


@needs_node
def test_js_engine_reproduces_python(tmp_path):
    fx = tmp_path / "fixtures.json"
    subprocess.run([sys.executable, str(ROOT / "tools" / "dump_conformance.py"), str(fx)], check=True, capture_output=True)
    data = json.loads(fx.read_text())
    traces, renders, bundles = _term_scenarios()
    data["traces"] += traces
    data["renders"] += renders
    data["bundles"].update(bundles)
    fx.write_text(json.dumps(data, ensure_ascii=False))
    r = subprocess.run(["node", str(ROOT / "tests" / "js_conformance.mjs"), str(fx)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"{len(data['traces'])} traces" in r.stdout


@needs_node
def test_generated_runs_pass_every_invariant():
    r = subprocess.run(["node", str(ROOT / "tests" / "js_lab.mjs"), "60"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
