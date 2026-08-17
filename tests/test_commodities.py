"""Matching commodity names however they happen to be spelled."""

from __future__ import annotations

import pytest

from edsg.core.commodities import COMMODITIES, canonical, matches, singular

#: The three spellings Elite and an organizer produce for one commodity.
LTD_INTERNAL = "$lowtemperaturediamond_name;"
LTD_LOCALISED = "Low Temp. Diamonds"
LTD_TYPED = "Low Temperature Diamonds"


def test_every_spelling_of_one_commodity_converges():
    """The bug this exists for: three spellings, three different
    normalised forms, and a criterion that silently scored zero."""
    forms = {
        canonical(LTD_INTERNAL),
        canonical(LTD_LOCALISED),
        canonical(LTD_TYPED),
        canonical("Low Temp Diamonds"),
        canonical("low temperature diamond"),
    }
    assert forms == {"lowtemperaturediamond"}


@pytest.mark.parametrize(
    "pattern",
    [LTD_TYPED, LTD_LOCALISED, "Low Temp Diamonds", "lowtemperaturediamond"],
)
def test_the_internal_name_matches_what_an_organizer_types(pattern):
    assert matches(LTD_INTERNAL, pattern)


def test_a_partial_name_still_filters():
    assert matches(LTD_INTERNAL, "diamond")


def test_an_unrelated_commodity_does_not_match():
    assert not matches("$painite_name;", "Tritium")
    assert not matches(LTD_INTERNAL, "Void Opals")


def test_matching_is_symmetric_for_full_names():
    assert matches(LTD_LOCALISED, LTD_INTERNAL)
    assert matches(LTD_INTERNAL, LTD_LOCALISED)


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("diamonds", "diamond"),
        ("systems", "system"),
        ("batteries", "battery"),
        # Left alone: folding these changes the meaning or the word.
        ("gas", "gas"),
        ("glass", "glass"),
        ("arms", "arms"),
        ("biowaste", "biowaste"),
        ("textiles", "textiles"),
    ],
)
def test_plural_folding_is_conservative(word, expected):
    assert singular(word) == expected


def test_empty_input_matches_nothing():
    assert not matches("", "Tritium")
    assert not matches("$tritium_name;", "")


def test_the_catalogue_is_free_of_duplicates():
    canonicals = [canonical(name) for name in COMMODITIES]
    duplicates = {name for name in canonicals if canonicals.count(name) > 1}
    assert not duplicates, f"duplicated in the catalogue: {duplicates}"


def test_catalogue_entries_match_themselves():
    for name in COMMODITIES:
        assert matches(name, name), name


def test_matching_never_consults_the_catalogue():
    """A commodity Frontier adds tomorrow must still score today."""
    assert matches("$brandnewmineral_name;", "Brand New Minerals")
    assert not any(canonical(name) == "brandnewmineral" for name in COMMODITIES)


def test_a_scored_criterion_matches_all_spellings(tmp_path):
    """End to end through the evaluator, not just the helper."""
    import json

    from edsg.core.criteria import Criterion, Filters, Measure, MetricKind
    from edsg.core.journal import ReadStats, iter_journal_dir, parse_timestamp
    from edsg.core.metrics import MetricEvaluator
    from edsg.core.models import EventWindow

    rows = [
        {
            "timestamp": "2026-06-05T10:00:00Z",
            "event": "MiningRefined",
            "Type": LTD_INTERNAL,
            "Type_Localised": LTD_LOCALISED,
        }
        for _ in range(7)
    ]
    (tmp_path / "Journal.2026-06-01T090000.01.log").write_text(
        "\n".join(json.dumps(row) for row in rows), encoding="utf-8"
    )
    window = EventWindow(
        start=parse_timestamp("2026-01-01T00:00:00Z"),
        end=parse_timestamp("2026-12-31T23:59:59Z"),
    )

    for pattern in (LTD_TYPED, LTD_LOCALISED, "Low Temp Diamonds", "diamond"):
        criterion = Criterion(
            criterion_id="c",
            label="LTD",
            kind=MetricKind.MINING_REFINED,
            measure=Measure.TONNAGE,
            filters=Filters(commodities=[pattern]),
            points_per_unit=1.0,
            unit_cap=100,
        )
        evaluator = MetricEvaluator([criterion], window)
        for entry in iter_journal_dir(tmp_path, ReadStats()):
            evaluator.feed(entry)
        assert evaluator.results()[0].counted_units == 7, pattern
