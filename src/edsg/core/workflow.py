"""The three operations that make up an event's life.

Kept separate from the user interface so both binaries, and the tests,
drive exactly the same code paths:

1. :func:`issue_invitation` — organizer freezes an event and signs it.
2. :func:`participate` — participant verifies, scans, and signs results.
3. :func:`close_event` — organizer verifies submissions and ranks them.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from edsg.core.canonical import pretty_text
from edsg.core.crypto import (
    Identity,
    fingerprint,
    sign_document,
    verify_document,
)
from edsg.core.errors import (
    CriteriaError,
    DocumentError,
    EventStateError,
    JournalError,
)
from edsg.core.journal import CommanderIdentity, resolve_commander
from edsg.core.metrics import scan_journals
from edsg.core.models import (
    DOC_TYPE_INVITATION,
    DOC_TYPE_SUBMISSION,
    INVITATION_SUFFIX,
    SUBMISSION_SUFFIX,
    Eligibility,
    EventDefinition,
    EventState,
    ScanSummary,
    Submission,
)
from edsg.core.squadron import (
    MembershipResult,
    collect_evidence,
    evaluate_membership,
)
from edsg.core.standings import StandingsReport, build_standings, collect_submissions
from edsg.version import read_version

ProgressCallback = Callable[[int, str], None]


@dataclass
class Invitation:
    """A verified invitation and the identity that signed it."""

    event: EventDefinition
    signer_fingerprint: str
    signer_label: str
    signed_at: str
    envelope: dict[str, Any]

    @property
    def is_squadron_restricted(self) -> bool:
        return self.event.eligibility is Eligibility.SQUADRON


def issue_invitation(
    event: EventDefinition,
    identity: Identity,
    destination: Path,
) -> Path:
    """Freeze ``event``, sign it, and write the invitation file.

    The event moves to :attr:`EventState.OPEN`. Validation runs first so
    an organizer cannot distribute an event that can never score.
    """
    if event.state is EventState.CLOSED:
        raise EventStateError(
            "This event has been closed. Closed events cannot issue new invitations."
        )

    problems = event.validate()
    if problems:
        raise CriteriaError(
            "This event is not ready to be issued:\n  - " + "\n  - ".join(problems)
        )

    event.state = EventState.OPEN
    envelope = sign_document(identity, DOC_TYPE_INVITATION, event.to_dict())

    path = _resolve_output(destination, INVITATION_SUFFIX, _safe_stem(event.name))
    _write_json(path, envelope)
    return path


def load_invitation(path: Path) -> Invitation:
    """Read and cryptographically verify an invitation file."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DocumentError(f"Could not read {path.name}: {exc}") from exc

    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DocumentError(
            f"{path.name} is not a valid EDSG invitation: {exc}"
        ) from exc

    payload = verify_document(envelope, expected_type=DOC_TYPE_INVITATION)
    event = EventDefinition.from_dict(payload)

    meta = envelope.get("edsg", {})
    return Invitation(
        event=event,
        signer_fingerprint=fingerprint(envelope["public_key"]),
        signer_label=str(meta.get("signer_label", "")),
        signed_at=str(envelope.get("signed_at", "")),
        envelope=envelope,
    )


def check_eligibility(
    invitation: Invitation,
    squadron_evidence: list[Any],
) -> MembershipResult:
    """Decide whether a commander may take part.

    Open events admit everyone. Squadron events require a join event for
    the organizer's squadron with no later departure.
    """
    event = invitation.event
    if event.eligibility is Eligibility.OPEN or event.squadron is None:
        return MembershipResult(
            is_member=True,
            squadron=None,
            reason="This event is open to all commanders.",
            evidence=[],
        )
    return evaluate_membership(squadron_evidence, event.squadron.squadron_id)


def participate(
    invitation: Invitation,
    journal_dir: Path,
    identity: Identity,
    destination: Path,
    progress: ProgressCallback | None = None,
    commander_fid: str | None = None,
) -> tuple[Path, Submission, MembershipResult]:
    """Scan a participant's journals and write their signed submission.

    A submission is produced even when the commander turns out to be
    ineligible. Recording the reason and letting the organizer see it is
    more useful than silently refusing, and lets a participant show they
    followed the process when a squadron check goes wrong.
    """
    commander: CommanderIdentity = resolve_commander(journal_dir, commander_fid)

    outcome = scan_journals(
        journal_dir,
        invitation.event.criteria,
        invitation.event.window,
        progress=progress,
    )

    evidence = collect_evidence(outcome.squadron_events)
    membership = check_eligibility(invitation, evidence)

    submission = Submission(
        event_id=invitation.event.event_id,
        event_name=invitation.event.name,
        invitation_fingerprint=invitation.signer_fingerprint,
        commander_name=commander.name,
        commander_fid=commander.fid,
        results=outcome.results,
        total_points=outcome.total_points if membership.is_member else 0.0,
        eligible=membership.is_member,
        eligibility_reason=membership.reason,
        squadron_evidence=membership.to_dict(),
        scan=ScanSummary(
            files_read=outcome.stats.files_read,
            entries_parsed=outcome.stats.entries_parsed,
            malformed_lines=outcome.stats.malformed_lines,
            unreadable_files=outcome.stats.unreadable_files,
            first_event=outcome.first_event,
            last_event=outcome.last_event,
            game_versions=outcome.game_versions,
        ),
        generator_version=read_version(),
    )

    envelope = sign_document(identity, DOC_TYPE_SUBMISSION, submission.to_dict())

    path = _resolve_output(
        destination, SUBMISSION_SUFFIX, commander.safe_filename_stem()
    )
    _write_json(path, envelope)
    return path, submission, membership


def close_event(
    event: EventDefinition,
    submissions_dir: Path,
    invitation_fingerprint: str = "",
) -> StandingsReport:
    """Close ``event`` and compute standings from a submissions directory.

    Closing is one-way. The event definition is marked closed and stamped
    with the time; reopening is not offered anywhere in the application.
    Reports can be regenerated at any time from the retained submissions
    via :func:`regenerate_standings`.
    """
    if event.state is EventState.CLOSED:
        raise EventStateError(
            "This event is already closed. Use 'Regenerate reports' to "
            "produce its outputs again."
        )
    if event.state is EventState.DRAFT:
        raise EventStateError(
            "This event was never issued, so there is nothing to close."
        )

    loaded = collect_submissions(submissions_dir)
    if not loaded:
        raise DocumentError(
            f"No submission files were found in {submissions_dir}. "
            f"Participant files end in {SUBMISSION_SUFFIX}."
        )

    event.state = EventState.CLOSED
    event.closed_at = datetime.now(UTC).isoformat(timespec="seconds")

    return build_standings(
        event,
        loaded,
        invitation_fingerprint=invitation_fingerprint,
        generator_version=read_version(),
    )


def preview_standings(
    event: EventDefinition,
    submissions_dir: Path,
    invitation_fingerprint: str = "",
) -> StandingsReport:
    """Rank the submissions received so far without closing the event.

    Identical scoring to :func:`close_event`, but nothing is mutated: the
    event stays in whatever state it was in, no ``closed_at`` is stamped,
    and no reports are written. This is what lets an organizer see who is
    where, and spot a submission that will be rejected, while the event
    is still running — and check the standings look right *before* taking
    the one irreversible action in the application.
    """
    loaded = collect_submissions(submissions_dir)
    if not loaded:
        raise DocumentError(
            f"No submission files were found in {submissions_dir}. "
            f"Participant files end in {SUBMISSION_SUFFIX}."
        )
    return build_standings(
        event,
        loaded,
        invitation_fingerprint=invitation_fingerprint,
        generator_version=read_version(),
    )


def regenerate_standings(
    event: EventDefinition,
    submissions_dir: Path,
    invitation_fingerprint: str = "",
) -> StandingsReport:
    """Rebuild the reports of an already-closed event.

    Requires only that the participant submissions have been retained.
    The event stays closed and its ``closed_at`` stamp is left untouched,
    so a regenerated report is identical to the original.
    """
    if event.state is not EventState.CLOSED:
        raise EventStateError("Only a closed event's reports can be regenerated.")
    loaded = collect_submissions(submissions_dir)
    if not loaded:
        raise DocumentError(f"No submission files were found in {submissions_dir}.")
    return build_standings(
        event,
        loaded,
        invitation_fingerprint=invitation_fingerprint,
        generator_version=read_version(),
    )


def detect_squadron_from_journals(journal_dir: Path) -> Any:
    """Find the squadron the organizer currently belongs to."""
    from edsg.core.squadron import collect_evidence_from_dir, detect_own_squadron

    try:
        evidence = collect_evidence_from_dir(journal_dir)
    except JournalError:
        raise
    return detect_own_squadron(evidence)


def _resolve_output(destination: Path, suffix: str, default_stem: str) -> Path:
    """Resolve an output path that may name either a file or a directory.

    A path already carrying the right extension is used as-is. Anything
    else is treated as a directory and created, because a caller passing
    a not-yet-existing folder means "put it in here", not "name the file
    this". Getting that wrong wrote a submission to a file named after
    the intended folder.
    """
    if destination.suffix.lower() == suffix:
        destination.parent.mkdir(parents=True, exist_ok=True)
        return destination
    destination.mkdir(parents=True, exist_ok=True)
    return destination / f"{default_stem}{suffix}"


def _safe_stem(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_ " else "-" for ch in name).strip()
    cleaned = "-".join(part for part in cleaned.split() if part)
    return cleaned.lower() or "event"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(pretty_text(payload) + "\n", encoding="utf-8")
    except OSError as exc:
        raise DocumentError(f"Could not write {path}: {exc}") from exc


__all__ = [
    "Invitation",
    "ProgressCallback",
    "check_eligibility",
    "close_event",
    "detect_squadron_from_journals",
    "issue_invitation",
    "load_invitation",
    "participate",
    "preview_standings",
    "regenerate_standings",
]
