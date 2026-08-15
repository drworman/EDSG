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
from edsg.core.paths import (
    ROLE_ORGANIZER,
    ROLE_PARTICIPANT,
    config_dir,
    config_root,
    event_paths,
    safe_folder_name,
    set_role,
)
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
    settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings_path().write_text("{ this is not json", encoding="utf-8")
    assert load_settings().appearance.theme == "default"


def test_settings_reject_invalid_custom_colours(tmp_path, monkeypatch):
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path))
    settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings_path().write_text(
        json.dumps(
            {"appearance": {"theme": "green", "custom_colours": {"accent": "red"}}}
        ),
        encoding="utf-8",
    )
    loaded = load_settings()
    assert loaded.appearance.theme == "green"
    assert loaded.appearance.custom_colours == {}


def test_each_binary_has_its_own_settings_directory(tmp_path, monkeypatch):
    """Each role keeps its configuration separate.

    The organizer holds a signing identity participants have been told to
    trust, and squadron details; the participant holds neither. Sharing a
    folder means copying one role's configuration drags the other's
    identity along with it.
    """
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path))

    save_settings(Settings(appearance=Appearance(theme="purple")), role=ROLE_ORGANIZER)
    save_settings(Settings(appearance=Appearance(theme="green")), role=ROLE_PARTICIPANT)

    assert settings_path(ROLE_ORGANIZER) == tmp_path / "Organizer" / "settings.json"
    assert settings_path(ROLE_PARTICIPANT) == tmp_path / "Participant" / "settings.json"
    assert load_settings(ROLE_ORGANIZER).appearance.theme == "purple"
    assert load_settings(ROLE_PARTICIPANT).appearance.theme == "green"


def test_signing_keys_are_kept_per_role(tmp_path, monkeypatch):
    """An organizer's key must never appear in a participant install."""
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path))
    from edsg.core.crypto import load_identity, load_or_create_identity

    set_role(ROLE_ORGANIZER)
    organizer = load_or_create_identity("organizer", "Organizer")
    set_role(ROLE_PARTICIPANT)
    participant = load_or_create_identity("participant", "Participant")

    assert organizer.fingerprint != participant.fingerprint
    assert (tmp_path / "Organizer" / "keys" / "organizer.key").is_file()
    assert (tmp_path / "Participant" / "keys" / "participant.key").is_file()
    assert not (tmp_path / "Participant" / "keys" / "organizer.key").exists()

    # The participant role must not see the organizer's identity at all.
    assert load_identity("organizer") is None


def test_role_directories_use_the_expected_names(tmp_path, monkeypatch):
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path))
    set_role(ROLE_ORGANIZER)
    assert config_dir() == tmp_path / "Organizer"
    set_role(ROLE_PARTICIPANT)
    assert config_dir() == tmp_path / "Participant"
    assert config_root() == tmp_path


def test_an_unknown_role_is_refused():
    with pytest.raises(ValueError, match="Unknown role"):
        set_role("Referee")


# -- remembered squadron ----------------------------------------------


def test_organizer_remembers_its_squadron(tmp_path, monkeypatch):
    """An organizer runs event after event for the same squadron."""
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path))
    from edsg.core.squadron import SquadronRef

    settings = Settings()
    assert settings.organizer.squadron_ref() is None

    settings.organizer.remember_squadron(
        SquadronRef(squadron_id=110393, name="MINING AND LOGISTICS LTD")
    )
    settings.organizer.organizer_name = "CMDR HUGH JASSOLE"
    save_settings(settings, role=ROLE_ORGANIZER)

    loaded = load_settings(ROLE_ORGANIZER)
    remembered = loaded.organizer.squadron_ref()
    assert remembered is not None
    assert remembered.squadron_id == 110393
    assert remembered.name == "MINING AND LOGISTICS LTD"
    assert loaded.organizer.organizer_name == "CMDR HUGH JASSOLE"


def test_forgetting_the_squadron_clears_it(tmp_path, monkeypatch):
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path))
    from edsg.core.squadron import SquadronRef

    settings = Settings()
    settings.organizer.remember_squadron(SquadronRef(1, "Somewhere"))
    settings.organizer.remember_squadron(None)
    assert settings.organizer.squadron_ref() is None
    assert not settings.organizer.has_squadron


def test_a_malformed_squadron_id_degrades(tmp_path, monkeypatch):
    """A hand-edited settings file must not stop the app starting."""
    monkeypatch.setenv("EDSG_CONFIG_DIR", str(tmp_path))
    settings_path(ROLE_ORGANIZER).parent.mkdir(parents=True, exist_ok=True)
    settings_path(ROLE_ORGANIZER).write_text(
        json.dumps({"organizer": {"squadron_id": "not a number"}}),
        encoding="utf-8",
    )
    assert load_settings(ROLE_ORGANIZER).organizer.squadron_ref() is None


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
