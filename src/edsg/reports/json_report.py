"""JSON standings output.

The machine-readable format, and the most complete: it carries the full
event definition, every accepted submission's per-criterion detail, and
the rejection list. Anything the other three formats show is derived
from this structure, so a Discord bot or spreadsheet import can rely on
it as the canonical record.
"""

from __future__ import annotations

from pathlib import Path

from edsg.core.canonical import pretty_text
from edsg.core.standings import StandingsReport
from edsg.reports.style import ReportStyle


def build_payload(report: StandingsReport, style: ReportStyle | None = None) -> dict:
    """Return the full report structure."""
    style = style or ReportStyle()
    payload = report.to_dict()
    if style.has_branding:
        payload["branding"] = {
            "squadron_name": style.branding.squadron_name,
            "squadron_tag": style.branding.squadron_tag,
            "contacts": [
                {"kind": label, "value": value}
                for label, value in style.contact_lines()
            ],
        }
    payload["criteria_index"] = {
        criterion.criterion_id: {
            "label": criterion.label,
            "kind": criterion.kind.value,
            "measure": criterion.measure.value,
            "points_per_unit": criterion.points_per_unit,
            "unit_cap": criterion.unit_cap,
            "minimum_units": criterion.minimum_units,
            "description": criterion.describe(),
            "notes": criterion.notes,
        }
        for criterion in report.event.criteria
    }
    return payload


def write_json(
    report: StandingsReport, path: Path, style: ReportStyle | None = None
) -> Path:
    """Write the JSON report to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_text(build_payload(report, style)) + "\n", encoding="utf-8")
    return path


__all__ = ["build_payload", "write_json"]
