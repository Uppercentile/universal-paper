# UP:Participation — Participation in an aggregator agreement

**Family:** Parties and participation · **Spec:** `UP/0.1-draft` · **Machine definition:** [`UP-Participation.json`](UP-Participation.json)

Makes this Agreement a participation under a parent Agreement, binding the parent's aggregator and supplier as signers.

## Parameters

| Name | Type | Meaning |
|---|---|---|
| `parent` | `ChainId` | The chain of the parent Agreement. |

No parameter has a default value (A6).

## Machine definition

```json
[
  {
    "form": "Link",
    "parent": {
      "param": "parent"
    },
    "bind": [
      "aggregator",
      "supplier"
    ]
  }
]
```

## Claims

None.

## Human rendering

```text
This Agreement is a participation under the agreement identified by {{parent}}. The Aggregator and the Supplier of that agreement are parties to this one in the same roles. This Agreement is in force only while that agreement is in force.
```

## Provenance

Drafted by: Universal Paper v0 working draft (publisher name pending open question 2). Reviewed by: none yet. Initial draft. Not yet reviewed by counsel from any segment.
