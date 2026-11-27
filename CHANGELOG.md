# Changelog

All notable changes to the specification, the Term library, and the reference implementations. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Until 1.0, a change to the spec may change what is valid and the hashes of Term definitions. Such changes are marked **Validity**.

## [Unreleased]

### Added

- Optional Legal Context Protocol integration, outside the language: `docs/integrations/legal-context-protocol.md`, a reference adapter in `integrations/lcp/`, worked examples in `examples/integrations/lcp/`, and an optional page at universalpaper.org/integrations/. No change to the spec, schemas, fingerprints, Terms or engines.
- Optional Verifiable Credentials convention, outside the language: `docs/integrations/verifiable-credentials.md`, a payload-shape helper and two unsigned example payloads (roster participation snapshot, role proof) in `examples/integrations/vc/`, and an optional page at universalpaper.org/integrations/verifiable-credentials/. No change to the spec, schemas, fingerprints, Terms or engines.
- Optional Fingerprint Coordination convention, outside the language: `docs/integrations/fingerprint-coordination.md`, a reference helper (`up_fpc.py`: structural diffs, Derived Profiles, engine-checked Proposal seeds), JSON Schemas, worked examples, `regenerate.py --check`, and a static simulated demo from public examples in `examples/integrations/fingerprint-coordination/`, plus an optional page at universalpaper.org/integrations/fingerprint-coordination/. The demo has a predictive-redline playthrough of one seed driven by `demo/scenario.json` (HowTo JSON-LD, static fallback). No change to the spec, schemas, fingerprints, Terms or engines.

### Changed

- MCP tools: every tool now has a short title for people (for example "Validate a bundle"), set on the tool and in its annotations, so clients can show it in place of the function name. A test checks it. No change to what any tool computes.

## [0.1.2] - 2026-11-24

### Changed

- MCP tools: every parameter now has a description in its input schema (format, structure and valid values, e.g. a bundle as an object, JSON text or `"example:<name>"`), and every tool description says when to use it rather than a named sibling tool and what it needs first. A test checks both. No change to what any tool computes.

## [0.1.1] - 2026-11-24

### Added

- MCP tool `simulate_amendment`: one call checks a proposed change to one clause parameter against the agent's Mandate (A9). Every tool also accepts `"example:<name>"` as its bundle. New example bundle `examples/mandate-cap`.
- MCP tools `simulate_price_conformity`, `simulate_termination` and `simulate_eligibility` (`src/universal_paper/whatif.py`): whether prices conform to a member's contract prices in its attested tier; whether a party may terminate now, when it takes effect and what is still owed; whether a member is an active participant at a time. Read-only, computed by the reference interpreter. New example bundle `examples/what-if`.
- One-click installs for the hosted MCP server (Add to Cursor, Install in VS Code) on the developer page and in the README, plus `llms-install.md`.

With these, the PyPI packages and the MCP Registry entry match the hosted endpoint: 13 tools.

## [0.1.0] - 2026-11-24

Version 0.1.0 is the first release to PyPI. Pre-release audit. Details and rationale for every item are in [AUDIT.md](AUDIT.md).

### Added

- The official MCP server, released three ways: a hosted, stateless endpoint (`up-mcp --hosted`, `Dockerfile`, served at `https://mcp.universalpaper.org/mcp`), the `universal-paper-mcp` package on PyPI (`uvx universal-paper-mcp`), and an MCP Registry entry `io.github.Uppercentile/universal-paper` (`server.json`). The hosted mode never reads file paths, keeps no access logs and only counts calls per tool name (`/stats`).
- `release.yml` publishes both packages to PyPI with trusted publishing and `server.json` to the MCP Registry on a `v*` tag; `deploy-mcp.yml` deploys the endpoint to Fly.io. See `deploy/README.md`.
- MCP sections on the developer page, in `llms.txt` and in `partners.json`.

### Changed (Validity)

- Every Term parameter and every claim data field is checked against its declared type, in both engines (A1; spec 05 §2.4). Spec 01 §2 defines the type expressions and the bounds: Period count 1 to 10 000, Rounding scale 0 to 18, Decimal strings at most 64 characters, years 0001 to 9999.
- Ed25519 verification is strict and identical in both engines: lowercase hex, canonical encodings, S < L, and keys of small order are invalid (spec 01 §1.3).
- Canonical JSON rejects lone surrogates and non-ASCII keys, and canonicalizes integral numbers such as `100.0` as integers (spec 01 §1.1).
- Window renewals are computed directly from the original end (`eₖ = end + k × period`), with no month-end drift (spec 04 §3.1).
- New structural type `Name` for clause and option names. The Admin-Fee, Tiers, and Tier-Selection definitions changed, so their hashes changed. Example bundles and traces were regenerated.
- Malformed Mandates are not covered; a proposal's `expires` must be a Time; seal salts must be 64 lowercase hex characters.
- A Bundle that holds two versions of one chain is invalid (spec 01 §12).

### Fixed

- Evaluators could hang on a renewal period of zero length.
- Python decimal arithmetic was rounded to 28 digits in valuations and fee sums; it is now exact, as the spec requires and as the JavaScript engine already was.
- Time parsing and formatting differed between engines (seconds or minutes of 60, years before 1000, non-ASCII digits, trailing newlines).
- Rendered dates depended on the process locale.
- The CLI no longer prints tracebacks on bad input, and rejects duplicate JSON keys and NaN.
- An installed package now includes the Term library.

### Added

- `up-mcp`, a read-only MCP server over the reference interpreter (validate, derive, check an event, simulate under a Mandate, render, hash, Terms, examples). Optional dependency: `pip install 'universal-paper[mcp]'`.
- Tests for all sixteen Terms and every claim type, cross-engine differential tests, Hypothesis fuzz tests, RFC 8032 vectors, CLI tests, and one regression test per audit finding.
- Term definition hashes in `spec/06-terms/README.md`.
- CI workflow, Dependabot, issue and pull request templates, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, ruff and mypy configuration, and package metadata.

## [0.1.0.dev0] - 2026-11-22

First working draft: specification `UP/0.1-draft`, sixteen-Term library, JSON Schemas, Python reference interpreter and CLI, worked examples with traces, the Explorer with a second engine in JavaScript, and conformance tests between the two.
