## What this changes

<!-- One or two sentences. Link the issue if there is one. -->

## Kind of change

- [ ] Specification (`spec/`): wording only, no change in meaning
- [ ] Specification: changes what is valid, or what an evaluator computes
- [ ] Term library (`tools/gen_terms.py`, regenerated `spec/06-terms/`)
- [ ] Reference interpreter (`src/`)
- [ ] JavaScript engine or Explorer (`explorer/src/`)
- [ ] Tests, tooling, or docs only

## Checklist

- [ ] `python -m pytest` passes (it includes the JavaScript conformance and differential tests when Node.js is installed)
- [ ] `ruff check src tests tools examples` and `mypy` pass
- [ ] If the spec's meaning changed: both engines are updated, `CHANGELOG.md` says so, and generated files are rebuilt (`tools/gen_terms.py`, `examples/build_examples.py`, `tools/build_explorer.py`)
- [ ] No real party names, keys, prices, or contract data (examples use hypothetical values only)
