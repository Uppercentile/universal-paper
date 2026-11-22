# UP:Tier-Selection — Tier attestation and selection

**Family:** Tiers and attestation · **Spec:** `UP/0.1-draft` · **Machine definition:** [`UP-Tier-Selection.json`](UP-Tier-Selection.json)

Lets the Member attest that it qualifies for a tier; the selection takes effect when the Supplier acknowledges it.

## Parameters

| Name | Type | Meaning |
|---|---|---|
| `tiers_clause` | `string` | Name of the Tiers clause in the parent Agreement. |
| `initial` | `string` | Tier in effect before any selection. |
| `effective` | `"on-ack" | {next: Period}` | When an acknowledged selection takes effect. |

No parameter has a default value (A6).

## Machine definition

```json
[
  {
    "form": "Selection",
    "options": {
      "from": {
        "link": true,
        "clause": {
          "param": "tiers_clause"
        }
      }
    },
    "subject": "member",
    "ack": [
      "supplier"
    ],
    "effective": {
      "param": "effective"
    },
    "initial": {
      "param": "initial"
    }
  }
]
```

## Claims

| Claim type | Data | Meaning |
|---|---|---|
| `UP:Tier-Selection/selects` | `{"option": "string", "basis": "string"}` | The Member attests that it meets the conditions of the named tier, stating the basis. |

## Human rendering

```text
The Member's tier is {{initial}} until changed under this clause. The Member may attest that it meets the conditions of another tier, stating the basis. The change takes effect when the Supplier acknowledges the attestation, {{effective|effective}}.
```

## Provenance

Drafted by: Universal Paper v0 working draft (publisher name pending open question 2). Reviewed by: none yet. Initial draft. Not yet reviewed by counsel from any segment.
