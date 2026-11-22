# 06 — Initial Term library

Sixteen Terms covering term and renewal, termination, participation, tiers, attestation, pricing reference, reporting, fees, fee disclosure, audit, purchase commitments, notices, governing law, and overlays of existing contracts.

- Each Term has a markdown page (ID, parameters, machine definition, claims, rendering) and a JSON file that is its canonical machine definition. The pages are generated from the JSON's source data by `tools/gen_terms.py`, so the two cannot drift.
- Every machine definition uses only the six clause forms in [04-inference §3](../04-inference.md#3-clause-forms). No Term needs special code.
- **No parameter anywhere has a default value.** Every price, rate, period, count, and threshold is supplied by the parties ([A6](../03-axioms.md)).
- Every definition carries `provenance` (drafted by, reviewed by, version history). None has been reviewed by counsel yet.
- Each definition's hash is listed under [Definition hashes](#definition-hashes) below.
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

## Definition hashes

A Clause pins its Term by this hash (`def`). It is `hash()` of the JSON file (spec/01-domain.md §1.2). `tests/test_terms.py` recomputes every one.

| Term | Definition hash |
|---|---|
| `UP:Fixed-Term` | `sha256:0f0c265a43d9fa361ef55b8136d4cad9d5e11ebabe79a8ea93e87f352b68f372` |
| `UP:Renewing-Term` | `sha256:19126e50a5e29d7b86c6c2cac51bd3b743048e3139b0b02763cb6d685d5e5d22` |
| `UP:Termination-Convenience` | `sha256:6636ada39098601025c16e5ea201ed2ccde106ee20a1c499c815d26e14703cff` |
| `UP:Termination-Cause` | `sha256:372d5a69edc5f19ca1f986c67312957711d4b2bc45d61457ce85dfd630faa492` |
| `UP:Participation` | `sha256:b4702b4663f074fff69b20fa34d5eaf46e5c26d1912365cc9288f159e5889701` |
| `UP:Tiers` | `sha256:d93331fba3ba3e376b1e9b40ee1ea9dedecdc1db8da49981aaa4ce56bbc39f70` |
| `UP:Tier-Selection` | `sha256:caca2ea12ee3bdab2d1c22cd36ffa18970e3e65991a60b9ca0724982f0e710e5` |
| `UP:Price-Reference` | `sha256:589002827fe61e7caefda7f6c7221de0f2a6f3dd12aea13d731369c9efefae12` |
| `UP:Sales-Reporting` | `sha256:dbef07d6cee32d6bf7293f28239c09b66efa98ddb73195ce329568d3bc7cba84` |
| `UP:Admin-Fee` | `sha256:86262a69a7bfba34d47e0f3052aecb541702abea12286e098e60333fa1e24168` |
| `UP:Fee-Disclosure` | `sha256:bbee8002e913a12e1472c6d7f0763f94a07f3dc6451048b3cece180d359149ac` |
| `UP:Audit` | `sha256:8d60e3ce9a589784026b794689da8d9fe153f926552b99892fd00038409d41a8` |
| `UP:Purchase-Commitment` | `sha256:878498986dfb65d2060889abbff61c30a2c285c793c75dd505a1eb972c49ce34` |
| `UP:Notices` | `sha256:ac1e78bc3e0ed82e0cda2f203c4cd5446cb1da7ef7ce1dd972763ca76fcc59e1` |
| `UP:Governing-Law` | `sha256:0b111a86bffafa0e54bacb62d294082939bfb1e61cd121f41b099f54295e49d2` |
| `UP:Overlay` | `sha256:120f918ad9a1a2a8f55d269f44a5fdb18ed19ca6a235142300330a962338b94a` |
