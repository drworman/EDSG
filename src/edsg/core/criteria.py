"""The criteria model: what an organizer measures and how it scores.

A criterion pairs a *metric* (what to count) with *filters* (which events
count) and a *scoring rule* (what those units are worth). Keeping the
three separate means a small set of metrics covers a very large space of
events: "tritium mined", "tritium sold to our carrier" and "anything sold
at Jameson Memorial" are all the same two metrics with different filters.

The catch-all :attr:`MetricKind.EVENT_COUNT` satisfies the requirement to
score on any journal event whatsoever, including event types Frontier has
not shipped yet, by counting raw event names.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from edsg.core.errors import CriteriaError
from edsg.core.numbers import quantity


class MetricKind(StrEnum):
    """What a criterion counts."""

    EVENT_COUNT = "event_count"
    MINING_REFINED = "mining_refined"
    MARKET_SELL = "market_sell"
    MARKET_BUY = "market_buy"
    EXOBIO_SCANNED = "exobio_scanned"
    EXOBIO_SOLD = "exobio_sold"
    BODIES_SCANNED = "bodies_scanned"
    BODIES_MAPPED = "bodies_mapped"
    SYSTEMS_VISITED = "systems_visited"
    EXPLORATION_SOLD = "exploration_sold"
    MISSIONS = "missions"
    BOUNTIES = "bounties"
    COMBAT_BONDS = "combat_bonds"
    POWERPLAY_MERITS = "powerplay_merits"
    COLONISATION_CONTRIBUTION = "colonisation_contribution"
    COLONISATION_COMPLETION = "colonisation_completion"

    @property
    def label(self) -> str:
        return METRIC_LABELS[self]

    @property
    def description(self) -> str:
        return METRIC_DESCRIPTIONS[self]


METRIC_LABELS: dict[MetricKind, str] = {
    MetricKind.EVENT_COUNT: "Raw journal events",
    MetricKind.MINING_REFINED: "Ore refined (mining)",
    MetricKind.MARKET_SELL: "Commodities sold",
    MetricKind.MARKET_BUY: "Commodities bought",
    MetricKind.EXOBIO_SCANNED: "Exobiology samples analysed",
    MetricKind.EXOBIO_SOLD: "Exobiology data sold",
    MetricKind.BODIES_SCANNED: "Bodies scanned",
    MetricKind.BODIES_MAPPED: "Bodies surface-mapped",
    MetricKind.SYSTEMS_VISITED: "Systems visited",
    MetricKind.EXPLORATION_SOLD: "Exploration data sold",
    MetricKind.MISSIONS: "Missions",
    MetricKind.BOUNTIES: "Bounty vouchers",
    MetricKind.COMBAT_BONDS: "Combat bonds",
    MetricKind.POWERPLAY_MERITS: "Powerplay merits",
    MetricKind.COLONISATION_CONTRIBUTION: "Colonisation cargo delivered",
    MetricKind.COLONISATION_COMPLETION: "Colonisation builds completed",
}

METRIC_DESCRIPTIONS: dict[MetricKind, str] = {
    MetricKind.EVENT_COUNT: (
        "Counts any journal event by name. Use this for anything the "
        "purpose-built metrics do not cover, including new event types."
    ),
    MetricKind.MINING_REFINED: (
        "Each MiningRefined event is one tonne delivered to the cargo "
        "hold by the refinery. Filter by commodity to score a single ore."
    ),
    MetricKind.MARKET_SELL: (
        "Commodity sales. Filter by commodity and by destination system, "
        "station, station type or market ID to target a specific buyer."
    ),
    MetricKind.MARKET_BUY: "Commodity purchases, filterable like sales.",
    MetricKind.EXOBIO_SCANNED: (
        "Completed biological samples. Only the third and final "
        "'Analyse' scan of an organism counts, so partial samples do not "
        "inflate a score."
    ),
    MetricKind.EXOBIO_SOLD: (
        "Biological data sold at Vista Genomics, by sample count or value."
    ),
    MetricKind.BODIES_SCANNED: (
        "Bodies scanned. Restrict to first discoveries to reward genuine "
        "exploration rather than re-scanning known space."
    ),
    MetricKind.BODIES_MAPPED: (
        "Bodies mapped with surface probes. Restrict to first mappings "
        "to exclude already-mapped bodies."
    ),
    MetricKind.SYSTEMS_VISITED: "Distinct star systems entered by hyperspace jump.",
    MetricKind.EXPLORATION_SOLD: (
        "Cartographic data sold, by system count or credit value."
    ),
    MetricKind.MISSIONS: (
        "Missions by outcome. Filter by outcome, mission name, faction or destination."
    ),
    MetricKind.BOUNTIES: "Bounty vouchers claimed, by count or credit value.",
    MetricKind.COMBAT_BONDS: "Combat bonds awarded, by count or credit value.",
    MetricKind.POWERPLAY_MERITS: "Merits earned for a pledged power.",
    MetricKind.COLONISATION_CONTRIBUTION: (
        "Commodities delivered to a colonisation construction site. Each "
        "delivery records exactly what the commander handed over, so this "
        "measures their own contribution rather than the site's total. "
        "Filter by commodity, or by market ID to target one build."
    ),
    MetricKind.COLONISATION_COMPLETION: (
        "Construction sites that reached completion and which the "
        "commander actually delivered to. Docking at somebody else's "
        "finished build does not count. Use it to reward seeing a "
        "construction through rather than dropping one load and leaving."
    ),
}


class Measure(StrEnum):
    """How the counted things are converted into units."""

    COUNT = "count"
    TONNAGE = "tonnage"
    CREDITS = "credits"
    DISTINCT = "distinct"

    @property
    def label(self) -> str:
        return {
            Measure.COUNT: "Number of events",
            Measure.TONNAGE: "Tonnes",
            Measure.CREDITS: "Credits",
            Measure.DISTINCT: "Distinct items",
        }[self]


class MissionOutcome(StrEnum):
    """Terminal states a mission can reach."""

    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"
    ACCEPTED = "accepted"


#: Which measures make sense for each metric. Enforced at validation time
#: so an organizer cannot build a criterion that can only ever score zero.
ALLOWED_MEASURES: dict[MetricKind, tuple[Measure, ...]] = {
    MetricKind.EVENT_COUNT: (Measure.COUNT,),
    MetricKind.MINING_REFINED: (Measure.TONNAGE, Measure.DISTINCT),
    MetricKind.MARKET_SELL: (Measure.TONNAGE, Measure.CREDITS, Measure.COUNT),
    MetricKind.MARKET_BUY: (Measure.TONNAGE, Measure.CREDITS, Measure.COUNT),
    MetricKind.EXOBIO_SCANNED: (Measure.COUNT, Measure.DISTINCT),
    MetricKind.EXOBIO_SOLD: (Measure.COUNT, Measure.CREDITS),
    MetricKind.BODIES_SCANNED: (Measure.DISTINCT, Measure.COUNT),
    MetricKind.BODIES_MAPPED: (Measure.DISTINCT, Measure.COUNT),
    MetricKind.SYSTEMS_VISITED: (Measure.DISTINCT, Measure.COUNT),
    MetricKind.EXPLORATION_SOLD: (Measure.CREDITS, Measure.COUNT, Measure.DISTINCT),
    MetricKind.MISSIONS: (Measure.COUNT, Measure.CREDITS),
    MetricKind.BOUNTIES: (Measure.COUNT, Measure.CREDITS),
    MetricKind.COMBAT_BONDS: (Measure.COUNT, Measure.CREDITS),
    MetricKind.POWERPLAY_MERITS: (Measure.COUNT,),
    MetricKind.COLONISATION_CONTRIBUTION: (
        Measure.TONNAGE,
        Measure.COUNT,
        Measure.DISTINCT,
    ),
    # Only DISTINCT is offered: the depot event is a status snapshot that
    # repeats on every visit, so counting events would reward re-docking.
    MetricKind.COLONISATION_COMPLETION: (Measure.DISTINCT,),
}

DEFAULT_MEASURE: dict[MetricKind, Measure] = {
    kind: measures[0] for kind, measures in ALLOWED_MEASURES.items()
}


#: Which filter groups each metric exposes. Lives here rather than in
#: the dialog so the documentation generator can read it without Qt.
FILTER_GROUPS: dict[MetricKind, set[str]] = {
    MetricKind.EVENT_COUNT: {"events", "location"},
    MetricKind.MINING_REFINED: {"commodities", "location"},
    MetricKind.MARKET_SELL: {"commodities", "location", "market"},
    MetricKind.MARKET_BUY: {"commodities", "location", "market"},
    MetricKind.EXOBIO_SCANNED: {"bio", "location"},
    MetricKind.EXOBIO_SOLD: {"bio", "location", "market"},
    MetricKind.BODIES_SCANNED: {"systems", "discovery"},
    MetricKind.BODIES_MAPPED: {"systems", "mapping"},
    MetricKind.SYSTEMS_VISITED: {"systems"},
    MetricKind.EXPLORATION_SOLD: {"systems", "location", "market"},
    MetricKind.MISSIONS: {"missions", "factions", "location"},
    MetricKind.BOUNTIES: {"factions", "location"},
    MetricKind.COMBAT_BONDS: {"factions", "location"},
    MetricKind.POWERPLAY_MERITS: {"powers", "location"},
    MetricKind.COLONISATION_CONTRIBUTION: {"commodities", "location", "market"},
    MetricKind.COLONISATION_COMPLETION: {"location", "market"},
}


def _clean_list(values: Any) -> list[str]:
    """Coerce input into a list of non-empty stripped strings."""
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    cleaned: list[str] = []
    for value in values:
        text = str(value).strip()
        if text:
            cleaned.append(text)
    return cleaned


def _clean_int_list(values: Any) -> list[int]:
    if values is None:
        return []
    if isinstance(values, (str, int)):
        values = [values]
    cleaned: list[int] = []
    for value in values:
        try:
            cleaned.append(int(str(value).strip()))
        except (TypeError, ValueError):
            continue
    return cleaned


def normalise_name(value: str) -> str:
    """Normalise a game name for tolerant comparison.

    Frontier's internal names appear as ``$tritium_name;`` while the
    localised form is ``Tritium``. Organizers type the latter. Stripping
    the decoration and case-folding lets one filter match both.
    """
    text = value.strip().lower()
    if text.startswith("$"):
        text = text[1:]
    if text.endswith(";"):
        text = text[:-1]
    for suffix in ("_name", "_localised"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return re.sub(r"[^a-z0-9]+", "", text)


@dataclass
class Filters:
    """Restrictions narrowing which events a metric counts.

    Empty lists mean "no restriction". Within one field the values are
    OR-ed; across fields they are AND-ed. So systems ``[A, B]`` with
    commodities ``[Tritium]`` means "tritium, in A or B".
    """

    systems: list[str] = field(default_factory=list)
    stations: list[str] = field(default_factory=list)
    station_types: list[str] = field(default_factory=list)
    market_ids: list[int] = field(default_factory=list)
    commodities: list[str] = field(default_factory=list)
    event_names: list[str] = field(default_factory=list)
    mission_names: list[str] = field(default_factory=list)
    mission_outcomes: list[str] = field(default_factory=list)
    factions: list[str] = field(default_factory=list)
    genera: list[str] = field(default_factory=list)
    species: list[str] = field(default_factory=list)
    powers: list[str] = field(default_factory=list)
    first_discovery_only: bool = False
    first_mapped_only: bool = False

    def is_empty(self) -> bool:
        return not any(
            [
                self.systems,
                self.stations,
                self.station_types,
                self.market_ids,
                self.commodities,
                self.event_names,
                self.mission_names,
                self.mission_outcomes,
                self.factions,
                self.genera,
                self.species,
                self.powers,
                self.first_discovery_only,
                self.first_mapped_only,
            ]
        )

    def describe(self) -> list[str]:
        """Return human-readable one-line summaries of each restriction."""
        parts: list[str] = []
        if self.systems:
            parts.append(f"systems: {', '.join(self.systems)}")
        if self.stations:
            parts.append(f"stations: {', '.join(self.stations)}")
        if self.station_types:
            parts.append(f"station types: {', '.join(self.station_types)}")
        if self.market_ids:
            parts.append(f"market IDs: {', '.join(str(m) for m in self.market_ids)}")
        if self.commodities:
            parts.append(f"commodities: {', '.join(self.commodities)}")
        if self.event_names:
            parts.append(f"events: {', '.join(self.event_names)}")
        if self.mission_names:
            parts.append(f"mission name contains: {', '.join(self.mission_names)}")
        if self.mission_outcomes:
            parts.append(f"outcomes: {', '.join(self.mission_outcomes)}")
        if self.factions:
            parts.append(f"factions: {', '.join(self.factions)}")
        if self.genera:
            parts.append(f"genera: {', '.join(self.genera)}")
        if self.species:
            parts.append(f"species: {', '.join(self.species)}")
        if self.powers:
            parts.append(f"powers: {', '.join(self.powers)}")
        if self.first_discovery_only:
            parts.append("first discoveries only")
        if self.first_mapped_only:
            parts.append("first mappings only")
        return parts

    def to_dict(self) -> dict[str, Any]:
        return {
            "systems": self.systems,
            "stations": self.stations,
            "station_types": self.station_types,
            "market_ids": self.market_ids,
            "commodities": self.commodities,
            "event_names": self.event_names,
            "mission_names": self.mission_names,
            "mission_outcomes": self.mission_outcomes,
            "factions": self.factions,
            "genera": self.genera,
            "species": self.species,
            "powers": self.powers,
            "first_discovery_only": self.first_discovery_only,
            "first_mapped_only": self.first_mapped_only,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Filters:
        data = data or {}
        return cls(
            systems=_clean_list(data.get("systems")),
            stations=_clean_list(data.get("stations")),
            station_types=_clean_list(data.get("station_types")),
            market_ids=_clean_int_list(data.get("market_ids")),
            commodities=_clean_list(data.get("commodities")),
            event_names=_clean_list(data.get("event_names")),
            mission_names=_clean_list(data.get("mission_names")),
            mission_outcomes=_clean_list(data.get("mission_outcomes")),
            factions=_clean_list(data.get("factions")),
            genera=_clean_list(data.get("genera")),
            species=_clean_list(data.get("species")),
            powers=_clean_list(data.get("powers")),
            first_discovery_only=bool(data.get("first_discovery_only", False)),
            first_mapped_only=bool(data.get("first_mapped_only", False)),
        )


@dataclass
class Criterion:
    """One scored rule within an event."""

    label: str
    kind: MetricKind
    measure: Measure
    filters: Filters = field(default_factory=Filters)
    points_per_unit: float = 1.0
    #: Required. The cap is what makes a criterion a finite race: it is
    #: filled chronologically across every participant, so it also bounds
    #: how much of a commander's journal has to travel in a submission.
    unit_cap: float | None = None
    #: Optional participation floor. A commander allocated fewer units
    #: than this scores nothing for the criterion.
    minimum_units: float | None = None
    criterion_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    notes: str = ""

    def score(self, units: float) -> tuple[float, float]:
        """Return ``(counted_units, points)`` for a raw unit total.

        A minimum acts as a qualifying threshold: below it the criterion
        contributes nothing at all. A cap limits how many units can be
        converted to points, which stops one runaway category deciding a
        whole event.
        """
        if self.minimum_units is not None and units < self.minimum_units:
            return 0.0, 0.0
        counted = units
        if self.unit_cap is not None:
            counted = min(counted, self.unit_cap)
        return counted, counted * self.points_per_unit

    def describe(self) -> str:
        """Return a one-line human summary of the rule."""
        base = f"{self.kind.label} measured in {self.measure.label.lower()}"
        detail = "; ".join(self.filters.describe())
        if detail:
            base = f"{base} ({detail})"
        scoring = f"{quantity(self.points_per_unit)} pt/unit"
        if self.unit_cap is not None:
            scoring += f", unit cap {quantity(self.unit_cap)}"
        if self.minimum_units is not None:
            scoring += f", {quantity(self.minimum_units)} minimum per CMDR"
        return f"{base} — {scoring}"

    def validate(self) -> list[str]:
        """Return a list of problems, empty when the criterion is sound."""
        problems: list[str] = []
        if not self.label.strip():
            problems.append("Criterion needs a label.")
        allowed = ALLOWED_MEASURES[self.kind]
        if self.measure not in allowed:
            names = ", ".join(m.value for m in allowed)
            problems.append(
                f"{self.label or self.kind.value}: measure "
                f"'{self.measure.value}' is not valid for "
                f"{self.kind.label}. Choose one of: {names}."
            )
        if self.kind is MetricKind.EVENT_COUNT and not self.filters.event_names:
            problems.append(
                f"{self.label or 'Raw journal events'}: name at least one "
                f"journal event to count."
            )
        if self.points_per_unit == 0:
            problems.append(f"{self.label}: points per unit is zero.")
        if self.unit_cap is None:
            problems.append(
                f"{self.label or 'This criterion'}: set a unit cap. The cap "
                f"is what the event is racing for, and it decides how much "
                f"of each commander's journal has to be submitted."
            )
        elif self.unit_cap <= 0:
            problems.append(f"{self.label}: unit cap must be above zero.")
        if self.minimum_units is not None and self.minimum_units < 0:
            problems.append(f"{self.label}: minimum units cannot be negative.")
        if (
            self.unit_cap is not None
            and self.minimum_units is not None
            and self.minimum_units > self.unit_cap
        ):
            problems.append(
                f"{self.label}: minimum ({quantity(self.minimum_units)}) exceeds the "
                f"cap ({quantity(self.unit_cap)}), so it can never score."
            )
        for outcome in self.filters.mission_outcomes:
            valid = {item.value for item in MissionOutcome}
            if outcome.lower() not in valid:
                problems.append(
                    f"{self.label}: '{outcome}' is not a mission outcome. "
                    f"Use one of: {', '.join(sorted(valid))}."
                )
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "label": self.label,
            "kind": self.kind.value,
            "measure": self.measure.value,
            "filters": self.filters.to_dict(),
            "points_per_unit": self.points_per_unit,
            "unit_cap": self.unit_cap,
            "minimum_units": self.minimum_units,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Criterion:
        try:
            kind = MetricKind(data["kind"])
        except (KeyError, ValueError) as exc:
            raise CriteriaError(
                f"Unknown or missing metric kind: {data.get('kind')!r}. "
                f"This invitation may come from a newer version of EDSG."
            ) from exc
        try:
            measure = Measure(data.get("measure", DEFAULT_MEASURE[kind].value))
        except ValueError as exc:
            raise CriteriaError(f"Unknown measure: {data.get('measure')!r}.") from exc

        cap = data.get("unit_cap")
        minimum = data.get("minimum_units")
        return cls(
            criterion_id=str(data.get("criterion_id") or uuid.uuid4().hex[:12]),
            label=str(data.get("label", "")),
            kind=kind,
            measure=measure,
            filters=Filters.from_dict(data.get("filters")),
            points_per_unit=float(data.get("points_per_unit", 1.0)),
            unit_cap=float(cap) if cap is not None else None,
            minimum_units=float(minimum) if minimum is not None else None,
            notes=str(data.get("notes", "")),
        )


__all__ = [
    "ALLOWED_MEASURES",
    "DEFAULT_MEASURE",
    "FILTER_GROUPS",
    "METRIC_DESCRIPTIONS",
    "METRIC_LABELS",
    "Criterion",
    "Filters",
    "Measure",
    "MetricKind",
    "MissionOutcome",
    "normalise_name",
]
