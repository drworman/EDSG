"""PDF standings output.

Built with ReportLab's platypus layer, which is pure Python and bundles
into a PyInstaller binary without native dependencies.

The standings table widens with every criterion, so the page is
landscape and column widths are computed from the count rather than
fixed. Past roughly eight criteria the per-criterion columns are dropped
and only totals are shown, because an unreadable table helps nobody.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from edsg.core.standings import StandingsReport
from edsg.reports.common import format_points, format_units, summary_lines

#: Beyond this many criteria the detail columns are omitted.
MAX_DETAIL_COLUMNS = 8

ACCENT = colors.HexColor("#c25400")
HEADER_BG = colors.HexColor("#1b2027")
ROW_ALT = colors.HexColor("#f4f5f7")
LINE = colors.HexColor("#c9ced6")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "EDSGTitle",
            parent=base["Title"],
            fontSize=20,
            leading=24,
            alignment=TA_LEFT,
            textColor=ACCENT,
            spaceAfter=2,
        ),
        "tagline": ParagraphStyle(
            "EDSGTagline",
            parent=base["Normal"],
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#55606e"),
            spaceAfter=10,
        ),
        "heading": ParagraphStyle(
            "EDSGHeading",
            parent=base["Heading2"],
            fontSize=12,
            leading=15,
            textColor=ACCENT,
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
            textColor=colors.HexColor("#55606e"),
        ),
        "footer": ParagraphStyle(
            "EDSGFooter",
            parent=base["Normal"],
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#6b7480"),
        ),
    }


def _table_style(header_rows: int = 1) -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, header_rows - 1), HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, header_rows - 1), colors.white),
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


def _summary_flowables(report: StandingsReport, styles) -> list:
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


def _criteria_flowables(report: StandingsReport, styles) -> list:
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
    table.setStyle(_table_style())
    return [Paragraph("Scoring criteria", styles["heading"]), table]


def _standings_flowables(report: StandingsReport, styles) -> list:
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
    table.setStyle(_table_style())
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


def _rejected_flowables(report: StandingsReport, styles) -> list:
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
    table.setStyle(_table_style())
    return [Paragraph("Rejected submissions", styles["heading"]), table]


def _audit_flowables(report: StandingsReport, styles) -> list:
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
    table.setStyle(_table_style())
    note = Paragraph(
        "Signatures confirm each file is unchanged since the participant "
        "generated it. They do not attest to the contents of the underlying "
        "journal files.",
        styles["cell_small"],
    )
    return [Paragraph("Submission audit", styles["heading"]), table, Spacer(1, 4), note]


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


def write_pdf(report: StandingsReport, path: Path) -> Path:
    """Write the PDF report to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()
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

    story: list = [Paragraph(event.name, styles["title"])]
    if event.description:
        story.append(Paragraph(event.description, styles["tagline"]))

    story.extend(_summary_flowables(report, styles))
    story.extend(_standings_flowables(report, styles))
    story.append(PageBreak())
    story.extend(_criteria_flowables(report, styles))
    story.extend(_rejected_flowables(report, styles))
    story.extend(_audit_flowables(report, styles))

    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return path


__all__ = ["MAX_DETAIL_COLUMNS", "write_pdf"]
