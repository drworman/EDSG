"""Goal tiers, reward pools and the distribution matrix."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from edsg.core.criteria import Criterion, Measure, MetricKind
from edsg.core.models import EventDefinition
from edsg.core.tiers import (
    MAX_GOAL_TIERS,
    RewardBand,
    TierPlan,
    band_weights,
    build_progress,
    default_reward_bands,
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


def plan_of(tier_count: int = 5, pool: float = 500_000_000.0) -> TierPlan:
    return TierPlan(
        enabled=True,
        tier_count=tier_count,
        reward_pool=pool,
        reward_bands=default_reward_bands(),
    )


# -- tiers are derived, never typed -------------------------------------


def test_the_top_tier_is_the_events_point_ceiling():
    """The organizer never types a target; it comes from the caps."""
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
    tiers = plan_of().tiers_for(event.point_ceiling())
    assert tiers[-1].threshold == 2000.0


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
    """Five tiers step in twentieths, four in quarters, and so on."""
    tiers = plan_of(tier_count=count).tiers_for(CEILING)
    assert [tier.threshold for tier in tiers] == expected


def test_tier_count_is_capped_at_five():
    assert len(plan_of(tier_count=99).tiers_for(CEILING)) == MAX_GOAL_TIERS


def test_no_tiers_without_a_ceiling():
    assert plan_of().tiers_for(0) == []


# -- the reward pool ----------------------------------------------------


def test_the_pool_grows_a_share_per_tier():
    plan = plan_of(tier_count=5, pool=500)
    assert plan.pool_for(1) == 100
    assert plan.pool_for(3) == 300
    assert plan.pool_for(5) == 500


def test_nothing_is_paid_below_tier_one():
    """Tier 1 is the floor: under it the event achieved nothing."""
    plan = plan_of(pool=500)
    assert plan.pool_for(0) == 0.0

    report = build_progress(plan, field_of(4, top=10, step=0), CEILING)
    assert report.tiers_reached == 0
    assert not report.rewards_unlocked
    assert report.pool == 0.0
    assert all(award.each == 0 for award in report.awards)


def test_reaching_every_tier_unlocks_the_whole_pool():
    plan = plan_of(pool=500)
    report = build_progress(plan, field_of(10, top=1000, step=0), CEILING)
    assert report.tiers_reached == 5
    assert report.pool == 500


# -- distribution -------------------------------------------------------


def test_a_place_in_a_higher_tier_is_always_worth_more():
    """Weighing whole tiers rather than places would let eleventh
    place out-earn first whenever the tiers were uneven."""
    report = build_progress(plan_of(), field_of(18, top=1000, step=1), CEILING)
    paid = [award.each for award in report.awards if award.count]
    assert paid == sorted(paid, reverse=True)
    assert paid[0] > paid[-1]


def test_the_pool_is_never_exceeded():
    for count in (1, 2, 7, 18, 40, 137):
        report = build_progress(
            plan_of(pool=500_000_000), field_of(count, top=1000, step=1), CEILING
        )
        spent = sum(award.each * award.count for award in report.awards)
        assert spent <= report.pool + 1.0, f"{count} participants overspent"


def test_weights_descend_by_tier():
    assert band_weights(5) == [5.0, 4.0, 3.0, 2.0, 1.0]
    assert band_weights(0) == []


def test_every_commander_is_paid_from_exactly_one_tier():
    report = build_progress(plan_of(), field_of(40, top=1000, step=1), CEILING)
    seen = [fid for award in report.awards for _, fid, _ in award.commanders]
    assert len(seen) == len(set(seen)) == 40


def test_a_fixed_tier_sits_above_the_percentile_tiers():
    report = build_progress(plan_of(), field_of(40, top=1000, step=1), CEILING)
    assert report.awards[0].count == 10
    assert report.awards[0].highest_points >= report.awards[1].highest_points


def test_an_empty_tier_pays_nothing():
    report = build_progress(plan_of(), field_of(3, top=1000, step=1), CEILING)
    assert report.awards[0].count == 3
    assert report.awards[-1].count == 0
    assert report.awards[-1].each == 0.0


def test_progress_with_no_participants():
    report = build_progress(plan_of(), [], CEILING)
    assert report.total == 0
    assert report.participants == 0
    assert not report.rewards_unlocked


def test_the_tier_text_matches_frontiers_wording():
    report = build_progress(plan_of(), field_of(4, top=250, step=0), CEILING)
    assert report.tier_text == "Tier 2/5"


# -- validation ---------------------------------------------------------


def test_a_disabled_plan_needs_no_validation():
    assert TierPlan().validate(0) == []


def test_a_plan_needs_something_to_measure():
    assert any("nothing to measure" in item for item in plan_of().validate(0))


def test_a_plan_needs_at_least_one_reward_tier():
    plan = TierPlan(enabled=True, reward_pool=100, reward_bands=[])
    assert any("at least one reward tier" in item for item in plan.validate(100))


def test_a_negative_pool_is_refused():
    plan = plan_of(pool=-1)
    assert any("cannot be negative" in item for item in plan.validate(CEILING))


@pytest.mark.parametrize("percentile", [0, -5, 101])
def test_percentiles_outside_the_range_are_refused(percentile):
    plan = TierPlan(
        enabled=True,
        reward_pool=100,
        reward_bands=[RewardBand(label="X", percentile=percentile)],
    )
    assert any("percentile" in item for item in plan.validate(CEILING))


# -- serialisation ------------------------------------------------------


def test_a_plan_survives_a_round_trip():
    plan = plan_of(tier_count=4, pool=250_000_000)
    restored = TierPlan.from_dict(plan.to_dict())
    assert restored.tier_count == 4
    assert restored.reward_pool == 250_000_000
    assert len(restored.reward_bands) == 5
    assert restored.reward_bands[0].top_count == 10


def test_an_event_carries_its_plan_through_an_invitation(
    tmp_path, simple_event, identity
):
    from edsg.core.workflow import issue_invitation, load_invitation

    simple_event.tiers = plan_of(tier_count=3, pool=90_000_000)
    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))
    carried = invitation.event.tiers
    assert carried.enabled
    assert carried.tier_count == 3
    assert carried.reward_pool == 90_000_000


def test_a_plain_event_has_no_progress(simple_event):
    from edsg.core.standings import StandingsReport

    report = StandingsReport(event=simple_event, standings=[], accepted=[], rejected=[])
    assert report.progress() is None
