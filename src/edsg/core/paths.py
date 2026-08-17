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

#: The two binaries. Each keeps its own configuration under the shared
#: EDSG directory, because they hold different things: an organizer has a
#: signing identity whose fingerprint participants have been told to
#: trust, plus squadron branding, and a participant has neither. Mixing
#: them in one folder means copying a config between machines drags the
#: other role's identity along with it.
ROLE_ORGANIZER = "Organizer"
ROLE_PARTICIPANT = "Participant"
ROLES = (ROLE_ORGANIZER, ROLE_PARTICIPANT)

#: Set by whichever binary is running. The CLI sets it per command, and
#: each GUI entry point sets it before anything reads configuration.
_active_role: str = ROLE_ORGANIZER

#: Folder holding every event's working files, inside the workspace root.
EVENTS_DIRNAME = "Events"

#: Dropped beside a frozen binary to keep the workspace on the same drive.
PORTABLE_MARKER = "EDSG-portable.txt"

#: The three folders making up an event workspace. Numbered so they sort
#: in the order they are used: alphabetically "standings" would otherwise
#: land between "invitation" and "submissions".
INVITATION_DIRNAME = "1 - Invitation"
SUBMISSIONS_DIRNAME = "2 - Submissions"
STANDINGS_DIRNAME = "3 - Standings"


def _windows_appdata() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata)
    return Path.home() / "AppData" / "Roaming"


def set_role(role: str) -> None:
    """Record which binary is running.

    Called once at start-up, before anything reads configuration.
    """
    global _active_role
    if role not in ROLES:
        raise ValueError(f"Unknown role {role!r}; expected one of {ROLES}.")
    _active_role = role


def active_role() -> str:
    """Return the role of the running binary."""
    return _active_role


def config_root() -> Path:
    """Return the shared EDSG configuration directory.

    This is the OS-appropriate per-user location, and it is the same for
    both binaries. Per-role configuration lives in a subdirectory of it.

    ``EDSG_CONFIG_DIR`` overrides it, which makes tests hermetic and lets
    someone keep an organizer identity on removable media.
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
    # Capitalised to match the other platforms and the folder the user is
    # told to look in; XDG has no convention requiring lowercase.
    return base / APP_NAME


def config_dir(role: str | None = None) -> Path:
    """Return the configuration directory for a role.

    Defaults to the running binary's own role, so callers do not have to
    thread it through. Everything a binary saves lives here: its signing
    key, its preferences, and for the organizer its squadron details.
    """
    return config_root() / (role or _active_role)


def ensure_config_dir(role: str | None = None) -> Path:
    """Create the configuration directory if needed and return it.

    On POSIX the directory is created with owner-only permissions because
    it holds private signing keys.
    """
    path = config_dir(role)
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        # Non-fatal if it fails; key files carry their own mode regardless.
        with contextlib.suppress(OSError):
            path.chmod(0o700)
    return path


def keys_dir(role: str | None = None) -> Path:
    """Return the directory holding signing identities."""
    return config_dir(role) / "keys"


def _windows_documents() -> Path:
    """Return the Documents folder, honouring a redirected location.

    Windows lets a user (or OneDrive) move Documents elsewhere, and the
    real location lives in the registry. Assuming ``~/Documents`` puts
    files somewhere the user does not look.
    """
    try:
        # Reached through importlib and getattr because the module does
        # not exist off Windows: a direct import breaks every other
        # platform, and direct attribute access fails type-checking
        # anywhere the module is absent.
        import importlib

        winreg = importlib.import_module("winreg")
        key = (
            r"Software\Microsoft\Windows\CurrentVersion"
            r"\Explorer\User Shell Folders"
        )
        opener = winreg.OpenKey
        query = winreg.QueryValueEx
        with opener(winreg.HKEY_CURRENT_USER, key) as handle:
            raw, _ = query(handle, "Personal")
        expanded = os.path.expandvars(str(raw))
        if expanded:
            return Path(expanded)
    except (ImportError, OSError, ValueError, AttributeError):
        pass
    return Path.home() / "Documents"


def _linux_documents() -> Path:
    """Return the XDG documents directory, or ``~/Documents``."""
    configured = os.environ.get("XDG_DOCUMENTS_DIR")
    if configured:
        return Path(os.path.expandvars(configured)).expanduser()

    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    user_dirs = base / "user-dirs.dirs"
    try:
        for line in user_dirs.read_text(encoding="utf-8").splitlines():
            if not line.startswith("XDG_DOCUMENTS_DIR"):
                continue
            value = line.split("=", 1)[1].strip().strip('"')
            return Path(os.path.expandvars(value)).expanduser()
    except (OSError, IndexError):
        pass
    return Path.home() / "Documents"


def documents_dir() -> Path:
    """Return the user's Documents folder for this platform."""
    if sys.platform == "win32":
        return _windows_documents()
    if sys.platform == "darwin":
        return Path.home() / "Documents"
    return _linux_documents()


def is_portable() -> bool:
    """Return whether a portable marker sits beside the binary.

    Dropping an empty ``EDSG-portable.txt`` next to the executable keeps
    events on the same drive, which is what someone running EDSG from a
    memory stick wants.
    """
    if not getattr(sys, "frozen", False):
        return False
    marker = Path(sys.executable).resolve().parent / PORTABLE_MARKER
    try:
        return marker.is_file()
    except OSError:
        return False


def app_root() -> Path:
    """Return the directory EDSG treats as its workspace root.

    Events are the user's own documents, so they belong in Documents.
    Writing beside the executable is not safe as a default: on Windows a
    binary in Program Files cannot write to its own folder, and on macOS
    writing inside a signed ``.app`` bundle breaks its signature.

    Two escapes exist. ``EDSG_HOME`` points the workspace anywhere, and
    an ``EDSG-portable.txt`` marker beside a frozen binary keeps events
    on the same drive for stick use.
    """
    override = os.environ.get("EDSG_HOME")
    if override:
        return Path(override).expanduser()

    if is_portable():
        return Path(sys.executable).resolve().parent

    return documents_dir() / APP_NAME


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
        invitation=root / INVITATION_DIRNAME,
        submissions=root / SUBMISSIONS_DIRNAME,
        standings=root / STANDINGS_DIRNAME,
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
    "APP_NAME",
    "EVENTS_DIRNAME",
    "INVITATION_DIRNAME",
    "PORTABLE_MARKER",
    "ROLES",
    "ROLE_ORGANIZER",
    "ROLE_PARTICIPANT",
    "STANDINGS_DIRNAME",
    "SUBMISSIONS_DIRNAME",
    "EventPaths",
    "active_role",
    "app_root",
    "config_dir",
    "config_root",
    "default_journal_dirs",
    "documents_dir",
    "ensure_config_dir",
    "event_paths",
    "events_root",
    "find_journal_dir",
    "is_portable",
    "keys_dir",
    "safe_folder_name",
    "set_role",
]
