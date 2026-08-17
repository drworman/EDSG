"""The menu bar shared by both applications.

Kept in one place so the organizer and participant offer the same File,
Options and Help menus, with only the file actions differing.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow, QMenu

from edsg.core.paths import app_root, config_dir
from edsg.gui.about import (
    ISSUES_URL,
    PROJECT_URL,
    RELEASES_URL,
    WIKI_URL,
    AboutDialog,
    funding_links,
    open_url,
)
from edsg.gui.widgets import open_path


def _action(
    window: QMainWindow,
    text: str,
    slot: Callable[[], object],
    shortcut: str = "",
    tip: str = "",
) -> QAction:
    action = QAction(text, window)
    if shortcut:
        action.setShortcut(QKeySequence(shortcut))
    if tip:
        action.setStatusTip(tip)
    action.triggered.connect(slot)
    return action


def build_menus(
    window: QMainWindow,
    role: str,
    file_actions: list[QAction | None] | None = None,
    on_preferences: Callable[[], object] | None = None,
) -> None:
    """Attach the standard menu bar to ``window``.

    ``file_actions`` are inserted at the top of the File menu; a ``None``
    entry becomes a separator. Everything else is identical between the
    two builds.

    Menu ownership needs both halves of the story. Each menu is built
    with the window as its parent, so the C++ object belongs to the
    window, and each is also kept in a list on the window so the Python
    wrapper stays alive. PySide6 hands out a wrapper every time something
    calls ``QAction.menu()``, and letting the last one go destroys the
    menu underneath the others — which is how a Help menu ends up empty
    long after it was built.
    """
    bar = window.menuBar()

    owned: list[QMenu] = []
    window._edsg_menus = owned

    file_menu = QMenu("&File", window)
    owned.append(file_menu)
    bar.addMenu(file_menu)
    for item in file_actions or []:
        if item is None:
            file_menu.addSeparator()
        else:
            file_menu.addAction(item)
    if file_actions:
        file_menu.addSeparator()
    file_menu.addAction(
        _action(
            window,
            "Open &workspace folder",
            lambda: open_path(app_root()),
            tip="The folder EDSG saves events into",
        )
    )
    file_menu.addAction(
        _action(
            window,
            "Open &settings folder",
            lambda: open_path(config_dir()),
            tip="Preferences and signing keys",
        )
    )
    file_menu.addSeparator()
    file_menu.addAction(_action(window, "&Quit", window.close, "Ctrl+Q"))

    options_menu = QMenu("&Options", window)
    owned.append(options_menu)
    bar.addMenu(options_menu)
    if on_preferences is not None:
        options_menu.addAction(
            _action(
                window,
                "&Preferences\u2026",
                on_preferences,
                "Ctrl+,",
                tip="Theme, colours and squadron branding",
            )
        )

    help_menu = QMenu("&Help", window)
    owned.append(help_menu)
    bar.addMenu(help_menu)
    help_menu.addAction(
        _action(
            window,
            "&Documentation",
            lambda: open_url(WIKI_URL, window),
            "F1",
            tip="Open the EDSG documentation in your browser",
        )
    )
    help_menu.addAction(
        _action(window, "Project on &GitHub", lambda: open_url(PROJECT_URL, window))
    )
    help_menu.addAction(
        _action(window, "&Report an issue", lambda: open_url(ISSUES_URL, window))
    )
    help_menu.addAction(
        _action(window, "Check for &releases", lambda: open_url(RELEASES_URL, window))
    )
    help_menu.addSeparator()

    support_menu = QMenu("&Support EDSG development", window)
    support_menu.setStatusTip("EDSG is free; these help keep it maintained")
    owned.append(support_menu)
    help_menu.addMenu(support_menu)
    for link in funding_links():
        support_menu.addAction(
            _action(window, link.label, lambda url=link.url: open_url(url, window))
        )

    help_menu.addSeparator()
    help_menu.addAction(
        _action(
            window,
            "&About EDSG",
            lambda: AboutDialog(window, role).exec(),
            tip="Version, licence and project links",
        )
    )


__all__ = ["build_menus"]
