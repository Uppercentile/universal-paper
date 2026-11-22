"""Ed25519, SHA-256 and canonical JSON against published test vectors, plus the strict verification rules."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from universal_paper.canon import CanonError, content_hash, jcs, normalize
from universal_paper.crypto import SMALL_ORDER_Y, Key, valid_key, verify

ROOT = Path(__file__).resolve().parent.parent
P = 2**255 - 19
L = 2**252 + 27742317777372353535851937790883648493

# RFC 8032 §7.1, TEST 1 to TEST 3: (secret, public, message, signature).
RFC8032 = [
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    ("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
     "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025", "af82",
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
]


@pytest.mark.parametrize("secret,public,msg,sig", RFC8032)
def test_python_ed25519_matches_rfc8032(secret, public, msg, sig):
    k = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(secret))
    assert k.sign(bytes.fromhex(msg)).hex() == sig
    assert Key(k).public == "ed25519:" + public


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_javascript_ed25519_and_hashes_match_published_vectors(tmp_path):
    script = tmp_path / "v.mjs"
    script.write_text(
        'import { createRequire } from "node:module"; const require = createRequire(import.meta.url);\n'
        f'require({json.dumps(str(ROOT / "explorer/src/up-crypto.js"))}); const UP = globalThis.UP;\n'
        f"const V = {json.dumps(RFC8032)};\n"
        "const out = V.map(([s, p, m, g]) => [UP.hex(UP.ed25519.publicFromSecret(UP.unhex(s))), UP.hex(UP.ed25519.sign(UP.unhex(s), UP.unhex(m))),"
        " UP.ed25519.verify(UP.unhex(p), UP.unhex(m), UP.unhex(g))]);\n"
        'out.push(UP.hex(UP.sha256(UP.utf8("abc"))), UP.hex(UP.sha256(UP.utf8(""))), UP.hex(UP.sha512(UP.utf8("abc"))));\n'
        'out.push(UP.hex(UP.sha256(UP.utf8("a".repeat(1000)))));\n'
        "console.log(JSON.stringify(out));\n")
    out = json.loads(subprocess.run(["node", str(script)], capture_output=True, text=True, check=True).stdout)
    for (_s, p, _m, g), (pub, sig, ok) in zip(RFC8032, out[:3]):
        assert (pub, sig, ok) == (p, g, True)
    assert out[3] == hashlib.sha256(b"abc").hexdigest() == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert out[4] == hashlib.sha256(b"").hexdigest()
    assert out[5] == hashlib.sha512(b"abc").hexdigest()
    assert out[6] == hashlib.sha256(b"a" * 1000).hexdigest()


# ---- strict verification -------------------------------------------------------

def _torsion_ys():
    """Recompute the y-coordinates of every point of order dividing 8, from first principles."""
    d = (-121665 * pow(121666, P - 2, P)) % P

    def add(a, b):
        (x1, y1), (x2, y2) = a, b
        t = d * x1 * x2 * y1 * y2
        return ((x1 * y2 + x2 * y1) * pow(1 + t, P - 2, P) % P, (y1 * y2 + x1 * x2) * pow(1 - t, P - 2, P) % P)

    def mul(k, pt):
        acc = (0, 1)
        while k:
            if k & 1:
                acc = add(acc, pt)
            pt, k = add(pt, pt), k >> 1
        return acc

    def recover(y):
        x2 = (y * y - 1) * pow(d * y * y + 1, P - 2, P) % P
        x = pow(x2, (P + 3) // 8, P)
        if (x * x - x2) % P:
            x = x * pow(2, (P - 1) // 4, P) % P
        return x if (x * x - x2) % P == 0 else None

    ys, y = set(), 2
    while len(ys) < 5 and y < 100:
        x = recover(y)
        if x is not None:
            t = mul(L, (x, y))
            ys |= {mul(k, t)[1] for k in range(8)}
        y += 1
    return ys


def test_small_order_table_is_exactly_the_torsion_points():
    assert set(SMALL_ORDER_Y) == _torsion_ys()


def test_small_order_keys_are_invalid_and_cannot_be_forged_for():
    obj = {"type": "x", "spec": "y"}
    for y in SMALL_ORDER_Y:
        pub = "ed25519:" + y.to_bytes(32, "little").hex()
        assert not valid_key(pub)
        # With the identity point as R and S = 0, a small-order key "verifies" on most messages
        # under plain RFC 8032 rules. The strict rules refuse it.
        assert not verify(pub, (1).to_bytes(32, "little").hex() + "00" * 32, obj)


def test_non_canonical_encodings_rejected():
    k = Key.from_seed("strict")
    obj = {"type": "x", "spec": "y"}
    s = k.sign_obj(obj)
    assert verify(k.public, s["sig"], obj)
    S = int.from_bytes(bytes.fromhex(s["sig"][64:]), "little")
    assert not verify(k.public, s["sig"][:64] + (S + L).to_bytes(32, "little").hex(), obj)  # S >= L
    assert not verify(k.public, s["sig"].upper(), obj)  # signature hex must be lowercase
    assert not verify("ed25519:" + k.public[8:].upper(), s["sig"], obj)  # key hex must be lowercase
    spaced = " ".join(s["sig"][i:i + 2] for i in range(0, 128, 2))
    assert not verify(k.public, spaced, obj)  # bytes.fromhex would have accepted this
    assert not verify("ed25519:" + (P + 1).to_bytes(32, "little").hex(), s["sig"], obj)  # y >= p
    assert not verify(k.public, (P + 1).to_bytes(32, "little").hex() + s["sig"][64:], obj)  # R with y >= p
    assert not verify(None, s["sig"], obj) and not verify(k.public, None, obj)


# ---- canonical JSON ---------------------------------------------------------------

def test_rfc8785_style_examples():
    # Key order is by UTF-16 code units; strings escape only what JSON requires.
    assert jcs({"b": 1, "a": [True, False], "A": "€é\n\u001f"}) == '{"A":"€é\\n\\u001f","a":[true,false],"b":1}'.encode()
    assert jcs({"x": "\U0001F600"}) == '{"x":"😀"}'.encode()


def test_lone_surrogates_non_ascii_keys_and_non_integers_rejected():
    for bad in ["\ud800", "a\udfffb"]:
        with pytest.raises(CanonError):
            jcs({"s": bad})
    with pytest.raises(CanonError):
        jcs({"é": 1})
    for bad in [1.5, float("nan"), float("inf"), 2**53, -(2**53), 1e300]:
        with pytest.raises(CanonError):
            jcs({"n": bad})


def test_integral_floats_canonicalize_as_integers():
    assert jcs({"n": 100.0, "m": -0.0}) == b'{"m":0,"n":100}'
    assert content_hash({"n": 1e2}) == content_hash({"n": 100})
    assert normalize({"a": [1.0, 2.5, {"b": 3.0}]}) == {"a": [1, 2.5, {"b": 3}]}
