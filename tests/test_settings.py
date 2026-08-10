"""Settings, palettes, workspace layout and report branding."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from edsg.core.palettes import (
    CUSTOMISABLE,
    PALETTES,
    contrast_ratio,
    get_palette,
    is_colour,
)
from edsg.core.paths import event_paths, safe_folder_name
from edsg.core.settings import (
    Appearance,
    Branding,
    Contact,
    Settings,
    load_settings,
    save_settings,
    settings_path,
)

# -- palettes ---------------------------------------------------------


def test_every_theme_has_readable_table_headers():
    """The header tone is derived, not chosen, so this must hold for all.

    Unreadable header text on the generated reports is what prompted the
    derived colours in the first place.
    """
    for palette in PALETTES.values():
        ratio = contrast_ratio(palette.header_bg, palette.header_text)
        assert ratio >= 4.5, f"{palette.name} header contrast is {ratio:.2f}"


def test_every_theme_has_readable_body_text():
    for palette in PALETTES.values():
        ratio = contrast_ratio(palette.surface, palette.text)
        assert ratio >= 4.5, f"{palette.name} body contrast is {ratio:.2f}"


def test_unknown_theme_falls_back_to_default():
    assert get_palette("no-such-theme").name == "default"


def test_overrides_apply_and_rubbish_is_ignored():
    palette = get_palette("default", {"accent": "#123456", "bogus": "#000000"})
    assert palette.accent == "#123456"
    palette = get_palette("default", {"accent": "not a colour"})
    assert palette.accent == PALETTES["default"].accent


@pytest.mark.parametrize(
    ("value", "valid"),
    [("#fff", True), ("#a1b2c3", True), ("fff", False), ("#gggggg", False)],
)
def test_colour_validation(value, valid):
    assert is_colour(value) is valid


# -- settings ---------------------------------------------------------


def test_settings_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path))
    original = Settings(
        appearance=Appearance(theme="blue", custom_colours={"accent": "#112233"}),
        branding=Branding(
            squadron_name="Mining and Logistics, Ltd.",
            squadron_tag="MALL",
            contacts=[Contact("discord", "discord.gg/mall")],
        ),
    )
    save_settings(original)
    loaded = load_settings()

    assert loaded.appearance.theme == "blue"
    assert loaded.appearance.custom_colours == {"accent": "#112233"}
    assert loaded.branding.title_line() == "Mining and Logistics, Ltd. [MALL]"
    assert loaded.branding.visible_contacts()[0].value == "discord.gg/mall"


def test_corrupt_settings_fall_back_to_defaults(tmp_path, monkeypatch):
    """A bad settings file must never stop the application starting."""
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path))
    settings_path().write_text("{ this is not json", encoding="utf-8")
    assert load_settings().appearance.theme == "default"


def test_settings_reject_invalid_custom_colours(tmp_path, monkeypatch):
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path))
    settings_path().write_text(
        json.dumps(
            {"appearance": {"theme": "green", "custom_colours": {"accent": "red"}}}
        ),
        encoding="utf-8",
    )
    loaded = load_settings()
    assert loaded.appearance.theme == "green"
    assert loaded.appearance.custom_colours == {}


def test_both_binaries_share_one_settings_file(tmp_path, monkeypatch):
    """The organizer and participant must not need separate configuration."""
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path))
    save_settings(Settings(appearance=Appearance(theme="purple")))
    assert settings_path().parent == tmp_path
    assert load_settings().appearance.theme == "purple"


def test_branding_is_empty_by_default():
    assert not Branding().has_content
    assert Branding(squadron_tag="MALL").title_line() == "[MALL]"


def test_missing_logo_is_reported_as_absent(tmp_path):
    branding = Branding(logo_path=str(tmp_path / "nope.png"))
    assert branding.logo() is None


# -- workspace layout -------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Test Event #1", "Test Event -1"),
        ("Mining & Logistics: Q3/2026", "Mining - Logistics- Q3-2026"),
        ("   ...   ", "unnamed-event"),
        ("CON", "event-CON"),
        ("PRN", "event-PRN"),
    ],
)
def test_event_folder_names_are_filesystem_safe(name, expected):
    """Windows rejects several characters and reserves device names."""
    assert safe_folder_name(name) == expected


def test_event_workspace_layout(tmp_path, monkeypatch):
    monkeypatch.setenv("EDSG_HOME", str(tmp_path))
    paths = event_paths("Summer Drive").create()

    assert paths.root == tmp_path / "Events" / "Summer Drive"
    assert paths.invitation.is_dir()
    assert paths.submissions.is_dir()
    assert paths.standings.is_dir()
    assert paths.invitation.parent == paths.root


def test_creating_a_workspace_twice_is_harmless(tmp_path, monkeypatch):
    monkeypatch.setenv("EDSG_HOME", str(tmp_path))
    event_paths("Repeat").create()
    marker = event_paths("Repeat").submissions / "keep.edsgs"
    marker.write_text("{}", encoding="utf-8")
    event_paths("Repeat").create()
    assert marker.is_file(), "re-creating must not clear received submissions"


# -- report branding ---------------------------------------------------


def test_reports_carry_the_branding(tmp_path):
    from edsg.core.models import EventDefinition
    from edsg.core.standings import StandingsReport
    from edsg.reports.html_report import build_html
    from edsg.reports.markdown_report import build_markdown
    from edsg.reports.style import ReportStyle

    report = StandingsReport(
        event=EventDefinition(name="Branded Event"),
        standings=[],
        accepted=[],
        rejected=[],
        generator_version="20260810",
    )
    style = ReportStyle.from_settings(
        Settings(
            appearance=Appearance(theme="green"),
            branding=Branding(
                squadron_name="Mining and Logistics, Ltd.",
                squadron_tag="MALL",
                contacts=[Contact("discord", "discord.gg/mall")],
            ),
        )
    )

    html = build_html(report, style)
    assert "Mining and Logistics, Ltd. [MALL]" in html
    assert "discord.gg/mall" in html
    assert PALETTES["green"].accent in html

    markdown = build_markdown(report, style)
    assert "Mining and Logistics, Ltd. [MALL]" in markdown


def test_reports_without_branding_omit_the_block(tmp_path):
    from edsg.core.models import EventDefinition
    from edsg.core.standings import StandingsReport
    from edsg.reports.html_report import build_html
    from edsg.reports.style import ReportStyle

    report = StandingsReport(
        event=EventDefinition(name="Plain Event"),
        standings=[],
        accepted=[],
        rejected=[],
    )
    html = build_html(report, ReportStyle())
    assert 'class="brand"' not in html
    assert "Plain Event" in html


def test_oversized_logo_is_refused(tmp_path):
    from edsg.reports.style import MAX_LOGO_BYTES, ReportStyle

    logo = tmp_path / "huge.png"
    logo.write_bytes(b"\x89PNG" + b"\0" * (MAX_LOGO_BYTES + 1))
    style = ReportStyle(branding=Branding(logo_path=str(logo)))
    assert style.logo_path() is None
    assert style.logo_data_uri() == ""


def test_unsupported_logo_format_is_refused(tmp_path):
    from edsg.reports.style import ReportStyle

    logo = tmp_path / "logo.svg"
    logo.write_text("<svg/>", encoding="utf-8")
    style = ReportStyle(branding=Branding(logo_path=str(logo)))
    assert style.logo_path() is None


def test_customisable_keys_all_exist_on_the_palette():
    palette = get_palette("default")
    for key in CUSTOMISABLE:
        assert isinstance(getattr(palette, key), str)


def _parse_funding(text: str) -> dict[str, str]:
    """Read .github/FUNDING.yml without needing a YAML parser.

    The file is a handful of fixed-shape lines, and this guard is worth
    more running everywhere than it is depending on PyYAML being present.
    """
    found: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip("[]")
        value = value.split(",")[0].strip().strip("\"'")
        if not value:
            continue
        if key == "patreon":
            found["patreon"] = f"https://patreon.com/{value}"
        elif key == "ko_fi":
            found["ko_fi"] = f"https://ko-fi.com/{value}"
        elif key == "custom":
            found["custom"] = value
    return found


def test_funding_links_match_the_repository_file():
    """The About dialog must not drift from .github/FUNDING.yml."""
    pytest.importorskip("PySide6")
    from edsg.gui.about import funding_links

    funding_file = Path(__file__).resolve().parent.parent / ".github" / "FUNDING.yml"
    if not funding_file.is_file():
        pytest.skip("FUNDING.yml is not present in this checkout")

    declared = _parse_funding(funding_file.read_text(encoding="utf-8"))
    assert declared, "FUNDING.yml parsed to nothing"
    assert {link.key: link.url for link in funding_links()} == declared


def test_funding_parser_handles_the_real_shapes():
    parsed = _parse_funding(
        "# a comment\n"
        "patreon: drworman\n"
        "ko_fi: drworman\n"
        'custom: ["https://paypal.me/DavidWorman"]\n'
    )
    assert parsed == {
        "patreon": "https://patreon.com/drworman",
        "ko_fi": "https://ko-fi.com/drworman",
        "custom": "https://paypal.me/DavidWorman",
    }
