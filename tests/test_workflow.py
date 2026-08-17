"""End-to-end workflow: issue, participate, close, regenerate."""

from __future__ import annotations

import json

import pytest

from conftest import commander_events
from edsg.core.crypto import generate_identity
from edsg.core.errors import DocumentError, EventStateError, SignatureError
from edsg.core.models import (
    INVITATION_SUFFIX,
    SUBMISSION_SUFFIX,
    Eligibility,
    EventState,
)
from edsg.core.workflow import (
    close_event,
    issue_invitation,
    load_invitation,
    participate,
    regenerate_standings,
)


def mining_journal(
    make_journal, tonnes, name="TESTER", fid="F1234567", squadron=110393
):
    """Build a journal for a commander in the test squadron.

    Membership is included by default because every event is now
    squadron-locked; pass ``squadron=None`` to build an outsider.
    """
    events = commander_events(name, fid)
    if squadron is not None:
        events.append(
            {
                "timestamp": "2026-06-01T12:00:03Z",
                "event": "SquadronStartup",
                "SquadronID": squadron,
                "SquadronName": "TEST SQUADRON",
                "CurrentRank": 3,
                "CurrentRankName": "Intern",
            }
        )
    events += [
        {
            "timestamp": "2026-06-05T10:00:00Z",
            "event": "MiningRefined",
            "Type": "$tritium_name;",
            "Type_Localised": "Tritium",
        }
        for _ in range(tonnes)
    ]
    return make_journal(events, name=fid)


def test_full_cycle(tmp_path, make_journal, simple_event, identity):
    invitation_path = issue_invitation(simple_event, identity, tmp_path)
    assert invitation_path.suffix == INVITATION_SUFFIX
    assert simple_event.state is EventState.OPEN

    invitation = load_invitation(invitation_path)
    assert invitation.event.name == "Test Event"
    assert invitation.signer_fingerprint == identity.fingerprint

    subs = tmp_path / "subs"
    for fid, tonnes in (("F0000001", 10), ("F0000002", 25)):
        journal = mining_journal(make_journal, tonnes, name=fid, fid=fid)
        participant = generate_identity(fid)
        path, submission, _ = participate(invitation, journal, participant, subs)
        assert path.name.endswith(SUBMISSION_SUFFIX)
        assert fid in path.name
        assert submission.total_points == tonnes * 2.0

    report = close_event(simple_event, subs, invitation.signer_fingerprint)
    assert simple_event.state is EventState.CLOSED
    assert [s.commander_fid for s in report.standings] == ["F0000002", "F0000001"]
    assert report.standings[0].total_points == 50.0
    assert not report.rejected


def test_submission_filename_names_the_event_and_commander(
    tmp_path, make_journal, simple_event, identity
):
    """A commander in several events must not overwrite their own file."""
    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))
    journal = mining_journal(make_journal, 3, name="SOME NAME", fid="F9998887")
    path, _, _ = participate(
        invitation, journal, generate_identity("p"), tmp_path / "out"
    )
    assert path.name == "Test-Event-F9998887-SOME-NAME.edsgs"


def test_closing_twice_is_refused(tmp_path, make_journal, simple_event, identity):
    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))
    subs = tmp_path / "subs"
    participate(
        invitation, mining_journal(make_journal, 5), generate_identity("p"), subs
    )
    close_event(simple_event, subs)
    with pytest.raises(EventStateError, match="already closed"):
        close_event(simple_event, subs)


def test_closed_event_cannot_issue_again(
    tmp_path, make_journal, simple_event, identity
):
    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))
    subs = tmp_path / "subs"
    participate(
        invitation, mining_journal(make_journal, 5), generate_identity("p"), subs
    )
    close_event(simple_event, subs)
    with pytest.raises(EventStateError, match="closed"):
        issue_invitation(simple_event, identity, tmp_path / "again.edsgi")


def test_regeneration_reproduces_the_standings(
    tmp_path, make_journal, simple_event, identity
):
    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))
    subs = tmp_path / "subs"
    for fid, tonnes in (("F0000001", 10), ("F0000002", 25)):
        journal = mining_journal(make_journal, tonnes, name=fid, fid=fid)
        participate(invitation, journal, generate_identity(fid), subs)

    first = close_event(simple_event, subs)
    closed_at = simple_event.closed_at
    again = regenerate_standings(simple_event, subs)

    assert [(s.rank, s.commander_fid, s.total_points) for s in again.standings] == [
        (s.rank, s.commander_fid, s.total_points) for s in first.standings
    ]
    # Regeneration must not restamp the closing time.
    assert simple_event.closed_at == closed_at


def test_regenerating_an_open_event_is_refused(tmp_path, simple_event):
    with pytest.raises(EventStateError, match="closed"):
        regenerate_standings(simple_event, tmp_path)


def test_tampered_submission_is_rejected(
    tmp_path, make_journal, simple_event, identity
):
    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))
    subs = tmp_path / "subs"
    path, _, _ = participate(
        invitation, mining_journal(make_journal, 5), generate_identity("p"), subs
    )
    data = json.loads(path.read_text())
    data["payload"]["total_points"] = 999_999
    path.write_text(json.dumps(data))

    report = close_event(simple_event, subs)
    assert not report.standings
    assert len(report.rejected) == 1
    assert "FAILED" in report.rejected[0].rejection


def test_submission_from_another_invitation_is_rejected(
    tmp_path, make_journal, simple_event, identity
):
    """A participant using a forged invitation must not slip through."""
    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))
    subs = tmp_path / "subs"
    participate(
        invitation, mining_journal(make_journal, 5), generate_identity("p"), subs
    )

    impostor = generate_identity("impostor")
    report = close_event(
        simple_event, subs, invitation_fingerprint=impostor.fingerprint
    )
    assert not report.standings
    assert "different key" in report.rejected[0].rejection


def test_newer_submission_supersedes_older(
    tmp_path, make_journal, simple_event, identity
):
    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))
    subs = tmp_path / "subs"
    participant = generate_identity("p")

    first_path, first_submission, _ = participate(
        invitation, mining_journal(make_journal, 5, fid="F1"), participant, subs
    )

    # Re-sign the first result with an explicitly older stamp and keep it
    # alongside the new one, so "newest wins" is tested rather than which
    # of two same-second writes happened to land first.
    from edsg.core.crypto import sign_document
    from edsg.core.models import DOC_TYPE_SUBMISSION

    first_submission.generated_at = "2026-06-01T00:00:00+00:00"
    older = sign_document(participant, DOC_TYPE_SUBMISSION, first_submission.to_dict())
    (subs / "older.edsgs").write_text(json.dumps(older))
    first_path.unlink()

    participate(
        invitation, mining_journal(make_journal, 40, fid="F1"), participant, subs
    )

    report = close_event(simple_event, subs)
    assert len(report.standings) == 1
    assert report.standings[0].total_points == 80.0
    assert any("Superseded" in item.rejection for item in report.rejected)


def test_squadron_event_admits_a_member(
    tmp_path, make_journal, simple_event, identity, squadron
):
    simple_event.eligibility = Eligibility.SQUADRON
    simple_event.squadron = squadron
    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))

    journal = mining_journal(make_journal, 10, fid="F1", squadron=squadron.squadron_id)
    _, submission, membership = participate(
        invitation, journal, generate_identity("p"), tmp_path / "subs"
    )
    assert membership.is_member
    assert submission.eligible
    assert submission.total_points == 20.0


def test_squadron_event_excludes_a_non_member(
    tmp_path, make_journal, simple_event, identity, squadron
):
    simple_event.eligibility = Eligibility.SQUADRON
    simple_event.squadron = squadron
    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))

    # Explicitly outside the squadron: the helper now puts commanders in
    # it by default, because every event is squadron-locked.
    journal = mining_journal(make_journal, 10, fid="F2", squadron=None)
    _, submission, membership = participate(
        invitation, journal, generate_identity("p"), tmp_path / "subs"
    )
    assert not membership.is_member
    # A submission is still produced, but scores nothing.
    assert not submission.eligible
    assert submission.total_points == 0.0

    report = close_event(simple_event, tmp_path / "subs")
    assert not report.standings
    assert report.rejected


def test_issuing_an_invalid_event_is_refused(tmp_path, identity, simple_event):
    simple_event.criteria = []
    with pytest.raises(Exception, match="not ready"):
        issue_invitation(simple_event, identity, tmp_path)


def test_closing_with_no_submissions_is_refused(tmp_path, simple_event, identity):
    issue_invitation(simple_event, identity, tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(DocumentError, match="No submission files"):
        close_event(simple_event, empty)


def test_invitation_tampering_is_detected(tmp_path, simple_event, identity):
    path = issue_invitation(simple_event, identity, tmp_path)
    data = json.loads(path.read_text())
    data["payload"]["criteria"][0]["points_per_unit"] = 1000
    path.write_text(json.dumps(data))
    with pytest.raises(SignatureError):
        load_invitation(path)


def test_preview_does_not_mutate_the_event(
    tmp_path, make_journal, simple_event, identity
):
    """Previewing must leave the event exactly as it was."""
    from edsg.core.workflow import preview_standings

    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))
    subs = tmp_path / "subs"
    participate(
        invitation, mining_journal(make_journal, 12), generate_identity("p"), subs
    )

    before = (simple_event.state, simple_event.closed_at)
    report = preview_standings(simple_event, subs, invitation.signer_fingerprint)

    assert (simple_event.state, simple_event.closed_at) == before
    assert simple_event.state is EventState.OPEN
    assert report.participant_count == 1
    assert report.standings[0].total_points == 24.0


def test_preview_matches_the_final_standings(
    tmp_path, make_journal, simple_event, identity
):
    """What the organizer previews is what closing will produce."""
    from edsg.core.workflow import preview_standings

    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))
    subs = tmp_path / "subs"
    for fid, tonnes in (("F0000001", 10), ("F0000002", 25)):
        journal = mining_journal(make_journal, tonnes, name=fid, fid=fid)
        participate(invitation, journal, generate_identity(fid), subs)

    preview = preview_standings(simple_event, subs, invitation.signer_fingerprint)
    final = close_event(simple_event, subs, invitation.signer_fingerprint)

    assert [(s.rank, s.commander_fid, s.total_points) for s in preview.standings] == [
        (s.rank, s.commander_fid, s.total_points) for s in final.standings
    ]


def test_preview_reports_submissions_that_would_be_rejected(
    tmp_path, make_journal, simple_event, identity
):
    """A bad file must show up before the event is closed, not after."""
    from edsg.core.workflow import preview_standings

    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))
    subs = tmp_path / "subs"
    participate(
        invitation, mining_journal(make_journal, 5), generate_identity("p"), subs
    )
    (subs / "F9999999.edsgs").write_text('{"not": "an edsg file"}')

    report = preview_standings(simple_event, subs, invitation.signer_fingerprint)
    assert report.participant_count == 1
    assert len(report.rejected) == 1
    assert "F9999999" in report.rejected[0].path.name


def test_preview_works_before_the_event_is_issued(
    tmp_path, make_journal, simple_event, identity
):
    """Preview must not require the OPEN state that closing does."""
    from edsg.core.workflow import preview_standings

    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))
    subs = tmp_path / "subs"
    participate(
        invitation, mining_journal(make_journal, 7), generate_identity("p"), subs
    )

    simple_event.state = EventState.DRAFT
    report = preview_standings(simple_event, subs)
    assert report.participant_count == 1
    assert simple_event.state is EventState.DRAFT


def test_preview_with_no_submissions_is_an_error(tmp_path, simple_event):
    from edsg.core.workflow import preview_standings

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(DocumentError, match="No submission files"):
        preview_standings(simple_event, empty)
