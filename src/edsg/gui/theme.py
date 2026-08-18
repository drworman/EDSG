"""Visual identity for both applications.

A single Qt stylesheet drives every widget so the organizer and
participant builds are visually indistinguishable apart from their
content. The palette borrows Elite Dangerous' orange-on-near-black HUD,
but at lower saturation than the game uses: a HUD is glanced at for
seconds, whereas an organizer may sit in this application for an hour
building an event, and full-strength orange on black is exhausting to
read for that long.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from edsg.core.palettes import DEFAULT_PALETTE, Palette, get_palette


def _colours_from(palette: Palette) -> dict[str, str]:
    """Expand a core palette into the keys the stylesheet uses."""
    return {
        "bg": palette.bg,
        "surface": palette.surface,
        "surface_alt": palette.surface_alt,
        "surface_hi": palette.header_bg,
        "line": palette.line,
        "line_soft": palette.zebra,
        "text": palette.text,
        "text_dim": palette.text_dim,
        "text_faint": palette.text_faint,
        "accent": palette.accent,
        "accent_dim": palette.accent_dim,
        "accent_soft": palette.zebra,
        "good": palette.good,
        "warn": palette.warn,
        "bad": palette.bad,
        "info": palette.accent,
    }


#: The active colours. Mutated in place by :func:`apply_theme` so the
#: modules that imported this dict at import time keep seeing the current
#: theme without every one of them needing a refresh hook.
COLOURS: dict[str, str] = _colours_from(get_palette(DEFAULT_PALETTE))

#: Point sizes, scaled by the platform's default UI font.
FONT_SIZES = {"title": 17, "heading": 11, "body": 10, "small": 9}


def _stylesheet() -> str:
    c = COLOURS
    return f"""
QWidget {{
    background-color: {c["bg"]};
    color: {c["text"]};
    font-size: {FONT_SIZES["body"]}pt;
}}
QMainWindow, QDialog {{ background-color: {c["bg"]}; }}

QLabel {{ background: transparent; }}
QLabel[role="title"] {{
    color: {c["accent"]};
    font-size: {FONT_SIZES["title"]}pt;
    font-weight: 600;
    letter-spacing: 1px;
}}
QLabel[role="subtitle"] {{ color: {c["text_faint"]}; font-size: {FONT_SIZES["small"]}pt; }}
QLabel[role="heading"] {{
    color: {c["accent"]};
    font-size: {FONT_SIZES["heading"]}pt;
    font-weight: 600;
}}
QLabel[role="hint"] {{ color: {c["text_faint"]}; font-size: {FONT_SIZES["small"]}pt; }}
QLabel[role="good"] {{ color: {c["good"]}; }}
QLabel[role="warn"] {{ color: {c["warn"]}; }}
QLabel[role="bad"] {{ color: {c["bad"]}; }}
QLabel[role="mono"] {{
    color: {c["text_dim"]};
    font-family: "DejaVu Sans Mono", "Consolas", "Menlo", monospace;
}}
QLabel[role="fingerprint"] {{
    color: {c["accent"]};
    font-family: "DejaVu Sans Mono", "Consolas", "Menlo", monospace;
    font-size: {FONT_SIZES["heading"]}pt;
    letter-spacing: 1px;
}}

QGroupBox {{
    border: 1px solid {c["line"]};
    border-radius: 4px;
    margin-top: 20px;
    padding: 14px 12px 12px 12px;
    background-color: {c["surface"]};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 2px 8px;
    color: {c["accent"]};
    font-size: {FONT_SIZES["small"]}pt;
    font-weight: 600;
    text-transform: uppercase;
}}

QPushButton {{
    background-color: {c["surface_alt"]};
    border: 1px solid {c["line"]};
    border-radius: 3px;
    padding: 6px 16px;
    min-height: 20px;
    color: {c["text"]};
}}
QPushButton:hover {{ background-color: {c["surface_hi"]}; border-color: {c["accent_dim"]}; }}
QPushButton:pressed {{ background-color: {c["line"]}; }}
QPushButton:disabled {{ background-color: {c["surface"]}; color: {c["text_faint"]};
                        border-color: {c["line_soft"]}; }}
QPushButton[role="primary"] {{
    background-color: {c["accent_dim"]};
    border: 1px solid {c["accent"]};
    color: #ffffff;
    font-weight: 600;
    padding: 7px 20px;
    min-height: 22px;
}}
QPushButton[role="primary"]:hover {{ background-color: {c["accent"]}; }}
QPushButton[role="primary"]:disabled {{
    background-color: {c["surface_alt"]};
    border-color: {c["line"]};
    color: {c["text_faint"]};
}}
QPushButton[role="danger"] {{ border-color: {c["bad"]}; color: {c["bad"]}; }}
QPushButton[role="danger"]:hover {{ background-color: #3a1f1d; }}
QPushButton[role="support"] {{
    background: transparent;
    border: none;
    color: {c["text_dim"]};
    padding: 1px 4px;
    font-size: {FONT_SIZES["small"]}pt;
}}
QPushButton[role="support"]:hover {{ color: {c["accent"]}; }}
QPushButton[role="link"] {{
    background: transparent; border: none; color: {c["info"]};
    padding: 2px 4px; text-decoration: underline;
}}

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QDateTimeEdit {{
    background-color: {c["surface_alt"]};
    border: 1px solid {c["line"]};
    border-radius: 3px;
    padding: 5px 8px;
    min-height: 20px;
    color: {c["text"]};
    selection-background-color: {c["accent_dim"]};
    selection-color: #ffffff;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QDateTimeEdit:focus {{
    border-color: {c["accent"]};
}}
QLineEdit:disabled, QDateTimeEdit:disabled, QDoubleSpinBox:disabled {{
    background-color: {c["surface"]}; color: {c["text_faint"]};
}}
QLineEdit[state="invalid"] {{ border-color: {c["bad"]}; }}

QComboBox {{
    background-color: {c["surface_alt"]};
    border: 1px solid {c["line"]};
    border-radius: 3px;
    padding: 5px 8px;
    min-height: 20px;
    color: {c["text"]};
}}
QComboBox:focus {{ border-color: {c["accent"]}; }}
QComboBox:disabled {{ background-color: {c["surface"]}; color: {c["text_faint"]}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {c["surface_alt"]};
    border: 1px solid {c["line"]};
    selection-background-color: {c["accent_dim"]};
    selection-color: #ffffff;
    outline: none;
}}

QTabWidget::pane {{ border: 1px solid {c["line"]}; border-radius: 3px; top: -1px;
                    background-color: {c["bg"]}; }}
QTabBar::tab {{
    background-color: {c["surface"]};
    color: {c["text_faint"]};
    border: 1px solid {c["line"]};
    border-bottom: none;
    padding: 9px 20px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {c["bg"]};
    color: {c["accent"]};
    border-bottom: 2px solid {c["accent"]};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{ color: {c["text_dim"]}; }}
QTabBar::tab:disabled {{ color: {c["line"]}; }}

QTreeWidget, QTreeView, QTableWidget, QTableView, QListWidget {{
    background-color: {c["surface"]};
    alternate-background-color: {c["surface_alt"]};
    border: 1px solid {c["line"]};
    border-radius: 3px;
    gridline-color: {c["line_soft"]};
    outline: none;
}}
QTreeWidget::item, QTableWidget::item, QListWidget::item {{
    padding: 5px 4px;
    border: none;
}}
QTreeWidget::item:selected, QTableWidget::item:selected, QListWidget::item:selected {{
    background-color: {c["accent_dim"]};
    color: #ffffff;
}}
/* File dialogs and other Qt-supplied windows.

   Qt draws the back, forward and parent-directory arrows with the
   style's own pixmaps, which are dark grey and all but vanish against a
   dark background. Giving the buttons a raised surface and a border puts
   something legible behind them, and the hover and pressed states make
   it obvious they are controls at all. */
QToolButton {{
    background: {c["surface_alt"]};
    border: 1px solid {c["line"]};
    border-radius: 3px;
    padding: 3px;
    margin: 1px;
    min-width: 22px;
    min-height: 22px;
}}
QToolButton:hover {{
    background: {c["surface_hi"]};
    border-color: {c["accent"]};
}}
QToolButton:pressed {{ background: {c["accent_dim"]}; }}
QToolButton:disabled {{
    background: {c["surface"]};
    border-color: {c["line_soft"]};
}}
QToolButton::menu-indicator {{ image: none; }}

/* The sidebar of shortcuts, and the file list itself. */
QListView, QTreeView {{
    background: {c["surface"]};
    alternate-background-color: {c["line_soft"]};
}}
QFileDialog QListView::item:selected,
QFileDialog QTreeView::item:selected {{
    background: {c["accent_dim"]};
    color: {c["text"]};
}}

QHeaderView::section {{
    background-color: {c["surface_alt"]};
    color: {c["text_faint"]};
    border: none;
    border-right: 1px solid {c["line_soft"]};
    border-bottom: 1px solid {c["line"]};
    padding: 7px 6px;
    font-size: {FONT_SIZES["small"]}pt;
    font-weight: 600;
    text-transform: uppercase;
}}

QCheckBox, QRadioButton {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator {{ width: 14px; height: 14px; }}
QRadioButton::indicator {{ width: 16px; height: 16px; }}
QCheckBox::indicator {{
    border: 1px solid {c["line"]}; border-radius: 3px;
    background-color: {c["surface_alt"]};
}}
QCheckBox::indicator:checked {{
    background-color: {c["accent_dim"]}; border-color: {c["accent"]};
}}
QCheckBox::indicator:disabled {{ border-color: {c["line_soft"]}; }}
QRadioButton::indicator:unchecked {{
    border: 1px solid {c["line"]};
    border-radius: 8px;
    background-color: {c["surface_alt"]};
}}
QRadioButton::indicator:checked {{
    border: 1px solid {c["accent"]};
    border-radius: 8px;
    background-color: qradialgradient(
        cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 {c["accent"]}, stop:0.45 {c["accent"]},
        stop:0.5 {c["surface_alt"]}, stop:1 {c["surface_alt"]});
}}

QProgressBar {{
    background-color: {c["surface_alt"]};
    border: 1px solid {c["line"]};
    border-radius: 3px;
    height: 16px;
    text-align: center;
    color: {c["text_dim"]};
    font-size: {FONT_SIZES["small"]}pt;
}}
QProgressBar::chunk {{ background-color: {c["accent_dim"]}; border-radius: 2px; }}

QScrollBar:vertical {{ background: {c["bg"]}; width: 11px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {c["line"]}; border-radius: 5px; min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: {c["accent_dim"]}; }}
QScrollBar:horizontal {{ background: {c["bg"]}; height: 11px; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: {c["line"]}; border-radius: 5px; min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{ background: {c["accent_dim"]}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QMenuBar {{ background-color: {c["surface"]}; border-bottom: 1px solid {c["line"]}; }}
QMenuBar::item {{ padding: 6px 12px; background: transparent; }}
QMenuBar::item:selected {{ background-color: {c["surface_hi"]}; color: {c["accent"]}; }}
QMenu {{
    background-color: {c["surface_alt"]};
    border: 1px solid {c["line"]};
    padding: 4px;
}}
QMenu::item {{ padding: 6px 24px 6px 12px; }}
QMenu::item:selected {{ background-color: {c["accent_dim"]}; color: #ffffff; }}
QMenu::separator {{ height: 1px; background: {c["line"]}; margin: 4px 8px; }}

QStatusBar {{
    background-color: {c["surface"]};
    border-top: 1px solid {c["line"]};
    color: {c["text_faint"]};
}}
QStatusBar::item {{ border: none; }}

QSplitter::handle {{ background-color: {c["line_soft"]}; }}
QSplitter::handle:hover {{ background-color: {c["accent_dim"]}; }}

QToolTip {{
    background-color: {c["surface_hi"]};
    color: {c["text"]};
    border: 1px solid {c["accent_dim"]};
    padding: 5px 7px;
}}

QFrame[role="separator"] {{ background-color: {c["line"]}; max-height: 1px; border: none; }}
QFrame[role="card"] {{
    background-color: {c["surface"]};
    border: 1px solid {c["line"]};
    border-radius: 4px;
}}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
"""


def apply_theme(app: QApplication, palette: Palette | None = None) -> None:
    """Apply a theme to an application instance.

    Fusion is forced because the native Windows and macOS styles ignore
    large parts of a stylesheet, which would leave the two platforms
    looking unlike the Linux build for no benefit.

    Passing a palette re-themes a running application; the change takes
    effect immediately because Qt re-evaluates the stylesheet on every
    widget when it is set.
    """
    if palette is not None:
        COLOURS.update(_colours_from(palette))

    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLOURS["bg"]))
    palette.setColor(QPalette.WindowText, QColor(COLOURS["text"]))
    palette.setColor(QPalette.Base, QColor(COLOURS["surface_alt"]))
    palette.setColor(QPalette.AlternateBase, QColor(COLOURS["surface"]))
    palette.setColor(QPalette.Text, QColor(COLOURS["text"]))
    palette.setColor(QPalette.Button, QColor(COLOURS["surface_alt"]))
    palette.setColor(QPalette.ButtonText, QColor(COLOURS["text"]))
    palette.setColor(QPalette.Highlight, QColor(COLOURS["accent_dim"]))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipBase, QColor(COLOURS["surface_hi"]))
    palette.setColor(QPalette.ToolTipText, QColor(COLOURS["text"]))
    palette.setColor(QPalette.PlaceholderText, QColor(COLOURS["text_faint"]))
    # Rich-text anchors otherwise render in the system blue, which
    # fights every theme.
    palette.setColor(QPalette.Link, QColor(COLOURS["accent"]))
    palette.setColor(QPalette.LinkVisited, QColor(COLOURS["accent_dim"]))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(COLOURS["text_faint"]))
    palette.setColor(
        QPalette.Disabled, QPalette.ButtonText, QColor(COLOURS["text_faint"])
    )
    app.setPalette(palette)
    app.setStyleSheet(_stylesheet())


def mono_font(point_size: int = FONT_SIZES["small"]) -> QFont:
    """Return a monospace font for fingerprints and log output."""
    font = QFont("DejaVu Sans Mono")
    font.setStyleHint(QFont.Monospace)
    font.setFixedPitch(True)
    font.setPointSize(point_size)
    return font


def colour(name: str) -> QColor:
    """Return a palette colour as a :class:`QColor`."""
    return QColor(COLOURS[name])


__all__ = ["COLOURS", "FONT_SIZES", "apply_theme", "colour", "mono_font"]
