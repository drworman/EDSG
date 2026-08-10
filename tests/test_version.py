"""The version file and its parsing.

Versions are ``YYYYMMDD`` datestamps. The parsing has to degrade rather
than raise: a malformed version file should never stop the application
starting, since the version is cosmetic to almost everything it does.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from edsg import version as version_module
from edsg.version import read_version, version_date, version_tuple

#: The same shape the CI check enforces.
DATESTAMP = re.compile(
    r"^20\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(-[0-9A-Za-z.]+)?$"
)


def test_version_file_is_a_valid_datestamp():
    """Guards against a hand-edited version file breaking a release."""
    raw = read_version()
    assert DATESTAMP.match(raw), f"{raw!r} is not a YYYYMMDD datestamp"
    stamp = raw.split("-", 1)[0]
    # Must be a real calendar date, not merely a matching pattern.
    date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8]))


def test_version_file_lives_at_the_repository_root():
    root = Path(__file__).resolve().parent.parent / "version"
    assert root.is_file()
    assert root.read_text(encoding="utf-8").strip() == read_version()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("20260810", (2026, 8, 10)),
        ("20260810-rc1", (2026, 8, 10)),
        ("20260810+build.7", (2026, 8, 10)),
        ("  20260810  ", (2026, 8, 10)),
        ("0.1.0", (0, 0, 0)),
        ("2026081", (0, 0, 0)),
        ("abcdefgh", (0, 0, 0)),
        ("", (0, 0, 0)),
    ],
)
def test_version_tuple_parsing(monkeypatch, raw, expected):
    monkeypatch.setattr(version_module, "read_version", lambda: raw)
    assert version_tuple() == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("20260810", date(2026, 8, 10)),
        ("20260229", None),  # 2026 is not a leap year
        ("20261301", None),
        ("nonsense", None),
    ],
)
def test_version_date_rejects_impossible_dates(monkeypatch, raw, expected):
    monkeypatch.setattr(version_module, "read_version", lambda: raw)
    assert version_date() == expected


def test_generated_documents_carry_the_version(tmp_path, make_journal, simple_event):
    """A submission records the build that produced it."""
    from conftest import commander_events
    from edsg.core.crypto import generate_identity
    from edsg.core.workflow import issue_invitation, load_invitation, participate

    invitation = load_invitation(
        issue_invitation(simple_event, generate_identity("org"), tmp_path)
    )
    journal = make_journal(commander_events(), name="F1")
    _, submission, _ = participate(
        invitation, journal, generate_identity("p"), tmp_path / "out"
    )
    assert submission.generator_version == read_version()
