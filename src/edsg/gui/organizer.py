"""The event organizer application.

Four tabs following the shape of the job: define the event, set the
criteria, issue the invitation, then close and publish. Later tabs stay
visible but refuse to act until their prerequisites are met, which makes
the sequence discoverable without forcing a wizard on someone who is
editing an event they built last week.
"""

from __future__ import annotations

import contextlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QDate, QDateTime, Qt, QTime
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDateTimeEdit,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from edsg.core.canonical import pretty_text
from edsg.core.criteria import Criterion
from edsg.core.crypto import Identity, load_or_create_identity
from edsg.core.errors import EDSGError
from edsg.core.models import (
    INVITATION_SUFFIX,
    Eligibility,
    EventDefinition,
    EventState,
    EventWindow,
)

# The list column is narrow, so the short form is used where it is
# exact. Reports keep the full figure, where precision matters more
# than brevity.
from edsg.core.numbers import editable
from edsg.core.paths import (
    ROLE_ORGANIZER,
    EventPaths,
    event_paths,
    find_journal_dir,
    set_role,
)
from edsg.core.settings import load_settings, save_settings
from edsg.core.workflow import (
    close_event,
    detect_squadron_from_journals,
    issue_invitation,
    load_invitation,
    preview_standings,
    regenerate_standings,
)
from edsg.gui.about import SupportStrip
from edsg.gui.criterion_dialog import edit_criterion
from edsg.gui.menus import build_menus
from edsg.gui.preferences import edit_preferences
from edsg.gui.rewards_panel import RewardsPanel
from edsg.gui.theme import COLOURS, apply_theme
from edsg.gui.widgets import (
    InfoPane,
    LogPane,
    PathPicker,
    ask_confirm,
    button,
    label,
    open_path,
    primary_button,
    run_in_background,
    separator,
    show_error,
    show_info,
    show_warning,
    to_utc,
    wait_for_workers,
    window_title,
)
from edsg.reports import write_all
from edsg.reports.style import ReportStyle
from edsg.version import read_version

#: Extension for an organizer's editable working copy of an event.
DRAFT_SUFFIX = ".edsgevent"

#: Written into an event's workspace folder whenever the event changes,
#: so nothing is lost by closing the window.
AUTOSAVE_NAME = f"event{DRAFT_SUFFIX}"

ROLE = "Organizer"


class OrganizerWindow(QMainWindow):
    """Main window of the organizer build."""

    def __init__(self) -> None:
        super().__init__()
        self.event_def = EventDefinition(name="")
        self.identity: Identity | None = None
        self.invitation_fingerprint = ""
        self.report_dir: Path | None = None
        self.busy = False
        self.settings = load_settings()
        self.workspace: EventPaths | None = None
        self._autosaved_to: Path | None = None

        # A remembered squadron and organizer name are offered as the
        # defaults, so a squadron running events regularly configures
        # them once.
        remembered = self.settings.organizer.squadron_ref()
        if remembered is not None:
            self.event_def.squadron = remembered

        self.setWindowTitle(window_title(ROLE))
        self.resize(1120, 860)
        self.setMinimumSize(960, 720)

        self._build_menu()
        self._build()
        self._load_identity()
        self._refresh()

    # -- construction ---------------------------------------------------

    def _build_menu(self) -> None:
        new_action = QAction("&New event", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._new_event)

        open_action = QAction("&Open event draft\u2026", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_draft)

        save_action = QAction("&Save event draft\u2026", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_draft)

        build_menus(
            self,
            ROLE,
            file_actions=[new_action, open_action, save_action],
            on_preferences=self._edit_preferences,
        )

    def _edit_preferences(self) -> None:
        """Open preferences and adopt whatever comes back."""
        updated = edit_preferences(self, self.settings)
        if updated is not None:
            self.settings = updated
            self.log.write("Preferences saved.", "good")
        self.apply_palette(self.settings.appearance.palette())

    def apply_palette(self, palette) -> None:
        """Re-theme the running application.

        Called live from the preferences dialog as colours change, so the
        organizer can see a theme before committing to it.
        """
        application = QApplication.instance()
        if application is not None:
            apply_theme(application, palette)
        self._refresh()

    def _build(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title_box.addWidget(label("ED: SQUAD GOALS", "title"))
        title_box.addWidget(label(f"Organizer build {read_version()}", "subtitle"))
        header.addLayout(title_box)
        header.addStretch(1)
        header_right = QVBoxLayout()
        header_right.setSpacing(2)
        header_right.addWidget(SupportStrip(compact=True), 0, Qt.AlignRight)
        self.state_label = label("", "hint")
        self.state_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header_right.addWidget(self.state_label)
        header.addLayout(header_right)
        layout.addLayout(header)
        layout.addWidget(separator())

        self.next_step_label = label("", "hint", wrap=True)
        layout.addWidget(self.next_step_label)

        splitter = QSplitter(Qt.Vertical)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._event_tab(), "1 \u00b7 Event")
        self.tabs.addTab(self._criteria_tab(), "2 \u00b7 Criteria")
        self.rewards_panel = RewardsPanel()
        self.tabs.addTab(self.rewards_panel, "3 \u00b7 Rewards")
        self.tabs.addTab(self._issue_tab(), "4 \u00b7 Issue invitation")
        self.tabs.addTab(self._close_tab(), "4 \u00b7 Close && publish")
        splitter.addWidget(self.tabs)

        nav = QHBoxLayout()
        self.back_button = button("\u2039  Back")
        self.back_button.clicked.connect(lambda: self._step(-1))
        self.next_button = button("Next  \u203a")
        self.next_button.clicked.connect(lambda: self._step(1))
        nav.addStretch(1)
        nav.addWidget(self.back_button)
        nav.addWidget(self.next_button)
        layout.addLayout(nav)

        self.log = LogPane(rows=6)
        splitter.addWidget(self.log)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([640, 170])
        layout.addWidget(splitter, 1)

        self.statusBar().showMessage("Ready")
        self.log.write(f"EDSG organizer {read_version()} started.", "accent")

    def _set_period(self, start: QDateTime, end: QDateTime) -> None:
        """Apply a period, enabling both bounds."""
        self.start_enabled.setChecked(True)
        self.end_enabled.setChecked(True)
        self.start_edit.setDateTime(start)
        self.end_edit.setDateTime(end)
        self._refresh_readiness()

    def _period_whole_day(self) -> None:
        day = self.start_edit.date()
        self._set_period(
            QDateTime(day, QTime(0, 0, 0)), QDateTime(day, QTime(23, 59, 59))
        )

    def _period_this_month(self) -> None:
        day = self.start_edit.date()
        first = QDate(day.year(), day.month(), 1)
        last = QDate(day.year(), day.month(), first.daysInMonth())
        self._set_period(
            QDateTime(first, QTime(0, 0, 0)), QDateTime(last, QTime(23, 59, 59))
        )

    def _period_this_year(self) -> None:
        year = self.start_edit.date().year()
        self._set_period(
            QDateTime(QDate(year, 1, 1), QTime(0, 0, 0)),
            QDateTime(QDate(year, 12, 31), QTime(23, 59, 59)),
        )

    def _event_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        details = QGroupBox("Event details")
        form = QFormLayout(details)
        form.setSpacing(8)
        self.name_field = QLineEdit()
        self.name_field.setPlaceholderText("e.g. Summer Mining Drive 3311")
        self.name_field.textChanged.connect(self._refresh_readiness)
        form.addRow("Event name", self.name_field)

        self.organizer_field = QLineEdit()
        self.organizer_field.setPlaceholderText("e.g. CMDR Jameson")
        form.addRow("Organizer", self.organizer_field)

        self.description_field = QPlainTextEdit()
        self.description_field.setPlaceholderText(
            "Shown to participants when they open the invitation."
        )
        self.description_field.setMinimumHeight(64)
        self.description_field.setMaximumHeight(80)
        form.addRow("Description", self.description_field)
        layout.addWidget(details)

        period = QGroupBox("Period")
        period_layout = QVBoxLayout(period)
        row = QHBoxLayout()
        row.setSpacing(10)

        # Defaults snap to day boundaries. Using "now" gave an arbitrary
        # time of day, so an event meant to cover a whole first day
        # silently excluded everything before the moment it was created.
        today = QDate.currentDate()
        start_default = QDateTime(today, QTime(0, 0, 0))
        end_default = QDateTime(today.addDays(14), QTime(23, 59, 59))

        self.start_enabled = QCheckBox("Starts")
        self.start_enabled.setChecked(True)
        self.start_edit = QDateTimeEdit(start_default)
        # Seconds are displayed because they are stored: showing HH:mm
        # while keeping :36 underneath meant the window was not what the
        # organizer was shown.
        self.start_edit.setDisplayFormat("yyyy-MM-dd  HH:mm:ss")
        self.start_edit.setCalendarPopup(True)
        self.start_edit.setToolTip(
            "Click the date or time you want to change, then type or use "
            "the arrow keys. Times are UTC."
        )

        self.end_enabled = QCheckBox("Ends")
        self.end_enabled.setChecked(True)
        self.end_edit = QDateTimeEdit(end_default)
        self.end_edit.setDisplayFormat("yyyy-MM-dd  HH:mm:ss")
        self.end_edit.setCalendarPopup(True)
        self.end_edit.setToolTip(self.start_edit.toolTip())

        for check, edit in (
            (self.start_enabled, self.start_edit),
            (self.end_enabled, self.end_edit),
        ):
            check.toggled.connect(edit.setEnabled)
            check.toggled.connect(self._refresh_readiness)
            edit.dateTimeChanged.connect(self._refresh_readiness)
            row.addWidget(check)
            row.addWidget(edit)
            row.addSpacing(20)
        row.addStretch(1)
        period_layout.addLayout(row)
        shortcuts = QHBoxLayout()
        shortcuts.setSpacing(6)
        shortcuts.addWidget(label("Quick set", "hint"))
        for text, tip, handler in (
            (
                "Whole day",
                "00:00:00 to 23:59:59 on the start date",
                self._period_whole_day,
            ),
            (
                "This month",
                "First to last day of the start month",
                self._period_this_month,
            ),
            (
                "This year",
                "1 January to 31 December of the start year",
                self._period_this_year,
            ),
        ):
            widget = button(text)
            widget.setToolTip(tip)
            widget.clicked.connect(handler)
            shortcuts.addWidget(widget)
        shortcuts.addStretch(1)
        period_layout.addLayout(shortcuts)

        period_layout.addWidget(
            label(
                "Times are UTC, matching the journals. Click the hour or "
                "minute to edit it, or use a quick-set button. Untick a "
                "bound to leave that end of the window open.",
                "hint",
                wrap=True,
            )
        )
        layout.addWidget(period)

        eligibility = QGroupBox("Your squadron")
        elig_layout = QVBoxLayout(eligibility)

        squad_row = QHBoxLayout()
        self.squadron_label = label("No squadron detected.", "hint")
        self.detect_button = button("Detect from my journals\u2026")
        self.detect_button.setToolTip(
            "Read your own journals to identify your squadron. You never "
            "have to type an ID."
        )
        self.detect_button.clicked.connect(self._detect_squadron)
        squad_row.addWidget(self.squadron_label, 1)
        squad_row.addWidget(self.detect_button)
        elig_layout.addLayout(squad_row)
        elig_layout.addWidget(
            label(
                "Every event is limited to your own squadron. Elite has no "
                "way to hand credits to a commander outside it \u2014 a "
                "fleet carrier market loses a slice to fees and to the void, "
                "while the squadron bank pays directly \u2014 so an open "
                "event could not pay its winners.\n\n"
                "Participants must show a join event for this squadron with "
                "no later leave, kick or disband.",
                "hint",
                wrap=True,
            )
        )
        layout.addWidget(eligibility)

        # No tie-break control: commanders on equal points now share a
        # rank and are paid alike, so there is nothing left to break.
        layout.addStretch(1)
        return tab

    def _criteria_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)
        layout.addWidget(
            label(
                "Each criterion measures one thing and converts it into "
                "points. Add as many as the event needs \u2014 double-click "
                "a row to edit it.",
                "hint",
                wrap=True,
            )
        )

        self.criteria_tree = QTreeWidget()
        self.criteria_tree.setColumnCount(5)
        self.criteria_tree.setHeaderLabels(
            ["Criterion", "Metric", "Measure", "Scoring", "Restrictions"]
        )
        self.criteria_tree.setRootIsDecorated(False)
        self.criteria_tree.setAlternatingRowColors(True)
        self.criteria_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.criteria_tree.itemDoubleClicked.connect(lambda *_: self._edit_criterion())
        header = self.criteria_tree.header()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        self.criteria_tree.setColumnWidth(0, 190)
        self.criteria_tree.setColumnWidth(1, 170)
        self.criteria_tree.setColumnWidth(2, 150)
        self.criteria_tree.setColumnWidth(3, 150)
        layout.addWidget(self.criteria_tree, 1)

        row = QHBoxLayout()
        row.setSpacing(6)
        add = primary_button("Add criterion\u2026")
        add.clicked.connect(self._add_criterion)
        row.addWidget(add)
        for text, slot in (
            ("Edit\u2026", self._edit_criterion),
            ("Duplicate", self._duplicate_criterion),
        ):
            widget = button(text)
            widget.clicked.connect(slot)
            row.addWidget(widget)
        remove = button("Remove", "danger")
        remove.clicked.connect(self._remove_criterion)
        row.addWidget(remove)
        row.addStretch(1)
        up = button("Move up")
        up.clicked.connect(lambda: self._move(-1))
        down = button("Move down")
        down.clicked.connect(lambda: self._move(1))
        row.addWidget(up)
        row.addWidget(down)
        layout.addLayout(row)
        return tab

    def _issue_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        identity_group = QGroupBox("Your signing identity")
        identity_layout = QVBoxLayout(identity_group)

        fingerprint_row = QHBoxLayout()
        self.fingerprint_label = label("\u2014", "fingerprint")
        fingerprint_row.addWidget(self.fingerprint_label)
        self.copy_fingerprint_button = button("Copy")
        self.copy_fingerprint_button.setToolTip("Copy the fingerprint to the clipboard")
        self.copy_fingerprint_button.clicked.connect(self._copy_fingerprint)
        fingerprint_row.addWidget(self.copy_fingerprint_button)
        fingerprint_row.addStretch(1)
        identity_layout.addLayout(fingerprint_row)

        identity_layout.addWidget(
            label(
                "Publish this fingerprint somewhere your participants "
                "already trust \u2014 your squadron Discord, for instance. "
                "It is how they confirm an invitation really came from you. "
                "EDSG cannot do that for them.",
                "hint",
                wrap=True,
            )
        )
        identity_layout.addWidget(
            label(
                "It is a SHA-256 fingerprint of the Ed25519 public key EDSG "
                "generated for you on first run, held in your settings "
                "folder. The same key signs every invitation you issue, so "
                "the fingerprint stays the same until you delete it.",
                "hint",
                wrap=True,
            )
        )
        layout.addWidget(identity_group)

        readiness = QGroupBox("Readiness")
        readiness_layout = QVBoxLayout(readiness)
        self.readiness_pane = InfoPane(rows=10)
        readiness_layout.addWidget(self.readiness_pane)
        layout.addWidget(readiness, 1)

        row = QHBoxLayout()
        self.issue_button = primary_button("Issue invitation\u2026")
        self.issue_button.setToolTip(
            "Freeze the event, sign it, and write the .edsgi to send to participants"
        )
        self.issue_button.clicked.connect(self._issue)
        row.addWidget(self.issue_button)
        self.issued_label = label("", "hint")
        row.addWidget(self.issued_label, 1)
        layout.addLayout(row)
        return tab

    def _close_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        submissions = QGroupBox("Participant submissions")
        sub_layout = QVBoxLayout(submissions)
        self.submissions_picker = PathPicker("Folder holding the .edsgs files")
        self.submissions_picker.button.clicked.connect(self._pick_submissions)
        sub_layout.addWidget(self.submissions_picker)
        sub_layout.addWidget(
            label(
                "Put every .edsgs file you received into one folder, and keep "
                "that folder. It is the only way to regenerate the reports "
                "once the event is closed.",
                "hint",
                wrap=True,
            )
        )
        layout.addWidget(submissions)

        invitation = QGroupBox("Invitation used for this event (recommended)")
        inv_layout = QVBoxLayout(invitation)
        self.invitation_picker = PathPicker("The .edsgi file you issued")
        self.invitation_picker.button.clicked.connect(self._pick_invitation)
        inv_layout.addWidget(self.invitation_picker)
        inv_layout.addWidget(
            label(
                "Loading it lets EDSG reject submissions built from a "
                "different or forged invitation, and restores the event "
                "definition if you are closing from a fresh install.",
                "hint",
                wrap=True,
            )
        )
        layout.addWidget(invitation)

        results = QGroupBox("Standings")
        results_layout = QVBoxLayout(results)

        status_row = QHBoxLayout()
        self.standings_status = label(
            "Choose a submissions folder to preview the standings.", "hint"
        )
        self.refresh_preview_button = button("Refresh preview")
        self.refresh_preview_button.setToolTip(
            "Score the submissions folder again without closing the event"
        )
        self.refresh_preview_button.clicked.connect(self._preview_standings)
        status_row.addWidget(self.standings_status, 1)
        status_row.addWidget(self.refresh_preview_button)
        results_layout.addLayout(status_row)

        self.standings_tree = QTreeWidget()
        self.standings_tree.setColumnCount(4)
        self.standings_tree.setHeaderLabels(
            ["Rank", "Commander", "Frontier ID", "Points"]
        )
        self.standings_tree.setRootIsDecorated(False)
        self.standings_tree.setAlternatingRowColors(True)
        # Commander takes the slack. Leaving Points as the stretched last
        # column pushed its right-aligned value hundreds of pixels from
        # its own header, so the column read as empty.
        header = self.standings_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.standings_tree.setColumnWidth(0, 70)
        self.standings_tree.setColumnWidth(2, 140)
        self.standings_tree.setColumnWidth(3, 130)
        results_layout.addWidget(self.standings_tree)
        layout.addWidget(results, 1)

        row = QHBoxLayout()
        self.close_button = primary_button("Close event && publish\u2026")
        self.close_button.setToolTip(
            "Rank the submissions and publish the reports. This cannot be undone."
        )
        self.close_button.clicked.connect(self._close_event)
        self.regen_button = button("Regenerate reports\u2026")
        self.regen_button.setToolTip(
            "Rebuild the reports of a closed event from its submissions folder"
        )
        self.regen_button.clicked.connect(self._regenerate)
        self.open_reports_button = button("Open report folder")
        self.open_reports_button.setToolTip(
            "Open the folder the standings were written to"
        )
        self.open_reports_button.clicked.connect(self._open_reports)
        row.addWidget(self.close_button)
        row.addWidget(self.regen_button)
        row.addWidget(self.open_reports_button)
        row.addStretch(1)
        layout.addLayout(row)
        return tab

    # -- identity -------------------------------------------------------

    def _load_identity(self) -> None:
        try:
            self.identity = load_or_create_identity("organizer", "EDSG event organizer")
        except EDSGError as exc:
            show_error(self, "Signing identity", exc)
            self.log.write(f"Could not load a signing identity: {exc}", "bad")
            return
        self.fingerprint_label.setText(self.identity.fingerprint)
        self.log.write(
            f"Signing identity ready \u2014 {self.identity.fingerprint}", "good"
        )

    # -- form <-> model --------------------------------------------------

    def _autosave(self) -> None:
        """Write the working event into its own workspace folder.

        The event used to live only in memory until the organizer chose
        File > Save event draft, so closing the window lost the work.
        Saving on every meaningful change means an event is always
        recoverable, and File > Open event draft finds it where the rest
        of the event's files already are.
        """
        if not self.event_def.name.strip():
            return
        try:
            workspace = event_paths(self.event_def.name)
            workspace.root.mkdir(parents=True, exist_ok=True)
            target = workspace.root / AUTOSAVE_NAME
            target.write_text(
                pretty_text(self.event_def.to_dict()) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            # Autosave failing must never interrupt what the organizer
            # is doing; the manual draft save reports its own errors.
            self.log.write(f"Could not autosave the event: {exc}", "warn")
            return
        self._autosaved_to = target

    def _step(self, offset: int) -> None:
        """Move between tabs with the Back and Next buttons."""
        target = self.tabs.currentIndex() + offset
        if 0 <= target < self.tabs.count():
            self.tabs.setCurrentIndex(target)

    def _copy_fingerprint(self) -> None:
        """Put the signing fingerprint on the clipboard."""
        if self.identity is None:
            return
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return
        clipboard.setText(self.identity.fingerprint)
        self.statusBar().showMessage("Fingerprint copied to the clipboard", 4000)
        self.log.write("Fingerprint copied to the clipboard.", "muted")

    def _collect(self) -> None:
        if hasattr(self, "rewards_panel"):
            self.event_def.tiers = self.rewards_panel.collect()
        self.event_def.name = self.name_field.text().strip()
        self.event_def.organizer_name = self.organizer_field.text().strip()
        self.event_def.description = self.description_field.toPlainText().strip()
        self.event_def.window = EventWindow(
            start=(
                to_utc(self.start_edit.dateTime().toPython())
                if self.start_enabled.isChecked()
                else None
            ),
            end=(
                to_utc(self.end_edit.dateTime().toPython())
                if self.end_enabled.isChecked()
                else None
            ),
        )
        # Always squadron-locked; there is no longer an open option.
        self.event_def.eligibility = Eligibility.SQUADRON
        # Qt hands back a plain str for StrEnum user data; convert it.

    def _populate(self) -> None:
        if hasattr(self, "rewards_panel"):
            self.rewards_panel.load(
                self.event_def.tiers, self.event_def.point_ceiling()
            )
        self.name_field.setText(self.event_def.name)
        self.organizer_field.setText(self.event_def.organizer_name)
        self.description_field.setPlainText(self.event_def.description)

        window = self.event_def.window
        # Built from the naive UTC components rather than an epoch, which
        # avoids the deprecated Qt.TimeSpec overload and keeps the widget
        # showing exactly the UTC time that is stored.
        self.start_enabled.setChecked(window.start is not None)
        if window.start:
            self.start_edit.setDateTime(_to_qt(window.start))
        self.end_enabled.setChecked(window.end is not None)
        if window.end:
            self.end_edit.setDateTime(_to_qt(window.end))

        self._refresh()

    # -- refresh ---------------------------------------------------------

    #: What each state means and what the organizer does next.
    STATE_GUIDANCE = {
        EventState.DRAFT: (
            "DRAFT \u2014 still being written. Nothing has been sent out.",
            "Next: finish the criteria, then issue the invitation on tab 3.",
        ),
        EventState.OPEN: (
            "OPEN \u2014 invitation issued, awaiting submissions.",
            "Next: collect the .edsgs files participants send you into the "
            "event's submissions folder, then close the event on tab 4.",
        ),
        EventState.CLOSED: (
            "CLOSED \u2014 standings published. This cannot be undone.",
            "Reports can still be regenerated from the submissions folder.",
        ),
    }

    def _refresh_navigation(self) -> None:
        """Enable Back and Next according to the tab in view."""
        index = self.tabs.currentIndex()
        self.back_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < self.tabs.count() - 1)

    def _refresh(self) -> None:
        self._refresh_navigation()
        if hasattr(self, "rewards_panel"):
            self.rewards_panel.set_ceiling(self.event_def.point_ceiling())
        state, guidance = self.STATE_GUIDANCE[self.event_def.state]
        self.state_label.setText(state)
        self.next_step_label.setText(guidance)

        if self.event_def.squadron:
            self.squadron_label.setText(f"Squadron: {self.event_def.squadron}")
            self.squadron_label.setProperty("role", "good")
        else:
            self.squadron_label.setText("No squadron detected.")
            self.squadron_label.setProperty("role", "hint")
        self.squadron_label.style().unpolish(self.squadron_label)
        self.squadron_label.style().polish(self.squadron_label)
        self.detect_button.setEnabled(not self.busy)

        self.criteria_tree.clear()
        for criterion in self.event_def.criteria:
            scoring = f"{editable(criterion.points_per_unit)} pt/unit"
            if criterion.unit_cap is not None:
                scoring += f" \u00b7 cap {editable(criterion.unit_cap)}"
            if criterion.minimum_units is not None:
                scoring += f" \u00b7 min {editable(criterion.minimum_units)}"
            item = QTreeWidgetItem(
                [
                    criterion.label,
                    criterion.kind.label,
                    criterion.measure.label,
                    scoring,
                    "; ".join(criterion.filters.describe()) or "no restrictions",
                ]
            )
            item.setData(0, Qt.UserRole, criterion.criterion_id)
            if not criterion.filters.describe():
                item.setForeground(4, QColor(COLOURS["text_faint"]))
            self.criteria_tree.addTopLevelItem(item)

        self._refresh_readiness()

        closed = self.event_def.state is EventState.CLOSED
        draft = self.event_def.state is EventState.DRAFT
        self.issue_button.setEnabled(not closed and not self.busy)
        self.close_button.setEnabled(not closed and not draft and not self.busy)
        self.regen_button.setEnabled(closed and not self.busy)
        self.open_reports_button.setEnabled(self.report_dir is not None)

    def _refresh_readiness(self) -> None:
        self._collect()
        problems = self.event_def.validate()
        if problems:
            rows = "".join(
                f'<tr><td class="bad">\u2717</td><td>{item}</td></tr>'
                for item in problems
            )
            html = f"<h3>Not ready to issue</h3><table cellspacing=4>{rows}</table>"
        else:
            facts = [
                ("Event", self.event_def.name),
                ("Period", self.event_def.window.describe()),
                (
                    "Eligibility",
                    str(self.event_def.squadron)
                    if self.event_def.eligibility is Eligibility.SQUADRON
                    else "Open to all commanders",
                ),
                ("Criteria", str(len(self.event_def.criteria))),
                (
                    "Goal",
                    f"{self.event_def.point_ceiling():,.0f} points across "
                    f"{self.event_def.tiers.tier_count} tier(s), "
                    f"{self.event_def.tiers.reward_pool:,.0f} "
                    f"{self.event_def.tiers.currency} pool"
                    if self.event_def.tiers.enabled
                    else "no rewards \u2014 plain leaderboard",
                ),
            ]
            rows = "".join(
                f'<tr><td class="good">\u2713</td>'
                f'<td class="k">{key}</td><td class="v">{value}</td></tr>'
                for key, value in facts
            )
            html = f"<h3>Ready to issue</h3><table cellspacing=4>{rows}</table>"
        self.readiness_pane.setHtml(html)

    # -- criteria --------------------------------------------------------

    def _selected(self) -> Criterion | None:
        items = self.criteria_tree.selectedItems()
        if not items:
            return None
        return self.event_def.criterion_by_id(items[0].data(0, Qt.UserRole))

    def _add_criterion(self) -> None:
        criterion = edit_criterion(self)
        if criterion is None:
            return
        self.event_def.criteria.append(criterion)
        self.log.write(f"Added criterion '{criterion.label}'.", "good")
        self._autosave()
        self._refresh()

    def _edit_criterion(self) -> None:
        current = self._selected()
        if current is None:
            show_info(self, "Nothing selected", "Select a criterion to edit.")
            return
        updated = edit_criterion(self, current)
        if updated is None:
            return
        self.event_def.criteria[self.event_def.criteria.index(current)] = updated
        self.log.write(f"Updated criterion '{updated.label}'.", "good")
        self._autosave()
        self._refresh()

    def _duplicate_criterion(self) -> None:
        current = self._selected()
        if current is None:
            return
        clone = Criterion.from_dict(current.to_dict())
        clone.criterion_id = Criterion(
            label="", kind=clone.kind, measure=clone.measure
        ).criterion_id
        clone.label = f"{current.label} (copy)"
        self.event_def.criteria.append(clone)
        self._refresh()

    def _remove_criterion(self) -> None:
        current = self._selected()
        if current is None:
            return
        if not ask_confirm(
            self,
            "Remove criterion",
            f"Remove '{current.label}'?",
            confirm_text="Remove",
            dangerous=True,
        ):
            return
        self.event_def.criteria.remove(current)
        self.log.write(f"Removed criterion '{current.label}'.", "warn")
        self._autosave()
        self._refresh()

    def _move(self, offset: int) -> None:
        current = self._selected()
        if current is None:
            return
        index = self.event_def.criteria.index(current)
        target = index + offset
        if not 0 <= target < len(self.event_def.criteria):
            return
        items = self.event_def.criteria
        items[index], items[target] = items[target], items[index]
        self._refresh()
        self.criteria_tree.setCurrentItem(self.criteria_tree.topLevelItem(target))

    # -- squadron --------------------------------------------------------

    def _detect_squadron(self) -> None:
        initial = find_journal_dir()
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select YOUR Elite Dangerous journal folder",
            str(initial) if initial else "",
        )
        if not directory:
            return

        self._set_busy(True, "Scanning your journals for squadron membership\u2026")

        def work(_report):
            return detect_squadron_from_journals(Path(directory))

        def finished(squadron) -> None:
            self._set_busy(False)
            if squadron is None:
                self.log.write("No current squadron membership found.", "warn")
                show_warning(
                    self,
                    "No squadron found",
                    "Those journals show no squadron you are currently in.\n\n"
                    "Log in to the game while in your squadron so a "
                    "SquadronStartup event is written, then try again.",
                )
                return
            self.event_def.squadron = squadron

            # Remembered so the next event does not need detecting again.
            self.settings.organizer.remember_squadron(squadron)
            try:
                save_settings(self.settings)
            except OSError as exc:
                self.log.write(f"Could not save the squadron: {exc}", "warn")
            else:
                self.log.write(
                    f"Detected squadron {squadron} — remembered for future events.",
                    "good",
                )
            self._refresh()

        def failed(exc: BaseException) -> None:
            self._set_busy(False)
            self.log.write(f"Squadron scan failed: {exc}", "bad")
            show_error(self, "Could not scan those journals", exc)

        run_in_background(work, finished, failed)

    # -- issuing ---------------------------------------------------------

    def _issue(self) -> None:
        self._collect()
        if self.identity is None:
            show_error(self, "No identity", "No signing identity is available.")
            return
        problems = self.event_def.validate()
        if problems:
            show_error(self, "Not ready to issue", problems[0], "\n".join(problems[1:]))
            return

        # Every event gets a workspace beside the binary:
        #   Events/<Event Name>/{invitation,submissions,standings}
        # The three folders are created together so the organizer never
        # has to invent a place to put received submissions.
        try:
            workspace = event_paths(self.event_def.name).create()
        except OSError as exc:
            show_error(self, "Could not create the event folder", exc)
            return

        suggested = str(
            workspace.invitation
            / f"{_safe_stem(self.event_def.name)}{INVITATION_SUFFIX}"
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save invitation",
            suggested,
            f"EDSG invitation (*{INVITATION_SUFFIX})",
        )
        if not path:
            return

        try:
            written = issue_invitation(self.event_def, self.identity, Path(path))
        except EDSGError as exc:
            self.log.write(f"Issue failed: {exc}", "bad")
            show_error(self, "Could not issue the invitation", exc)
            return

        # The organizer's own name rarely changes between events either.
        if self.event_def.organizer_name != self.settings.organizer.organizer_name:
            self.settings.organizer.organizer_name = self.event_def.organizer_name
            with contextlib.suppress(OSError):
                save_settings(self.settings)

        self.invitation_fingerprint = self.identity.fingerprint
        self.invitation_picker.set_path(written)
        self.issued_label.setText(f"Issued: {written.name}")
        self.workspace = workspace
        self._autosave()

        # Point the close tab at the folders just created, so collecting
        # submissions and publishing need no further navigation.
        self.submissions_picker.set_path(workspace.submissions)
        self.report_dir = workspace.standings

        self.log.write(f"Invitation issued to {written}", "good")
        self.log.write(f"Event workspace: {workspace.root}", "muted")
        self._refresh()
        show_info(
            self,
            "Invitation issued",
            f"Saved to {written}",
            f"Send this file to your participants, together with your "
            f"fingerprint so they can confirm it came from you:\n\n"
            f"{self.identity.fingerprint}\n\n"
            f"Put the submissions you receive into:\n"
            f"{workspace.submissions}\n\n"
            f"Standings will be written to:\n{workspace.standings}",
        )

    # -- closing ---------------------------------------------------------

    def _pick_submissions(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Folder holding the .edsgs files"
        )
        if directory:
            self.submissions_picker.set_path(directory)
            self._preview_standings()

    def _pick_invitation(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open the invitation for this event",
            "",
            f"EDSG invitation (*{INVITATION_SUFFIX})",
        )
        if not path:
            return
        try:
            invitation = load_invitation(Path(path))
        except EDSGError as exc:
            show_error(self, "Could not read that invitation", exc)
            return
        self.invitation_picker.set_path(path)
        self.invitation_fingerprint = invitation.signer_fingerprint
        if invitation.event.event_id != self.event_def.event_id:
            self.event_def = invitation.event
            self._populate()
            self.log.write(
                "Loaded the event definition from that invitation.", "accent"
            )
        self.log.write(
            f"Invitation verified, signed by {invitation.signer_fingerprint}.",
            "good",
        )
        self._refresh()
        if self.submissions_picker.path() is not None:
            self._preview_standings()

    def _submissions_dir(self) -> Path | None:
        directory = self.submissions_picker.path()
        if directory is None:
            show_warning(
                self,
                "No submissions folder",
                "Choose the folder holding the participant .edsgs files.",
            )
            return None
        if not directory.is_dir():
            show_error(self, "Not a folder", f"{directory} is not a folder.")
            return None
        return directory

    def _close_event(self) -> None:
        directory = self._submissions_dir()
        if directory is None:
            return
        if not ask_confirm(
            self,
            "Close this event?",
            "Closing is permanent.",
            "The event cannot be reopened and no further invitations can be "
            "issued.\n\nReports can be regenerated later, as long as you keep "
            "the submissions folder.",
            confirm_text="Close event",
            dangerous=True,
        ):
            return
        self._run_close(directory, regenerate=False)

    def _regenerate(self) -> None:
        directory = self._submissions_dir()
        if directory is not None:
            self._run_close(directory, regenerate=True)

    def _run_close(self, directory: Path, regenerate: bool) -> None:
        target = QFileDialog.getExistingDirectory(self, "Where should the reports go?")
        if not target:
            return
        report_dir = Path(target)
        fingerprint = self.invitation_fingerprint
        event = self.event_def
        style = ReportStyle.from_settings(self.settings)

        self._set_busy(True, "Reading submissions\u2026")
        self.log.write(f"Reading submissions from {directory}\u2026")

        def work(_report):
            runner = regenerate_standings if regenerate else close_event
            report = runner(event, directory, fingerprint)
            written = write_all(report, report_dir, _safe_stem(event.name), style)
            return report, written

        def finished(payload) -> None:
            self._set_busy(False)
            report, written = payload
            self.report_dir = report_dir

            self._populate_standings(report, preview=False)

            verb = "Regenerated" if regenerate else "Closed"
            self.log.write(
                f"{verb} \u2014 {report.participant_count} ranked, "
                f"{len(report.rejected)} rejected.",
                "good",
            )
            for item in report.rejected:
                self.log.write(f"Rejected {item.path.name}: {item.rejection}", "warn")
            for path in written:
                self.log.write(f"Wrote {path.name}", "muted")
            self._refresh()
            show_info(
                self,
                "Reports written",
                f"{report.participant_count} commander(s) ranked, "
                f"{len(report.rejected)} submission(s) rejected.",
                f"Saved to {report_dir}",
            )
            # Opened after the dialog is dismissed, so the file manager
            # does not appear behind it.
            open_path(report_dir)

        def failed(exc: BaseException) -> None:
            self._set_busy(False)
            self.log.write(f"Close failed: {exc}", "bad")
            show_error(self, "Could not close the event", exc)

        run_in_background(work, finished, failed)

    def _populate_standings(self, report, preview: bool) -> None:
        """Fill the standings table from a report."""
        self.standings_tree.clear()
        for standing in report.standings:
            item = QTreeWidgetItem(
                [
                    f"{standing.rank}{' =' if standing.tied else ''}",
                    f"CMDR {standing.commander_name}",
                    standing.commander_fid,
                    f"{standing.total_points:,.2f}",
                ]
            )
            item.setTextAlignment(0, Qt.AlignCenter)
            item.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)
            if standing.rank == 1:
                item.setForeground(1, QColor(COLOURS["accent"]))
            self.standings_tree.addTopLevelItem(item)

        ranked = report.participant_count
        rejected = len(report.rejected)
        if preview:
            text = (
                f"Preview \u2014 {ranked} ranked, {rejected} would be "
                f"rejected. The event is not closed and nothing has been "
                f"written."
            )
            role = "warn" if rejected else "hint"
        else:
            text = f"Final \u2014 {ranked} ranked, {rejected} rejected."
            role = "good"
        self.standings_status.setText(text)
        self.standings_status.setProperty("role", role)
        self.standings_status.style().unpolish(self.standings_status)
        self.standings_status.style().polish(self.standings_status)

    def _preview_standings(self) -> None:
        """Score the submissions folder without closing anything.

        Runs on every folder selection so an organizer can see the
        standings, and any submission that will be rejected, before
        committing to the one irreversible action in the application.
        """
        directory = self.submissions_picker.path()
        if directory is None or not directory.is_dir() or self.busy:
            return

        self._collect()
        if not self.event_def.criteria:
            self.standings_status.setText(
                "Load the invitation for this event to preview the standings."
            )
            return

        event = self.event_def
        fingerprint = self.invitation_fingerprint
        self.refresh_preview_button.setEnabled(False)
        self.standings_status.setText("Reading submissions\u2026")

        def work(_report):
            return preview_standings(event, directory, fingerprint)

        def finished(report) -> None:
            self.refresh_preview_button.setEnabled(True)
            self._populate_standings(report, preview=True)
            self.log.write(
                f"Preview: {report.participant_count} ranked, "
                f"{len(report.rejected)} would be rejected.",
                "accent",
            )
            for item in report.rejected:
                self.log.write(
                    f"Would reject {item.path.name}: {item.rejection}", "warn"
                )

        def failed(exc: BaseException) -> None:
            self.refresh_preview_button.setEnabled(True)
            self.standings_tree.clear()
            self.standings_status.setText(str(exc))
            self.log.write(f"Preview failed: {exc}", "warn")

        run_in_background(work, finished, failed)

    def _open_reports(self) -> None:
        if self.report_dir:
            open_path(self.report_dir)

    # -- drafts ----------------------------------------------------------

    def _new_event(self) -> None:
        if not ask_confirm(
            self,
            "New event",
            "Discard the current event and start a new one?",
            confirm_text="Discard",
            dangerous=True,
        ):
            return
        self.event_def = EventDefinition(
            name="",
            organizer_name=self.settings.organizer.organizer_name,
            squadron=self.settings.organizer.squadron_ref(),
        )
        self.invitation_fingerprint = ""
        self.report_dir = None
        self.workspace = None
        self.invitation_picker.clear()
        self.submissions_picker.clear()
        self.standings_tree.clear()
        self._populate()
        self.log.write("Started a new event.", "accent")

    def _save_draft(self) -> None:
        self._collect()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save event draft",
            f"{_safe_stem(self.event_def.name)}{DRAFT_SUFFIX}",
            f"EDSG event draft (*{DRAFT_SUFFIX})",
        )
        if not path:
            return
        try:
            Path(path).write_text(
                pretty_text(self.event_def.to_dict()) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            show_error(self, "Could not save", exc)
            return
        self.log.write(f"Draft saved to {path}", "good")

    def _open_draft(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open event draft", "", f"EDSG event draft (*{DRAFT_SUFFIX})"
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self.event_def = EventDefinition.from_dict(data)
        except (OSError, json.JSONDecodeError, EDSGError) as exc:
            show_error(self, "Could not open that draft", exc)
            return
        self._populate()
        self.log.write(f"Loaded draft {Path(path).name}", "good")

    # -- helpers ---------------------------------------------------------

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self.busy = busy
        self.statusBar().showMessage(message or "Ready")
        QApplication.setOverrideCursor(Qt.WaitCursor) if busy else (
            QApplication.restoreOverrideCursor()
        )
        self.tabs.setEnabled(not busy)
        self._refresh()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        """Drain background work before the interpreter shuts down.

        A pool thread still inside Python when the process exits is a
        crash on close, and a scan can run for several seconds.
        """
        wait_for_workers()
        super().closeEvent(event)


def _to_qt(moment: datetime) -> QDateTime:
    """Return a QDateTime showing ``moment`` as its UTC wall time."""
    utc = moment.astimezone(UTC)
    return QDateTime(
        QDate(utc.year, utc.month, utc.day),
        QTime(utc.hour, utc.minute, utc.second),
    )


def _safe_stem(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_ " else "-" for ch in name)
    return "-".join(part for part in cleaned.split() if part).lower() or "event"


def main() -> int:
    """Entry point for the organizer binary."""
    # Set here as well as in the entry point, because this module can be
    # run directly with ``python -m edsg.gui.organizer``.
    set_role(ROLE_ORGANIZER)

    app = QApplication(sys.argv)
    app.setApplicationName("ED: Squad Goals")
    app.setApplicationDisplayName("ED: Squad Goals")
    app.setOrganizationName("EDSG")
    apply_theme(app)
    window = OrganizerWindow()
    window.show()
    return app.exec()


__all__ = ["DRAFT_SUFFIX", "OrganizerWindow", "main"]
