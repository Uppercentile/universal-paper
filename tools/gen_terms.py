"""Generate spec/06-terms/*.md and *.json from the Term data below.

The JSON files are the canonical machine definitions. The markdown files are
readable views of the same data. Run: python3 tools/gen_terms.py
"""
import json, pathlib

SPEC = "UP/0.1-draft"
P = lambda n: {"param": n}
OUT = pathlib.Path(__file__).resolve().parent.parent / "spec" / "06-terms"

TERMS = [
 dict(id="UP:Fixed-Term", title="Term of agreement", family="Term and renewal",
  purpose="Sets when the Agreement is in force, with no renewal.",
  params={"start": ("Time", "First instant the Agreement is in force."),
          "end": ("Time", "First instant the Agreement is no longer in force.")},
  forms=[{"form": "Window", "start": P("start"), "end": P("end")}],
  claims={},
  render="This Agreement is in force from {{start|time}} until {{end|time}}."),

 dict(id="UP:Renewing-Term", title="Term of agreement with renewal", family="Term and renewal",
  purpose="Sets an initial term that renews automatically unless a named role opts out by notice.",
  params={"start": ("Time", "First instant in force."),
          "end": ("Time", "End of the initial term."),
          "renewal_period": ("Period", "Length of each renewal."),
          "max_renewals": ("int", "Maximum number of renewals."),
          "optout_roles": ("[Role]", "Roles that may prevent the next renewal."),
          "optout_notice": ("Period", "How long before a term ends an opt-out notice must be given.")},
  forms=[{"form": "Window", "start": P("start"), "end": P("end"),
          "renew": {"period": P("renewal_period"), "max": P("max_renewals"),
                    "optout_roles": P("optout_roles"), "optout_notice": P("optout_notice")}}],
  claims={"optout": ({}, "Notice that the Agreement will not renew at the end of the current term.")},
  render=("This Agreement is in force from {{start|time}} until {{end|time}}. It then renews for successive "
          "periods of {{renewal_period|period}}, up to {{max_renewals}} times, unless {{optout_roles|role}} gives "
          "notice of non-renewal at least {{optout_notice|period}} before the end of the then-current term.")),

 dict(id="UP:Termination-Convenience", title="Termination for convenience", family="Termination",
  purpose="Lets a named role end the Agreement without cause, by notice.",
  params={"holders": ("[Role]", "Roles that may terminate."),
          "notice": ("Period", "Time from notice to termination.")},
  forms=[{"form": "Exit", "holders": P("holders"), "notice": P("notice")}],
  claims={"notice": ({}, "Notice of termination.")},
  render=("{{holders|role}} may terminate this Agreement without cause by notice. Termination takes effect "
          "{{notice|period}} after the notice is given.")),

 dict(id="UP:Termination-Cause", title="Termination for cause", family="Termination",
  purpose="Lets a role end the Agreement after giving notice of a material breach that is not cured in time.",
  params={"holders": ("[Role]", "Roles that may terminate for cause."),
          "cure_period": ("Period", "Time allowed to cure after a breach notice."),
          "notice": ("Period", "Time from termination notice to termination.")},
  forms=[{"form": "Exit", "holders": P("holders"), "notice": P("notice"),
          "requires": {"claim": "UP:Termination-Cause/breach", "age": P("cure_period"),
                       "unless": "UP:Termination-Cause/cured"}}],
  claims={"breach": ({"description": "string"}, "Notice describing an alleged material breach."),
          "cured": ({"breach": "Hash"}, "Statement that the breach identified by the referenced notice has been cured. Effective only when acknowledged by the party that gave the breach notice."),
          "notice": ({"breach": "Hash"}, "Notice of termination for the referenced, uncured breach.")},
  render=("If a party commits a material breach, {{holders|role}} may give notice describing it. If the breach is "
          "not cured within {{cure_period|period}} of that notice, {{holders|role}} may terminate this Agreement by "
          "further notice, effective {{notice|period}} after that notice. A breach counts as cured only when the "
          "party that gave the breach notice acknowledges the cure.")),

 dict(id="UP:Participation", title="Participation in an aggregator agreement", family="Parties and participation",
  purpose="Makes this Agreement a participation under a parent Agreement, binding the parent's aggregator and supplier as signers.",
  params={"parent": ("ChainId", "The chain of the parent Agreement.")},
  forms=[{"form": "Link", "parent": P("parent"), "bind": ["aggregator", "supplier"]}],
  claims={},
  render=("This Agreement is a participation under the agreement identified by {{parent}}. The Aggregator and the "
          "Supplier of that agreement are parties to this one in the same roles. This Agreement is in force only "
          "while that agreement is in force.")),

 dict(id="UP:Tiers", title="Tiered price schedule", family="Tiers and pricing",
  purpose="Lists named tiers, describes the conditions for each, and sets a price for each Item in each tier.",
  params={"tiers": ("[{name: string, conditions: string}]", "The tiers, in order, with descriptive qualification conditions."),
          "prices": ("[{item: Identifier, by: {<tier>: Amount}}]", "Price of each Item in each tier.")},
  forms=[{"form": "Valuation", "source": {"table": P("prices"), "options": P("tiers")}}],
  claims={},
  render=("The following tiers apply. {{#each tiers}}Tier {{name}}: {{conditions}}. {{/each}}"
          "The price of each Item in each tier is: {{#each prices}}{{item}}: {{by|amount}}. {{/each}}"
          "Whether a Member meets a tier's conditions is established by that Member's attestation and the "
          "Supplier's acknowledgment, as set out in the tier selection clause of the Member's participation.")),

 dict(id="UP:Tier-Selection", title="Tier attestation and selection", family="Tiers and attestation",
  purpose="Lets the Member attest that it qualifies for a tier; the selection takes effect when the Supplier acknowledges it.",
  params={"tiers_clause": ("string", "Name of the Tiers clause in the parent Agreement."),
          "initial": ("string", "Tier in effect before any selection."),
          "effective": ("\"on-ack\" | {next: Period}", "When an acknowledged selection takes effect.")},
  forms=[{"form": "Selection", "options": {"from": {"link": True, "clause": P("tiers_clause")}},
          "subject": "member", "ack": ["supplier"], "effective": P("effective"), "initial": P("initial")}],
  claims={"selects": ({"option": "string", "basis": "string"}, "The Member attests that it meets the conditions of the named tier, stating the basis.")},
  render=("The Member's tier is {{initial}} until changed under this clause. The Member may attest that it meets "
          "the conditions of another tier, stating the basis. The change takes effect when the Supplier acknowledges "
          "the attestation, {{effective|effective}}.")),

 dict(id="UP:Price-Reference", title="Price by reference to a price list", family="Pricing reference",
  purpose="Prices Items as a stated factor of a price list that a named role attests.",
  params={"items": ("[Identifier]", "Items in scope."),
          "list_role": ("Role", "Role that attests the reference price list."),
          "factor": ("Decimal", "Multiplier applied to the reference price."),
          "rounding": ("Rounding", "Rounding applied to the result.")},
  forms=[{"form": "Valuation", "items": P("items"),
          "source": {"reference": {"claim": "UP:Price-Reference/list", "role": P("list_role"),
                                   "factor": P("factor"), "rounding": P("rounding")}}}],
  claims={"list": ({"effective": "Time", "prices": "[{item: Identifier, price: Amount}]"}, "A reference price list, effective from the stated time.")},
  render=("The price of each Item in scope is its price in the most recent reference price list attested by "
          "{{list_role|role}} that is effective at the time of purchase, multiplied by {{factor}} and rounded "
          "{{rounding|rounding}}.")),

 dict(id="UP:Sales-Reporting", title="Sales reporting", family="Reporting",
  purpose="Requires a role to report sales made under the Agreement each period, by a deadline.",
  params={"reporter": ("Role", "Role that reports."),
          "recipient": ("Role", "Role that receives the report."),
          "period": ("Period", "Reporting period."),
          "due": ("Period", "Time after each period's end by which the report is due.")},
  forms=[{"form": "Duty", "duty": "report", "obligor": P("reporter"), "obligee": P("recipient"),
          "trigger": {"every": P("period"), "anchor": "window-start"}, "due": P("due"),
          "discharge": {"claim": "UP:Sales-Reporting/report"}}],
  claims={"report": ({"period": "{start: Time, end: Time}",
                      "lines": "[{participation: ChainId, item: Identifier, quantity: Decimal, net: Amount}]",
                      "total_net": "Amount"}, "Sales for one period, by participation and Item, with the total net sales.")},
  render=("{{reporter|role}} reports to {{recipient|role}} the sales made under this Agreement in each reporting "
          "period of {{period|period}}, by Member participation and Item, within {{due|period}} after the period ends.")),

 dict(id="UP:Admin-Fee", title="Administrative fee", family="Fees",
  purpose="Requires a payer role to pay a payee role a fee computed as a stated rate of reported net sales each period.",
  params={"payer": ("Role", "Role that pays the fee."),
          "payee": ("Role", "Role that receives the fee."),
          "rate": ("Rate", "Fee as a fraction of reported net sales."),
          "report_clause": ("string", "Name of the Sales-Reporting clause whose reports form the base."),
          "period": ("Period", "Fee period."),
          "due": ("Period", "Time after each period's end by which the fee is due."),
          "rounding": ("Rounding", "Rounding applied to each period's fee.")},
  forms=[{"form": "Duty", "duty": "pay", "obligor": P("payer"), "obligee": P("payee"),
          "trigger": {"every": P("period"), "anchor": "window-start"}, "due": P("due"),
          "discharge": {"claim": "UP:Admin-Fee/paid", "ack": [P("payee")]},
          "amount": {"rate": P("rate"), "base": {"claim": "UP:Sales-Reporting/report", "clause": P("report_clause"), "field": "total_net"},
                     "rounding": P("rounding")}}],
  claims={"paid": ({"period": "{start: Time, end: Time}", "amount": "Amount", "reference": "string"}, "The payer attests payment of the fee for the period. Discharges the duty when acknowledged by the payee.")},
  render=("For each period of {{period|period}}, {{payer|role}} pays {{payee|role}} an administrative fee equal to "
          "{{rate|rate}} of the net sales reported for that period, rounded {{rounding|rounding}}, within "
          "{{due|period}} after the period ends. The fee is fixed at that rate for the term of this Agreement unless "
          "the Agreement is amended.")),

 dict(id="UP:Fee-Disclosure", title="Fee disclosure", family="Fees",
  purpose="Requires the aggregator to disclose to the member, each period, the administrative fees it received from the supplier under the parent Agreement.",
  params={"period": ("Period", "Disclosure period."),
          "due": ("Period", "Time after each period's end by which the disclosure is due.")},
  forms=[{"form": "Duty", "duty": "disclose", "obligor": "aggregator", "obligee": "member",
          "trigger": {"every": P("period"), "anchor": "window-start"}, "due": P("due"),
          "discharge": {"claim": "UP:Fee-Disclosure/disclosed"}}],
  claims={"disclosed": ({"period": "{start: Time, end: Time}", "received": "Amount", "basis": "string"}, "The Aggregator states the administrative fees it received from the Supplier for the period under the parent agreement, attributable to this Member where the parent agreement reports by participation.")},
  render=("For each period of {{period|period}}, the Aggregator discloses to the Member, in writing, the amount of "
          "administrative fees it received from the Supplier under the parent agreement for that period, within "
          "{{due|period}} after the period ends. This clause records a disclosure process. It makes no statement "
          "about whether any arrangement satisfies any law.")),

 dict(id="UP:Audit", title="Audit right", family="Audit",
  purpose="Lets a role request an audit of another role's records under the Agreement, a limited number of times per period.",
  params={"auditor": ("Role", "Role that may request an audit."),
          "auditee": ("Role", "Role whose records are audited."),
          "response": ("Period", "Time after a request by which records must be made available."),
          "max_requests": ("int", "Maximum requests per limit period."),
          "per": ("Period", "Limit period.")},
  forms=[{"form": "Duty", "duty": "make-records-available", "obligor": P("auditee"), "obligee": P("auditor"),
          "trigger": {"on": "UP:Audit/request", "by": [P("auditor")], "limit": {"count": P("max_requests"), "per": P("per")}},
          "due": P("response"), "discharge": {"claim": "UP:Audit/available", "ack": [P("auditor")]}}],
  claims={"request": ({"scope": "string", "lookback": "{start: Time, end: Time}"}, "Request for an audit of records within the stated scope and time range."),
          "available": ({"request": "Hash"}, "The auditee attests that the requested records are available. Discharges the duty when acknowledged by the auditor.")},
  render=("{{auditor|role}} may request an audit of the records of {{auditee|role}} relating to this Agreement. The "
          "number of audit requests may not exceed {{max_requests}} in any period of {{per|period}}. {{auditee|role}} "
          "makes the requested records available within {{response|period}} of each request.")),

 dict(id="UP:Purchase-Commitment", title="Purchase commitment", family="Compliance",
  purpose="Records a member's commitment to purchase a stated share of its purchases in a stated category under the Agreement, with periodic attestation.",
  params={"category": ("string", "Description of the product category."),
          "share": ("Rate", "Committed share of category purchases."),
          "period": ("Period", "Measurement period."),
          "due": ("Period", "Time after each period's end by which the attestation is due.")},
  forms=[{"form": "Duty", "duty": "attest-compliance", "obligor": "member", "obligee": "supplier",
          "trigger": {"every": P("period"), "anchor": "window-start"}, "due": P("due"),
          "discharge": {"claim": "UP:Purchase-Commitment/met", "ack": ["supplier"]}}],
  claims={"met": ({"period": "{start: Time, end: Time}", "basis": "string"}, "The Member attests that it met the committed share for the period. Discharges the duty when acknowledged by the Supplier.")},
  render=("The Member commits to purchase under this Agreement at least {{share|rate}} of its purchases of "
          "{{category}} in each period of {{period|period}}, and attests whether it met that commitment within "
          "{{due|period}} after each period ends.")),

 dict(id="UP:Notices", title="Notices", family="General",
  purpose="Makes signed attestations on the agreement's chain the binding method of giving notice.",
  params={},
  forms=[],
  claims={},
  render=("Any notice under this Agreement is given by a signed attestation recorded on this Agreement's chain of "
          "events, and is given at the time stated in that attestation.")),

 dict(id="UP:Governing-Law", title="Governing law", family="General",
  purpose="Names the law that governs the Agreement and the forum for disputes.",
  params={"law": ("string", "Governing law, e.g. a named jurisdiction."),
          "forum": ("string", "Forum for disputes.")},
  forms=[],
  claims={},
  render="This Agreement is governed by the law of {{law}}. Disputes are resolved in {{forum}}."),
dict(id="UP:Overlay", title="Overlay of an existing agreement", family="General",
  purpose="Declares that this Agreement describes an existing contract, identified by the hash of its document, without amending or replacing it.",
  params={"document": ("Hash", "SHA-256 hash of the existing contract document, as the parties hold it."),
          "document_title": ("string", "Title of the existing contract. Sealable."),
          "document_date": ("Time", "Date the existing contract was signed."),
          "governs": ("\"document\" | \"this-record\"", "Which text controls if this record and the existing contract are inconsistent.")},
  forms=[],
  claims={},
  render=("This record describes the agreement titled {{document_title}}, signed on {{document_date|time}}, whose "
          "document has the hash {{document}}. It does not amend or replace that agreement. If this record and "
          "that agreement are inconsistent, {{governs|governs}} controls."))

]

def definition(t):
    return {
        "type": "TermDefinition", "spec": SPEC, "id": t["id"], "title": t["title"],
        "params": {k: {"type": v[0], "doc": v[1]} for k, v in t["params"].items()},
        "forms": t["forms"],
        "claims": {f'{t["id"]}/{k}': {"data": v[0], "doc": v[1]} for k, v in t["claims"].items()},
        "render": t["render"],
        "provenance": {
            "drafted_by": "Universal Paper v0 working draft (publisher name pending open question 2)",
            "reviewed_by": [],
            "change_note": "Initial draft. Not yet reviewed by counsel from any segment.",
        },
    }

def md(t, d):
    fn = t["id"].replace(":", "-")
    lines = [f'# {t["id"]} — {t["title"]}', "",
             f'**Family:** {t["family"]} · **Spec:** `{SPEC}` · **Machine definition:** [`{fn}.json`]({fn}.json)', "",
             t["purpose"], "", "## Parameters", ""]
    if d["params"]:
        lines += ["| Name | Type | Meaning |", "|---|---|---|"]
        lines += [f'| `{k}` | `{v["type"]}` | {v["doc"]} |' for k, v in d["params"].items()]
    else:
        lines.append("None.")
    lines += ["", "No parameter has a default value (A6).", "", "## Machine definition", ""]
    if d["forms"]:
        lines += ["```json", json.dumps(d["forms"], indent=2), "```"]
    else:
        lines.append("No clause forms. This Term has legal meaning only: it changes no State and produces no Commitments.")
    lines += ["", "## Claims", ""]
    if d["claims"]:
        lines += ["| Claim type | Data | Meaning |", "|---|---|---|"]
        lines += [f'| `{k}` | `{json.dumps(v["data"])}` | {v["doc"]} |' for k, v in d["claims"].items()]
    else:
        lines.append("None.")
    lines += ["", "## Human rendering", "", "```text", d["render"], "```", "", "## Provenance", "",
              f'Drafted by: {d["provenance"]["drafted_by"]}. Reviewed by: none yet. {d["provenance"]["change_note"]}', ""]
    return fn, "\n".join(lines)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for t in TERMS:
        d = definition(t)
        fn, text = md(t, d)
        (OUT / f"{fn}.md").write_text(text)
        (OUT / f"{fn}.json").write_text(json.dumps(d, indent=2) + "\n")
        forms = ", ".join(sorted({f["form"] for f in d["forms"]})) or "none"
        rows.append(f'| [{t["id"]}]({fn}.md) | {t["family"]} | {forms} | {t["purpose"]} |')
    readme = OUT / "README.md"
    head = readme.read_text().split("<!-- table -->")[0] if readme.exists() else ""
    readme.write_text(head + "<!-- table -->\n\n| Term | Family | Forms | Purpose |\n|---|---|---|---|\n" + "\n".join(rows) + "\n")

if __name__ == "__main__":
    main()
