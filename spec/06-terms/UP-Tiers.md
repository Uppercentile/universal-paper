# UP:Tiers — Tiered price schedule

**Family:** Tiers and pricing · **Spec:** `UP/0.1-draft` · **Machine definition:** [`UP-Tiers.json`](UP-Tiers.json)

Lists named tiers, describes the conditions for each, and sets a price for each Item in each tier.

## Parameters

| Name | Type | Meaning |
|---|---|---|
| `tiers` | `[{name: Name, conditions: string}]` | The tiers, in order, with descriptive qualification conditions. |
| `prices` | `[{item: Identifier, by: {<tier>: Amount}}]` | Price of each Item in each tier. |

No parameter has a default value (A6).

## Machine definition

```json
[
  {
    "form": "Valuation",
    "source": {
      "table": {
        "param": "prices"
      },
      "options": {
        "param": "tiers"
      }
    }
  }
]
```

## Claims

None.

## Human rendering

```text
The following tiers apply. {{#each tiers}}Tier {{name}}: {{conditions}}. {{/each}}The price of each Item in each tier is: {{#each prices}}{{item}}: {{by|amount}}. {{/each}}Whether a Member meets a tier's conditions is established by that Member's attestation and the Supplier's acknowledgment, as set out in the tier selection clause of the Member's participation.
```

## Provenance

Drafted by: Universal Paper v0 working draft (publisher name pending open question 2). Reviewed by: none yet. Initial draft. Not yet reviewed by counsel from any segment.
