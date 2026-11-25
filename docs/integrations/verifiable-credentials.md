# Verifiable Credentials (optional integration)

> **Optional external convention.** Universal Paper is a self-contained language for computable agreements. It does not depend on Verifiable Credentials. Universal Paper does not issue, verify, require or process them. This page describes an optional convention that agents and counterparties may use for roster, participation and role proofs.

Nothing here changes the Universal Paper language, its schemas, its fingerprint rules, its Terms or its engines. You can ignore this page entirely and lose nothing.

## Purpose

GPO rosters move between aggregators, suppliers, distributors and members all the time, and agents increasingly need to show who they act for. A [W3C Verifiable Credential](https://www.w3.org/TR/vc-data-model-2.0/) (VC) is a widely supported way to carry a short, signed statement. This convention keeps that statement narrow: **a Universal Paper fingerprint plus a simple claim about who is an active participant, or what role someone holds.**

The fingerprint names exactly which agreement artifact the claim is about. Any party can fetch that artifact and evaluate it themselves.

## What this is, and what it is not

| This is | This is not |
|---|---|
| A signed snapshot: "issuer X said, at time T, that participant P had participation status S under the artifact with fingerprint F" | The participation status itself. Status comes from evaluating the agreement with a Universal Paper engine (e.g. `simulate_eligibility`) |
| A role label an issuer assigns to an agent or user, with respect to an artifact | A Universal Paper Role (`aggregator`, `supplier`, `member`…) or a Mandate. A VC grants no authority inside Universal Paper: who may sign which Event is decided only by party keys and Mandates (axiom A9) |
| A convention using standard VC fields plus three claims: `agreementFingerprint`, `participant`/`participantStatus`/`eligibleAsOf`, or `role` | A new Universal Paper field, Term, primitive, rule or hash |
| A payload-shape helper and two static examples | An issuer, verifier, wallet, registry, status service or application. None is offered or implied |

**A VC is only a snapshot.** It can be stale the moment after it is signed: a participation can be terminated, an agreement amended or expired. It never replaces engine evaluation. When the question is "do these terms and contract prices apply to this member now?", the answer is the result of running a Universal Paper engine over the artifact, not the credential.

## Example payload

An aggregator's unsigned snapshot that member `HIN HYP000001` was an active participant under the [conventional example](../../examples/conventional/bundle.json) bundle:

```json
{
  "@context": ["https://www.w3.org/ns/credentials/v2"],
  "type": ["VerifiableCredential", "ParticipationStatusCredential"],
  "issuer": "did:example:hypothetical-health-purchasing-alliance",
  "validFrom": "2027-04-20T12:00:00Z",
  "validUntil": "2027-05-20T12:00:00Z",
  "credentialSubject": {
    "agreementFingerprint": "sha256:93ab686a4b85a5670a056ccfd7d7f5c5d1cfaa5a2184f6e03e48961b726abcae",
    "participant": { "scheme": "HIN", "id": "HYP000001" },
    "participantStatus": "active",
    "eligibleAsOf": "2027-04-20T12:00:00Z"
  }
}
```

- `agreementFingerprint` is a Universal Paper fingerprint, `"sha256:" + hex(SHA-256(JCS(strip(o))))` exactly as in [spec/01-domain.md §1](../../spec/01-domain.md). Here it is the bundle's (`up hash examples/conventional/bundle.json`). A bundle is the recommended reference, because a verifier can evaluate it on its own.
- `participant` uses the same `{scheme, id}` shape as a Universal Paper Identifier, so its `id` can be passed straight to `simulate_eligibility`.
- `participantStatus` is `active` or `inactive`. `eligibleAsOf` is the time the issuer evaluated it.
- `validFrom` and `validUntil` are standard VC fields. Keep the window short; it bounds how long anyone should rely on the snapshot, not how long the participation lasts.
- The `type` names and claim names are issuer-defined terms, which VC Data Model 2.0 allows through its base context. Issuers who want stricter JSON-LD can publish their own context. Nothing in Universal Paper reads these names.

A role proof has the same envelope with `"type": ["VerifiableCredential", "RoleCredential"]` and a subject of `id` (the agent or user), `agreementFingerprint` and `role`, such as `purchasing-agent`, `roster-admin` or `read-only`. Both payloads are in [examples/integrations/vc/](../../examples/integrations/vc/README.md).

## Agent flow

1. **Verify the credential** with any standard VC library: proof, issuer key, validity window and, if the issuer uses one, status list. This step is entirely outside Universal Paper.
2. **Extract** `agreementFingerprint` and the claims (`participant`, `participantStatus`, `eligibleAsOf`, or `role`).
3. **Get and check the artifact.** Obtain the bundle by any channel and recompute its fingerprint with any Universal Paper engine. It must equal `agreementFingerprint`. Validate the bundle.
4. **Evaluate, if status matters.** Run `simulate_eligibility` (reference interpreter, JavaScript engine, [MCP server](../../README.md#mcp-server-for-agents) or your own implementation) for the participant at the time you care about. If the engine and the credential disagree, the engine is right.
5. **Decide** using your own policy: whether you trust that issuer for that claim, and what a role label lets that agent do in your systems.

## Code

A payload-shape helper, [examples/integrations/vc/up_vc.py](../../examples/integrations/vc/up_vc.py), standard library only. It builds the two unsigned shapes and reads them back. It has no signature suites, no issuance and no verification logic.

```python
import up_vc   # from examples/integrations/vc/

vc = up_vc.roster_participation(
    issuer="did:example:hypothetical-health-purchasing-alliance",
    agreement_fingerprint="sha256:93ab686a4b85a5670a056ccfd7d7f5c5d1cfaa5a2184f6e03e48961b726abcae",
    participant_scheme="HIN", participant_id="HYP000001",
    participant_status="active", eligible_as_of="2027-04-20T12:00:00Z")
# ...sign with your VC library, send, verify with your VC library, then:
claims = up_vc.extract(vc)
claims["agreementFingerprint"], claims["participantId"], claims["participantStatus"]
```

| Function | Does |
|---|---|
| `roster_participation(...)` | An unsigned `ParticipationStatusCredential` payload |
| `role_proof(...)` | An unsigned `RoleCredential` payload |
| `extract(vc)` | The fingerprint and basic claims from either shape. Checks the shape only, never the proof |

A machine-readable summary of this integration (helper functions and signatures, claim shapes as JSON Schema, example URLs and the MCP tools to evaluate with) is at [universalpaper.org/integrations/index.json](https://universalpaper.org/integrations/index.json).

## Not the only way

Rosters and authority are already exchanged many ways: roster files and EDI between aggregators, suppliers and distributors, identifiers such as HIN and GLN, signed Universal Paper participation agreements themselves, Mandates, API tokens, or a phone call. All are equally valid alongside Universal Paper. A Verifiable Credential is one portable, widely implemented option. Universal Paper gives it no special status.

## What we are not sure about

This page relies only on the core fields of the [W3C VC Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/) (`@context`, `type`, `issuer`, `validFrom`, `validUntil`, `credentialSubject`) as of November 2026. The claim names are a suggestion, not a registered vocabulary. If a shared vocabulary for roster or participation claims emerges, this page should point to it. Universal Paper does not change.

---

*Optional integration documentation by Uppercentile, CC BY 4.0. The helper and examples are Apache-2.0 and CC0 1.0 like the rest of the repository. The VC Data Model is maintained by the W3C. This page does not speak for it.*
