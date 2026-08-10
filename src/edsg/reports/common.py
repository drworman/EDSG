"""Formatting helpers shared by the report writers.

Centralised so the four output formats agree on how a number, a rank or
an event summary reads. A commander comparing the Markdown and the PDF
should see identical figures.
"""

from __future__ import annotations

from edsg.core.criteria import Measure
from edsg.core.models import Eligibility, EventDefinition
from edsg.core.standings import StandingsReport

#: Medals for the top three places, used in Markdown and HTML.
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def format_points(value: float) -> str:
    """Format a point total, dropping a pointless trailing ``.0``."""
    if abs(value - round(value)) < 1e-9:
        return f"{round(value):,}"
    return f"{value:,.2f}"


def format_units(value: float, measure: Measure) -> str:
    """Format a unit total appropriately for its measure."""
    if measure is Measure.CREDITS:
        return f"{value:,.0f} cr"
    if measure is Measure.TONNAGE:
        return f"{format_points(value)} t"
    return format_points(value)


def ordinal(rank: int) -> str:
    """Return ``1st``, ``2nd``, ``3rd`` and so on."""
    if 10 <= rank % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(rank % 10, "th")
    return f"{rank}{suffix}"


def eligibility_line(event: EventDefinition) -> str:
    """Describe who was allowed to take part."""
    if event.eligibility is Eligibility.SQUADRON and event.squadron:
        return f"Restricted to squadron {event.squadron}"
    return "Open to all commanders"


def summary_lines(report: StandingsReport) -> list[tuple[str, str]]:
    """Return the label/value pairs shown in every report header."""
    event = report.event
    return [
        ("Event", event.name),
        ("Organizer", event.organizer_name or "not stated"),
        ("Event ID", event.event_id),
        ("Period", event.window.describe()),
        ("Eligibility", eligibility_line(event)),
        ("Participants ranked", str(report.participant_count)),
        ("Submissions rejected", str(len(report.rejected))),
        ("Closed", event.closed_at or "not recorded"),
        ("Report generated", report.generated_at),
        ("EDSG version", report.generator_version or "unknown"),
    ]


__all__ = [
    "MEDALS",
    "eligibility_line",
    "format_points",
    "format_units",
    "ordinal",
    "summary_lines",
]
