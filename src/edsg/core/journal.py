"""Reading Elite Dangerous journal files.

A journal directory contains a series of ``Journal.<timestamp>.<part>.log``
files, each a stream of newline-delimited JSON objects, one per event.
The same directory also holds live-state files such as ``Status.json``;
EDSG reads only the journals, because event scoring must be reproducible
from a fixed historical record rather than a snapshot of the present.

Robustness matters more than strictness here. A journal being written by
a running game can end in a partial line, and Frontier adds new event
types with every update. Unparsable lines are counted and skipped;
unknown events are simply carried through.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from edsg.core.errors import JournalError

#: ``Journal.2026-05-19T003353.01.log`` is the current naming; the older
#: ``Journal.190519003353.01.log`` also occurs in the wild.
#:
#: Underscores are accepted in place of the dots because files that have
#: been through a cloud sync, an upload form or an email client often
#: arrive as ``Journal_2026-05-19T003353_01.log``. Rejecting those would
#: mean silently scoring zero for a participant who sent perfectly good
#: journals, which is a far worse failure than being slightly permissive.
JOURNAL_PATTERN = re.compile(r"^Journal[._].+[._]\d+\.log$", re.IGNORECASE)

#: Events that identify the commander who owns a journal.
IDENTITY_EVENTS = ("Commander", "LoadGame", "NewCommander")


@dataclass
class JournalEntry:
    """A single parsed journal event."""

    event: str
    timestamp: datetime | None
    data: dict[str, Any]
    source: Path
    line_number: int

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def localised(self, key: str) -> str:
        """Return the localised variant of ``key`` when present.

        Frontier emits ``Type`` alongside ``Type_Localised``; the latter is
        what a human expects to read, but it is absent when the raw value
        is already display-ready.
        """
        value = self.data.get(f"{key}_Localised")
        if isinstance(value, str) and value:
            return value
        raw = self.data.get(key)
        return str(raw) if raw is not None else ""

    def name_variants(self, key: str) -> tuple[str, ...]:
        """Return every spelling of ``key`` that a filter might match.

        A commodity appears as ``lowtemperaturediamond`` in ``Type`` and
        as ``Low Temp. Diamonds`` in ``Type_Localised``. Organizers copy
        either form from wikis and third-party tools, so filters are
        matched against both.
        """
        variants: list[str] = []
        for candidate in (self.data.get(key), self.data.get(f"{key}_Localised")):
            if isinstance(candidate, str) and candidate:
                variants.append(candidate)
        return tuple(variants)

    def display_name(self, key: str) -> str:
        """Return the most human-readable spelling of ``key``.

        Falls back to title-casing the internal name so a report does not
        mix ``Low Temp. Diamonds`` with a bare ``aluminium``.
        """
        localised = self.data.get(f"{key}_Localised")
        if isinstance(localised, str) and localised:
            return localised
        raw = self.data.get(key)
        if not isinstance(raw, str) or not raw:
            return ""
        cleaned = raw.strip()
        if cleaned.startswith("$"):
            cleaned = cleaned[1:]
        if cleaned.endswith(";"):
            cleaned = cleaned[:-1]
        if cleaned.lower().endswith("_name"):
            cleaned = cleaned[: -len("_name")]
        cleaned = cleaned.replace("_", " ").strip()
        return cleaned.title() if cleaned.islower() else cleaned


@dataclass
class ReadStats:
    """Diagnostics gathered while reading a journal directory."""

    files_read: int = 0
    entries_parsed: int = 0
    malformed_lines: int = 0
    unreadable_files: list[str] = field(default_factory=list)


def parse_timestamp(value: Any) -> datetime | None:
    """Parse a journal timestamp into an aware UTC datetime."""
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def find_journal_files(directory: Path) -> list[Path]:
    """Return the journal files in ``directory``, oldest first.

    Files are ordered by name. Frontier's timestamp naming sorts
    chronologically as text, and the trailing part number keeps
    continuation files in sequence.
    """
    if not directory.is_dir():
        raise JournalError(f"Not a directory: {directory}")
    try:
        entries = [
            path
            for path in directory.iterdir()
            if path.is_file() and JOURNAL_PATTERN.match(path.name)
        ]
    except OSError as exc:
        raise JournalError(f"Could not list {directory}: {exc}") from exc
    return sorted(entries, key=lambda path: path.name)


def iter_journal_file(path: Path, stats: ReadStats) -> Iterator[JournalEntry]:
    """Yield entries from a single journal file."""
    try:
        # Frontier writes UTF-8; ``errors="replace"`` keeps a stray byte
        # from aborting an entire event's worth of scoring.
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            stats.files_read += 1
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    stats.malformed_lines += 1
                    continue
                if not isinstance(data, dict):
                    stats.malformed_lines += 1
                    continue
                event = data.get("event")
                if not isinstance(event, str):
                    stats.malformed_lines += 1
                    continue
                stats.entries_parsed += 1
                yield JournalEntry(
                    event=event,
                    timestamp=parse_timestamp(data.get("timestamp")),
                    data=data,
                    source=path,
                    line_number=line_number,
                )
    except OSError as exc:
        stats.unreadable_files.append(f"{path.name}: {exc}")


def iter_journal_dir(
    directory: Path,
    stats: ReadStats | None = None,
) -> Iterator[JournalEntry]:
    """Yield every entry from every journal file in ``directory``.

    Entries are produced in file order, which is chronological. They are
    deliberately not sorted globally: journals are already ordered, and
    buffering hundreds of thousands of events to sort them would cost
    memory for no gain.
    """
    stats = stats if stats is not None else ReadStats()
    for path in find_journal_files(directory):
        yield from iter_journal_file(path, stats)


class MultipleCommandersError(JournalError):
    """Raised when a folder holds journals for several commanders.

    Carries the candidates so a user interface can offer a choice rather
    than making the user reorganise their Saved Games folder.
    """

    def __init__(self, message: str, commanders: list[CommanderIdentity]):
        super().__init__(message)
        self.commanders = commanders


@dataclass
class CommanderIdentity:
    """The Frontier identity that owns a journal directory."""

    fid: str
    name: str

    @property
    def is_complete(self) -> bool:
        return bool(self.fid and self.name)

    def safe_filename_stem(self) -> str:
        """Return a filesystem-safe stem derived from the Frontier ID.

        Submissions are named by FID because it is the stable unique
        identifier Frontier assigns; commander names are neither unique
        nor immutable.
        """
        cleaned = "".join(ch for ch in self.fid if ch.isalnum() or ch in "-_")
        return cleaned or "unknown-cmdr"


def detect_commanders(directory: Path) -> list[CommanderIdentity]:
    """Return every distinct commander appearing in a journal directory.

    Normally this is exactly one. More than one means the directory holds
    journals for multiple accounts, which EDSG refuses to guess between.
    """
    seen: dict[str, str] = {}
    stats = ReadStats()
    for entry in iter_journal_dir(directory, stats):
        if entry.event not in IDENTITY_EVENTS:
            continue
        fid = entry.get("FID")
        name = entry.get("Name") or entry.get("Commander")
        if isinstance(fid, str) and fid and isinstance(name, str) and name:
            seen.setdefault(fid, name)
    return [CommanderIdentity(fid=fid, name=name) for fid, name in seen.items()]


def resolve_commander(directory: Path, fid: str | None = None) -> CommanderIdentity:
    """Return the commander owning ``directory``.

    Elite Dangerous writes every account on a machine into the same
    folder, so more than one commander is a normal situation rather than
    an error. When that happens the caller must say which one by passing
    ``fid``; there is no safe way to guess, because the Frontier ID is
    what a submission is attributed to.

    Raises :class:`JournalError` when no commander can be identified, or
    when several can and none was chosen.
    """
    commanders = detect_commanders(directory)
    if not commanders:
        raise JournalError(
            "No commander could be identified in that directory. Make sure "
            "it is your Elite Dangerous journal folder and contains at "
            "least one Journal.*.log file."
        )

    if fid:
        for commander in commanders:
            if commander.fid == fid:
                return commander
        names = ", ".join(f"{c.name} ({c.fid})" for c in commanders)
        raise JournalError(
            f"No journals for commander {fid} were found in that folder. "
            f"It holds journals for: {names}."
        )

    if len(commanders) > 1:
        names = ", ".join(f"{c.name} ({c.fid})" for c in commanders)
        raise MultipleCommandersError(
            f"That folder holds journals for more than one commander: "
            f"{names}. Choose which one to scan.",
            commanders=commanders,
        )
    return commanders[0]


__all__ = [
    "IDENTITY_EVENTS",
    "JOURNAL_PATTERN",
    "CommanderIdentity",
    "JournalEntry",
    "ReadStats",
    "detect_commanders",
    "find_journal_files",
    "iter_journal_dir",
    "iter_journal_file",
    "parse_timestamp",
    "resolve_commander",
]
