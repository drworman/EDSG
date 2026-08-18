"""Number formatting: readable, and never in scientific notation."""

from __future__ import annotations

import math

import pytest

from edsg.core.numbers import compact, credits, percentage, plain, quantity


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0"),
        (999, "999"),
        (1_000, "1K"),
        (3_200, "3.2K"),
        (12_500, "12.5K"),
        (125_000, "125K"),
        (1_000_000, "1M"),
        (1_250_000, "1.25M"),
        (12_500_000, "12.5M"),
        (7_000_000_000, "7B"),
        (1_500_000_000_000, "1.5T"),
        (-2_400_000, "-2.4M"),
    ],
)
def test_compact_reads_the_way_a_person_would_say_it(value, expected):
    assert compact(value) == expected


@pytest.mark.parametrize("value", [1e6, 1.25e6, 7e9, 1e12, 1e-6, 123456789.5])
def test_nothing_ever_renders_as_an_exponent(value):
    """A unit cap of a million used to reach users as '1e+06'."""
    for text in (plain(value), quantity(value), compact(value)):
        assert "e+" not in text.lower()
        assert "e-" not in text.lower()


def test_plain_keeps_the_exact_figure():
    assert plain(1_000_000) == "1,000,000"
    assert plain(1234.5) == "1,234.50"
    assert plain(1234.0) == "1,234"
    assert plain(1234.567, 1) == "1,234.6"


def test_quantity_drops_a_pointless_decimal():
    assert quantity(2000.0) == "2,000"
    assert quantity(0.5) == "0.50"


@pytest.mark.parametrize(
    ("fraction", "expected"),
    [(0.25, "25%"), (1.0, "100%"), (0.0, "0%"), (0.075, "7.5%")],
)
def test_percentages_drop_a_pointless_decimal(fraction, expected):
    assert percentage(fraction) == expected


def test_credits_can_be_long_or_short():
    assert credits(1_000_000_000) == "1,000,000,000 Cr"
    assert credits(1_000_000_000, short=True) == "1B Cr"
    assert credits(500, unit="Cr") == "500 Cr"


def test_infinities_and_nan_degrade_rather_than_raise():
    for value in (math.inf, -math.inf, math.nan):
        assert compact(value) == "—"
        assert plain(value) == "—"
        assert percentage(value) == "—"


def test_a_criterion_description_shows_real_numbers():
    """The description is printed in every report and shown in the
    organizer, and it was the loudest place exponents appeared."""
    from edsg.core.criteria import Criterion, Measure, MetricKind

    criterion = Criterion(
        criterion_id="x",
        label="Big",
        kind=MetricKind.MINING_REFINED,
        measure=Measure.TONNAGE,
        points_per_unit=1.0,
        unit_cap=1_000_000_000,
        minimum_units=1_000_000,
    )
    text = criterion.describe()
    assert "1,000,000,000" in text
    assert "1,000,000 minimum" in text
    assert "e+" not in text
