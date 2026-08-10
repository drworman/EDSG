"""Report theming and the branding block.

Every report carries the organizer's identity in its top-left corner and
uses the palette chosen in preferences, so a squadron's standings look
like they came from that squadron rather than from a generic tool.

:class:`ReportStyle` is what the four writers receive. It is resolved
once, from settings, and passed down; nothing below reads settings for
itself, which keeps the writers testable with an explicit style.
"""

from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

from edsg.core.palettes import DEFAULT_PALETTE, Palette, get_palette
from edsg.core.settings import Branding, Settings

#: Logos larger than this are refused rather than embedded. A report is
#: meant to be mailed around; a multi-megabyte image in a self-contained
#: HTML file defeats that.
MAX_LOGO_BYTES = 2 * 1024 * 1024

#: Image types worth embedding. SVG is excluded on purpose: ReportLab
#: cannot draw it, and a logo that appears in the HTML but not the PDF is
#: worse than one that appears in neither.
LOGO_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}


@dataclass
class ReportStyle:
    """Everything the writers need to render a branded, themed report."""

    palette: Palette = field(default_factory=lambda: get_palette(DEFAULT_PALETTE))
    branding: Branding = field(default_factory=Branding)

    @classmethod
    def from_settings(cls, settings: Settings) -> ReportStyle:
        return cls(
            palette=settings.appearance.palette(),
            branding=settings.branding,
        )

    # -- logo handling --------------------------------------------------

    def logo_path(self) -> Path | None:
        """Return a usable logo path, or ``None``.

        Every reason to refuse is checked here so the writers do not each
        reimplement it: missing file, unsupported format, too large.
        """
        path = self.branding.logo()
        if path is None:
            return None
        if path.suffix.lower() not in LOGO_SUFFIXES:
            return None
        try:
            if path.stat().st_size > MAX_LOGO_BYTES:
                return None
        except OSError:
            return None
        return path

    def logo_data_uri(self) -> str:
        """Return the logo as a data URI, or an empty string.

        Embedded rather than linked because the HTML report is meant to
        stay self-contained when it is mailed or dropped on a web host.
        """
        path = self.logo_path()
        if path is None:
            return ""
        try:
            raw = path.read_bytes()
        except OSError:
            return ""
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"

    # -- branding text --------------------------------------------------

    @property
    def has_branding(self) -> bool:
        return self.branding.has_content

    def heading(self) -> str:
        """Return the squadron line, or an empty string."""
        return self.branding.title_line()

    def contact_lines(self) -> list[tuple[str, str]]:
        """Return ``(label, value)`` pairs for the branding block."""
        return [
            (item.label, item.value.strip())
            for item in self.branding.visible_contacts()
        ]


def default_style() -> ReportStyle:
    """Return the style from the current user's settings.

    Imported lazily by callers that have settings; the CLI uses this so a
    scripted close produces the same branded output as the interface.
    """
    from edsg.core.settings import load_settings

    return ReportStyle.from_settings(load_settings())


__all__ = [
    "LOGO_SUFFIXES",
    "MAX_LOGO_BYTES",
    "ReportStyle",
    "default_style",
]
