"""GUI smoke tests.

These exist because of a specific bug: migrating the enums to ``StrEnum``
broke the criterion dialog completely, and the whole core-level suite
still passed. Qt round-trips combo box user data through ``QVariant``,
which turns a ``StrEnum`` member back into a plain ``str``, so
``currentData()`` no longer returned an enum.

Nothing here tests appearance. They check that the dialogs construct,
that every metric can be selected, and that what comes back out is a
valid domain object.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="Qt is not installed")

from PySide6.QtWidgets import QApplication

from edsg.core.criteria import ALLOWED_MEASURES, Measure, MetricKind
from edsg.core.models import TieBreak

pytestmark = pytest.mark.gui


@pytest.fixture(scope="module")
def app():
    """A single QApplication for the module; Qt allows only one."""
    existing = QApplication.instance()
    yield existing or QApplication([])


@pytest.fixture
def dialog(app):
    from edsg.gui.criterion_dialog import CriterionDialog

    widget = CriterionDialog(None)
    yield widget
    widget.deleteLater()


def test_every_metric_can_be_selected(dialog):
    """Selecting a metric must not raise and must round-trip as an enum."""
    for kind in MetricKind:
        index = dialog.kind_box.findData(kind)
        assert index >= 0, f"{kind.value} is missing from the metric list"
        dialog.kind_box.setCurrentIndex(index)
        assert dialog._current_kind() is kind
        assert isinstance(dialog._current_kind(), MetricKind)


def test_measures_offered_match_the_metric(dialog):
    for kind in MetricKind:
        dialog.kind_box.setCurrentIndex(dialog.kind_box.findData(kind))
        offered = {
            Measure(dialog.measure_box.itemData(i))
            for i in range(dialog.measure_box.count())
        }
        assert offered == set(ALLOWED_MEASURES[kind]), kind.value
        assert isinstance(dialog._current_measure(), Measure)


def test_metric_help_text_is_present_for_every_metric(dialog):
    for kind in MetricKind:
        dialog.kind_box.setCurrentIndex(dialog.kind_box.findData(kind))
        assert dialog.kind_help.text().strip(), kind.value


def test_saving_produces_a_valid_criterion(dialog):
    dialog.kind_box.setCurrentIndex(
        dialog.kind_box.findData(MetricKind.COLONISATION_CONTRIBUTION)
    )
    dialog.label_field.setText("Colonisation cargo")
    dialog.commodities_field.setText("Steel, CMM Composite")
    dialog.market_ids_field.setText("3955868162")
    dialog.points_spin.setValue(0.5)
    dialog._save()

    criterion = dialog.result_criterion
    assert criterion is not None
    assert criterion.kind is MetricKind.COLONISATION_CONTRIBUTION
    assert criterion.measure is Measure.TONNAGE
    assert criterion.filters.commodities == ["Steel", "CMM Composite"]
    assert criterion.filters.market_ids == [3955868162]
    assert not criterion.validate()


def test_irrelevant_filters_are_hidden(dialog):
    """A mining criterion must not offer a mission-outcome row."""
    dialog.kind_box.setCurrentIndex(dialog.kind_box.findData(MetricKind.MINING_REFINED))
    assert not dialog.rows["outcomes"][1].isVisible()
    assert not dialog.rows["genera"][1].isVisible()

    dialog.kind_box.setCurrentIndex(dialog.kind_box.findData(MetricKind.MISSIONS))
    assert dialog.rows["mission_names"][1].isVisibleTo(dialog)


def test_organizer_window_builds_and_collects(app, tmp_path, monkeypatch):
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path / "cfg"))
    from edsg.gui.organizer import OrganizerWindow

    window = OrganizerWindow()
    try:
        window.name_field.setText("Smoke Test Event")
        window._collect()
        assert window.event_def.name == "Smoke Test Event"
        # The tie-break must survive the QVariant round-trip as an enum.
        assert isinstance(window.event_def.tie_break, TieBreak)
        # No criteria yet, so the event must report itself as not ready.
        assert window.event_def.validate()
    finally:
        window.deleteLater()


def test_participant_window_builds(app, tmp_path, monkeypatch):
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path / "cfg"))
    from edsg.gui.participant import ParticipantWindow

    window = ParticipantWindow()
    try:
        # Nothing loaded, so scanning must be unavailable.
        assert not window.scan_button.isEnabled()
        assert not window.save_button.isEnabled()
    finally:
        window.deleteLater()


def test_worker_reference_is_held_until_it_reports(app):
    """A running worker must not be collectable.

    Losing the reference lets Qt destroy the signals object while a
    queued emission is still in flight, which segfaults inside the event
    loop with no Python traceback.
    """
    import gc

    from edsg.gui import widgets

    started = widgets.run_in_background(
        lambda report: "value", lambda r: None, lambda e: None
    )
    assert started in widgets._ACTIVE_WORKERS
    gc.collect()
    assert started in widgets._ACTIVE_WORKERS
    assert widgets.wait_for_workers(5000)


def test_workers_do_not_autodelete(app):
    """Qt must not own the runnable; Python does."""
    from edsg.gui.widgets import Worker

    worker = Worker(lambda report: None)
    assert worker.autoDelete() is False


def test_preview_populates_the_standings_table(app, tmp_path, monkeypatch):
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path / "cfg"))

    from edsg.core.criteria import Criterion, Filters
    from edsg.core.crypto import generate_identity
    from edsg.core.journal import parse_timestamp
    from edsg.core.models import (
        Eligibility,
        EventDefinition,
        EventState,
        EventWindow,
    )
    from edsg.core.workflow import issue_invitation, load_invitation, participate
    from edsg.gui.organizer import OrganizerWindow
    from edsg.gui.widgets import wait_for_workers

    event = EventDefinition(
        name="Preview Test",
        window=EventWindow(
            start=parse_timestamp("2026-06-01T00:00:00Z"),
            end=parse_timestamp("2026-06-30T23:59:59Z"),
        ),
        eligibility=Eligibility.OPEN,
        criteria=[
            Criterion(
                criterion_id="m1",
                label="Tritium",
                kind=MetricKind.MINING_REFINED,
                measure=Measure.TONNAGE,
                filters=Filters(commodities=["Tritium"]),
                points_per_unit=1.0,
            )
        ],
    )
    invitation = load_invitation(
        issue_invitation(event, generate_identity("org"), tmp_path)
    )

    import json as _json

    journal = tmp_path / "journal"
    journal.mkdir()
    events = [
        {
            "timestamp": "2026-06-01T12:00:01Z",
            "event": "Commander",
            "FID": "F1",
            "Name": "PREVIEW",
        },
        *(
            {
                "timestamp": "2026-06-05T10:00:00Z",
                "event": "MiningRefined",
                "Type": "$tritium_name;",
                "Type_Localised": "Tritium",
            }
            for _ in range(9)
        ),
    ]
    (journal / "Journal.2026-06-01T120000.01.log").write_text(
        "\n".join(_json.dumps(item) for item in events), encoding="utf-8"
    )
    subs = tmp_path / "subs"
    participate(invitation, journal, generate_identity("p"), subs)

    window = OrganizerWindow()
    try:
        window.event_def = event
        window.event_def.state = EventState.OPEN
        window._populate()
        window.submissions_picker.set_path(subs)
        window._preview_standings()
        assert wait_for_workers(10_000)
        app.processEvents()

        assert window.standings_tree.topLevelItemCount() == 1
        assert "Preview" in window.standings_status.text()
        # The whole point: previewing must not close anything.
        assert window.event_def.state is EventState.OPEN
        assert window.event_def.closed_at is None
    finally:
        window.deleteLater()


def test_support_links_open_their_destinations(app, monkeypatch):
    """Each funding button must hand its own URL to the browser.

    Guards two things a screenshot cannot: that the buttons are wired at
    all, and that the lambda captures each link rather than closing over
    the loop variable and sending everyone to PayPal.
    """
    from PySide6.QtWidgets import QPushButton

    from edsg.gui import about

    opened: list[str] = []

    class Opens:
        @staticmethod
        def openUrl(url):
            opened.append(url.toString())
            return True

    monkeypatch.setattr(about, "QDesktopServices", Opens)

    strip = about.SupportStrip()
    buttons = strip.findChildren(QPushButton)
    assert len(buttons) == len(about.funding_links())

    for widget in buttons:
        widget.click()

    assert opened == [link.url for link in about.funding_links()]
    strip.deleteLater()


def test_failed_link_shows_the_address(app, monkeypatch):
    """A browser that will not open must not look like a dead button."""
    from PySide6.QtWidgets import QPushButton

    from edsg.gui import about

    class Refuses:
        @staticmethod
        def openUrl(url):
            return False

    shown: list[str] = []
    monkeypatch.setattr(about, "QDesktopServices", Refuses)
    monkeypatch.setattr(
        about,
        "show_info",
        lambda parent, title, message, detail="": shown.append(detail),
    )

    strip = about.SupportStrip()
    for widget in strip.findChildren(QPushButton):
        widget.click()

    assert shown == [link.url for link in about.funding_links()]
    strip.deleteLater()


def test_help_menu_offers_every_support_link(app, tmp_path, monkeypatch):
    """The same destinations must be reachable from the menu bar."""
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path / "cfg"))
    import gc

    from edsg.gui.about import funding_links
    from edsg.gui.organizer import OrganizerWindow

    window = OrganizerWindow()
    try:
        # Reading a menu twice is exactly what broke before: PySide6
        # returns a new wrapper each time, and dropping one destroyed the
        # menu. This test asserts the fix by doing precisely that.
        menus = {
            action.text().replace("&", ""): action.menu()
            for action in window.menuBar().actions()
            if action.menu() is not None
        }
        gc.collect()
        assert set(menus) == {"File", "Options", "Help"}

        help_items = {
            action.text().replace("&", "") for action in menus["Help"].actions()
        }
        assert "About EDSG" in help_items
        assert "Documentation" in help_items
        assert "Project on GitHub" in help_items

        options_items = {
            action.text().replace("&", "") for action in menus["Options"].actions()
        }
        assert any(item.startswith("Preferences") for item in options_items)

        support = next(
            action.menu()
            for action in menus["Help"].actions()
            if action.menu() is not None
        )
        offered = {action.text().replace("&", "") for action in support.actions()}
        assert {link.label for link in funding_links()} == offered
    finally:
        window.deleteLater()
