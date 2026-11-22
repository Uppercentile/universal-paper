import json

from universal_paper.simulate import simulate
from universal_paper.trace import make_trace

from build_examples import conventional, generative, tamper_drop_signature, tamper_fee_rate


def test_simulation_runs_hypothetical_tier_change_forward():
    w, actors, at = conventional()
    d = w.data()
    m2, sup = actors["m2"], actors["sup"]
    res = simulate(d, [
        {"chain": 2, "kind": "attest", "by": m2.pub, "at": "2027-05-01T00:00:00Z",
         "body": {"claim": {"type": "UP:Tier-Selection/selects", "clause": "tier", "data": {"option": "C", "basis": "what if"}}},
         "cosigners": [sup.pub]},
    ], at="2027-05-02T00:00:00Z")
    assert res["hypothetical"] and res["steps"][0]["accepted"]
    p2 = next(c for c in res["final"]["chains"] if c["chain"] == 2)
    assert p2["selections"][m2.pub] == "C"
    assert p2["prices"][0]["price"] == {"value": "9.80", "currency": "USD"}
    assert len(w.data()["chains"][2]) == len(d["chains"][2])  # the real bundle is untouched


def test_simulation_still_enforces_mandates():
    w, actors, at = generative()
    d = w.data()
    hosp = actors["hosp"]
    m = d["mandates"][1]
    from universal_paper.canon import content_hash
    res = simulate(d, [{"chain": 3, "kind": "attest", "by": hosp.pub, "at": "2027-02-10T00:00:00Z",
                        "body": {"claim": {"type": "UP:Tier-Selection/selects", "clause": "tier", "data": {"option": "C", "basis": "x"}}},
                        "agent": {"key": m["agent"], "mandate": content_hash(m)}}])
    assert not res["steps"][0]["accepted"] and "out of bounds" in res["steps"][0]["reason"]


def _evals(d):
    return [{"id": i, "name": i, "data": d} for i in ("a", "b", "c")]


def test_clean_trace_has_consensus_at_every_step():
    w, _, at = conventional()
    d = w.data()
    t = make_trace(d, _evals(d), {}, at)
    assert all(s["consensus"] for s in t["steps"])
    assert all(r["accepted"] for s in t["steps"] for r in s["results"].values())


def test_tampered_evaluator_diverges_and_others_agree():
    w, _, at = conventional()
    d = w.data()
    for variant, who in ((tamper_fee_rate(d), "b"), (tamper_drop_signature(d, 0, 1), "a")):
        ev = _evals(d)
        idx = [e["id"] for e in ev].index(who)
        ev[idx] = {**ev[idx], "data": variant, "tampered": "test"}
        t = make_trace(d, ev, {}, at)
        assert not all(s["consensus"] for s in t["steps"])
        honest = [e["id"] for e in ev if e["id"] != who]
        for s in t["steps"]:
            assert len({s["results"][h]["world_hash"] for h in honest}) == 1
        assert s["results"][who]["world_hash"] != s["results"][honest[0]]["world_hash"]


def test_shipped_traces_validate_against_schema():
    import glob

    import jsonschema
    tr = json.load(open("schema/trace.schema.json"))
    files = glob.glob("examples/traces/*.trace.json")
    assert len(files) >= 6
    for f in files:
        jsonschema.validate(json.load(open(f)), tr)


def test_states_and_bundles_validate_against_schema():
    import jsonschema

    from universal_paper.engine import Evaluator
    up = json.load(open("schema/universal-paper.schema.json"))
    w, _, _ = conventional()
    jsonschema.validate(w.data(), up)
    e = Evaluator(w.bundle())
    for pos in range(len(w.chains)):
        for st in e.run(w.chain_id(pos)):
            jsonschema.validate(st.state, {**up, "oneOf": [{"$ref": "#/$defs/State"}]})


def test_committed_example_bundles_match_a_fresh_build():
    import build_examples as b
    for name, fn in (("conventional", b.conventional), ("generative", b.generative), ("overlay", b.overlay)):
        w, _, _ = fn()
        assert json.load(open(f"examples/{name}/bundle.json")) == json.loads(json.dumps(w.data())), name
