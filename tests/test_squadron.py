"""Squadron membership reconciliation.

Departure events (LeftSquadron, KickedFromSquadron, DisbandedSquadron)
do not appear in the sample journals EDSG was developed against, so they
are covered here synthetically against Frontier's documented schema.
"""

from __future__ import annotations

from edsg.core.journal import parse_timestamp
from edsg.core.squadron import (
    SquadronEvidence,
    detect_own_squadron,
    evaluate_membership,
)

SQUAD = 110393


def evidence(event: str, when: str, squadron_id: int = SQUAD) -> SquadronEvidence:
    return SquadronEvidence(
        event=event,
        timestamp=parse_timestamp(when),
        squadron_id=squadron_id,
        squadron_name="TEST SQUADRON",
    )


def test_join_with_no_departure_is_a_member():
    result = evaluate_membership(
        [evidence("JoinedSquadron", "2026-06-01T10:00:00Z")], SQUAD
    )
    assert result.is_member


def test_startup_alone_proves_current_membership():
    """SquadronStartup fires at login for the squadron you are in now."""
    result = evaluate_membership(
        [evidence("SquadronStartup", "2026-06-05T10:00:00Z")], SQUAD
    )
    assert result.is_member
    assert "SquadronStartup" in result.reason


def test_leaving_after_joining_is_not_a_member():
    result = evaluate_membership(
        [
            evidence("JoinedSquadron", "2026-06-01T10:00:00Z"),
            evidence("LeftSquadron", "2026-06-10T10:00:00Z"),
        ],
        SQUAD,
    )
    assert not result.is_member
    assert "left" in result.reason


def test_being_kicked_is_not_a_member():
    result = evaluate_membership(
        [
            evidence("JoinedSquadron", "2026-06-01T10:00:00Z"),
            evidence("KickedFromSquadron", "2026-06-10T10:00:00Z"),
        ],
        SQUAD,
    )
    assert not result.is_member
    assert "kicked" in result.reason


def test_disbanded_squadron_is_not_a_member():
    result = evaluate_membership(
        [
            evidence("JoinedSquadron", "2026-06-01T10:00:00Z"),
            evidence("DisbandedSquadron", "2026-06-10T10:00:00Z"),
        ],
        SQUAD,
    )
    assert not result.is_member


def test_rejoining_after_leaving_is_a_member_again():
    """The newest event wins, so a rejoin restores membership."""
    result = evaluate_membership(
        [
            evidence("JoinedSquadron", "2026-06-01T10:00:00Z"),
            evidence("LeftSquadron", "2026-06-10T10:00:00Z"),
            evidence("JoinedSquadron", "2026-06-15T10:00:00Z"),
        ],
        SQUAD,
    )
    assert result.is_member


def test_login_after_leaving_confirms_the_departure():
    """A SquadronStartup for a different squadron must not resurrect this one."""
    result = evaluate_membership(
        [
            evidence("JoinedSquadron", "2026-06-01T10:00:00Z"),
            evidence("LeftSquadron", "2026-06-10T10:00:00Z"),
            evidence("SquadronStartup", "2026-06-12T10:00:00Z", squadron_id=999),
        ],
        SQUAD,
    )
    assert not result.is_member


def test_applying_is_not_joining():
    result = evaluate_membership(
        [evidence("AppliedToSquadron", "2026-06-01T10:00:00Z")], SQUAD
    )
    assert not result.is_member
    assert "application" in result.reason.lower()


def test_membership_of_another_squadron_does_not_count():
    result = evaluate_membership(
        [evidence("JoinedSquadron", "2026-06-01T10:00:00Z", squadron_id=555)], SQUAD
    )
    assert not result.is_member


def test_simultaneous_join_and_leave_favours_the_departure():
    """A tie is far more likely a leave recorded at login than a join."""
    result = evaluate_membership(
        [
            evidence("JoinedSquadron", "2026-06-01T10:00:00Z"),
            evidence("LeftSquadron", "2026-06-01T10:00:00Z"),
        ],
        SQUAD,
    )
    assert not result.is_member


def test_no_evidence_at_all_is_not_a_member():
    assert not evaluate_membership([], SQUAD).is_member


def test_detect_own_squadron_finds_the_current_one():
    found = detect_own_squadron(
        [
            evidence("JoinedSquadron", "2026-05-01T10:00:00Z", squadron_id=111),
            evidence("LeftSquadron", "2026-05-05T10:00:00Z", squadron_id=111),
            evidence("JoinedSquadron", "2026-06-01T10:00:00Z", squadron_id=222),
        ]
    )
    assert found is not None
    assert found.squadron_id == 222


def test_detect_own_squadron_returns_none_when_departed():
    assert (
        detect_own_squadron(
            [
                evidence("JoinedSquadron", "2026-06-01T10:00:00Z"),
                evidence("LeftSquadron", "2026-06-02T10:00:00Z"),
            ]
        )
        is None
    )


def test_evidence_is_retained_for_the_audit_trail():
    result = evaluate_membership(
        [
            evidence("JoinedSquadron", "2026-06-01T10:00:00Z"),
            evidence("SquadronStartup", "2026-06-02T10:00:00Z"),
        ],
        SQUAD,
    )
    assert len(result.evidence) == 2
    assert result.to_dict()["squadron"]["squadron_id"] == SQUAD
