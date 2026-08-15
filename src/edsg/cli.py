"""A headless command line, used for automation and CI smoke tests.

The GUI is the product; this exists so the release workflow can prove a
built binary actually runs on a machine with no display, and so an
organizer can script an event without clicking through the interface.
Both binaries expose it: passing ``--cli`` to either one lands here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from edsg.core.crypto import load_or_create_identity
from edsg.core.errors import EDSGError
from edsg.core.journal import resolve_commander
from edsg.core.models import INVITATION_SUFFIX, EventDefinition
from edsg.core.paths import ROLE_ORGANIZER, ROLE_PARTICIPANT, set_role
from edsg.core.workflow import (
    close_event,
    detect_squadron_from_journals,
    issue_invitation,
    load_invitation,
    participate,
    regenerate_standings,
)
from edsg.version import read_version


def _cmd_version(_args: argparse.Namespace) -> int:
    print(read_version())
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    """Verify a signed file and print what it contains."""
    path = Path(args.file)
    raw = json.loads(path.read_text(encoding="utf-8"))
    doc_type = raw.get("doc_type", "")

    if doc_type == "edsg.invitation":
        invitation = load_invitation(path)
        event = invitation.event
        print(f"Invitation      {event.name}")
        print(f"Event ID        {event.event_id}")
        print(f"Signed by       {invitation.signer_fingerprint}")
        print(f"Period          {event.window.describe()}")
        print(f"Eligibility     {event.eligibility.value}")
        if event.squadron:
            print(f"Squadron        {event.squadron}")
        print(f"Criteria        {len(event.criteria)}")
        for criterion in event.criteria:
            print(f"  - {criterion.label}: {criterion.describe()}")
        return 0

    if doc_type == "edsg.submission":
        from edsg.core.standings import load_submission_file

        loaded = load_submission_file(path)
        if loaded.submission is None:
            print(f"REJECTED: {loaded.rejection}", file=sys.stderr)
            return 1
        submission = loaded.submission
        print(f"Submission      CMDR {submission.commander_name}")
        print(f"Frontier ID     {submission.commander_fid}")
        print(f"Event           {submission.event_name} ({submission.event_id})")
        print(f"Signed by       {loaded.signer_fingerprint}")
        print(
            f"Eligible        {submission.eligible} — {submission.eligibility_reason}"
        )
        print(f"Total points    {submission.total_points:,.2f}")
        for result in submission.results:
            print(
                f"  - {result.label}: {result.counted_units:,.2f} units "
                f"-> {result.points:,.2f} pts"
            )
        return 0

    print(f"Unrecognised document type: {doc_type!r}", file=sys.stderr)
    return 2


def _cmd_squadron(args: argparse.Namespace) -> int:
    set_role(ROLE_ORGANIZER)
    squadron = detect_squadron_from_journals(Path(args.journals))
    if squadron is None:
        print("No current squadron membership found.", file=sys.stderr)
        return 1
    print(f"{squadron.name}\t{squadron.squadron_id}")
    return 0


def _cmd_commander(args: argparse.Namespace) -> int:
    commander = resolve_commander(Path(args.journals))
    print(f"{commander.name}\t{commander.fid}")
    return 0


def _cmd_issue(args: argparse.Namespace) -> int:
    # Issuing is an organizer action, so it uses the organizer's identity
    # and settings even when invoked through the participant binary.
    set_role(ROLE_ORGANIZER)
    data = json.loads(Path(args.event).read_text(encoding="utf-8"))
    event = EventDefinition.from_dict(data)
    identity = load_or_create_identity(args.identity, "EDSG event organizer")
    written = issue_invitation(event, identity, Path(args.out))
    print(written)
    print(f"fingerprint: {identity.fingerprint}", file=sys.stderr)
    return 0


def _cmd_participate(args: argparse.Namespace) -> int:
    set_role(ROLE_PARTICIPANT)
    invitation = load_invitation(Path(args.invitation))
    identity = load_or_create_identity(args.identity, "EDSG participant")
    destination = Path(args.out)
    destination.mkdir(parents=True, exist_ok=True)
    path, submission, membership = participate(
        invitation, Path(args.journals), identity, destination
    )
    print(path)
    print(
        f"CMDR {submission.commander_name}: {submission.total_points:,.2f} pts, "
        f"eligible={membership.is_member} ({membership.reason})",
        file=sys.stderr,
    )
    return 0


def _load_event(path: Path) -> tuple[EventDefinition, str]:
    """Load an event from either an invitation or a raw event JSON.

    Accepting the ``.edsgi`` directly matters: the organizer always has
    it, and requiring them to extract an event JSON by hand is how a
    stale copy ends up rejecting every submission.
    """
    if path.suffix.lower() == INVITATION_SUFFIX:
        invitation = load_invitation(path)
        return invitation.event, invitation.signer_fingerprint
    data = json.loads(path.read_text(encoding="utf-8"))
    return EventDefinition.from_dict(data), ""


def _cmd_close(args: argparse.Namespace) -> int:
    # Closing publishes reports, which carry the organizer's theme and
    # squadron branding.
    set_role(ROLE_ORGANIZER)
    event, fingerprint = _load_event(Path(args.event))
    if args.invitation:
        fingerprint = load_invitation(Path(args.invitation)).signer_fingerprint

    runner = regenerate_standings if args.regenerate else close_event
    report = runner(event, Path(args.submissions), fingerprint)

    # Imported here rather than at module scope: only the organizer build
    # needs ReportLab, and keeping it lazy halves the participant binary.
    from edsg.reports import write_all

    written = write_all(report, Path(args.out), args.stem)
    for standing in report.standings:
        print(
            f"{standing.rank}\t{standing.commander_name}\t{standing.total_points:,.2f}"
        )
    for item in report.rejected:
        print(f"REJECTED\t{item.path.name}\t{item.rejection}", file=sys.stderr)
    for path in written:
        print(f"wrote {path}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the headless interface."""
    parser = argparse.ArgumentParser(
        prog="edsg",
        description="ED: Squad Goals — headless interface.",
    )
    parser.add_argument("--version", action="version", version=f"EDSG {read_version()}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("version", help="Print the version.").set_defaults(
        func=_cmd_version
    )

    inspect = subparsers.add_parser(
        "inspect", help="Verify and describe an invitation or submission."
    )
    inspect.add_argument("file")
    inspect.set_defaults(func=_cmd_inspect)

    squadron = subparsers.add_parser(
        "squadron", help="Detect the squadron a journal folder belongs to."
    )
    squadron.add_argument("journals")
    squadron.set_defaults(func=_cmd_squadron)

    commander = subparsers.add_parser(
        "commander", help="Identify the commander owning a journal folder."
    )
    commander.add_argument("journals")
    commander.set_defaults(func=_cmd_commander)

    issue = subparsers.add_parser(
        "issue", help="Sign an event definition into an invitation."
    )
    issue.add_argument("event", help="Event definition JSON.")
    issue.add_argument("--out", required=True)
    issue.add_argument("--identity", default="organizer")
    issue.set_defaults(func=_cmd_issue)

    take_part = subparsers.add_parser(
        "participate", help="Scan journals and produce a signed submission."
    )
    take_part.add_argument("invitation")
    take_part.add_argument("--journals", required=True)
    take_part.add_argument("--out", required=True)
    take_part.add_argument("--identity", default="participant")
    take_part.set_defaults(func=_cmd_participate)

    close = subparsers.add_parser(
        "close", help="Close an event and write every report format."
    )
    close.add_argument(
        "event",
        help="The .edsgi invitation for the event, or an event definition JSON.",
    )
    close.add_argument("--submissions", required=True)
    close.add_argument("--out", required=True)
    close.add_argument("--stem", default="standings")
    close.add_argument("--invitation", default="")
    close.add_argument(
        "--regenerate",
        action="store_true",
        help="Rebuild reports for an already-closed event.",
    )
    close.set_defaults(func=_cmd_close)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the headless interface."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except EDSGError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
