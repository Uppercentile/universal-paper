"""Differential tests: the Python reference and the JavaScript engine must agree on every primitive.

Each test generates thousands of seeded random inputs (valid and invalid), runs them on both
engines, and requires identical results, including identical rejections. A failure prints the
input, so it can be turned into a fixed regression test.
"""
import random

import pytest

from universal_paper.crypto import Key

from oracle import BAD_TIMES, HAS_NODE, both, mismatches, rand_decimal, rand_json, rand_string, rand_time

pytestmark = pytest.mark.skipif(not HAS_NODE, reason="Node.js is not installed")

P = 2**255 - 19
L = 2**252 + 27742317777372353535851937790883648493


def le(n: int) -> str:
    return n.to_bytes(32, "little").hex()


def agree(ops):
    a, b = both(ops)
    bad = mismatches(ops, a, b)
    assert not bad, f"{len(bad)} disagreement(s):\n" + "\n".join(bad)
    return a


def test_canonical_json_and_hashes_agree():
    r = random.Random(1)
    values = [rand_json(r) for _ in range(3000)]
    ops = [{"op": "jcs", "value": v} for v in values] + [{"op": "hash", "value": v} for v in values]
    res = agree(ops)
    # Make sure the generator exercises both outcomes.
    assert any("ok" in x for x in res) and any("error" in x for x in res)


def test_signatures_agree_including_edge_cases():
    r = random.Random(2)
    ops = []
    for i in range(40):
        obj = {"type": "Event", "spec": "UP/0.1-draft", "n": i, "s": "".join(c for c in rand_string(r) if not 0xD800 <= ord(c) <= 0xDFFF)}
        ops.append({"op": "sign", "seed": f"seed {i}", "obj": obj})
        k = Key.from_seed(f"seed {i}")
        s = k.sign_obj(obj)
        sig, pub = s["sig"], s["key"]
        flip = r.randrange(128)
        mutated = sig[:flip] + format(int(sig[flip], 16) ^ (1 + r.randrange(15)), "x") + sig[flip + 1:]
        S = int.from_bytes(bytes.fromhex(sig[64:]), "little")
        for p_, s_ in [(pub, sig), (pub, mutated), (pub, sig.upper()), ("ed25519:" + pub[8:].upper(), sig),
                       (pub, sig[:64] + le(S + L)), (pub, sig + "00"), (pub, " " + sig[1:]), (pub[:-2], sig)]:
            ops.append({"op": "verify", "pub": p_, "sig": s_, "obj": obj})
        ops.append({"op": "verify", "pub": pub, "sig": sig, "obj": {**obj, "n": i + 1}})
    small = [le(0), le(1), le(P - 1), le(P + 1), le(2**255 - 1),
             "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05",
             "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a",
             "0100000000000000000000000000000000000000000000000000000000000080"]
    for a in small:
        ops.append({"op": "valid_key", "pub": "ed25519:" + a})
        for R in small:
            ops.append({"op": "verify", "pub": "ed25519:" + a, "sig": R + le(0), "obj": {"type": "x", "spec": "y"}})
    res = agree(ops)
    # Strict rules: no small-order or non-canonical key ever verifies anything.
    for o, x in zip(ops, res):
        if o["op"] == "verify" and o["pub"][8:] in small:
            assert x == {"ok": False}, o
        if o["op"] == "valid_key":
            assert x == {"ok": False}, o


def test_times_and_periods_agree():
    r = random.Random(3)
    times = [rand_time(r) for _ in range(500)] + BAD_TIMES
    ops = [{"op": "time", "value": t} for t in times]
    for _ in range(3000):
        t = r.choice(times)
        p = {"unit": r.choice(["day", "month", "quarter", "year", "week"]), "count": r.choice([1, 2, 3, 12, 0, -1, 10000, 10001, "1", True, 1.0])}
        ops.append({"op": "add_period", "t": t, "p": p, "k": r.choice([0, 1, 2, 5, 37, 120])})
    agree(ops)


def test_exact_decimal_arithmetic_agrees():
    r = random.Random(4)
    ops = []
    for _ in range(3000):
        rounding = {"scale": r.choice([0, 1, 2, 4, 18, 19, -1, True]), "mode": r.choice(["half-even", "half-up", "down", "up", "ceiling"])}
        ops.append({"op": "mul_round", "a": rand_decimal(r), "b": rand_decimal(r), "rounding": rounding})
        ops.append({"op": "sum_mul_round", "values": [rand_decimal(r) for _ in range(r.randint(0, 5))], "rate": rand_decimal(r), "rounding": rounding})
        ops.append({"op": "dec", "value": r.choice([rand_decimal(r), "1e5", "+1", "01", "1.", ".5", "1.5\n", "-0", "-0.00", "１", "9" * 65])})
    # A product that the old 28-digit default context rounded before the final rounding.
    ops.append({"op": "mul_round", "a": "1000000000000000000000.005", "b": "1.0000001", "rounding": {"scale": 2, "mode": "half-even"}})
    res = agree(ops)
    assert res[-1] == {"ok": "1000000100000000000000.01"}


def _shipped_types():
    import json
    from pathlib import Path
    out = set()
    for p in sorted((Path(__file__).resolve().parent.parent / "spec" / "06-terms").glob("*.json")):
        t = json.loads(p.read_text())
        out |= {d["type"] for d in t["params"].values()}
        out |= {ft for c in t["claims"].values() for ft in c["data"].values()}
    return sorted(out)


def test_type_checks_agree_on_every_shipped_type():
    from samples import SEAL, mutate, sample
    r = random.Random(5)
    ops = []
    types = _shipped_types() + ["{<k>: [Name]}", "[[int]]", "Bogus", "{a: Time", "\"x\" | int | {b: Hash}"]
    for t in types:
        for _ in range(150):
            try:
                v = sample(t, r)
            except Exception:
                v = None
            for value in (v, mutate(v, r), mutate(mutate(v, r), r), SEAL):
                ops.append({"op": "typecheck", "type": t, "value": value, "path": "p"})
    res = agree(ops)
    assert sum(x.get("ok") is None for x in res) > 1000  # many valid
    assert sum(isinstance(x.get("ok"), str) for x in res) > 1000  # many invalid, with identical reasons
