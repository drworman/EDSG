"""Report generation in all four formats."""

from __future__ import annotations

import json

from conftest import commander_events
from edsg.core.crypto import generate_identity
from edsg.core.workflow import (
    close_event,
    issue_invitation,
    load_invitation,
    participate,
)
from edsg.reports import WRITERS, write_all
from edsg.reports.html_report import build_html
from edsg.reports.markdown_report import build_markdown


def build_report(tmp_path, make_journal, simple_event, identity, tonnes=(10, 25)):
    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))
    subs = tmp_path / "subs"
    for index, amount in enumerate(tonnes, start=1):
        fid = f"F000000{index}"
        events = commander_events(f"CMDR {index}", fid) + [
            {
                "timestamp": "2026-06-05T10:00:00Z",
                "event": "MiningRefined",
                "Type": "$tritium_name;",
                "Type_Localised": "Tritium",
            }
            for _ in range(amount)
        ]
        journal = make_journal(events, name=fid)
        participate(invitation, journal, generate_identity(fid), subs)
    return close_event(simple_event, subs, invitation.signer_fingerprint)


def test_all_four_formats_are_written(tmp_path, make_journal, simple_event, identity):
    report = build_report(tmp_path, make_journal, simple_event, identity)
    written = write_all(report, tmp_path / "reports", "standings")
    assert {path.suffix.lstrip(".") for path in written} == set(WRITERS)
    for path in written:
        assert path.stat().st_size > 0


def test_pdf_has_a_valid_header(tmp_path, make_journal, simple_event, identity):
    report = build_report(tmp_path, make_journal, simple_event, identity)
    written = write_all(report, tmp_path / "reports", "standings")
    pdf = next(path for path in written if path.suffix == ".pdf")
    assert pdf.read_bytes().startswith(b"%PDF")


def test_json_report_round_trips(tmp_path, make_journal, simple_event, identity):
    report = build_report(tmp_path, make_journal, simple_event, identity)
    written = write_all(report, tmp_path / "reports", "standings")
    payload = json.loads(
        next(p for p in written if p.suffix == ".json").read_text(encoding="utf-8")
    )
    assert payload["participant_count"] == 2
    assert payload["standings"][0]["total_points"] == 50.0
    assert payload["event"]["name"] == "Test Event"
    # The criteria index lets a consumer resolve per-criterion IDs.
    assert "mining01" in payload["criteria_index"]


def test_markdown_contains_the_standings(
    tmp_path, make_journal, simple_event, identity
):
    report = build_report(tmp_path, make_journal, simple_event, identity)
    text = build_markdown(report)
    assert "# Test Event" in text
    assert "CMDR 2" in text
    assert "Tritium mined" in text


def test_markdown_escapes_pipes(tmp_path, make_journal, simple_event, identity):
    """A pipe in an event name must not break the table."""
    simple_event.name = "Pipe | Event"
    report = build_report(tmp_path, make_journal, simple_event, identity)
    assert "Pipe \\| Event" in build_markdown(report)


def test_html_is_self_contained(tmp_path, make_journal, simple_event, identity):
    report = build_report(tmp_path, make_journal, simple_event, identity)
    html = build_html(report)
    assert html.startswith("<!DOCTYPE html>")
    assert "<style>" in html
    # No external assets: the file must render offline from a single copy.
    assert "src=" not in html
    assert "<link" not in html


def test_html_escapes_markup(tmp_path, make_journal, simple_event, identity):
    simple_event.description = "<script>alert(1)</script>"
    report = build_report(tmp_path, make_journal, simple_event, identity)
    html = build_html(report)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_reports_survive_an_empty_event(tmp_path, make_journal, simple_event, identity):
    """No eligible submissions must still produce readable reports."""
    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))
    subs = tmp_path / "subs"
    path, _, _ = participate(
        invitation,
        make_journal(commander_events(), name="F1"),
        generate_identity("p"),
        subs,
    )
    data = json.loads(path.read_text())
    data["payload"]["total_points"] = 1  # break the signature deliberately
    path.write_text(json.dumps(data))

    report = close_event(simple_event, subs)
    assert not report.standings
    written = write_all(report, tmp_path / "reports", "standings")
    assert len(written) == len(WRITERS)
    assert "No eligible submissions" in build_markdown(report)


def test_rejections_appear_in_the_reports(
    tmp_path, make_journal, simple_event, identity
):
    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))
    subs = tmp_path / "subs"
    participate(
        invitation,
        make_journal(commander_events("GOOD", "F1"), name="F1"),
        generate_identity("p"),
        subs,
    )
    bad = subs / "F9999999.edsgs"
    bad.write_text('{"not": "an edsg file"}')

    report = close_event(simple_event, subs)
    assert report.rejected
    assert "Rejected submissions" in build_markdown(report)
    assert "F9999999" in build_html(report)
