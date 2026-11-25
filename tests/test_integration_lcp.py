"""The OPTIONAL Legal Context Protocol adapter (integrations/lcp/) and its examples. Not part of the language.

These tests check only that the adapter reuses the existing fingerprint exactly; nothing in the
core depends on them.
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integrations" / "lcp"))

import up_lcp  # noqa: E402

from universal_paper.canon import content_hash, jcs  # noqa: E402

EX = ROOT / "examples"
LCP_EX = EX / "integrations" / "lcp"


def bundle(name: str) -> dict:
    return json.loads((EX / name / "bundle.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["conventional", "mandate-cap", "confidential", "overlay"])
def test_atr_hash_of_canonical_bytes_is_the_up_fingerprint(name):
    b = bundle(name)
    raw = up_lcp.canonical_bytes(b)
    assert raw == jcs(b)
    assert up_lcp.fingerprint(b) == content_hash(b)
    assert "0x" + hashlib.sha256(raw).hexdigest() == up_lcp.to_atr_hash(content_hash(b))
    doc = up_lcp.legal_context("https://example.org/terms.up.json", b)
    assert set(doc) == {"terms", "termsFormat", "atrHash"} and len(doc["atrHash"]) == 66
    v = up_lcp.verify(doc, raw)
    assert v.ok and v.atr_hash_matches and v.canonical and v.fingerprint == content_hash(b) and v.up_type == "Bundle"
    assert v.chain_ids == [content_hash(ch[0]) for ch in b["chains"]]


def test_term_definition_fingerprint_is_its_def_hash():
    term = json.loads((ROOT / "spec/06-terms/UP-Admin-Fee.json").read_text(encoding="utf-8"))
    defs = {c["def"] for ch in bundle("conventional")["chains"] for E in ch[:1] for c in E["body"]["agreement"]["clauses"] if c["term"] == "UP:Admin-Fee"}
    assert defs == {up_lcp.fingerprint(term)}
    assert up_lcp.verify(up_lcp.legal_context("https://example.org/t.json", term), up_lcp.canonical_bytes(term)).ok


def test_hash_notations_compare_by_bytes():
    fp = "sha256:" + "ab" * 32
    assert up_lcp.to_atr_hash(fp) == "0x" + "ab" * 32
    assert up_lcp.to_up_fingerprint("0x" + "AB" * 32) == fp
    assert up_lcp.same_hash("0x" + "AB" * 32, fp) and up_lcp.same_hash("sha256:0x" + "ab" * 32, fp)
    with pytest.raises(ValueError):
        up_lcp.to_atr_hash("sha256:abc")


def test_verify_rejects_tampered_noncanonical_and_unpinned():
    b = bundle("conventional")
    doc = up_lcp.legal_context("https://example.org/terms.up.json", b)
    raw = up_lcp.canonical_bytes(b)
    tampered = raw.replace(b'"rate":"0.02"', b'"rate":"0.03"')
    assert tampered != raw
    v = up_lcp.verify(doc, tampered)
    assert not v.ok and not v.atr_hash_matches and v.canonical
    pretty = json.dumps(b, indent=2).encode()
    v = up_lcp.verify({**doc, "atrHash": "0x" + hashlib.sha256(pretty).hexdigest()}, pretty)
    assert not v.ok and v.atr_hash_matches and not v.canonical  # LCP-valid, but not the UP fingerprint
    assert not up_lcp.verify({"terms": doc["terms"]}, raw).ok  # Level 1: nothing pinned
    assert not up_lcp.verify(doc, raw, expected_fingerprint="sha256:" + "00" * 32).ok


def test_signed_objects_and_bad_urls_are_refused():
    event = bundle("conventional")["chains"][0][0]
    with pytest.raises(ValueError, match="Bundle"):
        up_lcp.canonical_bytes(event)
    with pytest.raises(ValueError, match="https"):
        up_lcp.legal_context("http://example.org/terms.json", bundle("conventional"))


def test_evaluate_and_mandate_check_reuse_the_engine():
    assert up_lcp.evaluate(bundle("conventional"))["valid"]
    assert up_lcp.evaluate(bundle("generative"))["valid"] is False  # two out-of-Mandate agent events, by design
    b = bundle("mandate-cap")
    m = b["mandates"][0]
    cid = content_hash(b["chains"][0][0])
    from universal_paper.engine import Bundle, Evaluator
    ev = Evaluator(Bundle(b))
    cur = ev.agreement(ev.state_at(cid))
    results = {}
    for f in ("1.02", "1.05"):
        ag = copy.deepcopy(cur)
        next(c for c in ag["clauses"] if c["n"] == "price")["params"]["factor"] = f
        results[f] = up_lcp.check_mandate(b, {"chain": 0, "kind": "propose", "by": m["principal"], "at": "2026-12-02T10:00:00Z",
                                              "body": {"agreement": ag, "supersedes": content_hash(cur)},
                                              "agent": {"key": m["agent"], "mandate": content_hash(m)}})
    assert results["1.02"]["accepted"] and not results["1.05"]["accepted"] and "1.02" in results["1.05"]["reason"]


@pytest.mark.parametrize("name", ["conventional", "mandate-cap"])
def test_committed_example_files_are_self_consistent(name):
    lcp = json.loads((LCP_EX / name / "legal-context.json").read_text(encoding="utf-8"))
    raw = (LCP_EX / name / "terms.up.json").read_bytes()
    assert lcp["terms"] == f"https://universalpaper.org/examples/integrations/lcp/{name}/terms.up.json"
    v = up_lcp.verify(lcp, raw)
    assert v.ok, v.problems
    assert up_lcp.evaluate(v.artifact)["valid"]


def test_agent_example_runs_offline():
    r = subprocess.run([sys.executable, str(LCP_EX / "agent.py")], capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert r.returncode == 0, r.stderr
    assert "price factor 1.01: inside the Mandate" in r.stdout and "price factor 1.05: outside the Mandate" in r.stdout
