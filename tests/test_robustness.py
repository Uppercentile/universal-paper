"""Hostile and malformed input: the evaluator rejects it, never crashes or hangs, and never accepts a forgery.

Uses Hypothesis with derandomize=True so CI runs are reproducible. Set HYPOTHESIS_PROFILE=deep
for a longer local run.
"""
import contextlib
import copy
import io
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from universal_paper.__main__ import main
from universal_paper.canon import content_hash
from universal_paper.engine import Bundle, Evaluator
from universal_paper.report import snapshot

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = {n: json.loads((ROOT / "examples" / n / "bundle.json").read_text()) for n in ("conventional", "generative", "overlay")}

settings.register_profile("ci", max_examples=150, deadline=None, derandomize=True,
                          suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
settings.register_profile("deep", max_examples=3000, deadline=None, suppress_health_check=list(HealthCheck))
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

JSON_LEAF = st.one_of(st.booleans(), st.integers(-(2**53) + 1, 2**53 - 1), st.text(max_size=12),
                      st.sampled_from(["sha256:" + "0" * 64, "2027-01-01T00:00:00Z", {"unit": "day", "count": 0}, {"seal": "sha256:" + "1" * 64}]))
JSON = st.recursive(JSON_LEAF, lambda kids: st.one_of(st.lists(kids, max_size=3), st.dictionaries(st.text("abcdefgh_", max_size=6), kids, max_size=3)), max_leaves=8)


def _paths(x, prefix=()):
    yield prefix
    if isinstance(x, dict):
        for k, v in x.items():
            yield from _paths(v, prefix + (k,))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from _paths(v, prefix + (i,))


def _set(x, path, value):
    for p in path[:-1]:
        x = x[p]
    x[path[-1]] = value


@given(data=st.data())
def test_mutated_events_are_rejected_never_crash_and_forgeries_never_verify(data):
    name = data.draw(st.sampled_from(sorted(EXAMPLES)))
    bundle = copy.deepcopy(EXAMPLES[name])
    ci = data.draw(st.integers(0, len(bundle["chains"]) - 1))
    chain = bundle["chains"][ci]
    ei = data.draw(st.integers(0, len(chain) - 1))
    event = chain[ei]
    paths = [p for p in _paths(event) if p and p[0] != "sigs"]
    path = data.draw(st.sampled_from(paths))
    new = data.draw(JSON)
    before = content_hash(event)
    _set(event, path, new)
    try:
        changed = content_hash(event) != before
    except Exception:
        changed = True  # no longer canonicalizable: certainly not the signed object
    ev = Evaluator(Bundle(bundle))
    cid = content_hash(chain[0]) if ei else None
    for c in bundle["chains"]:
        try:
            steps = ev.run(content_hash(c[0]))
        except Exception:
            continue  # the genesis itself is no longer hashable; the chain has no id
        assert all(isinstance(s.accepted, bool) for s in steps)
    if changed and cid is not None:
        st_ = ev.run(cid)[ei]
        assert not st_.accepted, f"an altered event was accepted at {path}"
    # Derived values never crash on whatever was accepted.
    snapshot(ev, "2027-06-30T00:00:00Z")


@given(junk=JSON)
def test_arbitrary_json_as_a_bundle_never_crashes_the_evaluator(junk):
    data = {"type": "Bundle", "spec": "UP/0.1-draft", "terms": EXAMPLES["overlay"]["terms"], "chains": [[junk]] if isinstance(junk, dict) else []}
    try:
        b = Bundle(data)
    except Exception:
        return  # not canonicalizable; the CLI reports this as an input error
    ev = Evaluator(b)
    for cid in b.chains:
        assert not ev.run(cid)[0].accepted


def test_bundle_order_of_keys_does_not_change_any_hash_or_verdict():
    data = EXAMPLES["conventional"]

    def reverse(x):
        if isinstance(x, dict):
            return {k: reverse(x[k]) for k in reversed(list(x))}
        if isinstance(x, list):
            return [reverse(v) for v in x]
        return x

    a, b = Evaluator(Bundle(data)), Evaluator(Bundle(reverse(data)))
    for cid in a.b.chains:
        assert [(s.event_hash, s.accepted, content_hash(s.state) if s.state else None) for s in a.run(cid)] == \
               [(s.event_hash, s.accepted, content_hash(s.state) if s.state else None) for s in b.run(cid)]


# ---- command line ---------------------------------------------------------------------

def _up(*args):
    """Run the CLI in-process (so coverage sees it), from the repository root."""
    out, err = io.StringIO(), io.StringIO()
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(args))
    finally:
        os.chdir(cwd)
    return types.SimpleNamespace(returncode=code, stdout=out.getvalue(), stderr=err.getvalue())


def test_cli_entry_point_runs_as_a_module():
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    r = subprocess.run([sys.executable, "-m", "universal_paper", "validate", "examples/overlay/bundle.json"],
                       capture_output=True, text=True, cwd=ROOT, env=env)
    assert r.returncode == 0 and "Every event is valid." in r.stdout


def test_cli_commands_run_on_the_examples(tmp_path):
    assert _up("validate", "examples/conventional/bundle.json").returncode == 0
    assert _up("validate", "examples/generative/bundle.json").returncode == 2  # two out-of-bounds agent actions
    d = _up("derive", "examples/conventional/bundle.json", "--at", "2027-04-30T00:00:00Z")
    assert d.returncode == 0 and json.loads(d.stdout)
    r = _up("render", "examples/confidential/bundle.json", "--chain", "0", "--hashes-only")
    assert r.returncode == 0 and "[sealed sha256:" in r.stdout
    out = tmp_path / "t.json"
    assert _up("trace", "examples/overlay/bundle.json", "-o", str(out)).returncode == 0 and json.loads(out.read_text())
    sim = tmp_path / "events.json"
    sim.write_text(json.dumps([{"chain": 0, "kind": "attest", "by": EXAMPLES["conventional"]["chains"][0][0]["by"],
                                "at": "2027-05-01T00:00:00Z", "body": {"claim": {"type": "UP:Nope/x", "clause": "fee", "data": {}}}}]))
    s = _up("simulate", "examples/conventional/bundle.json", str(sim))
    assert s.returncode == 0 and json.loads(s.stdout)
    ev_file = tmp_path / "e.json"
    ev_file.write_text(json.dumps(EXAMPLES["overlay"]["chains"][0][0]))
    a = _up("apply", "examples/overlay/bundle.json", str(ev_file))
    assert a.returncode == 2 and "already starts a chain" in a.stderr  # applying it would fork the chain
    h = _up("hash", "spec/06-terms/UP-Notices.json")
    assert h.stdout.strip() == content_hash(json.loads((ROOT / "spec/06-terms/UP-Notices.json").read_text()))


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', "{not json", '{"n": NaN}', "[1, 2", '{"chains": [[1]]}', '{"chains": "x"}', "﻿{}"])
def test_cli_reports_bad_input_without_a_traceback(tmp_path, text):
    p = tmp_path / "bad.json"
    p.write_text(text, encoding="utf-8")
    for cmd in (["validate", str(p)], ["derive", str(p)], ["hash", str(p)], ["render", str(p)]):
        r = _up(*cmd)
        assert r.returncode in (0, 1, 2) and "Traceback" not in r.stderr, (cmd, r.stderr)
        if r.returncode == 1:
            assert r.stderr.startswith("up: error:")


def test_cli_missing_file_and_unknown_chain(tmp_path):
    r = _up("validate", str(tmp_path / "nope.json"))
    assert r.returncode == 1 and "cannot read" in r.stderr
    r = _up("render", "examples/overlay/bundle.json", "--chain", "sha256:" + "0" * 64)
    assert r.returncode == 1 and "no chain" in r.stderr
