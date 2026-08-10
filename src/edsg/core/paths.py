"""Platform-aware filesystem locations.

EDSG stores its own state (signing keys, preferences, recent paths) in the
conventional per-user configuration directory for each platform, and needs
to locate the Elite Dangerous journal directory, whose default location
differs per platform and per installation method.
"""

from __future__ import annotations

import contextlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "EDSG"
APP_DIRNAME = "edsg"

#: Folder created beside the binary to hold every event's working files.
EVENTS_DIRNAME = "Events"


def _windows_appdata() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata)
    return Path.home() / "AppData" / "Roaming"


def config_dir() -> Path:
    """Return the per-user EDSG configuration directory.

    Honours ``EDSG_CONFIG_DIR`` when set, which makes tests hermetic and
    lets users keep organizer identities on removable media.
    """
    override = os.environ.get("EDSG_CONFIG_DIR")
    if override:
        return Path(override).expanduser()

    if sys.platform == "win32":
        return _windows_appdata() / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME

    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / APP_DIRNAME


def ensure_config_dir() -> Path:
    """Create the configuration directory if needed and return it.

    On POSIX the directory is created with owner-only permissions because
    it holds private signing keys.
    """
    path = config_dir()
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        # Non-fatal if it fails; key files carry their own mode regardless.
        with contextlib.suppress(OSError):
            path.chmod(0o700)
    return path


def keys_dir() -> Path:
    """Return the directory holding signing identities."""
    return config_dir() / "keys"


def app_root() -> Path:
    """Return the directory EDSG treats as its workspace root.

    For a downloaded binary this is the folder the binary sits in, so an
    organizer can keep the executable and its events together on a stick
    or in a synced folder and have everything travel as one unit. Running
    from source it is the current working directory instead, because the
    source tree is not where anyone wants their event data.

    ``EDSG_HOME`` overrides both.
    """
    override = os.environ.get("EDSG_HOME")
    if override:
        return Path(override).expanduser()

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def events_root() -> Path:
    """Return the folder holding every event's working files."""
    return app_root() / EVENTS_DIRNAME


def safe_folder_name(name: str) -> str:
    """Turn an event name into something every filesystem accepts.

    Windows forbids ``<>:"/\\|?*`` and trailing dots or spaces; a name
    like ``Test Event #1`` also wants tidying rather than escaping.
    """
    cleaned = "".join(
        character if character.isalnum() or character in "-_ ." else "-"
        for character in name
    )
    cleaned = " ".join(cleaned.split())
    cleaned = cleaned.strip(" .-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    # Reserved device names on Windows, which cannot be used even with an
    # extension. Prefixing is enough to sidestep them.
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
    if cleaned.upper() in reserved:
        cleaned = f"event-{cleaned}"
    return cleaned[:120] or "unnamed-event"


@dataclass(frozen=True)
class EventPaths:
    """The three folders that make up one event's workspace."""

    root: Path
    invitation: Path
    submissions: Path
    standings: Path

    def create(self) -> EventPaths:
        """Create every folder, and return self for chaining."""
        for path in (self.root, self.invitation, self.submissions, self.standings):
            path.mkdir(parents=True, exist_ok=True)
        return self

    def exists(self) -> bool:
        return self.root.is_dir()


def event_paths(event_name: str) -> EventPaths:
    """Return the workspace folders for ``event_name``.

    Nothing is created; call :meth:`EventPaths.create` for that.
    """
    root = events_root() / safe_folder_name(event_name)
    return EventPaths(
        root=root,
        invitation=root / "invitation",
        submissions=root / "submissions",
        standings=root / "standings",
    )


def default_journal_dirs() -> list[Path]:
    """Return plausible Elite Dangerous journal directories for this host.

    The list is ordered by likelihood and is *not* filtered for existence;
    callers should check. Linux entries cover the common Steam Proton and
    Wine prefixes, since Elite Dangerous has no native Linux client.
    """
    home = Path.home()
    candidates: list[Path] = []

    if sys.platform == "win32":
        saved = home / "Saved Games" / "Frontier Developments" / "Elite Dangerous"
        candidates.append(saved)
        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            candidates.append(
                Path(userprofile)
                / "Saved Games"
                / "Frontier Developments"
                / "Elite Dangerous"
            )
    elif sys.platform == "darwin":
        candidates.append(
            home
            / "Library"
            / "Application Support"
            / "Frontier Developments"
            / "Elite Dangerous"
        )
    else:
        # Steam Proton default prefix for Elite Dangerous (app id 359320).
        steam_roots = [
            home / ".steam" / "steam" / "steamapps" / "compatdata",
            home / ".local" / "share" / "Steam" / "steamapps" / "compatdata",
            home
            / ".var"
            / "app"
            / "com.valvesoftware.Steam"
            / ".local"
            / "share"
            / "Steam"
            / "steamapps"
            / "compatdata",
        ]
        tail = Path("pfx") / "drive_c" / "users" / "steamuser" / "Saved Games"
        for root in steam_roots:
            candidates.append(
                root / "359320" / tail / "Frontier Developments" / "Elite Dangerous"
            )
        # Plain Wine prefix.
        candidates.append(
            home
            / ".wine"
            / "drive_c"
            / "users"
            / os.environ.get("USER", "user")
            / "Saved Games"
            / "Frontier Developments"
            / "Elite Dangerous"
        )

    return candidates


def find_journal_dir() -> Path | None:
    """Return the first existing default journal directory, if any."""
    for candidate in default_journal_dirs():
        try:
            if candidate.is_dir():
                return candidate
        except OSError:
            continue
    return None


__all__ = [
    "APP_DIRNAME",
    "APP_NAME",
    "EVENTS_DIRNAME",
    "EventPaths",
    "app_root",
    "config_dir",
    "default_journal_dirs",
    "ensure_config_dir",
    "event_paths",
    "events_root",
    "find_journal_dir",
    "keys_dir",
    "safe_folder_name",
]
