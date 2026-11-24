"""What-if questions an agent asks before anyone signs: rate conformity, termination, eligibility.

Each answer is computed by the reference interpreter from the bundle alone, so every party that runs the
same question on the same bundle gets the same answer, with the same reason. Nothing is signed or written:
hypothetical events are evaluated without signatures (Mandate limits still apply, see simulate.py).

These are conveniences over the specification, not new semantics. Where the specification leaves a fact to an
attestation (such as a member's tier), the answer says so and works from what has been attested and acknowledged.
"""
from __future__ import annotations

import json
from typing import Any

from .canon import content_hash
from .engine import Bundle, Evaluator, _val_items, clause_forms, keys_with_role, party_keys, roles_of
from .report import snapshot
from .simulate import run_hypothetical
from .values import SEALED, add_period, dec, dec_str, fmt_period

ROLES = ("aggregator", "supplier", "member")


class WhatIfError(ValueError):
    """The question cannot be asked of this bundle (unknown chain, party, item...)."""


def _latest(b: Bundle) -> str:
    times = [E["at"] for ch in b.chain_list for E in ch if isinstance(E, dict) and isinstance(E.get("at"), str)]
    if not times:
        raise WhatIfError("the bundle has no events")
    return max(times)


def _chain(b: Bundle, chain: int | str) -> tuple[int, str]:
    """A chain given by position or ChainId -> (position, ChainId)."""
    if isinstance(chain, str) and chain.isdigit():
        chain = int(chain)
    if isinstance(chain, int) and not isinstance(chain, bool):
        if 0 <= chain < len(b.chain_list) and b.chain_list[chain]:
            return chain, content_hash(b.chain_list[chain][0])
        raise WhatIfError(f"no chain {chain} in the bundle (it has {len(b.chain_list)})")
    if isinstance(chain, str) and chain in b.chain_pos:
        return b.chain_pos[chain], chain
    raise WhatIfError("chain must be a position (0, 1, ...) or a ChainId in the bundle")


def _label(ag: dict | None, pos: int) -> str:
    return (ag or {}).get("label", f"chain {pos}")


def _name(ag: dict, key: str) -> str:
    return next((p["party"].get("name", key) for p in ag.get("parties", []) if p["party"]["key"] == key), key)


def _party(ag: dict, who: str) -> str:
    """A party of `ag` given as a role, key, name, or identifier -> its key."""
    who = who.strip()
    if who in ROLES:
        keys = keys_with_role(ag, who)
        if not keys:
            raise WhatIfError(f"no party holds the role {who!r} in this agreement")
        if len(keys) > 1:
            raise WhatIfError(f"{len(keys)} parties hold the role {who!r} here; name the party by key, name, or identifier")
        return keys[0]
    for p in ag.get("parties", []):
        pa = p["party"]
        if who == pa["key"] or who.casefold() == str(pa.get("name", "")).casefold() \
                or any(who == i.get("id") for i in pa.get("ids", [])):
            return pa["key"]
    raise WhatIfError(f"{who!r} is not a party to this agreement; parties: "
                      + "; ".join(f"{p['role']}: {p['party'].get('name', p['party']['key'])}" for p in ag.get("parties", [])))


def _amount(x: Any, what: str) -> dict:
    if isinstance(x, int | float) and not isinstance(x, bool):
        x = str(x)
    if isinstance(x, str):
        x = {"value": x, "currency": None}
    if not isinstance(x, dict) or "value" not in x:
        raise WhatIfError(f"{what} must be an Amount like {{\"value\": \"1000.00\", \"currency\": \"USD\"}}")
    try:
        dec(str(x["value"]))
    except ValueError:
        raise WhatIfError(f"{what} has a value that is not a decimal: {x['value']!r}") from None
    return {"value": str(x["value"]), "currency": x.get("currency")}


def _item(x: Any) -> dict:
    if isinstance(x, dict) and "id" in x:
        return {"scheme": x.get("scheme"), "id": str(x["id"])}
    if isinstance(x, str | int) and not isinstance(x, bool):
        return {"scheme": None, "id": str(x)}
    raise WhatIfError("each line's item is an Identifier like {\"scheme\": \"GTIN\", \"id\": \"00000000000017\"} or an id string")


def _priced_items(ev: Evaluator, parent: str, t: str) -> list[dict]:
    pag = ev.agreement(ev.state_at(parent, t)) or {}
    seen: list[dict] = []
    for cf in clause_forms(ev.b, pag):
        if cf.kind == "Valuation":
            for i in sorted(_val_items(cf)):
                it = json.loads(i)
                if it not in seen:
                    seen.append(it)
    return seen


def _match(item: dict, known: list[dict]) -> dict | None:
    hits = [k for k in known if k.get("id") == item["id"] and item["scheme"] in (None, k.get("scheme"))]
    return hits[0] if len(hits) == 1 else None


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------

def _participation_status(ev: Evaluator, b: Bundle, pos: int, cid: str, t: str) -> tuple[str, str]:
    """(status, reason) of one participation chain at t, in words."""
    S = ev.state_at(cid, t)
    status = ev.status(cid, t)
    if S is None:
        return status, "The participation has no events at this time."
    if S["status"] == "proposed":
        pend = S.get("pending", {})
        ag = b.agreements.get(pend.get("agreement"), {})
        missing = sorted(party_keys(ag) - set(pend.get("signed", [])))
        who = ", ".join(f"{'/'.join(sorted(roles_of(ag, k)))} ({_name(ag, k)})" for k in missing)
        if status == "lapsed":
            return status, f"The participation was proposed but lapsed at {pend.get('expires')} before every party signed."
        return status, f"The participation is proposed but not executed: still to sign: {who}. Unanimity (A2) means it binds no one yet."
    start, end = ev.window(cid, t)
    if status == "terminated":
        return status, f"The participation was terminated, effective {S.get('ends_at')}."
    if status == "expired":
        return status, f"The participation's term ended at {end}."
    if status == "executed":
        return status, f"The participation is signed but its term starts at {start}."
    if status == "suspended":
        parents = ev.parents(cid, t)
        why = ", ".join(f"chain {b.chain_pos.get(p, '?')} is {ev.status(p, t)}" for p in parents)
        return status, f"The participation is signed and in term, but the agreement it participates in is not in force ({why})."
    return status, f"The participation is executed and in force from {start} until {end or 'no fixed end'}, and the agreement it participates in is in force."


def simulate_eligibility(data: dict, member: str, at: str | None = None, parent: int | str | None = None) -> dict:
    """Is `member` a real, active participant (UP:Participation) at time `at`, so its purchases count under the agreement?"""
    if not isinstance(member, str) or not member.strip():
        raise WhatIfError("member is a party key, name, or identifier (e.g. an HIN or GLN)")
    b = Bundle(data)
    ev = Evaluator(b)
    t = at or _latest(b)
    parent_cid = _chain(b, parent)[1] if parent is not None else None
    found: list[dict] = []
    who: Any = None
    for pos, ch in enumerate(b.chain_list):
        if not ch:
            continue
        cid = content_hash(ch[0])
        S = ev.state_at(cid, t)
        ag = ev.agreement(S) or b.agreements.get((S or {}).get("pending", {}).get("agreement")) \
            or (ch[0].get("body") or {}).get("agreement") or {}
        links = [cf.form["parent"] for cf in clause_forms(b, ag) if cf.kind == "Link"]
        if not links or (parent_cid and parent_cid not in links):
            continue
        try:
            key = _party(ag, member)
        except WhatIfError:
            continue
        if "member" not in roles_of(ag, key):
            continue
        who = who or {"key": key, "name": _name(ag, key)}
        status, reason = _participation_status(ev, b, pos, cid, t)
        entry = {"chain": pos, "chain_id": cid, "label": _label(ag, pos),
                 "parent": {"chain": b.chain_pos.get(links[0]), "chain_id": links[0],
                            "label": _label(ev.agreement(ev.state_at(links[0], t)), b.chain_pos.get(links[0], 0)),
                            "status": ev.status(links[0], t)},
                 "status": status, "reason": reason}
        if status == "active":
            sel = next((cf for cf in clause_forms(b, ag) if cf.kind == "Selection"), None)
            if sel:
                entry["tier"] = ev.selection(cid, sel.name, key, t)
        found.append(entry)
    if not found:
        scope = f" under chain {parent}" if parent is not None else ""
        return {"hypothetical": True, "at": t, "member": member, "eligible": False,
                "reason": f"No participation{scope} names {member!r} as its member, so its purchases do not count under any agreement in this bundle.",
                "participations": []}
    active = [p for p in found if p["status"] == "active"]
    if active:
        p = active[0]
        reason = (f"Eligible: {who['name']} is an active member under '{p['parent']['label']}' through chain {p['chain']}. "
                  + p["reason"])
    else:
        reason = f"Not eligible: {who['name']} has no participation in force at {t}. " + " ".join(
            f"Chain {p['chain']}: {p['reason']}" for p in found)
    return {"hypothetical": True, "at": t, "member": who, "eligible": bool(active), "reason": reason,
            "participations": found}


# ---------------------------------------------------------------------------
# Rate conformity
# ---------------------------------------------------------------------------

def simulate_rate_conformity(data: dict, chain: int | str, rates: list[dict], at: str | None = None,
                             tier: str | None = None) -> dict:
    """Do the rates given for items conform to the member's contract prices at `at`? Optionally as if it moved to `tier`."""
    if not isinstance(rates, list) or not rates:
        raise WhatIfError("rates is a non-empty list of {item, price}")
    b = Bundle(data)
    pos, cid = _chain(b, chain)
    ev = Evaluator(b)
    t = at or _latest(b)
    S = ev.state_at(cid, t)
    ag = ev.agreement(S)
    parents = ev.parents(cid, t) if ag else []
    if not ag or not parents:
        what = "is not an executed agreement" if not ag else "is not a participation (it has no UP:Participation clause)"
        raise WhatIfError(f"chain {pos} {what}; pass the member's participation chain")
    sel = next((cf for cf in clause_forms(b, ag) if cf.kind == "Selection"), None)
    member = keys_with_role(ag, sel.form["subject"])[0] if sel else keys_with_role(ag, "member")[0]
    status, why = _participation_status(ev, b, pos, cid, t)
    current = ev.selection(cid, sel.name, member, t) if sel else None
    options = ev.options(ag, sel.form) if sel else []

    out: dict[str, Any] = {"hypothetical": True, "chain": pos, "label": _label(ag, pos), "at": t,
                           "member": {"key": member, "name": _name(ag, member)}, "status": status}
    tier_out: dict[str, Any] = {"in_effect": current, "options": options,
                                "note": "A tier applies once the member attests it and the supplier acknowledges it (UP:Tier-Selection); "
                                        "it is never derived from volume."}
    applied = current
    peval = ev
    if tier is not None and tier != current:
        if not sel:
            raise WhatIfError("this participation has no tier selection clause")
        acks = [k for r in sel.form.get("ack", []) for k in keys_with_role(ag, r)]
        event = {"chain": pos, "kind": "attest", "by": member, "at": t, "cosigners": acks,
                 "body": {"claim": {"type": f"{sel.tid}/selects", "clause": sel.name,
                                    "data": {"option": tier, "basis": "Hypothetical: simulated by simulate_rate_conformity"}}}}
        data2, unverified, steps = run_hypothetical(data, [event])
        step = steps[0]
        change: dict[str, Any] = {"requested": tier, "accepted": step["accepted"], "reason": step.get("reason") or None}
        if step["accepted"]:
            peval = Evaluator(Bundle(data2), unverified)
            eff = sel.form.get("effective")
            if isinstance(eff, dict):
                start = peval.window(cid, t)[0] or t
                k = 0
                while add_period(start, eff["next"], k) <= t:
                    k += 1
                change["effective_at"] = add_period(start, eff["next"], k)
            else:
                change["effective_at"] = t
            change["note"] = "Simulated as the member's attestation, acknowledged by the supplier."
            if change["effective_at"] <= t:
                applied = tier
        tier_out["change"] = change
    tier_out["applied"] = applied
    out["tier"] = tier_out

    known = _priced_items(ev, parents[0], t)
    lines, problems, off = [], [], []
    for i, r in enumerate(rates):
        if not isinstance(r, dict) or "item" not in r or "price" not in r:
            raise WhatIfError(f"rate {i} needs an item and a price")
        given = _amount(r["price"], f"rate {i} price")
        item = _match(_item(r["item"]), known)
        line: dict[str, Any] = {"item": item or r["item"], "given": given, "contract": None, "conforms": None}
        lines.append(line)
        if item is None:
            problems.append(f"item {_item(r['item'])['id']} is not priced under the agreement")
            continue
        unit = peval.value(parents[0], item, applied, t) if applied else None
        if unit is SEALED:
            problems.append(f"the contract price of {item['id']} is sealed and not disclosed in this bundle")
            continue
        if unit is None:
            problems.append(f"no contract price for {item['id']} in tier {applied} at {t}")
            continue
        line["contract"] = unit
        line["by_tier"] = {o: (u if isinstance(u := ev.value(parents[0], item, o, t), dict) else None) for o in options}
        if given["currency"] is None:
            given["currency"] = unit["currency"]
        if given["currency"] != unit["currency"]:
            line["conforms"] = False
            off.append(f"{item['id']} is given in {given['currency']}, the contract price is in {unit['currency']}")
            continue
        diff = dec(given["value"]) - dec(unit["value"])
        line["conforms"] = diff == 0
        line["difference"] = {"value": dec_str(diff), "currency": unit["currency"]}
        if diff:
            match = [o for o, u in line["by_tier"].items() if u and dec(u["value"]) == dec(given["value"])]
            off.append(f"{item['id']} at {given['value']} is {'above' if diff > 0 else 'below'} the contract price "
                       f"{unit['value']} in tier {applied}" + (f" (it is the tier {', '.join(match)} price)" if match else ""))
    out["rates"] = lines

    if status != "active":
        out.update(conforms=False, reason=f"No contract price applies at {t}: {why}")
    elif tier_out.get("change") and not tier_out["change"]["accepted"]:
        out.update(conforms=False, reason=f"The tier change to {tier} would be rejected: {tier_out['change']['reason']}")
    elif problems:
        out.update(conforms=False, reason="Not every rate can be checked: " + "; ".join(problems) + ".")
    elif off:
        out.update(conforms=False, reason=f"{len(off)} of {len(lines)} rate(s) do not conform: " + "; ".join(off) + ".")
    else:
        out.update(conforms=True, reason=f"All {len(lines)} rate(s) equal the member's contract prices in tier {applied} at {t}.")
    return out

# ---------------------------------------------------------------------------
# Termination
# ---------------------------------------------------------------------------

def _exit_clauses(b: Bundle, ag: dict) -> list:
    return [cf for cf in clause_forms(b, ag) if cf.kind == "Exit"]


def simulate_termination(data: dict, chain: int | str, by: str, at: str | None = None, clause: str | None = None) -> dict:
    """If party `by` gives notice of termination on `chain` at `at`: is it allowed, when does it take effect, what remains owed."""
    b = Bundle(data)
    pos, cid = _chain(b, chain)
    ev = Evaluator(b)
    t = at or _latest(b)
    S: Any = ev.state_at(cid, t)
    ag = ev.agreement(S)
    if not ag or S["status"] != "executed":
        raise WhatIfError(f"chain {pos} has no executed agreement at {t} to terminate")
    if not isinstance(by, str):
        raise WhatIfError("by is a role (aggregator, supplier, member), party key, name, or identifier")
    key = _party(ag, by)
    roles = sorted(roles_of(ag, key))
    exits = _exit_clauses(b, ag)
    if clause is not None:
        exits = [cf for cf in exits if cf.name == clause]
        if not exits:
            raise WhatIfError(f"no termination clause {clause!r}; termination clauses: "
                              + (", ".join(cf.name for cf in _exit_clauses(b, ag)) or "none"))
    base = {"hypothetical": True, "chain": pos, "label": _label(ag, pos), "at": t,
            "by": {"key": key, "name": _name(ag, key), "roles": roles}, "status_now": ev.status(cid, t)}
    mine = [cf for cf in exits if set(cf.form["holders"]) & set(roles)]
    if not mine:
        held = "; ".join(f"'{cf.name}' ({cf.tid}): {', '.join(cf.form['holders'])}" for cf in exits) or "none"
        return {**base, "allowed": False,
                "reason": f"No termination clause lets the {'/'.join(roles)} terminate this agreement. Termination clauses and who may use them: {held}.",
                "options": []}
    if base["status_now"] in ("terminated", "expired"):
        return {**base, "allowed": False, "reason": f"The agreement is already {base['status_now']} at {t}.", "options": []}

    options = []
    for cf in mine:
        f = cf.form
        data_ = {}
        hint = None
        if "requires" in f:
            req = f["requires"]
            claims = S["facts"].get(cf.name, {}).get("claims", [])
            breaches = [c for c in claims if c["type"] == req["claim"] and c["by"] == key]
            open_ = [c for c in breaches if not any(x["type"] == req["unless"] and x["data"].get("breach") == c["event"]
                                                    and any(a["by"] == key for a in x["acks"]) for x in claims)]
            target = max(open_, key=lambda c: c["at"]) if open_ else None
            data_ = {"breach": target["event"] if target else "sha256:" + "0" * 64}
            if target:
                ready = add_period(target["at"], req["age"])
                hint = (f"Breach notice of {target['at']} ('{target['data'].get('description', '')}'): the cure period ends {ready}, "
                        f"so notice can be given from then, effective {add_period(ready, f['notice'])} at the earliest.")
            else:
                ready = add_period(t, req["age"])
                hint = (f"This party has given no uncured breach notice. If it gave one at {t}, it could terminate for cause "
                        f"from {ready}, effective {add_period(ready, f['notice'])} at the earliest.")
        event = {"chain": pos, "kind": "attest", "by": key, "at": t,
                 "body": {"claim": {"type": f"{cf.tid}/notice", "clause": cf.name, "data": data_}}}
        data2, unverified, steps = run_hypothetical(data, [event])
        step = steps[0]
        opt: dict[str, Any] = {"clause": cf.name, "term": cf.tid, "notice": f["notice"], "allowed": step["accepted"]}
        if hint:
            opt["cure"] = hint
        if not step["accepted"]:
            opt["reason"] = step.get("reason") or None
        else:
            ev2 = Evaluator(Bundle(data2), unverified)
            S2: Any = ev2.state_at(cid)
            notice_end = add_period(t, f["notice"])
            effective = S2.get("ends_at", notice_end)
            _, natural = ev.window(cid, t)
            opt["effective_at"] = effective
            if natural and natural <= notice_end:
                opt["note"] = f"The term ends at {natural} anyway, no later than this notice would take effect."
            opt["reason"] = f"Notice under '{cf.name}' at {t} takes effect at {effective} (notice period: {fmt_period(f['notice'])})."
            # Duties for every period that ends by the effective date survive the notice; list those not yet discharged.
            snap = snapshot(ev2, effective)
            obs = [{"clause": o["clause"], "duty": o["duty"], "obligor": o["obligor"]["role"], "obligee": o["obligee"]["role"],
                    "period": o["period"], "due": o["due"], **({"amount": o["amount"]} if "amount" in o else {}),
                    "status_now": "overdue" if o["due"] <= t else "not yet due"}
                   for c in snap["chains"] if c["chain"] == pos for o in c.get("obligations", []) if o["status"] != "discharged"]
            opt["still_owed"] = obs
            opt["fees_still_owed"] = [o for o in obs if o["duty"] == "pay"]
            children = []
            for p2, ch in enumerate(ev2.b.chain_list):
                if not ch or p2 == pos:
                    continue
                c2 = content_hash(ch[0])
                if cid in ev2.parents(c2, effective) and ev2.status(c2, t) in ("active", "executed"):
                    children.append({"chain": p2, "label": _label(ev2.agreement(ev2.state_at(c2, effective)), p2),
                                     "status_after": ev2.status(c2, effective)})
            opt["affected_participations"] = children
        options.append(opt)

    allowed = [o for o in options if o["allowed"]]
    if allowed:
        best = min(allowed, key=lambda o: o["effective_at"])
        reason = best["reason"]
        if best.get("affected_participations"):
            reason += f" {len(best['affected_participations'])} participation(s) under it stop being in force then."
        if best["fees_still_owed"] or best["still_owed"]:
            reason += (f" {len(best['still_owed'])} duties for periods ending by then are not yet discharged"
                       f", {len(best['fees_still_owed'])} of them fee payment(s).")
        for o in options:
            if not o["allowed"]:
                reason += f" Not available now under '{o['clause']}' ({o['term']}): {o.get('reason')}" + (f" {o['cure']}" if o.get("cure") else "")
        return {**base, "allowed": True, "clause": best["clause"], "effective_at": best["effective_at"], "reason": reason,
                "options": options}
    reason = " ".join(f"'{o['clause']}': {o.get('reason')}" + (f" {o['cure']}" if o.get("cure") else "") for o in options)
    return {**base, "allowed": False, "reason": f"Notice at {t} would be rejected. {reason}", "options": options}
