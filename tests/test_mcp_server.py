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
                     "hash_object", "list_terms", "explain_term", "get_example", "simulate_amendment"}
    for t in listed:
        ann = t.annotations
        assert getattr(ann, "read_only_hint", getattr(ann, "readOnlyHint", None)) is True


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
