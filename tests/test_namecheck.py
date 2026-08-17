"""Advisory name lookups against Spansh.

Every test runs against a local stand-in rather than the live service:
the check must behave predictably, and a test suite that needs the
internet is a test suite that fails on a train.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from edsg.core import namecheck
from edsg.core.namecheck import Verdict, check_name, check_names, summarise

#: What the stand-in knows about.
KNOWN = {
    "sol": [("Sol", "system")],
    "gamma lup": [("Gamma Lupi", "system"), ("Gamma Lupus", "system")],
    "gamma lupii": [("Gamma Lupi", "system")],
    "jameson memorial": [("Jameson Memorial", "station")],
}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query).get("q", [""])[0].lower()
        hits = KNOWN.get(query, [])
        body = json.dumps(
            {
                "results": [
                    {"type": kind, "record": {"name": name}} for name, kind in hits
                ]
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def spansh(monkeypatch):
    """Point the checker at a local stand-in for Spansh."""
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    monkeypatch.setattr(namecheck, "SPANSH_SEARCH", f"http://{host}:{port}/api/search")
    yield
    server.shutdown()


def test_an_exact_match_is_reported(spansh):
    result = check_name("Sol", "system")
    assert result.verdict is Verdict.EXACT
    assert not result.is_problem


def test_matching_ignores_case_and_punctuation(spansh):
    assert check_name("sol", "system").verdict is Verdict.EXACT


def test_a_near_miss_suggests_the_real_name(spansh):
    """The case this exists for: a typo that would score zero."""
    result = check_name("Gamma Lupii", "system")
    assert result.verdict is Verdict.NEAR
    assert result.is_problem
    assert "Gamma Lupi" in result.suggestions
    assert "Did you mean" in result.message()


def test_an_unrecognised_name_is_reported(spansh):
    result = check_name("Nowhereville", "system")
    assert result.verdict is Verdict.UNKNOWN
    assert result.is_problem


def test_a_station_is_looked_up_as_a_station(spansh):
    assert check_name("Jameson Memorial", "station").verdict is Verdict.EXACT
    # The same name is not a system, so asking for one finds nothing.
    assert check_name("Jameson Memorial", "system").verdict is Verdict.UNKNOWN


def test_a_very_short_name_is_skipped(spansh):
    result = check_name("XY", "system")
    assert result.verdict is Verdict.SKIPPED
    assert not result.is_problem


def test_an_unreachable_service_is_never_a_verdict(monkeypatch):
    """Being offline says nothing about whether a name is spelled right,
    and must never be presented as though it did."""
    monkeypatch.setattr(namecheck, "SPANSH_SEARCH", "http://127.0.0.1:9/api/search")
    result = check_name("Sol", "system")
    assert result.verdict is Verdict.UNAVAILABLE
    assert not result.is_problem


def test_a_broken_reply_is_not_a_verdict(monkeypatch):
    class Broken(_Handler):
        def do_GET(self):
            body = b"this is not json"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", 0), Broken)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address
    monkeypatch.setattr(namecheck, "SPANSH_SEARCH", f"http://{host}:{port}/api/search")
    try:
        assert check_name("Sol", "system").verdict is Verdict.UNAVAILABLE
    finally:
        server.shutdown()


def test_summarise_separates_problems_from_silence(spansh):
    checks = check_names(["Sol", "Gamma Lupii"], [])
    problems, answered = summarise(checks)
    assert answered
    assert len(problems) == 1

    problems, answered = summarise([])
    assert not answered
    assert problems == []


def test_several_names_are_checked_together(spansh):
    checks = check_names(["Sol"], ["Jameson Memorial"])
    assert len(checks) == 2
    assert all(item.verdict is Verdict.EXACT for item in checks)
