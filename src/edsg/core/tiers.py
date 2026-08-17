"""Goal tiers, reward bands and progress.

Modelled on Frontier's own community goals, which combine two things
that are easy to conflate:

*Goal tiers* measure the **collective** effort. Every participant's
points add into one total, and that total climbs through tiers toward a
target — Frontier renders this as "Tier 3/5".

*Reward bands* rank **individuals** against each other. Frontier uses a
fixed count for the top band ("Top 10 CMDRs") and percentiles below it
("Top 25%", "Top 50%", …), each paying a different amount.

The two combine: the band a commander lands in decides *which* payout
they get, and the goal tier the community reached decides *how much* that
payout is worth. Rather than asking an organizer to fill a five-by-five
grid of amounts, EDSG takes a base payout per band and a multiplier per
goal tier — the same shape in ten inputs instead of twenty-five.

Nothing here pays anybody. EDSG works out and publishes who is owed what;
handing over the credits happens in-game.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

#: Frontier runs at most five goal tiers, and more than that is
#: unreadable on a progress board.
MAX_GOAL_TIERS = 5

#: The same ceiling applies to reward bands.
MAX_REWARD_BANDS = 5


@dataclass
class GoalTier:
    """One collective threshold on the way to the target."""

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
class RewardBand:
    """One slice of the ranked participants, and what it pays.

    ``top_count`` set makes this a fixed-size band — Frontier's "Top 10
    CMDRs". Otherwise ``percentile`` defines the band as everyone down to
    that share of the field.
    """

    label: str
    payout: float = 0.0
    top_count: int | None = None
    percentile: float | None = None

    @property
    def is_fixed_count(self) -> bool:
        return self.top_count is not None and self.top_count > 0

    def describe(self) -> str:
        """Return how this band selects its members."""
        if self.is_fixed_count:
            return f"top {self.top_count} commanders"
        return f"top {self.percentile:g}% of the field"

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "payout": self.payout,
            "top_count": self.top_count,
            "percentile": self.percentile,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RewardBand:
        count = data.get("top_count")
        percentile = data.get("percentile")
        return cls(
            label=str(data.get("label", "")),
            payout=float(data.get("payout", 0.0)),
            top_count=int(count) if count else None,
            percentile=float(percentile) if percentile is not None else None,
        )


@dataclass
class TierPlan:
    """An event's goal tiers, reward bands and escalation.

    Disabled by default: an event without a target is still a perfectly
    good event, and the progress board simply does not appear.
    """

    enabled: bool = False
    #: How many goal tiers are in use, at most five. The thresholds
    #: themselves are derived from the criteria, not typed.
    tier_count: int = MAX_GOAL_TIERS
    #: The largest total the organizer is willing to pay out, reached
    #: only if every goal tier is reached.
    reward_pool: float = 0.0
    reward_bands: list[RewardBand] = field(default_factory=list)
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
        if len(self.reward_bands) > MAX_REWARD_BANDS:
            problems.append(f"At most {MAX_REWARD_BANDS} reward tiers are supported.")
        if not self.reward_bands:
            problems.append("Add at least one reward tier.")

        for band in self.reward_bands:
            if not band.label.strip():
                problems.append("Every reward tier needs a name.")
            if band.top_count is None and band.percentile is None:
                problems.append(
                    f"Reward tier '{band.label}' needs either a commander "
                    f"count or a percentile."
                )
            if band.percentile is not None and not 0 < band.percentile <= 100:
                problems.append(
                    f"Reward tier '{band.label}': percentile must be above 0 "
                    f"and at most 100."
                )
        return problems

    # -- derived tiers -------------------------------------------------

    def tiers_for(self, ceiling: float) -> list[GoalTier]:
        """Return the goal tiers, derived from the criteria.

        The top tier in use is the combined unit-cap value of every
        criterion — the most the event can possibly be worth — and the
        rest step down in equal shares of it. Five tiers step in
        twentieths, four in quarters, and so on, so unticking a tier
        rebalances the others rather than leaving a gap.

        Nothing here is typed by the organizer, so a tier cannot drift
        out of step with the criteria it is measuring.
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

        The pool grows a share per tier and is only whole once every
        tier is reached. **Tier 1 unlocks nothing on its own being
        missed**: below it the event paid for nothing, so the pool is
        zero.
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
            "currency": self.currency,
            "reward_bands": [band.to_dict() for band in self.reward_bands],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> TierPlan:
        data = data or {}
        bands = [
            RewardBand.from_dict(item)
            for item in (data.get("reward_bands") or [])
            if isinstance(item, dict)
        ]
        try:
            count = int(data.get("tier_count", MAX_GOAL_TIERS))
        except (TypeError, ValueError):
            count = MAX_GOAL_TIERS
        return cls(
            enabled=bool(data.get("enabled", False)),
            tier_count=max(1, min(count, MAX_GOAL_TIERS)),
            reward_pool=float(data.get("reward_pool", 0.0)),
            currency=str(data.get("currency", "Cr")),
            reward_bands=bands,
        )


def band_weights(count: int) -> list[float]:
    """Return the relative value of a place in each reward tier.

    Descending, so a place in the top tier is worth the most: with five
    tiers the weights are 5, 4, 3, 2 and 1.

    These weigh **each commander**, not each tier. Weighing whole tiers
    instead produces an absurdity whenever the tiers are uneven — a tier
    holding one commander would split the same slice one way that the
    top ten split ten ways, and eleventh place would out-earn first.
    """
    if count <= 0:
        return []
    return [float(value) for value in range(count, 0, -1)]


def default_reward_bands() -> list[RewardBand]:
    """Return bands shaped like Frontier's, for the organizer to edit."""
    return [
        RewardBand(label="Top 10 CMDRs", top_count=10),
        RewardBand(label="Top 25%", percentile=25.0),
        RewardBand(label="Top 50%", percentile=50.0),
        RewardBand(label="Top 75%", percentile=75.0),
        RewardBand(label="Top 100%", percentile=100.0),
    ]


@dataclass
class BandAward:
    """What one reward tier worked out to for the commanders in it."""

    band: RewardBand
    commanders: list[tuple[str, str, float]] = field(default_factory=list)
    #: Relative value of a single place in this tier.
    weight: float = 0.0
    #: Fraction of the unlocked pool this tier ended up taking.
    share: float = 0.0
    pool: float = 0.0
    each: float = 0.0
    lowest_points: float = 0.0
    highest_points: float = 0.0

    @property
    def count(self) -> int:
        return len(self.commanders)

    def range_text(self) -> str:
        """Return the points range this tier covers, Inara-style."""
        if not self.commanders:
            return "\u2014"
        if self.lowest_points == self.highest_points:
            return f"{self.lowest_points:,.0f}"
        return f"{self.lowest_points:,.0f} to {self.highest_points:,.0f}"


@dataclass
class ProgressReport:
    """The state of a tiered event: progress, and who is owed what."""

    plan: TierPlan
    total: float
    ceiling: float
    participants: int
    tiers_reached: int
    goal_tiers: list[GoalTier] = field(default_factory=list)
    awards: list[BandAward] = field(default_factory=list)
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
        """Return whether anything is paid at all.

        Tier 1 is the floor: below it the event achieved nothing it set
        out to, and nobody is paid.
        """
        return self.tiers_reached >= 1

    @property
    def tier_text(self) -> str:
        """Return ``Tier 3/5``, as Frontier renders it."""
        return f"Tier {self.tiers_reached}/{len(self.goal_tiers)}"

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
            "to_next_tier": self.to_next_tier,
            "next_tier": self.next_tier.to_dict() if self.next_tier else None,
            "goal_tiers": [tier.to_dict() for tier in self.goal_tiers],
            "awards": [
                {
                    "band": award.band.label,
                    "selects": award.band.describe(),
                    "share": round(award.share, 6),
                    "pool": award.pool,
                    "each": award.each,
                    "commander_count": award.count,
                    "commanders": [
                        {"name": name, "fid": fid, "points": points}
                        for name, fid, points in award.commanders
                    ],
                    "points_low": award.lowest_points,
                    "points_high": award.highest_points,
                }
                for award in self.awards
            ],
        }


def build_progress(
    plan: TierPlan, standings: list[Any], ceiling: float
) -> ProgressReport:
    """Work out tier progress and per-tier awards from ranked standings.

    ``ceiling`` is the combined unit-cap value of the event's criteria:
    the most the event can be worth, and therefore the top goal tier.

    Bands are filled by position, so each commander lands in exactly one
    — the best they qualify for. That is how Frontier's tables read,
    with `Top 10 CMDRs` sitting above the `Top 25%` range rather than
    inside it.
    """
    total = float(sum(item.total_points for item in standings))
    participants = len(standings)
    goal_tiers = plan.tiers_for(ceiling)
    tiers_reached = plan.tier_reached(total, ceiling)
    pool = plan.pool_for(tiers_reached)

    weights = band_weights(len(plan.reward_bands))
    awards: list[BandAward] = []
    assigned = 0
    for index, band in enumerate(plan.reward_bands):
        award = BandAward(band=band, share=0.0)
        award.weight = weights[index] if index < len(weights) else 0.0

        if assigned < participants:
            if band.is_fixed_count:
                end = min(assigned + int(band.top_count or 0), participants)
            else:
                fraction = (band.percentile or 100.0) / 100.0
                end = min(
                    max(assigned + 1, math.ceil(participants * fraction)),
                    participants,
                )
            members = standings[assigned:end]
            if members:
                award.commanders = [
                    (item.commander_name, item.commander_fid, item.total_points)
                    for item in members
                ]
                points = [item.total_points for item in members]
                award.lowest_points = min(points)
                award.highest_points = max(points)
                assigned = end

        awards.append(award)

    # The pool is shared out per commander rather than per tier, so a
    # place in a higher tier is always worth more than a place in a
    # lower one however the field falls. Every credit in the unlocked
    # pool is allocated, and never more than it.
    denominator = sum(award.weight * award.count for award in awards)
    if pool > 0 and denominator > 0:
        for award in awards:
            if not award.count:
                continue
            award.each = round(pool * award.weight / denominator, 2)
            award.pool = round(award.each * award.count, 2)
            award.share = award.pool / pool if pool else 0.0

    return ProgressReport(
        plan=plan,
        total=total,
        ceiling=ceiling,
        participants=participants,
        tiers_reached=tiers_reached,
        goal_tiers=goal_tiers,
        awards=awards,
        pool=pool,
    )


__all__ = [
    "MAX_GOAL_TIERS",
    "MAX_REWARD_BANDS",
    "BandAward",
    "GoalTier",
    "ProgressReport",
    "RewardBand",
    "TierPlan",
    "band_weights",
    "build_progress",
    "default_reward_bands",
]
