"""Building final standings from collected submissions.

An organizer drops every ``.edsgs`` file into one directory and closes
the event. This module verifies each file, rejects the ones that do not
belong, ranks the rest, and produces a structure the report writers turn
into JSON, Markdown, HTML and PDF.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from edsg.core.crypto import fingerprint, verify_document
from edsg.core.errors import DocumentError, EDSGError, SignatureError
from edsg.core.models import (
    DOC_TYPE_SUBMISSION,
    SUBMISSION_SUFFIX,
    EventDefinition,
    Submission,
)
from edsg.core.tiers import ProgressReport, build_progress


@dataclass
class LoadedSubmission:
    """A submission file and what became of it."""

    path: Path
    submission: Submission | None
    signer_fingerprint: str = ""
    accepted: bool = False
    rejection: str = ""

    @property
    def display_name(self) -> str:
        if self.submission is not None:
            return f"CMDR {self.submission.commander_name}"
        return self.path.name


@dataclass
class Standing:
    """One commander's place in the final table."""

    rank: int
    commander_name: str
    commander_fid: str
    total_points: float
    per_criterion: dict[str, float]
    per_criterion_units: dict[str, float]
    submitted_at: str
    tied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "commander_name": self.commander_name,
            "commander_fid": self.commander_fid,
            "total_points": self.total_points,
            "per_criterion": self.per_criterion,
            "per_criterion_units": self.per_criterion_units,
            "submitted_at": self.submitted_at,
            "tied": self.tied,
        }


@dataclass
class StandingsReport:
    """The complete outcome of a closed event."""

    event: EventDefinition
    standings: list[Standing]
    accepted: list[LoadedSubmission]
    rejected: list[LoadedSubmission]
    generated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )
    generator_version: str = ""

    @property
    def participant_count(self) -> int:
        return len(self.standings)

    @property
    def total_points(self) -> float:
        """Return the combined score of every ranked commander.

        This is what a tiered event measures its collective progress
        against: one number the whole field pushes upward.
        """
        return round(sum(item.total_points for item in self.standings), 4)

    def progress(self) -> ProgressReport | None:
        """Return tier progress, or ``None`` when the event has no plan."""
        if not self.event.tiers.enabled:
            return None
        return build_progress(self.event.tiers, self.standings)

    def criterion_labels(self) -> list[str]:
        return [criterion.label for criterion in self.event.criteria]

    def to_dict(self) -> dict[str, Any]:
        progress = self.progress()
        return {
            "event": self.event.to_dict(),
            "progress": progress.to_dict() if progress else None,
            "generated_at": self.generated_at,
            "generator_version": self.generator_version,
            "participant_count": self.participant_count,
            "standings": [item.to_dict() for item in self.standings],
            "rejected": [
                {
                    "file": item.path.name,
                    "commander": (
                        item.submission.commander_name if item.submission else ""
                    ),
                    "reason": item.rejection,
                }
                for item in self.rejected
            ],
            "submissions": [
                {
                    "file": item.path.name,
                    "signer_fingerprint": item.signer_fingerprint,
                    "commander_name": item.submission.commander_name,
                    "commander_fid": item.submission.commander_fid,
                    "generated_at": item.submission.generated_at,
                    "generator_version": item.submission.generator_version,
                    "eligible": item.submission.eligible,
                    "eligibility_reason": item.submission.eligibility_reason,
                    "squadron_evidence": item.submission.squadron_evidence,
                    "scan": item.submission.scan.to_dict(),
                    "results": [result.to_dict() for result in item.submission.results],
                }
                for item in self.accepted
                if item.submission is not None
            ],
        }


def load_submission_file(path: Path) -> LoadedSubmission:
    """Read, verify and parse one submission file.

    Verification failures are captured rather than raised, because a
    single bad file must not stop an organizer closing their event.
    """
    loaded = LoadedSubmission(path=path, submission=None)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        loaded.rejection = f"Could not read the file: {exc}"
        return loaded

    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        loaded.rejection = f"Not valid JSON: {exc}"
        return loaded

    try:
        payload = verify_document(envelope, expected_type=DOC_TYPE_SUBMISSION)
    except SignatureError as exc:
        loaded.rejection = str(exc)
        return loaded
    except DocumentError as exc:
        loaded.rejection = str(exc)
        return loaded

    try:
        loaded.submission = Submission.from_dict(payload)
    except EDSGError as exc:
        loaded.rejection = f"Submission could not be read: {exc}"
        return loaded

    public_key = envelope.get("public_key")
    if isinstance(public_key, str):
        loaded.signer_fingerprint = fingerprint(public_key)
    return loaded


def collect_submissions(directory: Path) -> list[LoadedSubmission]:
    """Load every submission file in ``directory``, sorted by name."""
    if not directory.is_dir():
        raise DocumentError(f"Not a directory: {directory}")
    paths = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() == SUBMISSION_SUFFIX
    )
    return [load_submission_file(path) for path in paths]


def _screen(
    loaded: list[LoadedSubmission],
    event: EventDefinition,
    invitation_fingerprint: str,
) -> tuple[list[LoadedSubmission], list[LoadedSubmission]]:
    """Split loaded submissions into accepted and rejected.

    Later submissions from the same commander supersede earlier ones, so
    a participant who reruns their scan can simply send a new file.
    """
    accepted: list[LoadedSubmission] = []
    rejected: list[LoadedSubmission] = []
    best_by_fid: dict[str, LoadedSubmission] = {}

    for item in loaded:
        if item.submission is None:
            rejected.append(item)
            continue
        submission = item.submission

        if submission.event_id != event.event_id:
            item.rejection = (
                f"Submitted for a different event: "
                f"'{submission.event_name}' (id {submission.event_id[:12]}…), "
                f"not '{event.name}' (id {event.event_id[:12]}…). The "
                f"participant may have used an older invitation."
            )
            rejected.append(item)
            continue

        if (
            invitation_fingerprint
            and submission.invitation_fingerprint
            and submission.invitation_fingerprint != invitation_fingerprint
        ):
            item.rejection = (
                "Generated from an invitation signed by a different key. "
                "The participant may have used an outdated or forged "
                "invitation file."
            )
            rejected.append(item)
            continue

        if not submission.eligible:
            item.rejection = (
                submission.eligibility_reason
                or "Participant was not eligible for this event."
            )
            rejected.append(item)
            continue

        if not submission.commander_fid:
            item.rejection = "Submission carries no commander ID."
            rejected.append(item)
            continue

        previous = best_by_fid.get(submission.commander_fid)
        if previous is None:
            best_by_fid[submission.commander_fid] = item
            continue

        assert previous.submission is not None
        # Strictly newer wins. On an exact tie the first file encountered
        # is kept, so the outcome does not depend on filename ordering.
        if submission.generated_at > previous.submission.generated_at:
            previous.rejection = (
                f"Superseded by a newer submission from the same commander "
                f"({submission.generated_at})."
            )
            rejected.append(previous)
            best_by_fid[submission.commander_fid] = item
        else:
            item.rejection = (
                f"Superseded by a newer submission from the same commander "
                f"({previous.submission.generated_at})."
            )
            rejected.append(item)

    accepted = list(best_by_fid.values())
    return accepted, rejected


def build_standings(
    event: EventDefinition,
    loaded: list[LoadedSubmission],
    invitation_fingerprint: str = "",
    generator_version: str = "",
) -> StandingsReport:
    """Rank accepted submissions and produce the full report."""
    accepted, rejected = _screen(loaded, event, invitation_fingerprint)

    from edsg.core.models import TieBreak

    def sort_key(item: LoadedSubmission) -> tuple[Any, ...]:
        submission = item.submission
        assert submission is not None
        primary = -submission.total_points
        if event.tie_break is TieBreak.EARLIEST_SUBMISSION:
            return (primary, submission.generated_at, submission.commander_name)
        if event.tie_break is TieBreak.MOST_CRITERIA_SCORED:
            scored = sum(1 for r in submission.results if r.points > 0)
            return (primary, -scored, submission.commander_name)
        return (primary, submission.commander_name.lower())

    ordered = sorted(accepted, key=sort_key)

    standings: list[Standing] = []
    previous_points: float | None = None
    previous_rank = 0
    for index, item in enumerate(ordered, start=1):
        submission = item.submission
        assert submission is not None
        points = round(submission.total_points, 4)
        # Standard competition ranking: equal scores share a rank and the
        # next distinct score skips ahead.
        if previous_points is not None and points == previous_points:
            rank = previous_rank
        else:
            rank = index
            previous_rank = rank
            previous_points = points

        standings.append(
            Standing(
                rank=rank,
                commander_name=submission.commander_name,
                commander_fid=submission.commander_fid,
                total_points=points,
                per_criterion={
                    result.criterion_id: round(result.points, 4)
                    for result in submission.results
                },
                per_criterion_units={
                    result.criterion_id: round(result.counted_units, 4)
                    for result in submission.results
                },
                submitted_at=submission.generated_at,
            )
        )

    counts: dict[float, int] = {}
    for standing in standings:
        counts[standing.total_points] = counts.get(standing.total_points, 0) + 1
    for standing in standings:
        standing.tied = counts[standing.total_points] > 1

    return StandingsReport(
        event=event,
        standings=standings,
        accepted=ordered,
        rejected=rejected,
        generator_version=generator_version,
    )


__all__ = [
    "LoadedSubmission",
    "Standing",
    "StandingsReport",
    "build_standings",
    "collect_submissions",
    "load_submission_file",
]
