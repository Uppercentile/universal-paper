<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/universal-paper-mark-white-512.png">
    <img src="assets/universal-paper-mark-black-512.png" alt="Universal Paper logo" width="120">
  </picture>
</p>

# Universal Paper

A first-order language for agreements between group purchasing organizations, suppliers, and members.

Universal Paper is a vocabulary, a grammar, and a set of validity rules. It is not an application. Anyone can verify an agreement written in it, offline, from the specification alone. The code here is a reference implementation of the language, never the language itself.

**Website:** [universalpaper.org](https://universalpaper.org) · [Playground](https://universalpaper.org/playground/) · [FAQ](https://universalpaper.org/faq/)

**Status:** `UP/0.1-draft`. Working draft, not yet reviewed by counsel. Until 1.0, changes to the spec may change what is valid and the hashes of Term definitions. Open questions are listed in [DESIGN_NOTES.md](DESIGN_NOTES.md#6-open-questions-for-the-steward). The pre-release audit is in [AUDIT.md](AUDIT.md).

| Path | What it is |
|---|---|
| [spec/](spec/00-overview.md) | The language specification (start here) |
| [DESIGN_NOTES.md](DESIGN_NOTES.md) | What was cut, merged, or added, and why |
| [schema/](schema/) | JSON Schemas for every primitive and for trace files |
| [src/universal_paper/](src/universal_paper/) | Reference interpreter (library and CLI) |
| [examples/](examples/) | Worked examples as full chains of signed events, plus traces |
| [explorer/index.html](explorer/index.html) | Universal Paper Playground: an ecosystem view, the Playground (write, compare, history), and conformance (built from `explorer/src/`) |
| [explorer/src/](explorer/src/) | The JavaScript second engine (`up-crypto.js`, `up-engine.js`), the random-run lab (`up-lab.js`), the history player (`up-play.js`), and the page |
| [site/](site/) | The universalpaper.org website build (`python3 site/build_site.py`), deployed to GitHub Pages |
| [tests/](tests/) | Tests for every axiom, transition rule, clause form, and Term, plus cross-engine differential and fuzz tests |
| [AUDIT.md](AUDIT.md) | Pre-release audit: findings, fixes, and what remains open |

## Quick start

Requires Python 3.11+ and Git. From an empty terminal on macOS or Linux:

```sh
git clone https://github.com/Uppercentile/universal-paper.git
cd universal-paper
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[test]'

up validate examples/conventional/bundle.json
```

On Windows (PowerShell), activate the environment with `.venv\Scripts\Activate.ps1` instead of `source .venv/bin/activate`. The virtual environment keeps the install out of your system Python, which recent macOS and Linux releases refuse to modify ([PEP 668](https://peps.python.org/pep-0668/)).

Then try the other commands, from the same folder with the environment active:

```sh
up derive examples/conventional/bundle.json --at 2027-04-30T00:00:00Z   # status, tiers, prices and what is owed on a date
up render examples/conventional/bundle.json --chain 0                   # the agreement as contract text
up render examples/confidential/bundle.json --chain 0 --hashes-only     # the same with every private value sealed
up trace  examples/conventional/bundle.json -o conventional.trace.json  # every event, every check, every state hash
up hash   spec/06-terms/UP-Admin-Fee.json                               # the content address of a Term definition
python -m pytest                                                        # the full test suite (Node.js 20+ for the JavaScript parts)
```

`up simulate BUNDLE EVENTS.json` runs your own hypothetical events forward against a bundle.

| Command | Does |
|---|---|
| `validate` | Checks every agreement and every event in a bundle against the axioms. Exit code 2 if any event is rejected. |
| `apply` | Applies one event to its chain's current state and prints the new state, or the rule that rejected it. |
| `derive` | Reports each agreement's status, tiers, contract prices, and obligations at a time. |
| `simulate` | Runs hypothetical events forward. Signatures are not required, but Mandate limits still apply. |
| `render` | Prints the human-readable agreement text, fixed by the agreement's hash. |
| `trace` | Writes a trace file: every event, every check, and each evaluator's state hash. |

## MCP server for agents

<!-- mcp-name: io.github.Uppercentile/universal-paper -->

[![Add to Cursor](https://img.shields.io/badge/Add_to-Cursor-15171b?logo=cursor&logoColor=white)](https://cursor.com/install-mcp?name=universal-paper&config=eyJ1cmwiOiJodHRwczovL21jcC51bml2ZXJzYWxwYXBlci5vcmcvbWNwIn0%3D) [![Install in VS Code](https://img.shields.io/badge/Install_in-VS_Code-2f45c6?logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=universal-paper&config=%7B%22type%22%3A%22http%22%2C%22url%22%3A%22https%3A%2F%2Fmcp.universalpaper.org%2Fmcp%22%7D)

The buttons open Cursor or VS Code if it is installed; your browser may ask first. If nothing happens, add the server by hand. VS Code: `code --add-mcp '{"name":"universal-paper","type":"http","url":"https://mcp.universalpaper.org/mcp"}'`. Cursor and other clients: see [llms-install.md](llms-install.md).

The official Universal Paper [Model Context Protocol](https://modelcontextprotocol.io) server is a read-only layer over the reference interpreter. It lets an agent check an agreement the same way every other party does, and test whether an action is within its Mandate before anyone signs. It holds no keys, signs nothing, and writes nothing.

| Use it | How |
|---|---|
| Hosted, nothing to install | `https://mcp.universalpaper.org/mcp` (Streamable HTTP, no sign-in) |
| Local, from PyPI | `uvx universal-paper-mcp` |
| Local, from this repo | `pip install -e '.[mcp]'` then `up-mcp` |

Claude: Universal Paper is [listed in Claude's connector directory](https://claude.ai/directory/universal-paper); search for it in Claude and add it (guide: [universalpaper.org/docs/claude](https://universalpaper.org/docs/claude/)). Claude Code: `claude mcp add --transport http universal-paper https://mcp.universalpaper.org/mcp`, or locally `claude mcp add universal-paper -- uvx universal-paper-mcp`. Other clients: `{"mcpServers": {"universal-paper": {"command": "uvx", "args": ["universal-paper-mcp"]}}}`, or the hosted URL wherever a client takes a remote server. Agents setting it up for you can follow [llms-install.md](llms-install.md). It is listed in the [MCP Registry](https://registry.modelcontextprotocol.io) as `io.github.Uppercentile/universal-paper`.

The hosted endpoint (`up-mcp --hosted`, built from the [Dockerfile](Dockerfile)) is stateless: no sessions, storage, access logs or telemetry, and it never reads file paths, so a bundle is passed as an object or JSON text. It counts calls per tool name in memory and shows the totals at [/stats](https://mcp.universalpaper.org/stats); that is its only usage signal. How it is deployed and released: [deploy/README.md](deploy/README.md).

| Tool | Does |
|---|---|
| `validate_bundle` | Checks every agreement and event against the axioms and says which rule rejected what. |
| `derive_state` | Status, tiers, contract prices and obligations at a time. |
| `check_event` | Dry-runs one signed event against its chain's current state. |
| `simulate_events` | Runs hypothetical, unsigned events forward. Mandate limits still apply. |
| `simulate_amendment` | Tries one parameter change as an agent's amendment under its Mandate, and says which bound it breaks. Try `simulate_amendment("example:mandate-cap", "price", "factor", "1.05")`. |
| `simulate_price_conformity` | Checks prices given for items against a member's contract prices in its tier (or a tier it might move to): conforms or not, and by how much. Try `simulate_price_conformity("example:what-if", 1, [{"item": "00000000000017", "price": "9.40"}])`. |
| `simulate_termination` | If a party gave notice now: allowed or not (including cure periods), the effective date, duties and fees (such as admin fees) still owed, and participations that stop with it. |
| `simulate_eligibility` | Whether a member is an active participant at a time, so the agreement's terms and contract prices apply to it, with the reason. |
| `render_text` | The human-readable agreement text, fixed by its hash (optionally as an outsider sees it). |
| `hash_object` | The content hash of any JSON value. |
| `list_terms`, `explain_term` | The Term library: parameters, claims, rendering template, provenance and hash. |
| `get_example` | One of the worked example bundles, including `mandate-cap` (an agent capped at ±2% on price) and `what-if` (for the price conformity, termination and eligibility tools). |

Bundles can be passed as JSON objects, JSON text, `"example:<name>"`, or (local server only) file paths.

## Examples

All parties, identifiers, prices, rates, quantities, and dates in the examples are **hypothetical**.

- **Conventional**: an aggregator–supplier agreement with three tiers and an admin fee, two members joining through participation and tier attestation, three months of sales reports, fee payments, one tier change, and a fee disclosure.
- **Generative**: an aggregator with no staff, run entirely by an agent under a Mandate, alongside a conventional aggregator. One hospital, acting through its own agent, participates in both at once without conflict. Two out-of-bounds agent actions are rejected under A9.
- **Overlay**: a 2024 contract described in Universal Paper in 2027, identified by its document hash, without renegotiation.
- **Confidential**: the conventional story with every price, rate, quantity, and amount sealed. An evaluator with no disclosures reaches the same verdicts and state hashes.

`python3 examples/build_examples.py` rebuilds every bundle and trace. Output is byte-identical across runs. Example keys and salts are derived from fixed seeds so the examples are reproducible; real keys and salts must be random.

## Playground page

Open `explorer/index.html` in a browser. It is one self-contained file; apart from web fonts it makes no network requests. Its look follows the shared design tokens in `explorer/src/tokens.css`, also used by the developer explainer. It has four parts:

- **How it works**: a scroll explainer that follows one fee clause from words to a fingerprint, signatures, and a caught edit, computed live. On a phone the visual pins at the top and the steps scroll under it.
- **Vision**: an illustration of where Universal Paper could sit, under apps for contracting, procurement, pricing, and settlement, with agents acting for parties under Mandates. The apps are hypothetical. The events are not: each scenario is generated, signed, and checked by the engine in the page, including an agent action outside its Mandate that every party rejects.
- **Playground** (collapsed by default; open it with its button or a link to `#playground`): start from an example and change the few things people try first (the fee, the length, the supplier, whether the rate is sealed) while the cover sheet, the contract, and the fingerprint update. Every clause stays editable under “Edit every clause”. **Compare** shows what changed between two versions, clause by clause and word by word, and whether existing signatures still cover it. **History** signs the agreement and plays it forward: enter monthly sales and payments and see the reports, fees, and the status of every duty on any date.
- **Conformance** (the headline figures show; the rest opens with its button or a link to `#conformance`): the test suite by file, the audit findings, and a button that runs random agreements and attacks in the browser against eight invariants.

On universalpaper.org the Playground has its own page, [/playground/](https://universalpaper.org/playground/), which shows this file's Playground section in the site's look; the rest of the site is built by `site/build_site.py` (see `site/README.md`).

Everything live runs on a second, independent engine in JavaScript (`explorer/src/`). `tests/test_js_conformance.py` requires it to reproduce every Python trace, rendering, and simulation byte for byte, and to pass every invariant on 60 fixed seeds. Rebuild the page after editing `explorer/src/` with `python3 tools/build_explorer.py`; add `--run-tests` to run the suite first and record the result shown on the page (`explorer/conformance-results.json`). The plain build is deterministic so CI can check the committed page.

## How it is tested

`python -m pytest` runs more than 200 tests in a few minutes. Node.js 20 or later is needed for the JavaScript parts, which are skipped without it. CI runs everything on Python 3.11 to 3.13.

- **Rules.** Every axiom (A1 to A13), every transition rule, and every clause form has tests that build small hypothetical agreements and try to break them.
- **Every Term.** All sixteen Terms are executed in a valid agreement, every parameter is checked against its declared type, and every claim type is attested, acknowledged, and attempted with ill-typed data.
- **Two engines, one answer.** The JavaScript engine must reproduce every Python trace, render, and simulation byte for byte, including a trace for every claim type of every Term. Differential tests run both engines on tens of thousands of seeded random inputs (canonical JSON, hashes, Ed25519 edge cases, times, periods, exact decimals, type checks) and require identical results, including identical rejections.
- **Published vectors.** Ed25519 against RFC 8032, SHA-256 and SHA-512 against known digests, and a check that the small-order key table is exactly the curve's torsion points.
- **Hostile input.** Hypothesis mutates signed example events and feeds arbitrary JSON to the evaluator: altered events are always rejected, nothing crashes or hangs, and derived values stay computable. `HYPOTHESIS_PROFILE=deep` runs a longer search.
- **Reproducibility.** Rebuilding the Term library, examples, traces, and the Playground page must produce byte-identical files.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full list and how to add tests.

## Optional integrations

- [Legal Context Protocol](docs/integrations/legal-context-protocol.md): an optional way for agents to discover a Universal Paper bundle at `/.well-known/legal-context.json` and pin it by its fingerprint. Universal Paper does not depend on it.
- [Verifiable Credentials](docs/integrations/verifiable-credentials.md): an optional convention for W3C Verifiable Credentials that reference a Universal Paper fingerprint, for roster participation and role snapshots. A credential is a snapshot only; participation status still comes from a Universal Paper engine (`simulate_eligibility`). Universal Paper does not issue, verify or require them.
- [Fingerprint Coordination](docs/integrations/fingerprint-coordination.md): an optional analytical convention for sharing Universal Paper fingerprints under explicit rules and deriving recomputable profiles (parameter ranges, variance, historical deltas, engine-checked Proposal seeds), with a [simulated demo](examples/integrations/fingerprint-coordination/demo/index.html) built only from the public examples. Universal Paper does not operate, require or depend on any analytics, telemetry or hosting.

## Contributing and security

Contributions to the specification and the code are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Please report vulnerabilities privately, as described in [SECURITY.md](SECURITY.md). Changes are recorded in [CHANGELOG.md](CHANGELOG.md).

## Licenses

Universal Paper was created by [Uppercentile](https://uppercentile.com), which offers it to the market for free. Anyone may use, implement, extend, fork, and build commercial products on it, without permission or payment. No account, fee, or license key is ever required.

| What | License |
|---|---|
| Specification, Term library, and documentation (`spec/`, `DESIGN_NOTES.md`, website text) | [CC BY 4.0](spec/LICENSE) |
| Code, JSON Schemas, tools, tests, and test vectors | [Apache-2.0](LICENSE) (see [NOTICE](NOTICE)) |
| Example agreements, bundles, and traces (`examples/`) | [CC0 1.0](examples/LICENSE) (public domain) |

To credit the specification: *"Universal Paper" specification by Uppercentile, https://universalpaper.org, licensed under CC BY 4.0.* Details: [universalpaper.org/license](https://universalpaper.org/license/). Uppercentile is the specification's steward, not its owner; see the [neutrality charter](spec/08-neutrality-charter.md).
