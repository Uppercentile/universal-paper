"""The transition function, clause forms, and derived values.

Section references are to the specification in spec/. Every check that can
reject an Event is recorded as a Check, so traces can show exactly which rule
passed or failed and why.
"""
from __future__ import annotations

import copy
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from . import SPEC, typecheck
from .canon import content_hash, normalize
from .crypto import valid_key, verify
from .values import (
    SEALED,
    add_period,
    contains_seal,
    dec,
    dec_str,
    dmul,
    dsum,
    is_seal,
    opens,
    parse_time,
    round_dec,
)

ROLES = ("aggregator", "supplier", "member")
KINDS = ("propose", "accept", "attest")
FORMS = ("Window", "Exit", "Selection", "Valuation", "Duty", "Link")
# Parameter types that may never be sealed (spec/01-domain.md §3.3).
STRUCTURAL_TYPES = {"Time", "Period", "Role", "[Role]", "ChainId", "Hash", "int", "Rounding"}

AXIOM_LABELS = {
    "A1": "Composition",
    "A2": "Unanimity",
    "A3": "Chained transitions",
    "A4": "Determinism",
    "A5": "Non-retroactivity",
    "A6": "Value neutrality",
    "A7": "Role symmetry",
    "A8": "Rendering binding",
    "A9": "Bounded delegation",
    "A10": "Verifiable confidentiality",
    "A11": "Closed evidence",
    "A12": "Single attribution",
    "A13": "Resolved precedence",
    "R-propose": "Rule: propose",
    "R-accept": "Rule: accept",
    "R-attest": "Rule: attest",
    "F-Link": "Form: Link",
    "F-Exit": "Form: Exit",
    "F-Selection": "Form: Selection",
    "F-Duty": "Form: Duty",
}


def canon_key(x: Any) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

@dataclass
class Check:
    id: str
    rule: str
    passed: bool
    reason: str

    def to_json(self) -> dict:
        return {"id": self.id, "rule": self.rule, "label": AXIOM_LABELS.get(self.rule, self.rule),
                "passed": self.passed, "reason": self.reason}


class Reject(Exception):
    pass


@dataclass
class Checks:
    items: list[Check] = field(default_factory=list)

    def check(self, cid: str, rule: str, ok: bool, yes: str, no: str) -> None:
        self.items.append(Check(cid, rule, bool(ok), yes if ok else no))
        if not ok:
            raise Reject(no)


# ---------------------------------------------------------------------------
# Bundle
# ---------------------------------------------------------------------------

class Bundle:
    """Everything an evaluator needs, and nothing else (spec/01-domain.md §12)."""

    def __init__(self, data: dict):
        data = normalize(data)
        self.data = data
        self.terms = {content_hash(t): t for t in data.get("terms", [])}
        self.mandates = {content_hash(m): m for m in data.get("mandates", [])}
        self.chain_list: list[list[dict]] = [list(c) for c in data.get("chains", [])]
        self.chains: dict[str, list[dict]] = {}
        self.chain_pos: dict[str, int] = {}
        self.forks: list[str] = []  # ChainIds that appear more than once (spec/01-domain.md §12)
        for i, c in enumerate(self.chain_list):
            if c:
                cid = content_hash(c[0])
                if cid in self.chains:
                    self.forks.append(cid)
                self.chains[cid] = c
                self.chain_pos[cid] = i
        self.disclosures: dict[str, dict] = {}
        for d in data.get("disclosures", []):
            if isinstance(d, dict) and "seal" in d and opens(d, {"seal": d["seal"]}):
                self.disclosures[d["seal"]] = d
        self.agreements: dict[str, dict] = {}
        for c in self.chain_list:
            for e in c:
                ag = e.get("body", {}).get("agreement") if isinstance(e.get("body"), dict) else None
                if isinstance(ag, dict):
                    try:
                        self.agreements[content_hash(ag)] = ag
                    except Exception:
                        pass

    def reveal(self, x: Any) -> Any:
        if is_seal(x):
            d = self.disclosures.get(x["seal"])
            return d["value"] if d else SEALED
        return x

    def reveal_deep(self, x: Any) -> Any:
        if is_seal(x):
            return self.reveal(x)
        if isinstance(x, dict):
            return {k: self.reveal_deep(v) for k, v in x.items()}
        if isinstance(x, list):
            return [self.reveal_deep(v) for v in x]
        return x


# ---------------------------------------------------------------------------
# Agreement helpers
# ---------------------------------------------------------------------------

def parties(ag: dict) -> list[dict]:
    return ag.get("parties", [])


def party_keys(ag: dict) -> set[str]:
    return {p["party"]["key"] for p in parties(ag)}


def roles_of(ag: dict, key: str) -> set[str]:
    return {p["role"] for p in parties(ag) if p["party"]["key"] == key}


def keys_with_role(ag: dict, role: str) -> list[str]:
    return sorted(p["party"]["key"] for p in parties(ag) if p["role"] == role)


def resolve(x: Any, params: dict) -> Any:
    """Substitute {"param": name} references with the Clause's bound values."""
    if isinstance(x, dict):
        if set(x) == {"param"}:
            return params[x["param"]]
        return {k: resolve(v, params) for k, v in x.items()}
    if isinstance(x, list):
        return [resolve(v, params) for v in x]
    return x


def as_list(x: Any) -> list:
    return x if isinstance(x, list) else [x]


@dataclass
class ClauseForm:
    clause: dict
    term: dict
    form: dict  # resolved

    @property
    def name(self) -> str:
        return self.clause["n"]

    @property
    def kind(self) -> str:
        return self.form["form"]

    @property
    def tid(self) -> str:
        return self.term["id"]


def clause_forms(bundle: Bundle, ag: dict) -> list[ClauseForm]:
    out = []
    for c in ag.get("clauses", []):
        t = bundle.terms.get(c.get("def"))
        if not t:
            continue
        for f in t.get("forms", []):
            out.append(ClauseForm(c, t, resolve(f, c.get("params", {}))))
    return out


def find_clause(ag: dict, name: str) -> dict | None:
    for c in ag.get("clauses", []):
        if c.get("n") == name:
            return c
    return None


# ---------------------------------------------------------------------------
# Precedence (spec/04-inference.md §4)
# ---------------------------------------------------------------------------

def over_closure(ag: dict) -> dict[str, set[str]]:
    direct = {c["n"]: set(c.get("over", [])) for c in ag.get("clauses", [])}
    closure: dict[str, set[str]] = {}
    for n in direct:
        seen: set[str] = set()
        stack = list(direct[n])
        while stack:
            m = stack.pop()
            if m in seen:
                continue
            seen.add(m)
            stack.extend(direct.get(m, ()))
        closure[n] = seen
    return closure


def _val_items(cf: ClauseForm) -> set[str]:
    src = cf.form.get("source", {})
    if "table" in src:
        return {canon_key(r["item"]) for r in src["table"]}
    return {canon_key(i) for i in cf.form.get("items", [])}


def _during(cf: ClauseForm) -> tuple[str, str] | None:
    d = cf.form.get("during")
    return (d["start"], d["end"]) if d else None


def _intersects(a, b) -> bool:
    if a is None or b is None:
        return True
    return a[0] < b[1] and b[0] < a[1]


def _subset(a, b) -> bool:  # interval a within b (None = unbounded)
    if b is None:
        return True
    if a is None:
        return False
    return b[0] <= a[0] and a[1] <= b[1]


def conflict_key(cf: ClauseForm) -> str | None:
    if cf.kind == "Selection":
        return canon_key(["Selection", cf.form.get("subject"), cf.form.get("options")])
    if cf.kind == "Duty":
        return canon_key(["Duty", cf.form.get("duty"), cf.form.get("obligor"), cf.form.get("obligee")])
    return None


def governs(x: ClauseForm, y: ClauseForm, closure: dict[str, set[str]]) -> bool:
    """True if x takes precedence over y on their overlap."""
    if y.name in closure.get(x.name, ()):
        return True
    if y.name != x.name and x.name in closure.get(y.name, ()):
        return False
    if x.kind == "Valuation" and y.kind == "Valuation":
        xi, yi = _val_items(x), _val_items(y)
        xd, yd = _during(x), _during(y)
        if xi <= yi and _subset(xd, yd) and (xi < yi or (xd != yd and _subset(xd, yd))):
            return True
    return False


def precedence_issues(bundle: Bundle, ag: dict) -> list[str]:
    issues = []
    closure = over_closure(ag)
    names = {c["n"] for c in ag.get("clauses", [])}
    for c in ag.get("clauses", []):
        for o in c.get("over", []):
            if o not in names:
                issues.append(f"clause {c['n']!r} declares precedence over unknown clause {o!r}")
    for n, s in closure.items():
        if n in s:
            issues.append(f"precedence ('over') is circular through clause {n!r}")
    if issues:
        return issues
    cfs = clause_forms(bundle, ag)
    for i, x in enumerate(cfs):
        for y in cfs[i + 1:]:
            if x.name == y.name or x.kind != y.kind:
                continue
            if x.kind == "Valuation":
                overlap = bool(_val_items(x) & _val_items(y)) and _intersects(_during(x), _during(y))
            else:
                k = conflict_key(x)
                overlap = k is not None and k == conflict_key(y)
            if overlap and not (governs(x, y, closure) or governs(y, x, closure)):
                issues.append(f"clauses {x.name!r} and {y.name!r} conflict and neither takes precedence "
                              f"(no 'over' and neither is strictly more specific)")
    return issues


# ---------------------------------------------------------------------------
# Validation of content (A1, A6, A13)
# ---------------------------------------------------------------------------

def term_issues(t: dict) -> list[str]:
    issues = []
    if t.get("type") != "TermDefinition":
        issues.append("not a TermDefinition")
    for name, decl in t.get("params", {}).items():
        extra = set(decl) - {"type", "doc"}
        if extra:
            issues.append(f"parameter {name!r} declares {sorted(extra)}; only 'type' and 'doc' are allowed (A6: no defaults)")
        if not typecheck.known(decl.get("type")):
            issues.append(f"parameter {name!r} has an unrecognized type {decl.get('type')!r}")
    for ctype, cdecl in t.get("claims", {}).items():
        for fname, ftype in cdecl.get("data", {}).items():
            if not typecheck.known(ftype):
                issues.append(f"claim {ctype} field {fname!r} has an unrecognized type {ftype!r}")
    for f in t.get("forms", []):
        if f.get("form") not in FORMS:
            issues.append(f"unknown clause form {f.get('form')!r}")
    return issues


def agreement_issues(bundle: Bundle, ag: dict) -> list[tuple[str, str]]:
    """Return (rule, reason) pairs; empty means Valid(ag)."""
    out: list[tuple[str, str]] = []
    if not isinstance(ag, dict) or ag.get("type") != "Agreement":
        return [("A1", "the proposed object is not an Agreement")]
    if ag.get("spec") != SPEC:
        out.append(("A1", f"the Agreement declares spec {ag.get('spec')!r}, expected {SPEC!r}"))
    ps = parties(ag)
    if not ps:
        out.append(("A1", "the Agreement has no parties"))
    order = [(p.get("role"), p.get("party", {}).get("key")) for p in ps]
    if order != sorted(order):
        out.append(("A1", "parties are not sorted by (role, key)"))
    if len(set(order)) != len(order):
        out.append(("A1", "a party is listed twice in the same role"))
    for r, k in order:
        if r not in ROLES:
            out.append(("A1", f"unknown role {r!r}"))
        if not valid_key(k):
            out.append(("A1", f"malformed party key {k!r}"))
    names = [c.get("n") for c in ag.get("clauses", [])]
    if len(set(names)) != len(names):
        out.append(("A1", "clause names are not unique"))
    windows = links = 0
    for c in ag.get("clauses", []):
        t = bundle.terms.get(c.get("def"))
        if not t:
            out.append(("A1", f"clause {c.get('n')!r} pins a Term definition that is not in the bundle"))
            continue
        if t.get("id") != c.get("term"):
            out.append(("A1", f"clause {c.get('n')!r} names {c.get('term')!r} but pins {t.get('id')!r}"))
        if t.get("spec") != ag.get("spec"):
            out.append(("A1", f"clause {c.get('n')!r} uses a Term from spec {t.get('spec')!r}"))
        for issue in term_issues(t):
            out.append(("A6", f"Term {t.get('id')}: {issue}"))
        declared = set(t.get("params", {}))
        bound = set(c.get("params", {}))
        if declared != bound:
            missing, extra = declared - bound, bound - declared
            out.append(("A1", f"clause {c.get('n')!r}: parameters missing {sorted(missing)} / unexpected {sorted(extra)}"))
        for pname, pval in c.get("params", {}).items():
            ptype = t.get("params", {}).get(pname, {}).get("type", "")
            if contains_seal(pval) and ptype in STRUCTURAL_TYPES:
                out.append(("A10", f"clause {c.get('n')!r}: parameter {pname!r} ({ptype}) is structural and may not be sealed"))
            elif ptype == "Role" and pval not in ROLES:
                out.append(("A1", f"clause {c.get('n')!r}: {pval!r} is not a role"))
            elif ptype == "[Role]" and not (isinstance(pval, list) and all(r in ROLES for r in pval)):
                out.append(("A1", f"clause {c.get('n')!r}: {pname!r} must be a list of roles"))
            elif pname in t.get("params", {}) and typecheck.known(ptype):
                err = typecheck.check(ptype, pval, pname)
                if err:
                    out.append(("A1", f"clause {c.get('n')!r}: parameter {err}"))
        for f in t.get("forms", []):
            windows += f.get("form") == "Window"
            links += f.get("form") == "Link"
    if windows > 1:
        out.append(("A1", "more than one Window clause"))
    if links > 1:
        out.append(("A1", "more than one Link clause"))
    if not out:
        for issue in precedence_issues(bundle, ag):
            out.append(("A13", issue))
    return out


# ---------------------------------------------------------------------------
# Mandates (spec/01-domain.md §10)
# ---------------------------------------------------------------------------

def _bound_ok(bundle: Bundle, bound: dict, value: Any) -> tuple[bool, str]:
    if bound.get("any") is True:
        return True, "any value allowed"
    if is_seal(value) or contains_seal(value):
        return False, "the value is sealed, so it cannot be checked against the bound (rule 6: bounded values must be unsealed)"
    if "in" in bound:
        ok = any(canon_key(value) == canon_key(v) for v in bound["in"])
        return ok, f"{value!r} {'is' if ok else 'is not'} in the allowed set"
    if "max_period" in bound:
        # Compare periods by adding both to a fixed reference time.
        ref = "2000-01-01T00:00:00Z"
        ok = isinstance(value, dict) and add_period(ref, value) <= add_period(ref, bound["max_period"])
        return ok, f"period {'within' if ok else 'exceeds'} the maximum"
    if "min" in bound or "max" in bound:
        def num(v):
            if isinstance(v, dict) and "value" in v:
                return dec(v["value"]), v.get("currency")
            return dec(v), None
        try:
            v, cur = num(value)
        except Exception:
            return False, f"{value!r} is not a number or amount"
        for side in ("min", "max"):
            if side in bound:
                b, bcur = num(bound[side])
                if bcur != cur:
                    return False, "currency does not match the bound"
                if (side == "min" and v < b) or (side == "max" and v > b):
                    return False, f"{dec_str(v)} is {'below the minimum' if side == 'min' else 'above the maximum'} {dec_str(b)}"
        return True, "within bounds"
    return False, "unrecognized bound"


def mandate_coverage(bundle: Bundle, m: dict, agent_key: str, E: dict, ctx: dict) -> tuple[bool, str]:
    """ctx: {'agreement': Agreement whose roles apply, 'proposal': Agreement or None, 'claim': claim or None, 'chain': ChainId or None}"""
    if m.get("type") != "Mandate":
        return False, "the referenced object is not a Mandate"
    if not (valid_key(m.get("principal")) and valid_key(m.get("agent"))
            and typecheck.check("Time", m.get("not_before")) is None and typecheck.check("Time", m.get("expires")) is None):
        return False, "the Mandate is malformed (its keys or validity times are not well formed)"
    psig = [s for s in m.get("sigs", []) if s.get("key") == m.get("principal")]
    if not psig or not verify(m["principal"], psig[0]["sig"], m):
        return False, "the Mandate is not validly signed by its principal"
    if m.get("agent") != agent_key:
        return False, "the signing key is not the Mandate's agent"
    if not (m["not_before"] <= E["at"] < m["expires"]):
        return False, f"the Mandate is not in force at {E['at']} (valid {m['not_before']} to {m['expires']})"
    scope = m.get("scope", {})
    if E.get("kind") not in scope.get("kinds", []):
        return False, f"the Mandate does not allow '{E.get('kind')}' events"
    role_ag = ctx.get("agreement")
    if role_ag is None or not (roles_of(role_ag, m["principal"]) & set(scope.get("roles", []))):
        return False, "the principal does not hold a role the Mandate allows in this agreement"
    chains = scope.get("chains")
    if chains is not None and ctx.get("chain") not in chains:
        return False, "the Mandate does not cover this agreement's chain"
    prop = ctx.get("proposal")
    if prop is not None:
        terms = scope.get("terms", {})
        for c in prop.get("clauses", []):
            if c.get("term") not in terms:
                return False, f"the Mandate does not allow Term {c.get('term')}"
            bounds = terms[c["term"]]
            for pname, pval in c.get("params", {}).items():
                if pname not in bounds:
                    return False, f"the Mandate sets no bound for {c['term']} parameter '{pname}'"
                ok, why = _bound_ok(bundle, bounds[pname], pval)
                if not ok:
                    return False, f"{c['term']} parameter '{pname}': {why}"
    claim = ctx.get("claim")
    if claim is not None:
        claims = scope.get("claims", {})
        if claim.get("type") not in claims:
            return False, f"the Mandate does not allow claim {claim.get('type')}"
        bounds = claims[claim["type"]]
        for fname, fval in claim.get("data", {}).items():
            if fname not in bounds:
                return False, f"the Mandate sets no bound for claim field '{fname}'"
            ok, why = _bound_ok(bundle, bounds[fname], fval)
            if not ok:
                return False, f"claim field '{fname}': {why}"
    return True, "the Mandate covers this event"


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

@dataclass
class Step:
    index: int
    event: dict
    event_hash: str
    accepted: bool
    checks: list[Check]
    state: dict | None  # state after this step (unchanged if rejected)
    reason: str = ""


class Evaluator:
    def __init__(self, bundle: Bundle, unverified: Iterable[str] = ()):
        self.b = bundle
        self.unverified = set(unverified)  # event hashes whose signatures are hypothetical (simulation)
        self._runs: dict[str, list[Step]] = {}

    # ---- chain processing ----------------------------------------------

    def run(self, cid: str) -> list[Step]:
        if cid in self._runs:
            return self._runs[cid]
        self._runs[cid] = []  # guards against cycles
        steps: list[Step] = []
        S: dict | None = None
        for i, E in enumerate(self.b.chains.get(cid, [])):
            S2, checks, reason = self.apply(S, E)
            ok = S2 is not None
            if ok:
                S = S2
            steps.append(Step(i, E, content_hash(E), ok, checks, S, reason))
        self._runs[cid] = steps
        return steps

    def state_at(self, cid: str, t: str | None = None) -> dict | None:
        S = None
        for st in self.run(cid):
            if st.accepted and (t is None or st.event["at"] <= t):
                S = st.state
        return S

    def agreement(self, S: dict | None) -> dict | None:
        return self.b.agreements.get(S["agreement"]) if S else None

    # ---- signatures ----------------------------------------------------

    def principals(self, S, E, ck: Checks, ctx_for) -> dict[str, dict]:
        """Map each principal key to the signature that speaks for it (A9)."""
        out: dict[str, dict] = {}
        eh = content_hash(E)
        sigs = E.get("sigs", [])
        ck.check("sigs-present", "A9", isinstance(sigs, list) and len(sigs) > 0,
                 "The event carries signatures.", "The event carries no signatures.")
        for s in sigs:
            key = s.get("key", "")
            if eh not in self.unverified:
                ck.check(f"sig-{key[8:16]}", "A9", verify(key, s.get("sig", ""), E),
                         f"Signature by {key[:16]}… verifies over the event's hash.",
                         f"Signature by {key[:16]}… does not verify: the event was altered after signing, or the signature is missing or forged.")
            if "mandate" in s:
                m = self.b.mandates.get(s["mandate"])
                ck.check(f"mandate-{key[8:16]}", "A9", m is not None,
                         "The agent's Mandate is in the bundle.", "The agent cites a Mandate that is not in the bundle.")
                ok, why = mandate_coverage(self.b, m, key, E, ctx_for(m["principal"]))
                ck.check(f"mandate-cover-{key[8:16]}", "A9", ok,
                         f"Agent {key[:16]}… acts for {m['principal'][:16]}…: {why}.",
                         f"Agent {key[:16]}… is out of bounds: {why}. Out-of-bounds agent actions are invalid by definition.")
                out[m["principal"]] = s
            else:
                out[key] = s
        return out

    # ---- the transition function (spec/04-inference.md §1) -------------

    def apply(self, S: dict | None, E: dict) -> tuple[dict | None, list[Check], str]:
        ck = Checks()
        try:
            S2 = self._apply(S, E, ck)
            return S2, ck.items, ""
        except Reject as r:
            return None, ck.items, str(r)
        except Exception as ex:  # malformed input is a rejection, never a crash
            ck.items.append(Check("malformed", "A1", False, f"The event is malformed: {type(ex).__name__}: {ex}"))
            return None, ck.items, f"malformed event: {ex}"

    def _apply(self, S, E, ck: Checks) -> dict:
        ck.check("envelope", "A1",
                 isinstance(E, dict) and E.get("type") == "Event" and E.get("spec") == SPEC and E.get("kind") in KINDS,
                 "The record is a well-formed Universal Paper event.",
                 "The record is not a well-formed Universal Paper event of this spec version.")
        kind, body = E["kind"], E.get("body", {})
        eh = content_hash(E)
        if S is None:
            ck.check("linkage", "A3", "chain" not in E and "prev" not in E,
                     "This is a genesis event: it starts a new chain.",
                     "This event continues a chain that has no valid starting event in this copy, so it cannot apply.")
            ck.check("genesis-kind", "A3", kind == "propose" and "supersedes" not in body,
                     "The genesis event is a proposal.", "The first event of a chain must be a proposal of a new agreement.")
        else:
            ck.check("linkage", "A3", E.get("chain") == S["chain"] and E.get("prev") == content_hash(S),
                     "The event references this chain and the exact prior state hash.",
                     "The event does not reference the current state hash: it was built on a different history.")
            ck.check("time", "A5", parse_time(E["at"]) >= parse_time(S["at"]),
                     "The event's time is not earlier than the previous event.",
                     f"The event is backdated ({E['at']} is before the previous event at {S['at']}). Past states cannot be altered.")
        parse_time(E["at"])
        cur = self.agreement(S)
        pend = self.b.agreements.get(S["pending"]["agreement"]) if S and S.get("pending") else None
        prop = body.get("agreement") if kind == "propose" else None
        cid = S["chain"] if S else eh

        target_claim = None
        if kind == "accept" and S and not (S.get("pending") and body.get("target") == S["pending"]["event"]):
            target_claim = self._find_claim(S, body.get("target"))

        def ctx_for(principal: str) -> dict:
            if kind == "propose":
                return {"agreement": prop if principal in party_keys(prop or {}) else cur, "proposal": prop, "chain": S["chain"] if S else None}
            if kind == "accept" and target_claim is None:
                return {"agreement": pend or cur, "proposal": pend, "chain": cid}
            if kind == "accept":
                return {"agreement": cur, "claim": {"type": target_claim[1]["type"], "data": target_claim[1]["data"]}, "chain": cid}
            return {"agreement": cur, "claim": body.get("claim"), "chain": cid}

        P = self.principals(S, E, ck, ctx_for)
        ck.check("author", "A9", E.get("by") in P,
                 "A valid signature speaks for the event's author.",
                 "No valid signature speaks for the event's author.")
        known = party_keys(cur or {}) | party_keys(pend or {}) | party_keys(prop or {})
        unknown = [k for k in P if k not in known]
        ck.check("signers-known", "A9", not unknown,
                 "Every signer is a party to this agreement (directly or through a Mandate).",
                 f"Signer {unknown[0][:16]}… is not a party to this agreement." if unknown else "")

        if kind == "propose":
            return self._propose(S, E, eh, P, cur, ck)
        if kind == "accept":
            return self._accept(S, E, eh, P, pend, cur, target_claim, ck)
        return self._attest(S, E, eh, P, cur, ck)

    # ---- propose (spec/05-lifecycle.md §2.1, §2.2) ----------------------

    def _check_agreement(self, ag, ck: Checks, at: str) -> None:
        issues = agreement_issues(self.b, ag)
        for rule, why in issues:
            ck.check(f"valid-{rule}", rule, False, "", f"The proposed agreement is invalid: {why}.")
        ck.check("valid", "A1", True, "The proposed agreement is well formed and uses one spec version (A1, A6).", "")
        ck.check("precedence", "A13", True, "Every conflict between clauses is resolved by explicit precedence or specificity.", "")
        self._check_link(ag, ck, at)

    def _check_link(self, ag, ck: Checks, at: str) -> None:
        for cf in clause_forms(self.b, ag):
            if cf.kind != "Link":
                continue
            parent = cf.form["parent"]
            ck.check("link-parent", "F-Link", parent in self.b.chains,
                     "The parent agreement's chain is in the bundle.", "The parent agreement's chain is not in the bundle.")
            PS = self.state_at(parent, at)
            ck.check("link-executed", "F-Link", PS is not None and PS["status"] == "executed",
                     "The parent agreement is executed.", "The parent agreement is not executed at this time.")
            pag = self.agreement(PS)
            for role in cf.form.get("bind", []):
                ck.check(f"link-bind-{role}", "F-Link", keys_with_role(ag, role) == keys_with_role(pag, role),
                         f"The parent's {role} is a party here in the same role, so it must sign.",
                         f"The {role} here is not the parent agreement's {role}.")

    def _propose(self, S, E, eh, P, cur, ck: Checks) -> dict:
        body = E["body"]
        ag = body.get("agreement")
        if S is None:
            ck.check("propose-author", "R-propose", E["by"] in party_keys(ag or {}),
                     "The proposer is a party to the proposed agreement.", "The proposer is not a party to the proposed agreement.")
            self._check_agreement(ag, ck, E["at"])
            required = party_keys(ag)
            S2 = {"type": "State", "spec": SPEC, "chain": eh, "height": 0, "status": "proposed",
                  "agreement": content_hash(ag), "facts": {}}
        else:
            ck.check("amend-executed", "R-propose", S["status"] == "executed",
                     "The current agreement is executed, so it can be amended.", "Only an executed agreement can be amended.")
            ck.check("amend-supersedes", "R-propose", body.get("supersedes") == S["agreement"],
                     "The amendment names the current agreement it replaces.", "The amendment does not supersede the current agreement.")
            ck.check("amend-author", "R-propose", E["by"] in party_keys(cur),
                     "The proposer is a party to the current agreement.", "The proposer is not a party to the current agreement.")
            self._check_agreement(ag, ck, E["at"])
            required = party_keys(ag) | party_keys(cur)
            S2 = copy.deepcopy(S)
        pending = {"event": eh, "agreement": content_hash(ag), "signed": sorted(k for k in P if k in required)}
        if "expires" in body:
            ck.check("propose-expires", "R-propose", typecheck.check("Time", body["expires"]) is None,
                     "The proposal's expiry is a well-formed time.",
                     "The proposal's expiry is not a well-formed time.")
            pending["expires"] = body["expires"]
        S2["pending"] = pending
        S2 = self._advance(S2, E, eh)
        return self._maybe_execute(S2, E, ck)

    def _required(self, S) -> set[str]:
        new = self.b.agreements[S["pending"]["agreement"]]
        req = party_keys(new)
        if S["status"] == "executed":
            req |= party_keys(self.b.agreements[S["agreement"]])
        return req

    def _maybe_execute(self, S2, E, ck: Checks) -> dict:
        req = self._required(S2)
        signed = set(S2["pending"]["signed"])
        if req <= signed:
            new_ag = self.b.agreements[S2["pending"]["agreement"]]
            self._check_link(new_ag, ck, E["at"])
            ck.check("unanimity", "A2", True,
                     "Every required party has now signed the same agreement hash: the agreement is executed.", "")
            if S2["status"] == "executed":
                old = self.b.agreements[S2["agreement"]]
                old_terms = {c["n"]: c["def"] for c in old["clauses"]}
                new_terms = {c["n"]: c["def"] for c in new_ag["clauses"]}
                S2["facts"] = {n: v for n, v in S2["facts"].items() if new_terms.get(n) == old_terms.get(n) and n in new_terms}
            else:
                S2["executed_at"] = E["at"]
            S2["status"] = "executed"
            S2["agreement"] = S2["pending"]["agreement"]
            del S2["pending"]
        else:
            ck.check("unanimity", "A2", True,
                     f"Signatures recorded: {len(signed & req)} of {len(req)} required parties have signed.", "")
        return S2

    def _advance(self, S2, E, eh) -> dict:
        S2["height"] = S2.get("height", 0) + 1
        S2["last"] = eh
        S2["at"] = E["at"]
        return S2

    # ---- accept (spec/05-lifecycle.md §2.3, §2.5) -----------------------

    def _find_claim(self, S, target) -> tuple[str, dict] | None:
        for cname, f in S.get("facts", {}).items():
            for c in f.get("claims", []):
                if c["event"] == target:
                    return cname, c
        return None

    def _accept(self, S, E, eh, P, pend, cur, target_claim, ck: Checks) -> dict:
        ck.check("accept-chain", "R-accept", S is not None, "The acceptance belongs to an existing chain.", "An acceptance cannot start a chain.")
        target = E["body"].get("target")
        if S.get("pending") and target == S["pending"]["event"]:
            req = self._required(S)
            ck.check("accept-required", "R-accept", E["by"] in req,
                     "The accepting party is a required signer of the proposal.", "The accepting party is not a required signer of the proposal.")
            ck.check("accept-new", "R-accept", E["by"] not in S["pending"]["signed"],
                     "The accepting party has not already signed.", "The accepting party has already signed this proposal.")
            exp = S["pending"].get("expires")
            ck.check("accept-unexpired", "R-accept", exp is None or E["at"] < exp,
                     "The proposal has not lapsed.", f"The proposal lapsed at {exp}.")
            S2 = copy.deepcopy(S)
            S2["pending"]["signed"] = sorted(set(S2["pending"]["signed"]) | {k for k in P if k in req})
            S2 = self._advance(S2, E, eh)
            return self._maybe_execute(S2, E, ck)
        ck.check("accept-target", "R-accept", target_claim is not None,
                 "The acceptance acknowledges an earlier attestation in this chain.",
                 "The acceptance targets neither the pending proposal nor an attestation in this chain.")
        cname, claim = target_claim
        S2 = copy.deepcopy(S)
        claim2 = next(c for c in S2["facts"][cname]["claims"] if c["event"] == target)
        ack_roles = self._ack_roles(cur, cname, claim["type"], claim)
        mine = roles_of(cur, E["by"]) & ack_roles
        ck.check("ack-role", "R-accept", bool(mine),
                 f"The acknowledging party holds a role ({', '.join(sorted(mine))}) whose acknowledgment this claim needs.",
                 "The acknowledging party holds no role whose acknowledgment this claim needs.")
        ck.check("ack-new", "R-accept", all(a["by"] != E["by"] for a in claim2["acks"]),
                 "The party has not already acknowledged this claim.", "The party has already acknowledged this claim.")
        claim2["acks"] = sorted(claim2["acks"] + [{"by": E["by"], "at": E["at"], "event": eh}], key=lambda a: a["by"])
        self._after_ack(S2, cur, cname, claim2, ck)
        return self._advance(S2, E, eh)

    # ---- attest (spec/05-lifecycle.md §2.4) ------------------------------

    def _claim_rules(self, ag, cname) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
        """For a clause: claim type -> roles that may attest it; claim type -> roles whose ack it needs."""
        attest: dict[str, set[str]] = {}
        ack: dict[str, set[str]] = {}
        for cf in clause_forms(self.b, ag):
            if cf.name != cname:
                continue
            f, tid = cf.form, cf.tid
            if f["form"] == "Window" and "renew" in f:
                attest.setdefault(f"{tid}/optout", set()).update(f["renew"]["optout_roles"])
            elif f["form"] == "Exit":
                attest.setdefault(f"{tid}/notice", set()).update(f["holders"])
                if "requires" in f:
                    attest.setdefault(f["requires"]["claim"], set()).update(f["holders"])
                    attest.setdefault(f["requires"]["unless"], set()).update(ROLES)
                    ack.setdefault(f["requires"]["unless"], set()).update(f["holders"])
            elif f["form"] == "Selection":
                attest.setdefault(f"{tid}/selects", set()).add(f["subject"])
                ack.setdefault(f"{tid}/selects", set()).update(f.get("ack", []))
            elif f["form"] == "Valuation" and "reference" in f.get("source", {}):
                r = f["source"]["reference"]
                attest.setdefault(r["claim"], set()).add(r["role"])
            elif f["form"] == "Duty":
                d = f["discharge"]
                attest.setdefault(d["claim"], set()).add(f["obligor"])
                ack.setdefault(d["claim"], set()).update(as_list(d.get("ack", [])))
                if "on" in f["trigger"]:
                    attest.setdefault(f["trigger"]["on"], set()).update(f["trigger"]["by"])
        return attest, ack

    def _ack_roles(self, ag, cname, ctype, claim=None) -> set[str]:
        return self._claim_rules(ag, cname)[1].get(ctype, set())

    def _attest(self, S, E, eh, P, cur, ck: Checks) -> dict:
        ck.check("attest-chain", "R-attest", S is not None and S["status"] == "executed",
                 "The agreement is executed, so claims can be recorded under it.",
                 "Claims can only be recorded under an executed agreement.")
        claim = E["body"].get("claim", {})
        cname, ctype, data = claim.get("clause"), claim.get("type"), claim.get("data")
        clause = find_clause(cur, cname)
        ck.check("attest-clause", "R-attest", clause is not None,
                 f"The claim is made under clause '{cname}' of the current agreement.",
                 f"The current agreement has no clause named '{cname}'.")
        term = self.b.terms[clause["def"]]
        decl = term.get("claims", {}).get(ctype)
        ck.check("attest-type", "A11", decl is not None,
                 f"'{ctype}' is a claim type that this clause's Term defines.",
                 f"'{ctype}' is not a claim type defined by Term {term['id']}.")
        ck.check("attest-data", "R-attest", isinstance(data, dict) and set(data) == set(decl.get("data", {})),
                 "The claim's data has exactly the fields its Term defines.",
                 f"The claim's data fields {sorted(data) if isinstance(data, dict) else data} do not match {sorted(decl.get('data', {}))}.")
        bad = next((err for fname, ftype in decl.get("data", {}).items()
                    for err in [typecheck.check(ftype, data[fname], fname) if typecheck.known(ftype) else f"{fname} has an unrecognized type"]
                    if err), None)
        ck.check("attest-data-types", "R-attest", bad is None,
                 "Each data field has the type its Term declares.",
                 f"The claim's data does not match its Term: {bad}.")
        attest_roles, ack_roles = self._claim_rules(cur, cname)
        allowed = attest_roles.get(ctype, set())
        mine = roles_of(cur, E["by"]) & allowed
        ck.check("attest-role", "A7", bool(mine),
                 f"The author holds a role allowed to make this claim ({', '.join(sorted(mine))}).",
                 f"The author holds no role allowed to make this claim (allowed: {', '.join(sorted(allowed)) or 'none'}).")
        needed = ack_roles.get(ctype, set())
        acks = []
        for k in sorted(P):
            if k == E["by"]:
                continue
            ck.check(f"cosign-{k[8:16]}", "R-attest", bool(roles_of(cur, k) & needed),
                     "The co-signer's signature counts as an acknowledgment.",
                     "A co-signer holds no role whose acknowledgment this claim needs.")
            acks.append({"by": k, "at": E["at"], "event": eh})
        rec = {"event": eh, "type": ctype, "by": E["by"], "at": E["at"], "data": data, "acks": acks}
        S2 = copy.deepcopy(S)
        self._form_effects(S2, E, cur, cname, rec, ck)
        S2["facts"].setdefault(cname, {"claims": []})["claims"].append(rec)
        self._after_ack(S2, cur, cname, rec, ck)
        return self._advance(S2, E, eh)

    def _form_effects(self, S2, E, cur, cname, rec, ck: Checks) -> None:
        for cf in clause_forms(self.b, cur):
            if cf.name != cname:
                continue
            f, tid = cf.form, cf.tid
            if f["form"] == "Exit" and rec["type"] == f"{tid}/notice":
                if "requires" in f:
                    req = f["requires"]
                    claims = S2["facts"].get(cname, {}).get("claims", [])
                    ok = False
                    for b in claims:
                        if b["type"] != req["claim"] or b["by"] != rec["by"]:
                            continue
                        if rec["data"].get("breach") not in (None, b["event"]):
                            continue
                        if add_period(b["at"], req["age"]) > rec["at"]:
                            continue
                        cured = any(c["type"] == req["unless"] and c["data"].get("breach") == b["event"]
                                    and any(a["by"] == rec["by"] for a in c["acks"]) for c in claims)
                        if not cured:
                            ok = True
                    ck.check("exit-requires", "F-Exit", ok,
                             "An earlier breach notice by this party is old enough and has not been acknowledged as cured.",
                             "Termination for cause needs an earlier breach notice by this party, older than the cure period and not acknowledged as cured.")
                end = add_period(rec["at"], f["notice"])
                S2["ends_at"] = min(S2.get("ends_at", end), end)
                ck.check("exit-effect", "F-Exit", True, f"Termination takes effect at {S2['ends_at']}.", "")
            if f["form"] == "Selection" and rec["type"] == f"{tid}/selects":
                opts = self.options(cur, f)
                ck.check("selection-option", "F-Selection", rec["data"].get("option") in opts,
                         f"'{rec['data'].get('option')}' is one of the named options.",
                         f"'{rec['data'].get('option')}' is not one of the named options ({', '.join(opts)}).")
            if f["form"] == "Duty" and "on" in f["trigger"] and rec["type"] == f["trigger"]["on"]:
                lim = f["trigger"].get("limit")
                if lim:
                    prior = [c for c in S2["facts"].get(cname, {}).get("claims", [])
                             if c["type"] == rec["type"] and add_period(c["at"], lim["per"]) > rec["at"]]
                    ck.check("duty-limit", "F-Duty", len(prior) < int(lim["count"]),
                             f"This request is within the limit of {lim['count']} per period.",
                             f"This request exceeds the limit of {lim['count']} per period.")

    def _after_ack(self, S2, cur, cname, rec, ck: Checks) -> None:
        pass  # Effects that depend on acknowledgments are computed on demand from the recorded acks.

    # ---- derived values (spec/02, spec/04 §3) ---------------------------

    def options(self, ag: dict, sel_form: dict) -> list[str]:
        src = sel_form["options"]
        if isinstance(src, list):
            return [o["name"] for o in src]
        ref = src["from"]
        target_ag = ag
        if ref.get("link"):
            link = next((cf for cf in clause_forms(self.b, ag) if cf.kind == "Link"), None)
            if not link:
                return []
            target_ag = self.agreement(self.state_at(link.form["parent"]))
        for cf in clause_forms(self.b, target_ag or {}):
            if cf.name == ref["clause"]:
                opts = cf.form.get("options") or cf.form.get("source", {}).get("options") or []
                return [o["name"] for o in opts]
        return []

    def window(self, cid: str, t: str) -> tuple[str | None, str | None]:
        S = self.state_at(cid, t)
        ag = self.agreement(S)
        if not S or S["status"] != "executed":
            return None, None
        w = next((cf for cf in clause_forms(self.b, ag) if cf.kind == "Window"), None)
        if not w:
            start, end = S["executed_at"], None
        else:
            start, end = w.form["start"], w.form["end"]
            r = w.form.get("renew")
            if r:
                # e_k = end + k x period, each computed directly from end (spec/04-inference.md §2, §3.1).
                optouts = [c for c in S["facts"].get(w.name, {}).get("claims", []) if c["type"] == f"{w.tid}/optout"]
                e0, n = end, 0
                while end <= t and (r.get("max") is None or n < int(r["max"])):
                    if any(add_period(c["at"], r["optout_notice"]) <= end for c in optouts):
                        break
                    n += 1
                    end = add_period(e0, r["period"], n)
        if S.get("ends_at") and (end is None or S["ends_at"] < end):
            end = S["ends_at"]
        return start, end

    def parents(self, cid: str, t: str) -> list[str]:
        ag = self.agreement(self.state_at(cid, t))
        return [cf.form["parent"] for cf in clause_forms(self.b, ag or {}) if cf.kind == "Link"]

    def active(self, cid: str, t: str) -> bool:
        S = self.state_at(cid, t)
        if not S or S["status"] != "executed":
            return False
        start, end = self.window(cid, t)
        if not (start <= t and (end is None or t < end)):
            return False
        return all(self.active(p, t) for p in self.parents(cid, t))

    def status(self, cid: str, t: str) -> str:
        S = self.state_at(cid, t)
        if S is None:
            return "none"
        if S["status"] == "proposed":
            exp = S.get("pending", {}).get("expires")
            return "lapsed" if exp and t >= exp else "proposed"
        start, end = self.window(cid, t)
        if S.get("ends_at") and t >= S["ends_at"]:
            return "terminated"
        if end is not None and t >= end:
            return "expired"
        if t < start:
            return "executed"
        if not all(self.active(p, t) for p in self.parents(cid, t)):
            return "suspended"
        return "active"

    def _acks_complete(self, ag, rec, roles: set[str]) -> str | None:
        """Time the last needed acknowledgment arrived, or None if incomplete."""
        last = None
        for role in roles:
            hits = [a for a in rec["acks"] if role in roles_of(ag, a["by"])]
            if not hits:
                return None
            first = min(a["at"] for a in hits)
            last = first if last is None or first > last else last
        return last or rec["at"]

    def selection(self, cid: str, cname: str, key: str, t: str) -> str | None:
        S = self.state_at(cid, t)
        ag = self.agreement(S)
        if not ag:
            return None
        cf = next((x for x in clause_forms(self.b, ag) if x.name == cname and x.kind == "Selection"), None)
        if not cf:
            return None
        f = cf.form
        best = None
        for i, c in enumerate(S["facts"].get(cname, {}).get("claims", [])):
            if c["type"] != f"{cf.tid}/selects" or c["by"] != key:
                continue
            at = self._acks_complete(ag, c, set(f.get("ack", [])))
            if at is None:
                continue
            eff = at
            if isinstance(f.get("effective"), dict):
                start, _ = self.window(cid, t)
                k = 0
                while add_period(start, f["effective"]["next"], k) <= at:
                    k += 1
                eff = add_period(start, f["effective"]["next"], k)
            if eff <= t and (best is None or (eff, i) >= (best[0], best[1])):
                best = (eff, i, c["data"]["option"])
        if best:
            return best[2]
        return f.get("initial")

    def _valuations_for(self, ag, item, t) -> list[ClauseForm]:
        ik = canon_key(item)
        out = []
        for cf in clause_forms(self.b, ag):
            if cf.kind != "Valuation" or ik not in _val_items(cf):
                continue
            d = _during(cf)
            if d and not (d[0] <= t < d[1]):
                continue
            out.append(cf)
        return out

    def value(self, cid: str, item: dict, option: str | None, t: str):
        S = self.state_at(cid, t)
        ag = self.agreement(S)
        if not ag:
            return None
        cands = self._valuations_for(ag, item, t)
        if not cands:
            return None
        closure = over_closure(ag)
        gov = next((x for x in cands if all(x is y or governs(x, y, closure) for y in cands)), cands[0])
        src = gov.form["source"]
        if "table" in src:
            row = next(r for r in src["table"] if canon_key(r["item"]) == canon_key(item))
            by = self.b.reveal(row["by"])
            if by is SEALED:
                return SEALED
            amt = by.get(option) if option else None
            return self.b.reveal(amt) if amt is not None else None
        ref = src["reference"]
        lists = [c for c in S["facts"].get(gov.name, {}).get("claims", [])
                 if c["type"] == ref["claim"] and ref["role"] in roles_of(ag, c["by"]) and c["data"]["effective"] <= t]
        if not lists:
            return None
        latest = max(enumerate(lists), key=lambda ic: (ic[1]["data"]["effective"], ic[0]))[1]
        entry = next((p for p in latest["data"]["prices"] if canon_key(p["item"]) == canon_key(item)), None)
        if entry is None:
            return None
        price, factor = self.b.reveal(entry["price"]), self.b.reveal(ref["factor"])
        if price is SEALED or factor is SEALED:
            return SEALED
        v = round_dec(dmul(dec(price["value"]), dec(factor)), ref["rounding"])
        return {"value": dec_str(v), "currency": price["currency"]}

    def price(self, pid: str, item: dict, t: str):
        """price(item, P, t) for participation chain P (spec/02 §3)."""
        S = self.state_at(pid, t)
        ag = self.agreement(S)
        if not ag:
            return None
        parents = self.parents(pid, t)
        if not parents:
            return None
        sel = next((cf for cf in clause_forms(self.b, ag) if cf.kind == "Selection"), None)
        member = keys_with_role(ag, sel.form["subject"])[0] if sel else None
        option = self.selection(pid, sel.name, member, t) if sel else None
        return self.value(parents[0], item, option, t)

    def obligations(self, cid: str, t: str) -> list[dict]:
        S = self.state_at(cid, t)
        ag = self.agreement(S)
        if not S or S["status"] != "executed":
            return []
        cfs = clause_forms(self.b, ag)
        closure = over_closure(ag)
        duties = [cf for cf in cfs if cf.kind == "Duty"]
        live = [d for d in duties if not any(o is not d and conflict_key(o) == conflict_key(d) and governs(o, d, closure) for o in duties)]
        start, end = self.window(cid, t)
        out = []
        for d in live:
            f = d.form
            for obligor in keys_with_role(ag, f["obligor"]):
                for obligee in keys_with_role(ag, f["obligee"]):
                    for period, due, trig in self._duty_periods(S, d, start, end, t):
                        out.append(self._commitment(S, ag, d, obligor, obligee, period, due, trig, t))
        return out

    def _duty_periods(self, S, d: ClauseForm, start, end, t):
        f = d.form
        if "every" in f["trigger"]:
            k = 0
            while k < 10000:
                b0 = add_period(start, f["trigger"]["every"], k)
                b1 = add_period(start, f["trigger"]["every"], k + 1)
                if (end is not None and b0 >= end) or b1 > t:
                    break
                if b1 > S["executed_at"]:
                    yield {"start": b0, "end": b1}, add_period(b1, f["due"]), None
                k += 1
        else:
            for c in S["facts"].get(d.name, {}).get("claims", []):
                if c["type"] == f["trigger"]["on"]:
                    yield {"start": c["at"], "end": c["at"]}, add_period(c["at"], f["due"]), c["event"]

    def _commitment(self, S, ag, d: ClauseForm, obligor, obligee, period, due, trig, t) -> dict:
        f = d.form
        com = {"chain": S["chain"], "clause": d.name, "duty": f["duty"],
               "obligor": {"role": f["obligor"], "key": obligor},
               "obligee": {"role": f["obligee"], "key": obligee},
               "period": period, "due": due}
        if trig:
            com["trigger"] = trig
        owed = None
        if "amount" in f:
            a = f["amount"]
            base = [c for c in S["facts"].get(a["base"].get("clause", d.name), {}).get("claims", [])
                    if c["type"] == a["base"]["claim"] and c["data"].get("period") == period]
            if base:
                vals = [self.b.reveal(c["data"][a["base"]["field"]]) for c in base]
                rate = self.b.reveal(a["rate"])
                if SEALED in vals or rate is SEALED:
                    owed = SEALED
                else:
                    curs = {v["currency"] for v in vals}
                    if len(curs) == 1:
                        total = dsum(dec(v["value"]) for v in vals)
                        owed = {"value": dec_str(round_dec(dmul(total, dec(rate)), a["rounding"])), "currency": curs.pop()}
            com["amount"] = "sealed" if owed is SEALED else owed if owed else "no base reported yet"
        dis = f["discharge"]
        ack_roles = set(as_list(dis.get("ack", [])))
        status = None
        for c in S["facts"].get(d.name, {}).get("claims", []):
            if c["type"] != dis["claim"] or c["by"] != obligor:
                continue
            if trig:
                if c["data"].get("request") != trig:
                    continue
            elif c["data"].get("period") != period:
                continue
            done_at = self._acks_complete(ag, c, ack_roles)
            if done_at is None or done_at > t:
                continue
            if "amount" in f:
                paid = self.b.reveal(c["data"].get("amount"))
                if owed is SEALED or paid is SEALED:
                    status = status or "sealed"
                    continue
                if not isinstance(owed, dict) or paid.get("currency") != owed["currency"] or dec(paid["value"]) < dec(owed["value"]):
                    continue
            status = "discharged"
            com["discharged_at"] = done_at
            com["late"] = done_at > due
            break
        com["status"] = status or ("overdue" if t >= due else "open")
        return com
