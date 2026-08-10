"""Report generation in the four required output formats."""

from __future__ import annotations

from pathlib import Path

from edsg.core.standings import StandingsReport
from edsg.reports.html_report import write_html
from edsg.reports.json_report import write_json
from edsg.reports.markdown_report import write_markdown
from edsg.reports.pdf_report import write_pdf

#: Report writers keyed by the file extension they produce.
WRITERS = {
    "json": write_json,
    "md": write_markdown,
    "html": write_html,
    "pdf": write_pdf,
}


def write_all(report: StandingsReport, directory: Path, stem: str) -> list[Path]:
    """Write every report format into ``directory``.

    A failure in one format does not prevent the others being written;
    the exception is re-raised only after the rest have been attempted,
    so an organizer missing a PDF backend still gets their standings.
    """
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    first_error: Exception | None = None

    for extension, writer in WRITERS.items():
        path = directory / f"{stem}.{extension}"
        try:
            writer(report, path)
        except Exception as exc:
            if first_error is None:
                first_error = exc
            continue
        written.append(path)

    if first_error is not None and not written:
        raise first_error
    return written


__all__ = [
    "WRITERS",
    "write_all",
    "write_html",
    "write_json",
    "write_markdown",
    "write_pdf",
]
