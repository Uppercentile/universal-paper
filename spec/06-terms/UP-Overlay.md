# UP:Overlay — Overlay of an existing agreement

**Family:** General · **Spec:** `UP/0.1-draft` · **Machine definition:** [`UP-Overlay.json`](UP-Overlay.json)

Declares that this Agreement describes an existing contract, identified by the hash of its document, without amending or replacing it.

## Parameters

| Name | Type | Meaning |
|---|---|---|
| `document` | `Hash` | SHA-256 hash of the existing contract document, as the parties hold it. |
| `document_title` | `string` | Title of the existing contract. Sealable. |
| `document_date` | `Time` | Date the existing contract was signed. |
| `governs` | `"document" | "this-record"` | Which text controls if this record and the existing contract are inconsistent. |

No parameter has a default value (A6).

## Machine definition

No clause forms. This Term has legal meaning only: it changes no State and produces no Commitments.

## Claims

None.

## Human rendering

```text
This record describes the agreement titled {{document_title}}, signed on {{document_date|time}}, whose document has the hash {{document}}. It does not amend or replace that agreement. If this record and that agreement are inconsistent, {{governs|governs}} controls.
```

## Provenance

Drafted by: Universal Paper v0 working draft (publisher name pending open question 2). Reviewed by: none yet. Initial draft. Not yet reviewed by counsel from any segment.
