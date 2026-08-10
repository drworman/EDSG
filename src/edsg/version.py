"""Single source of truth for the application version.

The version string lives in a plain-text file named ``version`` at the
repository root so it can be bumped without touching any Python source.
Three lookup strategies are attempted in order, which covers development
checkouts, installed wheels and frozen PyInstaller binaries.

Versions are ``YYYYMMDD`` datestamps, matching ED Linux Dash. A release
is identified by the day it was cut, which sorts correctly as both an
integer and a string, and needs no judgement about whether a change is
"major" — a question that rarely has a clean answer for an application
whose release cadence follows someone else's game updates.

Note that this is *not* the document schema version. Compatibility
between EDSG builds is governed by ``SCHEMA_VERSION`` in
``core.models`` and ``CANONICAL_FORM`` in ``core.canonical``, both of
which are independent of the release date.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

#: Used only when every lookup strategy fails, which should not happen in
#: a correctly packaged build. Deliberately not a plausible date, so it
#: is obvious in a bug report that the version file was not found.
_FALLBACK_VERSION = "00000000"

_VERSION_FILENAME = "version"


def _candidate_paths() -> list[Path]:
    """Return possible locations of the ``version`` file, best first."""
    here = Path(__file__).resolve()
    candidates: list[Path] = []

    # 1. Frozen PyInstaller bundle: the file is added as a data file and
    #    unpacked next to the bootloader's temporary root.
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidates.append(Path(bundle_dir) / _VERSION_FILENAME)

    # 2. Installed package: the file is shipped inside the package.
    candidates.append(here.parent / _VERSION_FILENAME)

    # 3. Development checkout: src/edsg/version.py -> repository root.
    candidates.append(here.parents[2] / _VERSION_FILENAME)

    return candidates


def read_version() -> str:
    """Read and return the application version string."""
    for path in _candidate_paths():
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return _FALLBACK_VERSION


def version_tuple() -> tuple[int, int, int]:
    """Return the version as a ``(year, month, day)`` integer tuple.

    Any suffix is discarded, so ``20260810-rc1`` yields the same tuple as
    ``20260810``. An unparsable version degrades to ``(0, 0, 0)`` rather
    than raising: a malformed version file should never stop the
    application starting.
    """
    stamp = read_version().split("+", 1)[0].split("-", 1)[0].strip()
    if len(stamp) != 8 or not stamp.isdigit():
        return 0, 0, 0
    return int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8])


def version_date() -> date | None:
    """Return the release date, or ``None`` if the version is malformed.

    Useful for telling a participant that their build predates the
    invitation they have been sent.
    """
    year, month, day = version_tuple()
    try:
        return date(year, month, day)
    except ValueError:
        return None


__version__ = read_version()

__all__ = ["__version__", "read_version", "version_date", "version_tuple"]
