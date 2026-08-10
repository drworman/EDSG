"""Determining squadron membership from journal evidence.

Organizers may restrict an event to their own squadron. The organizer's
journals establish which squadron that is; each participant's journals
must then show that they joined it and have not since left, been kicked,
or had it disbanded under them.

Evidence quality
----------------
``SquadronStartup`` is the strongest signal available. Elite Dangerous
emits it at login for the squadron the commander is *currently* in, so a
``SquadronStartup`` newer than any departure event is direct evidence of
present membership. ``JoinedSquadron`` only proves membership as of that
moment, so it must be reconciled against later departures.

The sample journals used to develop EDSG contain ``SquadronStartup``,
``AppliedToSquadron``, ``JoinedSquadron``, ``SquadronDemotion`` and
``SharedBookmarkToSquadron``, but no departure events. Departure handling
is therefore written to Frontier's documented event schema rather than
against observed data, and is covered by synthetic tests.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from edsg.core.journal import JournalEntry, ReadStats, iter_journal_dir

#: Events proving the commander is in a squadron at that moment.
JOIN_EVENTS = frozenset({"JoinedSquadron", "SquadronStartup"})

#: Events proving the commander is no longer in a squadron.
LEAVE_EVENTS = frozenset({"LeftSquadron", "KickedFromSquadron", "DisbandedSquadron"})

#: Events that merely mention a squadron; useful as corroboration but
#: never as proof of joining or leaving. Applying is not joining.
MENTION_EVENTS = frozenset(
    {
        "AppliedToSquadron",
        "InvitedToSquadron",
        "SharedBookmarkToSquadron",
        "SquadronCreated",
        "SquadronDemotion",
        "SquadronPromotion",
        "WonATrophyForSquadron",
    }
)

SQUADRON_EVENTS = JOIN_EVENTS | LEAVE_EVENTS | MENTION_EVENTS


@dataclass(frozen=True)
class SquadronRef:
    """A squadron identified by Frontier's numeric ID."""

    squadron_id: int
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"squadron_id": self.squadron_id, "name": self.name}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SquadronRef:
        return cls(
            squadron_id=int(data.get("squadron_id", 0)),
            name=str(data.get("name", "")),
        )

    def __str__(self) -> str:
        return f"{self.name} [#{self.squadron_id}]"


@dataclass
class SquadronEvidence:
    """One squadron-relevant journal event, retained for the audit trail."""

    event: str
    timestamp: datetime | None
    squadron_id: int
    squadron_name: str
    rank_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "squadron_id": self.squadron_id,
            "squadron_name": self.squadron_name,
            "rank_name": self.rank_name,
        }


@dataclass
class MembershipResult:
    """The verdict on whether a commander belongs to a squadron."""

    is_member: bool
    squadron: SquadronRef | None
    reason: str
    evidence: list[SquadronEvidence]
    last_join: datetime | None = None
    last_leave: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_member": self.is_member,
            "squadron": self.squadron.to_dict() if self.squadron else None,
            "reason": self.reason,
            "last_join": self.last_join.isoformat() if self.last_join else None,
            "last_leave": self.last_leave.isoformat() if self.last_leave else None,
            "evidence": [item.to_dict() for item in self.evidence],
        }


def _extract(entry: JournalEntry) -> SquadronEvidence | None:
    squadron_id = entry.get("SquadronID")
    if not isinstance(squadron_id, int):
        return None
    return SquadronEvidence(
        event=entry.event,
        timestamp=entry.timestamp,
        squadron_id=squadron_id,
        squadron_name=str(entry.get("SquadronName") or ""),
        rank_name=str(entry.get("CurrentRankName") or entry.get("NewRankName") or ""),
    )


def collect_evidence(entries: Iterable[JournalEntry]) -> list[SquadronEvidence]:
    """Extract every squadron-relevant event from ``entries``."""
    found: list[SquadronEvidence] = []
    for entry in entries:
        if entry.event not in SQUADRON_EVENTS:
            continue
        evidence = _extract(entry)
        if evidence is not None:
            found.append(evidence)
    return found


def collect_evidence_from_dir(
    directory: Path,
    stats: ReadStats | None = None,
) -> list[SquadronEvidence]:
    """Extract squadron evidence from a whole journal directory."""
    return collect_evidence(iter_journal_dir(directory, stats))


def detect_own_squadron(
    evidence: Iterable[SquadronEvidence],
) -> SquadronRef | None:
    """Return the squadron the journal owner currently belongs to.

    Used on the organizer's own journals to fill in the squadron
    restriction without them having to type an ID by hand.
    """
    result = evaluate_membership(evidence, squadron_id=None)
    return result.squadron if result.is_member else None


def _sort_key(item: SquadronEvidence) -> tuple[int, float]:
    # Entries without a timestamp sort first so that any timestamped
    # event outranks them; the fallback keeps sorting total.
    if item.timestamp is None:
        return (0, 0.0)
    return (1, item.timestamp.timestamp())


def evaluate_membership(
    evidence: Iterable[SquadronEvidence],
    squadron_id: int | None,
) -> MembershipResult:
    """Decide membership of ``squadron_id`` from ``evidence``.

    When ``squadron_id`` is ``None`` the most recently joined squadron is
    inferred instead, which is how an organizer's own squadron is found.

    The rule is chronological: take the newest join event and the newest
    departure event, and whichever is later wins. A join with no later
    departure means the commander is in. Ties favour departure, since a
    same-second join and leave is far more likely to be a leave recorded
    at login than a join.
    """
    items = sorted(evidence, key=_sort_key)

    if squadron_id is None:
        joins = [item for item in items if item.event in JOIN_EVENTS]
        if not joins:
            return MembershipResult(
                is_member=False,
                squadron=None,
                reason="No squadron join events found in these journals.",
                evidence=items,
            )
        squadron_id = joins[-1].squadron_id

    relevant = [item for item in items if item.squadron_id == squadron_id]
    if not relevant:
        return MembershipResult(
            is_member=False,
            squadron=None,
            reason=f"No events referencing squadron #{squadron_id} were found.",
            evidence=items,
        )

    name = ""
    for item in reversed(relevant):
        if item.squadron_name:
            name = item.squadron_name
            break
    squadron = SquadronRef(squadron_id=squadron_id, name=name)

    joins = [item for item in relevant if item.event in JOIN_EVENTS]
    leaves = [item for item in relevant if item.event in LEAVE_EVENTS]

    last_join = joins[-1] if joins else None
    last_leave = leaves[-1] if leaves else None

    if last_join is None:
        applied = any(item.event == "AppliedToSquadron" for item in relevant)
        reason = (
            "An application to this squadron was found, but no join was ever completed."
            if applied
            else "No join event for this squadron was found."
        )
        return MembershipResult(
            is_member=False,
            squadron=squadron,
            reason=reason,
            evidence=relevant,
            last_leave=last_leave.timestamp if last_leave else None,
        )

    if last_leave is not None:
        join_time = last_join.timestamp
        leave_time = last_leave.timestamp
        departed_after_join = (
            join_time is None or leave_time is None or leave_time >= join_time
        )
        if departed_after_join:
            verb = {
                "LeftSquadron": "left",
                "KickedFromSquadron": "was kicked from",
                "DisbandedSquadron": "saw disbanded",
            }.get(last_leave.event, "left")
            when = (
                leave_time.strftime("%Y-%m-%d %H:%M UTC")
                if leave_time
                else "an unknown time"
            )
            return MembershipResult(
                is_member=False,
                squadron=squadron,
                reason=f"Commander {verb} this squadron at {when}.",
                evidence=relevant,
                last_join=join_time,
                last_leave=leave_time,
            )

    proof = "SquadronStartup" if last_join.event == "SquadronStartup" else "join"
    return MembershipResult(
        is_member=True,
        squadron=squadron,
        reason=f"Membership confirmed by {proof} event with no later departure.",
        evidence=relevant,
        last_join=last_join.timestamp,
        last_leave=last_leave.timestamp if last_leave else None,
    )


__all__ = [
    "JOIN_EVENTS",
    "LEAVE_EVENTS",
    "MENTION_EVENTS",
    "SQUADRON_EVENTS",
    "MembershipResult",
    "SquadronEvidence",
    "SquadronRef",
    "collect_evidence",
    "collect_evidence_from_dir",
    "detect_own_squadron",
    "evaluate_membership",
]
