# UP:Admin-Fee — Administrative fee

**Family:** Fees · **Spec:** `UP/0.1-draft` · **Machine definition:** [`UP-Admin-Fee.json`](UP-Admin-Fee.json)

Requires a payer role to pay a payee role a fee computed as a stated rate of reported net sales each period.

## Parameters

| Name | Type | Meaning |
|---|---|---|
| `payer` | `Role` | Role that pays the fee. |
| `payee` | `Role` | Role that receives the fee. |
| `rate` | `Rate` | Fee as a fraction of reported net sales. |
| `report_clause` | `Name` | Name of the Sales-Reporting clause whose reports form the base. |
| `period` | `Period` | Fee period. |
| `due` | `Period` | Time after each period's end by which the fee is due. |
| `rounding` | `Rounding` | Rounding applied to each period's fee. |

No parameter has a default value (A6).

## Machine definition

```json
[
  {
    "form": "Duty",
    "duty": "pay",
    "obligor": {
      "param": "payer"
    },
    "obligee": {
      "param": "payee"
    },
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
      "claim": "UP:Admin-Fee/paid",
      "ack": [
        {
          "param": "payee"
        }
      ]
    },
    "amount": {
      "rate": {
        "param": "rate"
      },
      "base": {
        "claim": "UP:Sales-Reporting/report",
        "clause": {
          "param": "report_clause"
        },
        "field": "total_net"
      },
      "rounding": {
        "param": "rounding"
      }
    }
  }
]
```

## Claims

| Claim type | Data | Meaning |
|---|---|---|
| `UP:Admin-Fee/paid` | `{"period": "{start: Time, end: Time}", "amount": "Amount", "reference": "string"}` | The payer attests payment of the fee for the period. Discharges the duty when acknowledged by the payee. |

## Human rendering

```text
For each period of {{period|period}}, {{payer|role}} pays {{payee|role}} an administrative fee equal to {{rate|rate}} of the net sales reported for that period, rounded {{rounding|rounding}}, within {{due|period}} after the period ends. The fee is fixed at that rate for the term of this Agreement unless the Agreement is amended.
```

## Provenance

Drafted by: Universal Paper v0 working draft (publisher name pending open question 2). Reviewed by: none yet. Initial draft. Not yet reviewed by counsel from any segment.
