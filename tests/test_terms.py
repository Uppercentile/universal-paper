"""Every Term in the library: its files, its hash, and every claim type it defines, exercised end to end.

The examples and the proving ground use only some Terms. These tests make sure each of the
sixteen Terms can be used in a valid, executed Agreement, that every parameter is type-checked,
and that every claim type it declares is accepted when well formed and rejected when not.
"""
import copy
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from universal_paper.build import World, load_terms
from universal_paper.canon import content_hash
from universal_paper.engine import agreement_issues
from universal_paper.typecheck import known

from build_examples import ITEMS, master_clauses, participation_clauses
from helpers import AGG, MEM, SUP, ev, master, raw
from samples import mutate, sample

ROOT = Path(__file__).resolve().parent.parent
TERMS = load_terms()
PARTICIPATION_LAYER = {"UP:Participation", "UP:Tier-Selection", "UP:Fee-Disclosure", "UP:Purchase-Commitment"}


def test_library_has_sixteen_terms_and_every_type_is_known():
    assert len(TERMS) == 16
    for t in TERMS.values():
        for name, decl in t["params"].items():
            assert known(decl["type"]), (t["id"], name)
        for ctype, c in t["claims"].items():
            assert ctype.startswith(t["id"] + "/")
            for fname, ftype in c["data"].items():
                assert known(ftype), (ctype, fname)


def test_term_files_are_generated_and_hashes_are_published(tmp_path):
    # gen_terms.py is the single source; regenerating must not change any file.
    before = {p.name: p.read_bytes() for p in (ROOT / "spec" / "06-terms").iterdir()}
    subprocess.run([sys.executable, str(ROOT / "tools" / "gen_terms.py")], check=True)
    after = {p.name: p.read_bytes() for p in (ROOT / "spec" / "06-terms").iterdir()}
    assert before == after, "spec/06-terms is out of date: run python3 tools/gen_terms.py"
    assert load_terms() == load_terms(ROOT / "spec" / "06-terms")  # the packaged copy matches the spec
    readme = (ROOT / "spec" / "06-terms" / "README.md").read_text()
    for t in TERMS.values():
        assert f"| `{t['id']}` | `{content_hash(t)}` |" in readme


def _params(w, tid, r):
    t = TERMS[tid]
    p = {name: sample(decl["type"], r) for name, decl in t["params"].items()}
    # Cross-references and structural choices that random samples cannot know.
    fix = {
        "UP:Fixed-Term": {"start": "2027-01-01T00:00:00Z", "end": "2028-01-01T00:00:00Z"},
        "UP:Renewing-Term": {"start": "2027-01-01T00:00:00Z", "end": "2028-01-01T00:00:00Z", "optout_roles": ["supplier"]},
        "UP:Termination-Convenience": {"holders": ["aggregator", "supplier", "member"]},
        "UP:Termination-Cause": {"holders": ["aggregator", "supplier", "member"], "cure_period": {"unit": "day", "count": 30}},
        "UP:Tiers": {"tiers": [{"name": "X", "conditions": "Hypothetical"}],
                     "prices": [{"item": {"scheme": "GTIN", "id": "09999999999999"}, "by": {"X": {"value": "1.00", "currency": "USD"}}}]},
        "UP:Price-Reference": {"items": [{"scheme": "GTIN", "id": "08888888888888"}], "list_role": "supplier"},
        "UP:Admin-Fee": {"report_clause": "reporting"},
        "UP:Tier-Selection": {"tiers_clause": "tiers", "initial": "C"},
        "UP:Audit": {"auditor": "aggregator", "auditee": "supplier"},
        "UP:Sales-Reporting": {"reporter": "supplier", "recipient": "aggregator"},
    }.get(tid, {})
    p.update(fix)
    return p


def _world_with(tid, r):
    """A World whose last chain is an executed Agreement that uses Term tid in clause 'x'."""
    w = World()
    a, _, _ = master(w)
    if tid in PARTICIPATION_LAYER:
        base = participation_clauses(w, w.chain_id(a), "2027-01-01T00:00:00Z")
        parties = [("aggregator", AGG), ("member", MEM), ("supplier", SUP)]
    else:
        base = [c for c in master_clauses(w) if c["n"] in ("reporting", "fee", "notices")]
        parties = [("aggregator", AGG), ("supplier", SUP)]
        if tid in ("UP:Tier-Selection", "UP:Fee-Disclosure"):
            parties.append(("member", MEM))
    forms = {f["form"] for f in TERMS[tid]["forms"]}
    keep = []
    for c in base:
        cforms = {f["form"] for f in TERMS[c["term"]]["forms"]}
        if c["term"] == tid or (forms & cforms & {"Window", "Link", "Selection"}):
            continue
        keep.append(c)
    clause = w.clause("x", tid, _params(w, tid, r))
    if tid == "UP:Participation":
        clause["params"]["parent"] = w.chain_id(a)
    A = w.agreement(parties, keep + [clause], f"uses {tid}")
    proposer = MEM if tid in PARTICIPATION_LAYER else AGG
    others = [actor for _, actor in parties if actor is not proposer]
    pos, _ = w.propose(proposer, A, "2026-12-15T00:00:00Z", cosigners=others)
    return w, pos, A


@pytest.mark.parametrize("tid", sorted(TERMS))
def test_every_term_executes_in_a_valid_agreement(tid):
    w, pos, A = _world_with(tid, random.Random(tid))
    e = ev(w)
    assert agreement_issues(e.b, A) == []
    assert e.state_at(w.chain_id(pos))["status"] == "executed"


@pytest.mark.parametrize("tid", sorted(TERMS))
def test_every_parameter_of_every_term_is_type_checked(tid):
    r = random.Random("params " + tid)
    w, pos, A = _world_with(tid, r)
    b = ev(w).b
    clause = next(c for c in A["clauses"] if c["n"] == "x")
    for name, decl in TERMS[tid]["params"].items():
        for _ in range(4):
            bad = copy.deepcopy(A)
            c = next(c for c in bad["clauses"] if c["n"] == "x")
            c["params"][name] = mutate(clause["params"][name], r)
            if known(decl["type"]):
                from universal_paper.typecheck import check
                if check(decl["type"], c["params"][name]) is None:
                    continue  # the mutation happened to stay well typed
            assert agreement_issues(b, bad), (tid, name, c["params"][name])


def _claim_data(tid, ctype, r, w, pos):
    t = TERMS[tid]
    data = {f: sample(ft, r) for f, ft in t["claims"][ctype]["data"].items()}
    if ctype == "UP:Tier-Selection/selects":
        data["option"] = "B"
    for f, ft in t["claims"][ctype]["data"].items():
        if ft == "Hash":  # refer to an earlier event of this chain
            data[f] = w.chain_id(pos)
    return data


CLAIMS = [(tid, ctype) for tid in sorted(TERMS) for ctype in sorted(TERMS[tid]["claims"])]


@pytest.mark.parametrize("tid,ctype", CLAIMS)
def test_every_claim_type_is_accepted_when_well_formed_and_rejected_when_not(tid, ctype):
    r = random.Random(ctype)
    w, pos, A = _world_with(tid, r)
    e = ev(w)
    attest_roles, ack_roles = e._claim_rules(A, "x")
    roles = sorted(attest_roles.get(ctype, set()))
    assert roles, f"{ctype}: no role may attest it"
    role = roles[0]
    author = {"aggregator": AGG, "supplier": SUP, "member": MEM}[role]
    data = _claim_data(tid, ctype, r, w, pos)
    body = {"claim": {"type": ctype, "clause": "x", "data": data}}
    st = raw(w, pos, "attest", author, "2027-02-01T00:00:00Z", body)
    if ctype == "UP:Termination-Cause/notice":
        # Needs an earlier, uncured breach notice older than the cure period (tested in test_rules).
        assert not st.accepted and any(c.rule == "F-Exit" and not c.passed for c in st.checks)
        return
    assert st.accepted, (ctype, st.reason)
    # Acknowledgment by each role the claim needs.
    for ack_role in sorted(ack_roles.get(ctype, set())):
        acker = {"aggregator": AGG, "supplier": SUP, "member": MEM}[ack_role]
        if acker is author or acker.pub not in {x["party"]["key"] for x in A["parties"]}:
            continue
        st2 = raw(w, pos, "accept", acker, "2027-02-02T00:00:00Z", {"target": st.event_hash})
        assert st2.accepted, (ctype, ack_role, st2.reason)
    # The same claim with ill-typed data is rejected, with a reason that names the field.
    w.chains[pos] = w.chains[pos][: st.index]
    for f in data:
        bad = copy.deepcopy(body)
        bad["claim"]["data"][f] = {"unit": "day", "count": 0} if isinstance(data[f], str) else "not-this-type"
        st3 = raw(w, pos, "attest", author, "2027-02-01T00:00:00Z", bad)
        assert not st3.accepted and f in st3.reason, (ctype, f, st3.reason)
        w.chains[pos].pop()


def test_seal_allowed_only_where_the_type_is_sealable():
    w = World()
    clauses = master_clauses(w)
    fee = next(c for c in clauses if c["n"] == "fee")
    fee["params"]["report_clause"] = w.seal("reporting", "clause name")  # Name is structural
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], clauses, "x")
    issues = agreement_issues(ev(w).b, A)
    assert any("report_clause is structural (Name) and may not be sealed" in why for _, why in issues), issues


def test_claim_item_identifiers_may_seal_their_id_but_not_their_scheme():
    from universal_paper.typecheck import check
    seal = {"seal": "sha256:" + "ab" * 32}
    assert check("Identifier", {"scheme": "GTIN", "id": seal}) is None
    assert check("Identifier", {"scheme": seal, "id": "1"}) is not None
    assert json.dumps(ITEMS)  # the examples' items are plain Identifiers
