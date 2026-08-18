"""HTML standings output.

A single self-contained file: no external stylesheets, fonts, scripts or
images, so it can be zipped and mailed, or dropped on a web host, and
still look the same. Colours come from the organizer's chosen theme and
the logo is embedded as a data URI.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from edsg.core.numbers import percentage
from edsg.core.standings import StandingsReport
from edsg.reports.common import MEDALS, format_points, format_units, summary_lines
from edsg.reports.style import ReportStyle


def _stylesheet(style: ReportStyle) -> str:
    colours = style.palette
    return f"""
:root {{
  --bg: {colours.bg};
  --surface: {colours.surface};
  --surface-alt: {colours.surface_alt};
  --line: {colours.line};
  --text: {colours.text};
  --dim: {colours.text_dim};
  --faint: {colours.text_faint};
  --accent: {colours.accent};
  --accent-dim: {colours.accent_dim};
  --accent-soft: {colours.accent_soft};
  --header-bg: {colours.header_bg};
  --header-text: {colours.header_text};
  --zebra: {colours.zebra};
  --good: {colours.good};
  --warn: {colours.warn};
  --bad: {colours.bad};
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  padding: 2.25rem 1.5rem 4rem;
  background: var(--bg);
  color: var(--text);
  font-family: "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 15px;
  line-height: 1.55;
}}
.wrap {{ max-width: 1180px; margin: 0 auto; }}

/* ── masthead ──────────────────────────────────────────────────────── */
.masthead {{
  display: flex;
  align-items: flex-start;
  gap: 1.25rem;
  border-bottom: 3px solid var(--accent);
  padding-bottom: 1.1rem;
  margin-bottom: 2rem;
}}
.brand {{ flex: 0 0 auto; max-width: 42%; }}
.brand-logo {{ max-height: 76px; max-width: 220px; display: block;
  margin-bottom: .5rem; }}
.brand-name {{ font-size: 1.05rem; font-weight: 700; color: var(--text);
  letter-spacing: .02em; }}
.brand-contacts {{ margin: .3rem 0 0; padding: 0; list-style: none;
  font-size: .8rem; color: var(--dim); }}
.brand-contacts li {{ white-space: nowrap; }}
.brand-contacts .k {{ color: var(--faint); text-transform: uppercase;
  font-size: .68rem; letter-spacing: .06em; margin-right: .35rem; }}
.titles {{ margin-left: auto; text-align: right; }}
h1 {{
  margin: 0 0 .2rem;
  font-size: 1.9rem;
  line-height: 1.15;
  letter-spacing: .03em;
  color: var(--accent);
  text-transform: uppercase;
}}
.tagline {{ color: var(--dim); margin: 0; font-size: .95rem; }}
.stamp {{ color: var(--faint); font-size: .78rem; margin-top: .35rem; }}

/* ── sections ──────────────────────────────────────────────────────── */
h2 {{
  margin: 2.4rem 0 .8rem;
  font-size: 1rem;
  text-transform: uppercase;
  letter-spacing: .1em;
  color: var(--accent);
  border-left: 3px solid var(--accent);
  padding-left: .6rem;
}}

/* ── tables ────────────────────────────────────────────────────────── */
table {{
  width: 100%;
  border-collapse: collapse;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 4px;
  overflow: hidden;
  font-size: .92rem;
}}
caption {{ caption-side: bottom; padding-top: .65rem; color: var(--dim);
  font-size: .8rem; text-align: left; }}
th, td {{ padding: .62rem .8rem; text-align: left;
  border-bottom: 1px solid var(--line); vertical-align: top; }}
thead th {{
  background: var(--header-bg);
  color: var(--header-text);
  text-transform: uppercase;
  font-size: .74rem;
  font-weight: 700;
  letter-spacing: .06em;
  white-space: nowrap;
  border-bottom: 2px solid var(--accent-dim);
}}
tbody tr:nth-child(even) {{ background: var(--zebra); }}
tbody tr:last-child td {{ border-bottom: none; }}
tbody tr:hover {{ background: var(--accent-soft); }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.rank {{ width: 4.5rem; font-weight: 700; text-align: center; }}
.rank-1 {{ color: var(--accent); }}
.cmdr {{ font-weight: 600; }}
.total {{ font-weight: 700; color: var(--accent); font-size: 1.05rem; }}
.sub {{ display: block; color: var(--dim); font-size: .76rem;
  font-weight: 400; }}

/* The summary table reads as a definition list, so its first column is
   a label rather than data. Dim but not faint: it was previously so low
   in contrast as to be unreadable at this size. */
.summary td:first-child {{
  color: var(--text);
  background: var(--surface-alt);
  width: 15rem;
  font-weight: 600;
  font-size: .78rem;
  text-transform: uppercase;
  letter-spacing: .05em;
}}
code {{ background: var(--surface-alt); padding: .12rem .38rem;
  border-radius: 3px; font-size: .85em; color: var(--text);
  font-family: "DejaVu Sans Mono", Consolas, Menlo, monospace; }}
.empty {{ color: var(--dim); font-style: italic; padding: 1rem 0; }}
.reject td {{ color: var(--bad); }}
/* ── progress board ────────────────────────────────────────────────── */
.board {{
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 1.1rem 1.25rem 1.25rem;
}}
.board-head {{
  display: flex; align-items: baseline; gap: 1rem; flex-wrap: wrap;
  margin-bottom: .75rem;
}}
.board-tier {{
  font-size: 1.5rem; font-weight: 700; color: var(--accent);
  letter-spacing: .04em;
}}
.board-total {{ color: var(--text); font-size: 1rem; }}
.board-total b {{ color: var(--accent); }}
.board-pct {{ margin-left: auto; color: var(--dim); font-size: .9rem; }}

.meter {{
  position: relative; height: 30px; background: var(--surface-alt);
  border: 1px solid var(--line); border-radius: 3px; overflow: hidden;
}}
.meter-fill {{
  /* Longhand rather than the `inset` shorthand: older rendering engines,
     including the one behind several PDF and screenshot tools, ignore
     `inset` entirely and the bar comes out empty. */
  position: absolute; left: 0; top: 0; bottom: 0;
  background: linear-gradient(90deg, var(--accent-dim), var(--accent));
  background-color: var(--accent-dim);
}}
.meter-ticks {{ position: absolute; left: 0; right: 0; top: 0; bottom: 0; }}
.meter-tick {{
  position: absolute; top: 0; bottom: 0; width: 2px;
  background: var(--bg); opacity: .85;
}}
.meter-tick.reached {{ background: var(--good); opacity: .9; }}
.tier-scale {{
  position: relative; height: 1.6rem; margin-top: .25rem;
  font-size: .72rem; color: var(--dim);
}}
.tier-mark {{ position: absolute; transform: translateX(-50%); white-space: nowrap; }}
.tier-mark.reached {{ color: var(--good); font-weight: 700; }}
.board-note {{ margin: .7rem 0 0; color: var(--dim); font-size: .86rem; }}
.board-note b {{ color: var(--text); }}

.reward-table td.band {{ font-weight: 600; }}
.reward-table td.payout {{ color: var(--accent); font-weight: 700; }}
.reward-table tr.empty-band td {{ color: var(--faint); }}

/* ── commander cards ───────────────────────────────────────────────── */
/* Laid out with a table rather than grid or flex. The report is opened
   in whatever the recipient has, and several PDF and screenshot engines
   still in use ignore both, collapsing every card into a tall column. */
.cmdr-card {{
  width: 100%;
  border-collapse: collapse;
  background: var(--surface);
  border: 1px solid var(--line);
  border-left: 3px solid var(--line);
  border-radius: 4px;
  margin-bottom: .55rem;
}}
.cmdr-card.rank-1 {{ border-left-color: var(--accent); }}
.cmdr-card.rank-2, .cmdr-card.rank-3 {{ border-left-color: var(--accent-dim); }}
.cmdr-card td {{ border: none; padding: .55rem .9rem; vertical-align: middle; }}
.cmdr-rank {{
  width: 3.4rem; font-size: 1.35rem; font-weight: 700; text-align: center;
  color: var(--dim); font-variant-numeric: tabular-nums;
}}
.cmdr-card.rank-1 .cmdr-rank {{ color: var(--accent); }}
.cmdr-name {{ font-weight: 600; font-size: 1.02rem; }}
.cmdr-fid {{ color: var(--faint); font-size: .74rem; }}
.cmdr-band {{ color: var(--dim); font-size: .76rem; }}
.cmdr-total {{
  width: 9rem; text-align: right; font-size: 1.25rem; font-weight: 700;
  color: var(--accent); font-variant-numeric: tabular-nums;
}}
.cmdr-total small {{ display: block; font-size: .62rem; font-weight: 400;
  color: var(--faint); letter-spacing: .1em; text-transform: uppercase; }}
.cmdr-breakdown {{ padding-top: 0 !important; }}
.chip {{
  display: inline-block;
  background: var(--surface-alt); border: 1px solid var(--line);
  border-radius: 3px; padding: .18rem .5rem; font-size: .76rem;
  white-space: nowrap; margin: 0 .3rem .3rem 0;
}}
.chip .k {{ color: var(--dim); }}
.chip .v {{ color: var(--text); font-weight: 600;
  font-variant-numeric: tabular-nums; }}
.chip .u {{ color: var(--faint); }}
.chip.zero {{ opacity: .55; }}

footer {{ margin-top: 3rem; padding-top: 1rem;
  border-top: 1px solid var(--line); color: var(--dim); font-size: .8rem; }}

@media print {{
  body {{ background: #fff; color: #000; padding: 0; font-size: 11pt; }}
  .board, .cmdr-card {{ background: #fff; border-color: #999; }}
  /* The fill must stay visible on paper. Browsers drop background
     colours when printing unless told not to, which turned the meter
     into an empty box. */
  .meter {{ background: #e8e8e8; border-color: #666;
    -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .meter-fill {{ background: #555;
    -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .meter-tick {{ background: #fff; }}
  .meter-tick.reached {{ background: #fff; }}
  .tier-mark.reached {{ color: #000; }}
  .cmdr-total, .board-tier, .board-total b {{ color: #000; }}
  .chip {{ background: #f2f2f2; border-color: #bbb; }}
  table {{ background: #fff; }}
  thead th {{ background: #e8e8e8; color: #000;
    border-bottom: 2px solid #666; }}
  tbody tr:nth-child(even) {{ background: #f5f5f5; }}
  .summary td:first-child {{ background: #f0f0f0; color: #000; }}
  h1, h2, .total, .rank-1 {{ color: #000; }}
  h2 {{ border-left-color: #666; }}
  .masthead {{ border-bottom-color: #666; }}
}}
"""


def _masthead(report: StandingsReport, style: ReportStyle) -> str:
    event = report.event
    brand = ""
    if style.has_branding:
        parts = []
        logo = style.logo_data_uri()
        if logo:
            parts.append(f'<img class="brand-logo" src="{logo}" alt=""/>')
        heading = style.heading()
        if heading:
            parts.append(f'<div class="brand-name">{escape(heading)}</div>')
        contacts = style.contact_lines()
        if contacts:
            items = "".join(
                f'<li><span class="k">{escape(label)}</span>{escape(value)}</li>'
                for label, value in contacts
            )
            parts.append(f'<ul class="brand-contacts">{items}</ul>')
        brand = f'<div class="brand">{"".join(parts)}</div>'

    description = (
        f'<p class="tagline">{escape(event.description)}</p>'
        if event.description and event.description != event.name
        else ""
    )
    return (
        f'<div class="masthead">{brand}'
        f'<div class="titles"><h1>{escape(event.name)}</h1>{description}'
        f'<div class="stamp">Standings generated {escape(report.generated_at)}'
        f"</div></div></div>"
    )


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


def _progress_board(report: StandingsReport) -> str:
    """Render the goal-tier board, in the shape Frontier's goals use.

    A tier readout, a meter marked with each threshold, and the reward
    bands with the points range each one covers.
    """
    progress = report.progress()
    if progress is None:
        return ""

    plan = progress.plan
    fill = progress.fraction * 100

    ticks, marks = [], []
    for index, tier in enumerate(progress.goal_tiers, start=1):
        if progress.ceiling <= 0:
            continue
        position = min(100.0, tier.threshold / progress.ceiling * 100)
        reached = index <= progress.tiers_reached
        state = " reached" if reached else ""
        ticks.append(
            f'<span class="meter-tick{state}" style="left:{position:.3f}%"></span>'
        )
        marks.append(
            f'<span class="tier-mark{state}" style="left:{position:.3f}%">'
            f"{escape(tier.label)}<br/>{tier.threshold:,.0f}</span>"
        )

    if progress.next_tier is not None:
        note = (
            f"<b>{progress.to_next_tier:,.0f}</b> more points to reach "
            f"{escape(progress.next_tier.label)}."
        )
    elif progress.goal_tiers:
        note = "<b>Every goal tier reached.</b>"
    else:
        note = ""
    if progress.rewards_unlocked:
        note += (
            f" Reaching {escape(progress.tier_text)} unlocks "
            f"<b>{progress.pool:,.0f} {escape(plan.currency)}</b> of the "
            f"{plan.reward_pool:,.0f} maximum."
        )
    elif plan.reward_pool:
        note += " <b>No rewards are paid:</b> the goal did not reach Tier 1."

    plan = progress.plan
    if progress.rewards_unlocked and progress.pool > 0:
        top = progress.top_payouts
        summary_rows = [
            f"<tr><td class='band'>Unlocked at "
            f"{escape(progress.tier_text)}</td>"
            f"<td class='num payout'>{progress.pool:,.0f} "
            f"{escape(plan.currency)}</td>"
            f"<td>of a {plan.reward_pool:,.0f} maximum</td></tr>"
        ]
        if top and plan.top_share:
            summary_rows.append(
                f"<tr><td class='band'>Top {len(top)} bonus</td>"
                f"<td class='num payout'>"
                f"{progress.pool * plan.top_share:,.0f}</td>"
                f"<td>{percentage(plan.top_share)} of the pool, shared among "
                f"the top {len(top)} by contribution</td></tr>"
            )
        summary_rows.append(
            f"<tr><td class='band'>Shared by contribution</td>"
            f"<td class='num payout'>"
            f"{progress.pool * (1 - plan.top_share):,.0f}</td>"
            f"<td>among all {progress.participants} contributor(s)</td></tr>"
        )
        reward_table = (
            "<table class='reward-table'><tbody>"
            + "".join(summary_rows)
            + "</tbody></table>"
        )
    else:
        reward_table = (
            "<p class='empty'>No rewards are due: the goal did not reach Tier 1.</p>"
        )

    return f"""<h2>Goal progress</h2>
<div class="board">
  <div class="board-head">
    <span class="board-tier">{escape(progress.tier_text)}</span>
    <span class="board-total"><b>{progress.total:,.0f}</b>
      / {progress.ceiling:,.0f} points</span>
    <span class="board-pct">{progress.fraction * 100:.2f}% &middot;
      {progress.participants} contributor(s)</span>
  </div>
  <div class="meter">
    <span class="meter-fill" style="width:{fill:.3f}%"></span>
    <span class="meter-ticks">{"".join(ticks)}</span>
  </div>
  <div class="tier-scale">{"".join(marks)}</div>
  <p class="board-note">{note}</p>
</div>

<h2>Reward tiers</h2>
{reward_table}
"""


def _reward_matrix(report: StandingsReport) -> str:
    """Render who is owed what, in the order an organizer pays it."""
    progress = report.progress()
    if progress is None or not progress.plan.reward_pool:
        return ""

    currency = escape(progress.plan.currency)
    if not progress.rewards_unlocked:
        return (
            f"<h2>Rewards</h2><p class='empty'>The goal finished on "
            f"{escape(progress.tier_text)}, below Tier 1, so no rewards are "
            f"due.</p>"
        )

    rows = []
    for item in progress.payouts:
        marker = " \u2605" if item.in_top else ""
        rows.append(
            f"<tr><td class='num rank'>{item.rank}{marker}</td>"
            f"<td class='cmdr'>CMDR {escape(item.commander_name)}</td>"
            f"<td><code>{escape(item.commander_fid)}</code></td>"
            f"<td class='num'>{format_points(item.points)}</td>"
            f"<td class='num'>{item.share * 100:.2f}%</td>"
            f"<td class='num'>{item.bonus:,.0f}</td>"
            f"<td class='num'>{item.proportional:,.0f}</td>"
            f"<td class='num payout'>{item.total:,.0f} {currency}</td></tr>"
        )
    if not rows:
        return ""

    return (
        "<h2>Rewards</h2>"
        "<table class='reward-table'><thead><tr><th class='num'>Rank</th>"
        "<th>Commander</th><th>Frontier ID</th><th class='num'>Points</th>"
        "<th class='num'>Share</th><th class='num'>Bonus</th>"
        "<th class='num'>Contribution</th><th class='num'>Receives</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + f"</tbody><caption>{progress.paid_total:,.0f} {currency} in total, "
        f"from {progress.pool:,.0f} unlocked at "
        f"{escape(progress.tier_text)}. A star marks the top group sharing "
        f"the bonus; commanders on equal points share a rank and are paid "
        f"alike. Paid in game by the organizer.</caption></table>"
    )


def _standings_cards(report: StandingsReport) -> str:
    """Render the standings as one card per commander.

    A wide table with a column per criterion becomes unreadable past
    three or four criteria, and pushes the totals away from the names.
    A card keeps each commander's rank, total and per-criterion
    breakdown together.
    """
    event = report.event
    if not report.standings:
        return '<p class="empty">No eligible submissions were received.</p>'

    progress = report.progress()
    bands: dict[str, str] = {}
    if progress is not None:
        for item in progress.payouts:
            if item.in_top:
                bands[item.commander_fid] = "Top group"

    cards = []
    for standing in report.standings:
        medal = MEDALS.get(standing.rank, "")
        tie = " =" if standing.tied else ""
        rank_class = f" rank-{standing.rank}" if standing.rank <= 3 else ""

        chips = []
        for criterion in event.criteria:
            points = standing.per_criterion.get(criterion.criterion_id, 0.0)
            units = standing.per_criterion_units.get(criterion.criterion_id, 0.0)
            zero = " zero" if not points else ""
            chips.append(
                f"<span class='chip{zero}'>"
                f"<span class='k'>{escape(criterion.label)}</span> "
                f"<span class='v'>{format_points(points)}</span> "
                f"<span class='u'>"
                f"{escape(format_units(units, criterion.measure))}</span></span>"
            )

        band = bands.get(standing.commander_fid, "")
        band_line = f"<div class='cmdr-band'>{escape(band)}</div>" if band else ""

        cards.append(
            f"<table class='cmdr-card{rank_class}'><tbody>"
            f"<tr>"
            f"<td class='cmdr-rank' rowspan='2'>"
            f"{medal or standing.rank}{tie}</td>"
            f"<td><div class='cmdr-name'>CMDR "
            f"{escape(standing.commander_name)}</div>"
            f"<div class='cmdr-fid'>{escape(standing.commander_fid)}</div>"
            f"{band_line}</td>"
            f"<td class='cmdr-total' rowspan='2'>"
            f"{format_points(standing.total_points)}"
            f"<small>points</small></td>"
            f"</tr>"
            f"<tr><td class='cmdr-breakdown'>{''.join(chips)}</td></tr>"
            f"</tbody></table>"
        )

    return f"<div class='cmdr-list'>{''.join(cards)}</div>"


def _standings_table(report: StandingsReport) -> str:
    event = report.event
    if not report.standings:
        return '<p class="empty">No eligible submissions were received.</p>'

    headers = ["Rank", "Commander", "Points"]
    headers.extend(criterion.label for criterion in event.criteria)
    head = "".join(
        f"<th>{escape(name)}</th>"
        if index == 1
        else f"<th class='num'>{escape(name)}</th>"
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
            f"<tr><td class='cmdr'>CMDR {escape(submission.commander_name)}"
            f"{note}</td>"
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


def build_html(report: StandingsReport, style: ReportStyle | None = None) -> str:
    """Render the whole report as a self-contained HTML document."""
    style = style or ReportStyle()
    event = report.event
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{escape(event.name)} — EDSG standings</title>
<style>{_stylesheet(style)}</style>
</head>
<body>
<div class="wrap">
{_masthead(report, style)}

<h2>Event summary</h2>
{_summary_table(report)}

{_progress_board(report)}

<h2>Standings</h2>
{_standings_cards(report)}

<h2>Scoring criteria</h2>
{_criteria_table(report)}

{_reward_matrix(report)}

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


def write_html(
    report: StandingsReport, path: Path, style: ReportStyle | None = None
) -> Path:
    """Write the HTML report to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_html(report, style), encoding="utf-8")
    return path


__all__ = ["build_html", "write_html"]
