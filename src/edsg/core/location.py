"""Tracking where the commander is as the journal replays.

Several scoring-relevant events carry no location of their own. A
``MarketSell`` records only a ``MarketID``; ``MiningRefined`` records
nothing but the commodity. Yet organizers want rules like "ore sold to
this specific fleet carrier" or "tonnage mined in this system".

The tracker replays location-bearing events to maintain the current
system and station, and separately builds a ``MarketID`` directory so a
market can be named even when the sale happened before the docking event
that identified it was seen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from edsg.core.journal import JournalEntry

#: Events that establish or change the commander's location.
LOCATION_EVENTS = frozenset(
    {
        "CarrierJump",
        "Docked",
        "FSDJump",
        "Location",
        "SupercruiseExit",
        "Undocked",
    }
)

#: Station types that are mobile, and so cannot be pinned to a system.
CARRIER_STATION_TYPES = frozenset({"FleetCarrier"})


@dataclass
class MarketRecord:
    """What is known about a market encountered in the journal."""

    market_id: int
    station_name: str = ""
    station_type: str = ""
    star_system: str = ""

    @property
    def is_carrier(self) -> bool:
        return self.station_type in CARRIER_STATION_TYPES


@dataclass
class LocationState:
    """The commander's position at a point in the journal replay."""

    star_system: str = ""
    system_address: int | None = None
    station_name: str = ""
    station_type: str = ""
    market_id: int | None = None
    body: str = ""
    docked: bool = False

    def snapshot(self) -> dict[str, Any]:
        """Return a plain dict copy, for attaching to a matched event."""
        return {
            "star_system": self.star_system,
            "station_name": self.station_name,
            "station_type": self.station_type,
            "market_id": self.market_id,
            "body": self.body,
            "docked": self.docked,
        }


class LocationTracker:
    """Maintains :class:`LocationState` across a journal replay."""

    def __init__(self) -> None:
        self.state = LocationState()
        self.markets: dict[int, MarketRecord] = {}

    def observe(self, entry: JournalEntry) -> None:
        """Update state from ``entry`` if it is location-bearing."""
        if entry.event not in LOCATION_EVENTS:
            return
        handler = getattr(self, f"_on_{entry.event.lower()}")
        handler(entry)

    # -- individual event handlers ------------------------------------

    def _remember_market(self, entry: JournalEntry) -> None:
        market_id = entry.get("MarketID")
        if not isinstance(market_id, int):
            return
        station_name = entry.get("StationName") or ""
        station_type = entry.get("StationType") or ""
        star_system = entry.get("StarSystem") or ""
        record = self.markets.get(market_id)
        if record is None:
            record = MarketRecord(market_id=market_id)
            self.markets[market_id] = record
        # Later observations win: a carrier's system legitimately changes.
        if station_name:
            record.station_name = station_name
        if station_type:
            record.station_type = station_type
        if star_system:
            record.star_system = star_system

    def _apply_system(self, entry: JournalEntry) -> None:
        star_system = entry.get("StarSystem")
        if isinstance(star_system, str) and star_system:
            self.state.star_system = star_system
        address = entry.get("SystemAddress")
        if isinstance(address, int):
            self.state.system_address = address
        body = entry.get("Body")
        if isinstance(body, str):
            self.state.body = body

    def _apply_station(self, entry: JournalEntry) -> None:
        self.state.station_name = entry.get("StationName") or ""
        self.state.station_type = entry.get("StationType") or ""
        market_id = entry.get("MarketID")
        self.state.market_id = market_id if isinstance(market_id, int) else None

    def _on_fsdjump(self, entry: JournalEntry) -> None:
        self._apply_system(entry)
        self.state.docked = False
        self.state.station_name = ""
        self.state.station_type = ""
        self.state.market_id = None

    def _on_location(self, entry: JournalEntry) -> None:
        self._apply_system(entry)
        self.state.docked = bool(entry.get("Docked"))
        if self.state.docked:
            self._apply_station(entry)
            self._remember_market(entry)
        else:
            self.state.station_name = ""
            self.state.station_type = ""
            self.state.market_id = None

    def _on_docked(self, entry: JournalEntry) -> None:
        self._apply_system(entry)
        self._apply_station(entry)
        self.state.docked = True
        self._remember_market(entry)

    def _on_undocked(self, entry: JournalEntry) -> None:
        self.state.docked = False
        self.state.station_name = ""
        self.state.station_type = ""
        self.state.market_id = None

    def _on_carrierjump(self, entry: JournalEntry) -> None:
        # A carrier jump moves the carrier and, if docked, the commander.
        self._apply_system(entry)
        self.state.docked = bool(entry.get("Docked", True))
        if self.state.docked:
            self._apply_station(entry)
        self._remember_market(entry)

    def _on_supercruiseexit(self, entry: JournalEntry) -> None:
        self._apply_system(entry)
        self.state.docked = False

    # -- lookup --------------------------------------------------------

    def market(self, market_id: int | None) -> MarketRecord | None:
        """Return what is known about ``market_id``, if anything."""
        if market_id is None:
            return None
        return self.markets.get(market_id)

    def describe_market(self, market_id: int | None) -> str:
        """Return a display string for a market, falling back to its ID."""
        record = self.market(market_id)
        if record is None:
            return f"Market {market_id}" if market_id is not None else "Unknown"
        if record.station_name and record.star_system:
            return f"{record.station_name} ({record.star_system})"
        return record.station_name or f"Market {market_id}"


@dataclass
class MarketDirectory:
    """A standalone pre-pass index of every market seen in a journal.

    Built before scoring so that a sale can be attributed even when the
    corresponding ``Docked`` event lies later in the journal than the
    sale itself, which happens whenever a journal file boundary falls
    between them.
    """

    records: dict[int, MarketRecord] = field(default_factory=dict)

    def observe(self, entry: JournalEntry) -> None:
        market_id = entry.get("MarketID")
        if not isinstance(market_id, int):
            return
        station_name = entry.get("StationName")
        if not isinstance(station_name, str) or not station_name:
            return
        record = self.records.get(market_id)
        if record is None:
            record = MarketRecord(market_id=market_id)
            self.records[market_id] = record
        record.station_name = station_name
        station_type = entry.get("StationType")
        if isinstance(station_type, str) and station_type:
            record.station_type = station_type
        star_system = entry.get("StarSystem")
        if isinstance(star_system, str) and star_system:
            record.star_system = star_system


__all__ = [
    "CARRIER_STATION_TYPES",
    "LOCATION_EVENTS",
    "LocationState",
    "LocationTracker",
    "MarketDirectory",
    "MarketRecord",
]
