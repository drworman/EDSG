"""The participant application.

Deliberately linear: open the invitation, point at your journals, scan,
send the result back. Each step unlocks the next.

The interface is explicit about what EDSG reads and what leaves the
machine, because the application is asking permission to read months of
someone's play history. Saying so plainly is the least it can do.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QMainWindow,
    QProgressBar,
    QScrollArea,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from edsg.core.criteria import Measure
from edsg.core.crypto import Identity, load_or_create_identity
from edsg.core.errors import EDSGError
from edsg.core.journal import (
    CommanderIdentity,
    MultipleCommandersError,
    resolve_commander,
)
from edsg.core.models import (
    INVITATION_SUFFIX,
    SUBMISSION_SUFFIX,
    Eligibility,
    Submission,
)
from edsg.core.paths import (
    ROLE_PARTICIPANT,
    app_root,
    find_journal_dir,
    set_role,
)
from edsg.core.settings import load_settings
from edsg.core.workflow import Invitation, load_invitation, participate
from edsg.gui.about import SupportStrip
from edsg.gui.menus import build_menus
from edsg.gui.preferences import edit_preferences
from edsg.gui.theme import COLOURS, apply_theme
from edsg.gui.widgets import (
    InfoPane,
    LogPane,
    PathPicker,
    label,
    open_path,
    primary_button,
    run_in_background,
    separator,
    show_error,
    show_info,
    wait_for_workers,
    window_title,
)
from edsg.version import read_version

ROLE = "Participant"


class ParticipantWindow(QMainWindow):
    """Main window of the participant build."""

    def __init__(self) -> None:
        super().__init__()
        self.invitation: Invitation | None = None
        self.journal_dir: Path | None = None
        self.commander: CommanderIdentity | None = None
        self.commander_fid: str | None = None
        self.identity: Identity | None = None
        self.submission: Submission | None = None
        self.submission_path: Path | None = None
        self.busy = False
        self.settings = load_settings()

        self.setWindowTitle(window_title(ROLE))
        self.resize(1020, 880)
        self.setMinimumSize(880, 720)

        self._build_menu()
        self._build()
        self._load_identity()
        self._autodetect_journals()
        self._refresh()

    # -- construction ---------------------------------------------------

    def _build_menu(self) -> None:
        open_action = QAction("&Open invitation\u2026", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_invitation)

        save_action = QAction("&Save submission as\u2026", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_as)

        build_menus(
            self,
            ROLE,
            file_actions=[open_action, save_action],
            on_preferences=self._edit_preferences,
        )

    def _edit_preferences(self) -> None:
        updated = edit_preferences(self, self.settings)
        if updated is not None:
            self.settings = updated
            self.log.write("Preferences saved.", "good")
        self.apply_palette(self.settings.appearance.palette())

    def apply_palette(self, palette) -> None:
        """Re-theme the running application."""
        application = QApplication.instance()
        if application is not None:
            apply_theme(application, palette)
        if self.invitation is not None:
            self._show_event()
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
        title_box.addWidget(label(f"Participant build {read_version()}", "subtitle"))
        header.addLayout(title_box)
        header.addStretch(1)
        header.addWidget(SupportStrip(compact=True), 0, Qt.AlignRight)
        layout.addLayout(header)
        layout.addWidget(separator())

        splitter = QSplitter(Qt.Vertical)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 8, 0)
        body_layout.setSpacing(12)

        body_layout.addWidget(self._invitation_group())
        body_layout.addWidget(self._journal_group())
        body_layout.addWidget(self._scan_group(), 1)
        body_layout.addWidget(self._send_group())

        # The four steps together are taller than a laptop screen once an
        # invitation is loaded, so the body scrolls rather than letting Qt
        # crush whichever group compresses most readily.
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setFrameShape(QScrollArea.NoFrame)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroller.setWidget(body)
        splitter.addWidget(scroller)
        self.log = LogPane(rows=5)
        splitter.addWidget(self.log)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([700, 150])
        layout.addWidget(splitter, 1)

        self.statusBar().showMessage("Ready")
        self.log.write(f"EDSG participant {read_version()} started.", "accent")

    def _invitation_group(self) -> QGroupBox:
        group = QGroupBox("Step 1 \u00b7 Open your invitation")
        layout = QVBoxLayout(group)
        self.invitation_picker = PathPicker(
            "The .edsgi file your organizer sent you", "Open\u2026"
        )
        self.invitation_picker.button.setToolTip(
            "Choose the invitation file. EDSG checks its signature before "
            "showing you anything."
        )
        self.invitation_picker.button.clicked.connect(self._open_invitation)
        layout.addWidget(self.invitation_picker)
        self.event_pane = InfoPane(rows=9)
        self._clear_event_pane()
        layout.addWidget(self.event_pane)
        return group

    def _journal_group(self) -> QGroupBox:
        group = QGroupBox("Step 2 \u00b7 Point EDSG at your journal folder")
        layout = QVBoxLayout(group)
        self.journal_picker = PathPicker("Your Elite Dangerous journal folder")
        self.journal_picker.button.setToolTip(
            "The folder holding your Journal.*.log files. EDSG usually finds "
            "it by itself, including Steam Proton and Wine prefixes."
        )
        self.journal_picker.button.clicked.connect(self._pick_journals)
        layout.addWidget(self.journal_picker)
        self.commander_label = label("No journal folder selected yet.", "hint")
        layout.addWidget(self.commander_label)
        layout.addWidget(
            label(
                "EDSG reads these files on this computer only. Nothing is "
                "uploaded anywhere. The file you produce contains your "
                "commander name, your Frontier ID and the totals for this "
                "event's criteria \u2014 no other part of your journals.",
                "hint",
                wrap=True,
            )
        )
        return group

    def _scan_group(self) -> QGroupBox:
        group = QGroupBox("Step 3 \u00b7 Compile your results")
        layout = QVBoxLayout(group)

        row = QHBoxLayout()
        self.scan_button = primary_button("Scan my journals")
        self.scan_button.setToolTip(
            "Read your journals and total up only what this event measures. "
            "Nothing leaves this computer."
        )
        self.scan_button.clicked.connect(self._scan)
        row.addWidget(self.scan_button)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.progress.setMinimumWidth(240)
        row.addWidget(self.progress, 1)
        self.progress_label = label("", "hint")
        row.addWidget(self.progress_label)
        row.addStretch(1)
        layout.addLayout(row)

        self.results_tree = QTreeWidget()
        self.results_tree.setColumnCount(3)
        self.results_tree.setHeaderLabels(["Criterion", "Measured", "Points"])
        self.results_tree.setRootIsDecorated(False)
        self.results_tree.setAlternatingRowColors(True)
        self.results_tree.setColumnWidth(0, 380)
        self.results_tree.setColumnWidth(1, 220)
        self.results_tree.setMinimumHeight(210)
        layout.addWidget(self.results_tree, 1)

        self.total_label = label("", "heading")
        self.total_label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.total_label)
        return group

    def _send_group(self) -> QGroupBox:
        group = QGroupBox("Step 4 \u00b7 Send it to your organizer")
        layout = QHBoxLayout(group)
        self.save_button = primary_button("Save submission\u2026")
        self.save_button.setToolTip(
            "Save a copy of your signed submission to send to the organizer"
        )
        self.save_button.clicked.connect(self._save_as)
        self.reveal_button = QWidget()
        from edsg.gui.widgets import button as make_button

        self.reveal_button = make_button("Open containing folder")
        self.reveal_button.setToolTip("Open the folder your submission was saved into")
        self.reveal_button.clicked.connect(self._reveal)
        layout.addWidget(self.save_button)
        layout.addWidget(self.reveal_button)
        self.saved_label = label("", "hint")
        layout.addWidget(self.saved_label, 1)
        return group

    # -- setup -----------------------------------------------------------

    def _load_identity(self) -> None:
        try:
            self.identity = load_or_create_identity("participant", "EDSG participant")
        except EDSGError as exc:
            show_error(self, "Signing identity", exc)
            self.log.write(f"Could not create a signing identity: {exc}", "bad")

    def _autodetect_journals(self) -> None:
        found = find_journal_dir()
        if found is not None:
            self.log.write(f"Found a journal folder at {found}.", "muted")
            self._set_journal_dir(found, quiet=True)

    # -- step 1 ----------------------------------------------------------

    def _open_invitation(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open event invitation",
            "",
            f"EDSG invitation (*{INVITATION_SUFFIX});;All files (*)",
        )
        if not path:
            return
        try:
            invitation = load_invitation(Path(path))
        except EDSGError as exc:
            self.invitation = None
            self.log.write(f"Invitation rejected: {exc}", "bad")
            show_error(
                self,
                "This invitation could not be verified",
                exc,
                "Ask your organizer to send the file again. Do not take "
                "part using a file that fails this check.",
            )
            self._refresh()
            return

        self.invitation = invitation
        self.invitation_picker.set_path(path)
        self.log.write(f"Invitation verified: '{invitation.event.name}'.", "good")
        self._show_event()
        self._refresh()

    def _clear_event_pane(self) -> None:
        self.event_pane.setHtml(
            '<p class="k">No invitation loaded yet.<br/><br/>'
            "Choose the <b>.edsgi</b> file your event organizer sent you. "
            "EDSG will check its signature and show you the rules before "
            "you scan anything.</p>"
        )

    def _show_event(self) -> None:
        if self.invitation is None:
            self._clear_event_pane()
            return
        event = self.invitation.event
        eligibility = (
            f"Squadron only \u2014 {event.squadron}"
            if event.eligibility is Eligibility.SQUADRON and event.squadron
            else "Open to all commanders"
        )
        facts = [
            ("Organizer", event.organizer_name or "not stated"),
            ("Period", event.window.describe()),
            ("Eligibility", eligibility),
        ]
        rows = "".join(
            f'<tr><td class="k">{key}&nbsp;&nbsp;</td><td class="v">{value}</td></tr>'
            for key, value in facts
        )
        criteria = "".join(
            f'<li><span class="v">{item.label}</span> '
            f'<span class="k">\u2014 {item.describe()}</span></li>'
            for item in event.criteria
        )

        goal = ""
        if event.tiers.enabled and event.tiers.target > 0:
            plan = event.tiers
            bands = ", ".join(band.label for band in plan.reward_bands)
            goal = (
                f'<p class="k">This is a squadron goal: everyone\u2019s '
                f"points add toward <b>{plan.target:,.0f}</b>, across "
                f"{len(plan.goal_tiers)} tier(s)."
                + (f" Reward tiers: {bands}." if bands else "")
                + "</p>"
            )
        description = (
            f'<p class="k">{event.description}</p>' if event.description else ""
        )
        self.event_pane.setHtml(
            f"<h3>{event.name}</h3>{description}"
            f"<table cellspacing=2>{rows}</table>"
            f'<p class="k">Signed by <span class="accent mono">'
            f"{self.invitation.signer_fingerprint}</span><br/>"
            f"Check that fingerprint against the one your organizer "
            f"published before you take part.</p>"
            f"{goal}"
            f'<p class="k">Scored on:</p><ul>{criteria}</ul>'
        )

    # -- step 2 ----------------------------------------------------------

    def _pick_journals(self) -> None:
        initial = self.journal_dir or find_journal_dir()
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select your Elite Dangerous journal folder",
            str(initial) if initial else "",
        )
        if directory:
            self._set_journal_dir(Path(directory))

    def _choose_commander(
        self, candidates: list[CommanderIdentity]
    ) -> CommanderIdentity | None:
        """Ask which commander to scan for.

        Elite writes every account on a machine into one folder, so this
        is a normal situation. EDSG must not guess: the Frontier ID is
        what the submission is attributed to.
        """
        labels = [f"CMDR {item.name}  ({item.fid})" for item in candidates]
        choice, accepted = QInputDialog.getItem(
            self,
            "Which commander?",
            "This folder holds journals for more than one commander.\n"
            "Choose the one you are taking part as:",
            labels,
            0,
            False,
        )
        if not accepted:
            return None
        return candidates[labels.index(choice)]

    def _set_journal_dir(self, directory: Path, quiet: bool = False) -> None:
        self.journal_picker.set_path(directory)
        try:
            commander = resolve_commander(directory, self.commander_fid)
        except MultipleCommandersError as exc:
            # Auto-detection at start-up must not throw a dialog at
            # someone who has not asked for anything yet.
            if quiet:
                self.journal_dir = None
                self.commander = None
                self.commander_label.setText(
                    f"{len(exc.commanders)} commanders found here — choose "
                    f"your journal folder to pick one."
                )
                self.commander_label.setProperty("role", "warn")
                self._restyle(self.commander_label)
                self._refresh()
                return
            chosen = self._choose_commander(exc.commanders)
            if chosen is None:
                self.journal_dir = None
                self.commander = None
                self.commander_label.setText("No commander chosen.")
                self.commander_label.setProperty("role", "warn")
                self._restyle(self.commander_label)
                self._refresh()
                return
            self.commander_fid = chosen.fid
            commander = chosen
        except EDSGError as exc:
            self.journal_dir = None
            self.commander = None
            self.commander_label.setText(str(exc))
            self.commander_label.setProperty("role", "bad")
            self._restyle(self.commander_label)
            if not quiet:
                show_error(self, "Could not read that folder", exc)
            self._refresh()
            return

        self.journal_dir = directory
        self.commander = commander
        self.commander_label.setText(f"CMDR {commander.name}  \u00b7  {commander.fid}")
        self.commander_label.setProperty("role", "good")
        self._restyle(self.commander_label)
        self.log.write(f"Journals belong to CMDR {commander.name}.", "good")
        self._refresh()

    @staticmethod
    def _restyle(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    # -- step 3 ----------------------------------------------------------

    def _scan(self) -> None:
        if self.invitation is None or self.journal_dir is None:
            return
        if self.identity is None:
            show_error(self, "No identity", "No signing identity is available.")
            return

        invitation = self.invitation
        journal_dir = self.journal_dir
        identity = self.identity
        chosen_fid = self.commander_fid
        # Submissions belong with the user's own documents, beside the
        # organizer's event folders, not inside Frontier's Saved Games
        # tree where the journals happen to live.
        destination = app_root() / "Submissions"

        self._set_busy(True, "Reading journals\u2026")
        self.results_tree.clear()
        self.total_label.setText("")
        self.log.write("Scanning journals \u2014 this may take a moment.")

        def work(report):
            destination.mkdir(parents=True, exist_ok=True)
            return participate(
                invitation,
                journal_dir,
                identity,
                destination,
                progress=lambda count, phase: report((count, phase)),
                commander_fid=chosen_fid,
            )

        def progressed(payload) -> None:
            count, phase = payload
            self.progress_label.setText(
                f"{phase} \u2014 {count:,} events" if count else phase
            )

        def finished(payload) -> None:
            path, submission, membership = payload
            self._set_busy(False)
            self.submission = submission
            self.submission_path = path
            self.progress_label.setText("complete")

            event = invitation.event
            for result in submission.results:
                criterion = event.criterion_by_id(result.criterion_id)
                measure = criterion.measure if criterion else Measure.COUNT
                measured = _format_units(result.counted_units, measure)
                if result.raw_units != result.counted_units:
                    measured += f"  (of {result.raw_units:,.0f})"
                item = QTreeWidgetItem(
                    [result.label, measured, f"{result.points:,.2f}"]
                )
                item.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
                item.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
                if result.points <= 0:
                    item.setForeground(2, QColor(COLOURS["text_faint"]))
                self.results_tree.addTopLevelItem(item)

            self.total_label.setText(f"Total: {submission.total_points:,.2f} points")

            if membership.is_member:
                self.log.write(f"Eligible \u2014 {membership.reason}", "good")
            else:
                self.log.write(f"NOT eligible \u2014 {membership.reason}", "bad")
                show_error(
                    self,
                    "You are not eligible for this event",
                    membership.reason,
                    "A submission has still been saved so you can send it to "
                    "your organizer, but it will score zero.",
                )

            if submission.scan.malformed_lines:
                self.log.write(
                    f"{submission.scan.malformed_lines} journal lines could "
                    f"not be read and were skipped.",
                    "warn",
                )
            self.log.write(
                f"Scanned {submission.scan.entries_parsed:,} events from "
                f"{submission.scan.files_read} files.",
                "muted",
            )
            self.log.write(f"Submission saved to {path}", "good")
            self.saved_label.setText(f"Saved: {path.name}")
            self._refresh()

        def failed(exc: BaseException) -> None:
            self._set_busy(False)
            self.progress_label.setText("failed")
            self.log.write(f"Scan failed: {exc}", "bad")
            show_error(self, "The scan could not finish", exc)

        run_in_background(work, finished, failed, progressed)

    # -- step 4 ----------------------------------------------------------

    def _save_as(self) -> None:
        if self.submission is None or self.submission_path is None:
            return
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Save your submission",
            self.submission.filename(),
            f"EDSG submission (*{SUBMISSION_SUFFIX})",
        )
        if not target:
            return
        try:
            Path(target).write_text(
                self.submission_path.read_text(encoding="utf-8"), encoding="utf-8"
            )
        except OSError as exc:
            show_error(self, "Could not save", exc)
            return
        self.submission_path = Path(target)
        self.saved_label.setText(f"Saved: {Path(target).name}")
        self.log.write(f"Copy saved to {target}", "good")
        show_info(
            self,
            "Submission saved",
            "Send this file to your event organizer.",
            str(target),
        )

    def _reveal(self) -> None:
        if self.submission_path:
            open_path(self.submission_path.parent)

    # -- state -----------------------------------------------------------

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self.busy = busy
        self.progress.setVisible(busy)
        self.statusBar().showMessage(message or "Ready")
        self._refresh()

    def _refresh(self) -> None:
        ready = (
            self.invitation is not None
            and self.journal_dir is not None
            and not self.busy
        )
        self.scan_button.setEnabled(ready)
        self.invitation_picker.button.setEnabled(not self.busy)
        self.journal_picker.button.setEnabled(not self.busy)
        has_result = self.submission is not None and not self.busy
        self.save_button.setEnabled(has_result)
        self.reveal_button.setEnabled(has_result)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        """Drain background work before the interpreter shuts down.

        A pool thread still inside Python when the process exits is a
        crash on close, and a scan can run for several seconds.
        """
        wait_for_workers()
        super().closeEvent(event)


def _format_units(value: float, measure: Measure) -> str:
    if measure is Measure.CREDITS:
        return f"{value:,.0f} cr"
    if measure is Measure.TONNAGE:
        return f"{value:,.0f} t"
    return f"{value:,.0f}"


def main() -> int:
    """Entry point for the participant binary."""
    # Set here as well as in the entry point, because this module can be
    # run directly with ``python -m edsg.gui.participant``.
    set_role(ROLE_PARTICIPANT)

    app = QApplication(sys.argv)
    app.setApplicationName("ED: Squad Goals")
    app.setApplicationDisplayName("ED: Squad Goals")
    app.setOrganizationName("EDSG")
    apply_theme(app)
    window = ParticipantWindow()
    window.show()
    return app.exec()


__all__ = ["ParticipantWindow", "main"]
