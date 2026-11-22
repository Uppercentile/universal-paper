"""Ed25519 keys and signatures over content hashes (spec/01-domain.md §1.3)."""
from __future__ import annotations

import hashlib

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
    def from_seed(cls, seed: str) -> "Key":
        return cls(Ed25519PrivateKey.from_private_bytes(hashlib.sha256(seed.encode()).digest()))

    @classmethod
    def generate(cls) -> "Key":
        return cls(Ed25519PrivateKey.generate())

    def sign_obj(self, obj: dict, mandate: str | None = None) -> dict:
        entry = {"key": self.public, "sig": self._priv.sign(digest(obj)).hex()}
        if mandate:
            entry["mandate"] = mandate
        return entry


def verify(pub: str, sig_hex: str, obj: dict) -> bool:
    try:
        if not pub.startswith("ed25519:"):
            return False
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub[8:])).verify(bytes.fromhex(sig_hex), digest(obj))
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
