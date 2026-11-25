"""The machine-readable index of OPTIONAL integrations (site/build_site.py -> /integrations/index.json).

Not part of the language. These tests only keep the index honest: every helper, example and MCP tool
it names exists, and the claim shapes it publishes accept the repository's own example payloads.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))
try:
    import markdown  # noqa: F401
except ImportError:  # the index needs no Markdown; the site build does
    sys.modules["markdown"] = types.ModuleType("markdown")

import build_site  # noqa: E402

from universal_paper.canon import content_hash  # noqa: E402


class _Args:
    domain = "universalpaper.org"
    repo_url = "https://github.com/Uppercentile/universal-paper"
    out = "unused"
    repo = str(ROOT)


SITE = build_site.Site(_Args())
INDEX = build_site.integrations_index(SITE)
BY_ID = {i["id"]: i for i in INDEX["integrations"]}
SERVER = (ROOT / "src/universal_paper/mcp_server.py").read_text(encoding="utf-8")


def served(url: str) -> Path:
    """Where the site build copies a served example from (examples/... in the repository)."""
    assert url.startswith("https://universalpaper.org/examples/integrations/")
    return ROOT / url.removeprefix("https://universalpaper.org/")


def test_index_is_plain_json_and_lists_every_integration():
    json.loads(json.dumps(INDEX))
    assert [i["id"] for i in INDEX["integrations"]] == [slug for _, slug, _, _ in build_site.INTEGRATIONS]
    assert all(i["status"] == "optional" for i in INDEX["integrations"])
    assert "does not depend" in INDEX["notice"]


def test_docs_helpers_and_examples_exist():
    for f, slug, _, _ in build_site.INTEGRATIONS:
        item = BY_ID[slug]
        assert (ROOT / f).is_file()
        assert item["docs"]["markdown"].endswith(f"/integrations/{slug}.md")
        assert (ROOT / item["helper"]["path"]).is_file()
        assert item["helper"]["functions"], "the helper's public functions are read from the file"
        for ex in item["examples"]:
            assert served(ex["url"]).is_file(), ex["url"]


def test_helper_functions_match_the_files():
    names = {i["id"]: {f["name"] for f in i["helper"]["functions"]} for i in INDEX["integrations"]}
    assert {"fingerprint", "canonical_bytes", "legal_context", "verify", "discover", "fetch", "evaluate", "check_mandate"} <= names["legal-context-protocol"]
    assert names["verifiable-credentials"] == {"roster_participation", "role_proof", "extract"}
    assert {"fingerprint", "inputs_root", "contribution", "diff_bundles", "derive_profile", "verify_profile",
            "extract_seeds", "seed_proposal", "simulate_seed"} <= names["fingerprint-coordination"]


def test_mcp_tools_named_exist():
    for item in INDEX["integrations"]:
        for tool in item["mcpTools"]:
            assert f"\ndef {tool}(" in SERVER, tool


def test_claim_shapes_accept_the_examples():
    vc = BY_ID["verifiable-credentials"]["claimShapes"]
    for name, shape in (("roster-participation.json", "ParticipationStatusCredential"), ("role-proof.json", "RoleCredential")):
        doc = json.loads((ROOT / "examples/integrations/vc" / name).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(vc[shape])
        jsonschema.validate(doc, vc[shape])
        other = "RoleCredential" if shape != "RoleCredential" else "ParticipationStatusCredential"
        assert not jsonschema.Draft202012Validator(vc[other]).is_valid(doc)
    lcp = BY_ID["legal-context-protocol"]["claimShapes"]["legal-context.json"]
    jsonschema.Draft202012Validator.check_schema(lcp)
    for d in sorted((ROOT / "examples/integrations/lcp").glob("*/legal-context.json")):
        doc = json.loads(d.read_text(encoding="utf-8"))
        jsonschema.validate(doc, lcp)
        terms = (d.parent / "terms.up.json").read_bytes()
        assert doc["atrHash"][2:] == content_hash(json.loads(terms)).removeprefix("sha256:")


def test_claim_shapes_reject_a_bad_fingerprint():
    shape = BY_ID["verifiable-credentials"]["claimShapes"]["RoleCredential"]
    doc = json.loads((ROOT / "examples/integrations/vc/role-proof.json").read_text(encoding="utf-8"))
    doc["credentialSubject"]["agreementFingerprint"] = "0x" + "a" * 64
    assert not jsonschema.Draft202012Validator(shape).is_valid(doc)


def test_fingerprint_coordination_shapes_and_demo():
    item = BY_ID["fingerprint-coordination"]
    fpc = ROOT / "examples/integrations/fingerprint-coordination"
    shapes = item["claimShapes"]
    for shape, name in (("FingerprintContribution", "contribution.json"), ("DerivedProfile", "demo-profile.json")):
        doc = json.loads((fpc / name).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(shapes[shape])
        jsonschema.validate(doc, shapes[shape])
        assert shapes[shape] == json.loads((fpc / "schemas" / (name.split(".")[0].replace("demo-profile", "derived-profile") + ".schema.json")).read_text(encoding="utf-8"))
    assert item["demo"]["url"] == "https://universalpaper.org/integrations/fingerprint-coordination/demo/"
    assert item["demo"]["simulated"] is True and item["external"] is None
    sc = json.loads((fpc / "demo/scenario.json").read_text(encoding="utf-8"))
    assert item["demo"]["scenario"]["url"] == "https://universalpaper.org/integrations/fingerprint-coordination/demo/scenario.json"
    assert item["demo"]["scenario"]["howToSteps"] == [s["id"] for s in sc["steps"]]
    assert item["demo"]["scenario"]["fingerprint"] == sc["fingerprint"]
