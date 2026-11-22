# UP:Fee-Disclosure — Fee disclosure

**Family:** Fees · **Spec:** `UP/0.1-draft` · **Machine definition:** [`UP-Fee-Disclosure.json`](UP-Fee-Disclosure.json)

Requires the aggregator to disclose to the member, each period, the administrative fees it received from the supplier under the parent Agreement.

## Parameters

| Name | Type | Meaning |
|---|---|---|
| `period` | `Period` | Disclosure period. |
| `due` | `Period` | Time after each period's end by which the disclosure is due. |

No parameter has a default value (A6).

## Machine definition

```json
[
  {
    "form": "Duty",
    "duty": "disclose",
    "obligor": "aggregator",
    "obligee": "member",
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
      "claim": "UP:Fee-Disclosure/disclosed"
    }
  }
]
```

## Claims

| Claim type | Data | Meaning |
|---|---|---|
| `UP:Fee-Disclosure/disclosed` | `{"period": "{start: Time, end: Time}", "received": "Amount", "basis": "string"}` | The Aggregator states the administrative fees it received from the Supplier for the period under the parent agreement, attributable to this Member where the parent agreement reports by participation. |

## Human rendering

```text
For each period of {{period|period}}, the Aggregator discloses to the Member, in writing, the amount of administrative fees it received from the Supplier under the parent agreement for that period, within {{due|period}} after the period ends. This clause records a disclosure process. It makes no statement about whether any arrangement satisfies any law.
```

## Provenance

Drafted by: Universal Paper v0 working draft (publisher name pending open question 2). Reviewed by: none yet. Initial draft. Not yet reviewed by counsel from any segment.
