"""Payload-shape helper for the OPTIONAL Verifiable Credentials convention. Not part of Universal Paper.

This file only builds and reads the *shape* of a minimal, UNSIGNED W3C Verifiable Credential
(VC Data Model 2.0) whose claims reference a Universal Paper fingerprint:

  - roster_participation(...)  a snapshot of one participant's participation status under an agreement
  - role_proof(...)            a role an issuer assigns to an agent or user, with respect to an agreement
  - extract(vc)                the fingerprint and the basic claims, read back out

It does NOT sign, issue, verify, resolve DIDs, check status lists or evaluate anything. Signing and
proof verification belong to any standard VC library. Whether a member is an active participant, so
that terms and prices apply, is answered by a Universal Paper engine (e.g. simulate_eligibility),
never by this file or by the credential.

Standard library only; no dependency on the universal-paper package. Pass in a fingerprint you
computed with any Universal Paper implementation (e.g. `up hash bundle.json`).

Docs: docs/integrations/verifiable-credentials.md. Code: Apache-2.0.
"""
from __future__ import annotations

import re
from typing import Any

VC_V2_CONTEXT = "https://www.w3.org/ns/credentials/v2"
PARTICIPATION_TYPE = "ParticipationStatusCredential"
ROLE_TYPE = "RoleCredential"
STATUSES = ("active", "inactive")

_FINGERPRINT = re.compile(r"^sha256:[0-9a-f]{64}$")


def _fingerprint(fp: Any) -> str:
    if not isinstance(fp, str) or not _FINGERPRINT.match(fp):
        raise ValueError("agreementFingerprint must be a Universal Paper fingerprint: 'sha256:' + 64 lowercase hex digits")
    return fp


def _text(x: Any, what: str) -> str:
    if not isinstance(x, str) or not x.strip():
        raise ValueError(f"{what} must be a non-empty string")
    return x


def _envelope(kind: str, issuer: str, subject: dict, valid_from: str | None, valid_until: str | None) -> dict:
    vc: dict[str, Any] = {"@context": [VC_V2_CONTEXT], "type": ["VerifiableCredential", kind],
                          "issuer": _text(issuer, "issuer")}
    if valid_from is not None:
        vc["validFrom"] = _text(valid_from, "validFrom")
    if valid_until is not None:
        vc["validUntil"] = _text(valid_until, "validUntil")
    vc["credentialSubject"] = subject
    return vc


def roster_participation(*, issuer: str, agreement_fingerprint: str, participant_id: str, participant_scheme: str,
                         participant_status: str, eligible_as_of: str | None = None,
                         valid_from: str | None = None, valid_until: str | None = None) -> dict:
    """An unsigned VC: a snapshot of one participant's participation status under the referenced artifact."""
    if participant_status not in STATUSES:
        raise ValueError(f"participantStatus must be one of {STATUSES}")
    subject: dict[str, Any] = {
        "agreementFingerprint": _fingerprint(agreement_fingerprint),
        "participant": {"scheme": _text(participant_scheme, "participant scheme"), "id": _text(participant_id, "participant id")},
        "participantStatus": participant_status,
    }
    if eligible_as_of is not None:
        subject["eligibleAsOf"] = _text(eligible_as_of, "eligibleAsOf")
    return _envelope(PARTICIPATION_TYPE, issuer, subject, valid_from, valid_until)


def role_proof(*, issuer: str, agreement_fingerprint: str, subject_id: str, role: str,
               valid_from: str | None = None, valid_until: str | None = None) -> dict:
    """An unsigned VC: the issuer says the subject (an agent or user) holds `role` with respect to the referenced artifact."""
    subject = {"id": _text(subject_id, "subject id"), "agreementFingerprint": _fingerprint(agreement_fingerprint),
               "role": _text(role, "role")}
    return _envelope(ROLE_TYPE, issuer, subject, valid_from, valid_until)


def extract(vc: dict) -> dict:
    """The fingerprint and basic claims of a payload of either shape. Reads the shape only: no proof is checked.

    Run your VC library's verification first, then call this on the verified credential.
    """
    if not isinstance(vc, dict):
        raise ValueError("a credential is a JSON object")
    types = vc.get("type") or []
    kind = next((t for t in (PARTICIPATION_TYPE, ROLE_TYPE) if t in types), None)
    subject = vc.get("credentialSubject")
    if kind is None or not isinstance(subject, dict):
        raise ValueError(f"not a {PARTICIPATION_TYPE} or {ROLE_TYPE} payload")
    out: dict[str, Any] = {"kind": kind, "issuer": vc.get("issuer"),
                           "agreementFingerprint": _fingerprint(subject.get("agreementFingerprint")),
                           "validFrom": vc.get("validFrom"), "validUntil": vc.get("validUntil")}
    if kind == PARTICIPATION_TYPE:
        p = subject.get("participant") or {}
        out.update(participantScheme=p.get("scheme"), participantId=p.get("id"),
                   participantStatus=subject.get("participantStatus"), eligibleAsOf=subject.get("eligibleAsOf"))
    else:
        out.update(subjectId=subject.get("id"), role=subject.get("role"))
    return out
