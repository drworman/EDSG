"""Reusable widgets and helpers shared by both applications."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QObject,
    QRunnable,
    Qt,
    QThreadPool,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QDesktopServices, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from edsg.gui.theme import COLOURS, mono_font
from edsg.version import read_version

# --------------------------------------------------------------------- #
# Background work
# --------------------------------------------------------------------- #


class WorkerSignals(QObject):
    """Signals emitted by a :class:`Worker`, delivered on the UI thread."""

    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(object)


class Worker(QRunnable):
    """Runs a callable on a thread-pool thread.

    Qt widgets may only be touched from the UI thread, so the callable
    never receives one. It is handed a ``report`` function it may call
    with any payload; that payload arrives back as a ``progress`` signal.

    Lifetime is managed from Python rather than by the thread pool. With
    Qt's default ``autoDelete``, the runnable is destroyed in C++ the
    moment ``run`` returns, which can tear down the signals object while
    a queued emission from it is still waiting to be delivered on the UI
    thread. The result is a segfault inside the event loop with no Python
    traceback to explain it, and it surfaces only when one task overlaps
    another.
    """

    def __init__(self, work: Callable[[Callable[[Any], None]], Any]) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.work = work
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.work(self.signals.progress.emit)
        except BaseException as exc:
            self.signals.failed.emit(exc)
        else:
            self.signals.finished.emit(result)


#: Workers that have been started and have not yet reported a result.
#: Holding a strong reference here is what keeps each worker, and the
#: signals object it emits from, alive for as long as Qt might still be
#: delivering from it.
_ACTIVE_WORKERS: set[Worker] = set()


def run_in_background(
    work: Callable[[Callable[[Any], None]], Any],
    on_finished: Callable[[Any], None],
    on_failed: Callable[[BaseException], None],
    on_progress: Callable[[Any], None] | None = None,
) -> Worker:
    """Start ``work`` on the global thread pool and wire up its signals."""
    worker = Worker(work)
    _ACTIVE_WORKERS.add(worker)

    def release(_payload: Any) -> None:
        # Deferred by one turn of the event loop so the reference
        # outlives the emission currently being delivered.
        QTimer.singleShot(0, lambda: _ACTIVE_WORKERS.discard(worker))

    worker.signals.finished.connect(on_finished)
    worker.signals.failed.connect(on_failed)
    if on_progress is not None:
        worker.signals.progress.connect(on_progress)
    # Connected last so the caller's handler runs before the reference
    # is dropped.
    worker.signals.finished.connect(release)
    worker.signals.failed.connect(release)

    QThreadPool.globalInstance().start(worker)
    return worker


def wait_for_workers(timeout_ms: int = 10_000) -> bool:
    """Block until background work finishes. Returns whether it drained.

    Called when a window closes. Letting the interpreter shut down while
    a pool thread is still executing Python is another route to a crash
    on exit, and a journal scan can take several seconds.
    """
    return QThreadPool.globalInstance().waitForDone(timeout_ms)


# --------------------------------------------------------------------- #
# Small widgets
# --------------------------------------------------------------------- #


def label(text: str, role: str = "", wrap: bool = False) -> QLabel:
    """Return a styled label. ``role`` selects a stylesheet variant."""
    widget = QLabel(text)
    if role:
        widget.setProperty("role", role)
    widget.setWordWrap(wrap)
    if role in {"mono", "fingerprint"}:
        widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return widget


def separator() -> QFrame:
    """Return a thin horizontal rule."""
    line = QFrame()
    line.setProperty("role", "separator")
    line.setFrameShape(QFrame.HLine)
    line.setFixedHeight(1)
    return line


def primary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("role", "primary")
    button.setCursor(Qt.PointingHandCursor)
    return button


def button(text: str, role: str = "") -> QPushButton:
    widget = QPushButton(text)
    if role:
        widget.setProperty("role", role)
    widget.setCursor(Qt.PointingHandCursor)
    return widget


class PathPicker(QWidget):
    """A read-only path field with a browse button."""

    changed = Signal(str)

    def __init__(
        self,
        placeholder: str = "",
        button_text: str = "Browse\u2026",
    ) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.field = QLineEdit()
        self.field.setPlaceholderText(placeholder)
        self.field.setReadOnly(True)
        self.button = button(button_text)
        layout.addWidget(self.field, 1)
        layout.addWidget(self.button)

    def set_path(self, path: str | Path) -> None:
        self.field.setText(str(path))
        self.changed.emit(str(path))

    def path(self) -> Path | None:
        text = self.field.text().strip()
        return Path(text) if text else None

    def clear(self) -> None:
        self.field.clear()


class TagField(QLineEdit):
    """A comma-separated list field.

    Organizers are pasting system and station names copied from the
    galaxy map or a third-party site, so one field they can paste into
    beats a list widget with add and remove buttons.
    """

    def __init__(self, placeholder: str = "") -> None:
        super().__init__()
        self.setPlaceholderText(placeholder or "comma separated, blank for any")

    def values(self) -> list[str]:
        return [part.strip() for part in self.text().split(",") if part.strip()]

    def int_values(self) -> list[int]:
        found: list[int] = []
        for part in self.values():
            try:
                found.append(int(part))
            except ValueError:
                continue
        return found

    def set_values(self, values: list[str] | list[int]) -> None:
        self.setText(", ".join(str(value) for value in values))


class LabelledField(QWidget):
    """A field with a caption above it and an optional hint below."""

    def __init__(self, caption: str, widget: QWidget, hint: str = "") -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addWidget(label(caption))
        layout.addWidget(widget)
        if hint:
            layout.addWidget(label(hint, "hint", wrap=True))
        self.widget = widget


class LogPane(QPlainTextEdit):
    """A colour-coded activity log."""

    TAGS = {
        "info": COLOURS["text"],
        "muted": COLOURS["text_faint"],
        "good": COLOURS["good"],
        "warn": COLOURS["warn"],
        "bad": COLOURS["bad"],
        "accent": COLOURS["accent"],
    }

    def __init__(self, rows: int = 7) -> None:
        super().__init__()
        self.setReadOnly(True)
        self.setFont(mono_font())
        self.setMaximumBlockCount(2000)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumHeight(20 * rows)

    def write(self, message: str, tag: str = "info") -> None:
        """Append a timestamped, colour-coded line."""
        stamp = datetime.now().strftime("%H:%M:%S")
        colour = self.TAGS.get(tag, self.TAGS["info"])
        safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.appendHtml(
            f'<span style="color:{COLOURS["text_faint"]}">[{stamp}]</span> '
            f'<span style="color:{colour}">{safe}</span>'
        )
        self.moveCursor(QTextCursor.End)


class InfoPane(QTextBrowser):
    """A rich-text pane for read-only summaries."""

    def __init__(self, rows: int = 8) -> None:
        super().__init__()
        self.setOpenExternalLinks(False)
        self.setMinimumHeight(18 * rows)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        self.document().setDefaultStyleSheet(
            f"""
            body {{ color: {COLOURS["text"]}; }}
            .k {{ color: {COLOURS["text_faint"]}; }}
            .v {{ color: {COLOURS["text"]}; }}
            .accent {{ color: {COLOURS["accent"]}; }}
            .good {{ color: {COLOURS["good"]}; }}
            .bad {{ color: {COLOURS["bad"]}; }}
            .warn {{ color: {COLOURS["warn"]}; }}
            .mono {{ font-family: monospace; }}
            h3 {{ color: {COLOURS["accent"]}; margin: 0 0 4px 0; }}
            """
        )


class CheckRow(QWidget):
    """A horizontal row of checkboxes with a caption."""

    def __init__(self, caption: str, options: list[str]) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(label(caption))
        self.boxes: dict[str, QCheckBox] = {}
        for option in options:
            box = QCheckBox(option)
            self.boxes[option] = box
            layout.addWidget(box)
        layout.addStretch(1)

    def checked(self) -> list[str]:
        return [name for name, box in self.boxes.items() if box.isChecked()]

    def set_checked(self, names: list[str]) -> None:
        wanted = {name.lower() for name in names}
        for name, box in self.boxes.items():
            box.setChecked(name.lower() in wanted)


# --------------------------------------------------------------------- #
# Dialogs
# --------------------------------------------------------------------- #


def _dialog(parent: QWidget | None, icon, title: str, text: str, detail: str = ""):
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(text)
    if detail:
        box.setInformativeText(detail)
    return box


def show_error(
    parent: QWidget | None, title: str, message: BaseException | str, detail: str = ""
) -> None:
    """Show an error dialog."""
    _dialog(parent, QMessageBox.Critical, title, str(message), detail).exec()


def show_warning(parent: QWidget | None, title: str, message: str) -> None:
    _dialog(parent, QMessageBox.Warning, title, message).exec()


def show_info(
    parent: QWidget | None, title: str, message: str, detail: str = ""
) -> None:
    _dialog(parent, QMessageBox.Information, title, message, detail).exec()


def ask_confirm(
    parent: QWidget | None,
    title: str,
    message: str,
    detail: str = "",
    confirm_text: str = "Continue",
    dangerous: bool = False,
) -> bool:
    """Ask a yes/no question, defaulting to the safe answer."""
    box = _dialog(
        parent,
        QMessageBox.Warning if dangerous else QMessageBox.Question,
        title,
        message,
        detail,
    )
    confirm = box.addButton(confirm_text, QMessageBox.AcceptRole)
    cancel = box.addButton("Cancel", QMessageBox.RejectRole)
    box.setDefaultButton(cancel)
    box.exec()
    return box.clickedButton() is confirm


def open_path(path: Path) -> None:
    """Open a file or folder with the platform's default handler."""
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))


class AboutDialog(QDialog):
    """Shared 'about' window, including the attribution notices."""

    def __init__(self, parent: QWidget | None, role: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("About ED: Squad Goals")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(label("ED: Squad Goals", "title"))
        layout.addWidget(
            label(f"{role} build \u2014 version {read_version()}", "subtitle")
        )
        layout.addWidget(separator())
        layout.addWidget(
            label(
                "Community event scoring for Elite Dangerous.\n\n"
                "Organizers define an event and issue a signed invitation. "
                "Participants scan their own journals and return a signed "
                "submission. Organizers close the event and publish "
                "standings.",
                wrap=True,
            )
        )
        layout.addWidget(separator())
        layout.addWidget(
            label(
                "Elite Dangerous is a trademark of Frontier Developments plc. "
                "EDSG is an unofficial community tool, not affiliated with, "
                "endorsed by, or supported by Frontier Developments.\n\n"
                "EDSG is released under the MIT licence. It uses Qt for "
                "Python (PySide6) under the LGPL v3, ReportLab under the "
                "BSD licence, and the cryptography library under the "
                "Apache 2.0 licence. See THIRD-PARTY-NOTICES.md in the "
                "distribution for full texts and relinking instructions.",
                "hint",
                wrap=True,
            )
        )
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


# --------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------- #


def to_utc(moment: datetime) -> datetime:
    """Attach UTC to a naive datetime taken from a Qt widget."""
    return moment.replace(tzinfo=UTC)


def window_title(role: str) -> str:
    return f"ED: Squad Goals {read_version()} \u2014 {role}"


__all__ = [
    "AboutDialog",
    "CheckRow",
    "InfoPane",
    "LabelledField",
    "LogPane",
    "PathPicker",
    "TagField",
    "Worker",
    "WorkerSignals",
    "ask_confirm",
    "button",
    "label",
    "open_path",
    "primary_button",
    "run_in_background",
    "separator",
    "show_error",
    "show_info",
    "show_warning",
    "to_utc",
    "wait_for_workers",
    "window_title",
]
