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
from edsg.reports.style import ReportStyle


def _escape(text: str) -> str:
    """Escape pipe characters so they cannot break a table row."""
    return str(text).replace("|", "\\|")


def build_markdown(report: StandingsReport, style: ReportStyle | None = None) -> str:
    """Render the whole report as Markdown."""
    style = style or ReportStyle()
    event = report.event
    lines: list[str] = []

    # Branding first, so a pasted report is attributable at a glance.
    if style.has_branding:
        heading = style.heading()
        if heading:
            lines.append(f"**{_escape(heading)}**")
        for label, value in style.contact_lines():
            lines.append(f"{_escape(label)}: {_escape(value)}  ")
        if lines:
            lines.append("")

    lines.extend([f"# {event.name}", ""])

    if event.description and event.description != event.name:
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

    progress = report.progress()
    if progress is not None:
        plan = progress.plan
        lines.append("## Goal progress")
        lines.append("")
        filled = round(progress.fraction * 20)
        lines.append(
            f"**{progress.tier_text}** \u2014 `"
            + "\u2588" * filled
            + "\u2591" * (20 - filled)
            + f"` {progress.fraction * 100:.2f}%"
        )
        lines.append("")
        lines.append(
            f"**{progress.total:,.0f}** of {progress.ceiling:,.0f} points from "
            f"{progress.participants} contributor(s)."
        )
        if progress.next_tier is not None:
            lines.append("")
            lines.append(
                f"{progress.to_next_tier:,.0f} more points to reach "
                f"{progress.next_tier.label}."
            )
        elif progress.goal_tiers:
            lines.append("")
            lines.append("Every goal tier reached.")
        lines.append("")

        lines.append("| Tier | Threshold | Reached |")
        lines.append("|---|---:|:---:|")
        for index, tier in enumerate(progress.goal_tiers, start=1):
            mark = "yes" if index <= progress.tiers_reached else "\u2014"
            lines.append(f"| {_escape(tier.label)} | {tier.threshold:,.0f} | {mark} |")
        lines.append("")

        lines.append("## Reward tiers")
        lines.append("")
        if progress.rewards_unlocked:
            lines.append(
                f"_{progress.tier_text} unlocks {progress.pool:,.0f} "
                f"{plan.currency} of the {plan.reward_pool:,.0f} maximum._"
            )
        elif plan.reward_pool:
            lines.append("_No rewards are paid: the goal did not reach Tier 1._")
        lines.append("")

        lines.append("| Reward tier | CMDRs | Points | Each | Tier total |")
        lines.append("|---|---:|---:|---:|---:|")
        for award in progress.awards:
            each = f"{award.each:,.0f} {plan.currency}" if award.each else "\u2014"
            subtotal = f"{award.pool:,.0f}" if award.pool else "\u2014"
            lines.append(
                f"| {_escape(award.band.label)} | {award.count} "
                f"| {_escape(award.range_text())} | {each} | {subtotal} |"
            )
        lines.append("")

        if progress.rewards_unlocked and any(award.count for award in progress.awards):
            lines.append("### Who receives what")
            lines.append("")
            lines.append("| Reward tier | Commander | Points | Receives |")
            lines.append("|---|---|---:|---:|")
            for award in progress.awards:
                for name, _fid, points in award.commanders:
                    lines.append(
                        f"| {_escape(award.band.label)} "
                        f"| CMDR {_escape(name)} | {points:,.0f} "
                        f"| {award.each:,.0f} {plan.currency} |"
                    )
            lines.append("")

        lines.append(
            "_Each commander is paid from the highest tier they reach. "
            "EDSG works the amounts out; the organizer pays them in game._"
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


def write_markdown(
    report: StandingsReport, path: Path, style: ReportStyle | None = None
) -> Path:
    """Write the Markdown report to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_markdown(report, style), encoding="utf-8")
    return path


__all__ = ["build_markdown", "write_markdown"]
