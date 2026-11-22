"""Helpers for building agreements, events, and bundles (used by examples and tests)."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from . import SPEC
from .canon import content_hash
from .crypto import Key, attach
from .engine import Bundle, Evaluator
from .values import seal_of

TERMS_DIR = Path(__file__).resolve().parents[2] / "spec" / "06-terms"


def load_terms(directory: Path = TERMS_DIR) -> dict[str, dict]:
    out = {}
    for p in sorted(directory.glob("*.json")):
        t = json.loads(p.read_text())
        out[t["id"]] = t
    return out


class Actor:
    def __init__(self, name: str, seed: str | None = None, ids: list[dict] | None = None):
        self.name = name
        self.key = Key.from_seed(seed or f"universal-paper-example:{name}")
        self.ids = ids or []

    @property
    def pub(self) -> str:
        return self.key.public

    def party(self) -> dict:
        p = {"key": self.pub, "name": self.name}
        if self.ids:
            p["ids"] = self.ids
        return p


class World:
    """A growing set of terms, mandates, chains, and disclosures."""

    def __init__(self, terms: dict[str, dict] | None = None):
        self.terms = terms or load_terms()
        self.mandates: list[dict] = []
        self.chains: list[list[dict]] = []
        self.disclosures: list[dict] = []
        self._salt_n = 0

    # ---- content -------------------------------------------------------

    def clause(self, n: str, term: str, params: dict, over: list[str] | None = None) -> dict:
        c = {"n": n, "term": term, "def": content_hash(self.terms[term]), "params": params}
        if over:
            c["over"] = over
        return c

    def agreement(self, parties: list[tuple[str, Actor]], clauses: list[dict], label: str) -> dict:
        ps = sorted(({"role": r, "party": a.party()} for r, a in parties), key=lambda p: (p["role"], p["party"]["key"]))
        return {"type": "Agreement", "spec": SPEC, "parties": ps, "clauses": clauses, "label": label}

    def seal(self, value, label: str) -> dict:
        """Seal a value with a deterministic salt. EXAMPLES ONLY: real salts must be random."""
        self._salt_n += 1
        salt = hashlib.sha256(f"example-salt:{label}:{self._salt_n}".encode()).hexdigest()
        s = seal_of(value, salt)
        self.disclosures.append({"seal": s["seal"], "salt": salt, "value": value})
        return s

    def mandate(self, principal: Actor, agent: Key, not_before: str, expires: str, scope: dict) -> str:
        m = {"type": "Mandate", "spec": SPEC, "principal": principal.pub, "agent": agent.public,
             "not_before": not_before, "expires": expires, "scope": scope}
        m = attach(m, principal.key.sign_obj(m))
        self.mandates.append(m)
        return content_hash(m)

    # ---- bundle and events --------------------------------------------

    def data(self, disclosures: bool = True, all_terms: bool = False) -> dict:
        used = {c["def"] for ch in self.chains for e in ch
                for c in (e.get("body", {}).get("agreement") or {}).get("clauses", [])}
        d = {"type": "Bundle", "spec": SPEC,
             "terms": [t for t in self.terms.values() if all_terms or content_hash(t) in used],
             "mandates": list(self.mandates),
             "chains": copy.deepcopy(self.chains)}
        if disclosures and self.disclosures:
            d["disclosures"] = list(self.disclosures)
        return d

    def bundle(self) -> Bundle:
        return Bundle(self.data(all_terms=True))

    def chain_id(self, pos: int) -> str:
        return content_hash(self.chains[pos][0])

    def _state(self, pos: int):
        ev = Evaluator(self.bundle())
        return ev.state_at(self.chain_id(pos))

    def event(self, pos: int | None, kind: str, by: Actor, at: str, body: dict,
              cosigners: list[Actor] = (), agent: tuple[Key, str] | None = None,
              expect: bool = True) -> tuple[int, str]:
        """Append a signed event. pos=None starts a new chain. agent=(agent key, mandate hash) signs for `by`."""
        E = {"type": "Event", "spec": SPEC, "kind": kind, "at": at, "by": by.pub, "body": body}
        if pos is not None:
            S = self._state(pos)
            E["chain"] = self.chain_id(pos)
            E["prev"] = content_hash(S)
        sigs = [agent[0].sign_obj(E, agent[1]) if agent else by.key.sign_obj(E)]
        sigs += [c.key.sign_obj(E) for c in cosigners]
        E = attach(E, *sigs)
        if pos is None:
            self.chains.append([E])
            pos = len(self.chains) - 1
        else:
            self.chains[pos].append(E)
        ev = Evaluator(self.bundle())
        step = ev.run(self.chain_id(pos))[-1]
        if step.accepted != expect:
            raise AssertionError(f"event at {at} by {by.name} expected {'accept' if expect else 'reject'}: {step.reason}")
        return pos, content_hash(E)

    def propose(self, by, ag, at, pos=None, **kw):
        body = {"agreement": ag}
        if "supersedes" in kw:
            body["supersedes"] = kw.pop("supersedes")
        if "expires" in kw:
            body["expires"] = kw.pop("expires")
        return self.event(pos, "propose", by, at, body, **kw)

    def accept(self, pos, by, target, at, **kw):
        return self.event(pos, "accept", by, at, {"target": target}, **kw)

    def attest(self, pos, by, clause, ctype, data, at, **kw):
        return self.event(pos, "attest", by, at, {"claim": {"type": ctype, "clause": clause, "data": data}}, **kw)
