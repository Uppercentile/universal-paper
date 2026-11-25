"""Optional reference adapter: Universal Paper artifacts <-> Legal Context Protocol (LCP) discovery files.

THIS IS AN OPTIONAL EXTERNAL INTEGRATION, NOT PART OF THE UNIVERSAL PAPER LANGUAGE.
Universal Paper does not depend on LCP. Nothing here changes how Universal Paper objects are
written, hashed, signed or evaluated. See docs/integrations/legal-context-protocol.md.

The whole idea fits in one line. LCP's `atrHash` is the SHA-256 of the terms document's bytes as
served. A Universal Paper fingerprint is the SHA-256 of the object's canonical JSON (RFC 8785, as
restricted by spec/01-domain.md §1). So if the published terms document IS those canonical bytes,
the two hashes are the same 32 bytes:

    atrHash  = "0x"     + hex(SHA-256(served bytes))
    UP hash  = "sha256:" + hex(SHA-256(JCS(strip(object))))

This module only reuses the reference interpreter's canonicalization (universal_paper.canon); it
adds no hashing of its own. Standard library otherwise. Apache-2.0, like the rest of the code.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from universal_paper.canon import content_hash, jcs, normalize

LCP_SPEC = "https://legalcontextprotocol.org/standard"
_HEX64 = re.compile(r"[0-9a-fA-F]{64}")


# ----------------------------------------------------------------------------- fingerprints
def fingerprint(obj: dict) -> str:
    """The Universal Paper fingerprint of a Bundle, Agreement, State, Term definition or any UP object: "sha256:<hex>".

    Exactly universal_paper.canon.content_hash. For signed objects (Events, Mandates) the top-level
    `sigs` are excluded, as the spec says (spec/01-domain.md §1).
    """
    return content_hash(normalize(obj))


def canonical_bytes(obj: dict) -> bytes:
    """The exact bytes to publish as the LCP terms document, so that its SHA-256 equals the UP fingerprint.

    Refuses objects with top-level `sigs` (Events, Mandates): their fingerprint leaves the signatures
    out, so no single file could both carry the signatures and hash to the fingerprint. Publish the
    Bundle that holds them instead.
    """
    if not isinstance(obj, dict):
        raise ValueError("a Universal Paper artifact is a JSON object")
    if "sigs" in obj:
        raise ValueError(f"a signed {obj.get('type', 'object')} cannot be published on its own: its fingerprint excludes "
                         "`sigs`; publish the Bundle that contains it")
    return jcs(normalize(obj))


def _digest_bytes(h: str) -> bytes:
    """32 raw bytes from "sha256:<hex>", "0x<hex>" or bare hex. LCP compares decoded bytes, not strings."""
    if not isinstance(h, str):
        raise ValueError("hash must be a string")
    s = h.strip()
    for prefix in ("sha256:0x", "sha256:", "0x", "0X"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    if not _HEX64.fullmatch(s):
        raise ValueError(f"not a SHA-256 hash: {h!r}")
    return bytes.fromhex(s)


def to_atr_hash(up_fingerprint: str) -> str:
    """"sha256:<hex>" -> "0x<hex>" (lowercase, 66 characters, as LCP recommends for emission)."""
    return "0x" + _digest_bytes(up_fingerprint).hex()


def to_up_fingerprint(atr_hash: str) -> str:
    """"0x<hex>" -> "sha256:<hex>"."""
    return "sha256:" + _digest_bytes(atr_hash).hex()


def same_hash(a: str, b: str) -> bool:
    """True if two hashes in either notation name the same 32 bytes."""
    return _digest_bytes(a) == _digest_bytes(b)


# ----------------------------------------------------------------------------- legal-context.json
def legal_context(terms_url: str, artifact: dict, *, acceptance_required: bool | None = None, **extra: Any) -> dict:
    """A minimal LCP discovery document pointing at a Universal Paper artifact, pinned by its fingerprint.

    Only uses fields defined by the LCP schema: `terms` (required), `termsFormat` and `atrHash`
    (Level 2), and `acceptanceRequired` (Level 3) when given. Anything else in `extra` is copied as is
    (for example `contact` or `disputeResolution`); this function does not check it.
    """
    if not isinstance(terms_url, str) or not terms_url.startswith("https://"):
        raise ValueError("LCP requires `terms` to be an absolute https:// URL")
    canonical_bytes(artifact)  # refuse what cannot be pinned
    doc: dict[str, Any] = {"terms": terms_url, "termsFormat": "json", "atrHash": to_atr_hash(fingerprint(artifact))}
    if acceptance_required is not None:
        doc["acceptanceRequired"] = bool(acceptance_required)
    doc.update(extra)
    return doc


def dumps_legal_context(doc: dict) -> str:
    """legal-context.json text: readable JSON. (The discovery file is not hashed, so any formatting works.)"""
    return json.dumps(doc, indent=2) + "\n"


# ----------------------------------------------------------------------------- verification
@dataclass
class Verification:
    ok: bool
    atr_hash_matches: bool  # SHA-256(served bytes) == atrHash: the LCP Level 2 check
    canonical: bool  # the bytes are the artifact's canonical form, so atrHash is also its UP fingerprint
    fingerprint: str | None  # the UP fingerprint, when the bytes parse
    up_type: str | None  # "Bundle", "Agreement", "Term", ...
    chain_ids: list[str] = field(default_factory=list)  # for a Bundle: the ChainId of every agreement in it
    problems: list[str] = field(default_factory=list)
    artifact: dict | None = None


def verify(lcp: dict, artifact_bytes: bytes, expected_fingerprint: str | None = None) -> Verification:
    """Check that the bytes fetched from `lcp["terms"]` are the Universal Paper artifact the file pins.

    Three checks: the LCP check (SHA-256 of the bytes equals `atrHash`), that the bytes are canonical
    Universal Paper JSON (so the same hash is the UP fingerprint), and, if given, that the fingerprint
    is the one you expected (for example a ChainId or Bundle hash a counterparty sent you).
    Evaluating what the artifact says is a separate step: see `evaluate`.
    """
    problems: list[str] = []
    atr = lcp.get("atrHash") if isinstance(lcp, dict) else None
    if not atr:
        return Verification(False, False, False, None, None, problems=["legal-context.json has no atrHash (LCP Level 1): nothing pins the terms"])
    try:
        atr_bytes = _digest_bytes(atr)
    except ValueError as e:
        return Verification(False, False, False, None, None, problems=[str(e)])
    matches = hashlib.sha256(artifact_bytes).digest() == atr_bytes
    if not matches:
        problems.append("SHA-256 of the terms document does not equal atrHash: these are not the pinned terms")
    try:
        obj = json.loads(artifact_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return Verification(False, matches, False, None, None, problems=problems + [f"terms document is not JSON: {e}"])
    if not isinstance(obj, dict):
        return Verification(False, matches, False, None, None, problems=problems + ["terms document is not a JSON object"])
    try:
        canon = canonical_bytes(obj) == artifact_bytes
        fp: str | None = fingerprint(obj)
    except ValueError as e:
        canon, fp = False, None
        problems.append(str(e))
    if fp and not canon:
        problems.append("terms document is not in canonical form, so atrHash is not its Universal Paper fingerprint; "
                        "publish canonical_bytes(artifact)")
    if expected_fingerprint and fp and not same_hash(expected_fingerprint, fp):
        problems.append(f"fingerprint {fp} is not the expected {expected_fingerprint}")
    chain_ids = []
    if obj.get("type") == "Bundle":
        chain_ids = [content_hash(ch[0]) for ch in obj.get("chains", []) if isinstance(ch, list) and ch and isinstance(ch[0], dict)]
    return Verification(not problems, matches, canon, fp, obj.get("type"), chain_ids, problems, obj)


def fetch(url: str, timeout: float = 20.0, max_bytes: int = 16 * 1024 * 1024) -> bytes:
    """GET a legal-context.json or terms document. https only (LCP requires it). Returns the raw bytes, unmodified."""
    if not url.startswith("https://"):
        raise ValueError("LCP documents must be fetched over https://")
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "up-lcp-reference/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (https enforced above)
        data = r.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"document larger than {max_bytes} bytes")
    return data


def discover(domain_or_url: str) -> dict:
    """Fetch and parse https://{domain}/.well-known/legal-context.json (or a full URL to a discovery file)."""
    url = domain_or_url if domain_or_url.startswith("https://") else f"https://{domain_or_url}/.well-known/legal-context.json"
    doc = json.loads(fetch(url).decode("utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("terms"), str):
        raise ValueError("not an LCP discovery document: `terms` is required")
    return doc


# ----------------------------------------------------------------------------- evaluation (the reference engine, unchanged)
def evaluate(bundle: dict, at: str | None = None) -> dict:
    """Validate a verified Bundle with the reference interpreter and derive its state. Any conforming UP engine works the same.

    Returns {"valid", "rejected_events", "agreement_issues", "state"}; `state` is the reference
    interpreter's snapshot (statuses, tiers, prices, obligations) at `at` or the bundle's latest time.
    """
    from universal_paper.__main__ import _latest
    from universal_paper.engine import Bundle, Evaluator, agreement_issues
    from universal_paper.report import snapshot

    b = Bundle(normalize(bundle))
    ev = Evaluator(b)
    rejected = []
    for ch in b.chain_list:
        if ch:
            rejected += [{"chain": content_hash(ch[0]), "index": st.index, "reason": st.reason}
                         for st in ev.run(content_hash(ch[0])) if not st.accepted]
    issues = [{"agreement": h, "rule": r, "reason": why} for h, ag in sorted(b.agreements.items()) for r, why in agreement_issues(b, ag)]
    return {"valid": not rejected and not issues and not b.forks, "rejected_events": rejected, "agreement_issues": issues,
            "state": snapshot(ev, at or _latest(b))}


def check_mandate(bundle: dict, event: dict) -> dict:
    """Optional: would an agent's hypothetical event be covered by its Mandate? Uses the reference simulator unchanged.

    `event` is a hypothetical event as universal_paper.simulate takes it:
    {chain, kind, by, at, body, agent: {key, mandate}}. Signatures are not needed; Mandate coverage
    (axiom A9) is checked exactly as for a signed event. Returns {"accepted", "reason"}.
    """
    from universal_paper.simulate import simulate

    step = simulate(normalize(bundle), [event])["steps"][0]
    return {"accepted": step["accepted"], "reason": step["reason"] or None}
