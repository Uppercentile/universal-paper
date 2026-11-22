# 01 — Domain

The domain is the set of things that exist in Universal Paper.

| Kind | Name | Authored or derived | Section |
|---|---|---|---|
| Primitive | **Party** | authored | §4 |
| Primitive | **Role** | closed vocabulary | §5 |
| Primitive | **Term** | authored in the Term library | §6 |
| Primitive | **Agreement** | authored by parties | §7 |
| Primitive | **Event** | authored and signed by parties or their agents | §8 |
| Primitive | **State** | derived from a chain of Events | §9 |
| Primitive | **Mandate** | authored and signed by a principal Party | §10 |
| Value primitive | **Identifier** | a reference into an existing scheme | §2 |
| Value primitive | **Seal** | a salted commitment to a confidential value | §3 |
| Derived | Commitment | derived from a State at a time | §11 |
| Container | Bundle | packaging for offline verification | §12 |

Seven primitives, two value primitives, one derived object. Candidates from the first-pass draft that are no longer primitives: **Tier** became a Term built on the *Selection* clause form, **Attestation** became an Event kind, **Item** became an Identifier, and **Signature** became part of the encoding. Reasons are in [DESIGN_NOTES.md](../DESIGN_NOTES.md).

---

## 1. Encoding, canonical form, and hashes

### 1.1 Canonical JSON

Every object is a JSON object. Its **canonical form** is its serialization under RFC 8785 (JSON Canonicalization Scheme, JCS), encoded as UTF-8.

To keep canonical forms identical across languages:

- JSON numbers MAY appear only as integers in the range −(2⁵³−1) to 2⁵³−1. Every other number (prices, rates, quantities with fractions) is a **Decimal** string (§2). As in RFC 8785, a number is a value, not a spelling: `100`, `100.0` and `1e2` are the same integer and canonicalize as `100`. A number with a fractional part, NaN, or Infinity is invalid.
- Object keys are ASCII.
- Strings MUST NOT contain unpaired surrogates (I-JSON, RFC 7493, on which RFC 8785 relies).
- `null` is not used. An absent optional field is omitted.
- A JSON text with a duplicate key in one object is invalid. (The reference CLI rejects such files when it reads them.)

### 1.2 Content hash

`hash(o) = "sha256:" + lowercase-hex( SHA-256( JCS( strip(o) ) ) )`

`strip(o)` removes the top-level field `sigs`, if present. No other field is removed. Signatures therefore never change the identity of what they sign.

Every hashed object carries `"type"` and `"spec"` fields, so two objects of different types or spec versions can never share a hash.

Confidential values are always hashed in their **sealed** form (§3). The hash of an object is therefore the same for a party that sees every value and for one that sees none.

### 1.3 Keys and signatures

- A **public key** is written `"ed25519:" + lowercase-hex(32 bytes)`.
- A **signature** is an Ed25519 signature (RFC 8032) whose message is the **32 raw bytes** of the SHA-256 digest inside `hash(o)`.
- Signatures are attached in a top-level `sigs` array of `{ "key": PublicKey, "sig": "<lowercase-hex 64 bytes>", "mandate"?: Hash }`, sorted by `key`. `mandate` is present when the signer is an agent acting under a Mandate (§10).

A signature is valid iff it verifies under its key for the hash of the object it is attached to, under these **strict** rules, which every implementation applies identically:

1. The key matches `ed25519:[0-9a-f]{64}` and the signature matches `[0-9a-f]{128}` (lowercase only, no whitespace).
2. The key is canonically encoded (its y-coordinate is less than p = 2²⁵⁵ − 19) and is **not of small order**. The eight points of order dividing 8 have the y-coordinates 0, 1, p − 1, and the two values listed in `src/universal_paper/crypto.py`. A key that is one of them would let anyone produce "signatures" that verify, so it is never a valid Party or agent key, and an Agreement that lists one is invalid (A1).
3. R (the first 32 bytes of the signature) is canonically encoded (y < p), and S (the last 32 bytes, little-endian) is less than the group order L.
4. The verification equation is the cofactorless one of RFC 8032 §5.1.7: [S]B = R + [k]A.

Without these rules, two correct Ed25519 libraries can disagree about edge-case signatures, and two evaluators would then disagree about validity (A4).

---

## 2. Value types

| Type | Form | Notes |
|---|---|---|
| Hash | `"sha256:<64 lowercase hex>"` | §1.2 |
| PublicKey | `"ed25519:<64 hex>"` | §1.3 |
| Time | RFC 3339 UTC, second precision, `Z` suffix, e.g. `"2027-01-01T00:00:00Z"` | Years 0001 to 9999. A real calendar date and a time of 00:00:00 to 23:59:59. ASCII digits only. No time zones or fractional seconds |
| Decimal | String matching `-?(0\|[1-9][0-9]*)(\.[0-9]+)?`, at most 64 characters | No exponent, no leading `+`, ASCII digits only |
| Amount | `{ "value": Decimal, "currency": "<ISO 4217 code>" }` | Currency is three uppercase ASCII letters |
| Rate | Decimal, as a fraction (`"0.025"` is two and a half percent) | |
| Period | `{ "unit": "day"\|"month"\|"quarter"\|"year", "count": int }` | count from 1 to 10 000. Arithmetic in [04-inference §2](04-inference.md#2-time-and-period-arithmetic) |
| Rounding | `{ "scale": int, "mode": "half-even"\|"half-up"\|"down"\|"up" }` | scale from 0 to 18. No default ([04-inference §6](04-inference.md#6-arithmetic)) |
| int | A JSON integer from 0 to 2⁵³ − 1 | Counts such as `max_renewals` |
| string | Any JSON string | Free text. Sealable |
| Name | A non-empty string that other fields refer to | Clause names, option (tier) names. Structural, never sealed |
| **Identifier** | `{ "scheme": string, "id": string }` | See below |
| ClaimType | `"<Term id>/<name>"` | e.g. `"UP:Tier-Selection/selects"` |
| ChainId | Hash | The hash of a chain's genesis Event (§8.3) |
| **Seal** | `{ "seal": "sha256:<64 hex>" }` | §3 |

### Type expressions

Term parameters (`params.<name>.type`) and claim data fields (`claims.<type>.data.<field>`) declare their types with a small expression language, which every evaluator parses the same way:

- a type name from the table above (`Time`, `Period`, `Decimal`, `Rate`, `Amount`, `Identifier`, `Hash`, `ChainId`, `Role`, `Rounding`, `string`, `Name`, `int`);
- `[T]`, a list of T;
- `{a: T, b: U}`, an object with exactly those fields;
- `{<k>: T}`, a non-empty object whose keys are chosen by the parties (for example tier names) and whose values are T;
- `"x" | T | …`, one of several alternatives, where `"x"` is a literal string.

A value has a type only if it matches it exactly (no extra or missing fields). A Seal may stand in place of an `Amount`, `Rate`, `Decimal`, `string`, or an Identifier's `id`, and nowhere else (§3.3). A TermDefinition that uses an unrecognized type expression is invalid (A1).

### Identifier

A typed reference to a Party, location, or Item in an **existing** identifier scheme. Universal Paper never mints a competing scheme.

- `scheme` names the scheme: for example `GTIN`, `GLN`, `HIN`, `DEA`, `NPI`, `340B`, `NDC`, or `DUNS`. The list is open, because schemes exist outside the language. A scheme name is matched exactly, case-sensitively.
- `UP:Local` is reserved for something with no external identifier. Its `id` is meaningful only inside the Agreement that uses it, which must describe it.
- A Party or Item may carry several Identifiers. Two Identifiers refer to the same thing only if scheme and id are equal. The language never infers that a HIN and a GLN name the same facility.

An **Item** is just an Identifier used where an Item is expected.

---

## 3. Seal

A salted hash commitment to a confidential value. A Seal proves that a value exists and has not changed, while the value stays hidden from anyone who has not been given it.

### 3.1 Sealing

To seal value `v` (any JSON value):

1. Choose a fresh 32-byte random `salt`, written as 64 lowercase hex characters. A salt is never reused.
2. `seal(v, salt) = { "seal": "sha256:" + hex( SHA-256( JCS( { "salt": salt, "value": v } ) ) ) }`

The Seal object then appears **in place of** the value, everywhere: in the Agreement, in Event bodies, in State. Every hash and every signature covers the sealed form.

The salt is what stops a reader from guessing a low-entropy value (a price, a rate) by hashing candidates.

### 3.2 Disclosure

A **Disclosure** reveals one sealed value to whoever receives it:

```json
{ "seal": "sha256:…", "salt": "<64 hex>", "value": <the value> }
```

It is valid iff recomputing `seal(value, salt)` gives `seal`. Disclosures are never hashed into an Agreement or Event. They travel separately, to the parties who need each value. Because every field is sealed separately, each can be revealed on its own.

### 3.3 What may be sealed

Only values that are commercially sensitive and that no validity check depends on:

| May be sealed | May not be sealed (structural) |
|---|---|
| Amount, Rate, Decimal quantities, free-text strings (descriptions, bases, conditions), Identifier `id`s inside claim data and Agreement parameters | Roles, PublicKeys, Times, Periods, Roundings, ints, Hashes, ChainIds, ClaimTypes, Names (clause names, option names), Term ids, Event kinds, and every field of a Mandate's scope other than its bounds |

This split is what makes [A10](03-axioms.md) achievable: every validity check reads only structural fields. Values that depend on sealed fields (a price, a fee amount, whether a payment covered it) are **computed values**. An evaluator without the Disclosure reports them as `sealed`, and still agrees with everyone on validity and on the State hash.

### 3.4 Forward compatibility

The `"sha256:"` prefix names the commitment scheme. A later spec version may add schemes that support zero-knowledge proofs (for example, range proofs over committed amounts) under a new prefix, without changing the shape of any object.

---

## 4. Party

Any entity that can sign.

```json
{
  "key": "ed25519:…",
  "name": "Hypothetical Health Purchasing Alliance",
  "ids": [ { "scheme": "GLN", "id": "0614141000005" } ]
}
```

- A Party **is** its public key. `name` and `ids` are labels. They become binding only when every party signs an Agreement that pairs them with that key.
- A Party may be a person, an organization, or software acting for either. The language does not distinguish them. Software that acts *for* a Party with bounded authority does so through a Mandate (§10).
- One Party may hold several Roles in one Agreement.

Party is not a hashed object on its own. It appears inside an Agreement.

---

## 5. Role

The function a Party performs **within a specific Agreement**.

`Role ∈ { aggregator, supplier, member }` **[PROVISIONAL: closed set of three; see open question 4]**

| Role | Function |
|---|---|
| aggregator | Aggregates demand and contracts on behalf of members (the GPO function). |
| supplier | Provides Items. |
| member | Buys Items under an aggregator's agreement. |

A Role is held relative to an Agreement. The same Party may be a member in one Agreement and an aggregator in another. New Roles can be added only by a new spec version.

---

## 6. Term

A canonical unit of meaning with a stable ID. Terms live in the Term library ([06-terms/](06-terms/README.md)), not inside individual agreements. This is incorporation by reference: the Agreement is the cover page (parties and variables), and Terms are the standard terms it incorporates.

### 6.1 Term definition

```json
{
  "type": "TermDefinition",
  "spec": "UP/0.1-draft",
  "id": "UP:Admin-Fee",
  "title": "Administrative fee",
  "params": { "<name>": { "type": "<UP value type>", "doc": "…" } },
  "forms": [ …clause forms (04-inference §3) bound to parameters… ],
  "claims": { "<ClaimType>": { "data": {…}, "doc": "…" } },
  "render": "…rendering template (04-inference §7)…",
  "provenance": {
    "drafted_by": "…",
    "reviewed_by": [ { "segment": "aggregator" | "supplier" | "member", "reviewer": "…", "date": Time } ],
    "supersedes"?: Hash,
    "change_note"?: "…"
  }
}
```

- `id` is stable across spec versions. A changed meaning gets a new id.
- `params` declares every parameter by name and value type. **A Term definition MUST NOT declare a default value for any parameter.** There is no field for one. ([A6](03-axioms.md))
- `forms` is the machine definition, expressed only in the clause forms of [04-inference §3](04-inference.md#3-clause-forms).
- `render` is the human definition. It is part of the hashed definition, so the prose is fixed by the same hash as the machine meaning ([A8](03-axioms.md)).
- `provenance` records who drafted the definition, which segments' counsel reviewed it, and the previous version it replaces. Following `supersedes` links gives the version history. It exists so a future cross-segment drafting committee can give the library legitimacy. Provenance is part of the hash, so a review is recorded by publishing a new version of the definition.

### 6.2 Clause

A **Clause** is a Term applied with parameter values inside an Agreement. It is not a separate primitive.

```json
{ "n": "fee", "term": "UP:Admin-Fee", "def": "sha256:…", "params": { … }, "over"?: [ "<clause name>" ] }
```

- `n` is a local name, unique within the Agreement.
- `def` pins the exact Term definition by hash.
- `params` binds every declared parameter. A sealable parameter value may be a Seal.
- `over` declares this Clause an **exception** that takes precedence over the named Clauses where they conflict ([04-inference §4](04-inference.md#4-exceptions-and-precedence)).

---

## 7. Agreement

A composition of Clauses binding Parties in Roles.

```json
{
  "type": "Agreement",
  "spec": "UP/0.1-draft",
  "parties": [
    { "role": "aggregator", "party": { "key": "ed25519:…", "name": "…" } },
    { "role": "supplier",   "party": { "key": "ed25519:…", "name": "…" } }
  ],
  "clauses": [ …Clauses… ],
  "label": "optional free text"
}
```

- `parties` is sorted by `(role, key)`. Every Party listed is a **required signer**.
- An Agreement references another agreement's chain only through a Clause built on the Link form ([04-inference §3.6](04-inference.md#36-link)). There is no special "sub-agreement" construct.
- An Agreement may **describe** an existing paper contract rather than replace it, by including an [UP:Overlay](06-terms/UP-Overlay.md) clause ([property 8](00-overview.md#5-engineered-properties)).
- An unsigned Agreement is a **draft**. Drafts are just data.

---

## 8. Event

Something that happens to an Agreement: a signed, timestamped, hash-linked record.

```json
{
  "type": "Event",
  "spec": "UP/0.1-draft",
  "kind": "propose" | "accept" | "attest",
  "chain": "<ChainId>",            // omitted on the genesis event
  "prev": "<hash of prior State>", // omitted on the genesis event
  "at": "<Time>",
  "by": "<PublicKey of the Party on whose behalf the Event is made>",
  "body": { … },
  "sigs": [ … ]
}
```

### 8.1 Event kinds

There are exactly three.

| Kind | Body | Meaning |
|---|---|---|
| `propose` | `{ "agreement": Agreement, "supersedes"?: Hash, "expires"?: Time }` | Offers an Agreement, or a replacement for the current one. |
| `accept` | `{ "target": Hash }` | Signs onto a prior `propose` (forming the agreement) or a prior `attest` (acknowledging the claim). |
| `attest` | `{ "claim": { "type": ClaimType, "clause": string, "data": {…} } }` | A signed statement that something is true, or a notice. Purchases, sales reports, tier qualification, payments, and termination notices are all attestations. Sealable data fields may be Seals. |

Transition rules are in [05-lifecycle](05-lifecycle.md). Expiry is not an Event: it follows from time.

### 8.2 Signatures on Events

The Event is made on behalf of the Party `by`. It must carry a valid signature that **speaks for** `by`: either `by`'s own signature, or an agent's signature with a `mandate` reference to a Mandate from `by` that covers the Event ([A9](03-axioms.md)).

Other Parties may co-sign. A co-signature on a `propose` counts the same as a separate `accept`. A co-signature on an `attest` counts the same as an `accept` of it. Co-signatures may also be made by agents under Mandates.

### 8.3 Chains

A **chain** is the ordered sequence of Events for one Agreement.

- The first Event is a `propose` with no `chain` or `prev`. It is the **genesis**.
- `ChainId = hash(genesis event)`. The ChainId is the stable identity of the agreement across amendments.
- Every later Event carries the ChainId and the hash of the State immediately before it.

---

## 9. State

The full status of an Agreement after some prefix of its chain.

```json
{
  "type": "State",
  "spec": "UP/0.1-draft",
  "chain": "<ChainId>",
  "height": 3,
  "last": "<hash of last applied Event>",
  "at": "<Time of last applied Event>",
  "status": "proposed" | "executed",
  "agreement": "<hash of the current Agreement>",
  "executed_at"?: "<Time>",
  "ends_at"?: "<Time>",
  "pending"?: { "event": Hash, "agreement": Hash, "signed": [PublicKey…], "expires"?: Time },
  "facts": { "<clause name>": { … per clause form, see 04-inference … } }
}
```

- State is **derived**, never authored. It is a pure function of the chain ([A4](03-axioms.md)).
- `facts` holds only what clause forms need to remember: selections made, notices given, claims recorded and acknowledged. Values are stored exactly as they appear in Events, **sealed or not**. State never stores a computed number (a fee, a price). That is why an evaluator without Disclosures computes the same State hash as one with them.
- The stored `status` is only `proposed` or `executed`. The status *reported at a time t* is computed ([05-lifecycle §1](05-lifecycle.md#1-status-model)).

---

## 10. Mandate

A signed, bounded grant of authority from a Party (the **principal**) to an **agent**, which may be a person or software.

```json
{
  "type": "Mandate",
  "spec": "UP/0.1-draft",
  "principal": "ed25519:…",
  "agent": "ed25519:…",
  "not_before": Time,
  "expires": Time,
  "scope": {
    "kinds": [ "propose", "accept", "attest" ],
    "roles": [ Role… ],
    "chains"?: [ ChainId… ],
    "terms"?:  { "<Term id>": { "<param>": Bound, … }, … },
    "claims"?: { "<ClaimType>": { "<data field>": Bound, … }, … }
  },
  "sigs": [ { "key": "<principal>", "sig": "…" } ]
}
```

`Bound` is one of: `{ "any": true }`, `{ "in": [values…] }`, `{ "min"?: Decimal|Amount, "max"?: Decimal|Amount }` (an Amount bound applies only to the same currency), or `{ "max_period": Period }`. Bounds are values the principal chooses. The spec suggests none (A6).

**Coverage.** A Mandate M covers a signature on Event E iff all six rules hold:

1. M is well formed (`principal` and `agent` are valid keys under §1.3, `not_before` and `expires` are Times), M is signed by `M.principal`, and the signing key is `M.agent`.
2. `M.not_before ≤ E.at < M.expires`.
3. `E.kind ∈ M.scope.kinds`, the principal holds a Role in `M.scope.roles` in the relevant Agreement, and if `chains` is present, E's chain is listed (a genesis `propose` is covered only when `chains` is absent).
4. For `propose`, and for `accept` of a proposal: every Clause of the proposed Agreement uses a Term listed in `terms`, and **every** parameter of that Clause has a Bound in M that its value satisfies. A parameter with no Bound is not covered. Use `{ "any": true }` to allow any value.
5. For `attest`, and for `accept` of an attestation: the claim type is listed in `claims`, and every data field has a Bound that its value satisfies.

An agent's signature that is not covered is invalid. Because validity is computed, an out-of-bounds action is not "disputed": it never enters the chain.

6. **Bounded values are unsealed.** Any value that rule 4 or 5 checks against a Bound other than `{ "any": true }` appears unsealed in the Event (or in the proposed Agreement). An agent-signed Event with a sealed value under a real Bound is not covered. **[PROVISIONAL]** This keeps A10 strict, at the cost that values an agent sets within bounds are visible to whoever holds that chain. See [DESIGN_NOTES](../DESIGN_NOTES.md#3-tension-mandate-bounds-on-sealed-values).

A Mandate is not tied to one chain. It is carried in the Bundle.

---

## 11. Commitment (derived)

A conditional obligation of a Party that arises under an Agreement. Commitments are the output of `obligations(S, t)`.

```json
{
  "clause": "fee",
  "duty": "pay",
  "obligor": { "role": "supplier", "key": "ed25519:…" },
  "obligee": { "role": "aggregator", "key": "ed25519:…" },
  "period": { "start": Time, "end": Time },
  "due": Time,
  "amount"?: Amount | "sealed",
  "status": "open" | "discharged" | "overdue" | "sealed"
}
```

`sealed` appears only for an evaluator that lacks a Disclosure the computation needs.

---

## 12. Bundle

The self-contained unit for offline verification. A container, not a primitive.

```json
{
  "type": "Bundle",
  "spec": "UP/0.1-draft",
  "terms":    [ …every TermDefinition pinned by any Clause… ],
  "mandates": [ …every Mandate referenced by any signature… ],
  "chains":   [ [ …Events of chain 1… ], [ …Events of chain 2… ] ],
  "disclosures"?: [ …Disclosures this holder has received… ]
}
```

A Bundle MUST include every chain that an included chain links to. Each chain appears in `chains` once. Two entries whose first Events are identical have the same ChainId, so they are two versions of one chain (a fork, which A3 rules out): such a Bundle is invalid, and an evaluator reports it instead of choosing one. Two holders of the same chains may hold different `disclosures`. They still agree on validity and every State hash. Given a Bundle and this spec, an evaluator needs nothing else: no network, no registry, no permission.
