"""Documents exchanged between organizers and participants.

Three document types exist:

``EventDefinition``
    The organizer's working copy, saved locally and editable until the
    event is closed.

Invitation
    A signed, frozen snapshot of an event definition, distributed to
    participants. Extension ``.edsgi``.

Submission
    A signed record of one participant's measured results. Extension
    ``.edsgs``, named for the commander's Frontier ID.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from edsg.core.criteria import Criterion
from edsg.core.errors import CriteriaError, DocumentError
from edsg.core.journal import parse_timestamp
from edsg.core.squadron import SquadronRef
from edsg.core.tiers import TierPlan

DOC_TYPE_INVITATION = "edsg.invitation"
DOC_TYPE_SUBMISSION = "edsg.submission"

INVITATION_SUFFIX = ".edsgi"
SUBMISSION_SUFFIX = ".edsgs"

#: Bumped when the document schema changes in a way older builds cannot
#: read. Distinct from the application version.
SCHEMA_VERSION = 1


class EventState(StrEnum):
    """Lifecycle of an event, from the organizer's point of view."""

    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


class Eligibility(StrEnum):
    """Who may take part."""

    OPEN = "open"
    SQUADRON = "squadron"


class TieBreak(StrEnum):
    """How equal point totals are ordered."""

    EARLIEST_SUBMISSION = "earliest_submission"
    MOST_CRITERIA_SCORED = "most_criteria_scored"
    ALPHABETICAL = "alphabetical"


@dataclass
class EventWindow:
    """The period during which activity counts.

    Both bounds are inclusive and stored as aware UTC datetimes. Elite
    Dangerous journals timestamp in UTC, so an event run across time
    zones needs no conversion beyond what the organizer enters.
    """

    start: datetime | None = None
    end: datetime | None = None

    def contains(self, moment: datetime | None) -> bool:
        """Return whether ``moment`` falls inside the window.

        Events with no timestamp are excluded rather than assumed to be
        in range: counting an undated event would let a malformed journal
        line score points.
        """
        if moment is None:
            return False
        if self.start is not None and moment < self.start:
            return False
        return not (self.end is not None and moment > self.end)

    def describe(self) -> str:
        fmt = "%Y-%m-%d %H:%M UTC"
        if self.start and self.end:
            return f"{self.start.strftime(fmt)} to {self.end.strftime(fmt)}"
        if self.start:
            return f"from {self.start.strftime(fmt)}"
        if self.end:
            return f"until {self.end.strftime(fmt)}"
        return "no time limit"

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> EventWindow:
        data = data or {}
        return cls(
            start=parse_timestamp(data.get("start")),
            end=parse_timestamp(data.get("end")),
        )

    def validate(self) -> list[str]:
        if self.start and self.end and self.end <= self.start:
            return ["The event end must be later than its start."]
        return []


@dataclass
class EventDefinition:
    """Everything that defines a competition."""

    name: str
    organizer_name: str = ""
    description: str = ""
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    window: EventWindow = field(default_factory=EventWindow)
    eligibility: Eligibility = Eligibility.OPEN
    squadron: SquadronRef | None = None
    criteria: list[Criterion] = field(default_factory=list)
    tiers: TierPlan = field(default_factory=TierPlan)
    tie_break: TieBreak = TieBreak.EARLIEST_SUBMISSION
    state: EventState = EventState.DRAFT
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )
    closed_at: str | None = None
    schema_version: int = SCHEMA_VERSION

    def validate(self) -> list[str]:
        """Return every problem preventing the event from being issued."""
        problems: list[str] = []
        if not self.name.strip():
            problems.append("The event needs a name.")
        if not self.criteria:
            problems.append("Add at least one scoring criterion.")
        problems.extend(self.window.validate())
        if self.eligibility is Eligibility.SQUADRON and self.squadron is None:
            problems.append(
                "This event is restricted to a squadron, but no squadron "
                "has been identified. Scan your own journals to detect it."
            )
        problems.extend(self.tiers.validate())
        labels: dict[str, int] = {}
        for criterion in self.criteria:
            problems.extend(criterion.validate())
            key = criterion.label.strip().lower()
            if key:
                labels[key] = labels.get(key, 0) + 1
        for label, count in labels.items():
            if count > 1:
                problems.append(
                    f"{count} criteria share the label '{label}'. Give each "
                    f"a distinct name so the standings stay readable."
                )
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "name": self.name,
            "description": self.description,
            "organizer_name": self.organizer_name,
            "window": self.window.to_dict(),
            "eligibility": self.eligibility.value,
            "squadron": self.squadron.to_dict() if self.squadron else None,
            "criteria": [item.to_dict() for item in self.criteria],
            "tiers": self.tiers.to_dict(),
            "tie_break": self.tie_break.value,
            "state": self.state.value,
            "created_at": self.created_at,
            "closed_at": self.closed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventDefinition:
        schema = int(data.get("schema_version", 1))
        if schema > SCHEMA_VERSION:
            raise DocumentError(
                f"This file uses event schema v{schema}, but this build of "
                f"EDSG understands up to v{SCHEMA_VERSION}. Update EDSG."
            )
        try:
            eligibility = Eligibility(data.get("eligibility", "open"))
            tie_break = TieBreak(
                data.get("tie_break", TieBreak.EARLIEST_SUBMISSION.value)
            )
            state = EventState(data.get("state", EventState.DRAFT.value))
        except ValueError as exc:
            raise DocumentError(f"Unrecognised event setting: {exc}") from exc

        squadron_data = data.get("squadron")
        criteria_data = data.get("criteria") or []
        if not isinstance(criteria_data, list):
            raise CriteriaError("Event criteria are malformed.")

        return cls(
            schema_version=schema,
            event_id=str(data.get("event_id") or uuid.uuid4().hex),
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            organizer_name=str(data.get("organizer_name", "")),
            window=EventWindow.from_dict(data.get("window")),
            eligibility=eligibility,
            squadron=(SquadronRef.from_dict(squadron_data) if squadron_data else None),
            criteria=[Criterion.from_dict(item) for item in criteria_data],
            tiers=TierPlan.from_dict(data.get("tiers")),
            tie_break=tie_break,
            state=state,
            created_at=str(data.get("created_at", "")),
            closed_at=data.get("closed_at"),
        )

    def criterion_by_id(self, criterion_id: str) -> Criterion | None:
        for criterion in self.criteria:
            if criterion.criterion_id == criterion_id:
                return criterion
        return None


@dataclass
class CriterionResult:
    """One participant's measured outcome for one criterion."""

    criterion_id: str
    label: str
    raw_units: float
    counted_units: float
    points: float
    detail: dict[str, Any] = field(default_factory=dict)
    samples: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "label": self.label,
            "raw_units": self.raw_units,
            "counted_units": self.counted_units,
            "points": self.points,
            "detail": self.detail,
            "samples": self.samples,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CriterionResult:
        return cls(
            criterion_id=str(data.get("criterion_id", "")),
            label=str(data.get("label", "")),
            raw_units=float(data.get("raw_units", 0.0)),
            counted_units=float(data.get("counted_units", 0.0)),
            points=float(data.get("points", 0.0)),
            detail=dict(data.get("detail") or {}),
            samples=[str(item) for item in (data.get("samples") or [])],
        )


@dataclass
class ScanSummary:
    """Diagnostics describing the journal scan behind a submission."""

    files_read: int = 0
    entries_parsed: int = 0
    malformed_lines: int = 0
    unreadable_files: list[str] = field(default_factory=list)
    first_event: str | None = None
    last_event: str | None = None
    game_versions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "files_read": self.files_read,
            "entries_parsed": self.entries_parsed,
            "malformed_lines": self.malformed_lines,
            "unreadable_files": self.unreadable_files,
            "first_event": self.first_event,
            "last_event": self.last_event,
            "game_versions": self.game_versions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ScanSummary:
        data = data or {}
        return cls(
            files_read=int(data.get("files_read", 0)),
            entries_parsed=int(data.get("entries_parsed", 0)),
            malformed_lines=int(data.get("malformed_lines", 0)),
            unreadable_files=[
                str(item) for item in (data.get("unreadable_files") or [])
            ],
            first_event=data.get("first_event"),
            last_event=data.get("last_event"),
            game_versions=[str(item) for item in (data.get("game_versions") or [])],
        )


@dataclass
class Submission:
    """A participant's signed results for one event."""

    event_id: str
    event_name: str
    invitation_fingerprint: str
    commander_name: str
    commander_fid: str
    results: list[CriterionResult] = field(default_factory=list)
    total_points: float = 0.0
    eligible: bool = True
    eligibility_reason: str = ""
    squadron_evidence: dict[str, Any] = field(default_factory=dict)
    scan: ScanSummary = field(default_factory=ScanSummary)
    generated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )
    generator_version: str = ""
    schema_version: int = SCHEMA_VERSION

    def filename(self) -> str:
        """Return the canonical filename for this submission."""
        stem = "".join(ch for ch in self.commander_fid if ch.isalnum() or ch in "-_")
        return f"{stem or 'unknown-cmdr'}{SUBMISSION_SUFFIX}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "event_name": self.event_name,
            "invitation_fingerprint": self.invitation_fingerprint,
            "commander_name": self.commander_name,
            "commander_fid": self.commander_fid,
            "results": [item.to_dict() for item in self.results],
            "total_points": self.total_points,
            "eligible": self.eligible,
            "eligibility_reason": self.eligibility_reason,
            "squadron_evidence": self.squadron_evidence,
            "scan": self.scan.to_dict(),
            "generated_at": self.generated_at,
            "generator_version": self.generator_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Submission:
        schema = int(data.get("schema_version", 1))
        if schema > SCHEMA_VERSION:
            raise DocumentError(
                f"This submission uses schema v{schema}, but this build of "
                f"EDSG understands up to v{SCHEMA_VERSION}. Update EDSG."
            )
        return cls(
            schema_version=schema,
            event_id=str(data.get("event_id", "")),
            event_name=str(data.get("event_name", "")),
            invitation_fingerprint=str(data.get("invitation_fingerprint", "")),
            commander_name=str(data.get("commander_name", "")),
            commander_fid=str(data.get("commander_fid", "")),
            results=[
                CriterionResult.from_dict(item) for item in (data.get("results") or [])
            ],
            total_points=float(data.get("total_points", 0.0)),
            eligible=bool(data.get("eligible", True)),
            eligibility_reason=str(data.get("eligibility_reason", "")),
            squadron_evidence=dict(data.get("squadron_evidence") or {}),
            scan=ScanSummary.from_dict(data.get("scan")),
            generated_at=str(data.get("generated_at", "")),
            generator_version=str(data.get("generator_version", "")),
        )


__all__ = [
    "DOC_TYPE_INVITATION",
    "DOC_TYPE_SUBMISSION",
    "INVITATION_SUFFIX",
    "SCHEMA_VERSION",
    "SUBMISSION_SUFFIX",
    "CriterionResult",
    "Eligibility",
    "EventDefinition",
    "EventState",
    "EventWindow",
    "ScanSummary",
    "Submission",
    "TieBreak",
]
