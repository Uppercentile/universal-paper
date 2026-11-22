# UP:Audit — Audit right

**Family:** Audit · **Spec:** `UP/0.1-draft` · **Machine definition:** [`UP-Audit.json`](UP-Audit.json)

Lets a role request an audit of another role's records under the Agreement, a limited number of times per period.

## Parameters

| Name | Type | Meaning |
|---|---|---|
| `auditor` | `Role` | Role that may request an audit. |
| `auditee` | `Role` | Role whose records are audited. |
| `response` | `Period` | Time after a request by which records must be made available. |
| `max_requests` | `int` | Maximum requests per limit period. |
| `per` | `Period` | Limit period. |

No parameter has a default value (A6).

## Machine definition

```json
[
  {
    "form": "Duty",
    "duty": "make-records-available",
    "obligor": {
      "param": "auditee"
    },
    "obligee": {
      "param": "auditor"
    },
    "trigger": {
      "on": "UP:Audit/request",
      "by": [
        {
          "param": "auditor"
        }
      ],
      "limit": {
        "count": {
          "param": "max_requests"
        },
        "per": {
          "param": "per"
        }
      }
    },
    "due": {
      "param": "response"
    },
    "discharge": {
      "claim": "UP:Audit/available",
      "ack": [
        {
          "param": "auditor"
        }
      ]
    }
  }
]
```

## Claims

| Claim type | Data | Meaning |
|---|---|---|
| `UP:Audit/request` | `{"scope": "string", "lookback": "{start: Time, end: Time}"}` | Request for an audit of records within the stated scope and time range. |
| `UP:Audit/available` | `{"request": "Hash"}` | The auditee attests that the requested records are available. Discharges the duty when acknowledged by the auditor. |

## Human rendering

```text
{{auditor|role}} may request an audit of the records of {{auditee|role}} relating to this Agreement, up to {{max_requests}} times per {{per|period}}. {{auditee|role}} makes the requested records available within {{response|period}} of each request.
```

## Provenance

Drafted by: Universal Paper v0 working draft (publisher name pending open question 2). Reviewed by: none yet. Initial draft. Not yet reviewed by counsel from any segment.
