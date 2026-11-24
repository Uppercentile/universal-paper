"""Build the worked examples: bundles, and traces with independent evaluators.

Run from the repository root:  python3 examples/build_examples.py

All parties, identifiers, prices, rates, quantities, and dates are HYPOTHETICAL.
They illustrate the language and carry no meaning beyond that.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from universal_paper.build import Actor, World  # noqa: E402
from universal_paper.canon import content_hash  # noqa: E402
from universal_paper.crypto import Key  # noqa: E402

USD = lambda v: {"value": v, "currency": "USD"}  # noqa: E731
MONTH = {"unit": "month", "count": 1}
QUARTER = {"unit": "quarter", "count": 1}
YEAR = {"unit": "year", "count": 1}
DAYS = lambda n: {"unit": "day", "count": n}  # noqa: E731
R2 = {"scale": 2, "mode": "half-even"}
GTIN = lambda s: {"scheme": "GTIN", "id": s}  # noqa: E731
ITEMS = [GTIN("00000000000017"), GTIN("00000000000024"), GTIN("00000000000031")]
LAW = {"law": "[hypothetical jurisdiction]", "forum": "[hypothetical forum]"}


def period(a, b):
    return {"start": a, "end": b}


def money(x: float) -> dict:
    return USD(f"{x:.2f}")


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------

def master_clauses(w: World, seal=None, tiers=("A", "B", "C"), prices=None, rate="0.02", label_extra=""):
    s = seal or (lambda v, l: v)
    prices = prices or {ITEMS[0]["id"]: ("9.10", "9.40", "9.80"),
                        ITEMS[1]["id"]: ("21.00", "21.75", "22.50"),
                        ITEMS[2]["id"]: ("3.05", "3.15", "3.30")}
    table = [{"item": GTIN(i), "by": {t: s(USD(p), f"price {i} {t}") for t, p in zip(tiers, ps)}} for i, ps in prices.items()]
    return [
        w.clause("term", "UP:Renewing-Term", {"start": "2027-01-01T00:00:00Z", "end": "2028-01-01T00:00:00Z",
                                              "renewal_period": YEAR, "max_renewals": 2,
                                              "optout_roles": ["aggregator", "supplier"], "optout_notice": DAYS(90)}),
        w.clause("tiers", "UP:Tiers", {"tiers": [
            {"name": "A", "conditions": s("Hypothetical: the Member's annual category purchases are at or above level A", "cond A")},
            {"name": "B", "conditions": s("Hypothetical: the Member's annual category purchases are at or above level B", "cond B")},
            {"name": "C", "conditions": s("Hypothetical: any participating Member", "cond C")}], "prices": table}),
        w.clause("reporting", "UP:Sales-Reporting", {"reporter": "supplier", "recipient": "aggregator", "period": MONTH, "due": DAYS(15)}),
        w.clause("fee", "UP:Admin-Fee", {"payer": "supplier", "payee": "aggregator", "rate": s(rate, "fee rate"),
                                         "report_clause": "reporting", "period": MONTH, "due": DAYS(30), "rounding": R2}),
        w.clause("audit", "UP:Audit", {"auditor": "aggregator", "auditee": "supplier", "response": DAYS(30),
                                       "max_requests": 1, "per": YEAR}),
        w.clause("exit", "UP:Termination-Convenience", {"holders": ["aggregator", "supplier"], "notice": DAYS(90)}),
        w.clause("notices", "UP:Notices", {}),
        w.clause("law", "UP:Governing-Law", LAW),
    ]


def participation_clauses(w: World, parent: str, start: str, initial="C"):
    return [
        w.clause("participation", "UP:Participation", {"parent": parent}),
        w.clause("tier", "UP:Tier-Selection", {"tiers_clause": "tiers", "initial": initial, "effective": "on-ack"}),
        w.clause("term", "UP:Fixed-Term", {"start": start, "end": "2028-01-01T00:00:00Z"}),
        w.clause("disclosure", "UP:Fee-Disclosure", {"period": QUARTER, "due": DAYS(30)}),
        w.clause("exit", "UP:Termination-Convenience", {"holders": ["member"], "notice": DAYS(30)}),
        w.clause("notices", "UP:Notices", {}),
    ]


def report_data(w, lines, prices, a, b, seal=None):
    s = seal or (lambda v, l: v)
    out, total = [], 0.0
    for pid, item_idx, qty, tier in lines:
        unit = float(prices[ITEMS[item_idx]["id"]]["ABC".index(tier)])
        net = round(unit * qty, 2)
        total += net
        out.append({"participation": pid, "item": ITEMS[item_idx], "quantity": s(str(qty), "qty"), "net": s(money(net), "net")})
    return {"period": period(a, b), "lines": out, "total_net": s(money(total), "total")}, round(total, 2)


PRICES = {ITEMS[0]["id"]: ("9.10", "9.40", "9.80"), ITEMS[1]["id"]: ("21.00", "21.75", "22.50"), ITEMS[2]["id"]: ("3.05", "3.15", "3.30")}


# ---------------------------------------------------------------------------
# 1. Conventional (and 4. Confidential, which is the same story with sealed values)
# ---------------------------------------------------------------------------

def conventional(sealed: bool = False):
    w = World()
    seal = w.seal if sealed else None
    s = seal or (lambda v, l: v)
    agg = Actor("Hypothetical Health Purchasing Alliance", ids=[{"scheme": "GLN", "id": "0000000000017"}])
    sup = Actor("Example Medical Supply Co.", ids=[{"scheme": "GLN", "id": "0000000000024"}])
    m1 = Actor("Hypothetical Community Hospital", ids=[{"scheme": "HIN", "id": "HYP000001"}])
    m2 = Actor("Sample Regional Clinic", ids=[{"scheme": "HIN", "id": "HYP000002"}])
    label = "Master agreement (hypothetical)" + (" — confidential" if sealed else "")
    A = w.agreement([("aggregator", agg), ("supplier", sup)], master_clauses(w, seal), label)
    a, h = w.propose(agg, A, "2026-12-01T15:00:00Z")
    w.accept(a, sup, h, "2026-12-05T10:00:00Z")
    cidA = w.chain_id(a)

    def join(m, start, at, initial_tier, tier_at, cosign):
        P = w.agreement([("aggregator", agg), ("member", m), ("supplier", sup)],
                        participation_clauses(w, cidA, start), f"Participation of {m.name}")
        p, ph = w.propose(m, P, at)
        w.accept(p, agg, ph, at.replace("T09", "T13"))
        w.accept(p, sup, ph, at.replace("T09", "T16"))
        data = {"option": initial_tier, "basis": s("Hypothetical basis: prior-year category purchases", "basis")}
        if cosign:
            w.attest(p, m, "tier", "UP:Tier-Selection/selects", data, tier_at, cosigners=[sup])
        else:
            _, th = w.attest(p, m, "tier", "UP:Tier-Selection/selects", data, tier_at)
            w.accept(p, sup, th, tier_at.replace("T10", "T15"))
        return p

    p1 = join(m1, "2027-01-05T00:00:00Z", "2027-01-04T09:00:00Z", "B", "2027-01-07T10:00:00Z", cosign=False)
    p2 = join(m2, "2027-01-11T00:00:00Z", "2027-01-10T09:00:00Z", "A", "2027-01-12T10:00:00Z", cosign=True)
    P1, P2 = w.chain_id(p1), w.chain_id(p2)

    jan, jan_total = report_data(w, [(P1, 0, 100, "B"), (P1, 1, 20, "B"), (P2, 0, 50, "A"), (P2, 2, 400, "A")],
                                 PRICES, "2027-01-01T00:00:00Z", "2027-02-01T00:00:00Z", seal)
    w.attest(a, sup, "reporting", "UP:Sales-Reporting/report", jan, "2027-02-10T12:00:00Z")
    # Tier change: member 1 moves from B to A.
    _, th = w.attest(p1, m1, "tier", "UP:Tier-Selection/selects",
                     {"option": "A", "basis": s("Hypothetical basis: purchases now at or above level A", "basis2")}, "2027-02-15T10:00:00Z")
    w.accept(p1, sup, th, "2027-02-16T09:00:00Z")
    fee_jan = round(jan_total * 0.02, 2)
    _, fh = w.attest(a, sup, "fee", "UP:Admin-Fee/paid", {"period": period("2027-01-01T00:00:00Z", "2027-02-01T00:00:00Z"),
                     "amount": s(money(fee_jan), "fee jan"), "reference": s("Hypothetical remittance 1001", "ref")}, "2027-02-20T12:00:00Z")
    w.accept(a, agg, fh, "2027-02-21T12:00:00Z")
    feb, feb_total = report_data(w, [(P1, 0, 40, "B"), (P1, 0, 60, "A"), (P1, 1, 25, "A"), (P2, 0, 55, "A"), (P2, 2, 380, "A")],
                                 PRICES, "2027-02-01T00:00:00Z", "2027-03-01T00:00:00Z", seal)
    w.attest(a, sup, "reporting", "UP:Sales-Reporting/report", feb, "2027-03-10T12:00:00Z")
    fee_feb = round(feb_total * 0.02, 2)
    _, fh = w.attest(a, sup, "fee", "UP:Admin-Fee/paid", {"period": period("2027-02-01T00:00:00Z", "2027-03-01T00:00:00Z"),
                     "amount": s(money(fee_feb), "fee feb"), "reference": s("Hypothetical remittance 1002", "ref")}, "2027-03-25T12:00:00Z")
    w.accept(a, agg, fh, "2027-03-26T12:00:00Z")
    mar, _ = report_data(w, [(P1, 0, 110, "A"), (P1, 1, 30, "A"), (P2, 0, 45, "A"), (P2, 2, 420, "A")],
                         PRICES, "2027-03-01T00:00:00Z", "2027-04-01T00:00:00Z", seal)
    w.attest(a, sup, "reporting", "UP:Sales-Reporting/report", mar, "2027-04-10T12:00:00Z")
    w.attest(p1, agg, "disclosure", "UP:Fee-Disclosure/disclosed",
             {"period": period("2027-01-05T00:00:00Z", "2027-04-05T00:00:00Z"),
              "received": s(money(fee_jan + fee_feb), "disclosed"),
              "basis": s("Hypothetical: all administrative fees received under the master agreement for the period", "dbasis")},
             "2027-04-20T12:00:00Z")
    return w, {"agg": agg, "sup": sup, "m1": m1, "m2": m2}, "2027-04-30T00:00:00Z"


# ---------------------------------------------------------------------------
# 2. Generative: one member, two aggregators (one run entirely by an agent), all through Mandates
# ---------------------------------------------------------------------------

def generative():
    w = World()
    gpo_x = Actor("Hypothetical Agent-Run Purchasing Cooperative")  # has no staff: every action is by its agent
    gpo_y = Actor("Hypothetical Specialty Purchasing Network")
    sup = Actor("Example Medical Supply Co.")
    hosp = Actor("Hypothetical Rural Hospital", ids=[{"scheme": "HIN", "id": "HYP000009"}])
    x_bot = Key.from_seed("universal-paper-example:agent:cooperative-bot")
    h_bot = Key.from_seed("universal-paper-example:agent:hospital-procurement-agent")
    nb, ex = "2026-11-01T00:00:00Z", "2027-12-31T00:00:00Z"
    any_ = {"any": True}
    # The cooperative's founders authorize its agent to contract, within a fee cap and a term cap.
    master_bounds = {
        "UP:Renewing-Term": {"start": any_, "end": any_, "renewal_period": {"max_period": YEAR}, "max_renewals": {"in": [0, 1, 2]},
                             "optout_roles": any_, "optout_notice": any_},
        "UP:Tiers": {"tiers": any_, "prices": any_},
        "UP:Sales-Reporting": {"reporter": {"in": ["supplier"]}, "recipient": {"in": ["aggregator"]}, "period": any_, "due": any_},
        "UP:Admin-Fee": {"payer": {"in": ["supplier"]}, "payee": {"in": ["aggregator"]}, "rate": {"max": "0.03"},
                         "report_clause": any_, "period": any_, "due": any_, "rounding": any_},
        "UP:Audit": {k: any_ for k in ("auditor", "auditee", "response", "max_requests", "per")},
        "UP:Termination-Convenience": {"holders": any_, "notice": any_},
        "UP:Notices": {}, "UP:Governing-Law": {"law": any_, "forum": any_},
        "UP:Participation": {"parent": any_},
        "UP:Tier-Selection": {"tiers_clause": any_, "initial": any_, "effective": any_},
        "UP:Fixed-Term": {"start": any_, "end": any_},
        "UP:Fee-Disclosure": {"period": any_, "due": any_},
    }
    mx = w.mandate(gpo_x, x_bot, nb, ex, {"kinds": ["propose", "accept", "attest"], "roles": ["aggregator"],
                                          "terms": master_bounds,
                                          "claims": {"UP:Fee-Disclosure/disclosed": {"period": any_, "received": any_, "basis": any_},
                                                     "UP:Admin-Fee/paid": {"period": any_, "amount": any_, "reference": any_}}})
    # The hospital authorizes its procurement agent to join agreements and attest tiers A or B only.
    mh = w.mandate(hosp, h_bot, nb, ex, {
        "kinds": ["propose", "accept", "attest"], "roles": ["member"],
        "terms": {"UP:Participation": {"parent": any_},
                  "UP:Tier-Selection": {"tiers_clause": {"in": ["tiers"]}, "initial": {"in": ["B", "C"]}, "effective": {"in": ["on-ack"]}},
                  "UP:Fixed-Term": {"start": any_, "end": any_},
                  "UP:Fee-Disclosure": {"period": any_, "due": any_},
                  "UP:Termination-Convenience": {"holders": {"in": [["member"]]}, "notice": {"max_period": DAYS(60)}},
                  "UP:Notices": {}},
        "claims": {"UP:Tier-Selection/selects": {"option": {"in": ["A", "B"]}, "basis": any_}}})

    X = w.agreement([("aggregator", gpo_x), ("supplier", sup)], master_clauses(w, rate="0.025"), "Master X (agent-run cooperative, hypothetical)")
    x, xh = w.propose(gpo_x, X, "2026-12-01T00:00:00Z", agent=(x_bot, mx))
    w.accept(x, sup, xh, "2026-12-02T00:00:00Z")
    yprices = {ITEMS[0]["id"]: ("8.95", "9.35", "9.90"), ITEMS[1]["id"]: ("20.50", "21.50", "22.75"), ITEMS[2]["id"]: ("3.00", "3.20", "3.40")}
    Y = w.agreement([("aggregator", gpo_y), ("supplier", sup)], master_clauses(w, prices=yprices, rate="0.03"),
                    "Master Y (specialty network, hypothetical)")
    y, yh = w.propose(gpo_y, Y, "2026-12-03T00:00:00Z")
    w.accept(y, sup, yh, "2026-12-04T00:00:00Z")

    def join(master_pos, gpo, at):
        P = w.agreement([("aggregator", gpo), ("member", hosp), ("supplier", sup)],
                        participation_clauses(w, w.chain_id(master_pos), "2027-01-01T00:00:00Z"),
                        f"Participation of {hosp.name} under {'X' if gpo is gpo_x else 'Y'}")
        p, ph = w.propose(hosp, P, at, agent=(h_bot, mh))
        if gpo is gpo_x:
            w.accept(p, gpo, ph, at.replace("T09", "T10"), agent=(x_bot, mx))
        else:
            w.accept(p, gpo, ph, at.replace("T09", "T10"))
        w.accept(p, sup, ph, at.replace("T09", "T11"))
        return p

    px = join(x, gpo_x, "2026-12-10T09:00:00Z")
    py = join(y, gpo_y, "2026-12-11T09:00:00Z")
    _, t1 = w.attest(px, hosp, "tier", "UP:Tier-Selection/selects", {"option": "B", "basis": "Hypothetical basis"}, "2027-01-02T09:00:00Z", agent=(h_bot, mh))
    w.accept(px, sup, t1, "2027-01-02T12:00:00Z")
    _, t2 = w.attest(py, hosp, "tier", "UP:Tier-Selection/selects", {"option": "A", "basis": "Hypothetical basis"}, "2027-01-03T09:00:00Z", agent=(h_bot, mh))
    w.accept(py, sup, t2, "2027-01-03T12:00:00Z")
    # Out of bounds 1: the hospital's agent tries to attest tier C, which its Mandate does not allow.
    w.attest(py, hosp, "tier", "UP:Tier-Selection/selects", {"option": "C", "basis": "Hypothetical basis"}, "2027-01-20T09:00:00Z",
             agent=(h_bot, mh), expect=False)
    # Out of bounds 2: the cooperative's agent proposes an amendment raising its own admin fee above its cap.
    X2 = copy.deepcopy(X)
    for c in X2["clauses"]:
        if c["n"] == "fee":
            c["params"]["rate"] = "0.035"
    w.propose(gpo_x, X2, "2027-01-25T09:00:00Z", pos=x, supersedes=content_hash(X), agent=(x_bot, mx), expect=False)
    # Purchases under both agreements, by the same member, at the same time: each report is on exactly one chain (A12).
    PX, PY = w.chain_id(px), w.chain_id(py)
    jx, jx_total = report_data(w, [(PX, 0, 70, "B"), (PX, 1, 10, "B")], PRICES, "2027-01-01T00:00:00Z", "2027-02-01T00:00:00Z")
    w.attest(x, sup, "reporting", "UP:Sales-Reporting/report", jx, "2027-02-05T12:00:00Z")
    jy, jy_total = report_data(w, [(PY, 0, 30, "A"), (PY, 2, 200, "A")], yprices, "2027-01-01T00:00:00Z", "2027-02-01T00:00:00Z")
    w.attest(y, sup, "reporting", "UP:Sales-Reporting/report", jy, "2027-02-05T12:00:00Z")
    _, fh = w.attest(x, sup, "fee", "UP:Admin-Fee/paid", {"period": period("2027-01-01T00:00:00Z", "2027-02-01T00:00:00Z"),
                     "amount": money(round(jx_total * 0.025, 2)), "reference": "Hypothetical remittance X-1"}, "2027-02-20T12:00:00Z")
    w.accept(x, gpo_x, fh, "2027-02-20T12:05:00Z", agent=(x_bot, mx))
    return w, {"gpo_x": gpo_x, "gpo_y": gpo_y, "sup": sup, "hosp": hosp}, "2027-03-01T00:00:00Z"


# ---------------------------------------------------------------------------
# 5. Mandate cap: an agent's pricing authority is capped at 2% either way (the "deterministic block" demo)
# ---------------------------------------------------------------------------

def mandate_cap():
    """A cooperative's agent may move prices at most 2% from the supplier's list. It tries 5%; the language says no.

    The bundle holds the signed Mandate and the active agreement (list price x 1.00). The out-of-bounds amendment is
    left for an agent to try with simulate_events or check_event; an in-bounds one (x 1.015) is shown here for contrast.
    """
    w = World()
    coop = Actor("Hypothetical Agent-Run Purchasing Cooperative")
    sup = Actor("Example Medical Supply Co.")
    bot = Key.from_seed("universal-paper-example:agent:pricing-agent")
    any_ = {"any": True}
    m = w.mandate(coop, bot, "2026-11-01T00:00:00Z", "2027-12-31T00:00:00Z", {
        "kinds": ["propose", "accept"], "roles": ["aggregator"],
        "terms": {"UP:Fixed-Term": {"start": any_, "end": any_},
                  "UP:Price-Reference": {"items": any_, "list_role": {"in": ["supplier"]},
                                         "factor": {"min": "0.98", "max": "1.02"}, "rounding": any_},
                  "UP:Notices": {}}})

    def deal(factor: str) -> dict:
        return w.agreement([("aggregator", coop), ("supplier", sup)], [
            w.clause("term", "UP:Fixed-Term", {"start": "2027-01-01T00:00:00Z", "end": "2028-01-01T00:00:00Z"}),
            w.clause("price", "UP:Price-Reference", {"items": ITEMS, "list_role": "supplier", "factor": factor, "rounding": R2}),
            w.clause("notices", "UP:Notices", {}),
        ], "Pricing agreement (agent-run cooperative, hypothetical)")

    A = deal("1.00")
    pos, h = w.propose(coop, A, "2026-12-01T09:00:00Z", agent=(bot, m))
    w.accept(pos, sup, h, "2026-12-01T10:00:00Z")
    # Out of bounds: a 5% increase. Rejected under A9, so it never enters the chain (checked here, then discarded).
    trial = copy.deepcopy(w)
    trial.propose(coop, deal("1.05"), "2027-02-01T09:00:00Z", pos=pos, supersedes=content_hash(A), agent=(bot, m), expect=False)
    return w, {"coop": coop, "sup": sup, "agent": bot, "mandate": m}, "2027-03-01T00:00:00Z"


def what_if():
    """For the simulate_purchase, simulate_termination and simulate_eligibility tools: one master, three members.

    The master adds termination for cause, and the aggregator has given a breach notice (cure period 30 days).
    Member 1 is active, in tier B, with an 80% purchase commitment. Member 2 gave notice and has left.
    Member 3 has signed with the aggregator, but the supplier has not signed yet.
    """
    w = World()
    agg = Actor("Hypothetical Health Purchasing Alliance", ids=[{"scheme": "GLN", "id": "0000000000017"}])
    sup = Actor("Example Medical Supply Co.", ids=[{"scheme": "GLN", "id": "0000000000024"}])
    m1 = Actor("Hypothetical Community Hospital", ids=[{"scheme": "HIN", "id": "HYP000001"}])
    m2 = Actor("Sample Regional Clinic", ids=[{"scheme": "HIN", "id": "HYP000002"}])
    m3 = Actor("Hypothetical Rural Hospital", ids=[{"scheme": "HIN", "id": "HYP000003"}])
    clauses = master_clauses(w)
    clauses.insert(6, w.clause("cause", "UP:Termination-Cause", {"holders": ["aggregator", "supplier"],
                                                                 "cure_period": DAYS(30), "notice": DAYS(30)}))
    A = w.agreement([("aggregator", agg), ("supplier", sup)], clauses, "Master agreement with termination for cause (hypothetical)")
    a, h = w.propose(agg, A, "2026-12-01T15:00:00Z")
    w.accept(a, sup, h, "2026-12-05T10:00:00Z")
    cidA = w.chain_id(a)

    def participation(m, start, commitment=False):
        cl = participation_clauses(w, cidA, start)
        if commitment:
            cl.insert(3, w.clause("commitment", "UP:Purchase-Commitment", {
                "category": "Hypothetical: the three listed items", "share": "0.80", "period": QUARTER, "due": DAYS(30)}))
        return w.agreement([("aggregator", agg), ("member", m), ("supplier", sup)], cl, f"Participation of {m.name}")

    # Member 1: active, tier B (attested, acknowledged by the supplier), commits 80% of category purchases.
    p1, ph = w.propose(m1, participation(m1, "2027-01-05T00:00:00Z", commitment=True), "2027-01-04T09:00:00Z")
    w.accept(p1, agg, ph, "2027-01-04T13:00:00Z")
    w.accept(p1, sup, ph, "2027-01-04T16:00:00Z")
    w.attest(p1, m1, "tier", "UP:Tier-Selection/selects",
             {"option": "B", "basis": "Hypothetical basis: prior-year category purchases"}, "2027-01-07T10:00:00Z", cosigners=[sup])
    # Member 2: joined, then gave 30 days' notice of termination for convenience.
    p2, ph = w.propose(m2, participation(m2, "2027-01-11T00:00:00Z"), "2027-01-10T09:00:00Z")
    w.accept(p2, agg, ph, "2027-01-10T13:00:00Z")
    w.accept(p2, sup, ph, "2027-01-10T16:00:00Z")
    w.attest(p2, m2, "exit", "UP:Termination-Convenience/notice", {}, "2027-01-25T09:00:00Z")
    # Member 3: proposed and signed by the aggregator; the supplier has not signed.
    p3, ph = w.propose(m3, participation(m3, "2027-03-01T00:00:00Z"), "2027-02-20T09:00:00Z")
    w.accept(p3, agg, ph, "2027-02-20T13:00:00Z")
    # The aggregator says the supplier missed the January sales report; the cure period runs 30 days.
    w.attest(a, agg, "cause", "UP:Termination-Cause/breach",
             {"description": "Hypothetical: the sales report for January 2027 was not delivered"}, "2027-03-01T09:00:00Z")
    return w, {"agg": agg, "sup": sup, "m1": m1, "m2": m2, "m3": m3}, "2027-03-15T00:00:00Z"


# ---------------------------------------------------------------------------
# 3. Overlay: an existing contract described without renegotiation
# ---------------------------------------------------------------------------

EXISTING_CONTRACT = """HYPOTHETICAL GROUP PURCHASING AGREEMENT (illustration only)
Between Hypothetical Legacy Purchasing Group and Example Surgical Products Inc.
Signed 1 March 2024. Term: 1 March 2024 to 1 March 2029.
Section 4: Supplier will pay an administrative fee of two percent of net sales, monthly, within 30 days of month end.
Section 5: Supplier will report net sales monthly within 15 days of month end.
Section 9: Prices are as set out in Exhibit A (two tiers).
Section 14: Indemnities, insurance, and recall procedures (not described in the Universal Paper overlay).
"""


def overlay():
    w = World()
    agg = Actor("Hypothetical Legacy Purchasing Group")
    sup = Actor("Example Surgical Products Inc.")
    doc_hash = "sha256:" + hashlib.sha256(EXISTING_CONTRACT.encode()).hexdigest()
    prices = {ITEMS[0]["id"]: ("12.00", "12.60"), ITEMS[1]["id"]: ("40.00", "41.50")}
    table = [{"item": GTIN(i), "by": {"Standard": USD(p[1]), "Committed": USD(p[0])}} for i, p in prices.items()]
    clauses = [
        w.clause("overlay", "UP:Overlay", {"document": doc_hash, "document_title": "Hypothetical Group Purchasing Agreement",
                                           "document_date": "2024-03-01T00:00:00Z", "governs": "document"}),
        w.clause("term", "UP:Fixed-Term", {"start": "2024-03-01T00:00:00Z", "end": "2029-03-01T00:00:00Z"}),
        w.clause("tiers", "UP:Tiers", {"tiers": [{"name": "Committed", "conditions": "As defined in Exhibit A of the existing agreement"},
                                                 {"name": "Standard", "conditions": "As defined in Exhibit A of the existing agreement"}],
                                       "prices": table}),
        w.clause("reporting", "UP:Sales-Reporting", {"reporter": "supplier", "recipient": "aggregator", "period": MONTH, "due": DAYS(15)}),
        w.clause("fee", "UP:Admin-Fee", {"payer": "supplier", "payee": "aggregator", "rate": "0.02", "report_clause": "reporting",
                                         "period": MONTH, "due": DAYS(30), "rounding": R2}),
    ]
    O = w.agreement([("aggregator", agg), ("supplier", sup)], clauses, "Overlay of an existing agreement (hypothetical)")
    o, oh = w.propose(agg, O, "2027-02-10T09:00:00Z", cosigners=[sup])  # both sign at once
    rep = {"period": period("2027-02-01T00:00:00Z", "2027-03-01T00:00:00Z"),
           "lines": [{"participation": "sha256:" + "0" * 64, "item": ITEMS[0], "quantity": "300", "net": USD("3600.00")}],
           "total_net": USD("3600.00")}
    w.attest(o, sup, "reporting", "UP:Sales-Reporting/report", rep, "2027-03-12T12:00:00Z")
    return w, {"agg": agg, "sup": sup}, "2027-04-15T00:00:00Z"


# ---------------------------------------------------------------------------
# Tampering (fault injection) for traces
# ---------------------------------------------------------------------------

def tamper_fee_rate(data):
    """Supplier's ERP copy: the admin fee rate in the master agreement was quietly changed after signing."""
    d = copy.deepcopy(data)
    for c in d["chains"][0][0]["body"]["agreement"]["clauses"]:
        if c["n"] == "fee":
            c["params"]["rate"] = "0.015"
    return d


def tamper_backdate(data, actor: Actor, chain_pos: int, event_idx: int, new_at: str):
    """Member's copy: a tier attestation re-signed by the member with an earlier date."""
    d = copy.deepcopy(data)
    E = d["chains"][chain_pos][event_idx]
    E["at"] = new_at
    E.pop("sigs")
    from universal_paper.crypto import attach
    d["chains"][chain_pos][event_idx] = attach(E, actor.key.sign_obj(E))
    return d


def tamper_drop_signature(data, chain_pos: int, event_idx: int):
    """Aggregator's copy: an acceptance whose signature is missing."""
    d = copy.deepcopy(data)
    d["chains"][chain_pos][event_idx]["sigs"] = []
    return d


# ---------------------------------------------------------------------------

def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def main():
    from universal_paper.trace import make_trace

    out = ROOT / "examples"
    traces = out / "traces"
    evals = lambda b: [  # noqa: E731
        {"id": "aggregator", "name": "Aggregator CLM", "data": b},
        {"id": "supplier", "name": "Supplier ERP", "data": b},
        {"id": "member", "name": "Member spreadsheet", "data": b},
    ]

    # 1. Conventional
    w, actors, at = conventional()
    data = w.data()
    write(out / "conventional" / "bundle.json", data)
    meta = {"title": "Conventional GPO arrangement",
            "description": "An aggregator–supplier agreement with three tiers and an admin fee, two members joining through participation and tier attestation, monthly sales reports, fee payments, and one tier change. All values are hypothetical."}
    write(traces / "conventional.trace.json", make_trace(data, evals(data), meta, at))
    # Fault injection variants
    t1 = evals(data)
    t1[1] = {**t1[1], "data": tamper_fee_rate(data), "tampered": "The admin fee rate in this copy of the master agreement was changed from 2% to 1.5% after signing."}
    write(traces / "conventional.tamper-supplier-fee.trace.json",
          make_trace(data, t1, {**meta, "title": "Fault: Supplier copy has a changed fee"}, at))
    t2 = evals(data)
    # chain 1 = participation of member 1; event 3 = its first tier attestation (2027-01-07). Backdate before the previous event.
    t2[2] = {**t2[2], "data": tamper_backdate(data, actors["m1"], 1, 3, "2027-01-03T10:00:00Z"),
             "tampered": "The member's tier attestation was re-signed with an earlier date (backdated)."}
    write(traces / "conventional.tamper-member-backdate.trace.json",
          make_trace(data, t2, {**meta, "title": "Fault: Member copy has a backdated attestation"}, at))
    t3 = evals(data)
    t3[0] = {**t3[0], "data": tamper_drop_signature(data, 0, 1),
             "tampered": "The supplier's signature on its acceptance of the master agreement is missing from this copy."}
    write(traces / "conventional.tamper-aggregator-missing-signature.trace.json",
          make_trace(data, t3, {**meta, "title": "Fault: Aggregator copy is missing a signature"}, at))

    # 2. Generative
    w, actors, at = generative()
    data = w.data()
    write(out / "generative" / "bundle.json", data)
    write(traces / "generative.trace.json", make_trace(data, [
        {"id": "cooperative", "name": "Cooperative agent runtime", "data": data},
        {"id": "supplier", "name": "Supplier ERP", "data": data},
        {"id": "hospital", "name": "Hospital procurement agent", "data": data},
    ], {"title": "Generative: one member, two aggregators, agents under Mandates",
        "description": "An aggregator with no staff, run entirely by an agent under a Mandate, and a conventional aggregator. One hospital, acting through its own agent, participates in both at once without conflict. Two out-of-bounds agent actions are rejected under A9. All values are hypothetical."}, at))

    # 3. Overlay
    w, actors, at = overlay()
    data = w.data()
    write(out / "overlay" / "bundle.json", data)
    (out / "overlay" / "existing-contract.txt").write_text(EXISTING_CONTRACT)
    write(traces / "overlay.trace.json", make_trace(data, evals(data), {
        "title": "Overlay: an existing agreement described, not replaced",
        "description": "A contract signed in 2024 is described in Universal Paper in 2027 without renegotiation. It is identified by its document hash, and duties start only from the overlay's signing. All values are hypothetical."}, at))

    # 4. Confidential
    w, actors, at = conventional(sealed=True)
    full = w.data()
    hidden = w.data(disclosures=False)
    write(out / "confidential" / "bundle.json", full)
    write(out / "confidential" / "bundle.hashes-only.json", hidden)
    write(traces / "confidential.trace.json", make_trace(full, [
        {"id": "aggregator", "name": "Aggregator CLM", "data": full},
        {"id": "supplier", "name": "Supplier ERP", "data": full},
        {"id": "observer", "name": "Observer (hashes only)", "data": hidden, "hashes_only": True},
    ], {"title": "Confidential: verification from Seals alone",
        "description": "The conventional story with every price, rate, quantity, and amount sealed. The observer holds no disclosures, yet reaches the same verdict and the same state hash at every step. All values are hypothetical."}, at))
    # 5. Mandate cap (bundle only: the out-of-bounds step is for an agent to try)
    w, actors, at = mandate_cap()
    write(out / "mandate-cap" / "bundle.json", w.data())
    # 6. What-if (bundle only: for the simulate_purchase, simulate_termination and simulate_eligibility tools)
    w, actors, at = what_if()
    write(out / "what-if" / "bundle.json", w.data())
    print("examples written")


if __name__ == "__main__":
    main()
