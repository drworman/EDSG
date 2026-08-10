"""Colour palettes shared by the interface and the reports.

Ported from ED Linux Dash so a commander running both tools sees one
visual identity. EDLD describes a theme with ten values; EDSG needs a few
more for report tables, and those are derived here rather than being
another thing to get wrong in a hand-written theme.

Deliberately free of any Qt import: the report writers use these too, and
the PDF writer must work in a build that has no GUI toolkit at all.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
from typing import Any

HEX_PATTERN = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


@dataclass(frozen=True)
class Palette:
    """A complete set of colours for one theme."""

    name: str
    label: str
    bg: str
    surface: str
    surface_alt: str
    line: str
    text: str
    text_dim: str
    accent: str
    accent_dim: str
    good: str
    warn: str
    bad: str
    light: bool = False

    # -- derived values -------------------------------------------------

    @property
    def text_faint(self) -> str:
        """A third text tone, between ``text_dim`` and the background."""
        return _mix(self.text_dim, self.bg, 0.35)

    @property
    def accent_soft(self) -> str:
        """A translucent accent, for table row hover."""
        red, green, blue = _to_rgb(self.accent)
        return f"rgba({red}, {green}, {blue}, 0.13)"

    @property
    def header_bg(self) -> str:
        """Background for table header rows."""
        return _mix(self.surface_alt, self.accent, 0.12)

    @property
    def header_text(self) -> str:
        """Text for table header rows.

        Header text was previously the muted body tone on a dark fill,
        which is close to unreadable at the small size headers use. It is
        now derived to keep real contrast against the header background.
        """
        return _readable_on(self.header_bg, self.text, self.bg)

    @property
    def zebra(self) -> str:
        """Alternating row background."""
        return _mix(self.surface, self.text, 0.04 if not self.light else 0.03)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def with_overrides(self, overrides: dict[str, str]) -> Palette:
        """Return a copy with individual colours replaced.

        Unknown keys and malformed values are ignored rather than raising:
        a hand-edited settings file should degrade to the built-in colour,
        not stop the application starting.
        """
        clean = {
            key: value
            for key, value in (overrides or {}).items()
            if key in CUSTOMISABLE and isinstance(value, str) and is_colour(value)
        }
        if not clean:
            return self
        # ``replace`` is typed against the declared field types, and the
        # narrowed str-only mapping does not satisfy the bool field.
        return replace(self, **clean)  # type: ignore[arg-type]


#: Fields a user may override in a custom theme.
CUSTOMISABLE = (
    "bg",
    "surface",
    "surface_alt",
    "line",
    "text",
    "text_dim",
    "accent",
    "accent_dim",
    "good",
    "warn",
    "bad",
)


def is_colour(value: str) -> bool:
    """Return whether ``value`` is a hex colour EDSG will accept."""
    return bool(HEX_PATTERN.match(value.strip()))


def _to_rgb(value: str) -> tuple[int, int, int]:
    text = value.lstrip("#")
    if len(text) == 3:
        text = "".join(char * 2 for char in text)
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def _mix(base: str, other: str, amount: float) -> str:
    """Blend ``other`` into ``base`` and return a hex colour."""
    first = _to_rgb(base)
    second = _to_rgb(other)
    blended = (round(a + (b - a) * amount) for a, b in zip(first, second, strict=True))
    return "#{:02x}{:02x}{:02x}".format(*blended)


def _relative_luminance(value: str) -> float:
    """Return WCAG relative luminance, 0 for black and 1 for white."""

    def channel(component: int) -> float:
        fraction = component / 255
        if fraction <= 0.03928:
            return fraction / 12.92
        return ((fraction + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(part) for part in _to_rgb(value))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: str, second: str) -> float:
    """Return the WCAG contrast ratio between two colours."""
    light = _relative_luminance(first)
    dark = _relative_luminance(second)
    if light < dark:
        light, dark = dark, light
    return (light + 0.05) / (dark + 0.05)


def _readable_on(background: str, *candidates: str) -> str:
    """Return the candidate with the best contrast against ``background``.

    Falls back to plain white or black when none of the candidates is
    legible, because an unreadable label is worse than an off-palette one.
    """
    best = max(candidates, key=lambda colour: contrast_ratio(background, colour))
    if contrast_ratio(background, best) >= 4.5:
        return best
    for fallback in ("#ffffff", "#000000"):
        if contrast_ratio(background, fallback) >= 4.5:
            return fallback
    return best


#: The built-in themes, matching ED Linux Dash.
PALETTES: dict[str, Palette] = {
    "default": Palette(
        name="default",
        label="Elite Orange (default)",
        bg="#120f0b",
        surface="#1c1810",
        surface_alt="#241e16",
        line="#3d2e18",
        text="#e8ddd0",
        text_dim="#a8967c",
        accent="#e07b20",
        accent_dim="#9e5614",
        good="#57e389",
        warn="#f8e45c",
        bad="#e05c5c",
    ),
    "green": Palette(
        name="green",
        label="Green",
        bg="#0b0f0d",
        surface="#141c18",
        surface_alt="#1a2420",
        line="#1e3428",
        text="#d4e4da",
        text_dim="#7d9a89",
        accent="#00aa44",
        accent_dim="#00752f",
        good="#57e389",
        warn="#f8e45c",
        bad="#e05c5c",
    ),
    "blue": Palette(
        name="blue",
        label="Blue",
        bg="#0c0e14",
        surface="#141820",
        surface_alt="#1a2030",
        line="#253050",
        text="#d0d8e8",
        text_dim="#7e8ca3",
        accent="#3d8fd4",
        accent_dim="#2a6494",
        good="#57e389",
        warn="#f8e45c",
        bad="#e05c5c",
    ),
    "purple": Palette(
        name="purple",
        label="Purple",
        bg="#0e0d14",
        surface="#17151f",
        surface_alt="#201c28",
        line="#302845",
        text="#dcd8e8",
        text_dim="#8a80a8",
        accent="#9b59b6",
        accent_dim="#6d3e80",
        good="#57e389",
        warn="#f8e45c",
        bad="#e05c5c",
    ),
    "red": Palette(
        name="red",
        label="Red",
        bg="#130e0e",
        surface="#1e1414",
        surface_alt="#261818",
        line="#452626",
        text="#e8d8d8",
        text_dim="#a88484",
        accent="#cc3333",
        accent_dim="#8f2424",
        good="#57e389",
        warn="#f8e45c",
        bad="#e05c5c",
    ),
    "yellow": Palette(
        name="yellow",
        label="Yellow",
        bg="#110f08",
        surface="#1b180e",
        surface_alt="#232014",
        line="#3f381c",
        text="#e8e2cf",
        text_dim="#a89c78",
        accent="#d4a017",
        accent_dim="#94700f",
        good="#57e389",
        warn="#f8e45c",
        bad="#e05c5c",
    ),
    "light": Palette(
        name="light",
        label="Light",
        bg="#f0f2f5",
        surface="#ffffff",
        surface_alt="#e4e8ef",
        line="#c3cad6",
        text="#1a1f27",
        text_dim="#5a6472",
        accent="#005faa",
        accent_dim="#00447a",
        good="#1e7a45",
        warn="#8a6100",
        bad="#b3261e",
        light=True,
    ),
}

DEFAULT_PALETTE = "default"


def get_palette(name: str, overrides: dict[str, str] | None = None) -> Palette:
    """Return a palette by name, with optional per-colour overrides.

    An unknown name falls back to the default rather than raising, so a
    settings file written by a newer build still opens.
    """
    base = PALETTES.get(name, PALETTES[DEFAULT_PALETTE])
    if overrides:
        return base.with_overrides(overrides)
    return base


def palette_choices() -> list[tuple[str, str]]:
    """Return ``(name, label)`` pairs for a theme picker."""
    return [(item.name, item.label) for item in PALETTES.values()]


__all__ = [
    "CUSTOMISABLE",
    "DEFAULT_PALETTE",
    "PALETTES",
    "Palette",
    "contrast_ratio",
    "get_palette",
    "is_colour",
    "palette_choices",
]
