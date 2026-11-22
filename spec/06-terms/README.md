# 06 — Initial Term library

Sixteen Terms covering term and renewal, termination, participation, tiers, attestation, pricing reference, reporting, fees, fee disclosure, audit, purchase commitments, notices, governing law, and overlays of existing contracts.

- Each Term has a markdown page (ID, parameters, machine definition, claims, rendering) and a JSON file that is its canonical machine definition. The pages are generated from the JSON's source data by `tools/gen_terms.py`, so the two cannot drift.
- Every machine definition uses only the six clause forms in [04-inference §3](../04-inference.md#3-clause-forms). No Term needs special code.
- **No parameter anywhere has a default value.** Every price, rate, period, count, and threshold is supplied by the parties ([A6](../03-axioms.md)).
- Every definition carries `provenance` (drafted by, reviewed by, version history). None has been reviewed by counsel yet.
- Term definition hashes are not pinned yet. They will be computed once the canonical encoding is implemented, and listed here.
- **[PROVISIONAL]** The library covers the aggregator–supplier layer and the member participation layer about equally (open question 1).

Which layer each Term usually sits in:

| Layer | Terms |
|---|---|
| Aggregator–supplier master agreement | Fixed-Term or Renewing-Term, Tiers or Price-Reference, Sales-Reporting, Admin-Fee, Audit, Termination-Convenience, Termination-Cause, Notices, Governing-Law, Overlay |
| Member participation | Participation, Tier-Selection, Fee-Disclosure, Purchase-Commitment, Fixed-Term or Renewing-Term, Termination-Convenience, Notices |

<!-- table -->

| Term | Family | Forms | Purpose |
|---|---|---|---|
| [UP:Fixed-Term](UP-Fixed-Term.md) | Term and renewal | Window | Sets when the Agreement is in force, with no renewal. |
| [UP:Renewing-Term](UP-Renewing-Term.md) | Term and renewal | Window | Sets an initial term that renews automatically unless a named role opts out by notice. |
| [UP:Termination-Convenience](UP-Termination-Convenience.md) | Termination | Exit | Lets a named role end the Agreement without cause, by notice. |
| [UP:Termination-Cause](UP-Termination-Cause.md) | Termination | Exit | Lets a role end the Agreement after giving notice of a material breach that is not cured in time. |
| [UP:Participation](UP-Participation.md) | Parties and participation | Link | Makes this Agreement a participation under a parent Agreement, binding the parent's aggregator and supplier as signers. |
| [UP:Tiers](UP-Tiers.md) | Tiers and pricing | Valuation | Lists named tiers, describes the conditions for each, and sets a price for each Item in each tier. |
| [UP:Tier-Selection](UP-Tier-Selection.md) | Tiers and attestation | Selection | Lets the Member attest that it qualifies for a tier; the selection takes effect when the Supplier acknowledges it. |
| [UP:Price-Reference](UP-Price-Reference.md) | Pricing reference | Valuation | Prices Items as a stated factor of a price list that a named role attests. |
| [UP:Sales-Reporting](UP-Sales-Reporting.md) | Reporting | Duty | Requires a role to report sales made under the Agreement each period, by a deadline. |
| [UP:Admin-Fee](UP-Admin-Fee.md) | Fees | Duty | Requires a payer role to pay a payee role a fee computed as a stated rate of reported net sales each period. |
| [UP:Fee-Disclosure](UP-Fee-Disclosure.md) | Fees | Duty | Requires the aggregator to disclose to the member, each period, the administrative fees it received from the supplier under the parent Agreement. |
| [UP:Audit](UP-Audit.md) | Audit | Duty | Lets a role request an audit of another role's records under the Agreement, a limited number of times per period. |
| [UP:Purchase-Commitment](UP-Purchase-Commitment.md) | Compliance | Duty | Records a member's commitment to purchase a stated share of its purchases in a stated category under the Agreement, with periodic attestation. |
| [UP:Notices](UP-Notices.md) | General | none | Makes signed attestations on the agreement's chain the binding method of giving notice. |
| [UP:Governing-Law](UP-Governing-Law.md) | General | none | Names the law that governs the Agreement and the forum for disputes. |
| [UP:Overlay](UP-Overlay.md) | General | none | Declares that this Agreement describes an existing contract, identified by the hash of its document, without amending or replacing it. |
