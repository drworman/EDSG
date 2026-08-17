"""Filling a unit cap in the order the work actually happened."""

from __future__ import annotations

import pytest

from edsg.core.allocation import allocate_all, allocate_criterion
from edsg.core.criteria import Criterion, Measure, MetricKind


def criterion(cap=100.0, minimum=None, points=1.0):
    return Criterion(
        criterion_id="t",
        label="Tritium",
        kind=MetricKind.MINING_REFINED,
        measure=Measure.TONNAGE,
        points_per_unit=points,
        unit_cap=cap,
        minimum_units=minimum,
    )


def test_the_cap_fills_in_the_order_the_work_happened():
    """The worked example: A leads on volume and submits first, but B
    does the work that fills the cap, so B takes the larger share."""
    result = allocate_criterion(
        criterion(cap=100),
        {
            "A": [("10:00", 43.0), ("12:00", 70.0)],
            "B": [("11:00", 60.0)],
        },
    )
    assert result.units_for("A") == 43.0
    assert result.units_for("B") == 57.0
    assert result.total_units == 100.0
    assert result.cap_reached
    assert result.cap_reached_at == "11:00"
    assert result.cap_reached_by == "B"


def test_submission_order_does_not_matter():
    """The same events allocate identically whichever way they arrive."""
    events = {
        "A": [("10:00", 43.0), ("12:00", 70.0)],
        "B": [("11:00", 60.0)],
    }
    forwards = allocate_criterion(criterion(), events)
    backwards = allocate_criterion(criterion(), {"B": events["B"], "A": events["A"]})
    assert forwards.units_for("A") == backwards.units_for("A")
    assert forwards.units_for("B") == backwards.units_for("B")


def test_work_after_the_cap_is_forfeited():
    result = allocate_criterion(
        criterion(cap=50), {"A": [("10:00", 30.0), ("11:00", 40.0)]}
    )
    entry = result.allocated["A"]
    assert entry.units == 50.0
    assert entry.offered == 70.0
    assert entry.forfeited == 20.0


def test_an_event_is_split_when_it_straddles_the_cap():
    result = allocate_criterion(criterion(cap=100), {"A": [("10:00", 250.0)]})
    assert result.units_for("A") == 100.0
    assert result.allocated["A"].forfeited == 150.0


def test_nothing_is_credited_past_a_full_cap():
    result = allocate_criterion(
        criterion(cap=10),
        {"A": [("09:00", 10.0)], "B": [("10:00", 99.0)]},
    )
    assert result.units_for("A") == 10.0
    assert result.units_for("B") == 0.0
    assert result.total_units == 10.0


def test_ties_resolve_the_same_way_every_time():
    """Two events at the same instant must not depend on dict order."""
    first = allocate_criterion(
        criterion(cap=10), {"A": [("10:00", 8.0)], "B": [("10:00", 8.0)]}
    )
    second = allocate_criterion(
        criterion(cap=10), {"B": [("10:00", 8.0)], "A": [("10:00", 8.0)]}
    )
    assert first.units_for("A") == second.units_for("A")
    assert first.units_for("B") == second.units_for("B")


def test_points_follow_the_allocated_units():
    result = allocate_criterion(
        criterion(cap=100, points=2.5), {"A": [("10:00", 40.0)]}
    )
    assert result.points_for("A") == 100.0


# -- the participation floor -------------------------------------------


def test_a_commander_below_the_minimum_scores_nothing():
    result = allocate_criterion(
        criterion(cap=100, minimum=20),
        {"A": [("10:00", 80.0)], "B": [("11:00", 5.0)]},
    )
    assert result.units_for("A") == 80.0
    assert result.points_for("A") == 80.0
    # B is credited the units but scores no points.
    assert result.units_for("B") == 5.0
    assert result.points_for("B") == 0.0
    assert result.allocated["B"].below_minimum


def test_forfeited_units_are_not_redistributed():
    """Redistributing would change who filled the cap and when, so the
    allocation would stop describing what happened."""
    result = allocate_criterion(
        criterion(cap=100, minimum=50),
        {"A": [("10:00", 90.0)], "B": [("11:00", 10.0)]},
    )
    assert result.total_units == 100.0
    assert result.units_for("A") == 90.0
    assert result.points_for("B") == 0.0
    # A does not gain B's forfeited ten.
    assert result.units_for("A") != 100.0


# -- shape --------------------------------------------------------------


def test_every_criterion_is_allocated():
    criteria = [
        criterion(),
        Criterion(
            criterion_id="other",
            label="Other",
            kind=MetricKind.EVENT_COUNT,
            measure=Measure.COUNT,
            unit_cap=5,
        ),
    ]
    result = allocate_all(criteria, {"t": {"A": [("10:00", 5.0)]}})
    assert set(result) == {"t", "other"}
    assert result["other"].total_units == 0.0


def test_a_commander_with_no_contributions_is_still_listed():
    result = allocate_criterion(criterion(), {"A": []})
    assert "A" in result.allocated
    assert result.units_for("A") == 0.0


def test_the_allocation_serialises():
    result = allocate_criterion(criterion(cap=100), {"A": [("10:00", 43.0)]})
    payload = result.to_dict()
    assert payload["cap"] == 100
    assert payload["allocated"]["A"]["units"] == 43.0
    assert "forfeited" in payload["allocated"]["A"]


@pytest.mark.parametrize("cap", [1, 7, 100, 12345])
def test_the_total_never_exceeds_the_cap(cap):
    result = allocate_criterion(
        criterion(cap=cap),
        {f"F{index}": [(f"1{index}:00", cap)] for index in range(5)},
    )
    assert result.total_units <= cap
