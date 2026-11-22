# UP:Renewing-Term — Term of agreement with renewal

**Family:** Term and renewal · **Spec:** `UP/0.1-draft` · **Machine definition:** [`UP-Renewing-Term.json`](UP-Renewing-Term.json)

Sets an initial term that renews automatically unless a named role opts out by notice.

## Parameters

| Name | Type | Meaning |
|---|---|---|
| `start` | `Time` | First instant in force. |
| `end` | `Time` | End of the initial term. |
| `renewal_period` | `Period` | Length of each renewal. |
| `max_renewals` | `int` | Maximum number of renewals. |
| `optout_roles` | `[Role]` | Roles that may prevent the next renewal. |
| `optout_notice` | `Period` | How long before a term ends an opt-out notice must be given. |

No parameter has a default value (A6).

## Machine definition

```json
[
  {
    "form": "Window",
    "start": {
      "param": "start"
    },
    "end": {
      "param": "end"
    },
    "renew": {
      "period": {
        "param": "renewal_period"
      },
      "max": {
        "param": "max_renewals"
      },
      "optout_roles": {
        "param": "optout_roles"
      },
      "optout_notice": {
        "param": "optout_notice"
      }
    }
  }
]
```

## Claims

| Claim type | Data | Meaning |
|---|---|---|
| `UP:Renewing-Term/optout` | `{}` | Notice that the Agreement will not renew at the end of the current term. |

## Human rendering

```text
This Agreement is in force from {{start|time}} until {{end|time}}. It then renews for successive periods of {{renewal_period|period}}, up to {{max_renewals}} times, unless {{optout_roles|role}} gives notice of non-renewal at least {{optout_notice|period}} before the end of the then-current term.
```

## Provenance

Drafted by: Universal Paper v0 working draft (publisher name pending open question 2). Reviewed by: none yet. Initial draft. Not yet reviewed by counsel from any segment.
