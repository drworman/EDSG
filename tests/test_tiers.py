"""Goal tiers, reward bands and the progress board."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from edsg.core.tiers import (
    MAX_GOAL_TIERS,
    GoalTier,
    RewardBand,
    TierPlan,
    build_progress,
    default_reward_bands,
    even_tiers,
    tiers_from_step,
)


@dataclass
class FakeStanding:
    """Just enough of a Standing for the progress calculation."""

    commander_name: str
    commander_fid: str
    total_points: float


def field_of(count: int, top: float = 1000.0, step: float = 25.0):
    return [
        FakeStanding(f"CMDR {index:02d}", f"F{index:07d}", top - index * step)
        for index in range(count)
    ]


# -- tier construction --------------------------------------------------


def test_even_tiers_end_exactly_on_the_target():
    tiers = even_tiers(350_000_000, 5)
    assert len(tiers) == 5
    assert tiers[-1].threshold == 350_000_000
    assert [tier.threshold for tier in tiers] == sorted(
        tier.threshold for tier in tiers
    )


def test_an_uneven_target_puts_the_remainder_in_the_first_tier():
    """Later thresholds stay round and the last lands on the target."""
    tiers = even_tiers(1003, 3)
    assert tiers[-1].threshold == 1003
    assert tiers[0].threshold == 335  # 334 + remainder of 1
    assert tiers[1].threshold == 669


def test_tiers_are_capped_at_five():
    assert len(even_tiers(1000, 99)) == MAX_GOAL_TIERS


def test_stepping_down_from_the_target():
    tiers = tiers_from_step(1000, 5, from_top=True)
    assert [tier.threshold for tier in tiers] == [200, 400, 600, 800, 1000]


def test_stepping_up_from_the_first_tier():
    tiers = tiers_from_step(1000, 3, from_top=False)
    assert [tier.threshold for tier in tiers] == [1000, 1200, 1400]


def test_no_tiers_without_a_target():
    assert even_tiers(0, 5) == []
    assert tiers_from_step(0, 5, from_top=True) == []


# -- progress -----------------------------------------------------------


def test_tier_reached_counts_cleared_thresholds():
    plan = TierPlan(enabled=True, target=1000, goal_tiers=even_tiers(1000, 5))
    assert plan.tier_reached(0) == 0
    assert plan.tier_reached(200) == 1
    assert plan.tier_reached(650) == 3
    assert plan.tier_reached(5000) == 5


def test_the_multiplier_follows_the_tier_reached():
    plan = TierPlan(
        enabled=True,
        target=1000,
        goal_tiers=even_tiers(1000, 5),
        escalation=[1.0, 1.5, 2.0, 3.0, 4.5],
    )
    assert plan.multiplier_for(0) == 1.0
    assert plan.multiplier_for(3) == 2.0
    assert plan.multiplier_for(5) == 4.5
    # More tiers reached than multipliers supplied holds at the last.
    assert plan.multiplier_for(9) == 4.5


def test_progress_is_clamped_to_the_target():
    plan = TierPlan(enabled=True, target=100)
    assert plan.progress_fraction(-5) == 0.0
    assert plan.progress_fraction(50) == 0.5
    assert plan.progress_fraction(500) == 1.0


# -- reward bands -------------------------------------------------------


def test_a_fixed_band_sits_above_the_percentile_bands():
    """Frontier's tables read this way: Top 10 CMDRs is above Top 25%,
    not inside it, so nobody is paid from two bands."""
    plan = TierPlan(
        enabled=True,
        target=1_000_000,
        goal_tiers=even_tiers(1_000_000, 5),
        reward_bands=default_reward_bands(),
    )
    report = build_progress(plan, field_of(40))

    counts = [award.count for award in report.awards]
    assert counts[0] == 10
    assert sum(counts) == 40

    everyone = [name for award in report.awards for name in award.commanders]
    assert len(everyone) == len(set(everyone)), "a commander was paid twice"


def test_band_payouts_scale_with_the_tier_reached():
    plan = TierPlan(
        enabled=True,
        target=100,
        goal_tiers=[GoalTier("Tier 1", 50), GoalTier("Tier 2", 100)],
        reward_bands=[RewardBand(label="All", percentile=100.0, payout=1_000_000)],
        escalation=[2.0, 5.0],
    )
    # Two commanders at 60 points each clears both tiers.
    report = build_progress(plan, field_of(2, top=60, step=0))
    assert report.tiers_reached == 2
    assert report.awards[0].payout == 5_000_000


def test_empty_bands_are_still_reported():
    """The board should show what a band would have paid."""
    plan = TierPlan(
        enabled=True,
        target=100,
        reward_bands=[
            RewardBand(label="Top 10 CMDRs", top_count=10, payout=500),
            RewardBand(label="Rest", percentile=100.0, payout=100),
        ],
    )
    report = build_progress(plan, field_of(3))
    assert report.awards[0].count == 3
    assert report.awards[1].count == 0
    assert report.awards[1].payout == 0.0


def test_progress_with_no_participants():
    plan = TierPlan(enabled=True, target=100, reward_bands=default_reward_bands())
    report = build_progress(plan, [])
    assert report.total == 0
    assert report.participants == 0
    assert report.tiers_reached == 0
    assert all(award.count == 0 for award in report.awards)


def test_the_tier_text_matches_frontiers_wording():
    plan = TierPlan(enabled=True, target=1000, goal_tiers=even_tiers(1000, 5))
    report = build_progress(plan, field_of(4, top=100, step=0))
    assert report.tier_text == "Tier 2/5"


# -- validation ---------------------------------------------------------


def test_a_disabled_plan_needs_no_validation():
    assert TierPlan().validate() == []


def test_tiers_must_increase():
    plan = TierPlan(
        enabled=True,
        target=1000,
        goal_tiers=[GoalTier("A", 500), GoalTier("B", 200)],
    )
    assert any("increase" in problem for problem in plan.validate())


def test_a_tier_above_the_target_is_refused():
    plan = TierPlan(enabled=True, target=100, goal_tiers=[GoalTier("A", 500)])
    assert any("above the" in problem for problem in plan.validate())


def test_a_band_needs_a_count_or_a_percentile():
    plan = TierPlan(enabled=True, target=100, reward_bands=[RewardBand(label="Broken")])
    assert any("count or a percentile" in problem for problem in plan.validate())


@pytest.mark.parametrize("percentile", [0, -5, 101])
def test_percentiles_outside_the_range_are_refused(percentile):
    plan = TierPlan(
        enabled=True,
        target=100,
        reward_bands=[RewardBand(label="X", percentile=percentile)],
    )
    assert any("percentile" in problem for problem in plan.validate())


# -- serialisation ------------------------------------------------------


def test_a_plan_survives_a_round_trip():
    plan = TierPlan(
        enabled=True,
        target=16000,
        currency="Cr",
        goal_tiers=even_tiers(16000, 5),
        reward_bands=default_reward_bands(),
        escalation=[1.0, 1.5, 2.0, 3.0, 4.5],
    )
    restored = TierPlan.from_dict(plan.to_dict())
    assert restored.target == plan.target
    assert len(restored.goal_tiers) == 5
    assert restored.reward_bands[0].top_count == 10
    assert restored.escalation == plan.escalation


def test_an_event_carries_its_plan_through_an_invitation(
    tmp_path, simple_event, identity
):
    from edsg.core.workflow import issue_invitation, load_invitation

    simple_event.tiers = TierPlan(
        enabled=True,
        target=5000,
        goal_tiers=even_tiers(5000, 3),
        reward_bands=default_reward_bands(),
        escalation=[1.0, 2.0, 3.0],
    )
    invitation = load_invitation(issue_invitation(simple_event, identity, tmp_path))
    carried = invitation.event.tiers
    assert carried.enabled
    assert carried.target == 5000
    assert len(carried.goal_tiers) == 3


def test_a_plain_event_has_no_progress(simple_event):
    from edsg.core.standings import StandingsReport

    report = StandingsReport(event=simple_event, standings=[], accepted=[], rejected=[])
    assert report.progress() is None
