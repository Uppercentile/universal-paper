# Verifiable Credentials worked examples (optional)

> **Optional external convention.** These examples are not needed to understand or use Universal Paper. Universal Paper does not issue, verify, require or process Verifiable Credentials. They show the optional path described in [docs/integrations/verifiable-credentials.md](../../../docs/integrations/verifiable-credentials.md). All parties and values are hypothetical.

Two unsigned [W3C Verifiable Credential](https://www.w3.org/TR/vc-data-model-2.0/) payloads. Both reference the fingerprint of the [conventional example](../../conventional/bundle.json) bundle, `sha256:93ab686a4b85a5670a056ccfd7d7f5c5d1cfaa5a2184f6e03e48961b726abcae`, which you can recompute with `up hash examples/conventional/bundle.json`.

| File | Says | Issued by (hypothetical) |
|---|---|---|
| [roster-participation.json](roster-participation.json) | Member `HIN HYP000001` had participation status `active` under that bundle as of 2027-04-20 | the aggregator |
| [role-proof.json](role-proof.json) | Agent `did:example:purchasing-agent-01` holds the role `purchasing-agent` with respect to that bundle | the member |

They contain identity, participation status and role only. No prices, fees, limits or Mandates.

## roster-participation.json

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

## role-proof.json

```json
{
  "@context": ["https://www.w3.org/ns/credentials/v2"],
  "type": ["VerifiableCredential", "RoleCredential"],
  "issuer": "did:example:hypothetical-community-hospital",
  "validFrom": "2027-04-20T12:00:00Z",
  "validUntil": "2027-07-20T12:00:00Z",
  "credentialSubject": {
    "id": "did:example:purchasing-agent-01",
    "agreementFingerprint": "sha256:93ab686a4b85a5670a056ccfd7d7f5c5d1cfaa5a2184f6e03e48961b726abcae",
    "role": "purchasing-agent"
  }
}
```

## Extracting the fingerprint

It is `credentialSubject.agreementFingerprint`. With the payload-shape helper [up_vc.py](up_vc.py) (standard library only):

```python
import json, sys
sys.path.insert(0, "examples/integrations/vc")
import up_vc

claims = up_vc.extract(json.load(open("examples/integrations/vc/roster-participation.json")))
claims["agreementFingerprint"]   # 'sha256:93ab686a…abcae'
claims["participantId"]          # 'HYP000001'
claims["participantStatus"]      # 'active'  (a snapshot: see below)
```

`up_vc.roster_participation(...)` and `up_vc.role_proof(...)` build the same unsigned shapes. The helper does not sign, issue or verify anything.

## Verifying the proof

These payloads are unsigned. An issuer adds a proof, and a verifier checks it, with any standard VC library, for example Digital Bazaar's `vc` (JavaScript), Veramo (TypeScript), SpruceID `ssi` (Rust) or walt.id (Kotlin), using Data Integrity or VC-JOSE-COSE. These are pointers, not endorsements.

## Snapshot, not status

A verified credential tells you what its issuer said at one time. It does not tell you what the agreement says now. The authoritative answer to "is this member an active participant, so the terms and prices apply?" comes from a Universal Paper engine evaluating the artifact the fingerprint names:

```sh
up hash examples/conventional/bundle.json          # must equal agreementFingerprint
python3 -c "import json; from universal_paper import whatif; \
print(whatif.simulate_eligibility(json.load(open('examples/conventional/bundle.json')), 'HYP000001')['reason'])"
```

or the `simulate_eligibility` tool of the [MCP server](../../../README.md#mcp-server-for-agents). If the engine and the credential disagree, the engine is right.

Examples: CC0 1.0, like everything in `examples/`. Helper: Apache-2.0.
