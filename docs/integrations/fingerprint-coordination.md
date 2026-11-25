# Fingerprint Coordination (optional integration)

> **Optional external convention.** Universal Paper is a self-contained language for computable agreements. It does not depend on this convention. Universal Paper does not operate, require, endorse or depend on any telemetry service, analytics or prediction engine, storage platform, registry or visualization. This page describes an optional analytical convention that parties and agents may use, outside the language, to share fingerprints and derive recomputable profiles from them.

Nothing here changes the Universal Paper language, its schemas, its fingerprint rules, its Terms, its Event kinds, its axioms or its engines. You can ignore this page entirely and lose nothing.

**See it first:** the [simulated insight demo](https://universalpaper.org/integrations/fingerprint-coordination/demo/) ([source](../../examples/integrations/fingerprint-coordination/demo/index.html)) is built only from the hypothetical example bundles already in the repository. It needs no backend, account or network call.

## Purpose

Every Universal Paper artifact is structured and content-addressed, so a set of artifacts is comparable by construction: the same Term, the same parameter, the same engine. Fingerprint Coordination is a minimal way to **share or pool fingerprints under explicit rules** and to **derive profiles that anyone holding the same inputs can recompute byte for byte**.

What a profile can carry:

- **Predictive redline / Proposal seeds.** Unsigned candidate changes to one agreement, produced by a fixed rule from the pooled inputs and run through a Universal Paper engine before they are listed: new agreement fingerprint, accepted or rejected, and how derived obligations differ.
- **Variance and outlier detection.** Where each agreement sits against its cohort, per parameter, without publishing its raw value.
- **Aggregated parameter ranges and median deltas.** Minimum, median and maximum per parameter, and the median change proposed in history.
- **Historical delta analysis.** Every proposal that superseded an agreement, diffed structurally, with the engine's verdict.
- **A closed loop.** Accepted (and rejected) proposals feed the next profile, and every seed passes the same engine that will judge the real proposal.
- **Recomputable business intelligence.** Every derived object lists its inputs by fingerprint and carries its own fingerprint, so a reader checks it instead of trusting it.

## What this is, and what it is not

| This is | This is not |
|---|---|
| Two small JSON shapes, a **Contribution** and a **Derived Profile**, each fingerprinted with the Universal Paper rule | A new Universal Paper field, Term, Event kind, primitive, rule or hash |
| A reference helper, standard library plus the `universal-paper` package, that diffs, derives, verifies and simulates locally | A hosted service, registry, data pool, dashboard, API or application. None is offered or implied |
| A way to pool fingerprints among parties who already hold, or are entitled to, the artifacts | A way to obtain anyone's agreements. A fingerprint reveals nothing without the artifact |
| Seeds: candidate changes a party may review, sign and propose | Recommendations, benchmarks, market data or advice. Only the parties decide what to propose |
| A simulated demo from public, hypothetical examples | Real or live data of any kind |

**Engine evaluation stays authoritative.** A profile is derived data. What an agreement says, and whether a proposal is valid, comes only from evaluating the artifacts with a Universal Paper engine.

## Privacy by default

- **The default disclosure is `fingerprint-only`.** A contribution shares more (`structure`: which Terms; `parameters`: unsealed values) only when its contributor says so.
- **Sealed values are never counted.** A sealed parameter (axiom A10) stays sealed: the profile counts it as `sealed` and nothing else. The demo includes the confidential example as its hashes-only file to show this.
- **Minimum cohort.** No statistic is published from fewer distinct inputs than `minimumCohort` (3 in the demo). Suppressed statistics keep their key and counts and lose their values.
- **Positions, not values, per agreement.** The variance matrix records where an agreement sits against the cohort (above, below, at the median), never its raw value. Per-agreement rows are keyed by fingerprint, which is meaningful only to someone who already holds that artifact. Labels appear in the demo only because its inputs are public.
- **Local by construction.** The helper has no network code and writes nothing unless you ask. No telemetry, ever.

## Shapes

Both shapes use the Universal Paper fingerprint, `"sha256:" + hex(SHA-256(JCS(strip(o))))` exactly as in [spec/01-domain.md §1](../../spec/01-domain.md). An object's own `fingerprint` member is the fingerprint of all its other members. JSON Schemas: [contribution.schema.json](../../examples/integrations/fingerprint-coordination/schemas/contribution.schema.json), [derived-profile.schema.json](../../examples/integrations/fingerprint-coordination/schemas/derived-profile.schema.json).

### Contribution

What a party shares, how much of each artifact, and the rules for using it ([example](../../examples/integrations/fingerprint-coordination/contribution.json)):

```json
{
  "type": "FingerprintContribution",
  "convention": "fingerprint-coordination/0.1",
  "contributor": "did:example:hypothetical-health-purchasing-alliance",
  "created": "2027-04-20T12:00:00Z",
  "artifacts": [
    { "fingerprint": "sha256:93ab686a4b85a5670a056ccfd7d7f5c5d1cfaa5a2184f6e03e48961b726abcae",
      "kind": "Bundle", "disclosure": "parameters" }
  ],
  "rules": {
    "purposes": ["parameter-ranges", "variance", "historical-deltas", "proposal-seeds"],
    "minimumCohort": 3, "attribution": "none", "outputs": "aggregate-only",
    "sealedValues": "never-counted", "expires": "2028-04-20T12:00:00Z"
  },
  "fingerprint": "sha256:7d1a3e5b9b8d06d28ca135d498c5e6dbf728ac4159c17812c86c9d5708be09a3"
}
```

The artifacts themselves travel by whatever channel the parties already use. The contribution names them; it does not carry them.

### Derived Profile

The output ([demo-profile.json](../../examples/integrations/fingerprint-coordination/demo-profile.json)). Abridged:

```json
{
  "type": "DerivedProfile",
  "convention": "fingerprint-coordination/0.1",
  "simulated": true,
  "notice": "SIMULATED FROM PUBLIC EXAMPLES. ...",
  "method": { "helper": "examples/integrations/fingerprint-coordination/up_fpc.py", "function": "derive_profile",
              "minimumCohort": 3, "maxSeeds": 2, "sealedValues": "never-counted" },
  "inputs": [ { "fingerprint": "sha256:93ab…abcae", "kind": "Bundle", "label": "conventional",
                "source": "examples/conventional/bundle.json", "disclosure": "parameters" } ],
  "inputsRoot": "sha256:…",
  "parameters": [ { "key": "UP:Admin-Fee.rate", "observations": 5, "inputs": 4, "sealed": 1,
                    "min": "0.02", "median": "0.02", "max": "0.03", "differsFromMode": 2, "historicalChanges": 1 } ],
  "matrix": [ { "cohort": "aggregator+supplier", "columns": ["A1", "A4"], "rows": [ { "key": "UP:Admin-Fee.rate",
                "cells": [ { "state": "median", "deviation": "0" }, { "state": "sealed" } ] } ] } ],
  "deltas": [ { "from": "sha256:…", "to": "sha256:…", "outcome": "rejected", "paramsChanged": [ … ], "reason": "…" } ],
  "seeds": [ { "id": "seed-1", "rule": "toward-median", "target": { "input": "sha256:…", "chain": 1, "agreement": "sha256:…" },
               "change": { "op": "set-param", "clause": "fee", "param": "rate", "from": "0.03", "to": "0.02" },
               "simulation": { "accepted": true, "newAgreement": "sha256:1b59…f3ee", "obligationsChanged": [ … ] } } ],
  "fingerprint": "sha256:…"
}
```

- `inputs` lists every input by fingerprint; `inputsRoot` is the fingerprint of the sorted, de-duplicated array of those fingerprints, so a set of inputs can be named in one value.
- Parameters are compared within a **cohort** of agreements with the same set of Roles. Parameters that identify one agreement (times, chain ids, hashes, names, free text) are never compared.
- `method` names the helper and options, so `verify_profile` can recompute the profile and require the same fingerprint.

### Seed rules

Seeds come from two fixed, documented rules. Neither is a judgment about what anyone should agree to.

| Rule | Picks | Proposes |
|---|---|---|
| `toward-median` | The largest numeric outlier in a cohort | That parameter set to the cohort median |
| `common-clause` | The most common parameterized Term (in at least 2/3 of a cohort, from at least `minimumCohort` inputs) missing from an agreement | Adding it, with the cohort's most common parameters, to the most structurally similar agreement that lacks it |

Price and tier Terms (`UP:Tiers`, `UP:Tier-Selection`, `UP:Price-Reference`) are shown as ranges but never seeded, and tier qualification conditions are never compared. Each seed's `simulation` runs the change as a hypothetical, unsigned superseding proposal that every party signs, using the Universal Paper engine, and records the result.

## Agent flow

1. **Verify.** Check the profile's own fingerprint (`check_fingerprint`). Get the inputs you are entitled to, recompute each one's fingerprint with any Universal Paper engine, and require them to match `inputs` and `inputsRoot`. To trust the statistics, recompute the whole profile (`verify_profile`) instead of reading them.
2. **Extract seeds.** `extract_seeds(profile)` returns the seeds after checking the profile and each seed's shape. Keep only seeds whose `target.agreement` is an agreement you are a party to.
3. **Simulate (optional).** Rebuild the proposal with `seed_proposal(bundle, seed, by=...)` and run it yourself: `simulate_seed`, the MCP tools `simulate_events` or `simulate_amendment` (if you act under a Mandate, which also checks its bounds), or your own engine.
4. **Evaluate.** Decide with your own policy whether to propose anything. If you do, sign the `propose` event with your own keys and send it to the other parties like any other Universal Paper event. The other parties' engines decide whether it is valid.

The [MCP server](../../README.md#mcp-server-for-agents) tools that help: `hash_object`, `validate_bundle`, `derive_state`, `simulate_events`, `simulate_amendment`.

## Code

A reference helper, [examples/integrations/fingerprint-coordination/up_fpc.py](../../examples/integrations/fingerprint-coordination/up_fpc.py). It reuses the Universal Paper package's canonicalization, fingerprints and engine unchanged. No network, no storage, no machine learning; the same inputs give the same bytes.

```python
import json, sys
sys.path.insert(0, "examples/integrations/fingerprint-coordination")
import up_fpc

bundles = [{"label": n, "source": f"examples/{n}/bundle.json", "disclosure": "parameters",
            "data": json.load(open(f"examples/{n}/bundle.json"))} for n in ("conventional", "generative", "overlay", "what-if")]
profile = up_fpc.derive_profile(bundles, minimum_cohort=3)
up_fpc.verify_profile(profile, bundles)["ok"]          # True: recomputed, same fingerprint
seed = up_fpc.extract_seeds(profile)[0]
event = up_fpc.seed_proposal(bundles[1]["data"], seed, by="supplier")   # unsigned; review, then sign
```

| Function | Does |
|---|---|
| `fingerprint(obj)` | The Universal Paper fingerprint, unchanged |
| `with_fingerprint(obj)` / `check_fingerprint(obj)` | Set or check an object's own `fingerprint` member |
| `inputs_root(fingerprints)` | One fingerprint for a set of inputs |
| `contribution(...)` | A FingerprintContribution |
| `agreements(bundle)` | Each chain's agreement in force, with its proposal history and engine outcomes |
| `diff_agreements(a, b)` / `diff_bundles(a, b)` | Structural diff: clauses added or removed, parameters changed ([example](../../examples/integrations/fingerprint-coordination/structural-diff.json)) |
| `derive_profile(inputs, ...)` | A DerivedProfile |
| `verify_profile(profile, inputs)` | Recompute and compare |
| `extract_seeds(profile)` | The seeds, shape-checked |
| `seed_proposal(bundle, seed, by=...)` | The unsigned `propose` event a seed describes |
| `simulate_seed(bundle, seed, ...)` | New agreement fingerprint, engine verdict and obligation delta |

`python3 examples/integrations/fingerprint-coordination/regenerate.py --check` rebuilds the demo profile, the example contribution, the structural diff and the demo's embedded copy from the public bundles, and fails if any has drifted. A machine-readable summary of this integration (helper functions and signatures, claim shapes as JSON Schema, example URLs and MCP tools) is at [universalpaper.org/integrations/index.json](https://universalpaper.org/integrations/index.json).

## Where profiles can live

Anywhere bytes can be fetched and hashed: an HTTPS URL pinned by the profile's fingerprint, a file in a repository, IPFS (content-addressed already) or Arweave. A host is only transport; the fingerprint is the check. Enrichers (a BI tool, a spreadsheet, an agent's own models) may read profiles and produce their own; anything they derive should list its inputs and carry its own fingerprint the same way. These are options, not endorsements, and Universal Paper gives none of them special status.

## What we are not sure about

The seed rules are deliberately simple and the demo corpus is tiny and hypothetical; with real data, cohorts need more care than "same Roles". Re-identification risk grows as cohorts shrink, so `minimumCohort` is a floor, not a guarantee; parties pooling sensitive data should agree stronger rules among themselves. The shapes are a suggestion at version 0.1. If a shared vocabulary for agreement analytics emerges, this page should point to it. Universal Paper does not change.

---

*Optional integration documentation by Uppercentile, CC BY 4.0. The helper and demo are Apache-2.0 and the example data CC0 1.0, like the rest of the repository. Uppercentile does not operate any pooling, analytics or hosting service for this convention.*
