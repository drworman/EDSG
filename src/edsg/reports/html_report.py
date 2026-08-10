"""HTML standings output.

A single self-contained file: no external stylesheets, fonts or scripts,
so it can be zipped and mailed, or dropped on a web host, and still look
the same. The palette follows the game's own orange-on-black HUD.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from edsg.core.standings import StandingsReport
from edsg.reports.common import (
    MEDALS,
    format_points,
    format_units,
    summary_lines,
)

STYLESHEET = """
:root {
  --bg: #0b0d10;
  --panel: #14181d;
  --panel-alt: #1b2027;
  --line: #2b323c;
  --text: #e8eaed;
  --muted: #9aa4b2;
  --accent: #ff7100;
  --accent-soft: rgba(255, 113, 0, 0.14);
  --good: #5ac37d;
  --bad: #e5534b;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 2rem 1.25rem 4rem;
  background: var(--bg);
  color: var(--text);
  font-family: "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  line-height: 1.55;
}
.wrap { max-width: 1100px; margin: 0 auto; }
header {
  border-bottom: 2px solid var(--accent);
  padding-bottom: 1rem;
  margin-bottom: 2rem;
}
h1 {
  margin: 0 0 .35rem;
  font-size: 2rem;
  letter-spacing: .04em;
  color: var(--accent);
  text-transform: uppercase;
}
h2 {
  margin: 2.5rem 0 .85rem;
  font-size: 1.15rem;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: var(--accent);
}
.tagline { color: var(--muted); margin: 0; }
table {
  width: 100%;
  border-collapse: collapse;
  background: var(--panel);
  border: 1px solid var(--line);
  font-size: .93rem;
}
caption { caption-side: bottom; padding-top: .6rem; color: var(--muted);
  font-size: .82rem; text-align: left; }
th, td { padding: .6rem .75rem; text-align: left;
  border-bottom: 1px solid var(--line); vertical-align: top; }
thead th {
  background: var(--panel-alt);
  color: var(--muted);
  text-transform: uppercase;
  font-size: .72rem;
  letter-spacing: .07em;
  white-space: nowrap;
}
tbody tr:last-child td { border-bottom: none; }
tbody tr:hover { background: var(--accent-soft); }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.rank { width: 4.5rem; font-weight: 700; }
.rank-1 { color: var(--accent); }
.cmdr { font-weight: 600; }
.total { font-weight: 700; color: var(--accent); font-size: 1.05rem; }
.sub { display: block; color: var(--muted); font-size: .76rem; }
.summary td:first-child { color: var(--muted); width: 14rem;
  text-transform: uppercase; font-size: .74rem; letter-spacing: .06em; }
code { background: var(--panel-alt); padding: .1rem .35rem;
  border-radius: 3px; font-size: .85em; color: var(--muted); }
.empty { color: var(--muted); font-style: italic; padding: 1rem 0; }
.reject td { color: var(--bad); }
footer { margin-top: 3rem; padding-top: 1rem;
  border-top: 1px solid var(--line); color: var(--muted); font-size: .82rem; }
@media print {
  body { background: #fff; color: #000; padding: 0; }
  table { background: #fff; }
  thead th { background: #eee; color: #000; }
  h1, h2, .total { color: #000; }
}
"""


def _summary_table(report: StandingsReport) -> str:
    rows = "".join(
        f"<tr><td>{escape(label)}</td><td>{escape(value)}</td></tr>"
        for label, value in summary_lines(report)
    )
    return f'<table class="summary"><tbody>{rows}</tbody></table>'


def _criteria_table(report: StandingsReport) -> str:
    rows = []
    for index, criterion in enumerate(report.event.criteria, start=1):
        notes = (
            f'<span class="sub">{escape(criterion.notes)}</span>'
            if criterion.notes
            else ""
        )
        rows.append(
            f"<tr><td class='num'>{index}</td>"
            f"<td><strong>{escape(criterion.label)}</strong>{notes}</td>"
            f"<td>{escape(criterion.describe())}</td></tr>"
        )
    return (
        "<table><thead><tr><th class='num'>#</th><th>Criterion</th>"
        "<th>Rule</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _standings_table(report: StandingsReport) -> str:
    event = report.event
    if not report.standings:
        return '<p class="empty">No eligible submissions were received.</p>'

    headers = ["Rank", "Commander", "Points"]
    headers.extend(criterion.label for criterion in event.criteria)
    head = "".join(
        f"<th class='num'>{escape(name)}</th>"
        if index != 1
        else f"<th>{escape(name)}</th>"
        for index, name in enumerate(headers)
    )

    rows = []
    for standing in report.standings:
        medal = MEDALS.get(standing.rank, "")
        tie = " =" if standing.tied else ""
        rank_class = "rank rank-1" if standing.rank == 1 else "rank"
        cells = [
            f"<td class='{rank_class}'>{medal} {standing.rank}{tie}</td>",
            f"<td class='cmdr'>CMDR {escape(standing.commander_name)}"
            f"<span class='sub'>{escape(standing.commander_fid)}</span></td>",
            f"<td class='num total'>{format_points(standing.total_points)}</td>",
        ]
        for criterion in event.criteria:
            points = standing.per_criterion.get(criterion.criterion_id, 0.0)
            units = standing.per_criterion_units.get(criterion.criterion_id, 0.0)
            cells.append(
                f"<td class='num'>{format_points(points)}"
                f"<span class='sub'>"
                f"{escape(format_units(units, criterion.measure))}</span></td>"
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")

    return (
        f"<table><thead><tr>{head}</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody><caption>Point totals per criterion, with the measured "
        "units beneath each score.</caption></table>"
    )


def _rejected_table(report: StandingsReport) -> str:
    if not report.rejected:
        return ""
    rows = []
    for item in report.rejected:
        commander = item.submission.commander_name if item.submission else "unknown"
        rows.append(
            f"<tr class='reject'><td><code>{escape(item.path.name)}</code></td>"
            f"<td>{escape(commander)}</td>"
            f"<td>{escape(item.rejection)}</td></tr>"
        )
    return (
        "<h2>Rejected submissions</h2><table><thead><tr><th>File</th>"
        "<th>Commander</th><th>Reason</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _audit_table(report: StandingsReport) -> str:
    rows = []
    for item in report.accepted:
        submission = item.submission
        if submission is None:
            continue
        warnings = []
        if submission.scan.malformed_lines:
            warnings.append(f"{submission.scan.malformed_lines} unreadable lines")
        if submission.scan.unreadable_files:
            warnings.append(f"{len(submission.scan.unreadable_files)} unreadable files")
        note = (
            f"<span class='sub'>{escape(', '.join(warnings))}</span>"
            if warnings
            else ""
        )
        rows.append(
            f"<tr><td class='cmdr'>CMDR {escape(submission.commander_name)}{note}</td>"
            f"<td><code>{escape(submission.commander_fid)}</code></td>"
            f"<td><code>{escape(item.signer_fingerprint)}</code></td>"
            f"<td>{escape(submission.generated_at)}</td>"
            f"<td class='num'>{submission.scan.entries_parsed:,}</td>"
            f"<td class='num'>{submission.scan.files_read:,}</td></tr>"
        )
    return (
        "<h2>Submission audit</h2><table><thead><tr><th>Commander</th>"
        "<th>Frontier ID</th><th>Signing key</th><th>Generated</th>"
        "<th class='num'>Events</th><th class='num'>Files</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody><caption>Signatures confirm each "
        "file is unchanged since the participant generated it. They do not "
        "attest to the contents of the underlying journal files.</caption>"
        "</table>"
    )


def build_html(report: StandingsReport) -> str:
    """Render the whole report as a self-contained HTML document."""
    event = report.event
    description = (
        f'<p class="tagline">{escape(event.description)}</p>'
        if event.description
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{escape(event.name)} — EDSG standings</title>
<style>{STYLESHEET}</style>
</head>
<body>
<div class="wrap">
<header>
<h1>{escape(event.name)}</h1>
{description}
</header>

<h2>Event summary</h2>
{_summary_table(report)}

<h2>Scoring criteria</h2>
{_criteria_table(report)}

<h2>Standings</h2>
{_standings_table(report)}

{_rejected_table(report)}

{_audit_table(report)}

<footer>
Generated by ED: Squad Goals {escape(report.generator_version or "")}
on {escape(report.generated_at)}.
Elite Dangerous is a trademark of Frontier Developments plc.
EDSG is an unofficial community tool and is not affiliated with
Frontier Developments.
</footer>
</div>
</body>
</html>
"""


def write_html(report: StandingsReport, path: Path) -> Path:
    """Write the HTML report to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_html(report), encoding="utf-8")
    return path


__all__ = ["STYLESHEET", "build_html", "write_html"]
