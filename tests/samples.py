"""Valid and invalid sample values for any Universal Paper type expression (tests only)."""
from __future__ import annotations

import copy
import random
from typing import Any

from universal_paper.typecheck import parse

SEAL = {"seal": "sha256:" + "ab" * 32}


def sample(text_or_node: Any, r: random.Random) -> Any:
    node = parse(text_or_node) if isinstance(text_or_node, str) else text_or_node
    kind = node[0]
    if kind == "atom":
        return _atom(node[1], r)
    if kind == "lit":
        return node[1]
    if kind == "list":
        return [sample(node[1], r) for _ in range(r.randint(1, 3))]
    if kind == "map":
        return {k: sample(node[1], r) for k in r.sample(["A", "B", "C"], r.randint(1, 3))}
    if kind == "record":
        return {f: sample(t, r) for f, t in node[1]}
    return sample(r.choice(node[1]), r)


def _atom(name: str, r: random.Random) -> Any:
    if name == "Time":
        return f"{r.randint(2026, 2030)}-{r.randint(1, 12):02d}-{r.randint(1, 28):02d}T00:00:00Z"
    if name == "Period":
        return {"unit": r.choice(["day", "month", "quarter", "year"]), "count": r.randint(1, 12)}
    if name in ("Decimal", "Rate"):
        return r.choice(["0", "0.02", "1", "12.5", "0.975"])
    if name == "Amount":
        return {"value": r.choice(["0.00", "9.10", "1250.00"]), "currency": "USD"}
    if name == "Identifier":
        return {"scheme": "GTIN", "id": r.choice(["00012345600012", "00012345600029"])}
    if name in ("Hash", "ChainId"):
        return "sha256:" + "".join(r.choice("0123456789abcdef") for _ in range(64))
    if name == "Role":
        return r.choice(["aggregator", "supplier", "member"])
    if name == "Rounding":
        return {"scale": r.randint(0, 4), "mode": r.choice(["half-even", "half-up", "down", "up"])}
    if name == "string":
        return r.choice(["", "Hypothetical text", "Tier A"])
    if name == "Name":
        return r.choice(["A", "B", "reporting"])
    return r.randint(0, 5)  # int


BAD = [None, True, False, 0, -1, 1.5, "", "x", [], {}, {"seal": "sha256:" + "ab" * 32}, {"unit": "day", "count": 0},
       {"unit": "week", "count": 1}, {"value": "1", "currency": "usd"}, {"scheme": "", "id": "1"}, "sha256:" + "AB" * 32,
       "2027-02-30T00:00:00Z", {"scale": 19, "mode": "up"}, ["member", "nobody"], "1e3", "01.5", 2**53]


def mutate(v: Any, r: random.Random) -> Any:
    """Return a copy of v with one value replaced by something likely of the wrong type."""
    v = copy.deepcopy(v)
    if isinstance(v, dict) and v and r.random() < 0.7:
        k = r.choice(sorted(v))
        if r.random() < 0.2:
            del v[k]
        else:
            v[k] = mutate(v[k], r)
        return v
    if isinstance(v, list) and v and r.random() < 0.7:
        i = r.randrange(len(v))
        v[i] = mutate(v[i], r)
        return v
    return copy.deepcopy(r.choice(BAD))
