"""Value types of Term parameters and claim data (spec/01-domain.md §2, §3.3).

A type is written as a small expression, for example ``Period``, ``[Role]``,
``{start: Time, end: Time}``, ``{<tier>: Amount}`` or ``"on-ack" | {next: Period}``.
``check(type_text, value)`` returns None when the value has the type, or a short
reason when it does not. The JavaScript engine (explorer/src/up-engine.js) mirrors
this module and must produce the same reasons.

A Seal may stand in place of a value only where the type is sealable: Amount,
Rate, Decimal, string, or the ``id`` of an Identifier. Every other type is
structural (spec/01-domain.md §3.3) and must appear unsealed.
"""
from __future__ import annotations

import re
from functools import cache
from typing import Any

from .values import DEC_RE, MAX_DECIMAL_LEN, MAX_PERIOD_COUNT, MAX_ROUNDING_SCALE, is_seal, parse_time

ROLES = ("aggregator", "supplier", "member")
UNITS = ("day", "month", "quarter", "year")
MODES = ("half-even", "half-up", "down", "up")
MAX_INT = 2**53 - 1
HASH_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
CURRENCY_RE = re.compile(r"[A-Z]{3}\Z")
ATOMS = ("Time", "Period", "Decimal", "Rate", "Amount", "Identifier", "Hash", "ChainId",
         "Role", "Rounding", "string", "Name", "int")
SEALABLE = ("Amount", "Rate", "Decimal", "string")


class TypeSyntaxError(ValueError):
    pass


# ---- parsing ---------------------------------------------------------------

_TOKEN = re.compile(r' *(?:(?P<lit>"[^"]*")|(?P<word><?[A-Za-z_][A-Za-z0-9_]*>?)|(?P<p>[\[\]{}:,|]))')


def _tokens(text: str) -> list[str]:
    out, i = [], 0
    while i < len(text):
        if text[i:].strip(" ") == "":
            break
        m = _TOKEN.match(text, i)
        if not m:
            raise TypeSyntaxError(f"cannot read type {text!r}")
        out.append(m.group(m.lastgroup or 0))
        i = m.end()
    return out


@cache
def parse(text: str) -> tuple:
    toks = _tokens(text)
    pos = 0

    def peek():
        return toks[pos] if pos < len(toks) else None

    def take(expected=None):
        nonlocal pos
        t = peek()
        if t is None or (expected is not None and t != expected):
            raise TypeSyntaxError(f"cannot read type {text!r}")
        pos += 1
        return t

    def union():
        alts = [atom()]
        while peek() == "|":
            take("|")
            alts.append(atom())
        return alts[0] if len(alts) == 1 else ("union", tuple(alts))

    def atom():
        t = take()
        if t.startswith('"'):
            return ("lit", t[1:-1])
        if t == "[":
            inner = union()
            take("]")
            return ("list", inner)
        if t == "{":
            k = take()
            if k.startswith("<") and k.endswith(">"):
                take(":")
                v = union()
                take("}")
                return ("map", v)
            fields = []
            while True:
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\Z", k):
                    raise TypeSyntaxError(f"cannot read type {text!r}")
                take(":")
                fields.append((k, union()))
                if peek() == ",":
                    take(",")
                    k = take()
                    continue
                take("}")
                return ("record", tuple(fields))
        if t in ATOMS:
            return ("atom", t)
        raise TypeSyntaxError(f"unknown type {t!r} in {text!r}")

    node = union()
    if pos != len(toks):
        raise TypeSyntaxError(f"cannot read type {text!r}")
    return node


def known(text: Any) -> bool:
    try:
        parse(text)
        return isinstance(text, str)
    except (TypeSyntaxError, TypeError):
        return False


# ---- checking --------------------------------------------------------------

def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _time_ok(v: Any) -> bool:
    try:
        parse_time(v)
        return True
    except (ValueError, TypeError):
        return False


def _dec_ok(v: Any) -> bool:
    return isinstance(v, str) and len(v) <= MAX_DECIMAL_LEN and DEC_RE.match(v) is not None


def _atom(name: str, v: Any, path: str) -> str | None:
    if is_seal(v):
        return None if name in SEALABLE else f"{path} is structural ({name}) and may not be sealed"
    ok = True
    if name == "Time":
        ok = _time_ok(v)
        what = "a Time (YYYY-MM-DDThh:mm:ssZ)"
    elif name == "Period":
        ok = (isinstance(v, dict) and set(v) == {"unit", "count"} and v["unit"] in UNITS
              and _is_int(v["count"]) and 1 <= v["count"] <= MAX_PERIOD_COUNT)
        what = f"a Period (unit day, month, quarter or year; count from 1 to {MAX_PERIOD_COUNT})"
    elif name in ("Decimal", "Rate"):
        ok = _dec_ok(v)
        what = f"a Decimal string of at most {MAX_DECIMAL_LEN} characters"
    elif name == "Amount":
        ok = (isinstance(v, dict) and set(v) == {"value", "currency"} and _dec_ok(v["value"])
              and isinstance(v["currency"], str) and CURRENCY_RE.match(v["currency"]) is not None)
        what = "an Amount ({value: Decimal, currency: three-letter code})"
    elif name == "Identifier":
        ok = (isinstance(v, dict) and set(v) == {"scheme", "id"} and isinstance(v["scheme"], str) and v["scheme"] != ""
              and ((isinstance(v["id"], str) and v["id"] != "") or is_seal(v["id"])))
        what = "an Identifier ({scheme: string, id: string})"
    elif name in ("Hash", "ChainId"):
        ok = isinstance(v, str) and HASH_RE.match(v) is not None
        what = "a hash (sha256: and 64 lowercase hex digits)"
    elif name == "Role":
        ok = v in ROLES if isinstance(v, str) else False
        what = "a role"
    elif name == "Rounding":
        ok = (isinstance(v, dict) and set(v) == {"scale", "mode"} and _is_int(v["scale"])
              and 0 <= v["scale"] <= MAX_ROUNDING_SCALE and v["mode"] in MODES)
        what = f"a Rounding (scale from 0 to {MAX_ROUNDING_SCALE}; mode half-even, half-up, down or up)"
    elif name == "string":
        ok = isinstance(v, str)
        what = "a string"
    elif name == "Name":
        ok = isinstance(v, str) and v != ""
        what = "a non-empty name"
    else:  # int
        ok = _is_int(v) and 0 <= v <= MAX_INT
        what = "a non-negative integer"
    return None if ok else f"{path} must be {what}"


def _check(node: tuple, v: Any, path: str) -> str | None:
    kind = node[0]
    if kind == "atom":
        return _atom(node[1], v, path)
    if is_seal(v):
        return f"{path} is structural and may not be sealed"
    if kind == "lit":
        return None if v == node[1] else f"{path} must be \"{node[1]}\""
    if kind == "list":
        if not isinstance(v, list):
            return f"{path} must be a list"
        for i, x in enumerate(v):
            err = _check(node[1], x, f"{path}[{i}]")
            if err:
                return err
        return None
    if kind == "map":
        if not isinstance(v, dict) or not v:
            return f"{path} must be a non-empty object"
        for k in sorted(v, key=lambda k: k.encode("utf-16-be")):
            if k == "":
                return f"{path} has an empty key"
            err = _check(node[1], v[k], f"{path}.{k}")
            if err:
                return err
        return None
    if kind == "record":
        names = [f for f, _ in node[1]]
        if not isinstance(v, dict) or set(v) != set(names):
            return f"{path} must have exactly the fields {', '.join(names)}"
        for f, t in node[1]:
            err = _check(t, v[f], f"{path}.{f}")
            if err:
                return err
        return None
    # union: the value must match one alternative
    for alt in node[1]:
        if _check(alt, v, path) is None:
            return None
    return f"{path} does not match any allowed form"


def check(type_text: str, value: Any, path: str = "value") -> str | None:
    """None if value has the type; otherwise the first reason it does not."""
    return _check(parse(type_text), value, path)
