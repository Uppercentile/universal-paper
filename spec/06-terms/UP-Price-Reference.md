# UP:Price-Reference — Price by reference to a price list

**Family:** Pricing reference · **Spec:** `UP/0.1-draft` · **Machine definition:** [`UP-Price-Reference.json`](UP-Price-Reference.json)

Prices Items as a stated factor of a price list that a named role attests.

## Parameters

| Name | Type | Meaning |
|---|---|---|
| `items` | `[Identifier]` | Items in scope. |
| `list_role` | `Role` | Role that attests the reference price list. |
| `factor` | `Decimal` | Multiplier applied to the reference price. |
| `rounding` | `Rounding` | Rounding applied to the result. |

No parameter has a default value (A6).

## Machine definition

```json
[
  {
    "form": "Valuation",
    "items": {
      "param": "items"
    },
    "source": {
      "reference": {
        "claim": "UP:Price-Reference/list",
        "role": {
          "param": "list_role"
        },
        "factor": {
          "param": "factor"
        },
        "rounding": {
          "param": "rounding"
        }
      }
    }
  }
]
```

## Claims

| Claim type | Data | Meaning |
|---|---|---|
| `UP:Price-Reference/list` | `{"effective": "Time", "prices": "[{item: Identifier, price: Amount}]"}` | A reference price list, effective from the stated time. |

## Human rendering

```text
The price of each Item in scope is its price in the most recent reference price list attested by {{list_role|role}} that is effective at the time of purchase, multiplied by {{factor}} and rounded {{rounding|rounding}}.
```

## Provenance

Drafted by: Universal Paper v0 working draft (publisher name pending open question 2). Reviewed by: none yet. Initial draft. Not yet reviewed by counsel from any segment.
