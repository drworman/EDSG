"""Goal tiers and how the reward pool is shared out.

Two things stack, and they are easy to conflate.

*Goal tiers* measure the **collective** effort. Every participant's
points add into one total, and that total climbs through tiers — rendered
the way Frontier renders it, "Tier 3/5". The thresholds are derived from
the event's criteria rather than typed: the top tier in use is worth
every criterion's unit cap converted to points, so a tier cannot drift
out of step with what it measures.

*Rewards* are shared out among individuals. The organizer sets one
figure, the maximum pool, and the goal tier reached decides how much of
it is unlocked. Nothing is unlocked below Tier 1.

The unlocked pool is then split in two:

- A **bonus** off the top, shared among the leading commanders in
  proportion to what each of them contributed.
- The **remainder**, shared among everyone in proportion to what they
  contributed.

Both halves are proportional, which is what makes the result fair at any
turnout. A flat per-head bonus looks simpler but pays a commander who
contributed almost nothing exactly what one who carried the event
receives, purely for landing inside the top ten. In a field of one whale
and twenty-five minnows that was an eighty-five-fold difference between
two commanders whose work was identical.

There is still a step at the edge of the bonus: the last commander inside
it earns roughly twice the first one outside. That is inherent to having
a leaderboard bonus at all, and it is deliberate.

Nothing here pays anybody. EDSG works out and publishes who is owed what;
handing over the credits happens in game, through the squadron bank.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Frontier runs at most five goal tiers, and more than that is
#: unreadable on a progress board.
MAX_GOAL_TIERS = 5

#: Commanders sharing the bonus taken off the top, by default.
DEFAULT_TOP_COUNT = 10

#: Fraction of the pool that bonus takes, by default.
DEFAULT_TOP_SHARE = 0.25


@dataclass
class GoalTier:
    """One collective threshold on the way to the goal."""

    label: str
    threshold: float

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "threshold": self.threshold}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoalTier:
        return cls(
            label=str(data.get("label", "")),
            threshold=float(data.get("threshold", 0.0)),
        )


@dataclass
class TierPlan:
    """An event's goal tiers and reward pool.

    Disabled by default: an event without rewards is still a perfectly
    good leaderboard.
    """

    enabled: bool = False
    #: How many goal tiers are in use, at most five. The thresholds
    #: themselves come from the criteria, not from the organizer.
    tier_count: int = MAX_GOAL_TIERS
    #: The largest total the organizer is willing to pay out, reached
    #: only if every goal tier is reached.
    reward_pool: float = 0.0
    #: How many leading commanders share the bonus taken off the top.
    top_count: int = DEFAULT_TOP_COUNT
    #: Fraction of the pool that bonus takes, 0..1.
    top_share: float = DEFAULT_TOP_SHARE
    currency: str = "Cr"

    # -- validation ----------------------------------------------------

    def validate(self, ceiling: float = 0.0) -> list[str]:
        """Return every problem preventing the plan from being used.

        ``ceiling`` is the combined unit-cap value of the event's
        criteria, which is what the top goal tier is worth.
        """
        problems: list[str] = []
        if not self.enabled:
            return problems

        if not 1 <= self.tier_count <= MAX_GOAL_TIERS:
            problems.append(f"Use between one and {MAX_GOAL_TIERS} goal tiers.")
        if self.reward_pool < 0:
            problems.append("The reward pool cannot be negative.")
        if ceiling <= 0:
            problems.append(
                "The goal has nothing to measure. Give every criterion a "
                "unit cap; together they set what the top tier is worth."
            )
        if self.top_count < 0:
            problems.append("The number of top commanders cannot be negative.")
        if not 0.0 <= self.top_share <= 1.0:
            problems.append("The share taken off the top must be between 0% and 100%.")
        return problems

    # -- derived tiers -------------------------------------------------

    def tiers_for(self, ceiling: float) -> list[GoalTier]:
        """Return the goal tiers, derived from the criteria.

        The top tier in use is the combined unit-cap value of every
        criterion — the most the event can be worth — and the rest step
        down in equal shares of it. Five tiers step in twentieths, four
        in quarters, so unticking a tier rebalances the others rather
        than leaving a gap.
        """
        count = max(1, min(self.tier_count, MAX_GOAL_TIERS))
        if ceiling <= 0:
            return []
        return [
            GoalTier(
                label=f"Tier {index}",
                threshold=round(ceiling * index / count, 4),
            )
            for index in range(1, count + 1)
        ]

    # -- progress ------------------------------------------------------

    def tier_reached(self, total: float, ceiling: float) -> int:
        """Return how many goal tiers ``total`` has cleared."""
        return sum(1 for tier in self.tiers_for(ceiling) if total >= tier.threshold)

    def pool_for(self, tiers_reached: int) -> float:
        """Return the credits unlocked by reaching ``tiers_reached``.

        The pool grows a share per tier and is whole only when every tier
        is reached. **Below Tier 1 nothing is unlocked at all**: the
        event did not achieve what it set out to.
        """
        count = max(1, min(self.tier_count, MAX_GOAL_TIERS))
        if tiers_reached < 1:
            return 0.0
        return round(self.reward_pool * min(tiers_reached, count) / count, 2)

    def progress_fraction(self, total: float, ceiling: float) -> float:
        """Return progress toward the top tier, clamped to 0..1."""
        if ceiling <= 0:
            return 0.0
        return max(0.0, min(1.0, total / ceiling))

    # -- serialisation -------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "tier_count": self.tier_count,
            "reward_pool": self.reward_pool,
            "top_count": self.top_count,
            "top_share": self.top_share,
            "currency": self.currency,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> TierPlan:
        data = data or {}

        def whole(key: str, fallback: int) -> int:
            try:
                return int(data.get(key, fallback))
            except (TypeError, ValueError):
                return fallback

        try:
            share = float(data.get("top_share", DEFAULT_TOP_SHARE))
        except (TypeError, ValueError):
            share = DEFAULT_TOP_SHARE

        count = whole("tier_count", MAX_GOAL_TIERS)
        return cls(
            enabled=bool(data.get("enabled", False)),
            tier_count=max(1, min(count, MAX_GOAL_TIERS)),
            reward_pool=float(data.get("reward_pool", 0.0)),
            top_count=max(0, whole("top_count", DEFAULT_TOP_COUNT)),
            top_share=min(max(share, 0.0), 1.0),
            currency=str(data.get("currency", "Cr")),
        )


@dataclass
class Payout:
    """What one commander is owed."""

    commander_name: str
    commander_fid: str
    points: float
    #: Fraction of the whole goal this commander contributed.
    share: float = 0.0
    #: Competition rank, shared by commanders on equal points.
    rank: int = 0
    in_top: bool = False
    bonus: float = 0.0
    proportional: float = 0.0

    @property
    def total(self) -> float:
        return round(self.bonus + self.proportional, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "commander": self.commander_name,
            "fid": self.commander_fid,
            "points": self.points,
            "share": round(self.share, 6),
            "in_top": self.in_top,
            "bonus": round(self.bonus, 2),
            "proportional": round(self.proportional, 2),
            "total": self.total,
        }


@dataclass
class ProgressReport:
    """The state of a tiered event: progress, and who is owed what."""

    plan: TierPlan
    total: float
    ceiling: float
    participants: int
    tiers_reached: int
    goal_tiers: list[GoalTier] = field(default_factory=list)
    payouts: list[Payout] = field(default_factory=list)
    pool: float = 0.0

    @property
    def next_tier(self) -> GoalTier | None:
        """Return the next tier not yet reached, if any."""
        if self.tiers_reached >= len(self.goal_tiers):
            return None
        return self.goal_tiers[self.tiers_reached]

    @property
    def to_next_tier(self) -> float:
        """Return the points still needed for the next tier."""
        upcoming = self.next_tier
        return max(0.0, upcoming.threshold - self.total) if upcoming else 0.0

    @property
    def fraction(self) -> float:
        return self.plan.progress_fraction(self.total, self.ceiling)

    @property
    def rewards_unlocked(self) -> bool:
        """Return whether anything is paid at all."""
        return self.tiers_reached >= 1

    @property
    def tier_text(self) -> str:
        """Return ``Tier 3/5``, as Frontier renders it."""
        return f"Tier {self.tiers_reached}/{len(self.goal_tiers)}"

    @property
    def paid_total(self) -> float:
        return round(sum(item.total for item in self.payouts), 2)

    @property
    def top_payouts(self) -> list[Payout]:
        return [item for item in self.payouts if item.in_top]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "ceiling": self.ceiling,
            "participants": self.participants,
            "tiers_reached": self.tiers_reached,
            "tier_count": len(self.goal_tiers),
            "rewards_unlocked": self.rewards_unlocked,
            "currency": self.plan.currency,
            "fraction": round(self.fraction, 6),
            "reward_pool_maximum": self.plan.reward_pool,
            "reward_pool_unlocked": self.pool,
            "top_count": self.plan.top_count,
            "top_share": self.plan.top_share,
            "paid_total": self.paid_total,
            "to_next_tier": self.to_next_tier,
            "next_tier": self.next_tier.to_dict() if self.next_tier else None,
            "goal_tiers": [tier.to_dict() for tier in self.goal_tiers],
            "payouts": [item.to_dict() for item in self.payouts],
        }


def rank_standings(standings: list[Any]) -> list[int]:
    """Return a competition rank per standing, ties sharing a position.

    Equal points means equal rank, and the next distinct score skips the
    positions the tie consumed: 1, 2, 2, 4.
    """
    ranks: list[int] = []
    previous: float | None = None
    position = 0
    for index, item in enumerate(standings, start=1):
        if previous is None or item.total_points != previous:
            position = index
            previous = item.total_points
        ranks.append(position)
    return ranks


def build_progress(
    plan: TierPlan, standings: list[Any], ceiling: float
) -> ProgressReport:
    """Work out tier progress and every commander's payout.

    ``standings`` is in rank order, and ``ceiling`` is the combined
    unit-cap value of the event's criteria.

    **Ties are paid alike.** Commanders on equal points hold the same
    rank, and if that rank falls at the edge of the top group they are
    all brought in — sharing the bonus among more people and diluting it
    for everyone in the group, rather than breaking the tie on something
    arbitrary like which file was read first.
    """
    total = float(sum(item.total_points for item in standings))
    participants = len(standings)
    goal_tiers = plan.tiers_for(ceiling)
    tiers_reached = plan.tier_reached(total, ceiling)
    pool = plan.pool_for(tiers_reached)

    ranks = rank_standings(standings)
    payouts = [
        Payout(
            commander_name=item.commander_name,
            commander_fid=item.commander_fid,
            points=item.total_points,
            share=(item.total_points / total) if total > 0 else 0.0,
            rank=rank,
        )
        for item, rank in zip(standings, ranks, strict=True)
    ]

    # The top group is everyone ranked inside the cut. A tie straddling
    # the boundary brings the whole tie in: splitting it would decide
    # real money on an accident of ordering.
    if plan.top_count > 0:
        cutoff = 0
        for item in payouts:
            if item.rank <= plan.top_count:
                cutoff = max(cutoff, item.rank)
        for item in payouts:
            item.in_top = bool(cutoff) and item.rank <= cutoff

    if pool > 0 and total > 0:
        bonus_pool = pool * plan.top_share
        rest_pool = pool - bonus_pool

        top_points = sum(item.points for item in payouts if item.in_top)
        # With no leading contributor worth rewarding, the bonus falls
        # back into the proportional share rather than going unpaid.
        if top_points <= 0:
            rest_pool = pool
            bonus_pool = 0.0

        for item in payouts:
            item.proportional = rest_pool * item.share
            if item.in_top and top_points > 0:
                # Proportional inside the group as well, so a commander
                # who barely qualified cannot collect what one who
                # carried the event collects.
                item.bonus = bonus_pool * (item.points / top_points)

    return ProgressReport(
        plan=plan,
        total=total,
        ceiling=ceiling,
        participants=participants,
        tiers_reached=tiers_reached,
        goal_tiers=goal_tiers,
        payouts=payouts,
        pool=pool,
    )


__all__ = [
    "DEFAULT_TOP_COUNT",
    "DEFAULT_TOP_SHARE",
    "MAX_GOAL_TIERS",
    "GoalTier",
    "Payout",
    "ProgressReport",
    "TierPlan",
    "build_progress",
    "rank_standings",
]
