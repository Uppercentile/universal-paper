# Agreements as query surfaces

> Research is not part of the Universal Paper language. It may grow, change, or be withdrawn. Agreements do not depend on it.

Research note 001 · Status: exploring · Published November 27, 2026 · No change to the language

HTML: https://universalpaper.org/research/query-surfaces/
Record (JSON): https://universalpaper.org/research/query-surfaces/entry.json
Summary (JSON): https://universalpaper.org/research/query-surfaces/summary.json
Example manifest (JSON, simulated): https://universalpaper.org/research/query-test-vectors/manifest.json

To learn what an agreement says about you today, you ask whoever holds it and trust the reply. This note tests another arrangement: the agreement answers for itself, and anyone can check the answer.

In brief:

- **The idea.** An agreement names the questions it will answer, and anyone holding it can compute the answer.
- **The proof.** An answer is a trace with a fingerprint. Two parties who get the same fingerprint have the same answer.
- **The cost.** Nothing is added to the language. The questions use engine calls that already exist.
- **The status.** An idea with one simulated example. None of it is built into a product.
- **The parts.** One experiment, one set of files to reuse, and six open questions, each on its own page.

Parts of this note:

- Experiment 002, Three traces, recomputed: https://universalpaper.org/research/three-traces-recomputed.md
- Reusable 003, A query manifest and three traces: https://universalpaper.org/research/query-test-vectors.md
- Questions 004 to 009, listed in section 7

Kind: Note. Topics: Queries and discovery, Fingerprints and state, Mandates and agents. Built on: `simulate_eligibility`, `derive_state`, `simulate_amendment`, `UP:Admin-Fee`, `A9`.

## 1. The idea

The signed agreement is the interface. A party names the questions the agreement will answer. Anyone with the bytes, or with the fingerprint plus the slice of values disclosed to them, runs an engine and gets a **trace**: the inputs, the state fingerprint and the verdict. A second engine on the other side recomputes the same trace.

1. A party names the questions, in a short, optional file beside the agreement.
2. Anyone with the bytes runs an engine: their own copy, on their own machine.
3. The engine returns a trace: inputs, state fingerprint, verdict.
4. The other side recomputes it. Equal fingerprints, same answer.

If the two fingerprints match, the answer is the same, because the bytes are the same. No account, no vendor API and no shared database sits between the two sides.

## 2. What it adds to the language

Nothing. No Term, no Event kind and no required field.

The file that names the questions is called a **manifest**. It is optional. It sits beside the agreement, it is fingerprinted with the rule the language already uses, and it can only name engine calls that already exist.

| Question | Existing engine call | What the call reads |
|---|---|---|
| Is this member covered? | `simulate_eligibility` | The participation, its term, and the agreement it sits under |
| What fee is owed? | `derive_state` (the fee derivation) | The obligations of the UP:Admin-Fee clause |
| Would this change be accepted? | `simulate_amendment` | The agent's Mandate and axiom A9, bounded delegation |

An agreement with no manifest is exactly as valid as one with a manifest, and a manifest cannot change what an agreement means. Delete every manifest and every agreement still computes the same.

## 3. The manifest

The example was derived from the generative example bundle in the repository (`examples/generative/bundle.json`, hypothetical parties, CC0). It names three questions about one agreement, Master X. It is simulated, and no party signed it.

1. Is this member covered by this agreement at this time? Runs `simulate_eligibility`. You supply the member and the time.
2. What administrative fee is owed, and has it been paid? Runs `derive_state` and reads the fee clause. You supply the time.
3. Would this fee rate be accepted if the aggregator's agent proposed it? Runs `simulate_amendment`. You supply the rate and the time.

The manifest file, with the three traces, is Reusable 003: https://universalpaper.org/research/query-test-vectors/manifest.json

- `agreement`: which agreement the questions are about, by its ChainId and by the fingerprint of the agreement in force.
- `named_by`: the party naming the questions. If a party signed a manifest, it would be the same Ed25519 signature the language uses everywhere else.
- `call`: the existing engine call that answers the question. A manifest cannot define a new one.
- `fixed`, `open`: the arguments the manifest pins, and the ones the asker supplies, such as the member and the time.
- `reads`: for a call that returns a whole state, the part that answers the question.

Manifest fingerprint: `{{MANIFEST_FP}}`

The rule is canonical JSON (RFC 8785), then SHA-256, as in section 1 of the domain. The hosted engine's `hash_object` and a separate script written for this note returned the same value.

## 4. The trace

An answer is a trace with three parts.

- **Inputs.** Every argument the call was given, including the time. Agreements are named by ChainId, never by their position in someone's file.
- **State.** The state fingerprint of each agreement the answer read. It pins the exact history the answer rests on.
- **Verdict.** What the engine returned: eligible or not, the fee and its status, accepted or rejected and by which rule.

The trace has a fingerprint of its own, computed the same way.

| Question, at 2027-03-01T00:00:00Z | Call | Verdict | Trace fingerprint |
|---|---|---|---|
| Is Hypothetical Rural Hospital covered by Master X? | `simulate_eligibility` | Eligible. An active participant on tier B. | `{{T0}}` |
| What administrative fee is owed under Master X, and has it been paid? | `derive_state`, obligations of clause `fee` | January 2027: $21.89 (2.5% of $875.50 in reported sales), due March 3, paid. February 2027: due March 31, open, no sales reported yet. | `{{T1}}` |
| Would a fee rate of 3.5% be accepted if the aggregator's agent proposed it under its Mandate? | `simulate_amendment` | Rejected by rule A9, bounded delegation. The Mandate allows at most 3%. A rate of 3% is accepted. | `{{T2}}` |

How these were checked, and what was not checked, is Experiment 002: https://universalpaper.org/research/three-traces-recomputed.md

The state fingerprint is not new either. Every event already carries one as `prev`, the fingerprint of the state it builds on, and `derive_state` returns it as `state_hash`. If two parties name the same state fingerprint, they hold the same history, whatever else differs in their files.

## 5. Recompute it yourself

**The MCP server is a convenience, not the source.** It runs the reference engine for you, which is handy inside an assistant. The answer comes from the bytes. A local engine must be able to recompute every trace. An answer that only one server can produce is a claim, and this idea has no use for it.

The commands for a local server and for the reference interpreter are in Experiment 002.

For this example, the state fingerprint of Master X is `{{STATE_X}}`. The hosted server returned this value on November 27, 2026. The trace file in the repository (`examples/traces/generative.trace.json`), written by the reference interpreter, carries the same value for the same history.

### With only a disclosed slice

Some values in an agreement can be sealed. Every fingerprint covers the sealed form, so a party who sees every value and a party who sees none compute the same state fingerprint. A party who holds the fingerprint plus the values disclosed to them gets a full verdict for any question those values answer. For the rest, the engine says `sealed` instead of guessing.

## 6. Where this could go

The third question is a small version of something larger. It lets an outside party ask, before offering anything, whether a change would be accepted.

The hope is a future app or layer in which an agreement, and possibly a party's profile, states to outside parties: this is what I have accepted, and this is what I will keep accepting, on these conditions, if you want to make an offer. An agent reads those acceptance states and acts on them. It makes the offer that will pass, or it skips the round trip.

None of that is built. If it is built, it belongs in an app or a layer above the language, not in the language.

## 7. What we are not sure about

Six questions are open. Each has its own page, with what is known so far and what would settle it.

{{QUESTIONS_MD}}

If you have a view on any of these, open an issue: https://github.com/Uppercentile/universal-paper/issues

## 8. For agents and tools

To answer a named question:

1. Fetch the manifest and check its fingerprint.
2. Load the bundle and run `validate_bundle`. It names any rejected events. They are skipped, and they leave the state fingerprint unchanged.
3. Run the call the question names, with its fixed arguments and your own open ones.
4. Build the trace: inputs, the state fingerprint of each agreement read, and the verdict.
5. Fingerprint the trace and compare it with the other side's.

Research note by Uppercentile, licensed under CC BY 4.0. Example data is CC0 1.0.
