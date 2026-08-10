"""The event organizer application.

Four tabs following the shape of the job: define the event, set the
criteria, issue the invitation, then close and publish. Later tabs stay
visible but refuse to act until their prerequisites are met, which makes
the sequence discoverable without forcing a wizard on someone who is
editing an event they built last week.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QRadioButton,
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
    TieBreak,
)
from edsg.core.paths import find_journal_dir
from edsg.core.workflow import (
    close_event,
    detect_squadron_from_journals,
    issue_invitation,
    load_invitation,
    regenerate_standings,
)
from edsg.gui.criterion_dialog import edit_criterion
from edsg.gui.theme import COLOURS, apply_theme
from edsg.gui.widgets import (
    AboutDialog,
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
    window_title,
)
from edsg.reports import write_all
from edsg.version import read_version

#: Extension for an organizer's editable working copy of an event.
DRAFT_SUFFIX = ".edsgevent"

ROLE = "Organizer"

TIE_BREAK_LABELS = {
    TieBreak.EARLIEST_SUBMISSION: "Earliest submission wins",
    TieBreak.MOST_CRITERIA_SCORED: "Most criteria scored wins",
    TieBreak.ALPHABETICAL: "Alphabetical by commander name",
}


class OrganizerWindow(QMainWindow):
    """Main window of the organizer build."""

    def __init__(self) -> None:
        super().__init__()
        self.event_def = EventDefinition(name="")
        self.identity: Identity | None = None
        self.invitation_fingerprint = ""
        self.report_dir: Path | None = None
        self.busy = False

        self.setWindowTitle(window_title(ROLE))
        self.resize(1120, 860)
        self.setMinimumSize(960, 720)

        self._build_menu()
        self._build()
        self._load_identity()
        self._refresh()

    # -- construction ---------------------------------------------------

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        for text, slot, shortcut in (
            ("&New event", self._new_event, "Ctrl+N"),
            ("&Open event draft\u2026", self._open_draft, "Ctrl+O"),
            ("&Save event draft\u2026", self._save_draft, "Ctrl+S"),
        ):
            action = QAction(text, self)
            action.setShortcut(shortcut)
            action.triggered.connect(slot)
            file_menu.addAction(action)
        file_menu.addSeparator()
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = self.menuBar().addMenu("&Help")
        about = QAction("&About", self)
        about.triggered.connect(lambda: AboutDialog(self, ROLE).exec())
        help_menu.addAction(about)

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
        self.state_label = label("", "hint")
        self.state_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(self.state_label)
        layout.addLayout(header)
        layout.addWidget(separator())

        splitter = QSplitter(Qt.Vertical)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._event_tab(), "1 \u00b7 Event")
        self.tabs.addTab(self._criteria_tab(), "2 \u00b7 Criteria")
        self.tabs.addTab(self._issue_tab(), "3 \u00b7 Issue invitation")
        self.tabs.addTab(self._close_tab(), "4 \u00b7 Close && publish")
        splitter.addWidget(self.tabs)

        self.log = LogPane(rows=6)
        splitter.addWidget(self.log)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([640, 170])
        layout.addWidget(splitter, 1)

        self.statusBar().showMessage("Ready")
        self.log.write(f"EDSG organizer {read_version()} started.", "accent")

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

        self.start_enabled = QCheckBox("Starts")
        self.start_enabled.setChecked(True)
        self.start_edit = QDateTimeEdit(QDateTime.currentDateTimeUtc())
        self.start_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.start_edit.setCalendarPopup(True)

        self.end_enabled = QCheckBox("Ends")
        self.end_enabled.setChecked(True)
        self.end_edit = QDateTimeEdit(QDateTime.currentDateTimeUtc().addDays(14))
        self.end_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.end_edit.setCalendarPopup(True)

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
        period_layout.addWidget(
            label(
                "Times are UTC, matching the journals. Untick a bound to "
                "leave that end of the window open.",
                "hint",
                wrap=True,
            )
        )
        layout.addWidget(period)

        eligibility = QGroupBox("Who can take part")
        elig_layout = QVBoxLayout(eligibility)
        self.open_radio = QRadioButton("Open to all commanders")
        self.squadron_radio = QRadioButton("Restricted to my squadron")
        self.open_radio.setChecked(True)
        self.open_radio.toggled.connect(self._refresh)
        elig_layout.addWidget(self.open_radio)
        elig_layout.addWidget(self.squadron_radio)

        squad_row = QHBoxLayout()
        self.squadron_label = label("No squadron detected.", "hint")
        self.detect_button = button("Detect from my journals\u2026")
        self.detect_button.clicked.connect(self._detect_squadron)
        squad_row.addWidget(self.squadron_label, 1)
        squad_row.addWidget(self.detect_button)
        elig_layout.addLayout(squad_row)
        elig_layout.addWidget(
            label(
                "Participants must show a join event for this squadron with "
                "no later leave, kick or disband. EDSG reads your own "
                "journals to identify the squadron so you never type an ID.",
                "hint",
                wrap=True,
            )
        )
        layout.addWidget(eligibility)

        ranking = QGroupBox("Ranking")
        ranking_form = QFormLayout(ranking)
        self.tie_box = QComboBox()
        for tie, text in TIE_BREAK_LABELS.items():
            self.tie_box.addItem(text, tie)
        ranking_form.addRow("Break ties by", self.tie_box)
        layout.addWidget(ranking)
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
        self.fingerprint_label = label("\u2014", "fingerprint")
        identity_layout.addWidget(self.fingerprint_label)
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
        layout.addWidget(identity_group)

        readiness = QGroupBox("Readiness")
        readiness_layout = QVBoxLayout(readiness)
        self.readiness_pane = InfoPane(rows=10)
        readiness_layout.addWidget(self.readiness_pane)
        layout.addWidget(readiness, 1)

        row = QHBoxLayout()
        self.issue_button = primary_button("Issue invitation\u2026")
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
        self.standings_tree = QTreeWidget()
        self.standings_tree.setColumnCount(4)
        self.standings_tree.setHeaderLabels(
            ["Rank", "Commander", "Frontier ID", "Points"]
        )
        self.standings_tree.setRootIsDecorated(False)
        self.standings_tree.setAlternatingRowColors(True)
        self.standings_tree.setColumnWidth(0, 70)
        self.standings_tree.setColumnWidth(1, 260)
        self.standings_tree.setColumnWidth(2, 140)
        results_layout.addWidget(self.standings_tree)
        layout.addWidget(results, 1)

        row = QHBoxLayout()
        self.close_button = primary_button("Close event && publish\u2026")
        self.close_button.clicked.connect(self._close_event)
        self.regen_button = button("Regenerate reports\u2026")
        self.regen_button.clicked.connect(self._regenerate)
        self.open_reports_button = button("Open report folder")
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

    def _collect(self) -> None:
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
        self.event_def.eligibility = (
            Eligibility.SQUADRON
            if self.squadron_radio.isChecked()
            else Eligibility.OPEN
        )
        # Qt hands back a plain str for StrEnum user data; convert it.
        self.event_def.tie_break = TieBreak(self.tie_box.currentData())

    def _populate(self) -> None:
        self.name_field.setText(self.event_def.name)
        self.organizer_field.setText(self.event_def.organizer_name)
        self.description_field.setPlainText(self.event_def.description)

        window = self.event_def.window
        self.start_enabled.setChecked(window.start is not None)
        if window.start:
            self.start_edit.setDateTime(
                QDateTime.fromSecsSinceEpoch(int(window.start.timestamp()), Qt.UTC)
            )
        self.end_enabled.setChecked(window.end is not None)
        if window.end:
            self.end_edit.setDateTime(
                QDateTime.fromSecsSinceEpoch(int(window.end.timestamp()), Qt.UTC)
            )

        if self.event_def.eligibility is Eligibility.SQUADRON:
            self.squadron_radio.setChecked(True)
        else:
            self.open_radio.setChecked(True)
        index = self.tie_box.findData(self.event_def.tie_break)
        if index >= 0:
            self.tie_box.setCurrentIndex(index)
        self._refresh()

    # -- refresh ---------------------------------------------------------

    def _refresh(self) -> None:
        self.state_label.setText(f"Event state: {self.event_def.state.value.upper()}")

        if self.event_def.squadron:
            self.squadron_label.setText(f"Squadron: {self.event_def.squadron}")
            self.squadron_label.setProperty("role", "good")
        else:
            self.squadron_label.setText("No squadron detected.")
            self.squadron_label.setProperty("role", "hint")
        self.squadron_label.style().unpolish(self.squadron_label)
        self.squadron_label.style().polish(self.squadron_label)
        self.detect_button.setEnabled(self.squadron_radio.isChecked())

        self.criteria_tree.clear()
        for criterion in self.event_def.criteria:
            scoring = f"{criterion.points_per_unit:g} pt/unit"
            if criterion.unit_cap is not None:
                scoring += f" \u00b7 cap {criterion.unit_cap:g}"
            if criterion.minimum_units is not None:
                scoring += f" \u00b7 min {criterion.minimum_units:g}"
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
                ("Tie-break", TIE_BREAK_LABELS[self.event_def.tie_break]),
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
            self.log.write(f"Detected squadron {squadron}.", "good")
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

        suggested = f"{_safe_stem(self.event_def.name)}{INVITATION_SUFFIX}"
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

        self.invitation_fingerprint = self.identity.fingerprint
        self.invitation_picker.set_path(written)
        self.issued_label.setText(f"Issued: {written.name}")
        self.log.write(f"Invitation issued to {written}", "good")
        self._refresh()
        show_info(
            self,
            "Invitation issued",
            f"Saved to {written}",
            "Send this file to your participants, together with your "
            "fingerprint so they can confirm it came from you:\n\n"
            f"{self.identity.fingerprint}",
        )

    # -- closing ---------------------------------------------------------

    def _pick_submissions(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Folder holding the .edsgs files"
        )
        if directory:
            self.submissions_picker.set_path(directory)

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

        self._set_busy(True, "Reading submissions\u2026")
        self.log.write(f"Reading submissions from {directory}\u2026")

        def work(_report):
            runner = regenerate_standings if regenerate else close_event
            report = runner(event, directory, fingerprint)
            written = write_all(report, report_dir, _safe_stem(event.name))
            return report, written

        def finished(payload) -> None:
            self._set_busy(False)
            report, written = payload
            self.report_dir = report_dir

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

        def failed(exc: BaseException) -> None:
            self._set_busy(False)
            self.log.write(f"Close failed: {exc}", "bad")
            show_error(self, "Could not close the event", exc)

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
        self.event_def = EventDefinition(name="")
        self.invitation_fingerprint = ""
        self.report_dir = None
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


def _safe_stem(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_ " else "-" for ch in name)
    return "-".join(part for part in cleaned.split() if part).lower() or "event"


def main() -> int:
    """Entry point for the organizer binary."""
    app = QApplication(sys.argv)
    app.setApplicationName("ED: Squad Goals")
    app.setApplicationDisplayName("ED: Squad Goals")
    app.setOrganizationName("EDSG")
    apply_theme(app)
    window = OrganizerWindow()
    window.show()
    return app.exec()


__all__ = ["DRAFT_SUFFIX", "OrganizerWindow", "main"]
