"""Reference helper for the OPTIONAL Fingerprint Coordination convention. Not part of Universal Paper.

Fingerprint Coordination is an analytical convention outside the language: parties (or their agents)
share Universal Paper fingerprints under explicit rules, and anyone holding the same inputs can derive
the same recomputable profile: parameter ranges, variance and outliers, historical structural deltas,
and Proposal seeds checked by a Universal Paper engine.

  fingerprint(obj)                     the Universal Paper fingerprint, exactly as the language defines it
  with_fingerprint(obj)                a copy whose `fingerprint` member is the fingerprint of everything else
  check_fingerprint(obj)               does the `fingerprint` member match?
  inputs_root(fingerprints)            one fingerprint for a set of input fingerprints
  contribution(...)                    a FingerprintContribution: which artifacts, under which rules
  agreements(bundle)                   every agreement in a bundle: in force, plus its proposal history
  diff_agreements(a, b)                structural diff of two agreements: clauses added/removed, parameters changed
  diff_bundles(a, b)                   structural diff of two bundles, chain by chain
  derive_profile(inputs, ...)          a DerivedProfile from bundles: statistics, deltas, outliers, seeds
  verify_profile(profile, inputs)      recompute a profile from the same inputs and compare
  extract_seeds(profile)               the Proposal seeds of a profile, shape-checked
  seed_proposal(bundle, seed, ...)     the unsigned `propose` event a seed describes, for a party to review and sign
  simulate_seed(bundle, seed, ...)     run a seed through the Universal Paper engine: new fingerprint and state delta

No network, no storage, no machine learning. Deterministic: the same inputs give the same bytes.
Requires the universal-paper package (Python 3.11+), whose canonicalization, fingerprints and engine it
reuses unchanged. Docs: docs/integrations/fingerprint-coordination.md. Code: Apache-2.0.
"""
from __future__ import annotations

import copy
import json
import re
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from universal_paper.canon import content_hash
from universal_paper.engine import Bundle, Evaluator
from universal_paper.report import snapshot
from universal_paper.simulate import simulate
from universal_paper.values import SEALED, dec_str, is_seal

CONVENTION = "fingerprint-coordination/0.1"
DISCLOSURES = ("fingerprint-only", "structure", "parameters")
PURPOSES = ("parameter-ranges", "variance", "historical-deltas", "proposal-seeds")
# Parameter types that identify one agreement rather than describe a term of trade: never compared or seeded.
SPECIFIC_TYPES = {"Time", "ChainId", "Hash", "string"}
# Terms that set prices or tiers: their ranges are shown, but a seed never proposes them.
NO_SEED_TERMS = {"UP:Tiers", "UP:Tier-Selection", "UP:Price-Reference"}

_FP = re.compile(r"^sha256:[0-9a-f]{64}$")
_DEC = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")


# ---------------------------------------------------------------------------- fingerprints
def fingerprint(obj: Any) -> str:
    """The Universal Paper fingerprint: "sha256:" + hex(SHA-256(JCS(strip(obj)))), unchanged from spec/01-domain.md."""
    return content_hash(obj)


def with_fingerprint(obj: dict) -> dict:
    """A copy of a Contribution or Derived Profile whose `fingerprint` is the fingerprint of all its other members."""
    body = {k: v for k, v in obj.items() if k != "fingerprint"}
    return {**body, "fingerprint": content_hash(body)}


def check_fingerprint(obj: dict) -> bool:
    """True if obj["fingerprint"] is the fingerprint of all its other members."""
    return isinstance(obj, dict) and obj.get("fingerprint") == content_hash({k: v for k, v in obj.items() if k != "fingerprint"})


def inputs_root(fingerprints: list[str]) -> str:
    """One fingerprint for a set of inputs: the fingerprint of the sorted, de-duplicated list of their fingerprints."""
    fps = sorted(set(fingerprints))
    for fp in fps:
        _check_fp(fp)
    return content_hash(fps)


def _check_fp(fp: Any) -> str:
    if not isinstance(fp, str) or not _FP.match(fp):
        raise ValueError(f"not a Universal Paper fingerprint: {fp!r}")
    return fp


# ---------------------------------------------------------------------------- contribution
def contribution(*, contributor: str, artifacts: list[dict], purposes: list[str], minimum_cohort: int = 3,
                 attribution: str = "none", outputs: str = "aggregate-only", created: str, expires: str | None = None) -> dict:
    """A FingerprintContribution: which artifacts a party shares, how much of each, and the rules for using them.

    artifacts: [{"fingerprint": "sha256:...", "kind": "Bundle", "disclosure": "fingerprint-only"|"structure"|"parameters"}].
    """
    if not isinstance(contributor, str) or not contributor.strip():
        raise ValueError("contributor must be a non-empty string")
    if not artifacts:
        raise ValueError("a contribution names at least one artifact")
    arts = []
    for a in artifacts:
        d = a.get("disclosure", "fingerprint-only")
        if d not in DISCLOSURES:
            raise ValueError(f"disclosure must be one of {DISCLOSURES}")
        arts.append({"fingerprint": _check_fp(a.get("fingerprint")), "kind": a.get("kind", "Bundle"), "disclosure": d})
    bad = [p for p in purposes if p not in PURPOSES]
    if bad or not purposes:
        raise ValueError(f"purposes must be a non-empty subset of {PURPOSES}")
    if not isinstance(minimum_cohort, int) or minimum_cohort < 2:
        raise ValueError("minimum_cohort must be an integer of at least 2")
    rules: dict[str, Any] = {"purposes": list(purposes), "minimumCohort": minimum_cohort,
                             "attribution": attribution, "outputs": outputs, "sealedValues": "never-counted"}
    if expires:
        rules["expires"] = expires
    return with_fingerprint({"type": "FingerprintContribution", "convention": CONVENTION, "contributor": contributor,
                             "created": created, "artifacts": sorted(arts, key=lambda a: a["fingerprint"]), "rules": rules})


# ---------------------------------------------------------------------------- reading bundles
def _terms_by_def(data: dict) -> dict[str, dict]:
    return {content_hash(t): t for t in data.get("terms", []) if isinstance(t, dict)}


def _roles(ag: dict) -> str:
    return "+".join(sorted({p.get("role", "?") for p in ag.get("parties", []) if isinstance(p, dict)}))


def agreements(bundle: dict) -> list[dict]:
    """Every chain's agreement in force at the bundle's latest event, with its proposal history and engine outcomes."""
    b = Bundle(bundle)
    ev = Evaluator(b)
    out = []
    for pos, chain in enumerate(b.chain_list):
        if not chain:
            continue
        cid = content_hash(chain[0])
        steps = ev.run(cid)
        history = []
        for E, step in zip(chain, steps):
            body = E.get("body") if isinstance(E.get("body"), dict) else {}
            if E.get("kind") == "propose" and isinstance(body.get("agreement"), dict):
                h = {"at": E["at"], "agreement": content_hash(body["agreement"]), "accepted": bool(step.accepted)}
                if body.get("supersedes"):
                    h["supersedes"] = body["supersedes"]
                if not step.accepted and step.reason:
                    h["reason"] = step.reason
                history.append(h)
        ag = ev.agreement(ev.state_at(cid))
        if ag is None:
            continue
        out.append({"chain": pos, "chainId": cid, "agreement": content_hash(ag), "label": ag.get("label", f"chain {pos}"),
                    "cohort": _roles(ag), "body": ag, "history": history})
    return out


def _flatten(term: str, params: dict, types: dict) -> dict[str, Any]:
    """Comparable parameters of one clause as {key: value}; keys like 'UP:Admin-Fee.rate' or 'UP:Tiers.prices[GTIN:1].A'."""
    out: dict[str, Any] = {}
    for name, value in params.items():
        ptype = (types.get(name) or {}).get("type", "")
        if ptype in SPECIFIC_TYPES or ptype == "Name":
            continue
        if name == "prices" and isinstance(value, list):
            for row in value:
                item = row.get("item", {}) if isinstance(row, dict) else {}
                for tier, amount in sorted((row.get("by") or {}).items()):
                    v = amount if is_seal(amount) else amount.get("value") if isinstance(amount, dict) else amount
                    out[f"{term}.prices[{item.get('scheme')}:{item.get('id')}].{tier}"] = v
        elif name == "tiers" and isinstance(value, list):
            continue  # descriptive conditions text; never compared or seeded
        else:
            out[f"{term}.{name}"] = value
    return out


def _params(b: Bundle, data: dict, ag: dict) -> dict[str, Any]:
    defs = _terms_by_def(data)
    out: dict[str, Any] = {}
    for c in ag.get("clauses", []):
        t = defs.get(c.get("def"), {})
        out.update(_flatten(c.get("term", "?"), c.get("params", {}), t.get("params", {})))
    return out


def _canon(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"))


def _num(v: Any) -> Decimal | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return Decimal(v)
    if isinstance(v, str) and _DEC.match(v):
        return Decimal(v)
    return None


def _dstr(d: Decimal) -> str:
    return dec_str(d.normalize()) if d != 0 else "0"


def _median(xs: list[Decimal]) -> Decimal:
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


# ---------------------------------------------------------------------------- structural diff
def diff_agreements(a: dict, b: dict) -> dict:
    """What changed from agreement a to agreement b: clauses added or removed (by name and Term) and parameters changed."""
    ca = {c.get("n"): c for c in a.get("clauses", [])}
    cb = {c.get("n"): c for c in b.get("clauses", [])}
    changes = []
    for n in sorted(set(ca) & set(cb)):
        pa, pb = ca[n].get("params", {}), cb[n].get("params", {})
        for p in sorted(set(pa) | set(pb)):
            if _canon(pa.get(p)) != _canon(pb.get(p)):
                ch = {"clause": n, "term": cb[n].get("term"), "param": p}
                if p in pa:
                    ch["from"] = pa[p]
                if p in pb:
                    ch["to"] = pb[p]
                d0, d1 = _num(pa.get(p)), _num(pb.get(p))
                if d0 is not None and d1 is not None:
                    ch["delta"] = _dstr(d1 - d0)
                changes.append(ch)
        if ca[n].get("term") != cb[n].get("term") or ca[n].get("def") != cb[n].get("def"):
            changes.append({"clause": n, "term": cb[n].get("term"), "param": "(definition)", "from": ca[n].get("def"), "to": cb[n].get("def")})
    other = sorted(k for k in set(a) | set(b) if k != "clauses" and _canon(a.get(k)) != _canon(b.get(k)))
    return {"from": content_hash(a), "to": content_hash(b),
            "clausesAdded": [{"clause": n, "term": cb[n].get("term")} for n in sorted(set(cb) - set(ca))],
            "clausesRemoved": [{"clause": n, "term": ca[n].get("term")} for n in sorted(set(ca) - set(cb))],
            "paramsChanged": changes, "otherMembersChanged": other}


def diff_bundles(a: dict, b: dict) -> dict:
    """Structural diff of two bundles: Term definitions added/removed, then the agreements in force, chain by chain."""
    ta, tb = _terms_by_def(a), _terms_by_def(b)
    ga, gb = agreements(a), agreements(b)
    chains = []
    for i in range(max(len(ga), len(gb))):
        x, y = (ga[i] if i < len(ga) else None), (gb[i] if i < len(gb) else None)
        if x and y:
            chains.append({"chain": i, **diff_agreements(x["body"], y["body"])})
        else:
            chains.append({"chain": i, "only": "from" if x else "to", "agreement": (x or y)["agreement"]})  # type: ignore[index]
    return {"type": "StructuralDiff", "convention": CONVENTION, "from": content_hash(a), "to": content_hash(b),
            "termsAdded": sorted(tb[h]["id"] for h in set(tb) - set(ta)),
            "termsRemoved": sorted(ta[h]["id"] for h in set(ta) - set(tb)), "chains": chains}


# ---------------------------------------------------------------------------- the profile
def derive_profile(inputs: list[dict], *, minimum_cohort: int = 3, max_seeds: int = 2, simulate_seeds: bool = True,
                   simulated: bool = True, notice: str | None = None) -> dict:
    """A DerivedProfile from bundles.

    inputs: [{"label": str, "source": str, "data": <bundle>, "disclosure": "parameters"|"structure"|"fingerprint-only"}].
    A statistic drawn from fewer than `minimum_cohort` distinct inputs is suppressed. Sealed values are never counted.
    """
    rows, ins = [], []
    for i in inputs:
        disc = i.get("disclosure", "fingerprint-only")
        if disc not in DISCLOSURES:
            raise ValueError(f"disclosure must be one of {DISCLOSURES}")
        fp = content_hash(i["data"])
        ins.append({"fingerprint": fp, "kind": "Bundle", "label": i["label"], "source": i["source"], "disclosure": disc})
        if disc == "fingerprint-only":
            continue
        b = Bundle(i["data"])
        for g in agreements(i["data"]):
            g["input"], g["disclosure"] = fp, disc
            g["params"] = _params(b, i["data"], g["body"]) if disc == "parameters" else {}
            g["terms"] = sorted({c.get("term") for c in g["body"].get("clauses", [])})
            rows.append(g)
    for n, g in enumerate(rows, 1):
        g["id"] = f"A{n}"

    deltas, delta_count = _deltas(rows, inputs)
    params, sealed = _parameters(rows, minimum_cohort, delta_count)
    presence = _presence(rows)
    matrix = _matrix(rows, params)
    outliers = _outliers(rows, params)
    seeds = _seeds(rows, params, presence, outliers, max_seeds)
    if simulate_seeds:
        data = {content_hash(i["data"]): i["data"] for i in inputs}
        for s in seeds:
            s["simulation"] = simulate_seed(data[s["target"]["input"]], s, library=[i["data"] for i in inputs])
    profile = {
        "type": "DerivedProfile", "convention": CONVENTION, "simulated": simulated,
        "notice": notice or "Derived with the Fingerprint Coordination reference helper. Recompute it from the listed inputs.",
        "method": {"helper": "examples/integrations/fingerprint-coordination/up_fpc.py", "function": "derive_profile",
                   "minimumCohort": minimum_cohort, "maxSeeds": max_seeds, "sealedValues": "never-counted",
                   "engine": "Universal Paper reference interpreter (universal-paper), UP/0.1-draft"},
        "inputs": ins, "inputsRoot": inputs_root([i["fingerprint"] for i in ins]),
        "corpus": {"agreements": len(rows), "cohorts": dict(sorted(Counter(g["cohort"] for g in rows).items())),
                   "sealedValuesNotCounted": sealed,
                   "suppressedStatistics": sum(1 for p in params if p["suppressed"])},
        "agreements": [{"id": g["id"], "input": g["input"], "chain": g["chain"], "agreement": g["agreement"], "label": g["label"],
                        "cohort": g["cohort"], "terms": g["terms"]} for g in rows],
        "parameters": params, "clausePresence": presence, "matrix": matrix,
        "deltas": deltas, "deltaStats": _delta_stats(deltas), "outliers": outliers, "seeds": seeds,
    }
    return with_fingerprint(profile)


def _deltas(rows: list[dict], inputs: list[dict]) -> tuple[list[dict], Counter]:
    """Historical structural deltas: every proposal that superseded an agreement, diffed, with the engine's outcome."""
    data = {content_hash(i["data"]): Bundle(i["data"]) for i in inputs}
    out, count = [], Counter()
    for g in rows:
        b = data[g["input"]]
        for h in g["history"]:
            if "supersedes" not in h or h["supersedes"] not in b.agreements:
                continue
            d = diff_agreements(b.agreements[h["supersedes"]], b.agreements[h["agreement"]])
            item = {"input": g["input"], "chain": g["chain"], "label": g["label"], "at": h["at"],
                    "outcome": "accepted" if h["accepted"] else "rejected", **d}
            if "reason" in h:
                item["reason"] = h["reason"]
            out.append(item)
            for c in d["paramsChanged"]:
                count[f"{c['term']}.{c['param']}"] += 1
    return out, count


def _delta_stats(deltas: list[dict]) -> list[dict]:
    by: dict[str, list[dict]] = {}
    for d in deltas:
        for c in d["paramsChanged"]:
            by.setdefault(f"{c['term']}.{c['param']}", []).append({**c, "outcome": d["outcome"]})
    out = []
    for key, cs in sorted(by.items()):
        s: dict[str, Any] = {"key": key, "changes": len(cs), "accepted": sum(c["outcome"] == "accepted" for c in cs),
                             "rejected": sum(c["outcome"] == "rejected" for c in cs)}
        ds = [Decimal(c["delta"]) for c in cs if "delta" in c]
        if ds:
            s["medianDelta"] = _dstr(_median(ds))
        out.append(s)
    return out


def _parameters(rows: list[dict], k: int, delta_count: Counter) -> tuple[list[dict], int]:
    cells: dict[tuple[str, str], list[tuple[dict, Any]]] = {}
    for g in rows:
        for key, v in g["params"].items():
            cells.setdefault((g["cohort"], key), []).append((g, v))
    out, sealed_total = [], 0
    for (cohort, key), obs in sorted(cells.items()):
        sealed = [g for g, v in obs if is_seal(v) or v is SEALED]
        sealed_total += len(sealed)
        open_ = [(g, v) for g, v in obs if not (is_seal(v) or v is SEALED)]
        n_inputs = len({g["input"] for g, _ in open_})
        term, param = key.split(".", 1)
        p: dict[str, Any] = {"key": key, "term": term, "param": param, "cohort": cohort, "observations": len(open_),
                             "inputs": n_inputs, "sealed": len(sealed), "suppressed": n_inputs < k,
                             "historicalChanges": delta_count.get(key, 0)}
        if not p["suppressed"]:
            counts = Counter(_canon(v) for _, v in open_)
            mode = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            p["values"] = [{"value": json.loads(c), "count": n} for c, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
            p["mode"] = json.loads(mode)
            p["differsFromMode"] = sum(1 for _, v in open_ if _canon(v) != mode)
            nums = [_num(v) for _, v in open_]
            if all(x is not None for x in nums):
                xs = [x for x in nums if x is not None]
                p["min"], p["max"], p["median"] = _dstr(min(xs)), _dstr(max(xs)), _dstr(_median(xs))
            p["variation"] = p["differsFromMode"] + p["historicalChanges"]
        out.append(p)
    return out, sealed_total


def _presence(rows: list[dict]) -> list[dict]:
    out = []
    for cohort in sorted({g["cohort"] for g in rows}):
        group = [g for g in rows if g["cohort"] == cohort]
        terms = Counter(t for g in group for t in g["terms"])
        for t, n in sorted(terms.items(), key=lambda kv: (-kv[1], kv[0])):
            out.append({"cohort": cohort, "term": t, "present": n, "of": len(group),
                        "absentFrom": [g["id"] for g in group if t not in g["terms"]]})
    return out


def _deviation(v: Any, p: dict) -> dict:
    if v is None:
        return {"state": "absent"}
    if is_seal(v) or v is SEALED:
        return {"state": "sealed"}
    if p.get("suppressed"):
        return {"state": "suppressed"}
    if "median" in p:
        x, m = _num(v), Decimal(p["median"])
        if x is None:
            return {"state": "other"}
        if x == m:
            return {"state": "median", "deviation": "0"}
        dev = ((x - m) / m).quantize(Decimal("0.0001")) if m != 0 else Decimal(0)
        return {"state": "above" if x > m else "below", "deviation": _dstr(dev)}
    return {"state": "mode" if _canon(v) == _canon(p.get("mode")) else "other"}


def _matrix(rows: list[dict], params: list[dict]) -> list[dict]:
    """Per cohort: agreements as columns, parameters as rows, each cell's position against the cohort (never the raw value)."""
    out = []
    for cohort in sorted({g["cohort"] for g in rows}):
        group = [g for g in rows if g["cohort"] == cohort and g["disclosure"] == "parameters"]
        ps = [p for p in params if p["cohort"] == cohort and not p["suppressed"]]
        ps.sort(key=lambda p: (-p.get("variation", 0), p["key"]))
        out.append({"cohort": cohort, "columns": [g["id"] for g in group],
                    "rows": [{"key": p["key"], "cells": [_deviation(g["params"].get(p["key"]), p) for g in group]} for p in ps]})
    return out


def _outliers(rows: list[dict], params: list[dict]) -> list[dict]:
    out = []
    for p in params:
        if p["suppressed"] or "median" not in p:
            continue
        for g in rows:
            if g["cohort"] != p["cohort"] or p["key"] not in g["params"]:
                continue
            d = _deviation(g["params"][p["key"]], p)
            if d["state"] in ("above", "below"):
                out.append({"agreement": g["id"], "key": p["key"], "state": d["state"], "deviation": d["deviation"]})
    out.sort(key=lambda o: (-abs(Decimal(o["deviation"])), o["key"], o["agreement"]))
    return out


def _seeds(rows: list[dict], params: list[dict], presence: list[dict], outliers: list[dict], max_seeds: int) -> list[dict]:
    """Deterministic seed rules. Candidates, not recommendations; a party decides whether to propose anything."""
    by_id = {g["id"]: g for g in rows}
    pmap = {(p["cohort"], p["key"]): p for p in params}
    seeds: list[dict] = []
    # Rule "toward-median": the largest numeric outlier (excluding price and tier Terms) moves to the cohort median.
    for o in outliers:
        g = by_id[o["agreement"]]
        term, param = o["key"].split(".", 1)
        if term in NO_SEED_TERMS or "[" in param:
            continue
        p = pmap[(g["cohort"], o["key"])]
        clause = next(c for c in g["body"]["clauses"] if c.get("term") == term)
        seeds.append({"rule": "toward-median", "target": _target(g),
                      "change": {"op": "set-param", "clause": clause["n"], "term": term, "param": param,
                                 "from": clause["params"][param], "to": p["median"]},
                      "basis": {"parameter": o["key"], "cohort": g["cohort"], "observations": p["observations"],
                                "inputs": p["inputs"], "median": p["median"], "deviation": o["deviation"]}})
        break
    # Rule "common-clause": the most common Term absent from some agreement in its cohort (present in at least 2/3),
    # added to the absent agreement most similar to those that have it, with the cohort's most common parameters.
    for pr in presence:
        if pr["term"] in NO_SEED_TERMS or not pr["absentFrom"] or 3 * pr["present"] < 2 * pr["of"]:
            continue
        if not any(p["term"] == pr["term"] and p["cohort"] == pr["cohort"] for p in params):
            continue  # a Term without parameters changes no derived value: nothing to show or compare
        have = [g for g in rows if g["cohort"] == pr["cohort"] and pr["term"] in g["terms"] and g["disclosure"] == "parameters"]
        clauses = [next(c for c in g["body"]["clauses"] if c.get("term") == pr["term"]) for g in have]
        if len({g["input"] for g in have}) < 3 or any(_has_specific(c, g) for c, g in zip(clauses, have)):
            continue
        modal = Counter(_canon({"n": c["n"], "def": c["def"], "params": c["params"]}) for c in clauses).most_common()
        best = json.loads(sorted(modal, key=lambda kv: (-kv[1], kv[0]))[0][0])
        union = set().union(*(set(g["terms"]) for g in have))
        cands = [by_id[a] for a in pr["absentFrom"] if by_id[a]["disclosure"] == "parameters"]
        if not cands:
            continue
        target = sorted(cands, key=lambda g: (-Decimal(len(set(g["terms"]) & union)) / len(set(g["terms"]) | union), g["id"]))[0]
        seeds.append({"rule": "common-clause", "target": _target(target),
                      "change": {"op": "add-clause", "clause": best["n"], "term": pr["term"], "def": best["def"], "params": best["params"]},
                      "basis": {"term": pr["term"], "cohort": pr["cohort"], "present": pr["present"], "of": pr["of"],
                                "inputs": len({g["input"] for g in have})}})
        break
    seeds = seeds[:max_seeds]
    for n, s in enumerate(seeds, 1):
        s["id"] = f"seed-{n}"
        s["note"] = "A candidate derived by a fixed rule from the inputs, not a recommendation. Only the parties decide what to propose."
    return seeds


def _has_specific(clause: dict, g: dict) -> bool:
    """Does the clause carry a parameter that identifies one agreement (a time, chain, hash, name or free text)?"""
    return any(f"{clause['term']}.{p}" not in g["params"] for p in clause.get("params", {}) if p not in ("prices", "tiers"))


def _target(g: dict) -> dict:
    return {"input": g["input"], "chain": g["chain"], "agreement": g["agreement"], "label": g["label"], "row": g["id"]}


# ---------------------------------------------------------------------------- agents: seeds -> proposals
def verify_profile(profile: dict, inputs: list[dict]) -> dict:
    """Recompute a profile from the same inputs and options, and compare. The inputs must hash to the listed fingerprints."""
    checks = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "passed": bool(ok), **({"detail": detail} if detail else {})})

    check("own fingerprint", check_fingerprint(profile))
    listed = sorted(i["fingerprint"] for i in profile.get("inputs", []))
    given = sorted(content_hash(i["data"]) for i in inputs)
    check("inputs match the listed fingerprints", listed == given, f"listed {len(listed)}, given {len(given)}")
    check("inputsRoot", profile.get("inputsRoot") == inputs_root(given))
    if checks[1]["passed"]:
        m = profile.get("method", {})
        disc = {i["fingerprint"]: i["disclosure"] for i in profile["inputs"]}
        again = derive_profile([{**i, "disclosure": disc[content_hash(i["data"])]} for i in inputs],
                               minimum_cohort=m.get("minimumCohort", 3), max_seeds=m.get("maxSeeds", 2),
                               simulate_seeds=all("simulation" in s for s in profile.get("seeds", [])),
                               simulated=profile.get("simulated", True), notice=profile.get("notice"))
        check("recomputed profile is identical", again["fingerprint"] == profile.get("fingerprint"), again["fingerprint"])
    return {"ok": all(c["passed"] for c in checks), "checks": checks}


def extract_seeds(profile: dict) -> list[dict]:
    """The Proposal seeds of a profile, after checking the profile's own fingerprint and each seed's shape."""
    if not check_fingerprint(profile):
        raise ValueError("the profile's fingerprint does not match its contents")
    out = []
    for s in profile.get("seeds", []):
        ch, t = s.get("change", {}), s.get("target", {})
        if ch.get("op") not in ("set-param", "add-clause") or not isinstance(ch.get("clause"), str):
            raise ValueError(f"seed {s.get('id')!r}: unknown change")
        _check_fp(t.get("input"))
        _check_fp(t.get("agreement"))
        out.append(s)
    return out


def _apply(ag: dict, change: dict) -> dict:
    new = copy.deepcopy(ag)
    if change["op"] == "set-param":
        c = next((c for c in new["clauses"] if c.get("n") == change["clause"]), None)
        if c is None or change["param"] not in c.get("params", {}):
            raise ValueError(f"no parameter {change['clause']}.{change['param']} in the target agreement")
        c["params"][change["param"]] = change["to"]
    elif change["op"] == "add-clause":
        if any(c.get("n") == change["clause"] for c in new["clauses"]):
            raise ValueError(f"the target agreement already has a clause named {change['clause']!r}")
        new["clauses"].append({"def": change["def"], "n": change["clause"], "params": change["params"], "term": change["term"]})
    return new


def _current(bundle: dict, seed: dict) -> tuple[dict, dict]:
    t = seed["target"]
    if content_hash(bundle) != t["input"]:
        raise ValueError("this bundle is not the seed's target input")
    g = next((g for g in agreements(bundle) if g["chain"] == t["chain"]), None)
    if g is None or g["agreement"] != t["agreement"]:
        raise ValueError("the target agreement is no longer in force in this bundle")
    return g, g["body"]


def _next_day(bundle: dict) -> str:
    latest = max(E["at"] for ch in bundle.get("chains", []) for E in ch)
    return (datetime.fromisoformat(latest.replace("Z", "+00:00")) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_proposal(bundle: dict, seed: dict, *, by: str, at: str | None = None) -> dict:
    """The unsigned `propose` event a seed describes (chain, kind, by, at, body). Review it, then sign it with your own keys."""
    g, cur = _current(bundle, seed)
    keys = {p["party"]["key"]: p.get("role") for p in cur.get("parties", [])}
    if by not in keys:
        by = next((k for k, r in keys.items() if r == by), by)
    if by not in keys:
        raise ValueError("by must be a party of the target agreement (a key or a role)")
    return {"chain": g["chain"], "kind": "propose", "by": by, "at": at or _next_day(bundle),
            "body": {"agreement": _apply(cur, seed["change"]), "supersedes": content_hash(cur)}}


def _obligations(snap: dict | None, chain: int) -> dict[str, dict]:
    out = {}
    for c in (snap or {}).get("chains", []):
        if c["chain"] != chain:
            continue
        for o in c.get("obligations", []):
            period = o.get("period", {})
            key = f"{o['clause']}/{o['duty']}/{period.get('start', o.get('due', ''))}"
            out[key] = {k: o[k] for k in ("clause", "duty", "period", "due", "amount", "status") if k in o}
    return out


def simulate_seed(bundle: dict, seed: dict, *, library: list[dict] | None = None, at: str | None = None,
                  horizon_days: int = 90) -> dict:
    """Run a seed through the Universal Paper engine, as if every party signed: the new agreement's fingerprint,
    whether the engine accepts it, and how derived obligations differ `horizon_days` later. Hypothetical and
    unsigned; nothing is signed or sent anywhere.

    library: other bundles to take a Term definition from, when the seed adds a clause whose Term the target bundle lacks.
    """
    g, cur = _current(bundle, seed)
    at = at or _next_day(bundle)
    horizon = (datetime.fromisoformat(at.replace("Z", "+00:00")) + timedelta(days=horizon_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = copy.deepcopy(bundle)
    notes = []
    if seed["change"]["op"] == "add-clause" and seed["change"]["def"] not in _terms_by_def(data):
        t = next((d for lib in library or [] for h, d in _terms_by_def(lib).items() if h == seed["change"]["def"]), None)
        if t is None:
            raise ValueError("the seed's Term definition is not in the bundle or the library")
        data["terms"] = [*data.get("terms", []), t]
        notes.append(f"The {t['id']} Term definition ({seed['change']['def']}) is added to a copy of the bundle from the public inputs.")
    parties = [p["party"]["key"] for p in cur.get("parties", [])]
    prop = seed_proposal(data, {**seed, "target": {**seed["target"], "input": content_hash(data)}}, by=parties[0], at=at)
    result = simulate(data, [{**prop, "cosigners": parties[1:]}], horizon)
    step = result["steps"][0]
    before = snapshot(Evaluator(Bundle(bundle)), horizon)
    ob0, ob1 = _obligations(before, g["chain"]), _obligations(result["final"], g["chain"])
    out: dict[str, Any] = {
        "hypothetical": True, "at": at, "comparedAt": horizon,
        "assumes": "every party of the target agreement signs the proposal; no other events happen",
        "accepted": step["accepted"], "newAgreement": content_hash(prop["body"]["agreement"]),
        "supersedes": prop["body"]["supersedes"],
        "stateHash": {"before": _state_hash(before, g["chain"]), "after": _state_hash(result["final"], g["chain"])},
        "obligationsChanged": [{"key": k, "before": ob0[k], "after": ob1[k]}
                               for k in sorted(set(ob0) & set(ob1)) if _canon(ob0[k]) != _canon(ob1[k])],
        "obligationsAdded": [ob1[k] for k in sorted(set(ob1) - set(ob0))],
        "obligationsRemoved": [ob0[k] for k in sorted(set(ob0) - set(ob1))],
    }
    if not step["accepted"] and step["reason"]:
        out["reason"] = step["reason"]
    if notes:
        out["notes"] = notes
    return out


def _state_hash(snap: dict | None, chain: int) -> str:
    return next((c.get("state_hash", "") for c in (snap or {}).get("chains", []) if c["chain"] == chain), "")
