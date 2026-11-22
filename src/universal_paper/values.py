"""Value types: Decimal, Amount, Time, Period, Rounding, Seal (spec/01-domain.md §2–3, spec/04-inference.md §2, §6)."""
from __future__ import annotations

import calendar
import hashlib
import re
from datetime import datetime, timedelta, timezone
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_UP, Context, Decimal
from typing import Any

from .canon import jcs

CTX = Context(prec=200)
DEC_RE = re.compile(r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$")
TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class Sealed:
    """Marker for a value this evaluator cannot see. Arithmetic on it yields Sealed."""

    _inst = None

    def __new__(cls):
        if cls._inst is None:
            cls._inst = super().__new__(cls)
        return cls._inst

    def __repr__(self):
        return "sealed"


SEALED = Sealed()


# ---- Decimal ---------------------------------------------------------------

def dec(s: str) -> Decimal:
    if not isinstance(s, str) or not DEC_RE.match(s):
        raise ValueError(f"not a Decimal string: {s!r}")
    return Decimal(s)


def dec_str(d: Decimal) -> str:
    if d == 0:
        d = abs(d)
    s = format(d, "f")
    return s


ROUNDING_MODES = {"half-even": ROUND_HALF_EVEN, "half-up": ROUND_HALF_UP, "down": ROUND_DOWN, "up": ROUND_UP}


def round_dec(d: Decimal, rounding: dict) -> Decimal:
    q = Decimal(1).scaleb(-int(rounding["scale"]))
    return d.quantize(q, rounding=ROUNDING_MODES[rounding["mode"]], context=CTX)


# ---- Time and Period -------------------------------------------------------

def parse_time(s: str) -> datetime:
    if not isinstance(s, str) or not TIME_RE.match(s):
        raise ValueError(f"not a UP Time: {s!r}")
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def fmt_time(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _add_months(d: datetime, n: int) -> datetime:
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return d.replace(year=y, month=m, day=day)


def add_period(t: str, p: dict, k: int = 1) -> str:
    """t + k×p, computed directly (never by repeated addition)."""
    d = parse_time(t)
    n = int(p["count"]) * k
    unit = p["unit"]
    if unit == "day":
        r = d + timedelta(days=n)
    elif unit == "month":
        r = _add_months(d, n)
    elif unit == "quarter":
        r = _add_months(d, 3 * n)
    elif unit == "year":
        r = _add_months(d, 12 * n)
    else:
        raise ValueError(f"bad period unit {unit!r}")
    return fmt_time(r)


def fmt_period(p: dict) -> str:
    n, u = int(p["count"]), p["unit"]
    word = {"day": "day", "month": "calendar month", "quarter": "calendar quarter", "year": "year"}[u]
    return f"{n} {word}" + ("s" if n != 1 else "")


# ---- Seals -----------------------------------------------------------------

def is_seal(x: Any) -> bool:
    return isinstance(x, dict) and set(x) == {"seal"} and isinstance(x["seal"], str)


def seal_of(value: Any, salt: str) -> dict:
    if not (isinstance(salt, str) and len(salt) == 64):
        raise ValueError("salt must be 64 hex characters")
    return {"seal": "sha256:" + hashlib.sha256(jcs({"salt": salt, "value": value})).hexdigest()}


def opens(disclosure: dict, seal: dict) -> bool:
    return seal_of(disclosure["value"], disclosure["salt"]) == seal and disclosure.get("seal") == seal["seal"]


def contains_seal(x: Any) -> bool:
    if is_seal(x):
        return True
    if isinstance(x, dict):
        return any(contains_seal(v) for v in x.values())
    if isinstance(x, list):
        return any(contains_seal(v) for v in x)
    return False
