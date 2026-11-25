# LCP worked examples (optional)

> **Optional external integration.** These examples are not needed to understand or use Universal Paper. They show the optional [Legal Context Protocol](https://legalcontextprotocol.org/) path described in [docs/integrations/legal-context-protocol.md](../../../docs/integrations/legal-context-protocol.md). All parties and values are hypothetical.

| Folder | What it pins | LCP level |
|---|---|---|
| [conventional/](conventional/) | The conventional GPO example bundle: a master agreement and two member participations | 2 (provable: `atrHash`) |
| [mandate-cap/](mandate-cap/) | An agent-run aggregator whose Mandate caps price changes at ±2% | 3 (`acceptanceRequired: true`) |

Each folder has `legal-context.json` (what a publisher serves at `/.well-known/legal-context.json`) and `terms.up.json` (the bundle's canonical bytes, which hash to `atrHash`). Both are also served on universalpaper.org under `/examples/integrations/lcp/`, so the `terms` URLs resolve.

```sh
python3 examples/integrations/lcp/agent.py            # discover, fetch, verify, evaluate, check the Mandate (local files)
python3 examples/integrations/lcp/agent.py --online   # the same, fetched from universalpaper.org
python3 examples/integrations/lcp/publish.py          # regenerate both folders from examples/*/bundle.json
```

The `terms.up.json` files are snapshots pinned by hash. That is deliberate: LCP treats the hash in a transaction record as the governing terms. They are not rebuilt by `examples/build_examples.py`.

Examples: CC0 1.0, like everything in `examples/`.
