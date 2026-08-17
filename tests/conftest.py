"""Shared fixtures.

Journal fixtures are synthesised rather than checked in, so the suite has
no dependency on any real commander's play history and can exercise
events Frontier's own logs happen not to contain.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from edsg.core.criteria import Criterion, Filters, Measure, MetricKind
from edsg.core.crypto import generate_identity
from edsg.core.journal import parse_timestamp
from edsg.core.models import Eligibility, EventDefinition, EventWindow
from edsg.core.squadron import SquadronRef


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Keep every test out of the developer's real EDSG config directory."""
    config = tmp_path / "config"
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(config))
    return config


def write_journal(directory: Path, name: str, events: list[dict]) -> Path:
    """Write a journal file containing ``events``."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")
    return path


@pytest.fixture
def make_journal(tmp_path):
    """Return a factory building a journal directory from event dicts."""

    def factory(events: list[dict], name: str = "cmdr") -> Path:
        directory = tmp_path / name
        write_journal(directory, "Journal.2026-06-01T120000.01.log", events)
        return directory

    return factory


def commander_events(name: str = "TESTER", fid: str = "F1234567") -> list[dict]:
    """Return the minimum events identifying a commander."""
    return [
        {
            "timestamp": "2026-06-01T12:00:00Z",
            "event": "Fileheader",
            "part": 1,
            "gameversion": "4.4.0.0",
        },
        {
            "timestamp": "2026-06-01T12:00:01Z",
            "event": "Commander",
            "FID": fid,
            "Name": name,
        },
        {
            "timestamp": "2026-06-01T12:00:02Z",
            "event": "LoadGame",
            "FID": fid,
            "Commander": name,
            "GameMode": "Solo",
        },
    ]


@pytest.fixture
def identity():
    return generate_identity("test identity")


@pytest.fixture
def window():
    return EventWindow(
        start=parse_timestamp("2026-06-01T00:00:00Z"),
        end=parse_timestamp("2026-06-30T23:59:59Z"),
    )


@pytest.fixture
def simple_event(window):
    """A minimal valid event.

    Squadron-locked with a capped criterion, because both are now
    required: credits can only be handed over through the squadron bank,
    and the cap is what a capped criterion races for.
    """
    return EventDefinition(
        name="Test Event",
        organizer_name="CMDR Organizer",
        window=window,
        eligibility=Eligibility.SQUADRON,
        squadron=SquadronRef(squadron_id=110393, name="TEST SQUADRON"),
        criteria=[
            Criterion(
                criterion_id="mining01",
                label="Tritium mined",
                kind=MetricKind.MINING_REFINED,
                measure=Measure.TONNAGE,
                filters=Filters(commodities=["Tritium"]),
                points_per_unit=2.0,
                unit_cap=1000,
            )
        ],
    )


@pytest.fixture
def squadron():
    return SquadronRef(squadron_id=110393, name="TEST SQUADRON")


@pytest.fixture(scope="session")
def qt_app():
    """A single QApplication for the whole session.

    Qt permits only one, and creating a second in the same process
    aborts, so every GUI test shares this.
    """
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from edsg.gui.theme import apply_theme

    existing = QApplication.instance()
    application = existing or QApplication([])
    apply_theme(application)
    return application
