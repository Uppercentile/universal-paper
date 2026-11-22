# UP:Termination-Cause — Termination for cause

**Family:** Termination · **Spec:** `UP/0.1-draft` · **Machine definition:** [`UP-Termination-Cause.json`](UP-Termination-Cause.json)

Lets a role end the Agreement after giving notice of a material breach that is not cured in time.

## Parameters

| Name | Type | Meaning |
|---|---|---|
| `holders` | `[Role]` | Roles that may terminate for cause. |
| `cure_period` | `Period` | Time allowed to cure after a breach notice. |
| `notice` | `Period` | Time from termination notice to termination. |

No parameter has a default value (A6).

## Machine definition

```json
[
  {
    "form": "Exit",
    "holders": {
      "param": "holders"
    },
    "notice": {
      "param": "notice"
    },
    "requires": {
      "claim": "UP:Termination-Cause/breach",
      "age": {
        "param": "cure_period"
      },
      "unless": "UP:Termination-Cause/cured"
    }
  }
]
```

## Claims

| Claim type | Data | Meaning |
|---|---|---|
| `UP:Termination-Cause/breach` | `{"description": "string"}` | Notice describing an alleged material breach. |
| `UP:Termination-Cause/cured` | `{"breach": "Hash"}` | Statement that the breach identified by the referenced notice has been cured. Effective only when acknowledged by the party that gave the breach notice. |
| `UP:Termination-Cause/notice` | `{"breach": "Hash"}` | Notice of termination for the referenced, uncured breach. |

## Human rendering

```text
If a party commits a material breach, {{holders|role}} may give notice describing it. If the breach is not cured within {{cure_period|period}} of that notice, {{holders|role}} may terminate this Agreement by further notice, effective {{notice|period}} after that notice. A breach counts as cured only when the party that gave the breach notice acknowledges the cure.
```

## Provenance

Drafted by: Universal Paper v0 working draft (publisher name pending open question 2). Reviewed by: none yet. Initial draft. Not yet reviewed by counsel from any segment.
