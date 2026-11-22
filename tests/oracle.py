"""Run the same primitive operations on both engines (Python reference and JavaScript).

`both(ops)` returns (python_results, js_results) as lists of {"ok": ...} or {"error": True}.
Used by tests/test_differential.py. Requires Node.js for the JavaScript side.
"""
from __future__ import annotations

import json
import random
import shutil
import subprocess
import tempfile
from pathlib import Path

from universal_paper.canon import CanonError, content_hash, jcs, normalize
from universal_paper.crypto import Key, valid_key, verify
from universal_paper.engine import Bundle, agreement_issues
from universal_paper.typecheck import check, known
from universal_paper.values import add_period, dec, dec_str, dmul, dsum, parse_time, round_dec

ROOT = Path(__file__).resolve().parent.parent
HAS_NODE = shutil.which("node") is not None


def py(op: dict) -> dict:
    try:
        o = op["op"]
        if o == "jcs":
            return {"ok": jcs(op["value"]).decode("utf-8")}
        if o == "hash":
            return {"ok": content_hash(op["value"])}
        if o == "verify":
            return {"ok": verify(op["pub"], op["sig"], op["obj"])}
        if o == "valid_key":
            return {"ok": valid_key(op["pub"])}
        if o == "sign":
            return {"ok": Key.from_seed(op["seed"]).sign_obj(op["obj"])}
        if o == "time":
            parse_time(op["value"])
            return {"ok": True}
        if o == "add_period":
            return {"ok": add_period(op["t"], op["p"], op["k"])}
        if o == "dec":
            return {"ok": dec_str(dec(op["value"]))}
        if o == "mul_round":
            return {"ok": dec_str(round_dec(dmul(dec(op["a"]), dec(op["b"])), op["rounding"]))}
        if o == "sum_mul_round":
            total = dsum(dec(v) for v in op["values"])
            return {"ok": dec_str(round_dec(dmul(total, dec(op["rate"])), op["rounding"]))}
        if o == "typecheck":
            return {"ok": check(op["type"], op["value"], op["path"]) if known(op["type"]) else "unknown type"}
        if o == "agreement_issues":
            return {"ok": [list(x) for x in agreement_issues(Bundle(op["bundle"]), op["agreement"])]}
        return {"error": f"unknown op {o}"}
    except (CanonError, ValueError, TypeError, KeyError, OverflowError, AttributeError, UnicodeError):
        return {"error": True}


def js(ops: list[dict]) -> list[dict]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(ops, f, ensure_ascii=True)
        path = f.name
    try:
        r = subprocess.run(["node", str(ROOT / "tests" / "js_oracle.mjs"), path], capture_output=True, text=True, check=True)
    finally:
        Path(path).unlink()
    return json.loads(r.stdout)


def both(ops: list[dict]) -> tuple[list[dict], list[dict]]:
    # Python sees exactly what JavaScript sees: the ops after a JSON round trip.
    # Numbers are normalized as Bundle() does on load, so 1.0 is the integer 1 on both sides.
    ops = json.loads(json.dumps(ops, ensure_ascii=True))
    return [py(normalize(o)) for o in ops], js(ops)


def mismatches(ops, a, b, limit=10):
    out = []
    for o, x, y in zip(ops, a, b):
        if x != y:
            out.append(f"{json.dumps(o, ensure_ascii=True)[:300]}\n    python={x}\n    js={y}")
            if len(out) >= limit:
                break
    return out


# ---- random generators (seeded, so every failure is reproducible) ---------------

CHARS = ["a", "Z", "0", " ", "\"", "\\", "/", "\b", "\f", "\n", "\r", "\t", "\x00", "\x1f", "\x7f", "é", "€",
         " ", "﻿", "\U0001F600", "\U00010000", "\ud800", "\udfff", "日"]


def rand_string(r: random.Random, n=8) -> str:
    return "".join(r.choice(CHARS) for _ in range(r.randint(0, n)))


def rand_json(r: random.Random, depth=0):
    k = r.randint(0, 9 if depth < 3 else 5)
    if k == 0:
        return r.choice([True, False])
    if k == 1:
        return r.choice([0, -1, 1, 2**53 - 1, -(2**53 - 1), 2**53, r.randint(-10**6, 10**6)])
    if k == 2:
        return r.choice([1.0, 100.0, -0.0, 1.5, 1e2, 0.1])
    if k == 3:
        return None if r.random() < 0.2 else rand_string(r)
    if k in (4, 5):
        return rand_string(r)
    if k in (6, 7):
        return [rand_json(r, depth + 1) for _ in range(r.randint(0, 4))]
    keys = [r.choice(["a", "b", "B", "type", "sigs", "", "10", "2", "é", "\U0001F600", "a\u0000"]) for _ in range(r.randint(0, 5))]
    return {key: rand_json(r, depth + 1) for key in keys}


def rand_decimal(r: random.Random) -> str:
    whole = r.choice(["0", str(r.randint(1, 9)) + "".join(r.choice("0123456789") for _ in range(r.randint(0, 30)))])
    frac = "".join(r.choice("0123456789") for _ in range(r.randint(0, 30)))
    s = ("-" if r.random() < 0.2 else "") + whole + ("." + frac if frac else "")
    return s


def rand_time(r: random.Random) -> str:
    y, mo, d = r.randint(1, 9999), r.randint(1, 12), r.randint(1, 28)
    h, mi, s = r.randint(0, 23), r.randint(0, 59), r.randint(0, 59)
    return f"{y:04d}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}Z"


BAD_TIMES = ["2027-02-29T00:00:00Z", "2028-02-29T00:00:00Z", "2027-13-01T00:00:00Z", "2027-00-10T00:00:00Z",
             "2027-01-01T24:00:00Z", "2027-01-01T10:60:00Z", "2027-01-01T10:00:60Z", "0000-01-01T00:00:00Z",
             "0050-06-15T00:00:00Z", "2027-01-01T00:00:00Z\n", "２０２７-01-01T00:00:00Z", "2027-01-01T00:00:00+00:00",
             "2027-01-01 00:00:00Z", "2027-1-1T00:00:00Z", "9999-12-31T23:59:59Z", "0001-01-01T00:00:00Z",
             "2027-04-31T00:00:00Z", "2027-01-01T00:00:00.5Z", ""]
