# 02 — Predicates and functions

Predicates are true or false. Functions resolve to values. Each is either **primitive** (defined directly against the encoding and the chain) or **defined** (an abbreviation for a formula over primitives). Defined symbols add no expressive power. They exist for readability and could be deleted without loss.

Notation: `A` an agreement chain (by ChainId), `S` a State, `E` an Event, `p` a Party (public key), `r` a Role, `t` a Time, `c` a clause name, `C` a Commitment. `chain(A, t)` is the prefix of A's chain whose Events have `at ≤ t`.

All predicates and functions take the evaluation time explicitly. There is no implicit "now".

## 1. Functions (primitive)

| Function | Result | Definition |
|---|---|---|
| `hash(o)` | Hash | [01-domain §1.2](01-domain.md#12-content-hash) |
| `apply(S, E)` | State or ⊥ | The transition function. Returns the next State, or ⊥ if `E` is not a valid transition from `S`. [04-inference §1](04-inference.md#1-the-transition-function) |
| `state(A, t)` | State | Fold of `apply` over `chain(A, t)`, from the empty state. ⊥ if any step is ⊥. |
| `agreement(S)` | Agreement | The Agreement whose hash is `S.agreement` (looked up in the Bundle). |
| `obligations(S, t)` | Set of Commitment | Every Commitment that the Duty clauses of `agreement(S)` produce at time t. [04-inference §3.5](04-inference.md#35-duty) |
| `selection(A, c, p, t)` | option name or ⊥ | The option of Selection clause `c` that applies to party `p` at t. [04-inference §3.3](04-inference.md#33-selection) |
| `value(A, c, item, o, t)` | Amount or ⊥ | The value that Valuation clause `c` yields for `item` under option `o` at t. [04-inference §3.4](04-inference.md#34-valuation) |

## 2. Predicates (primitive)

| Predicate | True iff |
|---|---|
| `SignedBy(o, p)` | `o.sigs` contains a valid signature by `p` over `hash(o)`. |
| `Covers(M, E)` | Mandate M covers an agent's signature on Event E ([01-domain §10](01-domain.md#10-mandate), coverage rules 1–5). |
| `Opens(D, σ)` | Disclosure D is valid for Seal σ: `seal(D.value, D.salt) = σ` ([01-domain §3.2](01-domain.md#32-disclosure)). |
| `HasRole(p, r, A, t)` | `agreement(state(A, t)).parties` contains `{role: r, party.key: p}`. |
| `Valid(Ag)` | Agreement `Ag` satisfies the structural axioms A1, A6, and A13 ([03-axioms](03-axioms.md)): it is well formed, uses one spec version, every Clause pins a known Term definition and binds every declared parameter, only sealable values are sealed, and every conflict between Clauses is resolved by declared precedence or specificity. |
| `ValidTransition(S, E, S′)` | `apply(S, E) = S′` and `S′ ≠ ⊥`. |
| `Executed(A, t)` | `state(A, t).status = executed`. |
| `Discharged(C, t)` | Some Event in `chain(A, t)` satisfies Commitment C's discharge condition ([04-inference §3.5](04-inference.md#35-duty)). |

## 3. Predicates and functions (defined)

These are abbreviations. Each line is the whole definition.

| Symbol | Definition |
|---|---|
| `SpeaksFor(E, p)` | `SignedBy(E, p) ∨ ∃ agent key k, Mandate M in the Bundle: SignedBy(E, k) ∧ M.principal = p ∧ M.agent = k ∧ Covers(M, E)` |
| `reveal(x, B)` | x itself if x is not a Seal; `D.value` if Bundle B holds a D with `Opens(D, x)`; otherwise the marker `sealed`. Every computed function applies `reveal` to its inputs, and any arithmetic on `sealed` yields `sealed`. |
| `window(A, t)` | The `[start, end)` interval given by the Window clauses of `agreement(state(A, t))`, with `end` replaced by `state(A,t).ends_at` when that is earlier. [04-inference §3.1](04-inference.md#31-window) |
| `Active(A, t)` | `Executed(A, t) ∧ t ∈ window(A, t) ∧ (∀ A′ ∈ parents(A): Active(A′, t))` |
| `parents(A)` | The `parent` of the Link clause of `agreement(state(A, t))`, if any. |
| `Attested(p, k, t)` in A | `∃ E ∈ chain(A, t): E.kind = attest ∧ E.by = p ∧ E.body.claim.type = k` |
| `Acknowledged(E, p, t)` in A | `SpeaksFor(E, p) ∨ ∃ E′ ∈ chain(A, t): E′.kind = accept ∧ E′.by = p ∧ E′.body.target = hash(E)` |
| `Eligible(m, A, t)` | `∃ P: A ∈ parents(P) ∧ HasRole(m, member, P, t) ∧ Active(P, t)` |
| `InTier(m, A, T, t)` | `selection(P, c, m, t) = T` for the participation chain P of m under A and the tier Selection clause c. This is the first-pass predicate expressed through the generic Selection form. |
| `price(item, P, t)` | `value(A, v, item, selection(P, s, m, t), t)`, where A is P's parent, v the Valuation clause in A, s the Selection clause in P, and m P's member. |
| `Compliant(p, A, t)` | `∀ C ∈ obligations(state(A, t), t): C.obligor.key = p ⇒ C.status ≠ overdue` |

## 4. Changes from the first-pass list

| First pass | Now | Why |
|---|---|---|
| `HasRole(party, role)` | `HasRole(p, r, A, t)` | A role is held within an Agreement, and can change on amendment. Without the agreement argument the predicate is ambiguous. |
| `Valid(agreement)` | kept | Structural validity of the content. Validity of the *chain* is `state(A, t) ≠ ⊥`. |
| `Active(agreement, t)` | defined | Follows from execution, window, termination, and parents. |
| `Eligible(member, agreement, t)` | defined | Follows from an active participation chain. |
| `Attested(party, claim, t)` | defined | An attestation is just an `attest` Event. |
| `InTier(...)` | defined via `selection` | Tier is no longer a primitive. Selection is the use-case-blind form behind it. |
| `Compliant(party, commitment, period)` | defined via `Discharged` | Compliance is "no overdue Commitments". The per-period version is a filter. |
| `ValidTransition(state, event, next)` | kept | |
| `state`, `obligations`, `hash` | kept | |
| `tier(member, agreement, t)` | `selection(A, c, p, t)` | Generic. |
| `price(item, agreement, tier, t)` | defined via `value` | Generic Valuation. |
| `fee(purchaseEvent)` | removed | Fees are Commitments produced by a Duty clause, so `obligations` already returns them. A per-purchase fee is a Duty whose period is one claim. |
| — | `apply(S, E)` added | The transition function is the heart of the language and deserved a name. |
| — | `Discharged(C, t)` added | Needed to say when an obligation is met without trusting either party's records. |
| — | `Covers`, `SpeaksFor` added | Bounded delegation (A9). Every place the first pass said "signed by p" now means `SpeaksFor(E, p)`. |
| — | `Opens`, `reveal` added | Confidentiality (A10). Validity predicates never call `reveal`. Only computed functions (`value`, `obligations` amounts, discharge comparisons) do. |
