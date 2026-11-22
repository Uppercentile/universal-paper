# Contributing

Thank you for helping. Universal Paper is a language first and software second, so contributions to the specification count as much as code.

By contributing you agree that your contributions to `spec/` are licensed under [CC BY 4.0](spec/LICENSE) and everything else under [Apache-2.0](LICENSE). Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Ground rules

- **The specification is the authority.** The Python interpreter is the reference implementation of it, and the JavaScript engine in `explorer/src/` is a second implementation. If code and spec disagree, the spec wins, or the spec gets fixed first.
- **Value neutrality (A6).** No Term, example, test, or default may suggest a price, fee, rate, threshold, or period. Examples use clearly hypothetical values.
- **No real data.** Never commit real party names, identifiers, prices, agreements, or keys. Example keys come from public seeds.
- **Determinism (A4).** Nothing may depend on the clock, locale, floating point, hash-map order, or platform. Both engines must agree byte for byte.

## Setting up

```sh
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
python -m pytest            # about two minutes; needs Node.js 20+ for the JavaScript tests
ruff check src tests tools examples
mypy
```

Without Node.js, the JavaScript conformance and differential tests are skipped. CI always runs them.

## Kinds of change

**Spec wording only** (no change in what is valid or computed): edit `spec/`, run the tests, open a pull request.

**A change in meaning** (what is valid, or what an evaluator computes):

1. Change the spec text first, in the same pull request.
2. Change both engines: `src/universal_paper/` and `explorer/src/`. Rejection reasons must match word for word, since traces record them.
3. Add a test that fails before the change. If it touches canonical form, signatures, numbers, or times, add cases to `tests/test_differential.py`.
4. Rebuild generated files and commit them: `python tools/gen_terms.py`, `python examples/build_examples.py`, `python tools/build_explorer.py`. CI fails if any of them is out of date.
5. Describe the change under "Unreleased" in `CHANGELOG.md`, and say whether existing Bundles stay valid.

**A new or changed Term:** edit the source list in `tools/gen_terms.py` (never the generated `spec/06-terms/*.json` or `UP-*.md`), then regenerate. A changed definition has a new hash, which `spec/06-terms/README.md` lists. A Term must use only the six clause forms. If it cannot, that is a spec discussion first.

**Interpreter or Playground page only:** keep both engines in step and keep `tests/test_js_conformance.py` passing.

## Tests

| File | What it holds |
|---|---|
| `test_axioms.py`, `test_rules.py` | Every axiom, transition rule, and clause form |
| `test_terms.py` | All sixteen Terms: execution, parameter types, every claim type |
| `test_crypto.py` | RFC 8032 and SHA vectors, strict signature rules, canonical JSON |
| `test_differential.py` | Python and JavaScript on thousands of seeded random inputs |
| `test_robustness.py` | Hostile input (Hypothesis), key order, the command line |
| `test_js_conformance.py` | The JavaScript engine reproduces every Python trace, render, and simulation |
| `test_audit_regressions.py` | One test per finding in `AUDIT.md` |

For a longer fuzzing run: `HYPOTHESIS_PROFILE=deep python -m pytest tests/test_robustness.py`.

## Style

Python follows `ruff` with the settings in `pyproject.toml`. Prose in the spec is plain, short, and neutral in voice (no "you" or "we"), with normative words (MUST, MAY) only where a rule is meant.

## Reporting security issues

Please do not open public issues for vulnerabilities. See [SECURITY.md](SECURITY.md).
