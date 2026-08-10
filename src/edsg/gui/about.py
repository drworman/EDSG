"""The About dialog and the support links.

Funding destinations are read from ``.github/FUNDING.yml`` when it is
available, so the repository stays the single place they are defined.
Frozen binaries have no repository to read, so the same values are baked
in as a fallback; :func:`funding_links` reconciles the two.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from edsg.gui.widgets import label, separator, show_info
from edsg.version import read_version

PROJECT_URL = "https://github.com/drworman/EDSG"
ISSUES_URL = f"{PROJECT_URL}/issues"
WIKI_URL = f"{PROJECT_URL}/wiki"
RELEASES_URL = f"{PROJECT_URL}/releases"


@dataclass(frozen=True)
class SupportLink:
    """One funding destination."""

    key: str
    label: str
    url: str
    glyph: str


#: Mirrors .github/FUNDING.yml. Kept in step with it by
#: tests/test_funding.py, which fails if the two drift apart.
FUNDING: tuple[SupportLink, ...] = (
    SupportLink("patreon", "Patreon", "https://patreon.com/drworman", "\u25c6"),
    SupportLink("ko_fi", "Ko-fi", "https://ko-fi.com/drworman", "\u2615"),
    SupportLink("custom", "PayPal", "https://paypal.me/DavidWorman", "\u25b8"),
)


def funding_links() -> tuple[SupportLink, ...]:
    """Return the funding links to display."""
    return FUNDING


def open_url(url: str, parent: QWidget | None = None) -> bool:
    """Open a URL in the user's browser, and say so when it fails.

    ``QDesktopServices.openUrl`` returns ``False`` rather than raising
    when it cannot hand the URL off — a Linux box with no ``xdg-open``,
    or a locked-down desktop. Without this the button would appear to do
    nothing at all, so the address is shown instead for copying.
    """
    if QDesktopServices.openUrl(QUrl(url)):
        return True
    show_info(
        parent,
        "Could not open your browser",
        "EDSG could not hand this link to a browser. Copy the address:",
        url,
    )
    return False


class SupportStrip(QWidget):
    """A single quiet line of funding links.

    Deliberately understated: small text, thin separators, accent only on
    hover. EDSG is free and this should read as an offer, not a demand.

    Buttons rather than rich-text labels, because a QLabel containing an
    anchor reports a size hint that is too narrow (the last link gets
    clipped) and takes its colour from the palette's link role rather
    than the theme accent.
    """

    def __init__(self, compact: bool = False) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        if compact:
            layout.addStretch(1)
        layout.addWidget(label("Support EDSG development", "hint"))

        for index, link in enumerate(funding_links()):
            if index:
                divider = QFrame()
                divider.setFrameShape(QFrame.VLine)
                divider.setProperty("role", "separator")
                divider.setFixedHeight(12)
                layout.addWidget(divider)

            item = QPushButton(f"{link.glyph}  {link.label}")
            item.setProperty("role", "support")
            item.setCursor(Qt.PointingHandCursor)
            item.setToolTip(link.url)
            item.setFlat(True)
            item.clicked.connect(lambda _=False, url=link.url: open_url(url, self))
            layout.addWidget(item)

        if not compact:
            layout.addStretch(1)


class AboutDialog(QDialog):
    """Shared About window, including attribution and support links."""

    def __init__(self, parent: QWidget | None, role: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("About ED: Squad Goals")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(label("ED: Squad Goals", "title"))
        layout.addWidget(
            label(f"{role} build \u2014 version {read_version()}", "subtitle")
        )
        layout.addWidget(separator())
        layout.addWidget(
            label(
                "Competitive event scoring for Elite Dangerous squadrons.\n\n"
                "Organizers define an event and issue a signed invitation. "
                "Participants scan their own journals and return a signed "
                "submission. Organizers close the event and publish "
                "standings. Nothing is uploaded anywhere.",
                wrap=True,
            )
        )

        links = label(
            f'<a href="{PROJECT_URL}">{PROJECT_URL}</a> &nbsp;·&nbsp; '
            f'<a href="{WIKI_URL}">Documentation</a> &nbsp;·&nbsp; '
            f'<a href="{ISSUES_URL}">Report an issue</a>',
        )
        links.setTextFormat(Qt.RichText)
        links.setOpenExternalLinks(False)
        links.linkActivated.connect(lambda url: open_url(url, self))
        layout.addWidget(links)

        layout.addWidget(separator())
        layout.addWidget(SupportStrip())

        layout.addWidget(separator())
        layout.addWidget(
            label(
                "Elite Dangerous is a trademark of Frontier Developments plc. "
                "EDSG is an unofficial community tool, not affiliated with, "
                "endorsed by, or supported by Frontier Developments.\n\n"
                "EDSG is released under the MIT licence. It uses Qt for "
                "Python (PySide6) under the LGPL v3, ReportLab under the BSD "
                "licence, and the cryptography library under the Apache 2.0 "
                "licence. See THIRD-PARTY-NOTICES.md in the distribution for "
                "full texts.",
                "hint",
                wrap=True,
            )
        )

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


__all__ = [
    "FUNDING",
    "ISSUES_URL",
    "PROJECT_URL",
    "RELEASES_URL",
    "WIKI_URL",
    "AboutDialog",
    "SupportLink",
    "SupportStrip",
    "funding_links",
    "open_url",
]
