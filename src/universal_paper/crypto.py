"""Ed25519 keys and signatures over content hashes (spec/01-domain.md §1.3)."""
from __future__ import annotations

import hashlib
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .canon import digest


class Key:
    """A private signing key. Example keys are derived from a seed phrase so examples are reproducible."""

    def __init__(self, priv: Ed25519PrivateKey):
        self._priv = priv
        raw = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.public = "ed25519:" + raw.hex()

    @classmethod
    def from_seed(cls, seed: str) -> Key:
        return cls(Ed25519PrivateKey.from_private_bytes(hashlib.sha256(seed.encode()).digest()))

    @classmethod
    def generate(cls) -> Key:
        return cls(Ed25519PrivateKey.generate())

    def sign_obj(self, obj: dict, mandate: str | None = None) -> dict:
        entry = {"key": self.public, "sig": self._priv.sign(digest(obj)).hex()}
        if mandate:
            entry["mandate"] = mandate
        return entry


KEY_RE = re.compile(r"ed25519:[0-9a-f]{64}\Z")
SIG_RE = re.compile(r"[0-9a-f]{128}\Z")
_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
# y-coordinates of the eight points of small order (order dividing 8). A key whose point has
# small order lets anyone produce "signatures" that verify on many messages, so such keys are
# never valid Party or agent keys (spec/01-domain.md §1.3). tests/test_crypto.py recomputes them.
SMALL_ORDER_Y = frozenset({
    0,
    1,
    _P - 1,
    0x05FC536D880238B13933C6D305ACDFD5F098EFF289F4C345B027B2C28F95E826,
    0x7A03AC9277FDC74EC6CC392CFA53202A0F67100D760B3CBA4FD84D3D706A17C7,
})


def _y(b: bytes) -> int:
    return int.from_bytes(b, "little") & ((1 << 255) - 1)


def valid_key(pub: object) -> bool:
    """A public key is valid iff it is lowercase hex, canonically encoded, and not of small order."""
    if not (isinstance(pub, str) and KEY_RE.match(pub)):
        return False
    y = _y(bytes.fromhex(pub[8:]))
    return y < _P and y not in SMALL_ORDER_Y


def verify(pub: object, sig_hex: object, obj: dict) -> bool:
    """Strict Ed25519 verification (spec/01-domain.md §1.3).

    Encodings must be canonical: lowercase hex, a valid key (see valid_key), R with y < p,
    and S < L. The equation is then checked by the cryptography package (cofactorless).
    The JavaScript engine applies the same rules, so both accept exactly the same signatures.
    """
    if not valid_key(pub) or not (isinstance(sig_hex, str) and SIG_RE.match(sig_hex)):
        return False
    sig = bytes.fromhex(sig_hex)
    if _y(sig[:32]) >= _P or int.from_bytes(sig[32:], "little") >= _L:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub[8:])).verify(sig, digest(obj))  # type: ignore[index]
        return True
    except (InvalidSignature, ValueError):
        return False


def attach(obj: dict, *entries: dict) -> dict:
    """Return obj with signatures added, sigs sorted by key (one entry per key)."""
    by_key = {s["key"]: s for s in obj.get("sigs", [])}
    for e in entries:
        by_key[e["key"]] = e
    out = dict(obj)
    out["sigs"] = [by_key[k] for k in sorted(by_key)]
    return out
