# Changelog

All notable changes to the specification, the Term library, and the reference implementations. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Until 1.0, a change to the spec may change what is valid and the hashes of Term definitions. Such changes are marked **Validity**.

## [Unreleased]

## [0.1.0] - 2026-11-22

First public release of the reference interpreter for the `UP/0.1-draft` specification (still a working draft, not yet reviewed by counsel). Includes the pre-release audit. Details and rationale for every item are in [AUDIT.md](AUDIT.md).

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

- `up-mcp`, a read-only MCP server over the reference interpreter (validate, derive, check an event, simulate under a Mandate, render, hash, Terms, examples). Optional dependency: `pip install 'universal-paper[mcp]'`. A `--public` mode and `deploy/mcp/` (Dockerfile, Fly.io config) host it over HTTP for untrusted callers.
- Tests for all sixteen Terms and every claim type, cross-engine differential tests, Hypothesis fuzz tests, RFC 8032 vectors, CLI tests, and one regression test per audit finding.
- Term definition hashes in `spec/06-terms/README.md`.
- CI workflow, Dependabot, issue and pull request templates, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, ruff and mypy configuration, and package metadata.

## [0.1.0.dev0] - 2026-11-22

First working draft: specification `UP/0.1-draft`, sixteen-Term library, JSON Schemas, Python reference interpreter and CLI, worked examples with traces, the Explorer with a second engine in JavaScript, and conformance tests between the two.
