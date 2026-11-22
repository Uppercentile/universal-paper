# 03 — Axioms

The axioms are the consensus rules. They always hold. An object or chain that violates any of them is invalid, whoever produced it and whatever any system says about it.

Each axiom says how it is checked, so that it can be verified by hand. A1–A10 are the axioms in the brief, tightened. A11–A13 are additions, explained at the end.

## A1 Composition

A valid Agreement is built only from the primitives of this spec and from Clauses whose Terms belong to a **single declared spec version**.

*Check:* `Agreement.spec` equals the `spec` of every pinned TermDefinition. Every Clause's `def` equals `hash` of a TermDefinition in the Bundle whose `id` equals the Clause's `term`. Every declared parameter is bound, with a value of the declared type or a Seal (only where sealing is allowed, [01-domain §3.3](01-domain.md#33-what-may-be-sealed)). Clause names are unique. `parties` is non-empty and sorted. At most one Window clause and at most one Link clause.

## A2 Unanimity

An Agreement is executed, or replaced by an amendment, only when **every required signer has signed the same Agreement hash**. The required signers are every Party in the Agreement's `parties` and, for an amendment, every Party in the Agreement being replaced.

*Check:* for the `propose` Event P that carries the Agreement, every required signer p either has a co-signature on P that speaks for p, or is the `by` of a valid `accept` targeting `hash(P)`, before P's `expires` if it has one.

## A3 Chained transitions

State changes only through Events that satisfy the transition rule for their kind ([05-lifecycle](05-lifecycle.md)). Every non-genesis Event carries the ChainId and the hash of the State it was applied to.

*Check:* for each Event `Eₙ` (n ≥ 1): `Eₙ.chain = hash(E₀)`, `Eₙ.prev = hash(Sₙ₋₁)`, and `apply(Sₙ₋₁, Eₙ) ≠ ⊥`.

Consequence: two Events cannot both follow the same State in one chain. A chain is a single line. (Concurrent writers must rebase. See DESIGN_NOTES, "Known limits".)

## A4 Determinism

Given the same Bundle and the same evaluation time `t`, every evaluator derives the same State, the same reported status, and the same Commitments, with the same hashes.

*Check:* the spec defines every computation exactly, including decimal rounding ([04-inference §6](04-inference.md#6-arithmetic)), calendar arithmetic ([04-inference §2](04-inference.md#2-time-and-period-arithmetic)), and conflict resolution ([04-inference §4](04-inference.md#4-exceptions-and-precedence)). Nothing depends on the evaluator's clock, locale, floating point, iteration order, or the order in which Clauses are listed.

## A5 Non-retroactivity

No Event can alter a past State. A correction is a new Event.

*Check:* follows from A3, since each Event commits to the hash of the prior State. In addition, every Event's `at` is greater than or equal to `S.at`, and no clause form uses an Event to change a fact as of a time earlier than that Event's `at`.

## A6 Value neutrality

The core, every Term definition, and every Mandate format define **no** default, suggested, or typical value for any price, discount, fee, rate, threshold, volume, quantity, or period. Every such value is supplied by the parties.

*Check:* parameter declarations have only `type` and `doc`, so there is nowhere to put a default. Clause-form fields that carry amounts, rates, periods, or counts are parameter references, never literals. Rendering templates contain no numerals other than those interpolated from parameters.

## A7 Role symmetry

Rules refer to Roles, never to Party identities.

*Check:* no TermDefinition or rule in this spec names a public key, an Identifier, or an organization. Inside an Agreement, Clauses refer to Roles. The `parties` list is the only place that binds a Role to a key.

## A8 Rendering binding (Ricardian)

The human-readable rendering of an Agreement is generated deterministically from its machine form, and both are covered by the same hash. There can never be a "legal version" and a "data version" that disagree.

*Check:* `render(Ag, D)` ([04-inference §7](04-inference.md#7-rendering)) is a pure function of the Agreement, the TermDefinitions it pins (whose `render` templates are inside their hashes), and the set of Disclosures `D`. Each sealed value renders as its value when D opens it, and as `[sealed sha256:…]` otherwise. The seal binds the value, so every party's rendering is fixed by `hash(Ag)`.

## A9 Bounded delegation

An Event signed by an agent is valid only if a valid, unexpired Mandate from the principal Party covers that Event's kind and every variable value involved. Out-of-bounds agent actions are invalid by definition, not merely disputed.

*Check:* wherever a rule requires a signature by Party p, the requirement is `SpeaksFor(E, p)` ([02](02-predicates-functions.md)). An agent signature counts only if `Covers(M, E)` for the Mandate M it references ([01-domain §10](01-domain.md#10-mandate)).

## A10 Verifiable confidentiality

Validity can be checked using Seals alone. Revealing a confidential value is never required to verify that an Agreement or transition is valid, only to compute values that depend on it.

*Check:* every check in `apply` and in A1–A9, A11–A13 reads only structural fields, which cannot be sealed ([01-domain §3.3](01-domain.md#33-what-may-be-sealed)). State stores sealed values as they appear ([01-domain §9](01-domain.md#9-state)). An evaluator with no Disclosures therefore reaches the same verdict and the same State hash as one with all of them.

Mandate Bounds are the one place a validity check reads a value. Coverage rule 6 ([01-domain §10](01-domain.md#10-mandate)) requires such values to be unsealed, so A10 still holds without exception. **[PROVISIONAL]** See [DESIGN_NOTES, "Tension"](../DESIGN_NOTES.md#3-tension-mandate-bounds-on-sealed-values).

## A11 Closed evidence

Evaluation uses only the Bundle and this spec. Facts about the outside world (a purchase happened, a member has a certain bed count, a payment cleared) enter only as `attest` Events. The core never treats a claim as true. It records that a claim was **attested** and, where a Term requires it, **acknowledged** by another role.

*Check:* every input to `apply`, `obligations`, `selection`, and `value` is a field of an Event, State, Agreement, Mandate, TermDefinition, or Disclosure in the Bundle, or the evaluation time.

## A12 Single attribution

Every Event belongs to exactly one chain. An effect on another Agreement happens only through that Agreement's own chain, or through a Link read by a clause form.

*Check:* an Event's `chain` field names exactly one chain, and `apply` reads other chains only through `parents(A)`.

## A13 Resolved precedence

Where two Clauses of an Agreement would give different answers to the same question, the answer is decided by **explicit precedence, then specificity**, and never by the order of Clauses or by interpreter accident. If neither decides it, the Agreement is invalid.

*Check:* the conflict and resolution rules of [04-inference §4](04-inference.md#4-exceptions-and-precedence). The `over` relation is acyclic. Every conflicting pair is ordered by `over` or by strict specificity.

---

## Notes on the axioms

- **A2** names who the required signers are on amendment, which the first pass left open.
- **A3** keeps the brief's choice that Events reference the prior *State* hash. Since State includes the last Event's hash, this links the chain, and it also makes each signer commit to their computed view of the State, so divergent interpreters are caught at the first Event where they disagree. This is what the Explorer's side-by-side evaluators make visible.
- **A10** is satisfiable because of a design rule rather than cryptography: State never stores computed numbers, and nothing structural may be sealed.
- **A11 Closed evidence** (added) is needed because "intrinsic validity" is otherwise ambiguous: tier qualification and purchases depend on facts outside any chain.
- **A12 Single attribution** (added) is what lets one member take part in two aggregators' agreements without conflict: a purchase is attested on exactly one chain.
- **A13 Resolved precedence** (added) turns the brief's requirement that exceptions be first-class into a validity rule. An ambiguous agreement is rejected when it is proposed, not discovered in a dispute.
