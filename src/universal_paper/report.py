"""Derived-value snapshots: statuses, tiers, prices, and obligations at a time."""
from __future__ import annotations

import json

from .canon import content_hash
from .engine import Evaluator, _val_items, clause_forms, keys_with_role
from .values import SEALED


def _amt(x):
    if x is SEALED:
        return "sealed"
    return x


def snapshot(ev: Evaluator, t: str, positions: list[int] | None = None) -> dict:
    b = ev.b
    chains = []
    for pos, chain in enumerate(b.chain_list):
        if not chain or (positions is not None and pos not in positions):
            continue
        cid = content_hash(chain[0])
        S = ev.state_at(cid, t)
        ag = ev.agreement(S)
        entry = {"chain": pos, "label": (ag or {}).get("label", f"chain {pos}"), "status": ev.status(cid, t),
                 "state_hash": content_hash(S) if S else None}
        if ag and S and S["status"] == "executed":
            cfs = clause_forms(b, ag)
            start, end = ev.window(cid, t)
            entry["window"] = {"start": start, "end": end}
            sel = next((cf for cf in cfs if cf.kind == "Selection"), None)
            if sel:
                tiers = {}
                for k in keys_with_role(ag, sel.form["subject"]):
                    tiers[k] = ev.selection(cid, sel.name, k, t)
                entry["selections"] = tiers
            parents = ev.parents(cid, t)
            if parents:
                pag = ev.agreement(ev.state_at(parents[0], t))
                items = []
                for cf in clause_forms(b, pag or {}):
                    if cf.kind == "Valuation":
                        items += [json.loads(i) for i in sorted(_val_items(cf))]
                seen, prices = set(), []
                for it in items:
                    k = json.dumps(it, sort_keys=True)
                    if k in seen:
                        continue
                    seen.add(k)
                    prices.append({"item": it, "price": _amt(ev.price(cid, it, t))})
                entry["prices"] = prices
            obs = ev.obligations(cid, t)
            if obs:
                entry["obligations"] = obs
        chains.append(entry)
    return {"at": t, "chains": chains}
