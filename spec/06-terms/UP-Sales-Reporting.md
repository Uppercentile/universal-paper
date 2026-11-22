# UP:Sales-Reporting — Sales reporting

**Family:** Reporting · **Spec:** `UP/0.1-draft` · **Machine definition:** [`UP-Sales-Reporting.json`](UP-Sales-Reporting.json)

Requires a role to report sales made under the Agreement each period, by a deadline.

## Parameters

| Name | Type | Meaning |
|---|---|---|
| `reporter` | `Role` | Role that reports. |
| `recipient` | `Role` | Role that receives the report. |
| `period` | `Period` | Reporting period. |
| `due` | `Period` | Time after each period's end by which the report is due. |

No parameter has a default value (A6).

## Machine definition

```json
[
  {
    "form": "Duty",
    "duty": "report",
    "obligor": {
      "param": "reporter"
    },
    "obligee": {
      "param": "recipient"
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
      "claim": "UP:Sales-Reporting/report"
    }
  }
]
```

## Claims

| Claim type | Data | Meaning |
|---|---|---|
| `UP:Sales-Reporting/report` | `{"period": "{start: Time, end: Time}", "lines": "[{participation: ChainId, item: Identifier, quantity: Decimal, net: Amount}]", "total_net": "Amount"}` | Sales for one period, by participation and Item, with the total net sales. |

## Human rendering

```text
{{reporter|role}} reports to {{recipient|role}} the sales made under this Agreement in each reporting period of {{period|period}}, by Member participation and Item, within {{due|period}} after the period ends.
```

## Provenance

Drafted by: Universal Paper v0 working draft (publisher name pending open question 2). Reviewed by: none yet. Initial draft. Not yet reviewed by counsel from any segment.
