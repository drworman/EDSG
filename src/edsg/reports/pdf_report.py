"""PDF standings output.

Built with ReportLab's platypus layer, which is pure Python and bundles
into a PyInstaller binary without native dependencies.

The standings table widens with every criterion, so the page is
landscape and column widths are computed from the count rather than
fixed. Past roughly eight criteria the per-criterion columns are dropped
and only totals are shown, because an unreadable table helps nobody.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from edsg.core.numbers import plain
from edsg.core.standings import StandingsReport
from edsg.reports.common import format_points, format_units, summary_lines
from edsg.reports.style import ReportStyle

#: Beyond this many criteria the detail columns are omitted.
MAX_DETAIL_COLUMNS = 8

#: The PDF prints on white regardless of the chosen theme — a dark
#: report wastes a cartridge and reads badly on paper. The theme supplies
#: the accent and the header tone; everything else is print-appropriate.
PAPER_TEXT = colors.HexColor("#1a1f27")
PAPER_MUTED = colors.HexColor("#55606e")
ROW_ALT = colors.HexColor("#f4f5f7")
LINE = colors.HexColor("#c9ced6")


def _accent(style: ReportStyle) -> colors.Color:
    """Return the theme accent, darkened if it would be faint on white."""
    accent = colors.HexColor(style.palette.accent)
    # Yellows and light blues vanish against paper; nudge them darker
    # until they carry against white.
    while _luminance(accent) > 0.45:
        accent = colors.Color(
            accent.red * 0.82, accent.green * 0.82, accent.blue * 0.82
        )
    return accent


def _luminance(colour: colors.Color) -> float:
    return 0.2126 * colour.red + 0.7152 * colour.green + 0.0722 * colour.blue


def _styles(accent: colors.Color) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "EDSGTitle",
            parent=base["Title"],
            fontSize=20,
            leading=24,
            alignment=TA_LEFT,
            textColor=accent,
            spaceAfter=2,
        ),
        "tagline": ParagraphStyle(
            "EDSGTagline",
            parent=base["Normal"],
            fontSize=9.5,
            leading=13,
            textColor=PAPER_MUTED,
            spaceAfter=10,
        ),
        "heading": ParagraphStyle(
            "EDSGHeading",
            parent=base["Heading2"],
            fontSize=12,
            leading=15,
            textColor=accent,
            spaceBefore=14,
            spaceAfter=6,
        ),
        "cell": ParagraphStyle(
            "EDSGCell", parent=base["Normal"], fontSize=8, leading=10
        ),
        "cell_small": ParagraphStyle(
            "EDSGCellSmall",
            parent=base["Normal"],
            fontSize=7,
            leading=9,
            textColor=PAPER_MUTED,
        ),
        "brand": ParagraphStyle(
            "EDSGBrand",
            parent=base["Normal"],
            fontSize=10,
            leading=13,
            textColor=PAPER_TEXT,
            spaceAfter=1,
        ),
        "footer": ParagraphStyle(
            "EDSGFooter",
            parent=base["Normal"],
            fontSize=7.5,
            leading=10,
            textColor=PAPER_MUTED,
        ),
    }


def _table_style(accent: colors.Color, header_rows: int = 1) -> TableStyle:
    header_bg = colors.Color(
        1 - (1 - accent.red) * 0.16,
        1 - (1 - accent.green) * 0.16,
        1 - (1 - accent.blue) * 0.16,
    )
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, header_rows - 1), header_bg),
            ("TEXTCOLOR", (0, 0), (-1, header_rows - 1), PAPER_TEXT),
            ("LINEBELOW", (0, header_rows - 1), (-1, header_rows - 1), 1.1, accent),
            ("FONTNAME", (0, 0), (-1, header_rows - 1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.4, LINE),
            ("ROWBACKGROUNDS", (0, header_rows), (-1, -1), [colors.white, ROW_ALT]),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
    )


def _summary_flowables(report: StandingsReport, styles, accent) -> list:
    rows = [
        [
            Paragraph(f"<b>{label}</b>", styles["cell"]),
            Paragraph(value, styles["cell"]),
        ]
        for label, value in summary_lines(report)
    ]
    table = Table(rows, colWidths=[45 * mm, 150 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, ROW_ALT]),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return [Paragraph("Event summary", styles["heading"]), table]


def _criteria_flowables(report: StandingsReport, styles, accent) -> list:
    rows = [
        [
            Paragraph("<b>#</b>", styles["cell"]),
            Paragraph("<b>Criterion</b>", styles["cell"]),
            Paragraph("<b>Rule</b>", styles["cell"]),
        ]
    ]
    for index, criterion in enumerate(report.event.criteria, start=1):
        rows.append(
            [
                Paragraph(str(index), styles["cell"]),
                Paragraph(criterion.label, styles["cell"]),
                Paragraph(criterion.describe(), styles["cell_small"]),
            ]
        )
    table = Table(rows, colWidths=[10 * mm, 55 * mm, 195 * mm], hAlign="LEFT")
    table.setStyle(_table_style(accent))
    return [Paragraph("Scoring criteria", styles["heading"]), table]


def _progress_flowables(report: StandingsReport, styles, accent) -> list:
    """Render the goal-tier board for print.

    The meter is drawn as a one-row table with two cells rather than a
    graphic, so it prints cleanly in black and white and needs no image
    support.
    """
    progress = report.progress()
    if progress is None:
        return []

    plan = progress.plan
    flowables: list = [Paragraph("Goal progress", styles["heading"])]

    headline = (
        f"<b>{escape(progress.tier_text)}</b> &nbsp;&nbsp; "
        f"<b>{progress.total:,.0f}</b> of {progress.ceiling:,.0f} points "
        f"&nbsp;&nbsp; {progress.fraction * 100:.2f}% &nbsp;&nbsp; "
        f"{progress.participants} contributor(s)"
    )
    flowables.append(Paragraph(headline, styles["cell"]))
    flowables.append(Spacer(1, 4))

    # A two-cell bar: filled portion, then the remainder.
    total_width = 250 * mm
    filled = max(0.0, min(1.0, progress.fraction))
    if 0 < filled < 1:
        widths = [total_width * filled, total_width * (1 - filled)]
        cells = [["", ""]]
    elif filled >= 1:
        widths, cells = [total_width], [[""]]
    else:
        widths, cells = [total_width], [[""]]

    meter = Table(cells, colWidths=widths, rowHeights=[6 * mm], hAlign="LEFT")
    meter_style = [
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if filled > 0:
        meter_style.append(("BACKGROUND", (0, 0), (0, 0), accent))
    if 0 < filled < 1:
        meter_style.append(("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#e9ecf0")))
    meter.setStyle(TableStyle(meter_style))
    flowables.append(meter)
    flowables.append(Spacer(1, 6))

    if progress.next_tier is not None:
        note = (
            f"{progress.to_next_tier:,.0f} more points to reach "
            f"{escape(progress.next_tier.label)}."
        )
    elif progress.goal_tiers:
        note = "Every goal tier reached."
    else:
        note = ""
    if progress.rewards_unlocked:
        note += (
            f" {escape(progress.tier_text)} unlocks {progress.pool:,.0f} "
            f"{escape(plan.currency)} of the {plan.reward_pool:,.0f} maximum."
        )
    elif plan.reward_pool:
        note += " No rewards are paid: the goal did not reach Tier 1."
    if note:
        flowables.append(Paragraph(note, styles["cell_small"]))
        flowables.append(Spacer(1, 6))

    rows = [
        [
            Paragraph("<b>Tier</b>", styles["cell"]),
            Paragraph("<b>Threshold</b>", styles["cell"]),
            Paragraph("<b>Reached</b>", styles["cell"]),
        ]
    ]
    # Listed highest first: a squadron climbs toward the top tier, so
    # reading downward should be reading back down the ladder.
    for index, tier in reversed(list(enumerate(progress.goal_tiers, start=1))):
        reached = "reached" if index <= progress.tiers_reached else "\u2014"
        rows.append(
            [
                Paragraph(escape(tier.label), styles["cell"]),
                Paragraph(plain(tier.threshold, 0), styles["cell"]),
                Paragraph(reached, styles["cell"]),
            ]
        )
    table = Table(rows, colWidths=[40 * mm, 45 * mm, 30 * mm], hAlign="LEFT")
    table.setStyle(_table_style(accent))
    flowables.append(table)

    return flowables


def _rewards_flowables(report: StandingsReport, styles, accent) -> list:
    """Render who is owed what, on its own page."""
    progress = report.progress()
    if progress is None or not progress.plan.reward_pool:
        return []

    plan = progress.plan
    flowables: list = []
    flowables.append(Paragraph("Rewards", styles["heading"]))
    if not progress.rewards_unlocked:
        flowables.append(
            Paragraph(
                "No rewards are due: the goal did not reach Tier 1.",
                styles["cell"],
            )
        )
        return flowables

    reward_rows = [
        [
            Paragraph("<b>Rank</b>", styles["cell"]),
            Paragraph("<b>Commander</b>", styles["cell"]),
            Paragraph("<b>Points</b>", styles["cell"]),
            Paragraph("<b>Share</b>", styles["cell"]),
            Paragraph("<b>Receives</b>", styles["cell"]),
        ]
    ]
    for item in progress.payouts:
        marker = " *" if item.in_top else ""
        reward_rows.append(
            [
                Paragraph(f"{item.rank}{marker}", styles["cell"]),
                Paragraph(escape(item.commander_name), styles["cell"]),
                Paragraph(f"{item.points:,.0f}", styles["cell"]),
                Paragraph(f"{item.share * 100:.2f}%", styles["cell"]),
                Paragraph(
                    f"{item.total:,.0f} {escape(plan.currency)}",
                    styles["cell"],
                ),
            ]
        )
    reward = Table(
        reward_rows,
        colWidths=[18 * mm, 60 * mm, 28 * mm, 22 * mm, 45 * mm],
        hAlign="LEFT",
    )
    reward.setStyle(_table_style(accent))
    flowables.append(reward)
    flowables.append(Spacer(1, 4))
    flowables.append(
        Paragraph(
            f"{progress.paid_total:,.0f} {escape(plan.currency)} in total, "
            f"from {progress.pool:,.0f} unlocked at "
            f"{escape(progress.tier_text)}. A star marks the top group "
            f"sharing the bonus; commanders on equal points share a rank "
            f"and are paid alike. Paid in game by the organizer.",
            styles["cell_small"],
        )
    )
    return flowables


def _standings_flowables(report: StandingsReport, styles, accent) -> list:
    event = report.event
    flowables = [Paragraph("Standings", styles["heading"])]

    if not report.standings:
        flowables.append(
            Paragraph("No eligible submissions were received.", styles["cell"])
        )
        return flowables

    show_detail = len(event.criteria) <= MAX_DETAIL_COLUMNS
    header = [
        Paragraph("<b>Rank</b>", styles["cell"]),
        Paragraph("<b>Commander</b>", styles["cell"]),
        Paragraph("<b>Points</b>", styles["cell"]),
    ]
    if show_detail:
        header.extend(
            Paragraph(f"<b>{criterion.label}</b>", styles["cell"])
            for criterion in event.criteria
        )

    rows = [header]
    for standing in report.standings:
        tie = " =" if standing.tied else ""
        cells = [
            Paragraph(f"<b>{standing.rank}{tie}</b>", styles["cell"]),
            Paragraph(
                f"CMDR {standing.commander_name}<br/>"
                f"<font size=6 color='#6b7480'>{standing.commander_fid}</font>",
                styles["cell"],
            ),
            Paragraph(f"<b>{format_points(standing.total_points)}</b>", styles["cell"]),
        ]
        if show_detail:
            for criterion in event.criteria:
                points = standing.per_criterion.get(criterion.criterion_id, 0.0)
                units = standing.per_criterion_units.get(criterion.criterion_id, 0.0)
                cells.append(
                    Paragraph(
                        f"{format_points(points)}<br/>"
                        f"<font size=6 color='#6b7480'>"
                        f"{format_units(units, criterion.measure)}</font>",
                        styles["cell"],
                    )
                )
        rows.append(cells)

    available = 260 * mm
    if show_detail and event.criteria:
        fixed = 16 * mm + 45 * mm + 20 * mm
        each = max(16 * mm, (available - fixed) / len(event.criteria))
        widths = [16 * mm, 45 * mm, 20 * mm] + [each] * len(event.criteria)
    else:
        widths = [20 * mm, 90 * mm, 30 * mm]

    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(_table_style(accent))
    flowables.append(table)

    if not show_detail:
        flowables.append(Spacer(1, 4))
        flowables.append(
            Paragraph(
                f"This event has {len(event.criteria)} criteria, too many to "
                f"tabulate legibly. Per-criterion figures are in the JSON "
                f"and HTML reports.",
                styles["cell_small"],
            )
        )
    return flowables


def _rejected_flowables(report: StandingsReport, styles, accent) -> list:
    if not report.rejected:
        return []
    rows = [
        [
            Paragraph("<b>File</b>", styles["cell"]),
            Paragraph("<b>Commander</b>", styles["cell"]),
            Paragraph("<b>Reason</b>", styles["cell"]),
        ]
    ]
    for item in report.rejected:
        commander = item.submission.commander_name if item.submission else "unknown"
        rows.append(
            [
                Paragraph(item.path.name, styles["cell_small"]),
                Paragraph(commander, styles["cell"]),
                Paragraph(item.rejection, styles["cell_small"]),
            ]
        )
    table = Table(rows, colWidths=[60 * mm, 50 * mm, 150 * mm], hAlign="LEFT")
    table.setStyle(_table_style(accent))
    return [Paragraph("Rejected submissions", styles["heading"]), table]


def _audit_flowables(report: StandingsReport, styles, accent) -> list:
    rows = [
        [
            Paragraph("<b>Commander</b>", styles["cell"]),
            Paragraph("<b>Frontier ID</b>", styles["cell"]),
            Paragraph("<b>Signing key</b>", styles["cell"]),
            Paragraph("<b>Generated</b>", styles["cell"]),
            Paragraph("<b>Events</b>", styles["cell"]),
        ]
    ]
    for item in report.accepted:
        submission = item.submission
        if submission is None:
            continue
        rows.append(
            [
                Paragraph(f"CMDR {submission.commander_name}", styles["cell"]),
                Paragraph(submission.commander_fid, styles["cell_small"]),
                Paragraph(item.signer_fingerprint, styles["cell_small"]),
                Paragraph(submission.generated_at, styles["cell_small"]),
                Paragraph(f"{submission.scan.entries_parsed:,}", styles["cell"]),
            ]
        )
    table = Table(
        rows,
        colWidths=[55 * mm, 32 * mm, 78 * mm, 55 * mm, 25 * mm],
        hAlign="LEFT",
    )
    table.setStyle(_table_style(accent))
    note = Paragraph(
        "Signatures confirm each file is unchanged since the participant "
        "generated it. They do not attest to the contents of the underlying "
        "journal files.",
        styles["cell_small"],
    )
    return [Paragraph("Submission audit", styles["heading"]), table, Spacer(1, 4), note]


def _masthead(style: ReportStyle, styles, accent) -> list:
    """Return the branding block, or nothing when none is configured."""
    if not style.has_branding:
        return []

    left: list = []
    logo = style.logo_path()
    if logo is not None:
        try:
            image = Image(str(logo))
            ratio = image.imageHeight / float(image.imageWidth or 1)
            image.drawWidth = min(45 * mm, image.imageWidth * 0.75)
            image.drawHeight = image.drawWidth * ratio
            if image.drawHeight > 20 * mm:
                image.drawHeight = 20 * mm
                image.drawWidth = image.drawHeight / (ratio or 1)
            image.hAlign = "LEFT"
            left.append(image)
        except Exception:
            pass

    heading = style.heading()
    if heading:
        left.append(Paragraph(f"<b>{escape(heading)}</b>", styles["brand"]))
    for label, value in style.contact_lines():
        left.append(
            Paragraph(
                f'<font color="#6b7480">{escape(label)}</font>&nbsp;{escape(value)}',
                styles["cell_small"],
            )
        )
    if not left:
        return []

    table = Table([[left]], colWidths=[120 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, accent),
            ]
        )
    )
    return [table, Spacer(1, 8)]


def _footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#6b7480"))
    width, _ = landscape(A4)
    canvas.drawString(
        15 * mm,
        10 * mm,
        "Generated by ED: Squad Goals — unofficial community tool, not "
        "affiliated with Frontier Developments.",
    )
    canvas.drawRightString(width - 15 * mm, 10 * mm, f"Page {document.page}")
    canvas.restoreState()


def write_pdf(
    report: StandingsReport, path: Path, style: ReportStyle | None = None
) -> Path:
    """Write the PDF report to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    style = style or ReportStyle()
    accent = _accent(style)
    styles = _styles(accent)
    event = report.event

    document = SimpleDocTemplate(
        str(path),
        pagesize=landscape(A4),
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=f"{event.name} — EDSG standings",
        author=event.organizer_name or "ED: Squad Goals",
        subject="Elite Dangerous event standings",
    )

    story: list = _masthead(style, styles, accent)
    story.append(Paragraph(escape(event.name), styles["title"]))
    if event.description and event.description != event.name:
        story.append(Paragraph(escape(event.description), styles["tagline"]))

    # One subject per page, in the order somebody reads the report:
    # what the event was, how the goal went, who is owed what, then the
    # standings and the supporting detail. Each section starts on a
    # fresh page so a printed copy can be handed round in parts.
    story.extend(_summary_flowables(report, styles, accent))
    story.extend(_criteria_flowables(report, styles, accent))

    progress = _progress_flowables(report, styles, accent)
    if progress:
        story.append(PageBreak())
        story.extend(progress)

    rewards = _rewards_flowables(report, styles, accent)
    if rewards:
        story.append(PageBreak())
        story.extend(rewards)

    story.append(PageBreak())
    story.extend(_standings_flowables(report, styles, accent))

    rejected = _rejected_flowables(report, styles, accent)
    if rejected:
        story.append(PageBreak())
        story.extend(rejected)

    story.append(PageBreak())
    story.extend(_audit_flowables(report, styles, accent))

    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return path


__all__ = ["MAX_DETAIL_COLUMNS", "write_pdf"]
