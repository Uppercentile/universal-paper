# Pre-release audit

**Scope:** the whole repository at `UP/0.1-draft`: the specification (`spec/`), the JSON Schemas, the Python reference interpreter and CLI (`src/`), the JavaScript engine (`explorer/src/`), the examples and traces, and the tests.
**Date:** 22 November 2026.
**Method:** reading the spec against both engines line by line; differential testing of the two engines on seeded random input; property-based fuzzing of the evaluator with Hypothesis; published test vectors; and targeted attacks (hang, forgery, divergence, crash).
**Outcome:** 16 findings, all fixed in both engines unless noted. Each fix has a regression test in `tests/test_audit_regressions.py` or a named test file. Most of the regression tests fail when run against the code from before the audit (the rest guard against nearby variants). The full suite went from 71 to 170 tests.

The audit was done by the same team that wrote the code. It is not a substitute for an independent review. See [What remains open](#what-remains-open).

## Severity

- **High:** an evaluator can be made to accept something invalid, hang, or disagree with another correct evaluator.
- **Medium:** an evaluator can compute a wrong or platform-dependent value, or the spec and code disagree on validity.
- **Low:** robustness, hygiene, or clarity issues with no effect on valid input.

## Findings

| # | Severity | Finding | Fix |
|---|---|---|---|
| F01 | High | **A signed Agreement could hang every evaluator.** A Renewing-Term with `renewal_period.count` of 0 and a very large `max_renewals` made the renewal loop spin without advancing. Period counts were never checked to be ≥ 1 although the spec requires it. | Periods are type-checked (count 1 to 10 000). `add_period` refuses bad counts. Regression: `test_f01`. |
| F02 | High | **Parameters were not type-checked** (spec drift from A1, which requires "a value of the declared type"). Only `Role` and `[Role]` were checked, so impossible dates, negative counts, booleans as integers, and malformed roundings were accepted into executed Agreements. | New `typecheck` module (and its JavaScript port) parses every type expression in the Term library and checks every parameter. Spec 01 §2 now defines the type expressions. `test_f02`, `test_terms.py`. |
| F03 | High | **Claim data was not type-checked** (drift from 05 §2.4, "data matching its schema"). A sales report with `total_net` of `"lots"` was accepted, after which `derive`, `trace`, and `obligations` crashed for everyone holding the chain. | Every claim field is checked against its declared type (`attest-data-types`). `test_f03`. |
| F04 | High | **The two engines disagreed on signature validity.** Python used `bytes.fromhex`, which accepts uppercase hex and whitespace, so an event whose signature was written in uppercase verified in Python and failed in JavaScript. OpenSSL accepted a non-canonical public key encoding (y ≥ p) that the JavaScript engine rejected. Either is a consensus split (A4). | Strict verification rules, written into spec 01 §1.3 and applied identically by both engines: lowercase hex only, canonical key and R, S < L, cofactorless equation. `test_crypto.py`, `test_differential.py`. |
| F05 | High | **Small-order keys allowed forgery.** For a key that is a point of small order (for example the identity point), the "signature" R = identity, S = 0 verified on any message in both engines. A party listed with such a key could be impersonated by anyone, or could later deny every signature. | Keys of small order are invalid as Party, agent, or Mandate keys and never verify. The table of the eight torsion points is recomputed from first principles in `test_crypto.py`. `test_f07`. |
| F06 | Medium | **Decimal arithmetic was not exact in Python** (spec 04 §6). Price-Reference valuation, fee base sums, and rate rendering used Python's default 28-digit context, while JavaScript used exact BigInt arithmetic. Example: 1000000000000000000000.005 × 1.0000001 rounded half-even to 2 places gave `.00` in Python and `.01` (correct) in JavaScript. | All sums and products use an exact context. Decimal strings are limited to 64 characters and rounding scales to 0 to 18, so exact arithmetic stays cheap. `test_f04`, `test_differential.py`. |
| F07 | Medium | **Canonical JSON differed between engines.** A lone surrogate in a string crashed Python but was silently replaced with U+FFFD and hashed in JavaScript. `100.0` or `1e2` was rejected by Python and accepted as `100` by JavaScript. Non-ASCII keys, forbidden by the spec, were accepted by both. | Both reject lone surrogates and non-ASCII keys, and both canonicalize integral numbers as integers, matching RFC 8785. Bundles are normalized on load. `test_crypto.py`, `test_differential.py`. |
| F08 | Medium | **Times and decimals were parsed differently.** JavaScript accepted `10:60:00` and `23:59:60` by rolling over, and read years 0000 to 0099 as 1900 to 1999. Python's `\d` matched non-ASCII digits (`２０２７`) and `$` matched before a trailing newline, so `"1.5\n"` was a valid Decimal. Python wrote years before 1000 without zero padding, producing an invalid Time. | ASCII-only, fully anchored patterns in both engines; explicit range checks; explicit zero-padded formatting; years limited to 0001 to 9999. `test_f08`, `test_f09`, `test_differential.py`. |
| F09 | Medium | **Rendering depended on the machine's locale** (A8). Dates used `strftime('%B')`, so a German locale rendered "Januar" and changed the text that the hash is supposed to fix. | Fixed English month names. `test_f09`. |
| F10 | Medium | **Renewals drifted at month end, and the spec contradicted itself.** 04 §3.1 defined `eₖ₊₁ = eₖ + period`, which 04 §2 forbids for periodic sequences. A term ending 31 January renewed to 28 February and then 28 March. | Spec and both engines now compute `eₖ = end + k × period` directly. `test_f05`. |
| F11 | Low | **Mandate and proposal fields were not validated.** Mandate keys and validity times were compared as raw strings, and a proposal's `expires` could be any string. | Mandates with malformed keys or times are not covered (with a clear reason). `expires` must be a Time. Spec 01 §10 and 05 §2.1 updated. `test_f10`. |
| F12 | Low | **A Bundle could hold two versions of one chain.** Two entries with the same genesis were silently resolved by using the last, hiding a fork. `up apply` could create one by re-applying a genesis. | Spec 01 §12 makes such a Bundle invalid. `up validate` reports it and exits 2. `up apply` refuses a duplicate genesis. `test_f12`. |
| F13 | Low | **The CLI printed tracebacks on bad input**, and silently accepted duplicate JSON keys and `NaN`. | Strict JSON loading (I-JSON), clear `up: error:` messages with exit code 1. `test_robustness.py`. |
| F14 | Low | **An installed package had no Term library.** `World()` looked for `spec/06-terms` relative to the source tree, so after `pip install` it silently found zero Terms. | The library ships as `universal_paper/terms.json`, generated by `tools/gen_terms.py` and checked against `spec/06-terms` by the tests. Verified by installing the wheel outside the repository. |
| F15 | Low | **Structural names could be sealed.** Clause and option names (for example Admin-Fee's `report_clause`, a tier's `name`) were typed `string`, which is sealable, although spec 01 §3.3 lists them as structural. Sealing one broke fee computation. | New type `Name` (structural). Three Term definitions changed: Admin-Fee, Tiers, Tier-Selection, so their hashes changed (listed in `spec/06-terms/README.md`). |
| F16 | Low | **Seal salts were only length-checked.** The spec requires 64 lowercase hex characters. | Both engines check the format. |

Also fixed while auditing: the spec's Term README still said definition hashes were "not pinned yet" (they are now listed and tested), the JSON Schema bounds now match the spec, and lint found two unused variables and a closure over a loop variable (harmless, rewritten for clarity).

## Test suite added

| File | Purpose |
|---|---|
| `tests/test_terms.py` | All 16 Terms execute; every parameter is type-checked; every claim type (13) is accepted when well formed, acknowledged, and rejected when ill typed. Term files are regenerated and compared, and every published hash is recomputed. |
| `tests/test_crypto.py` | RFC 8032 vectors in both engines; SHA-256/512 digests; strict-rule edge cases; torsion table from first principles; canonical JSON edge cases. |
| `tests/test_differential.py` | More than 30 000 seeded random operations run on both engines with identical results required: canonical JSON and hashes, signatures and edge cases, times and periods, exact decimals and rounding, type checks of every shipped type. |
| `tests/test_robustness.py` | Hypothesis mutates signed example events (any change must be rejected; nothing may crash) and feeds arbitrary JSON to the evaluator; key-order independence; every CLI command, and bad-input handling. A `deep` profile ran 6 000 cases with no failure. |
| `tests/test_js_conformance.py` | Now also requires the JavaScript engine to reproduce a Python trace for every claim type of every Term, not only the examples. |
| `tests/test_audit_regressions.py` | One test per finding. |

Branch coverage of the Python package is 91 % (the CLI is now measured too). The Explorer page itself (app.js, the browser UI) was not smoke-tested in a browser during the audit; its engine was tested in Node. CI (`.github/workflows/ci.yml`) runs the suite on Python 3.11, 3.12 and 3.13 with Node 20 and 22, plus ruff, mypy, and a check that regenerating every generated file changes nothing.

## What remains open

These are known and not fixed. None is a known way to make an evaluator accept something invalid.

1. **No independent review yet.** Both engines and this audit come from one team. A misreading of the spec shared by both engines would not be caught by the differential tests. Before 1.0, an external review of `spec/01` §1–3, `spec/04`, and `crypto.py` / `up-crypto.js` is the most valuable next step.
2. **The JavaScript Ed25519 is not constant-time.** That does not matter for verification of public data, which is all the Explorer does with real input. Its signing is only used with the public demo seeds. SECURITY.md says not to use it with real keys.
3. **Long-running loops are bounded but not constant.** Renewal and duty periods are enumerated up to the evaluation time, so a daily period evaluated thousands of years ahead costs millions of steps. It cannot hang (counts are at least 1 and times end at 9999), but a cap on evaluation horizon or a closed-form computation would be better.
4. **Rejection reasons for malformed input differ between engines.** Verdicts match. For input so malformed that an internal error is raised, the two engines word the reason differently. Example traces never contain such input.
5. **The JavaScript engine cannot see duplicate JSON keys** (the browser's `JSON.parse` keeps the last). The Explorer only loads files from this repository. The Python CLI rejects them.
6. **Typing is partial.** `mypy` passes, with Optional-narrowing checks relaxed for `engine.py`, whose design treats any exception on untrusted input as a rejection.
7. **Design limits already listed in DESIGN_NOTES §4:** no Mandate revocation other than expiry, no key rotation, single-line chains, asserted time.
8. **Legal content is unreviewed.** No Term has been reviewed by counsel (each says so in its provenance).

## Before the repository goes public

- Create the GitHub repository, push, and turn on **private vulnerability reporting** and branch protection for `main` (require the CI checks).
- Put a real contact address in the repository profile, since `SECURITY.md` and `CODE_OF_CONDUCT.md` point there.
- Decide the publishing name (open question 2). It appears in Term provenance and would change every Term hash, so it is best settled before the first public tag.
- Republish the Explorer artifact if it is shared, because the Term hashes in it changed.
