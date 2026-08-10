"""Preferences: appearance and squadron branding.

Both binaries open this dialog and write the same settings file, so a
commander who organises one event and takes part in another configures
their theme once.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from edsg.core.palettes import CUSTOMISABLE, Palette, get_palette, palette_choices
from edsg.core.settings import (
    CONTACT_KINDS,
    Appearance,
    Branding,
    Contact,
    Settings,
    save_settings,
)
from edsg.gui.widgets import button, label, show_error

#: Human wording for each overridable colour.
COLOUR_LABELS = {
    "bg": "Window background",
    "surface": "Panel background",
    "surface_alt": "Raised background",
    "line": "Borders",
    "text": "Text",
    "text_dim": "Secondary text",
    "accent": "Accent",
    "accent_dim": "Accent (dimmed)",
    "good": "Success",
    "warn": "Warning",
    "bad": "Error",
}

#: Images the logo picker will accept. SVG is excluded because ReportLab
#: cannot draw it, and a logo in the HTML but not the PDF is worse than
#: no logo at all.
LOGO_FILTER = "Images (*.png *.jpg *.jpeg *.gif *.bmp)"


def _scrollable(widget: QWidget) -> QScrollArea:
    """Wrap a tab so it scrolls rather than crushing its rows.

    The colour list is taller than a small laptop screen; without this
    Qt compresses every row until the text is clipped.
    """
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    area.setWidget(widget)
    return area


class ColourButton(QWidget):
    """A swatch that opens a colour picker."""

    changed = Signal()

    def __init__(self, key: str, value: str) -> None:
        super().__init__()
        self.key = key
        self._value = value
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.setMinimumHeight(32)
        self.swatch = QLabel()
        self.swatch.setFixedSize(28, 22)
        self.swatch.setFrameShape(QFrame.Box)
        self.field = QLineEdit(value)
        self.field.setFixedWidth(104)
        self.field.editingFinished.connect(self._from_field)
        pick = button("Pick\u2026")
        pick.clicked.connect(self._pick)

        layout.addWidget(self.swatch)
        layout.addWidget(self.field)
        layout.addWidget(pick)
        layout.addStretch(1)
        self._repaint()

    def value(self) -> str:
        return self._value

    def set_value(self, value: str) -> None:
        self._value = value
        self.field.setText(value)
        self._repaint()

    def _repaint(self) -> None:
        pixmap = QPixmap(26, 20)
        pixmap.fill(QColor(self._value))
        self.swatch.setPixmap(pixmap)

    def _from_field(self) -> None:
        text = self.field.text().strip()
        if QColor(text).isValid():
            self._value = QColor(text).name()
            self.field.setText(self._value)
            self._repaint()
            self.changed.emit()
        else:
            self.field.setText(self._value)

    def _pick(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._value), self, "Choose colour")
        if chosen.isValid():
            self.set_value(chosen.name())
            self.changed.emit()


class PreferencesDialog(QDialog):
    """Edit appearance and branding, shared by both builds."""

    #: Emitted when the theme changes, so the window can restyle live.
    theme_changed = Signal(object)

    def __init__(self, parent: QWidget | None, settings: Settings) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumSize(620, 620)
        self.settings = settings
        self._colour_buttons: dict[str, ColourButton] = {}

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._appearance_tab(), "Appearance")
        tabs.addTab(self._branding_tab(), "Squadron branding")
        layout.addWidget(tabs, 1)

        buttons = QDialogButtonBox()
        save = buttons.addButton("Save", QDialogButtonBox.AcceptRole)
        save.setProperty("role", "primary")
        buttons.addButton(QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self._cancel)
        layout.addWidget(buttons)

        self._original = settings.appearance.palette()

    # -- appearance -----------------------------------------------------

    def _appearance_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        picker = QGroupBox("Theme")
        form = QFormLayout(picker)
        self.theme_box = QComboBox()
        for name, text in palette_choices():
            self.theme_box.addItem(text, name)
        index = self.theme_box.findData(self.settings.appearance.theme)
        self.theme_box.setCurrentIndex(index if index >= 0 else 0)
        self.theme_box.currentIndexChanged.connect(self._on_theme_changed)
        form.addRow("Theme", self.theme_box)
        form.addRow(
            "",
            label(
                "The theme applies to this application and to the reports it "
                "generates. Both EDSG binaries share this setting.",
                "hint",
                wrap=True,
            ),
        )
        layout.addWidget(picker)

        custom = QGroupBox("Custom colours")
        grid = QGridLayout(custom)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)
        palette = self.settings.appearance.palette()
        for row, key in enumerate(CUSTOMISABLE):
            widget = ColourButton(key, getattr(palette, key))
            widget.changed.connect(self._on_colour_changed)
            self._colour_buttons[key] = widget
            grid.addWidget(label(COLOUR_LABELS.get(key, key)), row, 0)
            grid.addWidget(widget, row, 1)
        layout.addWidget(custom)

        row = QHBoxLayout()
        reset = button("Reset to theme defaults")
        reset.clicked.connect(self._reset_colours)
        row.addWidget(reset)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(
            label(
                "Changes preview immediately. Cancel restores what you had.",
                "hint",
            )
        )
        layout.addStretch(1)
        return _scrollable(tab)

    def _current_palette(self) -> Palette:
        return get_palette(
            self.theme_box.currentData(),
            {key: widget.value() for key, widget in self._colour_buttons.items()},
        )

    def _on_theme_changed(self) -> None:
        # Selecting a theme discards overrides, which is what someone
        # switching themes means by it.
        base = get_palette(self.theme_box.currentData())
        for key, widget in self._colour_buttons.items():
            widget.set_value(getattr(base, key))
        self.theme_changed.emit(base)

    def _on_colour_changed(self) -> None:
        self.theme_changed.emit(self._current_palette())

    def _reset_colours(self) -> None:
        self._on_theme_changed()

    # -- branding -------------------------------------------------------

    def _branding_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        branding = self.settings.branding

        identity = QGroupBox("Squadron")
        form = QFormLayout(identity)
        self.squadron_name = QLineEdit(branding.squadron_name)
        self.squadron_name.setPlaceholderText("Mining and Logistics, Ltd.")
        self.squadron_tag = QLineEdit(branding.squadron_tag)
        self.squadron_tag.setPlaceholderText("MALL")
        self.squadron_tag.setMaxLength(8)
        form.addRow("Name", self.squadron_name)
        form.addRow("Tag", self.squadron_tag)
        form.addRow(
            "",
            label(
                "Printed at the top of every report you generate. Leave "
                "blank for unbranded output.",
                "hint",
                wrap=True,
            ),
        )
        layout.addWidget(identity)

        contacts = QGroupBox("Contact details (optional)")
        contact_grid = QGridLayout(contacts)
        self.contact_rows: list[tuple[QComboBox, QLineEdit]] = []
        existing = branding.contacts or []
        for row in range(4):
            kind = QComboBox()
            for key, text in CONTACT_KINDS:
                kind.addItem(text, key)
            value = QLineEdit()
            value.setPlaceholderText("discord.gg/example")
            if row < len(existing):
                index = kind.findData(existing[row].kind)
                kind.setCurrentIndex(index if index >= 0 else 0)
                value.setText(existing[row].value)
            contact_grid.addWidget(kind, row, 0)
            contact_grid.addWidget(value, row, 1)
            self.contact_rows.append((kind, value))
        layout.addWidget(contacts)

        logo_group = QGroupBox("Logo (optional)")
        logo_layout = QVBoxLayout(logo_group)
        row = QHBoxLayout()
        self.logo_field = QLineEdit(branding.logo_path)
        self.logo_field.setReadOnly(True)
        self.logo_field.setPlaceholderText("No logo selected")
        browse = button("Choose\u2026")
        browse.clicked.connect(self._pick_logo)
        clear = button("Clear")
        clear.clicked.connect(lambda: self._set_logo(""))
        row.addWidget(self.logo_field, 1)
        row.addWidget(browse)
        row.addWidget(clear)
        logo_layout.addLayout(row)

        self.logo_preview = QLabel()
        self.logo_preview.setAlignment(Qt.AlignLeft)
        self.logo_preview.setMinimumHeight(64)
        logo_layout.addWidget(self.logo_preview)
        logo_layout.addWidget(
            label(
                "PNG, JPEG, GIF or BMP, under 2 MB. Embedded directly in the "
                "HTML report, so it keeps working when the file is shared. "
                "SVG is not supported because the PDF writer cannot draw it.",
                "hint",
                wrap=True,
            )
        )
        layout.addWidget(logo_group)
        layout.addStretch(1)
        self._refresh_logo_preview()
        return _scrollable(tab)

    def _pick_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a squadron logo", "", LOGO_FILTER
        )
        if path:
            self._set_logo(path)

    def _set_logo(self, path: str) -> None:
        self.logo_field.setText(path)
        self._refresh_logo_preview()

    def _refresh_logo_preview(self) -> None:
        path = self.logo_field.text().strip()
        if not path or not Path(path).is_file():
            self.logo_preview.clear()
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.logo_preview.setText("That file could not be read as an image.")
            return
        self.logo_preview.setPixmap(
            pixmap.scaled(220, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    # -- persistence ----------------------------------------------------

    def collect(self) -> Settings:
        """Return the settings as currently entered."""
        base = get_palette(self.theme_box.currentData())
        overrides = {
            key: widget.value()
            for key, widget in self._colour_buttons.items()
            if widget.value().lower() != getattr(base, key).lower()
        }
        contacts = [
            Contact(kind=kind.currentData(), value=value.text().strip())
            for kind, value in self.contact_rows
            if value.text().strip()
        ]
        return Settings(
            appearance=Appearance(
                theme=self.theme_box.currentData(), custom_colours=overrides
            ),
            branding=Branding(
                squadron_name=self.squadron_name.text().strip(),
                squadron_tag=self.squadron_tag.text().strip(),
                contacts=contacts,
                logo_path=self.logo_field.text().strip(),
            ),
        )

    def _save(self) -> None:
        settings = self.collect()
        try:
            save_settings(settings)
        except OSError as exc:
            show_error(self, "Could not save preferences", exc)
            return
        self.settings = settings
        self.theme_changed.emit(settings.appearance.palette())
        self.accept()

    def _cancel(self) -> None:
        self.theme_changed.emit(self._original)
        self.reject()


def edit_preferences(parent: QWidget | None, settings: Settings) -> Settings | None:
    """Open the dialog and return the saved settings, or ``None``."""
    dialog = PreferencesDialog(parent, settings)
    if parent is not None and hasattr(parent, "apply_palette"):
        dialog.theme_changed.connect(parent.apply_palette)
    if dialog.exec() == QDialog.Accepted:
        return dialog.settings
    return None


__all__ = [
    "COLOUR_LABELS",
    "ColourButton",
    "PreferencesDialog",
    "edit_preferences",
]
