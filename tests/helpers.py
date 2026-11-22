"""Small worlds for tests. All values are hypothetical."""
from __future__ import annotations

from universal_paper import SPEC
from universal_paper.build import Actor, World
from universal_paper.canon import content_hash
from universal_paper.crypto import attach
from universal_paper.engine import Evaluator

from build_examples import master_clauses, participation_clauses

AGG = Actor("Test Aggregator")
SUP = Actor("Test Supplier")
MEM = Actor("Test Member")
OTHER = Actor("Unrelated Party")


def master(w: World, clauses=None, at="2026-12-01T00:00:00Z", accept=True):
    A = w.agreement([("aggregator", AGG), ("supplier", SUP)], clauses or master_clauses(w), "Test master")
    a, h = w.propose(AGG, A, at)
    if accept:
        w.accept(a, SUP, h, at.replace("T00", "T01"))
    return a, A, h


def participation(w: World, a: int, at="2026-12-10T00:00:00Z", tier="B"):
    P = w.agreement([("aggregator", AGG), ("member", MEM), ("supplier", SUP)],
                    participation_clauses(w, w.chain_id(a), "2027-01-01T00:00:00Z"), "Test participation")
    p, h = w.propose(MEM, P, at, cosigners=[AGG, SUP])
    if tier:
        w.attest(p, MEM, "tier", "UP:Tier-Selection/selects", {"option": tier, "basis": "test"}, at.replace("T00", "T02"), cosigners=[SUP])
    return p, P


def raw(w: World, pos, kind, by: Actor, at, body, signers=None, prev="auto", chain="auto"):
    """Append an arbitrary (possibly invalid) event and return the evaluator's step for it."""
    E = {"type": "Event", "spec": SPEC, "kind": kind, "at": at, "by": by.pub, "body": body}
    if pos is not None:
        ev = Evaluator(w.bundle())
        cid = w.chain_id(pos)
        E["chain"] = cid if chain == "auto" else chain
        E["prev"] = content_hash(ev.state_at(cid)) if prev == "auto" else prev
    E = attach(E, *[s.key.sign_obj(E) for s in (signers or [by])])
    if pos is None:
        w.chains.append([E])
        pos = len(w.chains) - 1
    else:
        w.chains[pos].append(E)
    return Evaluator(w.bundle()).run(w.chain_id(pos))[-1]


def ev(w: World) -> Evaluator:
    return Evaluator(w.bundle())
