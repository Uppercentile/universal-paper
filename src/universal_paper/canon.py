"""Canonical JSON (RFC 8785 / JCS, restricted per spec/01-domain.md §1) and content hashes."""
from __future__ import annotations

import hashlib
from typing import Any

MAX_INT = 2**53 - 1


class CanonError(ValueError):
    pass


def _str(s: str) -> str:
    out = ['"']
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
        raise CanonError("non-integer JSON numbers are not allowed; use a Decimal string")
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
        parts.append("{")
        for i, k in enumerate(sorted(v, key=lambda k: k.encode("utf-16-be"))):
            if not isinstance(k, str):
                raise CanonError("object keys must be strings")
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


def strip(o: dict) -> dict:
    return {k: v for k, v in o.items() if k != "sigs"}


def digest(o: dict) -> bytes:
    """The 32 raw SHA-256 bytes that signatures cover."""
    return hashlib.sha256(jcs(strip(o) if isinstance(o, dict) else o)).digest()


def content_hash(o: Any) -> str:
    return "sha256:" + hashlib.sha256(jcs(strip(o) if isinstance(o, dict) else o)).hexdigest()


def hash_bytes(h: str) -> bytes:
    if not (isinstance(h, str) and h.startswith("sha256:") and len(h) == 71):
        raise CanonError(f"not a hash: {h!r}")
    return bytes.fromhex(h[7:])
