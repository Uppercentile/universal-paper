# Universal Paper

A first-order language for agreements between group purchasing organizations, suppliers, and members.

Universal Paper is a vocabulary, a grammar, and a set of validity rules. It is not an application. Anyone can verify an agreement written in it, offline, from the specification alone. The code here is a reference implementation of the language, never the language itself.

**Status:** `UP/0.1-draft`. Working draft. Open questions are listed in [DESIGN_NOTES.md](DESIGN_NOTES.md#6-open-questions-for-the-steward).

| Path | What it is |
|---|---|
| [spec/](spec/00-overview.md) | The language specification (start here) |
| [DESIGN_NOTES.md](DESIGN_NOTES.md) | What was cut, merged, or added, and why |
| [schema/](schema/) | JSON Schemas for every primitive and for trace files |
| [src/universal_paper/](src/universal_paper/) | Reference interpreter (library and CLI) |
| [examples/](examples/) | Worked examples as full chains of signed events, plus traces |
| [explorer/index.html](explorer/index.html) | Universal Paper Explorer, a visual player for trace files |
| [tests/](tests/) | Tests for every axiom, transition rule, clause form, and determinism |

## Quick start

Requires Python 3.11+ and the `cryptography` package.

```sh
pip install -e '.[test]'          # or: export PYTHONPATH=src
up validate examples/conventional/bundle.json
up derive   examples/conventional/bundle.json --at 2027-04-30T00:00:00Z
up render   examples/confidential/bundle.json --chain 0 --hashes-only
up simulate examples/conventional/bundle.json my-hypothetical-events.json
up trace    examples/conventional/bundle.json -o conventional.trace.json
up hash     some-object.json
python -m pytest
```

| Command | Does |
|---|---|
| `validate` | Checks every agreement and every event in a bundle against the axioms. Exit code 2 if any event is rejected. |
| `apply` | Applies one event to its chain's current state and prints the new state, or the rule that rejected it. |
| `derive` | Reports each agreement's status, tiers, contract prices, and obligations at a time. |
| `simulate` | Runs hypothetical events forward. Signatures are not required, but Mandate limits still apply. |
| `render` | Prints the human-readable agreement text, fixed by the agreement's hash. |
| `trace` | Writes a trace file: every event, every check, and each evaluator's state hash. |

## Examples

All parties, identifiers, prices, rates, quantities, and dates in the examples are **hypothetical**.

- **Conventional**: an aggregator–supplier agreement with three tiers and an admin fee, two members joining through participation and tier attestation, three months of sales reports, fee payments, one tier change, and a fee disclosure.
- **Generative**: an aggregator with no staff, run entirely by an agent under a Mandate, alongside a conventional aggregator. One hospital, acting through its own agent, participates in both at once without conflict. Two out-of-bounds agent actions are rejected under A9.
- **Overlay**: a 2024 contract described in Universal Paper in 2027, identified by its document hash, without renegotiation.
- **Confidential**: the conventional story with every price, rate, quantity, and amount sealed. An evaluator with no disclosures reaches the same verdicts and state hashes.

`python3 examples/build_examples.py` rebuilds every bundle and trace. Output is byte-identical across runs. Example keys and salts are derived from fixed seeds so the examples are reproducible; real keys and salts must be random.

## Explorer

Serve the repository and open the Explorer, for example `python3 -m http.server` then `http://localhost:8000/explorer/index.html`. Opened directly from disk, it asks you to pick a trace file from `examples/traces/` instead. It computes nothing itself; it only plays back what the interpreter wrote.

## Licenses

- Specification (`spec/`): [CC BY 4.0](spec/LICENSE)
- Code: [Apache-2.0](LICENSE)
