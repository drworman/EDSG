"""Settings shared by the organizer and participant builds.

Both binaries read and write one file in the per-user configuration
directory, so a commander who runs both sees the same theme without
configuring anything twice.

Nothing here is required for EDSG to work. A missing or corrupt settings
file falls back to defaults silently, because appearance preferences are
not worth refusing to start over.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from edsg.core.palettes import (
    CUSTOMISABLE,
    DEFAULT_PALETTE,
    Palette,
    get_palette,
    is_colour,
)
from edsg.core.paths import config_dir, ensure_config_dir

SETTINGS_FILENAME = "settings.json"

#: Bumped if the shape of the file changes incompatibly.
SETTINGS_VERSION = 1

#: Contact kinds offered in the preferences dialog, in display order.
CONTACT_KINDS = (
    ("discord", "Discord"),
    ("email", "Email"),
    ("website", "Website"),
    ("inara", "Inara"),
    ("other", "Other"),
)


@dataclass
class Contact:
    """One way to reach the organizer or squadron."""

    kind: str = "discord"
    value: str = ""

    @property
    def label(self) -> str:
        for key, text in CONTACT_KINDS:
            if key == self.kind:
                return text
        return self.kind.title()

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "value": self.value}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Contact:
        return cls(
            kind=str(data.get("kind", "other")),
            value=str(data.get("value", "")),
        )


@dataclass
class Branding:
    """Squadron identity printed at the head of every report."""

    squadron_name: str = ""
    squadron_tag: str = ""
    contacts: list[Contact] = field(default_factory=list)
    logo_path: str = ""

    @property
    def has_content(self) -> bool:
        return bool(
            self.squadron_name
            or self.squadron_tag
            or self.logo_path
            or any(item.value for item in self.contacts)
        )

    def title_line(self) -> str:
        """Return ``Name [TAG]``, or whichever half is set."""
        name = self.squadron_name.strip()
        tag = self.squadron_tag.strip()
        if name and tag:
            return f"{name} [{tag}]"
        return name or (f"[{tag}]" if tag else "")

    def visible_contacts(self) -> list[Contact]:
        return [item for item in self.contacts if item.value.strip()]

    def logo(self) -> Path | None:
        """Return the logo path if it exists, otherwise ``None``.

        Checked rather than trusted: a report must still generate after
        the organizer moves or deletes the image.
        """
        if not self.logo_path:
            return None
        path = Path(self.logo_path).expanduser()
        return path if path.is_file() else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "squadron_name": self.squadron_name,
            "squadron_tag": self.squadron_tag,
            "contacts": [item.to_dict() for item in self.contacts],
            "logo_path": self.logo_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Branding:
        data = data or {}
        contacts = data.get("contacts") or []
        return cls(
            squadron_name=str(data.get("squadron_name", "")),
            squadron_tag=str(data.get("squadron_tag", "")),
            contacts=[
                Contact.from_dict(item) for item in contacts if isinstance(item, dict)
            ],
            logo_path=str(data.get("logo_path", "")),
        )


@dataclass
class Appearance:
    """Theme selection, shared by the interface and the reports."""

    theme: str = DEFAULT_PALETTE
    custom_colours: dict[str, str] = field(default_factory=dict)

    def palette(self) -> Palette:
        return get_palette(self.theme, self.custom_colours)

    def to_dict(self) -> dict[str, Any]:
        return {"theme": self.theme, "custom_colours": self.custom_colours}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Appearance:
        data = data or {}
        raw = data.get("custom_colours") or {}
        colours = {
            key: value
            for key, value in raw.items()
            if key in CUSTOMISABLE and isinstance(value, str) and is_colour(value)
        }
        return cls(
            theme=str(data.get("theme", DEFAULT_PALETTE)),
            custom_colours=colours,
        )


@dataclass
class Settings:
    """Everything both binaries remember between runs."""

    appearance: Appearance = field(default_factory=Appearance)
    branding: Branding = field(default_factory=Branding)
    version: int = SETTINGS_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "appearance": self.appearance.to_dict(),
            "branding": self.branding.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Settings:
        return cls(
            appearance=Appearance.from_dict(data.get("appearance")),
            branding=Branding.from_dict(data.get("branding")),
            version=int(data.get("version", SETTINGS_VERSION)),
        )


def settings_path() -> Path:
    """Return the settings file location."""
    return config_dir() / SETTINGS_FILENAME


def load_settings() -> Settings:
    """Read the settings, falling back to defaults on any problem."""
    path = settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Settings()
    if not isinstance(data, dict):
        return Settings()
    try:
        return Settings.from_dict(data)
    except (TypeError, ValueError, AttributeError):
        return Settings()


def save_settings(settings: Settings) -> Path:
    """Write the settings, returning the path written."""
    ensure_config_dir()
    path = settings_path()
    payload = json.dumps(settings.to_dict(), indent=2, sort_keys=True)
    path.write_text(payload + "\n", encoding="utf-8")
    return path


__all__ = [
    "CONTACT_KINDS",
    "SETTINGS_FILENAME",
    "SETTINGS_VERSION",
    "Appearance",
    "Branding",
    "Contact",
    "Settings",
    "load_settings",
    "save_settings",
    "settings_path",
]
