# UP:Termination-Convenience — Termination for convenience

**Family:** Termination · **Spec:** `UP/0.1-draft` · **Machine definition:** [`UP-Termination-Convenience.json`](UP-Termination-Convenience.json)

Lets a named role end the Agreement without cause, by notice.

## Parameters

| Name | Type | Meaning |
|---|---|---|
| `holders` | `[Role]` | Roles that may terminate. |
| `notice` | `Period` | Time from notice to termination. |

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
    }
  }
]
```

## Claims

| Claim type | Data | Meaning |
|---|---|---|
| `UP:Termination-Convenience/notice` | `{}` | Notice of termination. |

## Human rendering

```text
{{holders|role}} may terminate this Agreement without cause by notice. Termination takes effect {{notice|period}} after the notice is given.
```

## Provenance

Drafted by: Universal Paper v0 working draft (publisher name pending open question 2). Reviewed by: none yet. Initial draft. Not yet reviewed by counsel from any segment.
