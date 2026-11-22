# Universal Paper

A first-order language for agreements between group purchasing organizations, suppliers, and members.

Universal Paper is a vocabulary, a grammar, and a set of validity rules. It is not an application. Anyone can verify an agreement written in it, offline, from the specification alone. The code here is a reference implementation of the language, never the language itself.

**Status:** `UP/0.1-draft`. Working draft, not yet reviewed by counsel. Until 1.0, changes to the spec may change what is valid and the hashes of Term definitions. Open questions are listed in [DESIGN_NOTES.md](DESIGN_NOTES.md#6-open-questions-for-the-steward). The pre-release audit is in [AUDIT.md](AUDIT.md).

| Path | What it is |
|---|---|
| [spec/](spec/00-overview.md) | The language specification (start here) |
| [DESIGN_NOTES.md](DESIGN_NOTES.md) | What was cut, merged, or added, and why |
| [schema/](schema/) | JSON Schemas for every primitive and for trace files |
| [src/universal_paper/](src/universal_paper/) | Reference interpreter (library and CLI) |
| [examples/](examples/) | Worked examples as full chains of signed events, plus traces |
| [explorer/index.html](explorer/index.html) | Universal Paper Explorer: scroll story, live proving ground, Playground, and trace replay (built from `explorer/src/`) |
| [explorer/src/](explorer/src/) | The JavaScript second engine (`up-crypto.js`, `up-engine.js`), the proving ground (`up-lab.js`), and the page |
| [tests/](tests/) | Tests for every axiom, transition rule, clause form, and Term, plus cross-engine differential and fuzz tests |
| [AUDIT.md](AUDIT.md) | Pre-release audit: findings, fixes, and what remains open |

## Quick start

Requires Python 3.11+ and the `cryptography` package.

```sh
pip install -e '.[test]'          # or: pip install -e . && export PYTHONPATH=src
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

Serve the repository and open the Explorer, for example `python3 -m http.server` then `http://localhost:8000/explorer/index.html`. It has four parts:

- **Story**: a scroll-through of one clause becoming data, a fingerprint, a flipped fingerprint, and a caught edit, all computed live.
- **Proving ground**: generates random agreements and histories from seeds, attacks copies of them, and checks eight invariants against independent arithmetic, until the page is closed. Any failing seed is kept and can be replayed.
- **Playground**: pick parties, add Terms, set values, and watch the cover sheet, the full contract, and the fingerprint update. Sign, then edit, and the signatures stop verifying.
- **Replay**: plays recorded traces from `examples/traces/` exactly as the Python interpreter wrote them. Live runs from the proving ground can be replayed too and are marked live.

Everything live runs on a second, independent engine in JavaScript (`explorer/src/`). Before it is used, `tests/test_js_conformance.py` requires it to reproduce every example trace, rendering, and simulation byte for byte, and to pass every invariant on 60 fixed seeds. Rebuild the page after editing `explorer/src/` with `python3 tools/build_explorer.py`.

## How it is tested

`python -m pytest` runs about 170 tests in a few minutes. Node.js 20 or later is needed for the JavaScript parts, which are skipped without it. CI runs everything on Python 3.11 to 3.13.

- **Rules.** Every axiom (A1 to A13), every transition rule, and every clause form has tests that build small hypothetical agreements and try to break them.
- **Every Term.** All sixteen Terms are executed in a valid agreement, every parameter is checked against its declared type, and every claim type is attested, acknowledged, and attempted with ill-typed data.
- **Two engines, one answer.** The JavaScript engine must reproduce every Python trace, render, and simulation byte for byte, including a trace for every claim type of every Term. Differential tests run both engines on tens of thousands of seeded random inputs (canonical JSON, hashes, Ed25519 edge cases, times, periods, exact decimals, type checks) and require identical results, including identical rejections.
- **Published vectors.** Ed25519 against RFC 8032, SHA-256 and SHA-512 against known digests, and a check that the small-order key table is exactly the curve's torsion points.
- **Hostile input.** Hypothesis mutates signed example events and feeds arbitrary JSON to the evaluator: altered events are always rejected, nothing crashes or hangs, and derived values stay computable. `HYPOTHESIS_PROFILE=deep` runs a longer search.
- **Reproducibility.** Rebuilding the Term library, examples, traces, and Explorer must produce byte-identical files.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full list and how to add tests.

## Contributing and security

Contributions to the specification and the code are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Please report vulnerabilities privately, as described in [SECURITY.md](SECURITY.md). Changes are recorded in [CHANGELOG.md](CHANGELOG.md).

## Licenses

- Specification (`spec/`): [CC BY 4.0](spec/LICENSE)
- Code: [Apache-2.0](LICENSE)
