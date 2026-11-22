"""Transition rules (spec/05-lifecycle.md) and clause forms (spec/04-inference.md §3)."""

from universal_paper.build import World
from universal_paper.canon import content_hash

from build_examples import DAYS, ITEMS, USD, conventional, master_clauses, overlay, period
from helpers import AGG, MEM, OTHER, SUP, ev, master, participation, raw

OPT = {"claim": {"type": "UP:Renewing-Term/optout", "clause": "term", "data": {}}}


# propose ----------------------------------------------------------------------

def test_proposer_must_be_party():
    w = World()
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], master_clauses(w), "x")
    assert not raw(w, None, "propose", OTHER, "2026-12-01T00:00:00Z", {"agreement": A}).accepted


def test_amendment_requires_executed_and_correct_supersedes():
    w = World()
    a, A, h = master(w, accept=False)
    st = raw(w, a, "propose", AGG, "2026-12-02T00:00:00Z", {"agreement": A, "supersedes": content_hash(A)})
    assert not st.accepted  # not executed yet
    w2 = World()
    a, A, h = master(w2)
    st = raw(w2, a, "propose", AGG, "2026-12-03T00:00:00Z", {"agreement": A, "supersedes": "sha256:" + "2" * 64})
    assert not st.accepted


def test_cosigned_proposal_executes_immediately():
    w = World()
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], master_clauses(w), "x")
    a, _ = w.propose(AGG, A, "2026-12-01T00:00:00Z", cosigners=[SUP])
    assert ev(w).state_at(w.chain_id(a))["status"] == "executed"


# accept -------------------------------------------------------------------------

def test_accept_after_expiry_rejected_and_status_lapsed():
    w = World()
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], master_clauses(w), "x")
    a, h = w.propose(AGG, A, "2026-12-01T00:00:00Z", expires="2026-12-05T00:00:00Z")
    assert ev(w).status(w.chain_id(a), "2026-12-06T00:00:00Z") == "lapsed"
    assert not raw(w, a, "accept", SUP, "2026-12-06T00:00:00Z", {"target": h}).accepted


def test_double_accept_rejected():
    w = World()
    a, A, h = master(w, accept=False)
    assert not raw(w, a, "accept", AGG, "2026-12-02T00:00:00Z", {"target": h}).accepted  # proposer already signed


def test_ack_requires_ack_role_and_only_once():
    w = World()
    a, _, _ = master(w)
    p, _ = participation(w, a, tier=None)
    _, th = w.attest(p, MEM, "tier", "UP:Tier-Selection/selects", {"option": "A", "basis": "t"}, "2026-12-11T00:00:00Z")
    assert not raw(w, p, "accept", AGG, "2026-12-11T01:00:00Z", {"target": th}).accepted  # aggregator is not an ack role
    w.chains[p].pop()
    w.accept(p, SUP, th, "2026-12-11T02:00:00Z")
    assert not raw(w, p, "accept", SUP, "2026-12-11T03:00:00Z", {"target": th}).accepted


# attest -------------------------------------------------------------------------

def test_attest_before_execution_rejected():
    w = World()
    a, A, h = master(w, accept=False)
    assert not raw(w, a, "attest", AGG, "2026-12-02T00:00:00Z", OPT).accepted


def test_attest_unknown_clause_and_bad_data_rejected():
    w = World()
    a, _, _ = master(w)
    assert not raw(w, a, "attest", AGG, "2027-01-02T00:00:00Z", {"claim": {"type": "UP:Renewing-Term/optout", "clause": "nope", "data": {}}}).accepted
    w.chains[a].pop()
    assert not raw(w, a, "attest", AGG, "2027-01-02T00:00:00Z", {"claim": {"type": "UP:Renewing-Term/optout", "clause": "term", "data": {"x": 1}}}).accepted


def test_cosigner_without_ack_role_rejected():
    w = World()
    a, _, _ = master(w)
    st = raw(w, a, "attest", AGG, "2027-01-02T00:00:00Z", OPT, signers=[AGG, SUP])
    assert not st.accepted


# Window ---------------------------------------------------------------------------

def test_window_renews_unless_opted_out():
    w = World()
    a, _, _ = master(w)
    e = ev(w)
    cid = w.chain_id(a)
    assert e.window(cid, "2028-06-01T00:00:00Z")[1] == "2029-01-01T00:00:00Z"
    assert e.window(cid, "2031-06-01T00:00:00Z")[1] == "2030-01-01T00:00:00Z"  # max 2 renewals
    assert e.status(cid, "2031-06-01T00:00:00Z") == "expired"
    w.attest(a, SUP, "term", "UP:Renewing-Term/optout", {}, "2027-09-01T00:00:00Z")
    e = ev(w)
    assert e.status(cid, "2028-01-01T00:00:00Z") == "expired"
    assert e.status(cid, "2027-12-31T23:59:59Z") == "active"


def test_late_optout_does_not_stop_renewal():
    w = World()
    a, _, _ = master(w)
    w.attest(a, SUP, "term", "UP:Renewing-Term/optout", {}, "2027-12-15T00:00:00Z")  # less than 90 days before end
    assert ev(w).status(w.chain_id(a), "2028-02-01T00:00:00Z") == "active"


# Exit -----------------------------------------------------------------------------

def test_termination_for_convenience_and_participations_suspend():
    w = World()
    a, _, _ = master(w)
    p, _ = participation(w, a)
    w.attest(a, AGG, "exit", "UP:Termination-Convenience/notice", {}, "2027-03-01T00:00:00Z")
    e = ev(w)
    end = "2027-05-30T00:00:00Z"
    assert e.state_at(w.chain_id(a))["ends_at"] == end
    assert e.status(w.chain_id(a), "2027-05-29T00:00:00Z") == "active"
    assert e.status(w.chain_id(a), end) == "terminated"
    assert e.status(w.chain_id(p), end) == "suspended"
    assert not e.active(w.chain_id(p), end)


def test_member_cannot_terminate_master():
    w = World()
    a, _, _ = master(w)
    assert not raw(w, a, "attest", MEM, "2027-03-01T00:00:00Z",
                   {"claim": {"type": "UP:Termination-Convenience/notice", "clause": "exit", "data": {}}}).accepted


def _cause_world():
    w = World()
    cl = master_clauses(w) + [w.clause("cause", "UP:Termination-Cause", {"holders": ["aggregator", "supplier"],
                                                                          "cure_period": DAYS(30), "notice": DAYS(10)})]
    a, _, _ = master(w, clauses=cl)
    _, bh = w.attest(a, AGG, "cause", "UP:Termination-Cause/breach", {"description": "Hypothetical breach"}, "2027-02-01T00:00:00Z")
    return w, a, bh


def test_termination_for_cause_needs_aged_uncured_breach():
    w, a, bh = _cause_world()
    notice = {"claim": {"type": "UP:Termination-Cause/notice", "clause": "cause", "data": {"breach": bh}}}
    assert not raw(w, a, "attest", AGG, "2027-02-15T00:00:00Z", notice).accepted  # cure period not over
    w.chains[a].pop()
    w.attest(a, AGG, "cause", "UP:Termination-Cause/notice", {"breach": bh}, "2027-03-05T00:00:00Z")
    assert ev(w).status(w.chain_id(a), "2027-03-15T00:00:00Z") == "terminated"


def test_acknowledged_cure_blocks_termination_for_cause():
    w, a, bh = _cause_world()
    _, ch = w.attest(a, SUP, "cause", "UP:Termination-Cause/cured", {"breach": bh}, "2027-02-10T00:00:00Z")
    w.accept(a, AGG, ch, "2027-02-11T00:00:00Z")
    notice = {"claim": {"type": "UP:Termination-Cause/notice", "clause": "cause", "data": {"breach": bh}}}
    assert not raw(w, a, "attest", AGG, "2027-03-05T00:00:00Z", notice).accepted


# Selection ------------------------------------------------------------------------

def test_selection_effective_on_ack_and_option_must_exist():
    w = World()
    a, _, _ = master(w)
    p, _ = participation(w, a, tier=None)
    pid = w.chain_id(p)
    assert ev(w).selection(pid, "tier", MEM.pub, "2027-01-02T00:00:00Z") == "C"  # initial
    _, th = w.attest(p, MEM, "tier", "UP:Tier-Selection/selects", {"option": "A", "basis": "t"}, "2027-01-05T00:00:00Z")
    assert ev(w).selection(pid, "tier", MEM.pub, "2027-01-06T00:00:00Z") == "C"  # not yet acknowledged
    w.accept(p, SUP, th, "2027-01-07T00:00:00Z")
    e = ev(w)
    assert e.selection(pid, "tier", MEM.pub, "2027-01-06T23:59:59Z") == "C"
    assert e.selection(pid, "tier", MEM.pub, "2027-01-07T00:00:00Z") == "A"
    assert not raw(w, p, "attest", MEM, "2027-01-08T00:00:00Z",
                   {"claim": {"type": "UP:Tier-Selection/selects", "clause": "tier", "data": {"option": "Z", "basis": "t"}}}).accepted


# Valuation (reference) -------------------------------------------------------------

def test_reference_price_list_with_factor_and_rounding():
    w = World()
    cl = [c for c in master_clauses(w) if c["n"] != "tiers"] + [
        w.clause("ref", "UP:Price-Reference", {"items": ITEMS[:1], "list_role": "supplier", "factor": "0.875",
                                               "rounding": {"scale": 2, "mode": "half-up"}})]
    a, _, _ = master(w, clauses=cl)
    w.attest(a, SUP, "ref", "UP:Price-Reference/list", {"effective": "2027-01-01T00:00:00Z",
             "prices": [{"item": ITEMS[0], "price": USD("10.01")}]}, "2026-12-20T00:00:00Z")
    e = ev(w)
    assert e.value(w.chain_id(a), ITEMS[0], None, "2027-01-02T00:00:00Z") == {"value": "8.76", "currency": "USD"}
    assert e.value(w.chain_id(a), ITEMS[0], None, "2026-12-25T00:00:00Z") is None  # list not yet effective


# Duty -------------------------------------------------------------------------------

def test_fee_commitments_amounts_and_statuses():
    w, _, at = conventional()
    fees = [o for o in ev(w).obligations(w.chain_id(0), at) if o["clause"] == "fee"]
    assert [(o["amount"]["value"], o["status"]) for o in fees] == [("61.00", "discharged"), ("62.13", "discharged"), ("66.43", "open")]
    later = [o for o in ev(w).obligations(w.chain_id(0), "2027-05-02T00:00:00Z") if o["clause"] == "fee"]
    assert later[2]["status"] == "overdue"


def test_underpayment_does_not_discharge():
    w = World()
    a, _, _ = master(w)
    rep = {"period": period("2027-01-01T00:00:00Z", "2027-02-01T00:00:00Z"), "lines": [], "total_net": USD("1000.00")}
    w.attest(a, SUP, "reporting", "UP:Sales-Reporting/report", rep, "2027-02-05T00:00:00Z")
    _, fh = w.attest(a, SUP, "fee", "UP:Admin-Fee/paid", {"period": rep["period"], "amount": USD("19.99"), "reference": "x"}, "2027-02-06T00:00:00Z")
    w.accept(a, AGG, fh, "2027-02-07T00:00:00Z")
    fee = [o for o in ev(w).obligations(w.chain_id(a), "2027-02-08T00:00:00Z") if o["clause"] == "fee"][0]
    assert fee["amount"] == USD("20.00") and fee["status"] == "open"


def test_unacknowledged_payment_does_not_discharge():
    w = World()
    a, _, _ = master(w)
    rep = {"period": period("2027-01-01T00:00:00Z", "2027-02-01T00:00:00Z"), "lines": [], "total_net": USD("1000.00")}
    w.attest(a, SUP, "reporting", "UP:Sales-Reporting/report", rep, "2027-02-05T00:00:00Z")
    w.attest(a, SUP, "fee", "UP:Admin-Fee/paid", {"period": rep["period"], "amount": USD("20.00"), "reference": "x"}, "2027-02-06T00:00:00Z")
    fee = [o for o in ev(w).obligations(w.chain_id(a), "2027-02-08T00:00:00Z") if o["clause"] == "fee"][0]
    assert fee["status"] == "open"


def test_audit_request_limit_and_discharge():
    w = World()
    a, _, _ = master(w)
    req = {"scope": "Hypothetical", "lookback": period("2027-01-01T00:00:00Z", "2027-02-01T00:00:00Z")}
    _, rh = w.attest(a, AGG, "audit", "UP:Audit/request", req, "2027-03-01T00:00:00Z")
    assert not raw(w, a, "attest", AGG, "2027-06-01T00:00:00Z", {"claim": {"type": "UP:Audit/request", "clause": "audit", "data": req}}).accepted
    w.chains[a].pop()
    e = ev(w)
    aud = [o for o in e.obligations(w.chain_id(a), "2027-04-15T00:00:00Z") if o["clause"] == "audit"][0]
    assert aud["status"] == "overdue" and aud["due"] == "2027-03-31T00:00:00Z"
    _, vh = w.attest(a, SUP, "audit", "UP:Audit/available", {"request": rh}, "2027-03-20T00:00:00Z")
    w.accept(a, AGG, vh, "2027-03-21T00:00:00Z")
    aud = [o for o in ev(w).obligations(w.chain_id(a), "2027-04-15T00:00:00Z") if o["clause"] == "audit"][0]
    assert aud["status"] == "discharged"


def test_overlay_creates_no_duties_before_signing():
    w, _, at = overlay()
    obs = ev(w).obligations(w.chain_id(0), at)
    assert obs and min(o["period"]["end"] for o in obs) == "2027-03-01T00:00:00Z"  # first period ending after 2027-02-10


# Link -------------------------------------------------------------------------------

def test_participation_must_bind_parent_supplier():
    w = World()
    a, _, _ = master(w)
    from build_examples import participation_clauses
    P = w.agreement([("aggregator", AGG), ("member", MEM), ("supplier", OTHER)],
                    participation_clauses(w, w.chain_id(a), "2027-01-01T00:00:00Z"), "x")
    assert not raw(w, None, "propose", MEM, "2026-12-10T00:00:00Z", {"agreement": P}).accepted


def test_participation_requires_executed_parent():
    w = World()
    a, _, _ = master(w, accept=False)
    from build_examples import participation_clauses
    P = w.agreement([("aggregator", AGG), ("member", MEM), ("supplier", SUP)],
                    participation_clauses(w, w.chain_id(a), "2027-01-01T00:00:00Z"), "x")
    assert not raw(w, None, "propose", MEM, "2026-12-10T00:00:00Z", {"agreement": P}).accepted
