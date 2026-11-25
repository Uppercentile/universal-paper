"""The OPTIONAL Verifiable Credentials convention (examples/integrations/vc/). Not part of the language.

These tests check only that the static examples reference a real fingerprint, stay within their
narrow shapes, and match the payload-shape helper. Nothing in the core depends on them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VC_EX = ROOT / "examples" / "integrations" / "vc"
sys.path.insert(0, str(VC_EX))

import up_vc  # noqa: E402

from universal_paper import whatif  # noqa: E402
from universal_paper.canon import content_hash  # noqa: E402

CONVENTIONAL = json.loads((ROOT / "examples/conventional/bundle.json").read_text(encoding="utf-8"))
FP = content_hash(CONVENTIONAL)
FORBIDDEN = ("price", "fee", "limit", "cap", "amount", "mandate", "bound", "tier", "rebate", "order")


def load(name: str) -> dict:
    return json.loads((VC_EX / name).read_text(encoding="utf-8"))


def keys(x) -> set[str]:
    if isinstance(x, dict):
        return set(x) | {k for v in x.values() for k in keys(v)}
    if isinstance(x, list):
        return {k for v in x for k in keys(v)}
    return set()


def test_exactly_two_static_examples():
    assert sorted(p.name for p in VC_EX.glob("*.json")) == ["role-proof.json", "roster-participation.json"]


@pytest.mark.parametrize("name", ["roster-participation.json", "role-proof.json"])
def test_examples_reference_a_real_non_mandate_fingerprint_and_are_unsigned(name):
    vc = load(name)
    assert vc["credentialSubject"]["agreementFingerprint"] == FP
    assert CONVENTIONAL["mandates"] == []
    assert "proof" not in vc  # signing is a VC library's job
    assert vc["@context"] == [up_vc.VC_V2_CONTEXT]
    assert not [k for k in keys(vc) if any(w in k.casefold() for w in FORBIDDEN)]


def test_roster_participation_shape_and_helper():
    vc = load("roster-participation.json")
    assert set(vc["credentialSubject"]) == {"agreementFingerprint", "participant", "participantStatus", "eligibleAsOf"}
    s = vc["credentialSubject"]
    assert vc == up_vc.roster_participation(
        issuer=vc["issuer"], agreement_fingerprint=FP, participant_id=s["participant"]["id"],
        participant_scheme=s["participant"]["scheme"], participant_status=s["participantStatus"],
        eligible_as_of=s["eligibleAsOf"], valid_from=vc["validFrom"], valid_until=vc["validUntil"])
    c = up_vc.extract(vc)
    assert (c["kind"], c["agreementFingerprint"], c["participantId"], c["participantStatus"]) == \
        ("ParticipationStatusCredential", FP, "HYP000001", "active")


def test_snapshot_agrees_with_the_engine_at_its_time():
    # the example snapshot is honest at eligibleAsOf; the engine, not the credential, is the authority
    c = up_vc.extract(load("roster-participation.json"))
    assert whatif.simulate_eligibility(CONVENTIONAL, c["participantId"], c["eligibleAsOf"])["eligible"] is True
    assert whatif.simulate_eligibility(CONVENTIONAL, c["participantId"], "2028-06-01T00:00:00Z")["eligible"] is False


def test_role_proof_shape_and_helper():
    vc = load("role-proof.json")
    assert set(vc["credentialSubject"]) == {"id", "agreementFingerprint", "role"}
    s = vc["credentialSubject"]
    assert vc == up_vc.role_proof(issuer=vc["issuer"], agreement_fingerprint=FP, subject_id=s["id"], role=s["role"],
                                  valid_from=vc["validFrom"], valid_until=vc["validUntil"])
    c = up_vc.extract(vc)
    assert (c["kind"], c["agreementFingerprint"], c["subjectId"], c["role"]) == \
        ("RoleCredential", FP, "did:example:purchasing-agent-01", "purchasing-agent")


def test_helper_rejects_bad_shapes():
    with pytest.raises(ValueError):
        up_vc.roster_participation(issuer="did:example:a", agreement_fingerprint="sha256:abc", participant_id="X",
                                   participant_scheme="HIN", participant_status="active")
    with pytest.raises(ValueError):
        up_vc.roster_participation(issuer="did:example:a", agreement_fingerprint=FP, participant_id="X",
                                   participant_scheme="HIN", participant_status="member")
    with pytest.raises(ValueError):
        up_vc.extract({"type": ["VerifiableCredential"], "credentialSubject": {"agreementFingerprint": FP}})
