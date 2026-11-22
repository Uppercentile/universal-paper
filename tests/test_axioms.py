"""One or more tests for every axiom (spec/03-axioms.md)."""
import copy
import json

import pytest

from build_examples import conventional, generative, master_clauses
from helpers import AGG, MEM, OTHER, SUP, ev, master, participation, raw
from universal_paper.build import World
from universal_paper.canon import content_hash
from universal_paper.engine import agreement_issues, term_issues
from universal_paper.render import render_agreement
from universal_paper.values import SEALED


# A1 Composition -------------------------------------------------------------

def test_a1_wrong_spec_version_rejected():
    w = World()
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], master_clauses(w), "x")
    A["spec"] = "UP/9.9"
    st = raw(w, None, "propose", AGG, "2026-12-01T00:00:00Z", {"agreement": A})
    assert not st.accepted and "spec" in st.reason


def test_a1_missing_parameter_rejected():
    w = World()
    cl = master_clauses(w)
    del cl[3]["params"]["rate"]
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], cl, "x")
    assert not raw(w, None, "propose", AGG, "2026-12-01T00:00:00Z", {"agreement": A}).accepted


def test_a1_two_windows_and_duplicate_names_rejected():
    w = World()
    cl = master_clauses(w)
    dup = copy.deepcopy(cl[0]); dup["n"] = "term2"
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], cl + [dup], "x")
    assert any("Window" in why for _, why in agreement_issues(w.bundle(), A))
    cl2 = master_clauses(w); cl2[1]["n"] = "term"
    A2 = w.agreement([("aggregator", AGG), ("supplier", SUP)], cl2, "x")
    assert any("unique" in why for _, why in agreement_issues(w.bundle(), A2))


def test_a1_term_id_must_match_pinned_definition():
    w = World()
    cl = master_clauses(w)
    cl[2]["term"] = "UP:Audit"
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], cl, "x")
    assert any("pins" in why for _, why in agreement_issues(w.bundle(), A))


# A2 Unanimity ---------------------------------------------------------------

def test_a2_not_executed_until_every_party_signs():
    w = World()
    a, A, h = master(w, accept=False)
    assert ev(w).state_at(w.chain_id(a))["status"] == "proposed"
    w.accept(a, SUP, h, "2026-12-02T00:00:00Z")
    assert ev(w).state_at(w.chain_id(a))["status"] == "executed"


def test_a2_non_party_cannot_accept():
    w = World()
    a, A, h = master(w, accept=False)
    st = raw(w, a, "accept", OTHER, "2026-12-02T00:00:00Z", {"target": h})
    assert not st.accepted


def test_a2_amendment_needs_old_and_new_parties():
    w = World()
    a, A, _ = master(w)
    A2 = copy.deepcopy(A)
    A2["label"] = "amended"
    _, h2 = w.propose(AGG, A2, "2027-01-01T00:00:00Z", pos=a, supersedes=content_hash(A))
    S = ev(w).state_at(w.chain_id(a))
    assert S["agreement"] == content_hash(A) and S["pending"]
    w.accept(a, SUP, h2, "2027-01-02T00:00:00Z")
    S = ev(w).state_at(w.chain_id(a))
    assert S["agreement"] == content_hash(A2) and "pending" not in S


# A3 Chained transitions -----------------------------------------------------

def test_a3_wrong_prev_rejected():
    w = World()
    a, A, h = master(w)
    st = raw(w, a, "attest", AGG, "2027-01-02T00:00:00Z",
             {"claim": {"type": "UP:Renewing-Term/optout", "clause": "term", "data": {}}}, prev="sha256:" + "1" * 64)
    assert not st.accepted and st.checks[-1].rule == "A3"


def test_a3_genesis_must_be_a_proposal():
    w = World()
    st = raw(w, None, "attest", AGG, "2027-01-02T00:00:00Z", {"claim": {"type": "x", "clause": "y", "data": {}}})
    assert not st.accepted


# A4 Determinism -------------------------------------------------------------

def test_a4_same_chain_same_hashes_twice():
    w1, _, at = conventional()
    w2, _, _ = conventional()
    assert json.dumps(w1.data(), sort_keys=True) == json.dumps(w2.data(), sort_keys=True)
    e1, e2 = ev(w1), ev(w2)
    for pos in range(len(w1.chains)):
        assert content_hash(e1.state_at(w1.chain_id(pos))) == content_hash(e2.state_at(w2.chain_id(pos)))
        assert e1.obligations(w1.chain_id(pos), at) == e2.obligations(w2.chain_id(pos), at)


def test_a4_trace_is_byte_identical_across_runs():
    from universal_paper.trace import make_trace
    w, _, at = conventional()
    d = w.data()
    ts = [json.dumps(make_trace(d, [{"id": "a", "name": "A", "data": d}], {"title": "t"}, at), sort_keys=True) for _ in range(2)]
    assert ts[0] == ts[1]


# A5 Non-retroactivity -------------------------------------------------------

def test_a5_backdated_event_rejected():
    w = World()
    a, A, h = master(w)
    st = raw(w, a, "attest", AGG, "2026-11-01T00:00:00Z",
             {"claim": {"type": "UP:Renewing-Term/optout", "clause": "term", "data": {}}})
    assert not st.accepted and st.checks[-1].rule == "A5"


# A6 Value neutrality --------------------------------------------------------

def test_a6_term_with_default_rejected():
    w = World()
    t = copy.deepcopy(w.terms["UP:Admin-Fee"])
    t["params"]["rate"]["default"] = "0.03"
    assert term_issues(t)
    w.terms["UP:Admin-Fee"] = t
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], master_clauses(w), "x")
    assert any(rule == "A6" for rule, _ in agreement_issues(w.bundle(), A))


def test_a6_no_shipped_term_has_defaults_or_numerals_in_templates():
    import re
    for t in World().terms.values():
        assert not term_issues(t), t["id"]
        assert not re.search(r"\d", re.sub(r"\{\{.*?\}\}", "", t["render"])), t["id"]


# A7 Role symmetry -----------------------------------------------------------

def test_a7_claim_by_wrong_role_rejected():
    w = World()
    a, A, _ = master(w)
    st = raw(w, a, "attest", AGG, "2027-02-10T00:00:00Z", {"claim": {"type": "UP:Sales-Reporting/report", "clause": "reporting",
             "data": {"period": {"start": "2027-01-01T00:00:00Z", "end": "2027-02-01T00:00:00Z"}, "lines": [], "total_net": {"value": "0", "currency": "USD"}}}})
    assert not st.accepted and st.checks[-1].rule == "A7"


def test_a7_terms_name_no_identities():
    for t in World().terms.values():
        assert "ed25519:" not in json.dumps(t)


# A8 Rendering binding -------------------------------------------------------

def test_a8_rendering_is_deterministic_and_tracks_the_hash():
    w = World()
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], master_clauses(w), "x")
    b = w.bundle()
    r1, r2 = render_agreement(b, A), render_agreement(b, copy.deepcopy(A))
    assert r1 == r2 and content_hash(A) in r1
    A2 = copy.deepcopy(A); A2["clauses"][3]["params"]["rate"] = "0.03"
    assert render_agreement(b, A2) != r1 and content_hash(A2) != content_hash(A)


def test_a8_sealed_rendering_binds_the_same_hash():
    w, _, _ = conventional(sealed=True)
    full = w.bundle()
    ag = w.chains[0][0]["body"]["agreement"]
    hidden = w.bundle(); hidden.disclosures = {}
    a, b = render_agreement(full, ag), render_agreement(hidden, ag)
    assert "[sealed sha256:" in b and "[sealed" not in a.split("## Terms")[1].split("### 3")[0]
    assert content_hash(ag) in a and content_hash(ag) in b


# A9 Bounded delegation ------------------------------------------------------

def test_a9_out_of_bounds_agent_actions_rejected_in_generative_example():
    w, _, _ = generative()
    e = ev(w)
    rejected = [st for pos in range(len(w.chains)) for st in e.run(w.chain_id(pos)) if not st.accepted]
    assert len(rejected) == 2
    assert all(st.checks[-1].rule == "A9" for st in rejected)
    assert "'C' is not in the allowed set" in rejected[0].reason or "'C' is not in the allowed set" in rejected[1].reason
    assert any("above the maximum 0.03" in st.reason for st in rejected)


def test_a9_agent_signature_without_mandate_does_not_speak_for_principal():
    from universal_paper.crypto import Key
    w = World()
    a, A, h = master(w, accept=False)
    bot = Key.from_seed("rogue-bot")
    from universal_paper import SPEC
    from universal_paper.crypto import attach
    E = {"type": "Event", "spec": SPEC, "kind": "accept", "at": "2026-12-02T00:00:00Z", "by": SUP.pub,
         "body": {"target": h}, "chain": w.chain_id(a), "prev": content_hash(ev(w).state_at(w.chain_id(a)))}
    w.chains[a].append(attach(E, bot.sign_obj(E)))
    st = ev(w).run(w.chain_id(a))[-1]
    assert not st.accepted


def test_a9_expired_mandate_rejected_and_sealed_bounded_value_rejected():
    from universal_paper.crypto import Key
    w = World()
    bot = Key.from_seed("bot")
    any_ = {"any": True}
    bounds = {c["term"]: {p: any_ for p in c["params"]} for c in master_clauses(w)}
    bounds["UP:Admin-Fee"]["rate"] = {"max": "0.03"}
    m = w.mandate(AGG, bot, "2026-01-01T00:00:00Z", "2026-06-01T00:00:00Z", {"kinds": ["propose"], "roles": ["aggregator"], "terms": bounds})
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], master_clauses(w), "x")
    w.propose(AGG, A, "2026-12-01T00:00:00Z", agent=(bot, m), expect=False)  # expired
    m2 = w.mandate(AGG, bot, "2026-01-01T00:00:00Z", "2027-06-01T00:00:00Z", {"kinds": ["propose"], "roles": ["aggregator"], "terms": bounds})
    w.propose(AGG, A, "2026-12-01T00:00:00Z", agent=(bot, m2))  # in bounds
    sealed = w.agreement([("aggregator", AGG), ("supplier", SUP)], master_clauses(w, seal=w.seal), "sealed")
    w.propose(AGG, sealed, "2026-12-01T00:00:00Z", agent=(bot, m2), expect=False)  # rule 6


# A10 Verifiable confidentiality ---------------------------------------------

def test_a10_hashes_only_evaluator_agrees_on_every_state_hash():
    w, _, at = conventional(sealed=True)
    full = ev(w)
    from universal_paper.engine import Bundle, Evaluator
    hidden = Evaluator(Bundle(w.data(disclosures=False)))
    assert not hidden.b.disclosures
    for pos in range(len(w.chains)):
        cid = w.chain_id(pos)
        fs, hs = full.run(cid), hidden.run(cid)
        assert [s.accepted for s in fs] == [s.accepted for s in hs] and all(s.accepted for s in hs)
        assert [content_hash(s.state) for s in fs] == [content_hash(s.state) for s in hs]
    p1 = w.chain_id(1)
    from build_examples import ITEMS
    assert hidden.price(p1, ITEMS[0], at) is SEALED
    assert full.price(p1, ITEMS[0], at) == {"value": "9.10", "currency": "USD"}
    fees = [o for o in hidden.obligations(w.chain_id(0), at) if o["clause"] == "fee"]
    assert fees and all(o["amount"] == "sealed" for o in fees)


def test_a10_structural_fields_cannot_be_sealed():
    w = World()
    cl = master_clauses(w)
    cl[2]["params"]["period"] = w.seal({"unit": "month", "count": 1}, "p")
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], cl, "x")
    assert any(rule == "A10" for rule, _ in agreement_issues(w.bundle(), A))


# A11 Closed evidence --------------------------------------------------------

def test_a11_undeclared_claim_type_rejected():
    w = World()
    a, A, _ = master(w)
    st = raw(w, a, "attest", SUP, "2027-02-10T00:00:00Z", {"claim": {"type": "UP:Sales-Reporting/rumor", "clause": "reporting", "data": {}}})
    assert not st.accepted and st.checks[-1].rule == "A11"


# A12 Single attribution -----------------------------------------------------

def test_a12_event_cannot_claim_another_chain():
    w = World()
    a, A, _ = master(w)
    b, B, _ = master(w, at="2026-12-03T00:00:00Z")
    st = raw(w, a, "attest", AGG, "2027-01-02T00:00:00Z",
             {"claim": {"type": "UP:Renewing-Term/optout", "clause": "term", "data": {}}}, chain=w.chain_id(b))
    assert not st.accepted


def test_a12_one_member_two_aggregators_no_conflict():
    w, actors, at = generative()
    e = ev(w)
    from build_examples import ITEMS
    px, py = w.chain_id(2), w.chain_id(3)
    assert e.status(px, at) == e.status(py, at) == "active"
    assert e.price(px, ITEMS[0], at) == {"value": "9.40", "currency": "USD"}  # tier B under X
    assert e.price(py, ITEMS[0], at) == {"value": "8.95", "currency": "USD"}  # tier A under Y


# A13 Resolved precedence ----------------------------------------------------

def _promo(w, items, during=None, over=None):
    from build_examples import USD
    cl = master_clauses(w)
    rows = [{"item": i, "by": {"A": USD("1.00"), "B": USD("1.00"), "C": USD("1.00")}} for i in items]
    t = w.clause("promo", "UP:Tiers", {"tiers": cl[1]["params"]["tiers"], "prices": rows}, over=over)
    return cl + [t]


def test_a13_unresolved_conflict_invalid():
    from build_examples import ITEMS
    w = World()
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], _promo(w, ITEMS), "x")
    assert any(rule == "A13" for rule, _ in agreement_issues(w.bundle(), A))


def test_a13_explicit_precedence_and_specificity_resolve():
    from build_examples import ITEMS
    w = World()
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], _promo(w, ITEMS, over=["tiers"]), "x")
    assert not agreement_issues(w.bundle(), A)
    B = w.agreement([("aggregator", AGG), ("supplier", SUP)], _promo(w, ITEMS[:1]), "x")
    assert not agreement_issues(w.bundle(), B)  # strictly more specific
    a, _ = w.propose(AGG, B, "2026-12-01T00:00:00Z", cosigners=[SUP])
    p, _ = participation(w, a)
    e = ev(w)
    assert e.price(w.chain_id(p), ITEMS[0], "2027-02-01T00:00:00Z") == {"value": "1.00", "currency": "USD"}
    assert e.price(w.chain_id(p), ITEMS[1], "2027-02-01T00:00:00Z") == {"value": "21.75", "currency": "USD"}


def test_a13_circular_precedence_invalid():
    from build_examples import ITEMS
    w = World()
    cl = _promo(w, ITEMS, over=["tiers"])
    cl[1]["over"] = ["promo"]
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], cl, "x")
    assert any("circular" in why for _, why in agreement_issues(w.bundle(), A))
