# LCP reference adapter (optional)

> **Optional external integration, not part of the Universal Paper language.** Universal Paper works without it. This is a reference adapter for publishing and verifying Universal Paper artifacts through the [Legal Context Protocol](https://legalcontextprotocol.org/) (LCP). Full explanation: [docs/integrations/legal-context-protocol.md](../../docs/integrations/legal-context-protocol.md).

One file, [`up_lcp.py`](up_lcp.py). It needs the `universal-paper` package (for its canonicalization and, optionally, its engine) and nothing else beyond the standard library. It adds no hashing of its own: LCP's `atrHash` is the Universal Paper fingerprint of the published artifact, because the published bytes are the artifact's canonical JSON.

Copy it into your project, or use it from a clone:

```sh
pip install universal-paper          # or: pip install -e . from a clone
PYTHONPATH=integrations/lcp python3 -c "import up_lcp; print(up_lcp.to_atr_hash('sha256:' + 'ab'*32))"
```

| Function | Does |
|---|---|
| `fingerprint(obj)`, `canonical_bytes(obj)` | The UP fingerprint, and the exact bytes to publish so their SHA-256 equals it |
| `to_atr_hash`, `to_up_fingerprint`, `same_hash` | `sha256:<hex>` and `0x<hex>`, compared by bytes |
| `legal_context(url, artifact, acceptance_required=None)` | A minimal `legal-context.json` pinned to the artifact |
| `verify(lcp, bytes, expected_fingerprint=None)` | LCP hash check plus canonical-form check |
| `discover(domain)`, `fetch(url)` | HTTPS GETs |
| `evaluate(bundle)`, `check_mandate(bundle, event)` | The reference engine and simulator, unchanged |

Runnable examples: [examples/integrations/lcp/](../../examples/integrations/lcp/). Tests: [tests/test_integration_lcp.py](../../tests/test_integration_lcp.py).

Code: Apache-2.0, like the rest of the repository.
