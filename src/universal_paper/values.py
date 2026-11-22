"""Value types: Decimal, Amount, Time, Period, Rounding, Seal (spec/01-domain.md §2–3, spec/04-inference.md §2, §6)."""
from __future__ import annotations

import calendar
import hashlib
import re
from datetime import UTC, datetime, timedelta
from decimal import MAX_EMAX, MAX_PREC, MIN_EMIN, ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_UP, Context, Decimal
from typing import Any

from .canon import jcs

# Exact arithmetic (spec/04-inference.md §6): with the maximum precision, addition and
# multiplication of Decimals never round. Rounding happens only in round_dec.
CTX = Context(prec=MAX_PREC, Emax=MAX_EMAX, Emin=MIN_EMIN)
# ASCII-only patterns anchored with \Z: Python's \d also matches non-ASCII digits, and $
# also matches before a trailing newline. The JavaScript engine uses the same patterns.
DEC_RE = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?\Z")
TIME_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
SALT_RE = re.compile(r"[0-9a-f]{64}\Z")
# Bounds that keep every computation small and identical across implementations (spec/01-domain.md §2).
MAX_DECIMAL_LEN = 64
MAX_PERIOD_COUNT = 10000
MAX_ROUNDING_SCALE = 18


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
    if not isinstance(s, str) or len(s) > MAX_DECIMAL_LEN or not DEC_RE.match(s):
        raise ValueError(f"not a Decimal string: {s!r}")
    return Decimal(s)


def dec_str(d: Decimal) -> str:
    if d == 0:
        d = abs(d)
    s = format(d, "f")
    return s


ROUNDING_MODES = {"half-even": ROUND_HALF_EVEN, "half-up": ROUND_HALF_UP, "down": ROUND_DOWN, "up": ROUND_UP}


def dmul(a: Decimal, b: Decimal) -> Decimal:
    return CTX.multiply(a, b)


def dsum(xs) -> Decimal:
    total = Decimal(0)
    for x in xs:
        total = CTX.add(total, x)
    return total


def round_dec(d: Decimal, rounding: dict) -> Decimal:
    scale = rounding["scale"]
    if not (isinstance(scale, int) and not isinstance(scale, bool) and 0 <= scale <= MAX_ROUNDING_SCALE):
        raise ValueError(f"rounding scale must be an integer from 0 to {MAX_ROUNDING_SCALE}")
    q = Decimal(1).scaleb(-scale)
    return d.quantize(q, rounding=ROUNDING_MODES[rounding["mode"]], context=CTX)


# ---- Time and Period -------------------------------------------------------

def parse_time(s: str) -> datetime:
    if not isinstance(s, str) or not TIME_RE.match(s):
        raise ValueError(f"not a UP Time: {s!r}")
    try:
        return datetime(int(s[0:4]), int(s[5:7]), int(s[8:10]), int(s[11:13]), int(s[14:16]), int(s[17:19]),
                        tzinfo=UTC)
    except ValueError:
        raise ValueError(f"not a UP Time: {s!r}") from None


def fmt_time(d: datetime) -> str:
    # Not strftime: on common platforms %Y does not zero-pad years before 1000.
    d = d.astimezone(UTC)
    return f"{d.year:04d}-{d.month:02d}-{d.day:02d}T{d.hour:02d}:{d.minute:02d}:{d.second:02d}Z"


def _add_months(d: datetime, n: int) -> datetime:
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return d.replace(year=y, month=m, day=day)


def add_period(t: str, p: dict, k: int = 1) -> str:
    """t + k×p, computed directly (never by repeated addition)."""
    d = parse_time(t)
    count = p["count"]
    if not (isinstance(count, int) and not isinstance(count, bool) and 1 <= count <= MAX_PERIOD_COUNT):
        raise ValueError(f"period count must be an integer from 1 to {MAX_PERIOD_COUNT}")
    n = count * k
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
    if not (isinstance(salt, str) and SALT_RE.match(salt)):
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
