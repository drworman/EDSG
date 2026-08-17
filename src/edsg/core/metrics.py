"""Turning journal events into scored units.

The evaluator makes a single pass over a commander's journals, offering
each event to every criterion in turn. One pass matters: the sample data
used to build EDSG contains over a quarter of a million events for two
commanders across three months, and an organizer may define a dozen
criteria.

Each criterion owns an :class:`Accumulator` holding its running totals,
a per-key breakdown for the report, and a handful of example events kept
as an audit trail.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from edsg.core.commodities import matches as commodity_matches
from edsg.core.criteria import (
    Criterion,
    Filters,
    Measure,
    MetricKind,
    normalise_name,
)
from edsg.core.journal import JournalEntry, ReadStats, iter_journal_dir
from edsg.core.location import LocationTracker, MarketDirectory, MarketRecord
from edsg.core.models import CriterionResult, EventWindow

#: How many example events to retain per criterion for the audit trail.
MAX_SAMPLES = 12

#: How many breakdown keys to carry into the submission.
MAX_BREAKDOWN_KEYS = 40

#: Journal events consulted by each metric kind.
METRIC_EVENTS: dict[MetricKind, frozenset[str]] = {
    MetricKind.EVENT_COUNT: frozenset(),  # populated from the filter
    MetricKind.MINING_REFINED: frozenset({"MiningRefined"}),
    MetricKind.MARKET_SELL: frozenset({"MarketSell"}),
    MetricKind.MARKET_BUY: frozenset({"MarketBuy"}),
    MetricKind.EXOBIO_SCANNED: frozenset({"ScanOrganic"}),
    MetricKind.EXOBIO_SOLD: frozenset({"SellOrganicData"}),
    MetricKind.BODIES_SCANNED: frozenset({"Scan"}),
    MetricKind.BODIES_MAPPED: frozenset({"SAAScanComplete"}),
    MetricKind.SYSTEMS_VISITED: frozenset({"FSDJump", "CarrierJump"}),
    MetricKind.EXPLORATION_SOLD: frozenset(
        {"SellExplorationData", "MultiSellExplorationData"}
    ),
    MetricKind.MISSIONS: frozenset(
        {
            "MissionAccepted",
            "MissionCompleted",
            "MissionFailed",
            "MissionAbandoned",
        }
    ),
    MetricKind.BOUNTIES: frozenset({"Bounty"}),
    MetricKind.COMBAT_BONDS: frozenset({"FactionKillBond"}),
    MetricKind.POWERPLAY_MERITS: frozenset({"PowerplayMerits"}),
    MetricKind.COLONISATION_CONTRIBUTION: frozenset({"ColonisationContribution"}),
    MetricKind.COLONISATION_COMPLETION: frozenset({"ColonisationConstructionDepot"}),
}

#: Mission outcome names mapped to the journal event that reports them.
MISSION_EVENT_BY_OUTCOME = {
    "accepted": "MissionAccepted",
    "completed": "MissionCompleted",
    "failed": "MissionFailed",
    "abandoned": "MissionAbandoned",
}


def _prettify(raw: str) -> str:
    """Turn an internal commodity name into something readable."""
    text = raw.strip()
    if text.startswith("$"):
        text = text[1:]
    if text.endswith(";"):
        text = text[:-1]
    if text.lower().endswith("_name"):
        text = text[: -len("_name")]
    text = text.replace("_", " ").strip()
    return text.title() if text.islower() else text


def _matches_commodity(value: str, patterns: Iterable[str]) -> bool:
    """Match a commodity name however it happens to be spelled.

    Commodities need more than case folding: the internal name is
    singular and unabbreviated while the localised name is often neither,
    so ``$lowtemperaturediamond_name;`` and "Low Temp. Diamonds" do not
    reconcile on their own, and an organizer typing the full name matches
    neither. See :mod:`edsg.core.commodities`.
    """
    return any(commodity_matches(value, pattern) for pattern in patterns)


def _matches_commodity_field(
    entry: JournalEntry, key: str, patterns: Iterable[str]
) -> bool:
    """Match a commodity filter against every spelling in the entry."""
    patterns = list(patterns)
    return any(
        _matches_commodity(value, patterns) for value in entry.name_variants(key)
    )


def _matches_field(entry: JournalEntry, key: str, patterns: Iterable[str]) -> bool:
    """Match ``patterns`` against every spelling of a journal field.

    Checks both the internal name and the localised name, so a filter
    written either way behaves identically.
    """
    patterns = list(patterns)
    return any(_matches_any(value, patterns) for value in entry.name_variants(key))


def _matches_any(value: str, patterns: Iterable[str]) -> bool:
    """Return whether ``value`` matches any pattern, tolerantly.

    Comparison is case-insensitive and ignores Frontier's ``$name;``
    decoration, so an organizer typing "Tritium" matches the journal's
    ``$tritium_name;``. Substring matching is deliberate: mission names
    like ``Mission_MassacreWing_name`` are matched by typing "massacre".
    """
    target = normalise_name(value)
    if not target:
        return False
    for pattern in patterns:
        needle = normalise_name(pattern)
        if needle and needle in target:
            return True
    return False


@dataclass
class Accumulator:
    """Running totals for one criterion."""

    criterion: Criterion
    units: float = 0.0
    events_seen: int = 0
    distinct_keys: set[str] = field(default_factory=set)
    # Values are floats: tonnage and credits are not whole numbers, so a
    # Counter (whose values are typed as int) is the wrong container even
    # though it behaves correctly at runtime.
    breakdown: dict[str, float] = field(default_factory=dict)
    samples: list[str] = field(default_factory=list)
    #: Every scoring event as ``(timestamp, units)``, in the order it
    #: happened. The organizer merges these across all participants at
    #: closing time and fills the unit cap chronologically, so whoever
    #: did the work first is credited first, not whoever submitted
    #: first. Truncated once this criterion's own cap is covered.
    contributions: list[tuple[str, float]] = field(default_factory=list)
    contributed: float = 0.0
    #: Set by the evaluator before each event is offered, so handlers do
    #: not each have to thread a timestamp through their own call.
    current_stamp: str = ""

    def add(
        self,
        amount: float,
        key: str = "",
        distinct_key: str | None = None,
        sample: str = "",
    ) -> None:
        """Record one matched event."""
        self.events_seen += 1
        if self.criterion.measure is Measure.DISTINCT:
            token = distinct_key if distinct_key is not None else key
            if token:
                if token in self.distinct_keys:
                    return
                self.distinct_keys.add(token)
            scored = 1.0
        else:
            scored = amount
        self.units += scored
        self._record(scored)
        if key:
            self.breakdown[key] = self.breakdown.get(key, 0.0) + (
                amount if amount else 1.0
            )
        if sample and len(self.samples) < MAX_SAMPLES:
            self.samples.append(sample)

    def _record(self, scored: float) -> None:
        """Log one contribution, up to this criterion's cap.

        Only the earliest events covering the cap can ever score, however
        the field turns out: even a commander who led the whole way
        cannot claim more than the cap. Recording past that point would
        bloat every submission to no purpose.
        """
        if not self.current_stamp or not scored:
            return
        cap = self.criterion.unit_cap
        if cap is not None and self.contributed >= cap:
            return
        self.contributions.append((self.current_stamp, round(scored, 4)))
        self.contributed += scored

    def result(self) -> CriterionResult:
        counted, points = self.criterion.score(self.units)
        ranked = sorted(self.breakdown.items(), key=lambda item: item[1], reverse=True)
        top = ranked[:MAX_BREAKDOWN_KEYS]
        return CriterionResult(
            criterion_id=self.criterion.criterion_id,
            label=self.criterion.label,
            contributions=list(self.contributions),
            raw_units=round(self.units, 4),
            counted_units=round(counted, 4),
            points=round(points, 4),
            detail={
                "measure": self.criterion.measure.value,
                "kind": self.criterion.kind.value,
                "events_matched": self.events_seen,
                "breakdown": {key: round(value, 4) for key, value in top},
                "breakdown_truncated": len(self.breakdown) > MAX_BREAKDOWN_KEYS,
            },
            samples=list(self.samples),
        )


class MetricEvaluator:
    """Scores one commander's journals against a set of criteria."""

    def __init__(
        self,
        criteria: Iterable[Criterion],
        window: EventWindow,
        markets: MarketDirectory | None = None,
    ) -> None:
        self.window = window
        self.markets = markets or MarketDirectory()
        self.tracker = LocationTracker()
        self.accumulators = [Accumulator(criterion) for criterion in criteria]

        # SAAScanComplete does not say whether a body was already mapped
        # by someone else, but the Scan event for the same body does.
        # Recorded here so first-mapping filters have something to consult.
        self._mapped_before: dict[tuple[Any, Any], bool] = {}

        # Construction sites this commander has delivered to. A depot's
        # completion only counts for someone who actually supplied it,
        # so this is recorded across the whole journal, not just the
        # scoring window.
        self._colonisation_supplied: set[int] = set()

        # Index accumulators by the events they care about so the hot loop
        # skips the overwhelming majority of entries with one dict lookup.
        self._by_event: dict[str, list[Accumulator]] = {}
        for accumulator in self.accumulators:
            for event_name in self._events_for(accumulator.criterion):
                self._by_event.setdefault(event_name, []).append(accumulator)

    @staticmethod
    def _events_for(criterion: Criterion) -> frozenset[str]:
        if criterion.kind is MetricKind.EVENT_COUNT:
            return frozenset(criterion.filters.event_names)
        if criterion.kind is MetricKind.MISSIONS:
            outcomes = criterion.filters.mission_outcomes
            if outcomes:
                names = {
                    MISSION_EVENT_BY_OUTCOME[outcome.lower()]
                    for outcome in outcomes
                    if outcome.lower() in MISSION_EVENT_BY_OUTCOME
                }
                if names:
                    return frozenset(names)
            # No outcome named: default to completions, which is what an
            # organizer almost always means by "missions".
            return frozenset({"MissionCompleted"})
        return METRIC_EVENTS[criterion.kind]

    # -- location helpers ---------------------------------------------

    def _market_for(self, entry: JournalEntry) -> MarketRecord | None:
        market_id = entry.get("MarketID")
        if not isinstance(market_id, int):
            return None
        record = self.markets.records.get(market_id)
        if record is not None:
            return record
        return self.tracker.market(market_id)

    def _location_names(self, entry: JournalEntry) -> tuple[str, str, str, int | None]:
        """Return ``(system, station, station_type, market_id)`` for an event.

        Market-bearing events resolve through the market directory, so a
        sale is attributed to the station that bought the goods even when
        the commander has since moved on. Everything else uses the
        commander's position at that point in the replay.
        """
        record = self._market_for(entry)
        if record is not None:
            system = record.star_system or self.tracker.state.star_system
            return system, record.station_name, record.station_type, record.market_id
        state = self.tracker.state
        return (
            state.star_system,
            state.station_name,
            state.station_type,
            state.market_id,
        )

    def _passes_location(self, entry: JournalEntry, filters: Filters) -> bool:
        if not (
            filters.systems
            or filters.stations
            or filters.station_types
            or filters.market_ids
        ):
            return True
        system, station, station_type, market_id = self._location_names(entry)
        if filters.systems and not _matches_any(system, filters.systems):
            return False
        if filters.stations and not _matches_any(station, filters.stations):
            return False
        if filters.station_types and not _matches_any(
            station_type, filters.station_types
        ):
            return False
        return not (filters.market_ids and market_id not in filters.market_ids)

    # -- main loop -----------------------------------------------------

    def feed(self, entry: JournalEntry) -> None:
        """Offer one journal entry to every interested criterion."""
        self.tracker.observe(entry)
        if entry.event == "ColonisationContribution":
            market_id = entry.get("MarketID")
            if isinstance(market_id, int):
                self._colonisation_supplied.add(market_id)

        if entry.event == "Scan":
            # Recorded outside the window check: a body scanned before the
            # event began still tells us whether it was already mapped.
            was_mapped = entry.get("WasMapped")
            if isinstance(was_mapped, bool):
                key = (entry.get("SystemAddress"), entry.get("BodyID"))
                self._mapped_before[key] = was_mapped

        candidates = self._by_event.get(entry.event)
        if not candidates:
            return
        if not self.window.contains(entry.timestamp):
            return
        for accumulator in candidates:
            self._apply(accumulator, entry)

    def _apply(self, accumulator: Accumulator, entry: JournalEntry) -> None:
        handler = _HANDLERS.get(accumulator.criterion.kind)
        if handler is None:
            return
        # Recorded here rather than in each of the fourteen handlers, so
        # a new metric cannot forget to timestamp its contributions.
        accumulator.current_stamp = (
            entry.timestamp.isoformat() if entry.timestamp else ""
        )
        handler(self, accumulator, entry)

    def results(self) -> list[CriterionResult]:
        """Return the scored result for every criterion, in order."""
        return [accumulator.result() for accumulator in self.accumulators]

    # -- per-metric handlers -------------------------------------------

    def _handle_event_count(
        self, accumulator: Accumulator, entry: JournalEntry
    ) -> None:
        filters = accumulator.criterion.filters
        if not self._passes_location(entry, filters):
            return
        stamp = entry.timestamp.isoformat() if entry.timestamp else "?"
        accumulator.add(1.0, key=entry.event, sample=f"{stamp} {entry.event}")

    def _handle_mining(self, accumulator: Accumulator, entry: JournalEntry) -> None:
        filters = accumulator.criterion.filters
        commodity = entry.display_name("Type")
        if filters.commodities and not _matches_commodity_field(
            entry, "Type", filters.commodities
        ):
            return
        if not self._passes_location(entry, filters):
            return
        stamp = entry.timestamp.isoformat() if entry.timestamp else "?"
        system = self.tracker.state.star_system or "unknown system"
        # Each MiningRefined event represents exactly one tonne leaving
        # the refinery for the cargo hold.
        accumulator.add(
            1.0,
            key=commodity or "unknown",
            distinct_key=normalise_name(commodity),
            sample=f"{stamp} refined 1 t {commodity} in {system}",
        )

    def _handle_market(self, accumulator: Accumulator, entry: JournalEntry) -> None:
        criterion = accumulator.criterion
        filters = criterion.filters
        commodity = entry.display_name("Type")
        if filters.commodities and not _matches_commodity_field(
            entry, "Type", filters.commodities
        ):
            return
        if not self._passes_location(entry, filters):
            return

        count = entry.get("Count") or 0
        if criterion.measure is Measure.TONNAGE:
            amount = float(count)
        elif criterion.measure is Measure.CREDITS:
            amount = float(entry.get("TotalSale") or entry.get("TotalCost") or 0)
        else:
            amount = 1.0

        _, station, _, market_id = self._location_names(entry)
        where = station or self.tracker.describe_market(market_id)
        stamp = entry.timestamp.isoformat() if entry.timestamp else "?"
        verb = "sold" if entry.event == "MarketSell" else "bought"
        accumulator.add(
            amount,
            key=commodity or "unknown",
            distinct_key=normalise_name(commodity),
            sample=f"{stamp} {verb} {count} t {commodity} at {where}",
        )

    def _handle_exobio_scanned(
        self, accumulator: Accumulator, entry: JournalEntry
    ) -> None:
        # Only the final Analyse scan completes a sample. Counting Log or
        # Sample scans would treble every score.
        if entry.get("ScanType") != "Analyse":
            return
        filters = accumulator.criterion.filters
        genus = entry.display_name("Genus")
        species = entry.display_name("Species")
        if filters.genera and not _matches_field(entry, "Genus", filters.genera):
            return
        if filters.species and not _matches_field(entry, "Species", filters.species):
            return
        if not self._passes_location(entry, filters):
            return
        stamp = entry.timestamp.isoformat() if entry.timestamp else "?"
        system = self.tracker.state.star_system or "unknown system"
        accumulator.add(
            1.0,
            key=species or genus or "unknown",
            distinct_key=normalise_name(species or genus),
            sample=f"{stamp} analysed {species or genus} in {system}",
        )

    def _handle_exobio_sold(
        self, accumulator: Accumulator, entry: JournalEntry
    ) -> None:
        criterion = accumulator.criterion
        filters = criterion.filters
        if not self._passes_location(entry, filters):
            return
        bio_data = entry.get("BioData") or []
        if not isinstance(bio_data, list):
            return
        stamp = entry.timestamp.isoformat() if entry.timestamp else "?"
        for item in bio_data:
            if not isinstance(item, dict):
                continue
            species = item.get("Species_Localised") or item.get("Species") or ""
            genus = item.get("Genus_Localised") or item.get("Genus") or ""
            if filters.genera and not _matches_any(genus, filters.genera):
                continue
            if filters.species and not _matches_any(species, filters.species):
                continue
            value = float(item.get("Value") or 0) + float(item.get("Bonus") or 0)
            amount = value if criterion.measure is Measure.CREDITS else 1.0
            accumulator.add(
                amount,
                key=species or genus or "unknown",
                distinct_key=normalise_name(species or genus),
                sample=f"{stamp} sold {species or genus} for {value:,.0f} cr",
            )

    def _handle_bodies_scanned(
        self, accumulator: Accumulator, entry: JournalEntry
    ) -> None:
        filters = accumulator.criterion.filters
        if filters.first_discovery_only and entry.get("WasDiscovered") is not False:
            return
        system = entry.get("StarSystem") or self.tracker.state.star_system or ""
        if filters.systems and not _matches_any(system, filters.systems):
            return
        body_name = entry.get("BodyName") or "unknown body"
        body_key = f"{entry.get('SystemAddress')}:{entry.get('BodyID')}"
        stamp = entry.timestamp.isoformat() if entry.timestamp else "?"
        first = " (first discovery)" if entry.get("WasDiscovered") is False else ""
        accumulator.add(
            1.0,
            key=system or "unknown",
            distinct_key=body_key,
            sample=f"{stamp} scanned {body_name}{first}",
        )

    def _handle_bodies_mapped(
        self, accumulator: Accumulator, entry: JournalEntry
    ) -> None:
        filters = accumulator.criterion.filters
        # SAAScanComplete carries no WasMapped flag, so a first-mapping
        # restriction is answered from the Scan event for the same body.
        if filters.first_mapped_only:
            body_key = (entry.get("SystemAddress"), entry.get("BodyID"))
            if self._mapped_before.get(body_key) is True:
                return
        system = self.tracker.state.star_system or ""
        if filters.systems and not _matches_any(system, filters.systems):
            return
        body_name = entry.get("BodyName") or "unknown body"
        distinct = f"{entry.get('SystemAddress')}:{entry.get('BodyID')}"
        stamp = entry.timestamp.isoformat() if entry.timestamp else "?"
        probes = entry.get("ProbesUsed")
        suffix = f" with {probes} probes" if probes else ""
        accumulator.add(
            1.0,
            key=system or "unknown",
            distinct_key=distinct,
            sample=f"{stamp} mapped {body_name}{suffix}",
        )

    def _handle_systems_visited(
        self, accumulator: Accumulator, entry: JournalEntry
    ) -> None:
        filters = accumulator.criterion.filters
        system = entry.get("StarSystem") or ""
        if filters.systems and not _matches_any(system, filters.systems):
            return
        stamp = entry.timestamp.isoformat() if entry.timestamp else "?"
        accumulator.add(
            1.0,
            key=system or "unknown",
            distinct_key=str(entry.get("SystemAddress") or system),
            sample=f"{stamp} arrived in {system}",
        )

    def _handle_exploration_sold(
        self, accumulator: Accumulator, entry: JournalEntry
    ) -> None:
        criterion = accumulator.criterion
        filters = criterion.filters
        if not self._passes_location(entry, filters):
            return
        stamp = entry.timestamp.isoformat() if entry.timestamp else "?"
        earnings = float(entry.get("TotalEarnings") or entry.get("BaseValue") or 0)

        systems: list[str] = []
        raw_systems = entry.get("Systems")
        if isinstance(raw_systems, list):
            systems.extend(str(item) for item in raw_systems)
        discovered = entry.get("Discovered")
        if isinstance(discovered, list):
            for item in discovered:
                if isinstance(item, dict) and item.get("SystemName"):
                    systems.append(str(item["SystemName"]))
                elif isinstance(item, str):
                    systems.append(item)

        if criterion.measure is Measure.DISTINCT:
            for system in systems:
                if filters.systems and not _matches_any(system, filters.systems):
                    continue
                accumulator.add(
                    1.0,
                    key=system,
                    distinct_key=normalise_name(system),
                    sample=f"{stamp} sold data for {system}",
                )
            return

        if filters.systems and not any(
            _matches_any(system, filters.systems) for system in systems
        ):
            return
        amount = earnings if criterion.measure is Measure.CREDITS else 1.0
        label = f"{len(systems)} system(s)" if systems else "cartographic data"
        accumulator.add(
            amount,
            key="exploration data",
            sample=f"{stamp} sold {label} for {earnings:,.0f} cr",
        )

    def _handle_missions(self, accumulator: Accumulator, entry: JournalEntry) -> None:
        criterion = accumulator.criterion
        filters = criterion.filters
        # MissionCompleted carries a player-facing LocalisedName alongside
        # the internal Name; either may be what an organizer filters on.
        name = str(entry.get("LocalisedName") or entry.get("Name") or "")
        raw_name = str(entry.get("Name") or "")
        if filters.mission_names and not (
            _matches_any(name, filters.mission_names)
            or _matches_any(raw_name, filters.mission_names)
        ):
            return
        faction = entry.get("Faction") or ""
        target_faction = entry.get("TargetFaction") or ""
        if filters.factions and not (
            _matches_any(str(faction), filters.factions)
            or _matches_any(str(target_faction), filters.factions)
        ):
            return
        destination = str(entry.get("DestinationSystem") or "")
        station = str(entry.get("DestinationStation") or "")
        if filters.systems and not _matches_any(destination, filters.systems):
            return
        if filters.stations and not _matches_any(station, filters.stations):
            return

        amount = (
            float(entry.get("Reward") or 0)
            if criterion.measure is Measure.CREDITS
            else 1.0
        )
        stamp = entry.timestamp.isoformat() if entry.timestamp else "?"
        outcome = entry.event.replace("Mission", "").lower()
        accumulator.add(
            amount,
            key=name or raw_name or "mission",
            distinct_key=str(entry.get("MissionID") or ""),
            sample=f"{stamp} {outcome}: {name or raw_name}",
        )

    def _handle_bounties(self, accumulator: Accumulator, entry: JournalEntry) -> None:
        criterion = accumulator.criterion
        filters = criterion.filters
        rewards = entry.get("Rewards") or []
        factions = [
            str(item.get("Faction", "")) for item in rewards if isinstance(item, dict)
        ]
        victim = str(entry.get("VictimFaction") or "")
        if filters.factions and not (
            any(_matches_any(name, filters.factions) for name in factions)
            or _matches_any(victim, filters.factions)
        ):
            return
        if not self._passes_location(entry, filters):
            return
        total = float(entry.get("TotalReward") or 0)
        amount = total if criterion.measure is Measure.CREDITS else 1.0
        ship = entry.display_name("Target") or "ship"
        stamp = entry.timestamp.isoformat() if entry.timestamp else "?"
        accumulator.add(
            amount,
            key=victim or "unknown faction",
            sample=f"{stamp} bounty on {ship} worth {total:,.0f} cr",
        )

    def _handle_combat_bonds(
        self, accumulator: Accumulator, entry: JournalEntry
    ) -> None:
        criterion = accumulator.criterion
        filters = criterion.filters
        awarding = str(entry.get("AwardingFaction") or "")
        victim = str(entry.get("VictimFaction") or "")
        if filters.factions and not (
            _matches_any(awarding, filters.factions)
            or _matches_any(victim, filters.factions)
        ):
            return
        if not self._passes_location(entry, filters):
            return
        reward = float(entry.get("Reward") or 0)
        amount = reward if criterion.measure is Measure.CREDITS else 1.0
        stamp = entry.timestamp.isoformat() if entry.timestamp else "?"
        accumulator.add(
            amount,
            key=awarding or "unknown faction",
            sample=f"{stamp} combat bond worth {reward:,.0f} cr",
        )

    def _handle_powerplay_merits(
        self, accumulator: Accumulator, entry: JournalEntry
    ) -> None:
        filters = accumulator.criterion.filters
        power = str(entry.get("Power") or "")
        if filters.powers and not _matches_any(power, filters.powers):
            return
        if not self._passes_location(entry, filters):
            return
        merits = float(entry.get("MeritsGained") or 0)
        stamp = entry.timestamp.isoformat() if entry.timestamp else "?"
        accumulator.add(
            merits,
            key=power or "unknown power",
            sample=f"{stamp} +{merits:,.0f} merits for {power}",
        )

    def _handle_colonisation_contribution(
        self, accumulator: Accumulator, entry: JournalEntry
    ) -> None:
        criterion = accumulator.criterion
        filters = criterion.filters
        if not self._passes_location(entry, filters):
            return
        contributions = entry.get("Contributions") or []
        if not isinstance(contributions, list):
            return

        stamp = entry.timestamp.isoformat() if entry.timestamp else "?"
        _, station, _, market_id = self._location_names(entry)
        where = station or self.tracker.describe_market(market_id)

        matched: list[tuple[str, float]] = []
        for item in contributions:
            if not isinstance(item, dict):
                continue
            raw = str(item.get("Name") or "")
            localised = str(item.get("Name_Localised") or "")
            if filters.commodities and not (
                _matches_commodity(raw, filters.commodities)
                or _matches_commodity(localised, filters.commodities)
            ):
                continue
            matched.append(
                (localised or _prettify(raw), float(item.get("Amount") or 0))
            )

        if not matched:
            return

        if criterion.measure is Measure.COUNT:
            # One delivery, however many commodities were in the hold.
            total = sum(amount for _, amount in matched)
            names = ", ".join(name for name, _ in matched)
            accumulator.add(
                1.0,
                key=where,
                sample=f"{stamp} delivered {total:,.0f} t ({names}) to {where}",
            )
            return

        for commodity, amount in matched:
            accumulator.add(
                amount,
                key=commodity or "unknown",
                distinct_key=normalise_name(commodity),
                sample=(f"{stamp} delivered {amount:,.0f} t {commodity} to {where}"),
            )

    def _handle_colonisation_completion(
        self, accumulator: Accumulator, entry: JournalEntry
    ) -> None:
        if not entry.get("ConstructionComplete"):
            return
        market_id = entry.get("MarketID")
        if not isinstance(market_id, int):
            return
        # A depot event fires whenever the site is viewed, including by
        # commanders who delivered nothing. Only credit a completion to
        # someone who actually supplied that site.
        if market_id not in self._colonisation_supplied:
            return
        filters = accumulator.criterion.filters
        if not self._passes_location(entry, filters):
            return

        _, station, _, _ = self._location_names(entry)
        where = station or self.tracker.describe_market(market_id)
        stamp = entry.timestamp.isoformat() if entry.timestamp else "?"
        accumulator.add(
            1.0,
            key=where,
            distinct_key=str(market_id),
            sample=f"{stamp} construction completed at {where}",
        )


#: Dispatch table built once, keyed by metric kind.
_HANDLERS = {
    MetricKind.EVENT_COUNT: MetricEvaluator._handle_event_count,
    MetricKind.MINING_REFINED: MetricEvaluator._handle_mining,
    MetricKind.MARKET_SELL: MetricEvaluator._handle_market,
    MetricKind.MARKET_BUY: MetricEvaluator._handle_market,
    MetricKind.EXOBIO_SCANNED: MetricEvaluator._handle_exobio_scanned,
    MetricKind.EXOBIO_SOLD: MetricEvaluator._handle_exobio_sold,
    MetricKind.BODIES_SCANNED: MetricEvaluator._handle_bodies_scanned,
    MetricKind.BODIES_MAPPED: MetricEvaluator._handle_bodies_mapped,
    MetricKind.SYSTEMS_VISITED: MetricEvaluator._handle_systems_visited,
    MetricKind.EXPLORATION_SOLD: MetricEvaluator._handle_exploration_sold,
    MetricKind.MISSIONS: MetricEvaluator._handle_missions,
    MetricKind.BOUNTIES: MetricEvaluator._handle_bounties,
    MetricKind.COMBAT_BONDS: MetricEvaluator._handle_combat_bonds,
    MetricKind.POWERPLAY_MERITS: MetricEvaluator._handle_powerplay_merits,
    MetricKind.COLONISATION_CONTRIBUTION: (
        MetricEvaluator._handle_colonisation_contribution
    ),
    MetricKind.COLONISATION_COMPLETION: (
        MetricEvaluator._handle_colonisation_completion
    ),
}


@dataclass
class ScanOutcome:
    """Everything a journal scan produced."""

    results: list[CriterionResult]
    stats: ReadStats
    first_event: str | None
    last_event: str | None
    game_versions: list[str]
    squadron_events: list[JournalEntry] = field(default_factory=list)

    @property
    def total_points(self) -> float:
        return round(sum(item.points for item in self.results), 4)


def build_market_directory(directory: Path) -> MarketDirectory:
    """Pre-index every market named anywhere in a journal directory.

    Run before scoring so that a sale can be attributed to a station even
    when the docking event that names it falls in a later journal file
    than the sale, which happens across session boundaries.
    """
    markets = MarketDirectory()
    for entry in iter_journal_dir(directory):
        markets.observe(entry)
    return markets


def scan_journals(
    directory: Path,
    criteria: Iterable[Criterion],
    window: EventWindow,
    progress: Any = None,
) -> ScanOutcome:
    """Score a commander's journals against ``criteria``.

    ``progress`` is an optional callable taking ``(entries_seen, phase)``
    so a user interface can show movement during a long scan.
    """
    criteria = list(criteria)
    markets = build_market_directory(directory)
    if progress is not None:
        progress(0, "indexing markets")

    evaluator = MetricEvaluator(criteria, window, markets)
    stats = ReadStats()
    first_event: str | None = None
    last_event: str | None = None
    versions: set[str] = set()
    squadron_events: list[JournalEntry] = []

    from edsg.core.squadron import SQUADRON_EVENTS  # local: avoids a cycle

    for index, entry in enumerate(iter_journal_dir(directory, stats), start=1):
        if entry.timestamp is not None:
            stamp = entry.timestamp.isoformat()
            if first_event is None:
                first_event = stamp
            last_event = stamp
        if entry.event == "Fileheader":
            version = entry.get("gameversion")
            if isinstance(version, str) and version:
                versions.add(version)
        if entry.event in SQUADRON_EVENTS:
            squadron_events.append(entry)
        evaluator.feed(entry)
        if progress is not None and index % 25_000 == 0:
            progress(index, "scoring")

    if progress is not None:
        progress(stats.entries_parsed, "done")

    return ScanOutcome(
        results=evaluator.results(),
        stats=stats,
        first_event=first_event,
        last_event=last_event,
        game_versions=sorted(versions),
        squadron_events=squadron_events,
    )


__all__ = [
    "MAX_BREAKDOWN_KEYS",
    "MAX_SAMPLES",
    "METRIC_EVENTS",
    "Accumulator",
    "MetricEvaluator",
    "ScanOutcome",
    "build_market_directory",
    "scan_journals",
]
