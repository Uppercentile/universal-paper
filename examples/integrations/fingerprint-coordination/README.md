# Fingerprint Coordination worked examples (optional)

> **Optional external convention.** These files are not needed to understand or use Universal Paper. Universal Paper does not operate, require, endorse or depend on any telemetry, analytics, prediction engine, storage platform or visualization. They show the optional analytical convention described in [docs/integrations/fingerprint-coordination.md](../../../docs/integrations/fingerprint-coordination.md).

**Simulated from public examples.** Every input is a hypothetical example bundle already in this repository. Parties, prices and fees are invented. Nothing here is market data, a benchmark or a recommendation.

| File | What it is |
|---|---|
| [demo/index.html](demo/index.html) | The simulated insight demo: variance ranking, variance map, ranges, historical deltas, two seed cards with engine results, and the raw profile beside them. Open it from disk; it makes no network calls and checks the profile's fingerprint in your browser |
| [demo/scenario.json](demo/scenario.json) | The predictive-redline playthrough of `seed-1`, built only from the profile: before/after values, median, both full agreement fingerprints, the engine verdict, the obligation delta and four ordered steps. The demo's step list, animation and HowTo JSON-LD all come from it |
| [demo-profile.json](demo-profile.json) | A Derived Profile of six public bundles (16 agreements) |
| [contribution.json](contribution.json) | A Contribution: one hypothetical aggregator sharing the conventional bundle's fingerprint, with its rules |
| [structural-diff.json](structural-diff.json) | `diff_bundles` from the conventional to the what-if bundle (it adds `UP:Termination-Cause`) |
| [schemas/](schemas/) | JSON Schemas for the Contribution and the Derived Profile |
| [up_fpc.py](up_fpc.py) | The reference helper (Python 3.11+, needs the `universal-paper` package; no network, no storage, no ML) |
| [regenerate.py](regenerate.py) | Rebuilds every file above from `examples/*/bundle.json`; `--check` fails on drift |

```sh
python3 examples/integrations/fingerprint-coordination/regenerate.py --check   # nothing has drifted
python3 examples/integrations/fingerprint-coordination/regenerate.py           # rewrite after the example bundles change
```

## Payloads

Both shapes carry their own `fingerprint`: the Universal Paper fingerprint (`"sha256:" + hex(SHA-256(JCS(...)))`) of every other member. A Contribution names artifacts by fingerprint with a `disclosure` of `fingerprint-only` (the default), `structure` or `parameters`, plus its rules (`purposes`, `minimumCohort`, `attribution`, `outputs`, `sealedValues: "never-counted"`). A Derived Profile lists every input by fingerprint, their `inputsRoot`, the `method` used, and its statistics, deltas and seeds.

The demo shares the confidential example as `bundle.hashes-only.json`: its fee rate and nine tier prices stay sealed and are counted only as `sealed`. Statistics resting on fewer than three distinct inputs (the overlay's own tier prices, the single `UP:Termination-Cause`, `UP:Price-Reference`) are suppressed.

## Verifying

```python
import json, sys
sys.path.insert(0, "examples/integrations/fingerprint-coordination")
import regenerate, up_fpc

profile = json.load(open("examples/integrations/fingerprint-coordination/demo-profile.json"))
up_fpc.check_fingerprint(profile)                                  # True
up_fpc.verify_profile(profile, regenerate.load_inputs())["ok"]     # True: recomputed from the bundles, same fingerprint
```

## From seed to Proposal

The demo has two seeds:

| Seed | Rule | Change | Engine result (hypothetical, all parties sign) |
|---|---|---|---|
| `seed-1` | `toward-median` | generative "Master Y": Admin-Fee `rate` 0.03 → 0.02 (the cohort median) | accepted; the open January fee obligation is recomputed from 26.06 USD to 17.37 USD |
| `seed-2` | `common-clause` | mandate-cap pricing agreement: add `UP:Sales-Reporting` (in 6 of 7 comparable agreements) | accepted; monthly report duties appear, due 2027-02-16 and 2027-03-16 |

An agent that is a party to the target agreement turns a seed into a Proposal like this:

```python
bundle = json.load(open("examples/generative/bundle.json"))
seed = next(s for s in up_fpc.extract_seeds(profile) if s["id"] == "seed-1")
event = up_fpc.seed_proposal(bundle, seed, by="supplier")   # {"chain", "kind": "propose", "by", "at", "body": {agreement, supersedes}}
up_fpc.simulate_seed(bundle, seed)["accepted"]              # True; or use the MCP tools simulate_events / simulate_amendment
# then: review it, sign it with your own keys, and send it to the other parties like any Universal Paper event
```

The seed is only a candidate. The other parties' engines decide whether the signed proposal is valid, and the parties decide whether to accept it.

## Optional hosts

A profile can be served from any HTTPS URL and pinned by its fingerprint, committed to a repository, or put on IPFS or Arweave. The host is transport only; recompute the fingerprint on receipt. These are options, not endorsements. Uppercentile runs no pooling, analytics or hosting service for this convention.

Examples and demo data: CC0 1.0, like everything in `examples/`. Helper, regenerate script and demo page: Apache-2.0.
