"""Behaviour changed in response to external tester feedback.

Each test here corresponds to a reported defect, so a regression shows
up as a named failure rather than a vague one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from conftest import commander_events
from edsg.core.journal import (
    MultipleCommandersError,
    detect_commanders,
    resolve_commander,
)
from edsg.core.paths import (
    INVITATION_DIRNAME,
    STANDINGS_DIRNAME,
    SUBMISSIONS_DIRNAME,
    app_root,
    documents_dir,
    event_paths,
)


def _write_journal(directory: Path, name: str, events: list[dict]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(
        "\n".join(json.dumps(event) for event in events), encoding="utf-8"
    )


# -- a folder holding several commanders -------------------------------


def test_several_commanders_offers_a_choice(tmp_path):
    """Elite writes every account into one folder; that is not an error.

    The tester could not complete a run at all because EDSG refused a
    folder containing a second account's journals.
    """
    _write_journal(
        tmp_path, "Journal.2026-06-01T120000.01.log", commander_events("ONE", "F1")
    )
    _write_journal(
        tmp_path, "Journal.2026-06-02T120000.01.log", commander_events("TWO", "F2")
    )

    with pytest.raises(MultipleCommandersError) as caught:
        resolve_commander(tmp_path)

    found = {item.fid for item in caught.value.commanders}
    assert found == {"F1", "F2"}


def test_naming_a_commander_resolves_the_ambiguity(tmp_path):
    _write_journal(
        tmp_path, "Journal.2026-06-01T120000.01.log", commander_events("ONE", "F1")
    )
    _write_journal(
        tmp_path, "Journal.2026-06-02T120000.01.log", commander_events("TWO", "F2")
    )

    chosen = resolve_commander(tmp_path, fid="F2")
    assert chosen.name == "TWO"
    assert chosen.fid == "F2"


def test_an_unknown_commander_is_reported(tmp_path):
    _write_journal(
        tmp_path, "Journal.2026-06-01T120000.01.log", commander_events("ONE", "F1")
    )
    with pytest.raises(Exception, match="No journals for commander"):
        resolve_commander(tmp_path, fid="F999")


def test_a_single_commander_still_needs_no_choice(tmp_path):
    _write_journal(
        tmp_path, "Journal.2026-06-01T120000.01.log", commander_events("ONE", "F1")
    )
    assert resolve_commander(tmp_path).fid == "F1"
    assert len(detect_commanders(tmp_path)) == 1


# -- the workspace lives in Documents ----------------------------------


def test_the_workspace_defaults_to_documents(monkeypatch):
    """Writing beside the binary fails in Program Files and breaks a
    signed macOS bundle, so events belong in the user's documents."""
    monkeypatch.delenv("EDSG_HOME", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert app_root() == documents_dir() / "EDSG"


def test_edsg_home_overrides_the_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("EDSG_HOME", str(tmp_path))
    assert app_root() == tmp_path


def test_event_folders_are_numbered_in_use_order(tmp_path, monkeypatch):
    """Alphabetically 'standings' fell between the other two, putting the
    last step in the middle of the folder listing."""
    monkeypatch.setenv("EDSG_HOME", str(tmp_path))
    paths = event_paths("Summer Drive").create()

    assert paths.invitation.name == INVITATION_DIRNAME
    assert paths.submissions.name == SUBMISSIONS_DIRNAME
    assert paths.standings.name == STANDINGS_DIRNAME

    listed = sorted(item.name for item in paths.root.iterdir())
    assert listed == [INVITATION_DIRNAME, SUBMISSIONS_DIRNAME, STANDINGS_DIRNAME]


# -- the event period ---------------------------------------------------


@pytest.mark.gui
def test_the_period_defaults_to_whole_days(qt_app, tmp_path, monkeypatch):
    """A default of 'now' silently excluded the first part of day one.

    The tester's own event ran from 2026-01-01T10:39:36, so anything
    logged that morning was not counted.
    """
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("EDSG_HOME", str(tmp_path / "home"))
    from edsg.gui.organizer import OrganizerWindow

    window = OrganizerWindow()
    try:
        start = window.start_edit.dateTime().toPython()
        end = window.end_edit.dateTime().toPython()
        assert (start.hour, start.minute, start.second) == (0, 0, 0)
        assert (end.hour, end.minute, end.second) == (23, 59, 59)
        # Seconds are shown because they are stored.
        assert "ss" in window.start_edit.displayFormat()
    finally:
        window.deleteLater()


@pytest.mark.gui
def test_quick_set_covers_a_whole_year(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("EDSG_HOME", str(tmp_path / "home"))
    from edsg.gui.organizer import OrganizerWindow

    window = OrganizerWindow()
    try:
        window._period_this_year()
        start = window.start_edit.dateTime().toPython()
        end = window.end_edit.dateTime().toPython()
        assert (start.month, start.day, start.hour) == (1, 1, 0)
        assert (end.month, end.day, end.hour, end.second) == (12, 31, 23, 59)
        assert start.year == end.year
    finally:
        window.deleteLater()


# -- the standings table ------------------------------------------------


@pytest.mark.gui
def test_points_is_not_the_stretched_column(qt_app, tmp_path, monkeypatch):
    """Points right-aligned in a stretched last column read as empty."""
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("EDSG_HOME", str(tmp_path / "home"))
    from PySide6.QtWidgets import QHeaderView

    from edsg.gui.organizer import OrganizerWindow

    window = OrganizerWindow()
    try:
        header = window.standings_tree.header()
        assert header.stretchLastSection() is False
        # Commander takes the slack instead.
        assert header.sectionResizeMode(1) == QHeaderView.Stretch
        assert header.sectionResizeMode(3) == QHeaderView.Fixed
    finally:
        window.deleteLater()


# -- autosave ------------------------------------------------------------


@pytest.mark.gui
def test_the_working_event_is_autosaved(qt_app, tmp_path, monkeypatch):
    """Closing the window used to lose an unsaved event entirely."""
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("EDSG_HOME", str(tmp_path / "home"))
    from edsg.gui.organizer import AUTOSAVE_NAME, OrganizerWindow

    window = OrganizerWindow()
    try:
        window.name_field.setText("Autosave Test")
        window._collect()
        window._autosave()

        saved = event_paths("Autosave Test").root / AUTOSAVE_NAME
        assert saved.is_file()
        assert json.loads(saved.read_text())["name"] == "Autosave Test"
    finally:
        window.deleteLater()


@pytest.mark.gui
def test_autosave_ignores_an_unnamed_event(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("EDSG_HOME", str(tmp_path / "home"))
    from edsg.gui.organizer import OrganizerWindow

    window = OrganizerWindow()
    try:
        window.name_field.setText("   ")
        window._collect()
        window._autosave()
        assert not (tmp_path / "home" / "Events").exists()
    finally:
        window.deleteLater()
