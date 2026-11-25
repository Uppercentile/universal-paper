"""The OPTIONAL Fingerprint Coordination convention (examples/integrations/fingerprint-coordination/). Not part of the language.

These tests check only that the worked examples are recomputable from the public bundles, that the helper reuses the
Universal Paper fingerprint exactly, that privacy defaults hold, and that seeds are what the engine says. Nothing in
the core depends on them.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
FPC = ROOT / "examples" / "integrations" / "fingerprint-coordination"
sys.path.insert(0, str(FPC))

import regenerate  # noqa: E402
import up_fpc  # noqa: E402

from universal_paper.canon import content_hash  # noqa: E402

INPUTS = regenerate.load_inputs()
PROFILE = json.loads((FPC / "demo-profile.json").read_text(encoding="utf-8"))
SCHEMA = {n: json.loads((FPC / "schemas" / f"{n}.schema.json").read_text(encoding="utf-8")) for n in ("contribution", "derived-profile")}


def test_worked_examples_have_not_drifted():
    assert regenerate.main(["--check"]) == 0


def test_demo_embeds_exactly_the_profile_and_makes_no_network_calls():
    page = (FPC / "demo/index.html").read_text(encoding="utf-8")
    embedded = re.search(r'<script type="application/json" id="profile">(.*?)</script>', page, re.S).group(1)
    assert json.loads(embedded.replace("<\\/", "</")) == PROFILE
    assert not re.search(r"""(src|href)=["']https?://(?!universalpaper\.org/integrations/)""", page)
    assert "fetch(" not in page and "XMLHttpRequest" not in page
    assert "Simulated demonstration" in page and "public example" in page


def test_fingerprints_are_the_universal_paper_rule():
    body = {k: v for k, v in PROFILE.items() if k != "fingerprint"}
    assert PROFILE["fingerprint"] == content_hash(body) == up_fpc.fingerprint(body)
    assert up_fpc.check_fingerprint(PROFILE)
    tampered = copy.deepcopy(PROFILE)
    tampered["seeds"][0]["change"]["to"] = "0.01"
    assert not up_fpc.check_fingerprint(tampered)
    fps = [i["fingerprint"] for i in PROFILE["inputs"]]
    assert fps == [content_hash(i["data"]) for i in INPUTS]
    assert PROFILE["inputsRoot"] == content_hash(sorted(fps)) == up_fpc.inputs_root(list(reversed(fps)))


def test_profile_is_recomputable_and_detects_wrong_inputs():
    assert up_fpc.verify_profile(PROFILE, INPUTS)["ok"]
    assert not up_fpc.verify_profile(PROFILE, INPUTS[:-1])["ok"]
    swapped = [*INPUTS[:-1], {**INPUTS[0], "label": "x"}]
    assert not up_fpc.verify_profile(PROFILE, swapped)["ok"]


def test_shapes_validate_against_the_schemas():
    for name, doc in (("contribution", json.loads((FPC / "contribution.json").read_text(encoding="utf-8"))), ("derived-profile", PROFILE)):
        jsonschema.Draft202012Validator.check_schema(SCHEMA[name])
        jsonschema.validate(doc, SCHEMA[name])
    bad = copy.deepcopy(PROFILE)
    bad["inputs"][0]["fingerprint"] = "0x" + "a" * 64
    assert not jsonschema.Draft202012Validator(SCHEMA["derived-profile"]).is_valid(bad)


def test_privacy_defaults():
    # sealed values are counted only as sealed: the confidential hashes-only bundle has 1 fee rate + 9 tier prices sealed
    assert PROFILE["corpus"]["sealedValuesNotCounted"] == 10
    rate = next(p for p in PROFILE["parameters"] if p["key"] == "UP:Admin-Fee.rate")
    assert (rate["sealed"], rate["observations"], rate["median"]) == (1, 5, "0.02")
    # statistics from fewer than minimumCohort distinct inputs carry no values
    for p in PROFILE["parameters"]:
        assert p["suppressed"] == (p["inputs"] < PROFILE["method"]["minimumCohort"])
        if p["suppressed"]:
            assert not {"values", "mode", "median", "min", "max"} & set(p)
    assert any(p["suppressed"] for p in PROFILE["parameters"] if p["term"] == "UP:Termination-Cause")
    # the per-agreement matrix records positions, never raw values
    for m in PROFILE["matrix"]:
        for r in m["rows"]:
            assert all(set(c) <= {"state", "deviation"} for c in r["cells"])
    # default disclosure is fingerprint-only, and it contributes no agreements
    only = up_fpc.derive_profile([{**INPUTS[0], "disclosure": "fingerprint-only"}], simulate_seeds=False)
    assert only["corpus"]["agreements"] == 0 and only["inputs"][0]["disclosure"] == "fingerprint-only"
    c = up_fpc.contribution(contributor="did:example:x", artifacts=[{"fingerprint": PROFILE["inputs"][0]["fingerprint"]}],
                            purposes=["variance"], created="2027-01-01T00:00:00Z")
    assert c["artifacts"][0]["disclosure"] == "fingerprint-only" and c["rules"]["sealedValues"] == "never-counted"
    assert up_fpc.check_fingerprint(c)


def test_seeds_respect_the_spec_decisions():
    for s in PROFILE["seeds"]:
        assert s["change"]["term"] not in up_fpc.NO_SEED_TERMS  # never tiers, tier selection or prices
        assert "recommendation" in s["note"]
    text = json.dumps(PROFILE).lower()
    for phrase in ("net new", "early termination fee", "volume threshold"):
        assert phrase not in text


def test_seed_simulations_are_what_the_engine_says():
    by_fp = {content_hash(i["data"]): i["data"] for i in INPUTS}
    s1, s2 = PROFILE["seeds"]
    assert (s1["rule"], s1["change"]["param"], s1["change"]["from"], s1["change"]["to"]) == ("toward-median", "rate", "0.03", "0.02")
    ch = s1["simulation"]["obligationsChanged"][0]
    assert (ch["before"]["amount"]["value"], ch["after"]["amount"]["value"]) == ("26.06", "17.37")
    assert (s2["rule"], s2["change"]["op"], s2["change"]["term"]) == ("common-clause", "add-clause", "UP:Sales-Reporting")
    assert [o["due"][:10] for o in s2["simulation"]["obligationsAdded"]] == ["2027-02-16", "2027-03-16"]
    for s in (s1, s2):
        bundle = by_fp[s["target"]["input"]]
        again = up_fpc.simulate_seed(bundle, s, library=list(by_fp.values()))
        assert again == s["simulation"] and again["accepted"] is True
        ev = up_fpc.seed_proposal(bundle, s, by="supplier")
        assert content_hash(ev["body"]["agreement"]) == s["simulation"]["newAgreement"]
        assert ev["body"]["supersedes"] == s["target"]["agreement"] and "sigs" not in ev


def test_historical_delta_matches_the_engine():
    (d,) = PROFILE["deltas"]
    assert d["outcome"] == "rejected" and "above the maximum 0.03" in d["reason"]
    assert [(c["param"], c["from"], c["to"], c["delta"]) for c in d["paramsChanged"]] == [("rate", "0.025", "0.035", "0.01")]
    assert PROFILE["deltaStats"] == [{"key": "UP:Admin-Fee.rate", "changes": 1, "accepted": 0, "rejected": 1, "medianDelta": "0.01"}]


def test_structural_diff():
    d = json.loads((FPC / "structural-diff.json").read_text(encoding="utf-8"))
    assert d["termsAdded"] == ["UP:Termination-Cause"]
    assert d["chains"][0]["clausesAdded"] == [{"clause": "cause", "term": "UP:Termination-Cause"}]
    same = up_fpc.diff_agreements(INPUTS[0]["data"]["chains"][0][0]["body"]["agreement"], INPUTS[0]["data"]["chains"][0][0]["body"]["agreement"])
    assert not (same["clausesAdded"] or same["clausesRemoved"] or same["paramsChanged"] or same["otherMembersChanged"])


def test_helper_rejects_bad_input():
    with pytest.raises(ValueError):
        up_fpc.inputs_root(["sha256:abc"])
    with pytest.raises(ValueError):
        up_fpc.contribution(contributor="x", artifacts=[{"fingerprint": PROFILE["inputsRoot"], "disclosure": "everything"}],
                            purposes=["variance"], created="2027-01-01T00:00:00Z")
    with pytest.raises(ValueError):
        up_fpc.contribution(contributor="x", artifacts=[{"fingerprint": PROFILE["inputsRoot"]}], purposes=["resale"], created="t")
    tampered = copy.deepcopy(PROFILE)
    tampered["notice"] = "real data"
    with pytest.raises(ValueError):
        up_fpc.extract_seeds(tampered)
    with pytest.raises(ValueError):
        up_fpc.seed_proposal(INPUTS[0]["data"], PROFILE["seeds"][0], by="supplier")  # wrong bundle for this seed


def test_helper_is_local_only():
    src = (FPC / "up_fpc.py").read_text(encoding="utf-8")
    for mod in ("urllib", "http", "socket", "requests", "httpx", "sqlite3", "open("):
        assert mod not in src, mod
