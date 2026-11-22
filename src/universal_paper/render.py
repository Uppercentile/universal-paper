"""Deterministic human rendering of an Agreement (spec/04-inference.md §7, axiom A8)."""
from __future__ import annotations

import re
from typing import Any

from .canon import content_hash
from .engine import Bundle
from .values import SEALED, fmt_period, is_seal, parse_time

ROLE_NAMES = {"aggregator": "the Aggregator", "supplier": "the Supplier", "member": "the Member"}
EACH_RE = re.compile(r"\{\{#each (\w+)\}\}(.*?)\{\{/each\}\}", re.S)
VAR_RE = re.compile(r"\{\{(\w+)(?:\|(\w+))?\}\}")
SENTENCE_RE = re.compile(r"(^|[.!?]\s+)([a-z])")
MODES = {"half-even": "half to even", "half-up": "half up", "down": "down", "up": "up"}


def _sealed_text(x: dict) -> str:
    return f"[sealed {x['seal']}]"


def fmt(bundle: Bundle, value: Any, f: str | None) -> str:
    if is_seal(value):
        v = bundle.reveal(value)
        if v is SEALED:
            return _sealed_text(value)
        value = v
    if f == "role":
        roles = value if isinstance(value, list) else [value]
        return " or ".join(ROLE_NAMES.get(r, r) for r in roles)
    if f == "amount":
        if isinstance(value, dict) and "value" in value:
            return f"{value['currency']} {value['value']}"
        if isinstance(value, dict):  # option -> Amount
            return "; ".join(f"{k}: {fmt(bundle, v, 'amount')}" for k, v in sorted(value.items()))
    if f == "rate":
        from decimal import Decimal
        d = Decimal(value) * 100
        s = format(d.normalize(), "f") if d == d.to_integral() else format(d, "f").rstrip("0").rstrip(".")
        return f"{s}%"
    if f == "period":
        return fmt_period(value)
    if f == "time":
        d = parse_time(value)
        return f"{d.day} {d.strftime('%B %Y')}, {d.strftime('%H:%M')} UTC"
    if f == "rounding":
        return f"to {value['scale']} decimal places, rounding {MODES[value['mode']]}"
    if f == "effective":
        if value == "on-ack":
            return "upon acknowledgment"
        return f"from the start of the next {fmt_period(value['next'])} period after acknowledgment"
    if f == "governs":
        return {"document": "the existing agreement", "this-record": "this record"}.get(value, str(value))
    if isinstance(value, dict) and set(value) == {"scheme", "id"}:
        idv = bundle.reveal(value["id"]) if is_seal(value["id"]) else value["id"]
        return f"{value['scheme']} {_sealed_text(value['id']) if idv is SEALED else idv}"
    if isinstance(value, list):
        return ", ".join(fmt(bundle, v, f) for v in value)
    return str(value)


def render_template(bundle: Bundle, template: str, params: dict) -> str:
    def each(m):
        items = params.get(m.group(1), [])
        if is_seal(items):
            return _sealed_text(items)
        return "".join(VAR_RE.sub(lambda v: fmt(bundle, {**params, **it}.get(v.group(1), v.group(0)), v.group(2)), m.group(2))
                       for it in items)
    text = EACH_RE.sub(each, template)
    text = VAR_RE.sub(lambda v: fmt(bundle, params.get(v.group(1), v.group(0)), v.group(2)), text).strip()
    return SENTENCE_RE.sub(lambda m: m.group(1) + m.group(2).upper(), text)


def render_agreement(bundle: Bundle, ag: dict) -> str:
    h = content_hash(ag)
    lines = [f"# {ag.get('label', 'Universal Paper agreement')}", "",
             f"Spec version: {ag['spec']}", f"Agreement hash: {h}", "", "## Parties", ""]
    for p in ag["parties"]:
        party = p["party"]
        ids = "; ".join(fmt(bundle, i, None) for i in party.get("ids", []))
        lines.append(f"- {party.get('name', party['key'])}, as {ROLE_NAMES[p['role']].replace('the ', 'the ', 1)}"
                     f" (key {party['key']}{'; ' + ids if ids else ''})")
    lines += ["", "## Terms", ""]
    for i, c in enumerate(ag["clauses"], 1):
        t = bundle.terms[c["def"]]
        lines.append(f"### {i}. {t['title']} ({c['term']}, clause \"{c['n']}\")")
        lines.append("")
        lines.append(render_template(bundle, t["render"], c["params"]))
        if c.get("over"):
            lines.append("")
            lines.append("This clause applies notwithstanding clause(s) " + ", ".join(f"\"{o}\"" for o in c["over"]) + ".")
        lines.append("")
    lines += ["## Signatures", "",
              f"Each party below signs the agreement identified by {h}. The signed text above is generated from that "
              "agreement and the Term definitions it pins by hash, so the text and the data cannot differ.", ""]
    for p in ag["parties"]:
        lines.append(f"- {p['party'].get('name', p['party']['key'])} ({ROLE_NAMES[p['role']]}): signature over {h}")
    return "\n".join(lines) + "\n"
