"""Filling a unit cap in the order the work actually happened.

A capped criterion is a race, and the thing being raced for is finite.
If a criterion is capped at 100 tonnes of tritium, the hundredth tonne
refined ends it — no matter whose submission reached the organizer
first, and no matter that somebody refined a further nine hundred
afterwards.

Scoring each submission on its own cannot express that. Two commanders
who each refined 60 tonnes would each be credited 60, totalling 120
against a cap of 100. So submissions carry the timestamp of every
scoring event, and the organizer merges them here: all contributions
from everyone, sorted by when they happened, filling the cap until it is
full.

Worked through, with a cap of 100:

===========  ==========  =======  =======  =============================
Time         Commander     Units   Filled  Credited
===========  ==========  =======  =======  =============================
10:00        A                43       43  43
11:00        B                60      100  57 — the cap fills mid-event
12:00        A                70      100  0  — nothing left to claim
===========  ==========  =======  =======  =============================

A refined more over the window and submitted first, and is still
credited 43, because B did the work that filled the cap.

The per-commander **minimum** is applied after allocation. It is a
participation floor: a commander who ends up below it scores nothing for
that criterion. Their allocated units are not redistributed — doing so
would change who reached the cap and when, and the allocation would no
longer describe what happened.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from edsg.core.criteria import Criterion


@dataclass(frozen=True)
class Contribution:
    """One scoring event, from one commander."""

    when: str
    commander_fid: str
    units: float


@dataclass
class Allocation:
    """What one commander was credited for one criterion."""

    commander_fid: str
    units: float = 0.0
    points: float = 0.0
    offered: float = 0.0
    below_minimum: bool = False

    @property
    def forfeited(self) -> float:
        """Return units that arrived too late to be credited."""
        return round(max(0.0, self.offered - self.units), 4)


@dataclass
class CriterionAllocation:
    """The outcome of filling one criterion's cap."""

    criterion_id: str
    label: str
    cap: float | None
    minimum: float | None
    allocated: dict[str, Allocation] = field(default_factory=dict)
    total_units: float = 0.0
    cap_reached: bool = False
    cap_reached_at: str = ""
    cap_reached_by: str = ""
    #: Commanders whose submission predates timestamped contributions.
    legacy: list[str] = field(default_factory=list)

    def units_for(self, commander_fid: str) -> float:
        entry = self.allocated.get(commander_fid)
        return entry.units if entry else 0.0

    def points_for(self, commander_fid: str) -> float:
        entry = self.allocated.get(commander_fid)
        return entry.points if entry else 0.0

    def to_dict(self) -> dict:
        return {
            "criterion_id": self.criterion_id,
            "label": self.label,
            "cap": self.cap,
            "minimum": self.minimum,
            "total_units": self.total_units,
            "cap_reached": self.cap_reached,
            "cap_reached_at": self.cap_reached_at,
            "cap_reached_by": self.cap_reached_by,
            "legacy_submissions": self.legacy,
            "allocated": {
                fid: {
                    "units": entry.units,
                    "points": entry.points,
                    "offered": entry.offered,
                    "forfeited": entry.forfeited,
                    "below_minimum": entry.below_minimum,
                }
                for fid, entry in self.allocated.items()
            },
        }


def allocate_criterion(
    criterion: Criterion,
    contributions_by_commander: dict[str, list[tuple[str, float]]],
) -> CriterionAllocation:
    """Fill one criterion's cap chronologically across every commander.

    ``contributions_by_commander`` maps a Frontier ID to that
    commander's ``(timestamp, units)`` list, oldest first.
    """
    result = CriterionAllocation(
        criterion_id=criterion.criterion_id,
        label=criterion.label,
        cap=criterion.unit_cap,
        minimum=criterion.minimum_units,
    )

    merged: list[Contribution] = []
    for fid, entries in contributions_by_commander.items():
        result.allocated.setdefault(fid, Allocation(commander_fid=fid))
        for when, units in entries:
            if units <= 0:
                continue
            merged.append(Contribution(when=when, commander_fid=fid, units=units))
            result.allocated[fid].offered += units

    # Sorted by time, then by commander so a tie resolves the same way on
    # every machine that regenerates the report.
    merged.sort(key=lambda item: (item.when, item.commander_fid))

    cap = criterion.unit_cap
    running = 0.0
    for item in merged:
        if cap is not None and running >= cap:
            break
        share = item.units
        if cap is not None:
            share = min(share, cap - running)
        if share <= 0:
            continue
        entry = result.allocated[item.commander_fid]
        entry.units = round(entry.units + share, 4)
        running = round(running + share, 4)
        if cap is not None and running >= cap and not result.cap_reached:
            result.cap_reached = True
            result.cap_reached_at = item.when
            result.cap_reached_by = item.commander_fid

    result.total_units = round(running, 4)

    minimum = criterion.minimum_units
    for entry in result.allocated.values():
        entry.offered = round(entry.offered, 4)
        if minimum is not None and entry.units < minimum:
            entry.below_minimum = True
            entry.points = 0.0
            continue
        entry.points = round(entry.units * criterion.points_per_unit, 4)

    return result


def allocate_all(
    criteria: list[Criterion],
    contributions: dict[str, dict[str, list[tuple[str, float]]]],
    legacy_fids: dict[str, list[str]] | None = None,
) -> dict[str, CriterionAllocation]:
    """Allocate every criterion, keyed by criterion ID.

    ``contributions`` maps criterion ID to commander ID to that
    commander's contribution list.
    """
    legacy_fids = legacy_fids or {}
    allocations: dict[str, CriterionAllocation] = {}
    for criterion in criteria:
        allocation = allocate_criterion(
            criterion, contributions.get(criterion.criterion_id, {})
        )
        allocation.legacy = legacy_fids.get(criterion.criterion_id, [])
        allocations[criterion.criterion_id] = allocation
    return allocations


__all__ = [
    "Allocation",
    "Contribution",
    "CriterionAllocation",
    "allocate_all",
    "allocate_criterion",
]
