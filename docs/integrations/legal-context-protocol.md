# Legal Context Protocol (optional integration)

> **Optional external integration.** Universal Paper is a self-contained language for computable agreements. It does not depend on the Legal Context Protocol or any other discovery or binding layer. This page describes an optional integration path that agents may use for higher-confidence discovery and transaction binding.

Nothing here changes the Universal Paper language, its schemas, its fingerprint rules, its Terms or its engines. You can ignore this page entirely and lose nothing.

## What this is, and what it is not

| This is | This is not |
|---|---|
| A way to publish a Universal Paper artifact where any agent can find it, using LCP's `/.well-known/legal-context.json` | A new Universal Paper field, Term, primitive or rule |
| A mapping: LCP's `atrHash` **is** the Universal Paper fingerprint of the published artifact | A new hash or canonicalization. It reuses [spec/01-domain.md §1](../../spec/01-domain.md) exactly |
| A small reference adapter and two runnable examples | A required, preferred or endorsed binding mechanism |
| A pointer to the LCP specification | A restatement or redefinition of LCP |

## The mapping

[LCP](https://legalcontextprotocol.org/) ([source](https://github.com/legal-context-protocol/legal-context-protocol)) is a draft open standard (v1.0, Apache-2.0, released for community review) for publishing legal terms at `https://{domain}/.well-known/legal-context.json`. Its only required field is `terms`, a URL to a standalone terms document. At its "Provable" level it adds `atrHash`: the SHA-256 of that document's bytes, written as `0x` and 64 hex digits. See the LCP [standard](https://legalcontextprotocol.org/standard), [schema](https://legalcontextprotocol.org/standard/schema) and [Level 2: Provable](https://legalcontextprotocol.org/levels/provable).

A Universal Paper fingerprint is `"sha256:" + hex(SHA-256(JCS(strip(o))))`: the SHA-256 of the object's canonical JSON, leaving out top-level `sigs`.

So: **publish the artifact as its canonical JSON bytes, and the two hashes are the same 32 bytes.**

```json
{
  "terms": "https://universalpaper.org/examples/integrations/lcp/conventional/terms.up.json",
  "termsFormat": "json",
  "atrHash": "0x93ab686a4b85a5670a056ccfd7d7f5c5d1cfaa5a2184f6e03e48961b726abcae"
}
```

Here `atrHash` is the fingerprint `sha256:93ab686a…abcae` of the [conventional example](../../examples/conventional/bundle.json) bundle, and `terms` serves exactly the bytes that hash to it. Every field used above is defined by LCP. Nothing is added to either format.

What to publish:

| Artifact | Its fingerprint | Good for |
|---|---|---|
| **Bundle** (recommended) | the bundle's hash | Self-contained: Terms, agreements, events and Mandates, so any engine can evaluate it. A new event makes a new bundle and a new hash: update `atrHash`, as LCP expects when terms change. |
| Agreement | the agreement's hash | The terms alone. Stable until amended, but not evaluable without its chain. |
| Term definition | the Term's `def` hash | Publishing a library Term on its own. |

Events and Mandates carry top-level `sigs`, which their fingerprint leaves out, so no single file can both carry the signatures and hash to the fingerprint. Publish them inside a Bundle. The adapter refuses them.

## Agent flow

1. **Discover.** GET `https://{domain}/.well-known/legal-context.json` and read `terms` and `atrHash`.
2. **Fetch.** GET the `terms` URL and keep the raw bytes. Do not re-serialize them.
3. **Verify the fingerprint.** SHA-256 of the bytes must equal `atrHash` (compare decoded bytes, as LCP requires). Then check the bytes are canonical Universal Paper JSON, so the same hash is the artifact's fingerprint. If a counterparty gave you a fingerprint, compare it too.
4. **Evaluate with any Universal Paper engine.** Validate the bundle, then derive statuses, tiers, prices and obligations. The reference interpreter, the JavaScript engine, the [MCP server](../../README.md#mcp-server-for-agents) or your own implementation all give the same answer.
5. **Optionally check your Mandate.** If you act for a party under a Mandate, dry-run your intended event first. Mandate coverage (axiom A9) is checked exactly as for a signed event.

Record `atrHash` with the transaction. LCP treats the hash in a transaction record as the terms that governed it. In Universal Paper the same 32 bytes name the bundle you evaluated, and the ChainIds inside it name the agreements across amendments.

## Code

The reference adapter is one file, [integrations/lcp/up_lcp.py](../../integrations/lcp/up_lcp.py). It uses the interpreter's own canonicalization and the standard library.

```python
import json, up_lcp

# Publisher: pin a bundle.
bundle = json.load(open("examples/conventional/bundle.json"))
open("terms.up.json", "wb").write(up_lcp.canonical_bytes(bundle))          # serve these bytes exactly
lcp = up_lcp.legal_context("https://example.org/terms.up.json", bundle)    # serve at /.well-known/legal-context.json

# Agent: verify, then evaluate.
v = up_lcp.verify(lcp, up_lcp.fetch(lcp["terms"]))
assert v.ok, v.problems                     # atrHash matches, canonical, so atrHash is the UP fingerprint
result = up_lcp.evaluate(v.artifact)        # the reference engine, unchanged
```

| Function | Does |
|---|---|
| `fingerprint(obj)` | The Universal Paper fingerprint (`sha256:…`) of a Bundle, Agreement, State or Term |
| `canonical_bytes(obj)` | The bytes to publish, so their SHA-256 is the fingerprint |
| `to_atr_hash`, `to_up_fingerprint`, `same_hash` | Convert between `sha256:<hex>` and `0x<hex>`, compare by bytes |
| `legal_context(url, artifact, acceptance_required=None)` | A minimal LCP discovery document pinned to the artifact |
| `verify(lcp, bytes, expected_fingerprint=None)` | The LCP hash check, the canonical-form check, and an optional expected fingerprint |
| `discover(domain)`, `fetch(url)` | HTTPS GETs for the discovery file and the terms |
| `evaluate(bundle)` | Validation and derived state from the reference interpreter |
| `check_mandate(bundle, event)` | Whether an agent's hypothetical event is inside its Mandate, from the reference simulator |

Worked examples: [examples/integrations/lcp/](../../examples/integrations/lcp/README.md). Run `python3 examples/integrations/lcp/agent.py` from the repository root (add `--online` to fetch the same files from universalpaper.org).

## Serving notes

- Serve `terms` byte for byte: no pretty-printing, no added newline, no templating. `Content-Type: application/json`. HTTP compression is fine, since the decoded bytes are unchanged.
- `termsFormat: "json"` is one of LCP's known values. LCP allows implementations to define more values; this integration does not.
- `legal-context.json` is public, and so is anything it points at. Publishing a bundle publishes everything in it that is not sealed. For confidential agreements, publish the hashes-only form (its fingerprint differs from the full bundle's, but evaluators reach the same verdicts and state hashes; see the [confidential example](../../examples/confidential/bundle.hashes-only.json)) or use LCP's own [private and custom terms](https://legalcontextprotocol.org/private-terms) pattern.
- LCP's signed acceptance (its Level 3, for example EIP-712 or JWS) is separate from Universal Paper's signed `accept` Events. Universal Paper does not read LCP signatures, and LCP does not replace a Universal Paper signature. Use either, both or neither.

## Not the only way

Any channel that delivers the bytes and lets the receiver recompute the fingerprint binds a Universal Paper agreement equally well: sending the bundle directly, attaching it to an EDI exchange, content-addressed storage, the MCP server, or a link in an email. LCP is one convenient, well-known place to look. Universal Paper gives it no special status.

## What we are not sure about

LCP is a draft. This page relies only on `terms`, `termsFormat`, `atrHash` and `acceptanceRequired` as the [LCP schema](https://legalcontextprotocol.org/standard/schema) defines them as of November 2026. Field names, levels and URLs may still change before LCP is final. If LCP changes, this page and the adapter change. Universal Paper does not.

---

*Optional integration documentation by Uppercentile, CC BY 4.0. The adapter and examples are Apache-2.0 and CC0 1.0 like the rest of the repository. LCP is maintained by its own stewards. This page does not speak for them.*
