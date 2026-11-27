"""The read-only MCP server (src/universal_paper/mcp_server.py): its tools agree with the CLI and engine."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from universal_paper import mcp_server as m
from universal_paper.__main__ import InputError
from universal_paper.canon import content_hash

EX = Path(__file__).resolve().parents[1] / "examples"


def bundle(name: str) -> dict:
    return json.loads((EX / name / "bundle.json").read_text(encoding="utf-8"))


def test_validate_conventional_is_valid_from_object_text_and_path():
    path = str(EX / "conventional" / "bundle.json")
    for given in (bundle("conventional"), Path(path).read_text(encoding="utf-8"), path):
        r = m.validate_bundle(given)
        assert r["valid"] and r["rejected_events"] == 0 and r["chains"]


def test_validate_reports_out_of_mandate_agent_actions():
    r = m.validate_bundle(bundle("generative"))
    reasons = [e["reason"] for c in r["chains"] for e in c["events"] if not e["accepted"]]
    assert r["valid"] is False and r["rejected_events"] == 2
    assert all("out of bounds" in x for x in reasons)


def test_check_event_matches_engine_and_writes_nothing():
    data = bundle("conventional")
    before = json.dumps(data, sort_keys=True)
    chain = data["chains"][0]
    # Re-applying the last event to the final state must be rejected (its prev hash no longer matches).
    r = m.check_event(data, chain[-1])
    assert r["accepted"] is False and r["reason"]
    assert json.dumps(data, sort_keys=True) == before


def test_derive_render_hash_terms_examples():
    data = bundle("conventional")
    assert m.derive_state(data)["chains"]
    text = m.render_text(data, chain=0)
    assert "Agreement hash: sha256:" in text
    assert m.hash_object({"b": 1, "a": [2]}) == content_hash({"a": [2], "b": 1})
    ids = {t["id"] for t in m.list_terms()}
    assert "UP:Admin-Fee" in ids
    assert m.explain_term("UP-Admin-Fee")["id"] == "UP:Admin-Fee"
    assert m.get_example("overlay") == bundle("overlay")
    assert m.simulate_events(data, [])


@pytest.mark.parametrize("call", [
    lambda: m.explain_term("UP:Nope"),
    lambda: m.get_example("nope"),
    lambda: m.render_text(bundle("conventional"), chain=99),
    lambda: m.validate_bundle("/no/such/file.json"),
    lambda: m.validate_bundle('{"a": 1, "a": 2}'),
])
def test_bad_input_is_an_input_error(call):
    with pytest.raises(InputError):
        call()


def test_server_lists_every_tool_as_read_only():
    pytest.importorskip("mcp")
    import anyio

    server = m.build_server()

    async def tools():
        return await server.list_tools()

    listed = anyio.run(tools)
    names = {t.name for t in listed}
    assert names == {"validate_bundle", "derive_state", "check_event", "simulate_events", "render_text",
                     "hash_object", "list_terms", "explain_term", "get_example", "simulate_amendment",
                     "simulate_price_conformity", "simulate_termination", "simulate_eligibility"}
    for t in listed:
        ann = t.annotations
        assert getattr(ann, "read_only_hint", getattr(ann, "readOnlyHint", None)) is True


def test_every_tool_has_a_title_on_the_tool_and_in_its_annotations():
    """Clients show the title to people in place of the function name, and directories require one."""
    pytest.importorskip("mcp")
    import anyio

    assert set(m.TOOL_TITLES) == set(m.TOOL_DOCS)
    assert len(set(m.TOOL_TITLES.values())) == len(m.TOOL_TITLES)
    for t in anyio.run(m.build_server().list_tools):
        title = m.TOOL_TITLES[t.name]
        assert 3 <= len(title) <= 40 and title[0].isupper() and not title.endswith(".")
        assert getattr(t.annotations, "title", None) == title, t.name
        if hasattr(t, "title"):  # SDKs with tool titles
            assert t.title == title, t.name


def test_hosted_mode_refuses_file_paths_and_local_mode_restores_them():
    pytest.importorskip("mcp")
    path = str(EX / "conventional" / "bundle.json")
    m.build_server(hosted=True)
    try:
        with pytest.raises(InputError, match="does not read file paths"):
            m.validate_bundle(path)
        assert m.validate_bundle(bundle("conventional"))["valid"]
    finally:
        m.build_server()
    assert m.validate_bundle(path)["valid"]


def test_hosted_endpoint_is_stateless_and_counts_only_tool_names():
    pytest.importorskip("mcp")
    pytest.importorskip("httpx")
    from starlette.testclient import TestClient

    from universal_paper import mcp_http

    usage = mcp_http.Usage()
    headers = {"accept": "application/json, text/event-stream", "content-type": "application/json",
               "mcp-protocol-version": "2025-06-18", "host": "mcp.universalpaper.org"}
    try:
        with TestClient(mcp_http.create_app(usage), base_url="https://mcp.universalpaper.org") as c:
            assert c.get("/healthz").json() == {"ok": True}
            assert c.get("/").json()["endpoint"] == "/mcp"
            init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
            r = c.post("/mcp", json=init, headers=headers)
            assert r.status_code == 200 and "mcp-session-id" not in r.headers  # stateless: no sessions
            secret = json.dumps(bundle("confidential"))
            call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "validate_bundle", "arguments": {"bundle": secret}}}
            out = c.post("/mcp", json=call, headers=headers).json()["result"]
            assert not out.get("isError") and json.loads(out["content"][0]["text"])["valid"]
            bad = {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                   "params": {"name": "validate_bundle", "arguments": {"bundle": "/etc/passwd"}}}
            assert c.post("/mcp", json=bad, headers=headers).json()["result"]["isError"]
            stats = c.get("/stats").json()
    finally:
        m.build_server()
    assert stats["calls"] == {"validate_bundle": 2} and stats["errors"] == {"validate_bundle": 1}
    assert "Supplier" not in json.dumps(stats) and secret[:40] not in json.dumps(stats)


def test_release_versions_agree():
    import tomllib

    root = EX.parent
    core = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    pkg = tomllib.loads((root / "packages/universal-paper-mcp/pyproject.toml").read_text(encoding="utf-8"))["project"]
    server = json.loads((root / "server.json").read_text(encoding="utf-8"))
    from universal_paper import __version__

    v = core["version"]
    assert __version__ == pkg["version"] == server["version"] == server["packages"][0]["version"] == v
    assert f"universal-paper[mcp]=={v}" in pkg["dependencies"]
    assert server["packages"][0]["identifier"] == pkg["name"]
    readme = (root / "packages/universal-paper-mcp/README.md").read_text(encoding="utf-8")
    assert f"mcp-name: {server['name']} -->" in readme
    assert len(server["description"]) <= 100


def test_simulate_amendment_blocks_an_agent_past_its_mandate_cap():
    out = m.simulate_amendment("example:mandate-cap", "price", "factor", 1.05)
    assert out["accepted"] is False and out["change"]["to"] == "1.05"
    assert "above the maximum 1.02" in out["reason"] and out["failed_checks"][0]["rule"] == "A9"
    inside = m.simulate_amendment(bundle("mandate-cap"), "price", "factor", "1.015")
    assert inside["accepted"] is True and inside["reason"] is None
    with pytest.raises(InputError, match="no clause"):
        m.simulate_amendment("example:mandate-cap", "fee", "rate", "0.05")
    assert m.validate_bundle("example:mandate-cap")["valid"]


# ---- what-if tools on example:what-if (master 0; member 1 active in tier B; member 2 left; member 3 unsigned) ----

GTIN17, GTIN24 = "00000000000017", {"scheme": "GTIN", "id": "00000000000024"}


def test_simulate_price_conformity_checks_prices_against_the_tier_in_effect():
    data = bundle("what-if")
    before = json.dumps(data, sort_keys=True)
    ok = m.simulate_price_conformity(data, 1, [{"item": GTIN17, "price": "9.40"},
                                              {"item": GTIN24, "price": {"value": "21.75", "currency": "USD"}}])
    assert ok["conforms"] is True and ok["tier"]["applied"] == "B"
    assert ok["prices"][0]["contract"] == {"value": "9.40", "currency": "USD"}
    assert ok["prices"][0]["by_tier"]["A"]["value"] == "9.10"
    off = m.simulate_price_conformity(data, 1, [{"item": GTIN17, "price": 9.8}])
    assert off["conforms"] is False and off["prices"][0]["difference"]["value"] == "0.40"
    assert "above" in off["reason"] and "tier C price" in off["reason"]
    assert json.dumps(data, sort_keys=True) == before


def test_simulate_price_conformity_tier_change_and_refusals():
    r = m.simulate_price_conformity("example:what-if", 1, [{"item": GTIN17, "price": "9.10"}], tier="A")
    assert r["conforms"] and r["tier"]["change"]["accepted"] and r["tier"]["applied"] == "A"
    bad = m.simulate_price_conformity("example:what-if", 1, [{"item": GTIN17, "price": "9.10"}], tier="Z")
    assert bad["conforms"] is False and "not one of the named options" in bad["reason"]
    left = m.simulate_price_conformity("example:what-if", 2, [{"item": GTIN17, "price": "9.80"}])
    assert left["conforms"] is False and "terminated" in left["reason"]
    unknown = m.simulate_price_conformity("example:what-if", 1, [{"item": "99", "price": "1.00"}])
    assert unknown["conforms"] is False and "not priced" in unknown["reason"]
    eur = m.simulate_price_conformity("example:what-if", 1, [{"item": GTIN17, "price": {"value": "9.40", "currency": "EUR"}}])
    assert eur["conforms"] is False and "EUR" in eur["reason"]
    with pytest.raises(InputError):
        m.simulate_price_conformity("example:what-if", 0, [{"item": GTIN17, "price": "9.40"}])  # the master is not a participation


def test_simulate_termination_convenience_cause_and_cure_period():
    now = m.simulate_termination("example:what-if", 0, "aggregator")
    assert now["allowed"] and now["clause"] == "exit" and now["effective_at"] == "2027-05-30T09:00:00Z"
    cause = next(o for o in now["options"] if o["clause"] == "cause")
    assert cause["allowed"] is False and "2027-03-31T09:00:00Z" in cause["cure"]
    assert [p["chain"] for p in next(o for o in now["options"] if o["clause"] == "exit")["affected_participations"]] == [1]
    later = m.simulate_termination("example:what-if", 0, "aggregator", at="2027-03-31T09:00:00Z", clause="cause")
    assert later["allowed"] and later["effective_at"] == "2027-04-30T09:00:00Z"
    assert later["options"][0]["fees_still_owed"]
    member = m.simulate_termination("example:what-if", 1, "Hypothetical Community Hospital")
    assert member["allowed"] and member["effective_at"] == "2027-03-31T09:00:00Z"
    no = m.simulate_termination("example:what-if", 1, "supplier")
    assert no["allowed"] is False and "No termination clause lets the supplier" in no["reason"]
    gone = m.simulate_termination("example:what-if", 2, "member")
    assert gone["allowed"] is False and "already terminated" in gone["reason"]
    with pytest.raises(InputError):
        m.simulate_termination("example:what-if", 0, "member")


def test_simulate_eligibility_active_left_unsigned_unknown():
    yes = m.simulate_eligibility("example:what-if", "HYP000001")
    assert yes["eligible"] is True and yes["participations"][0]["tier"] == "B"
    left = m.simulate_eligibility("example:what-if", "Sample Regional Clinic")
    assert left["eligible"] is False and "terminated" in left["reason"]
    before = m.simulate_eligibility("example:what-if", "Sample Regional Clinic", at="2027-02-01T00:00:00Z")
    assert before["eligible"] is True
    unsigned = m.simulate_eligibility("example:what-if", "Hypothetical Rural Hospital")
    assert unsigned["eligible"] is False and "supplier" in unsigned["reason"]
    nobody = m.simulate_eligibility("example:what-if", "Nobody")
    assert nobody["eligible"] is False and nobody["participations"] == []
    after_master_ends = m.simulate_eligibility("example:what-if", "HYP000001", at="2029-06-01T00:00:00Z")
    assert after_master_ends["eligible"] is False


def test_what_if_tools_reject_bad_times_and_roles_and_respect_seals():
    assert m.validate_bundle("example:what-if")["valid"]
    for call in (lambda: m.simulate_eligibility("example:what-if", "HYP000001", at="tomorrow"),
                 lambda: m.simulate_price_conformity("example:what-if", 1, [{"item": GTIN17, "price": "9.40"}], at="2027-13-01"),
                 lambda: m.simulate_termination("example:what-if", 0, "supplier", at="soon"),
                 lambda: m.simulate_eligibility("example:what-if", "member")):  # a role names no one member
        with pytest.raises(InputError):
            call()
    notice = m.simulate_eligibility("example:what-if", "Sample Regional Clinic", at="2027-02-10T00:00:00Z")
    assert notice["eligible"] is True and "Notice of termination has been given" in notice["reason"]
    hidden = bundle("confidential")
    hidden["disclosures"] = []
    sealed = m.simulate_price_conformity(hidden, 1, [{"item": GTIN17, "price": "9.10"}])
    assert sealed["conforms"] is False and "sealed" in sealed["reason"]
    assert m.simulate_price_conformity(bundle("confidential"), 1, [{"item": GTIN17, "price": "9.10"}])["conforms"] is True


def test_what_if_answers_are_deterministic():
    data = bundle("what-if")
    for call in (lambda d: m.simulate_termination(d, 0, "aggregator"),
                 lambda d: m.simulate_price_conformity(d, 1, [{"item": GTIN17, "price": "9.80"}], tier="A"),
                 lambda d: m.simulate_eligibility(d, "HYP000003")):
        assert json.dumps(call(data), sort_keys=True) == json.dumps(call(json.loads(json.dumps(data))), sort_keys=True)


def test_every_tool_and_parameter_is_described_for_agents():
    """Each tool says when to use it over a named sibling; each parameter's schema carries a description."""
    pytest.importorskip("mcp")
    import inspect

    import anyio

    assert set(m.TOOL_DOCS) == set(m.PARAM_DOCS)
    for name, docs in m.PARAM_DOCS.items():
        assert set(docs) == set(inspect.signature(getattr(m, name)).parameters), name

    listed = anyio.run(m.build_server().list_tools)
    assert {t.name for t in listed} == set(m.TOOL_DOCS)
    for t in listed:
        schema = getattr(t, "input_schema", None) or t.inputSchema
        for param, spec in schema.get("properties", {}).items():
            assert len(spec.get("description", "")) >= 30, f"{t.name}.{param} has no useful description"
        assert set(schema.get("properties", {})) == set(m.PARAM_DOCS[t.name])
        siblings = [other for other in m.TOOL_DOCS if other != t.name and other in t.description]
        assert siblings, f"{t.name} names no sibling tool to choose between"
    # Scope decisions: no volume thresholds for tiers, no net-new-business, no early-termination fee.
    text = " ".join(m.TOOL_DOCS.values()) + " ".join(d for p in m.PARAM_DOCS.values() for d in p.values())
    text += " " + " ".join(m.TOOL_TITLES.values())
    for banned in ("net new", "net-new", "early termination fee", "threshold"):
        assert banned not in text.lower()
