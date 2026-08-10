"""Markdown standings output.

Written to paste straight into Discord, a forum post or a squadron wiki,
so tables are kept narrow and no HTML is embedded.
"""

from __future__ import annotations

from pathlib import Path

from edsg.core.standings import StandingsReport
from edsg.reports.common import (
    MEDALS,
    format_points,
    format_units,
    summary_lines,
)


def _escape(text: str) -> str:
    """Escape pipe characters so they cannot break a table row."""
    return str(text).replace("|", "\\|")


def build_markdown(report: StandingsReport) -> str:
    """Render the whole report as Markdown."""
    event = report.event
    lines: list[str] = [f"# {event.name}", ""]

    if event.description:
        lines.extend([event.description, ""])

    lines.append("## Event summary")
    lines.append("")
    lines.append("| | |")
    lines.append("|---|---|")
    for label, value in summary_lines(report):
        lines.append(f"| **{_escape(label)}** | {_escape(value)} |")
    lines.append("")

    lines.append("## Scoring criteria")
    lines.append("")
    lines.append("| # | Criterion | Rule |")
    lines.append("|---:|---|---|")
    for index, criterion in enumerate(event.criteria, start=1):
        lines.append(
            f"| {index} | {_escape(criterion.label)} "
            f"| {_escape(criterion.describe())} |"
        )
    lines.append("")

    lines.append("## Standings")
    lines.append("")
    if not report.standings:
        lines.append("_No eligible submissions were received._")
        lines.append("")
    else:
        header = ["Rank", "Commander", "Points"]
        header.extend(criterion.label for criterion in event.criteria)
        alignment = ["---:", "---", "---:"] + ["---:"] * len(event.criteria)
        lines.append("| " + " | ".join(_escape(item) for item in header) + " |")
        lines.append("|" + "|".join(alignment) + "|")

        for standing in report.standings:
            medal = MEDALS.get(standing.rank, "")
            rank_cell = f"{medal} {standing.rank}".strip()
            if standing.tied:
                rank_cell += " ="
            row = [
                rank_cell,
                f"CMDR {_escape(standing.commander_name)}",
                format_points(standing.total_points),
            ]
            for criterion in event.criteria:
                points = standing.per_criterion.get(criterion.criterion_id, 0.0)
                units = standing.per_criterion_units.get(criterion.criterion_id, 0.0)
                row.append(
                    f"{format_points(points)}"
                    f"<br><sub>{format_units(units, criterion.measure)}</sub>"
                )
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    if report.rejected:
        lines.append("## Rejected submissions")
        lines.append("")
        lines.append("| File | Commander | Reason |")
        lines.append("|---|---|---|")
        for item in report.rejected:
            commander = item.submission.commander_name if item.submission else "unknown"
            lines.append(
                f"| `{_escape(item.path.name)}` | {_escape(commander)} "
                f"| {_escape(item.rejection)} |"
            )
        lines.append("")

    lines.append("## Submission audit")
    lines.append("")
    lines.append("| Commander | Frontier ID | Signed by | Generated | Journal events |")
    lines.append("|---|---|---|---|---:|")
    for item in report.accepted:
        submission = item.submission
        if submission is None:
            continue
        lines.append(
            f"| CMDR {_escape(submission.commander_name)} "
            f"| `{_escape(submission.commander_fid)}` "
            f"| `{_escape(item.signer_fingerprint)}` "
            f"| {_escape(submission.generated_at)} "
            f"| {submission.scan.entries_parsed:,} |"
        )
    lines.append("")
    lines.append(
        "_Signatures confirm each file is unchanged since the participant "
        "generated it. They do not attest to the contents of the "
        "underlying journal files._"
    )
    lines.append("")

    return "\n".join(lines)


def write_markdown(report: StandingsReport, path: Path) -> Path:
    """Write the Markdown report to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_markdown(report), encoding="utf-8")
    return path


__all__ = ["build_markdown", "write_markdown"]
