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
                     "hash_object", "list_terms", "explain_term", "get_example"}
    for t in listed:
        ann = t.annotations
        assert getattr(ann, "read_only_hint", getattr(ann, "readOnlyHint", None)) is True
