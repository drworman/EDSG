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
