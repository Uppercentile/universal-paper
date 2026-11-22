"""One regression test per finding in AUDIT.md. Each failed before the fix it names."""
import locale
import time

import pytest

from universal_paper.build import World
from universal_paper.crypto import Key
from universal_paper.engine import agreement_issues
from universal_paper.render import render_agreement
from universal_paper.values import add_period, dec, fmt_time, parse_time

from build_examples import ITEMS, USD, master_clauses
from helpers import AGG, SUP, ev, master, raw


def _renewing(w, **override):
    cl = master_clauses(w)
    cl[0]["params"].update(override)
    return cl


def test_f01_zero_length_renewal_period_is_rejected_and_cannot_hang_the_evaluator():
    w = World()
    cl = _renewing(w, renewal_period={"unit": "year", "count": 0}, max_renewals=2**53 - 1)
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], cl, "x")
    issues = agreement_issues(ev(w).b, A)
    assert any("renewal_period must be a Period" in why for _, why in issues)
    st = raw(w, None, "propose", AGG, "2026-12-01T00:00:00Z", {"agreement": A}, signers=[AGG, SUP])
    assert not st.accepted
    t0 = time.monotonic()
    ev(w).status(w.chain_id(0), "2099-01-01T00:00:00Z")
    assert time.monotonic() - t0 < 2


@pytest.mark.parametrize("name,value", [
    ("start", "2027-02-30T00:00:00Z"), ("optout_notice", {"unit": "day", "count": -5}), ("max_renewals", -1),
    ("max_renewals", True), ("optout_roles", ["supplier", "auditor"]), ("renewal_period", {"unit": "week", "count": 1}),
])
def test_f02_every_parameter_is_checked_against_its_declared_type(name, value):
    w = World()
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], _renewing(w, **{name: value}), "x")
    assert agreement_issues(ev(w).b, A)


def test_f03_ill_typed_claim_data_is_rejected_instead_of_breaking_derived_values():
    w = World()
    a, _, _ = master(w)
    bad = {"claim": {"type": "UP:Sales-Reporting/report", "clause": "reporting",
                     "data": {"period": {"start": "2027-01-01T00:00:00Z", "end": "2027-02-01T00:00:00Z"}, "lines": [],
                              "total_net": {"value": "lots", "currency": "USD"}}}}
    st = raw(w, a, "attest", SUP, "2027-02-05T00:00:00Z", bad)
    assert not st.accepted and "total_net must be an Amount" in st.reason
    ev(w).obligations(w.chain_id(a), "2027-03-31T00:00:00Z")  # used to raise on the accepted bad report


def test_f04_decimal_arithmetic_is_exact_beyond_28_digits():
    w = World()
    cl = [c for c in master_clauses(w) if c["n"] != "tiers"] + [
        w.clause("ref", "UP:Price-Reference", {"items": ITEMS[:1], "list_role": "supplier", "factor": "1.0000001",
                                               "rounding": {"scale": 2, "mode": "half-even"}})]
    a, _, _ = master(w, clauses=cl)
    w.attest(a, SUP, "ref", "UP:Price-Reference/list", {"effective": "2027-01-01T00:00:00Z",
             "prices": [{"item": ITEMS[0], "price": USD("1000000000000000000000.005")}]}, "2026-12-20T00:00:00Z")
    v = ev(w).value(w.chain_id(a), ITEMS[0], None, "2027-01-02T00:00:00Z")
    # Exact product 1000000100000000000000.0050000005 rounds up. The old 28-digit context gave .00.
    assert v == {"value": "1000000100000000000000.01", "currency": "USD"}


def test_f05_renewals_are_computed_from_the_original_end_without_month_end_drift():
    w = World()
    cl = _renewing(w, start="2027-01-01T00:00:00Z", end="2027-01-31T00:00:00Z",
                   renewal_period={"unit": "month", "count": 1}, max_renewals=5)
    a, _, _ = master(w, clauses=cl)
    _, end = ev(w).window(w.chain_id(a), "2027-03-30T00:00:00Z")
    # e1 = 28 Feb, e2 = 31 Mar (end + 2 months), not 28 Mar (e1 + 1 month).
    assert end == "2027-03-31T00:00:00Z"


def test_f06_signature_encodings_are_strict():
    from universal_paper.crypto import verify
    k = Key.from_seed("x")
    obj = {"type": "x", "spec": "y"}
    s = k.sign_obj(obj)["sig"]
    assert verify(k.public, s, obj)
    assert not verify(k.public, s.upper(), obj)
    assert not verify("ed25519:" + "01" + "00" * 31, "01" + "00" * 63, obj)  # identity key, "signature" R=identity S=0


def test_f07_small_order_party_key_makes_an_agreement_invalid():
    w = World()
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], master_clauses(w), "x")
    A["parties"].append({"role": "supplier", "party": {"key": "ed25519:01" + "00" * 31, "name": "identity point"}})
    assert any("malformed party key" in why for _, why in agreement_issues(ev(w).b, A))


@pytest.mark.parametrize("s", ["2027-01-01T00:00:00Z\n", "２０２７-01-01T00:00:00Z", "2027-01-01T10:60:00Z", "0000-01-01T00:00:00Z"])
def test_f08_time_strings_are_strict(s):
    with pytest.raises(ValueError):
        parse_time(s)


@pytest.mark.parametrize("s", ["1.5\n", "１", "9" * 65])
def test_f08_decimal_strings_are_strict(s):
    with pytest.raises(ValueError):
        dec(s)


def test_f09_years_before_1000_are_zero_padded_and_rendering_ignores_the_locale():
    assert fmt_time(parse_time("0999-12-31T00:00:00Z")) == "0999-12-31T00:00:00Z"
    assert add_period("0999-12-31T00:00:00Z", {"unit": "day", "count": 1}) == "1000-01-01T00:00:00Z"
    w = World()
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], master_clauses(w), "x")
    text = render_agreement(ev(w).b, A)
    for name in ("de_DE.UTF-8", "fr_FR.UTF-8", "C.UTF-8"):
        try:
            old = locale.setlocale(locale.LC_TIME)
            locale.setlocale(locale.LC_TIME, name)
        except locale.Error:
            continue
        try:
            assert render_agreement(ev(w).b, A) == text
        finally:
            locale.setlocale(locale.LC_TIME, old)
    assert "1 January 2027, 00:00 UTC" in text


def test_f10_malformed_mandate_and_proposal_expiry_are_rejected_cleanly():
    bot = Key.from_seed("bot")
    w = World()
    bounds = {c["term"]: {p: {"any": True} for p in c["params"]} for c in master_clauses(w)}
    m = w.mandate(AGG, bot, "2026-01-01", "2027-06-01T00:00:00Z", {"kinds": ["propose"], "roles": ["aggregator"], "terms": bounds})
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], master_clauses(w), "x")
    pos, _ = w.propose(AGG, A, "2026-12-01T00:00:00Z", agent=(bot, m), expect=False)
    assert "the Mandate is malformed" in ev(w).run(w.chain_id(pos))[-1].reason
    w2 = World()
    A2 = w2.agreement([("aggregator", AGG), ("supplier", SUP)], master_clauses(w2), "x")
    st = raw(w2, None, "propose", AGG, "2026-12-01T00:00:00Z", {"agreement": A2, "expires": "next week"})
    assert not st.accepted and "expiry" in st.reason



def test_f12_a_bundle_holding_two_versions_of_one_chain_is_reported(tmp_path):
    import copy
    import json
    from pathlib import Path

    from universal_paper.__main__ import main
    root = Path(__file__).resolve().parent.parent
    data = json.loads((root / "examples" / "conventional" / "bundle.json").read_text())
    fork = copy.deepcopy(data["chains"][0][:2])
    data["chains"].append(fork)  # same genesis, shorter history: a second version of chain 0
    p = tmp_path / "forked.json"
    p.write_text(json.dumps(data))
    assert main(["validate", str(p)]) == 2
