# Security policy

Universal Paper is a language whose whole purpose is that anyone can check an agreement without trusting anyone else. A bug that lets an invalid agreement or event pass as valid, lets two correct evaluators disagree, or lets a confidential value leak, is a security bug in the strongest sense. Please report it privately.

## What counts

Examples, roughly from most to least serious:

- A forged, altered, backdated, or unauthorized Event, Agreement, or Mandate that an evaluator accepts.
- Two evaluators (Python and JavaScript, or two runs of either) that reach different verdicts, State hashes, or derived values from the same Bundle. This breaks axiom A4.
- A sealed value that can be recovered, or a validity check that depends on a sealed value (A10).
- A rendering that differs from what the hash commits to (A8).
- Input that makes an evaluator hang, exhaust memory, or crash instead of rejecting it.
- A weakness in the specification itself, even if both engines implement it faithfully.

Typos and ordinary bugs that do not affect validity are welcome as public issues.

## How to report

Use GitHub's private vulnerability reporting for this repository (**Security → Report a vulnerability**). If that is not available to you, contact the maintainers at the address in the repository profile and ask for a private channel. Do not open a public issue for a vulnerability.

Please include the smallest Bundle or input that shows the problem, which engine (Python, JavaScript, or both), and what you expected. Use hypothetical data only. Never send real agreements, real prices, or private keys.

We aim to acknowledge a report within 5 working days and to agree a disclosure date with you. We will credit you in the advisory and in `CHANGELOG.md` unless you prefer otherwise.

## Supported versions

The project is a pre-1.0 draft (`UP/0.1-draft`). Only the latest commit on `main` receives fixes. Until 1.0, a security fix may change what is valid, and therefore change hashes of Term definitions and examples. Such changes are called out in `CHANGELOG.md`.

## Scope notes

- Example keys and salts in `examples/` are derived from public seeds so the examples are reproducible. They are not secret and must never be used for anything real. Real keys and salts must be random (`Key.generate()`, `secrets.token_hex(32)`).
- The Playground page (`explorer/index.html`) runs entirely in the browser; its only network requests load web fonts. Its JavaScript engine is a second implementation held to the Python reference by `tests/test_js_conformance.py` and `tests/test_differential.py`. It is a demonstration, not a wallet: do not paste real private keys into it.
- The JavaScript Ed25519 implementation is written for clarity and is not constant-time. It is fine for verifying public data. Do not use it to sign with real keys.

The audit done before publication is in [AUDIT.md](AUDIT.md).
