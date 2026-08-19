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


# -- squadron-only events ----------------------------------------------


def test_every_event_is_squadron_locked(simple_event):
    """Credits can only be handed over through the squadron bank, so an
    open event could not pay its winners."""
    from edsg.core.models import Eligibility

    assert simple_event.eligibility is Eligibility.SQUADRON
    assert not simple_event.validate()

    simple_event.squadron = None
    problems = simple_event.validate()
    assert any("squadron" in item.lower() for item in problems)


def test_a_new_event_defaults_to_squadron():
    from edsg.core.models import Eligibility, EventDefinition

    assert EventDefinition(name="X").eligibility is Eligibility.SQUADRON


def test_the_organizer_offers_no_open_option(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("EDSG_HOME", str(tmp_path / "home"))
    from edsg.gui.organizer import OrganizerWindow

    window = OrganizerWindow()
    try:
        assert not hasattr(window, "open_radio")
        assert not hasattr(window, "squadron_radio")
    finally:
        window.deleteLater()


# -- the unit cap is required ------------------------------------------


def test_a_criterion_without_a_unit_cap_is_refused():
    """The cap is what the criterion races for, and it bounds how much
    of a journal a submission has to carry."""
    from edsg.core.criteria import Criterion, Measure, MetricKind

    criterion = Criterion(
        criterion_id="x",
        label="Uncapped",
        kind=MetricKind.MINING_REFINED,
        measure=Measure.TONNAGE,
    )
    assert any("unit cap" in item.lower() for item in criterion.validate())

    criterion.unit_cap = 100
    assert not criterion.validate()


def test_the_point_ceiling_is_the_sum_of_the_caps(simple_event):
    # One criterion: 1000 units at 2 points each.
    assert simple_event.point_ceiling() == 2000.0


# -- the Rewards tab ----------------------------------------------------


def test_the_rewards_tab_sits_between_criteria_and_issue(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("EDSG_HOME", str(tmp_path / "home"))
    from edsg.gui.organizer import OrganizerWindow

    window = OrganizerWindow()
    try:
        titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]
        assert len(titles) == 5
        assert "Criteria" in titles[1]
        assert "Rewards" in titles[2]
        assert "Issue" in titles[3]
    finally:
        window.deleteLater()


def test_tier_thresholds_follow_the_criteria(qt_app):
    """Unticking a tier rebalances the rest, and nothing is typed."""
    from edsg.core.tiers import TierPlan
    from edsg.gui.rewards_panel import RewardsPanel

    panel = RewardsPanel()
    try:
        panel.load(
            TierPlan(enabled=True, tier_count=5, reward_pool=500),
            2000.0,
        )
        # Listed from the top down.
        assert panel.tier_rows[0].index == 5
        assert panel.tier_rows[-1].index == 1
        assert panel.tier_rows[0].threshold.text() == "2,000"
        assert panel.tier_rows[-1].threshold.text() == "400"

        panel.tier_rows[0].enabled.setChecked(False)
        assert panel.tier_count() == 4
        # The top tier in use is still the full ceiling.
        assert panel.tier_rows[1].threshold.text() == "2,000"
        assert panel.tier_rows[-1].threshold.text() == "500"
    finally:
        panel.deleteLater()


def test_at_least_one_goal_tier_always_remains(qt_app):
    from edsg.core.tiers import TierPlan
    from edsg.gui.rewards_panel import RewardsPanel

    panel = RewardsPanel()
    try:
        panel.load(
            TierPlan(enabled=True, reward_pool=10),
            1000.0,
        )
        for row in panel.tier_rows:
            row.enabled.setChecked(False)
        assert panel.tier_count() >= 1
    finally:
        panel.deleteLater()


# -- submission filenames ----------------------------------------------


def test_a_submission_is_named_for_its_event_and_commander():
    """A commander in several events, or running two accounts, must not
    overwrite their own file."""
    from edsg.core.models import Submission

    submission = Submission(
        event_id="x",
        invitation_fingerprint="y",
        event_name="20260817 Mining Drive Test",
        commander_fid="F10467336",
        commander_name="HUGH JASSOLE",
    )
    assert submission.filename() == (
        "20260817-Mining-Drive-Test-F10467336-HUGH-JASSOLE.edsgs"
    )


def test_awkward_names_still_produce_a_usable_filename():
    from edsg.core.models import Submission

    submission = Submission(
        event_id="x",
        invitation_fingerprint="y",
        event_name="Test Event #1",
        commander_fid="F1",
        commander_name="KO'ATL",
    )
    name = submission.filename()
    assert name == "Test-Event-1-F1-KO-ATL.edsgs"
    assert "--" not in name


def test_two_events_do_not_collide():
    from edsg.core.models import Submission

    def named(event: str) -> str:
        return Submission(
            event_id="x",
            invitation_fingerprint="y",
            event_name=event,
            commander_fid="F1",
            commander_name="A",
        ).filename()

    assert named("First Event") != named("Second Event")


# -- the criterion dialog layout ---------------------------------------


def test_the_scoring_fields_share_one_width(qt_app):
    """The Unit Cap was too narrow to read a five-figure number in."""
    from edsg.gui.criterion_dialog import FIELD_WIDTH, CriterionDialog

    dialog = CriterionDialog(None, None)
    try:
        assert dialog.cap_field.width() == FIELD_WIDTH
        assert dialog.minimum_field.width() == FIELD_WIDTH
        assert dialog.points_spin.width() == FIELD_WIDTH
    finally:
        dialog.deleteLater()


# -- the tie-break control is gone -------------------------------------


def test_the_organizer_offers_no_tie_break_control(qt_app, tmp_path, monkeypatch):
    """Ties now share a rank and are paid alike, so there is nothing
    left for an organizer to choose."""
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("EDSG_HOME", str(tmp_path / "home"))
    from edsg.gui.organizer import OrganizerWindow

    window = OrganizerWindow()
    try:
        assert not hasattr(window, "tie_box")
    finally:
        window.deleteLater()


# -- the report is self-contained --------------------------------------


def test_the_html_report_references_nothing_external(tmp_path):
    """It is mailed and uploaded, so it has to stand on its own."""
    import re

    from edsg.core.models import EventDefinition
    from edsg.core.settings import Appearance, Branding, Settings
    from edsg.core.standings import StandingsReport
    from edsg.reports.html_report import build_html
    from edsg.reports.style import ReportStyle

    logo = tmp_path / "logo.png"
    logo.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000a49444154789c63000100000500010d0a2db40000000049454e44ae"
            "426082"
        )
    )
    style = ReportStyle.from_settings(
        Settings(
            appearance=Appearance(theme="default"),
            branding=Branding(
                squadron_name="Empyrean Foundation",
                squadron_tag="EMPY",
                logo_path=str(logo),
            ),
        )
    )
    html = build_html(
        StandingsReport(
            event=EventDefinition(name="X"),
            standings=[],
            accepted=[],
            rejected=[],
        ),
        style,
    )

    assert "Empyrean Foundation [EMPY]" in html
    assert 'src="data:image/png;base64,' in html
    external = [
        url
        for url in re.findall(r'(?:src|href)="([^"]+)"', html)
        if not url.startswith(("data:", "#"))
    ]
    assert not external, f"references outside the file: {external}"


# -- a criterion can be reopened and saved ------------------------------


@pytest.mark.parametrize(
    ("cap", "minimum"),
    [
        (1_000_000, 1_000),
        (1_234_567, 25),
        (250_000, None),
        (1_000_000_000, 12_500_000),
        (200, 10),
    ],
)
def test_reopening_a_criterion_and_saving_keeps_its_numbers(qt_app, cap, minimum):
    """Grouping the displayed figure made the field unreadable to its own
    parser: reopening a criterion and saving it threw 'must be a number'.
    """
    from edsg.core.criteria import Criterion, Measure, MetricKind
    from edsg.gui.criterion_dialog import CriterionDialog

    original = Criterion(
        criterion_id="x",
        label="Test",
        kind=MetricKind.MINING_REFINED,
        measure=Measure.TONNAGE,
        points_per_unit=1.0,
        unit_cap=cap,
        minimum_units=minimum,
    )
    dialog = CriterionDialog(None, original)
    try:
        dialog._save()
        saved = dialog.result_criterion
        assert saved is not None, "saving a valid criterion was refused"
        assert saved.unit_cap == cap
        assert saved.minimum_units == minimum
    finally:
        dialog.deleteLater()


@pytest.mark.parametrize(
    ("typed", "expected"),
    [("1M", 1_000_000), ("2,500", 2_500), ("4.3K", 4_300), ("1B", 1e9)],
)
def test_a_cap_can_be_typed_in_any_readable_form(qt_app, typed, expected):
    from edsg.core.criteria import Criterion, Measure, MetricKind
    from edsg.gui.criterion_dialog import CriterionDialog

    dialog = CriterionDialog(
        None,
        Criterion(
            criterion_id="x",
            label="Test",
            kind=MetricKind.MINING_REFINED,
            measure=Measure.TONNAGE,
            points_per_unit=1.0,
            unit_cap=1,
        ),
    )
    try:
        dialog.cap_field.setText(typed)
        dialog._save()
        assert dialog.result_criterion is not None
        assert dialog.result_criterion.unit_cap == expected
    finally:
        dialog.deleteLater()


def test_the_reward_pool_reads_and_writes_short_forms(qt_app):
    from edsg.gui.widgets import ReadableSpinBox

    spin = ReadableSpinBox()
    try:
        spin.setDecimals(0)
        spin.setRange(0, 1_000_000_000_000)

        spin.setValue(1_000_000_000)
        assert spin.text() == "1B"
        # Not exact as a short form, so the full figure is shown instead
        # of quietly rounding what the organizer set.
        spin.setValue(1_234_567)
        assert spin.text() == "1,234,567"

        for typed, expected in (("1B", 1e9), ("250K", 250_000), ("1,000,000", 1e6)):
            spin.lineEdit().setText(typed)
            spin.interpretText()
            assert spin.value() == expected
    finally:
        spin.deleteLater()
