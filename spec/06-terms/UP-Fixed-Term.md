# UP:Fixed-Term — Term of agreement

**Family:** Term and renewal · **Spec:** `UP/0.1-draft` · **Machine definition:** [`UP-Fixed-Term.json`](UP-Fixed-Term.json)

Sets when the Agreement is in force, with no renewal.

## Parameters

| Name | Type | Meaning |
|---|---|---|
| `start` | `Time` | First instant the Agreement is in force. |
| `end` | `Time` | First instant the Agreement is no longer in force. |

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
    }
  }
]
```

## Claims

None.

## Human rendering

```text
This Agreement is in force from {{start|time}} until {{end|time}}.
```

## Provenance

Drafted by: Universal Paper v0 working draft (publisher name pending open question 2). Reviewed by: none yet. Initial draft. Not yet reviewed by counsel from any segment.
