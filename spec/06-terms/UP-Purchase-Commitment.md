# UP:Purchase-Commitment — Purchase commitment

**Family:** Compliance · **Spec:** `UP/0.1-draft` · **Machine definition:** [`UP-Purchase-Commitment.json`](UP-Purchase-Commitment.json)

Records a member's commitment to purchase a stated share of its purchases in a stated category under the Agreement, with periodic attestation.

## Parameters

| Name | Type | Meaning |
|---|---|---|
| `category` | `string` | Description of the product category. |
| `share` | `Rate` | Committed share of category purchases. |
| `period` | `Period` | Measurement period. |
| `due` | `Period` | Time after each period's end by which the attestation is due. |

No parameter has a default value (A6).

## Machine definition

```json
[
  {
    "form": "Duty",
    "duty": "attest-compliance",
    "obligor": "member",
    "obligee": "supplier",
    "trigger": {
      "every": {
        "param": "period"
      },
      "anchor": "window-start"
    },
    "due": {
      "param": "due"
    },
    "discharge": {
      "claim": "UP:Purchase-Commitment/met",
      "ack": [
        "supplier"
      ]
    }
  }
]
```

## Claims

| Claim type | Data | Meaning |
|---|---|---|
| `UP:Purchase-Commitment/met` | `{"period": "{start: Time, end: Time}", "basis": "string"}` | The Member attests that it met the committed share for the period. Discharges the duty when acknowledged by the Supplier. |

## Human rendering

```text
The Member commits to purchase under this Agreement at least {{share|rate}} of its purchases of {{category}} in each period of {{period|period}}, and attests whether it met that commitment within {{due|period}} after each period ends.
```

## Provenance

Drafted by: Universal Paper v0 working draft (publisher name pending open question 2). Reviewed by: none yet. Initial draft. Not yet reviewed by counsel from any segment.
