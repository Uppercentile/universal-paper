# Universal Paper — Overview

**Spec version:** `UP/0.1-draft` · **Status:** working draft, not stable · **License:** CC BY 4.0

> Provisional markers. Text tagged **[PROVISIONAL]** records an assumption made so drafting could continue. Each one ties to an open question in [DESIGN_NOTES.md](../DESIGN_NOTES.md#6-open-questions-for-the-steward) and may change.

## 1. What Universal Paper is

Universal Paper (UP) is a first-order language for agreements between group purchasing organizations, suppliers, and members. It is a vocabulary, a grammar, and a set of validity rules. It is not an application, a contract-management plug-in, an editor, a template library, or a business.

Tools, agents, and applications can be built on it later, by anyone. The core does not know or care what they are.

## 2. Thesis: universality in exchange for speed

Today every party contracts on "its own paper". Bespoke paper gives the strongest party leverage over the terms, and over the record itself, because whoever runs the larger system holds the master copy.

Universal Paper belongs to no party. In exchange for giving up bespoke paper, every party gets:

- **Speed.** Nothing that doesn't matter needs redlining.
- **Shared, verifiable truth** about what was agreed and what state it is in.
- **Interoperability** with any system or agent that speaks the language.

## 3. The ontological test

> If every piece of software disappeared tomorrow, would Universal Paper still exist and still work?

It must. The models are Incoterms, double-entry bookkeeping, GS1 identifiers, and the bill of lading. This specification is the language. Software is a reference implementation of it.

Concretely, a person with this document, a SHA-256 implementation, an Ed25519 verifier, and patience can check by hand whether an agreement is valid, what state it is in, and what is owed under it. Nothing in this spec may require a particular program, server, registry, or ledger.

## 4. Validity is computed, not granted

As in a consensus protocol, the validity of an agreement, and of every change to it, is a property computed from intrinsic rules. Every evaluator applies the same rules to the same data and reaches the same answer. No authority approves anything.

## 4a. Lessons from prior art

| Prior effort | What Universal Paper takes from it |
|---|---|
| Ricardian contracts | Prose and machine form bound to one hash ([A8](03-axioms.md)), plus the domain vocabulary they lacked. |
| Common Paper, Bonterms, oneNDA | Cover page plus standard terms incorporated by reference (Agreement plus Term library), CC BY 4.0, and Term provenance for a future cross-segment drafting committee. |
| Accord Project | Stay domain-specific. Six clause forms, not a general programming language. |
| ISDA Common Domain Model | Model lifecycle events, not just documents, and adopt incrementally through mapping ([07](07-mapping-guide.md)) and overlays. |
| MediLedger | Universal Paper is a language a network could speak, not a network. Confidentiality is designed in. |
| TradeLens | Credible neutrality from day one ([08-neutrality-charter](08-neutrality-charter.md)). |
| ASX CHESS replacement | Never lead with a ledger. The core is substrate-agnostic and small. |
| GS1 in healthcare | Reuse existing identifiers through multi-scheme Identifiers. Never mint a competing scheme. |
| Catala | Exceptions and precedence are first-class and deterministic ([04 §4](04-inference.md#4-exceptions-and-precedence), [A13](03-axioms.md)). |
| Agent Payments Protocol (AP2) | A Mandate primitive for bounded delegated authority ([A9](03-axioms.md)). Universal Paper is the agreement layer payment protocols can reference. |

## 5. Engineered properties

| Property | Meaning in this spec |
|---|---|
| Self-describing | An agreement, bundled with the Term definitions it pins by hash, carries its full meaning. ([01-domain §Bundle](01-domain.md#12-bundle)) |
| Content-addressed | Every Term definition, Agreement, Event, and State is identified by the SHA-256 hash of its canonical JSON. ([01-domain §1](01-domain.md#1-encoding-canonical-form-and-hashes)) |
| Self-validating | Validity is checkable offline, by anyone, without permission. ([03-axioms](03-axioms.md)) |
| Intrinsic transition rules | Each Event kind has a fixed rule saying who must sign and what must be true. ([05-lifecycle](05-lifecycle.md)) |
| Fault tolerant | The truth is the valid chain of signed Events, not any party's database. |
| Deterministic | The same chain and the same evaluation time give the same State, for every evaluator. ([A4](03-axioms.md)) |
| Confidential by construction | Prices, rosters, and volumes can be sealed field by field. Validity and every State hash can be checked from Seals alone. ([01-domain §3](01-domain.md#3-seal), [A10](03-axioms.md)) |
| Describes before it replaces | An existing agreement can be expressed as an overlay, without renegotiation. ([UP:Overlay](06-terms/UP-Overlay.md), [07-mapping-guide](07-mapping-guide.md)) |

## 6. Design principles

1. **Minimal.** As few primitives as possible. Each primitive is a permanent commitment.
2. **Orthogonal.** Each primitive does one thing.
3. **Composable.** Complex agreements are built from simple ones, never special-cased. A member's participation is itself an Agreement that references another Agreement.
4. **Use-case blind.** The core has no concept of onboarding, simulation, or agents.
5. **Value-neutral.** The language can express a price, fee, rate, threshold, or period, but defines no default for any of them and never suggests one.
6. **Role-based.** Rules refer to roles, never to specific organizations. One party may hold several roles.
7. **Human- and machine-readable.** Every construct has a canonical machine form and a deterministic human rendering. Prose is a rendering of a Term, not the Term itself.

## 7. Boundaries

### 7.1 Antitrust

Universal Paper standardizes **process, definitions, and compliance mechanics**. It never standardizes **prices or economic terms**. No Term in this specification, and no conforming Term library, may carry a default, suggested, typical, or recommended value for any price, discount, fee, rate, threshold, volume, or period. Every such value is a parameter that the parties supply. Examples in this repository use values that are explicitly hypothetical and carry no meaning beyond illustration. ([A6](03-axioms.md))

### 7.2 Legal enforceability

A Universal Paper agreement must still be a valid contract under the applicable contract law. The engineering guarantees shared, verifiable truth about *what was agreed* and *what state it is in*. It does not replace courts, and it does not decide disputes about facts in the world. Every agreement has a deterministic human-readable rendering suitable for signature ([04-inference §7](04-inference.md#7-rendering)), and the rendering is fixed by the same hash the parties sign.

### 7.3 Regulatory awareness

In U.S. healthcare, GPO administrative fees are subject to the federal anti-kickback statute's GPO safe harbor. The fee Term family ([UP:Admin-Fee](06-terms/UP-Admin-Fee.md), [UP:Fee-Disclosure](06-terms/UP-Fee-Disclosure.md)) can express the written-agreement and disclosure elements that arrangements commonly need. The spec does not encode any legal conclusion. Whether a given agreement satisfies any law is outside the language.

### 7.4 Neutrality of voice

Every Term rendering reads the same whichever party reads it. Renderings name roles ("the Supplier"), never "you" or "we", and never characterize one party's position favorably.

## 8. Document map

| File | Contents |
|---|---|
| [01-domain.md](01-domain.md) | Things that exist: encoding, Identifier, Seal, Party, Role, Term, Agreement, Event, State, Mandate, Commitment, Bundle |
| [02-predicates-functions.md](02-predicates-functions.md) | What can be asked of the domain |
| [03-axioms.md](03-axioms.md) | Consensus rules that always hold |
| [04-inference.md](04-inference.md) | How a State and an Event yield the next State; clause forms; rendering; simulation |
| [05-lifecycle.md](05-lifecycle.md) | Agreement status model and the rule for every Event kind |
| [06-terms/](06-terms/README.md) | Initial Term library |
| [07-mapping-guide.md](07-mapping-guide.md) | How rosters, eligibility files, and X12 EDI sets map onto Universal Paper |
| [08-neutrality-charter.md](08-neutrality-charter.md) | Who owns the language (no one) and how it is governed |

## 9. Versioning and governance [PROVISIONAL]

Each spec version is immutable once published. An Agreement declares exactly one spec version ([A1](03-axioms.md)). Changes are proposed through a public RFC-style process and recorded in a public changelog ([08-neutrality-charter](08-neutrality-charter.md)). The brief names Uppercentile as steward (not owner). The name the spec is published under is an open question (see DESIGN_NOTES).

Version strings take the form `UP/<major>.<minor>[-draft]`. A Term definition's hash changes whenever its text changes, so an Agreement that pins a hash is unaffected by later edits to the library.
