# 07 — Mapping guide

Universal Paper describes before it replaces (property 8). This guide shows how the artifacts that GPOs, suppliers, distributors, and members already exchange map onto Universal Paper primitives. In v0 it is a written mapping only. No converters are specified or built.

> **Verification note.** X12 transaction sets are described here at the level of what each set communicates, not segment by segment. Segment-level mappings should be written with, and checked by, people who operate these feeds. **[DRAFT: not yet reviewed by EDI practitioners]**

## 1. The mapping principle

Every existing artifact is one of two things:

- **An input**: a statement that some fact is true. It maps to an `attest` Event (and, where the counterparty confirms it, an `accept`).
- **An output**: a report of what is currently agreed or owed. It maps to a **projection**, a view computed from the chain at a time t (`state`, `Active`, `Eligible`, `selection`, `price`, `obligations`).

Outputs become checkable: any recipient can recompute a projection from the chain and compare. Inputs stay what they are, claims by one party, but each one is signed, timestamped, and tied to one agreement (A11, A12).

Nothing has to be replaced at once. A party can keep sending its existing files while also recording the same facts as Events, and compare the two.

## 2. Agreements on existing paper (overlay)

To describe an existing contract without renegotiating it:

1. Compute the SHA-256 hash of the signed contract document as the parties hold it.
2. Write an Agreement with the same parties in their roles, an [UP:Overlay](06-terms/UP-Overlay.md) clause naming that hash with `governs: "document"`, and Clauses for the provisions that Universal Paper can express (term, renewal, tiers and prices, reporting, fees, audit, termination).
3. Leave every provision the Term library cannot express in the document. The overlay does not need to be complete. It needs to be accurate for what it covers.
4. All parties sign the overlay Agreement. Their signatures attest that it accurately describes their existing contract.

From then on, the chain records events under the existing contract. Duties arise only for periods ending after the overlay is signed ([04-inference §3.5](04-inference.md#35-duty)), so an overlay of a contract signed years ago does not create a backlog of overdue duties.

## 3. GPO rosters and membership files

A GPO roster lists the facilities that belong to the GPO and can buy on its agreements, typically with names, addresses, identifiers (HIN, GLN, DEA, 340B ID), affiliation dates, and sometimes tier or category designations.

| Roster content | Universal Paper |
|---|---|
| One member facility | A Party with the member role, carrying its Identifiers (`ids`) |
| "Member is on the roster for agreement X" | An executed participation chain P with a Link to master X ([UP:Participation](06-terms/UP-Participation.md)) |
| Affiliation start and end dates | P's Window clause |
| Adds | Genesis `propose` and `accept`s on a new participation chain |
| Deletes, terminations | An Exit notice on P, or P's window ending |
| Tier or category designation | `selection(P, s, m, t)` from a [UP:Tier-Selection](06-terms/UP-Tier-Selection.md) clause |
| The roster as a whole, as of a date | A **projection**: the set of participation chains linked to X with `Active(P, t)` |

Because each participation is its own chain, a roster need not be shared as a whole. A member can prove its eligibility to a supplier or distributor by disclosing its own participation chain and nothing else.

## 4. Eligibility and membership verification files

Files that confirm whether a given facility may buy at a given contract price on a given date.

| Content | Universal Paper |
|---|---|
| "Facility F is eligible for contract X on date d" | `Eligible(F, X, d)` |
| Effective and end dates of eligibility | The interval over which `Active(P, t)` holds |
| Eligible tier | `selection(P, s, F, d)` |

An eligibility file is a projection. Two parties that hold the same chains cannot disagree about it.

## 5. X12 EDI sets used in contract pricing and chargebacks

| Set | What it communicates today | Universal Paper mapping | Gap in v0 |
|---|---|---|---|
| **845** Price Authorization Acknowledgment/Status | A supplier tells trading partners (commonly distributors) about a contract: its identity, effective and expiration dates, covered items, contract prices, and eligible customers. | A **projection** of the master and its participations at time t: contract identity ↔ master ChainId; dates ↔ `window`; items and prices ↔ the Valuation clause and `price`; eligible customers ↔ active participations and their tiers. | The usual recipient is a distributor, which has no Role in v0. A distributor can only receive the projection, not be a party to the agreement. |
| **844** Product Transfer Account Adjustment | A distributor claims a chargeback from a supplier: for sales to an eligible customer under a contract, the difference between the distributor's acquisition cost and the contract price. | Each claim line ↔ an `attest` by the distributor of a sale (customer, item, quantity, contract). The eligibility and contract price are **computed**, not asserted: `Eligible` and `price` at the sale date. | Needs a distributor Role, and a way to compute a chargeback amount as (reference cost − contract price) × quantity. The Duty form's `amount` (rate × sum) cannot express a difference. See DESIGN_NOTES, Future extensions. |
| **849** Response to Product Transfer Account Adjustment | The supplier accepts, rejects, or adjusts each chargeback line, with reasons. | Accepting a line ↔ an `accept` of the claim. Rejecting ↔ an `attest` of a rejection referencing it. | Today's common rejection reasons (customer not eligible, wrong price, contract not active on that date) become **deterministic**: every party computes the same answer from the chain, so those disputes disappear. Disputes about facts outside the chain remain. |
| **867** Product Transfer and Resale Report | A distributor reports its sales of a supplier's products to end customers (tracing). | The sales lines of a [UP:Sales-Reporting](06-terms/UP-Sales-Reporting.md) report, which is also the base for the [UP:Admin-Fee](06-terms/UP-Admin-Fee.md) Duty. | In v0 the supplier is the reporting role. A distributor reporting directly needs the distributor Role. |

## 6. Summary of gaps

The mapping exercise shows one consistent gap: **the distributor**. The 845, 844, and 867 flows all involve a distributor as a party in practice, and the chargeback in 844 needs a computed difference that no v0 clause form provides. Both are recorded in DESIGN_NOTES and tie to open question 4 (fixed or extensible Roles). Everything else in this guide maps onto the v0 primitives without new constructs.
