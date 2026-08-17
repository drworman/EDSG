"""Goal tiers, the reward pool and how it is shared out."""

from __future__ import annotations

import random
from dataclasses import dataclass

import pytest

from edsg.core.criteria import Criterion, Measure, MetricKind
from edsg.core.models import EventDefinition
from edsg.core.tiers import (
    MAX_GOAL_TIERS,
    TierPlan,
    build_progress,
    rank_standings,
)

CEILING = 2000.0


@dataclass
class FakeStanding:
    """Just enough of a Standing for the progress calculation."""

    commander_name: str
    commander_fid: str
    total_points: float


def field_of(count: int, top: float = 200.0, step: float = 5.0):
    return [
        FakeStanding(f"CMDR {index:02d}", f"F{index:07d}", top - index * step)
        for index in range(count)
    ]


def plan_of(tier_count=5, pool=800_000_000.0, top_count=10, top_share=0.25):
    return TierPlan(
        enabled=True,
        tier_count=tier_count,
        reward_pool=pool,
        top_count=top_count,
        top_share=top_share,
    )


# -- tiers are derived, never typed -------------------------------------


def test_the_top_tier_is_the_events_point_ceiling():
    event = EventDefinition(
        name="X",
        criteria=[
            Criterion(
                criterion_id="a",
                label="Tritium",
                kind=MetricKind.MINING_REFINED,
                measure=Measure.TONNAGE,
                points_per_unit=1.0,
                unit_cap=1000,
            ),
            Criterion(
                criterion_id="b",
                label="Bodies",
                kind=MetricKind.BODIES_SCANNED,
                measure=Measure.DISTINCT,
                points_per_unit=5.0,
                unit_cap=200,
            ),
        ],
    )
    assert event.point_ceiling() == 2000.0
    assert plan_of().tiers_for(event.point_ceiling())[-1].threshold == 2000.0


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (5, [400, 800, 1200, 1600, 2000]),
        (4, [500, 1000, 1500, 2000]),
        (2, [1000, 2000]),
        (1, [2000]),
    ],
)
def test_unticking_a_tier_rebalances_the_rest(count, expected):
    tiers = plan_of(tier_count=count).tiers_for(CEILING)
    assert [tier.threshold for tier in tiers] == expected


def test_tier_count_is_capped_at_five():
    assert len(plan_of(tier_count=99).tiers_for(CEILING)) == MAX_GOAL_TIERS


# -- the pool -----------------------------------------------------------


def test_the_pool_grows_a_share_per_tier():
    plan = plan_of(tier_count=5, pool=500)
    assert plan.pool_for(1) == 100
    assert plan.pool_for(3) == 300
    assert plan.pool_for(5) == 500


def test_nothing_is_paid_below_tier_one():
    report = build_progress(plan_of(pool=500), field_of(4, top=10, step=0), CEILING)
    assert report.tiers_reached == 0
    assert not report.rewards_unlocked
    assert report.pool == 0.0
    assert all(item.total == 0 for item in report.payouts)


# -- ranking ------------------------------------------------------------


def test_ties_share_a_rank_and_skip_the_next_positions():
    standings = [
        FakeStanding("A", "F1", 100),
        FakeStanding("B", "F2", 100),
        FakeStanding("C", "F3", 50),
        FakeStanding("D", "F4", 25),
    ]
    assert rank_standings(standings) == [1, 1, 3, 4]


def test_tied_commanders_are_paid_alike():
    """Equal work must earn equal money, whatever order the files
    happened to be read in."""
    standings = [
        FakeStanding("A", "F1", 100),
        FakeStanding("B", "F2", 100),
        FakeStanding("C", "F3", 50),
    ]
    report = build_progress(plan_of(pool=1_000_000, top_count=1), standings, 250.0)
    paid = {item.commander_name: item.total for item in report.payouts}
    assert paid["A"] == paid["B"]
    assert paid["A"] > paid["C"]


def test_a_tie_at_the_boundary_brings_the_whole_tie_into_the_top():
    """Splitting a tie would decide real money on an accident of
    ordering, so the group widens and the bonus dilutes instead."""
    standings = [
        FakeStanding("A", "F1", 100),
        FakeStanding("B", "F2", 50),
        FakeStanding("C", "F3", 50),
        FakeStanding("D", "F4", 50),
        FakeStanding("E", "F5", 10),
    ]
    report = build_progress(plan_of(pool=1_000_000, top_count=2), standings, 260.0)
    in_top = {item.commander_name for item in report.payouts if item.in_top}
    assert in_top == {"A", "B", "C", "D"}
    paid = {item.commander_name: item.total for item in report.payouts}
    assert paid["B"] == paid["C"] == paid["D"]


# -- distribution -------------------------------------------------------


def test_a_lower_contribution_never_out_earns_a_higher_one():
    for count in (1, 2, 7, 18, 40, 137):
        report = build_progress(plan_of(), field_of(count, top=1000, step=1), CEILING)
        paid = [item.total for item in report.payouts]
        assert paid == sorted(paid, reverse=True), f"{count} participants"


def test_the_bonus_is_proportional_inside_the_top_group():
    """A flat per-head bonus paid a commander who contributed 0.04% the
    same as one who contributed 99%, purely for landing in the top ten."""
    standings = [FakeStanding("Whale", "F0", 50_000)] + [
        FakeStanding(f"Min{index:02d}", f"F{index + 1}", 20) for index in range(25)
    ]
    report = build_progress(plan_of(pool=800_000_000), standings, 50_500.0)
    paid = {item.commander_name: item.total for item in report.payouts}

    assert paid["Whale"] > paid["Min00"] * 100
    # Every minnow did identical work, so every minnow is paid alike.
    minnows = {paid[f"Min{index:02d}"] for index in range(25)}
    assert len(minnows) == 1


def test_a_commander_who_contributed_nothing_is_paid_nothing():
    standings = [FakeStanding("Solo", "F1", 1000)] + [
        FakeStanding(f"Idle{index}", f"F{index + 2}", 0.0) for index in range(5)
    ]
    report = build_progress(plan_of(pool=800_000_000), standings, 1000.0)
    paid = {item.commander_name: item.total for item in report.payouts}
    assert paid["Solo"] > 0
    assert all(paid[f"Idle{index}"] == 0 for index in range(5))


def test_the_pool_is_never_exceeded():
    random.seed(5)
    for _ in range(300):
        count = random.randint(1, 90)
        standings = [
            FakeStanding(
                f"C{index}", f"F{index}", round(random.random() ** 2 * 1000, 2)
            )
            for index in range(count)
        ]
        standings.sort(key=lambda item: -item.total_points)
        report = build_progress(plan_of(pool=800_000_000), standings, CEILING)
        assert report.paid_total <= report.pool + 1.0


def test_everyone_who_contributed_is_paid():
    report = build_progress(plan_of(), field_of(40, top=1000, step=1), CEILING)
    assert all(item.total > 0 for item in report.payouts)


def test_turning_the_bonus_off_pays_purely_by_contribution():
    report = build_progress(
        plan_of(pool=1_000_000, top_count=0), field_of(5, top=100, step=10), CEILING
    )
    assert not any(item.in_top for item in report.payouts)
    first = report.payouts[0]
    assert first.total == pytest.approx(report.pool * first.share, rel=1e-6)


# -- validation and serialisation ---------------------------------------


def test_a_disabled_plan_needs_no_validation():
    assert TierPlan().validate(0) == []


def test_a_plan_needs_something_to_measure():
    assert any("nothing to measure" in item for item in plan_of().validate(0))


@pytest.mark.parametrize("share", [-0.1, 1.5])
def test_a_share_outside_the_range_is_refused(share):
    plan = plan_of(top_share=share)
    assert any("between 0% and 100%" in item for item in plan.validate(CEILING))


def test_a_plan_survives_a_round_trip():
    plan = plan_of(tier_count=4, pool=250_000_000, top_count=3, top_share=0.4)
    restored = TierPlan.from_dict(plan.to_dict())
    assert restored.tier_count == 4
    assert restored.reward_pool == 250_000_000
    assert restored.top_count == 3
    assert restored.top_share == 0.4


def test_rubbish_in_a_hand_edited_plan_degrades():
    restored = TierPlan.from_dict(
        {"enabled": True, "tier_count": "many", "top_count": None, "top_share": "half"}
    )
    assert restored.tier_count == MAX_GOAL_TIERS
    assert restored.top_count == 10
    assert restored.top_share == 0.25


def test_an_event_carries_its_plan_through_an_invitation(
    tmp_path, simple_event, identity
):
    from edsg.core.workflow import issue_invitation, load_invitation

    simple_event.tiers = plan_of(tier_count=3, pool=90_000_000, top_count=5)
    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))
    carried = invitation.event.tiers
    assert carried.enabled
    assert carried.tier_count == 3
    assert carried.top_count == 5


def test_a_plain_event_has_no_progress(simple_event):
    from edsg.core.standings import StandingsReport

    report = StandingsReport(event=simple_event, standings=[], accepted=[], rejected=[])
    assert report.progress() is None
