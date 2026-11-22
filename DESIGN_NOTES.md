# Design notes

This file records every place the v0 draft cut, merged, or added a primitive relative to the brief's first-pass lists, and why. It also records known limits, one design tension, future extensions kept out of the core, and the open questions for the steward.

Status: spec drafted and reviewed at the pause on 2026-11-22; reference interpreter, schemas, examples, traces, tests, and Explorer built on it as drafted.

## 1. The primitive set after pressure-testing

| | Brief's candidates (14) | v0 draft |
|---|---|---|
| Kept as primitives (7) | Party, Role, Term, Agreement, Event, State, Mandate | same |
| Kept as value primitives (2) | Identifier, Seal | Value types inside other objects, with no identity or lifecycle of their own |
| Made derived (1) | Commitment | Computed by `obligations(S, t)`, never authored |
| Merged away (4) | Tier, Attestation, Item, Signature | See §2 |
| Added (non-primitive) | — | Six **clause forms** that Terms are built from; **Bundle** container; **Clause** (a Term with bound parameters) |

## 2. Cuts, merges, and additions

### Merged: Tier → a Term built on two clause forms
A tier is "a named set of conditions that selects a price schedule". That is two separate ideas: *recording which option applies to a party* (Selection) and *looking up a value by option* (Valuation). Neither is specific to pricing tiers. The same Selection form records any designation, and the same Valuation form prices anything. Keeping Tier as a primitive would bake one commercial structure into the core, against "use-case blind" and "orthogonal". `InTier` and `tier()` survive as defined abbreviations ([02 §3](spec/02-predicates-functions.md)).

### Merged: Attestation → an Event kind
The brief lists Attestation as a primitive and "attestation" as an Event type. That is the same thing twice. An attestation is an `attest` Event. Purchases, sales reports, tier qualification, payments, notices, and termination notices are all attestations whose meaning is supplied by the Term that consumes them.

### Merged: Item → Identifier
An Item has no lifecycle and no rules of its own in the core. Everything the core needs from it is a reference into an existing scheme (GTIN, NDC, …), which is exactly what Identifier is. Item is now "an Identifier used where an Item is expected".

### Merged: Signature → the encoding
A signature is how Events and Mandates are authenticated, not a thing agreements talk about. It is defined once in the encoding ([01 §1.3](spec/01-domain.md#13-keys-and-signatures)).

### Made derived: Commitment
Commitments depend on the evaluation time (periods end, deadlines pass). If they were stored in State, State would depend on when it was computed, breaking determinism. They are the output of `obligations(S, t)`.

### Kept and justified: Mandate
Without it, an agent either holds the principal's key (unbounded authority) or cannot act. Neither satisfies A9. It cannot merge into Agreement (a Mandate is one-sided, exists before any agreement, and spans chains) or Event (it is not part of any one chain's history).

### Kept as value primitives: Identifier and Seal
Both are essential vocabulary but have no identity or lifecycle, so they are value types, not domain objects. Identifier enforces "never mint a competing scheme" by design: the core has no ID scheme except `UP:Local`. Seal is what makes A10 possible.

### Cut from the lifecycle: Draft and Amended
- **Draft** needs no consensus, so it is not a chain state. An unsigned Agreement is just data.
- **Amended** is not a status. An amendment is a transition from Executed to Executed under a new Agreement hash. The history is the chain.

### Added to the lifecycle: Executed, Lapsed, Suspended
"Everyone signed" and "in force" differ when the start date is in the future, so **Executed** is distinct from **Active**. **Lapsed** (proposal expired unsigned) and **Suspended** (participation in force but its master is not) make sure every (chain, time) pair has exactly one status.

### Event kinds reduced to three: propose, accept, attest
The brief lists purchase, attestation, proposal, acceptance, amendment, termination. Amendment is a `propose` that supersedes. Termination is an `attest` (a notice) that an Exit clause gives effect to, or an amendment that moves the end date. Purchases are attestations. **Expiry is not an Event at all**: it follows from time, so `Active(A, t)` turns false with nothing recorded.

### Added: six clause forms (Window, Exit, Selection, Valuation, Duty, Link)
The brief asks for each Term to have a "machine definition". Two easy answers fail. Prose plus interpreter code per Term makes the interpreter the real definition, failing the ontological test. A general rule language drifts toward a smart-contract language (the Accord Project lesson). The draft takes a middle path: a small, closed set of forms, each doing one thing, defined precisely enough to evaluate by hand. Every Term is a parameterized binding of forms, so a new Term needs no new code. The 16 Terms in the library need nothing beyond these six. This is the most consequential design choice in the draft, and the one most worth the steward's review.

### Added: Link form, instead of a "participation" construct
Participation is an ordinary Agreement with a Link to its master. The Link binds the master's aggregator and supplier as required signers of each participation, so they consent individually, and no special sub-agreement or "who may participate" clause is needed. An earlier draft had a separate Participation-Terms clause on the master. It was cut because the Link binding already gives the master's parties a veto.

### Added axioms: A11 Closed evidence, A12 Single attribution, A13 Resolved precedence
- **A11**: without it "intrinsic validity" is ambiguous, because tiers and purchases depend on outside facts. The core never treats a claim as true; it records that it was attested and acknowledged.
- **A12**: every Event belongs to one chain. This is what lets one member participate in two aggregators' agreements without conflict.
- **A13**: turns "exceptions are first-class" into a validity rule. Conflicts resolve by explicit `over`, then strict specificity, otherwise the Agreement is invalid. Clause order never decides.

### Predicates and functions
`HasRole` gained an agreement and time argument (a role is held within an agreement). `fee()` was removed (fees are Commitments). `apply`, `Discharged`, `Covers`, `SpeaksFor`, `Opens`, and `reveal` were added. Details in [02 §4](spec/02-predicates-functions.md).

### Kept from the brief, with the reasoning made explicit
A3 references the prior **State** hash, not the prior Event hash. Since State contains the last Event's hash, this still links the chain, and it makes every signer commit to their computed view of the State, so divergent evaluators are caught at the first disagreement. This is what the Explorer will make visible.

## 3. Tension: Mandate bounds on sealed values

A9 says an agent's action is valid only if every value is within its Mandate's bounds. A10 says validity can be checked from Seals alone. If an agent proposes a sealed price, a hashes-only evaluator cannot check the price against the bound. The two axioms collide.

Options:
1. **Bounded values must be unsealed** in agent-signed Events. A10 stays strict. Cost: values an agent sets within bounds are visible to whoever holds that chain (normally just its parties).
2. **Treat bound checks as disclosure-dependent.** A hashes-only evaluator reports "unverifiable" for those Events. Weakens A10.
3. **Zero-knowledge range proofs** prove the sealed value is within bounds without revealing it. Out of scope for v0, but the Seal format reserves room for it.

**Provisional choice: option 1**, written into coverage rule 6 ([01 §10](spec/01-domain.md#10-mandate)), with option 3 as the planned upgrade. Flagged for the steward.

## 4. Known limits of v0

- **A chain is a single line.** Two parties writing at once must rebase onto the newer State and re-sign. Fine for agreement-level events, and participations are separate chains, but high-volume purchase reporting on one master chain would contend. Batched reports (one attestation per period) keep this manageable.
- **Time is asserted, not trusted.** `at` is the author's claim. The chain enforces non-decreasing order, and counterparties' acknowledgments bound backdating in practice, but no trusted clock exists. This matches paper contracts.
- **No Mandate revocation** other than expiry. Revocation needs a place to record it that every evaluator sees, which the substrate-agnostic core lacks.
- **No key rotation.** A Party is its key. A lost key means amending every agreement it is party to.
- **No cross-chain atomicity.** Two chains cannot change in one step.
- **Tier conditions are descriptive.** Whether a member meets a tier is established by attestation and acknowledgment, not computed (A11).
- **No currency conversion.** Amounts in different currencies never combine.

## 5. Future extensions (kept out of the core)

Each was tempting because a specific use case needs it, and was deferred per the brief.

- **Distributor role and chargebacks.** The mapping guide shows 845, 844, and 867 all involve distributors, and 844's chargeback needs (reference cost − contract price) × quantity, which the Duty form cannot express. Depends on open question 4. Probably the first extension that real use will demand.
- **Computed conditions**: tier qualification evaluated from on-chain purchase totals, for richer simulation.
- **Mandate revocation and sub-delegation.**
- **Key rotation.**
- **Zero-knowledge commitments and range proofs** under a new Seal prefix.
- **Partial ordering or per-clause sub-chains** for high-volume reporting.
- **More than one Link per Agreement** (e.g. a participation that depends on a master and a separate membership agreement).
- **Price-change-by-notice** (a supplier updates prices with a notice period), expressible today through Price-Reference but worth a dedicated Term.
- **An optional ledger substrate** for ordering and availability. The language must keep working without one.
- **Translated renderings**, with the binding language stated.

## 5a. Notes from building the interpreter

- **Rejected events stay in a bundle.** An evaluator skips an invalid event, and the next event must build on the last *valid* state. This is how the generative example records two out-of-bounds agent actions without breaking its chains.
- **Trace consensus is per evaluator, over all chains.** Each evaluator's "world hash" is the hash of its current State hash for every chain. Equal world hashes mean exact agreement.
- **Every clause form needed only the fields in the spec.** No Term in the library required special code, which supports the clause-form approach.
- **Spec gap found:** the Duty form needs a `clause` on its `amount.base` so a fee can read another clause's reports. The spec text now says so.

## 5b. A second engine, and how it is held to the first

The Explorer computes its Playground and proving ground in the browser, so the interpreter was ported to JavaScript (`explorer/src/`), including dependency-free SHA-256, SHA-512, and Ed25519. Two implementations of one spec are a test of the spec: anything ambiguous shows up as a mismatch.

- **Conformance.** `tools/dump_conformance.py` records every example trace, rendering, and simulation from Python. `tests/js_conformance.mjs` requires the JavaScript engine to reproduce all of them exactly, including every check, reason, state hash, and derived value. It passed on the first complete run with no spec changes, which is some evidence that the spec text is precise enough to implement twice.
- **Proving ground.** `up-lab.js` generates random agreements from a seed (parties, tiers, items, prices, fee rate and rounding mode, monthly or quarterly reporting, tier changes, short, late, and skipped payments, optional agents under Mandates, optional sealing) and checks eight invariants: honest events accepted, determinism across four evaluators (one with every object's fields reordered), every tampered copy caught at the tampered event with history before it unchanged, Mandate bounds, sealed-observer agreement, fees against integer arithmetic, prices against the tier in force, and rendering bound to the fingerprint. Seven attack types are tried. `tests/js_lab.mjs` runs 60 fixed seeds in CI.
- **What this does not prove.** Random runs explore the shapes the generator knows. They do not cover Terms the generator never uses (Audit, Termination-Cause, Price-Reference, Overlay, Purchase-Commitment) beyond the fixed examples, and they share the engine with the Playground, so a bug common to both engines would only be caught by the Python conformance check.

## 6. Open questions for the steward

From the brief (asked, not decided). Each has a provisional assumption so drafting could continue, marked **[PROVISIONAL]** in the spec.

| # | Question | Provisional assumption |
|---|---|---|
| 1 | Which layer should the Term library emphasize: aggregator–supplier, member participation and price activation, or both? | Both about equally. The library has Terms for each layer, and several (term, termination, notices) serve both. |
| 2 | Publish under Jo's name, Uppercentile, or a neutral project name? | Uppercentile as steward (as the expanded brief says), "Universal Paper" as the project name, publisher field left blank in Term provenance. |
| 3 | How are spec changes proposed and versioned? | Public changelog plus RFC process, written into the Neutrality Charter. Comment periods and decision rules not yet set. |
| 4 | Should Role stay fixed at three or be extensible from the start? | Fixed at three in v0, extensible only by spec version. The mapping guide suggests distributor will be needed soon. |

Design choices made in drafting that the steward may want to confirm:

- The six clause forms as the only way to define Term meaning (§2).
- Three Event kinds, with termination as a notice and expiry as a function of time (§2).
- Mandate bounds on sealed values: option 1 (§3).
- Events reference the prior State hash, so the chain is strictly linear (§2, §4).
