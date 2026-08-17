"""Checking typed system and station names against Spansh.

A misspelled filter scores zero in silence, and because an invitation is
signed there is no correcting it afterwards without reissuing and asking
everyone to rescan. This module exists to catch that before the event
goes out.

It is **advisory only**. Every failure — no network, a timeout, a rate
limit, an unparsable reply — is treated as "cannot say", never as "that
name is wrong". Scoring never consults it, and an organizer can always
proceed past a warning: Spansh does not know about a system nobody has
reported yet, and being wrong about a real name must not block an event.

The client follows the shape used in ED Linux Dash: the public typeahead
endpoint, no API key, stdlib only, short timeout.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from enum import StrEnum

#: Public typeahead endpoint. No key, no account.
SPANSH_SEARCH = "https://spansh.co.uk/api/search"

#: Kept short. This runs while an organizer waits on a dialog.
TIMEOUT_SECONDS = 8

#: Spansh ignores very short queries, and so do we.
MIN_QUERY = 3

USER_AGENT = "EDSG (github.com/drworman/EDSG)"


class Verdict(StrEnum):
    """What a lookup concluded about one name."""

    #: Spansh returned this exact name.
    EXACT = "exact"
    #: Nothing matched exactly, but close names came back.
    NEAR = "near"
    #: Spansh answered and knew nothing resembling it.
    UNKNOWN = "unknown"
    #: The lookup could not be completed. Says nothing about the name.
    UNAVAILABLE = "unavailable"
    #: Too short to ask about.
    SKIPPED = "skipped"


@dataclass
class NameCheck:
    """The outcome of checking one typed name."""

    query: str
    kind: str
    verdict: Verdict
    suggestions: list[str] = field(default_factory=list)
    detail: str = ""

    @property
    def is_problem(self) -> bool:
        """Return whether this is worth showing the organizer.

        Only a confident answer counts. An unreachable Spansh is not a
        problem with the organizer's spelling.
        """
        return self.verdict in (Verdict.NEAR, Verdict.UNKNOWN)

    def message(self) -> str:
        """Return a line an organizer can act on."""
        if self.verdict is Verdict.EXACT:
            return f"{self.kind} '{self.query}' found."
        if self.verdict is Verdict.NEAR:
            names = ", ".join(self.suggestions[:3])
            return (
                f"No {self.kind.lower()} is named exactly '{self.query}'. "
                f"Did you mean: {names}?"
            )
        if self.verdict is Verdict.UNKNOWN:
            return (
                f"Spansh knows no {self.kind.lower()} resembling "
                f"'{self.query}'. Check the spelling."
            )
        if self.verdict is Verdict.UNAVAILABLE:
            return f"Could not check '{self.query}': {self.detail}"
        return f"'{self.query}' is too short to check."


def _normalise(value: str) -> str:
    """Fold a name for comparison, ignoring case and punctuation."""
    return "".join(character for character in value.lower() if character.isalnum())


def _query_spansh(query: str) -> list[dict]:
    """Return raw Spansh results, raising on any failure."""
    params = urllib.parse.urlencode({"q": query})
    request = urllib.request.Request(
        f"{SPANSH_SEARCH}?{params}", headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        payload = json.load(response)
    results = payload.get("results")
    return results if isinstance(results, list) else []


def check_name(query: str, wanted: str) -> NameCheck:
    """Check one name against Spansh.

    ``wanted`` is ``"system"`` or ``"station"``, matching the ``type``
    Spansh reports for each result.
    """
    kind = wanted.capitalize()
    query = query.strip()
    if len(query) < MIN_QUERY:
        return NameCheck(query=query, kind=kind, verdict=Verdict.SKIPPED)

    try:
        results = _query_spansh(query)
    except urllib.error.HTTPError as exc:
        return NameCheck(
            query=query,
            kind=kind,
            verdict=Verdict.UNAVAILABLE,
            detail=f"Spansh replied {exc.code}",
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return NameCheck(
            query=query,
            kind=kind,
            verdict=Verdict.UNAVAILABLE,
            detail=f"no answer from Spansh ({exc.__class__.__name__})",
        )
    except (ValueError, json.JSONDecodeError):
        return NameCheck(
            query=query,
            kind=kind,
            verdict=Verdict.UNAVAILABLE,
            detail="Spansh sent something unreadable",
        )

    names: list[str] = []
    for item in results:
        if not isinstance(item, dict) or item.get("type") != wanted:
            continue
        record = item.get("record") or {}
        name = str(record.get("name", "")).strip()
        if name:
            names.append(name)

    target = _normalise(query)
    if any(_normalise(name) == target for name in names):
        return NameCheck(query=query, kind=kind, verdict=Verdict.EXACT)
    if names:
        return NameCheck(
            query=query,
            kind=kind,
            verdict=Verdict.NEAR,
            suggestions=names[:5],
        )
    return NameCheck(query=query, kind=kind, verdict=Verdict.UNKNOWN)


def check_names(systems: list[str], stations: list[str]) -> list[NameCheck]:
    """Check several names, returning one result each.

    Called from a background thread: each name is a separate request and
    the whole set can take a few seconds.
    """
    checks: list[NameCheck] = []
    for name in systems:
        checks.append(check_name(name, "system"))
    for name in stations:
        checks.append(check_name(name, "station"))
    return checks


def summarise(checks: list[NameCheck]) -> tuple[list[NameCheck], bool]:
    """Return the problems, and whether the service answered at all.

    The second value distinguishes "everything checked out" from "nothing
    could be checked", which read the same otherwise.
    """
    answered = any(
        item.verdict in (Verdict.EXACT, Verdict.NEAR, Verdict.UNKNOWN)
        for item in checks
    )
    return [item for item in checks if item.is_problem], answered


__all__ = [
    "MIN_QUERY",
    "SPANSH_SEARCH",
    "TIMEOUT_SECONDS",
    "NameCheck",
    "Verdict",
    "check_name",
    "check_names",
    "summarise",
]
