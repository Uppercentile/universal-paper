"""Canonical JSON (RFC 8785 / JCS, restricted per spec/01-domain.md §1) and content hashes."""
from __future__ import annotations

import hashlib
from typing import Any

MAX_INT = 2**53 - 1


class CanonError(ValueError):
    pass


def _str(s: str) -> str:
    out = ['"']
    if any(0xD800 <= ord(ch) <= 0xDFFF for ch in s):
        # RFC 8785 relies on I-JSON (RFC 7493), which forbids lone surrogates.
        raise CanonError("strings must not contain lone surrogates")
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\b":
            out.append("\\b")
        elif ch == "\f":
            out.append("\\f")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif o < 0x20:
            out.append("\\u%04x" % o)
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _ser(v: Any, parts: list[str]) -> None:
    if v is True:
        parts.append("true")
    elif v is False:
        parts.append("false")
    elif v is None:
        raise CanonError("null is not allowed in Universal Paper objects")
    elif isinstance(v, int):
        if abs(v) > MAX_INT:
            raise CanonError(f"integer out of range: {v}")
        parts.append(str(v))
    elif isinstance(v, float):
        # JSON does not distinguish 100 from 100.0 or 1e2, and JavaScript cannot tell them
        # apart after parsing, so an integral number is canonicalized as that integer.
        if v != v or v in (float("inf"), float("-inf")) or not v.is_integer():
            raise CanonError("non-integer JSON numbers are not allowed; use a Decimal string")
        _ser(int(v), parts)
    elif isinstance(v, str):
        parts.append(_str(v))
    elif isinstance(v, (list, tuple)):
        parts.append("[")
        for i, x in enumerate(v):
            if i:
                parts.append(",")
            _ser(x, parts)
        parts.append("]")
    elif isinstance(v, dict):
        for k in v:
            if not isinstance(k, str):
                raise CanonError("object keys must be strings")
            if not k.isascii():
                raise CanonError("object keys must be ASCII (spec/01-domain.md §1.1)")
        parts.append("{")
        for i, k in enumerate(sorted(v, key=lambda k: k.encode("utf-16-be"))):
            if i:
                parts.append(",")
            parts.append(_str(k))
            parts.append(":")
            _ser(v[k], parts)
        parts.append("}")
    else:
        raise CanonError(f"unsupported type: {type(v).__name__}")


def jcs(v: Any) -> bytes:
    parts: list[str] = []
    _ser(v, parts)
    return "".join(parts).encode("utf-8")


def normalize(v: Any) -> Any:
    """Turn integral floats (from JSON text such as 100.0 or 1e2) into ints, recursively.

    Bundles are normalized on load so the evaluator sees numbers exactly as the JavaScript
    engine does. Non-integral floats are left alone; canonicalization rejects them.
    """
    if isinstance(v, float) and v == v and v not in (float("inf"), float("-inf")) and v.is_integer():
        return int(v)
    if isinstance(v, dict):
        return {k: normalize(x) for k, x in v.items()}
    if isinstance(v, list):
        return [normalize(x) for x in v]
    return v


def strip(o: dict) -> dict:
    return {k: v for k, v in o.items() if k != "sigs"}


def digest(o: dict) -> bytes:
    """The 32 raw SHA-256 bytes that signatures cover."""
    return hashlib.sha256(jcs(strip(o) if isinstance(o, dict) else o)).digest()


def content_hash(o: Any) -> str:
    return "sha256:" + hashlib.sha256(jcs(strip(o) if isinstance(o, dict) else o)).hexdigest()


def hash_bytes(h: str) -> bytes:
    if not (isinstance(h, str) and h.startswith("sha256:") and len(h) == 71
            and all(c in "0123456789abcdef" for c in h[7:])):
        raise CanonError(f"not a hash: {h!r}")
    return bytes.fromhex(h[7:])
