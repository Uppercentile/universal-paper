# 04 — Inference

This file defines how new truths follow from old ones: the transition function, time arithmetic, the six **clause forms** that every Term is built from, exceptions and precedence, decimal arithmetic, rendering, and simulation.

## 1. The transition function

`apply(S, E) → S′ | ⊥`

For the genesis Event, `S` is the empty state `∅`. For every Event, `apply` performs these checks in order. The first failure returns ⊥.

1. **Envelope.** `E.type = "Event"`, `E.spec` equals the chain's spec version, `E.kind ∈ {propose, accept, attest}`.
2. **Linkage (A3).** Genesis: `S = ∅`, `E.kind = propose`, and `chain`, `prev`, `supersedes` are absent. Otherwise `E.chain = S.chain` and `E.prev = hash(S)`.
3. **Time (A5).** `E.at ≥ S.at`.
4. **Signatures (A9).** `SpeaksFor(E, E.by)`. Every entry in `E.sigs` verifies. Every signature speaks for some Party of the current Agreement, of the Agreement in `S.pending`, or of the Agreement in `E` itself, either directly or through a covering Mandate. An unknown or uncovered signer makes the Event invalid; it is not ignored.
5. **Kind rule.** The rule for `E.kind` in [05-lifecycle §2](05-lifecycle.md#2-transition-rules).
6. **Clause effects.** For `attest`, and for `accept` of an attestation, the clause named by the claim applies its form's effect (§3) to `S.facts`.

`S′` copies S, increments `height`, sets `last = hash(E)` and `at = E.at`, and applies the changes from steps 5 and 6.

**Every check above reads only structural fields** ([01-domain §3.3](01-domain.md#33-what-may-be-sealed)). None calls `reveal`. That is what makes A10 hold: an evaluator with no Disclosures computes the same `apply` results and State hashes. (Mandate Bounds read values, but only values that coverage rule 6 requires to be unsealed.)

`state(A, t)` folds `apply` over the Events of A with `at ≤ t`, in chain order.

## 2. Time and period arithmetic

All Times are UTC. Adding a Period to a Time:

- `day × n`: add `n × 86 400` seconds.
- `month × n`: add n to the calendar month of the date, keeping the time of day. If the day of month does not exist in the target month, use the last day of that month.
- `quarter × n` = `month × 3n`. `year × n` = `month × 12n`.

A **periodic sequence** anchored at time `a` with Period `P` has boundaries `bₖ = a + (k × P)` for k = 0, 1, 2, …, each computed directly from `a` (never by repeated addition, which would drift through month-end clamping). Period k is the half-open interval `[bₖ, bₖ₊₁)`.

## 3. Clause forms

Every Term's machine definition is a binding of zero or more of these six forms to its parameters. (A Term with no forms, such as governing law, has legal meaning only.) The core interpreter implements the forms, not individual Terms. A new Term that uses only these forms needs no new code, only a new definition.

| Form | Does one thing |
|---|---|
| **Window** | Says when an Agreement is in force, including renewal. |
| **Exit** | Lets a role end the Agreement unilaterally by notice. |
| **Selection** | Records which of several named options applies to a party, based on acknowledged attestations. |
| **Valuation** | Says what an Item is worth under the Agreement. |
| **Duty** | Produces Commitments: who must do what, by when, and for how much, and what discharges them. |
| **Link** | Makes this Agreement depend on a parent Agreement's chain. |

Each form is described by its fields. In a TermDefinition, a field holds either a literal structural value or a reference `{"param": "<name>"}` to a parameter. Fields that carry economic values (amounts, rates, periods, counts) MUST be parameter references (A6).

### 3.1 Window

| Field | Type | Meaning |
|---|---|---|
| `start` | Time | First instant in force. |
| `end` | Time | First instant no longer in force, before any renewal. |
| `renew`? | `{ period: Period, max?: int, optout_roles: [Role], optout_notice: Period }` | Automatic renewal. |

An Agreement MUST contain at most one Window clause. Without one, its window is `[executed_at, ∞)`.

**End at time t.** Let `e₀ = end`. While `eₖ ≤ t`, renewal is defined, fewer than `max` renewals have occurred, and no party holding an `optout_roles` role has attested the claim `<term>/optout` on this chain with `at ≤ eₖ − optout_notice`: set `eₖ₊₁ = end + (k + 1) × period`, computed directly from `end` as in §2 (so a term ending on 31 January renews to 28 February and then 31 March, never 28 March). The window end is the last `eₖ`, or `S.ends_at` if that is earlier.

### 3.2 Exit

| Field | Type | Meaning |
|---|---|---|
| `holders` | [Role] | Who may exit. |
| `notice` | Period | Time from the notice to the end. |
| `requires`? | `{ claim: ClaimType, age: Period, unless: ClaimType }` | A precondition: a prior attestation of `claim` by the same holder, at least `age` old, with no later `unless` attestation acknowledged by that holder. (This expresses "termination for cause after an uncured breach notice".) |

**Effect.** On an `attest` of `<term>/notice` by a holder at time `a`, if `requires` is met at `a`: set `S.ends_at = min(S.ends_at, a + notice)`. Otherwise ⊥.

### 3.3 Selection

| Field | Type | Meaning |
|---|---|---|
| `options` | [{ name: string, conditions: string }] or `{ from: { link?: true, clause: string } }` | The named options, or a reference to the `options` of another clause, on this Agreement or (with `link`) on the parent reached through this Agreement's Link clause. `conditions` is descriptive text, rendered but **not** computed (A11). |
| `subject` | Role | Whose selection this records. |
| `ack` | [Role] | Roles whose acknowledgment makes a selection effective. May be empty. |
| `effective` | `"on-ack"` or `{ "next": Period, "anchor": "window-start" }` | When an acknowledged selection takes effect. |
| `initial`? | option name | The option in effect before any selection. Supplied by the parties, never by the Term. |

**Effect.** An `attest` of `<term>/selects` with data `{ option }` by a party holding `subject` records a pending selection. When every `ack` role has acknowledged it (co-signature or `accept`), it is recorded in `S.facts` as `(subject key, option, effective time)`. The effective time is the time of the last acknowledgment, or the next periodic boundary after it.

`selection(A, c, p, t)` is the option of the latest recorded selection for p with effective time ≤ t, else `initial`, else ⊥.

### 3.4 Valuation

| Field | Type | Meaning |
|---|---|---|
| `items`? | [Identifier] | The Items in scope. Required for a reference source. For a table, the Items are the table's rows. |
| `during`? | `{ start: Time, end: Time }` | Limits the clause to purchases in this interval. Used by time-bounded exceptions (§4). |
| `source` | `{ "table": [{ item, by: { <option>: Amount } }], "options": [{ name, conditions }] }` or `{ "reference": { claim: ClaimType, role: Role, factor: Decimal, rounding: Rounding } }` | Either a table with one column per named option, or a reference price list attested by a role, multiplied by a factor. |

`value(A, c, item, o, t)`, where `o` is an option name (ignored for a reference source):
- **Table.** The Amount in the row for `item` under column `o`. In practice `o = selection(P, s, m, t)`, read from the participation chain P (see `price` in 02).
- **Reference.** Take the latest acknowledged-or-attested price list claim by `role` with `data.effective ≤ t`, find `item`, multiply its Amount by `factor`, round per `rounding` (§5).

If the item is not in scope, ⊥. If a needed value is sealed and not disclosed to this evaluator, the result is `sealed`.

### 3.5 Duty

| Field | Type | Meaning |
|---|---|---|
| `duty` | string | A label from the Term (e.g. `"report"`, `"pay"`, `"disclose"`). The core gives it no meaning beyond the label. |
| `obligor`, `obligee` | Role | Who owes, and to whom. |
| `trigger` | `{ "every": Period, "anchor": "window-start" }` or `{ "on": ClaimType, "by": [Role], "limit"?: { count: int, per: Period } }` | Periodic, or caused by an attestation (e.g. an audit request). |
| `due` | Period | Time after the period end (or after the triggering claim) by which the duty must be discharged. |
| `discharge` | `{ claim: ClaimType, ack?: [Role] }` | The attestation by the obligor, with data `{ period }`, that discharges it, and any required acknowledgments. |
| `amount`? | `{ rate: Rate, base: { claim: ClaimType, clause: string, field: string }, rounding: Rounding }` | For a payment: `round(rate × Σ base.field)` over the base claims, attested under the named clause, whose `data.period` equals this period. |

**Commitments at time t.** For a periodic trigger: one Commitment for each period whose end is ≤ t, whose start is inside the window, and whose end is after `executed_at`. (The last condition means an Agreement signed after its start date still owes the first period's duty, and an [overlay](06-terms/UP-Overlay.md) of a years-old contract does not invent overdue duties for periods before anyone signed it.) For a claim trigger: one Commitment for each triggering claim within `limit`. A triggering claim over the limit is ⊥.

**Status.** `discharged` if a discharge claim for that period exists (with its acknowledgments, and for an `amount`, a `data.amount` at least equal in the same currency). Otherwise `overdue` if `t ≥ due`, else `open`. If the amount comparison needs a sealed value this evaluator cannot open, the amount and status are `sealed`, except that a missing discharge claim is `overdue` or `open` for everyone.

### 3.6 Link

| Field | Type | Meaning |
|---|---|---|
| `parent` | ChainId | The parent Agreement's chain. |
| `bind` | [Role] | Roles that must be held, in this Agreement, by the same Parties that hold them in the parent. Fixed by the Term, not a parameter, because it is structural. |

**Effect.** At genesis and on every execution, for each role r in `bind`: the parties holding r here equal the parties holding r in the parent's current Agreement. Otherwise ⊥. Because those parties are required signers here (A2), the parent's parties consent to each child individually. Clauses here may read the parent's clauses (`link: true`). `Active` here requires `Active` of the parent (02). An Agreement has at most one Link clause in v0.

## 4. Exceptions and precedence

Contracts say "X, except Y, notwithstanding Z." Following default logic (as in Catala), a Clause states a general rule and other Clauses may declare exceptions to it. The language decides every conflict the same way for every evaluator.

### 4.1 When two Clauses conflict

Two Clauses conflict when they are built on the same form and would answer the same question differently.

| Form | Question (conflict key) | Overlap test |
|---|---|---|
| Valuation | the value of item i at time t | both cover i, and their `during` intervals (default: unbounded) intersect |
| Selection | the option for subject p | same `subject` and same options source |
| Duty | the Commitment for (duty, obligor, obligee) | same `duty` label, `obligor`, and `obligee` |
| Window | the window | (at most one Window Clause, A1, so never) |
| Exit, Link | — | never: Exit rights accumulate, and there is at most one Link |

### 4.2 Resolution order

For each conflicting pair (X, Y), on the overlap only:

1. **Explicit precedence.** If X lists Y in `over` (directly or through a chain of `over`), X governs.
2. **Specificity.** Otherwise, if X is strictly more specific than Y, X governs. X is strictly more specific than Y when X's scope is a proper subset of Y's: for Valuation, X's item set ⊆ Y's and X's `during` ⊆ Y's, with at least one proper; for the other forms, never (they have no scope to compare, so they need `over`).
3. **Otherwise the Agreement is invalid** (A13). Clause order is never a tiebreaker.

`over` must be acyclic. The governing Clause replaces the other only on the overlap. Outside it, both apply as written.

### 4.3 Example

A Tiers clause prices every Item in the agreement. A second Valuation clause prices two of those Items at a temporary promotional price `during` one quarter. The second is strictly more specific (fewer items, shorter time), so it governs those two Items in that quarter without any `over`, and the Tiers clause governs everything else. If the promotional clause covered **all** Items for all time, neither would be more specific, and the Agreement would be invalid unless one names the other in `over`.

## 5. Expiry and other time-driven truths

Nothing happens at expiry. No Event is needed or allowed. `Active(A, t)` becomes false at the window end because `window(A, t)` is computed from t. The same applies to proposal expiry (status `lapsed`) and to Commitments becoming overdue. This keeps every time-driven truth a function of (chain, t), which is what makes simulation and hand-checking possible.

## 6. Arithmetic

- All arithmetic on Decimals is exact. (An implementation must not use a fixed-precision context, such as a 28-digit decimal default, for any intermediate sum or product.)
- A computation rounds **only** where a form says so, using a **Rounding** parameter `{ scale: int, mode: "half-even" | "half-up" | "down" | "up" }`. There is no default rounding (A6).
- Adding Amounts of different currencies is ⊥. The core does no currency conversion.
- Any operation with a `sealed` input yields `sealed` (see `reveal` in 02).

## 7. Rendering

`render(Ag, D)` turns an Agreement into human-readable text deterministically, given a set of Disclosures D (A8). A sealed value renders as its disclosed value if D opens it, and as `[sealed sha256:…]` otherwise. The text for signature is the rendering with every Disclosure the signing parties hold.

1. A header: the label, the spec version, and `hash(Ag)`.
2. The parties: each Party's name, its Role written as "the Aggregator", "the Supplier", or "a Member", and its key.
3. Each Clause in order: the Term's title, then its `render` template with parameters interpolated, then, if the Clause has `over`, the sentence "This clause applies notwithstanding clause(s) …".
4. A signature block stating that each Party signs the Agreement identified by `hash(Ag)`.

Template syntax (v0): `{{param}}` interpolates a parameter. Formatters: `|amount` (`USD 12.50` as written), `|rate` (the Decimal × 100 with `%`, exact), `|period` (`30 days`, `1 calendar month`), `|role` (`the Supplier`; a list joins with "or"), `|time` (`1 January 2027, 00:00 UTC`), `|rounding` (`to 2 decimal places, half to even`), `|effective` (`upon acknowledgment` or `from the start of the next 1-calendar-month period after acknowledgment`), `|governs` (`the existing agreement` or `this record`). `{{#each list}}…{{/each}}` repeats over a list parameter.

Because each template is inside the hashed TermDefinition and the Agreement pins that hash, the rendered text is fixed by the same hash the parties sign. Rendering never adds commentary, and never uses "you" or "we" (neutral voice).

## 8. Simulation

Simulation is not a separate feature. It is `state` and `obligations` evaluated over a chain extended with hypothetical Events.

`simulate(Bundle, [E₁ … Eₙ], t)` applies each hypothetical Event with signature verification (step 4 of §1) replaced by "the author holds a role that the Event's rule allows". Mandate coverage is still checked for Events marked as agent-made, so simulations can test whether an agent's intended actions are within bounds. Everything else applies unchanged. The result reports, after each Event, the State, its hash, the reported status, `selection` and `value` for requested parties and Items, and `obligations`. Results are always labeled hypothetical, and a hypothetical State can never be referenced by a real Event, since its `prev` hash comes from unsigned data.

## 9. The first-pass inference rules, formalized

**R1. Purchase pricing and fee accrual.**
First pass: `Active(A) ∧ InTier(M, A, T) ∧ Purchase(M, item) ⟹ price applies and a fee obligation arises.`

Formal: let P be M's participation chain under A, with tier Selection clause `s` and pricing Valuation clause `v` in A.
- `Active(P, t) ∧ selection(P, s, M, t) = T ⟹ price(item, P, t) = value(A, v, item, t)` evaluated under column T.
- Fees arise per period, not per purchase: the Admin-Fee Duty in A yields, for each ended period k, a Commitment of the supplier to the aggregator with `amount = round(rate × Σ net_sales)` over the supplier's sales-report claims for period k. A per-purchase fee is the same Duty with a per-claim trigger.

**R2. Tier change.**
`Attested(M, UP:Tier-Selection/selects{option: T}) at a ∧ Acknowledged(that Event, supplier) at b ⟹ selection(P, s, M, t) = T for t ≥ eff(b)`, where `eff` is per the clause's `effective` field. Every acknowledging `accept` carries `prev = hash(S)`, so the supplier necessarily acknowledges against the current State.

**R3. Expiry.**
`t ≥ end(window(A, t)) ⟹ ¬Active(A, t)`, where renewal (§3.1) has already been folded into `window`. No Event is involved.
