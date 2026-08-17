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

#: Step used when tiers are calculated rather than typed.
DEFAULT_TIER_STEP = 0.20


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
    target: float = 0.0
    goal_tiers: list[GoalTier] = field(default_factory=list)
    reward_bands: list[RewardBand] = field(default_factory=list)
    #: Payout multiplier per goal tier reached, indexed from tier 1. A
    #: shorter list than ``goal_tiers`` is fine; missing entries mean 1.0.
    escalation: list[float] = field(default_factory=list)
    currency: str = "Cr"

    # -- validation ----------------------------------------------------

    def validate(self) -> list[str]:
        """Return every problem preventing the plan from being used."""
        problems: list[str] = []
        if not self.enabled:
            return problems

        if self.target <= 0:
            problems.append(
                "Set a goal target above zero, or turn the progress board off."
            )
        if len(self.goal_tiers) > MAX_GOAL_TIERS:
            problems.append(f"At most {MAX_GOAL_TIERS} goal tiers are supported.")
        if len(self.reward_bands) > MAX_REWARD_BANDS:
            problems.append(f"At most {MAX_REWARD_BANDS} reward bands are supported.")

        thresholds = [tier.threshold for tier in self.goal_tiers]
        if any(value <= 0 for value in thresholds):
            problems.append("Every goal tier needs a threshold above zero.")
        if thresholds != sorted(thresholds):
            problems.append(
                "Goal tier thresholds must increase from the first to the last."
            )
        if len(set(thresholds)) != len(thresholds):
            problems.append("Two goal tiers share the same threshold.")
        if thresholds and thresholds[-1] > self.target:
            problems.append(
                f"The last goal tier ({thresholds[-1]:,.0f}) is above the "
                f"target ({self.target:,.0f})."
            )

        for band in self.reward_bands:
            if not band.label.strip():
                problems.append("Every reward band needs a name.")
            if band.top_count is None and band.percentile is None:
                problems.append(
                    f"Reward band '{band.label}' needs either a commander "
                    f"count or a percentile."
                )
            if band.percentile is not None and not 0 < band.percentile <= 100:
                problems.append(
                    f"Reward band '{band.label}': percentile must be above 0 "
                    f"and at most 100."
                )
        if any(value <= 0 for value in self.escalation):
            problems.append("Escalation multipliers must be above zero.")
        return problems

    # -- progress ------------------------------------------------------

    def tier_reached(self, total: float) -> int:
        """Return how many goal tiers ``total`` has cleared."""
        return sum(1 for tier in self.goal_tiers if total >= tier.threshold)

    def multiplier_for(self, tiers_reached: int) -> float:
        """Return the payout multiplier for a number of tiers reached."""
        if tiers_reached <= 0 or not self.escalation:
            return 1.0
        index = min(tiers_reached, len(self.escalation)) - 1
        return self.escalation[index]

    def progress_fraction(self, total: float) -> float:
        """Return progress toward the target, clamped to 0..1."""
        if self.target <= 0:
            return 0.0
        return max(0.0, min(1.0, total / self.target))

    # -- serialisation -------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "target": self.target,
            "currency": self.currency,
            "goal_tiers": [tier.to_dict() for tier in self.goal_tiers],
            "reward_bands": [band.to_dict() for band in self.reward_bands],
            "escalation": self.escalation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> TierPlan:
        data = data or {}
        return cls(
            enabled=bool(data.get("enabled", False)),
            target=float(data.get("target", 0.0)),
            currency=str(data.get("currency", "Cr")),
            goal_tiers=[
                GoalTier.from_dict(item)
                for item in (data.get("goal_tiers") or [])
                if isinstance(item, dict)
            ],
            reward_bands=[
                RewardBand.from_dict(item)
                for item in (data.get("reward_bands") or [])
                if isinstance(item, dict)
            ],
            escalation=[float(value) for value in (data.get("escalation") or [])],
        )


def even_tiers(target: float, count: int) -> list[GoalTier]:
    """Return ``count`` evenly spaced tiers ending on ``target``.

    Any remainder from an uneven division is added to the first tier, so
    later thresholds stay round and the last lands exactly on the target.
    """
    count = max(1, min(count, MAX_GOAL_TIERS))
    if target <= 0:
        return []

    step = math.floor(target / count)
    remainder = target - step * count
    tiers: list[GoalTier] = []
    running = 0.0
    for index in range(1, count + 1):
        running += step
        if index == 1:
            running += remainder
        if index == count:
            running = target
        tiers.append(GoalTier(label=f"Tier {index}", threshold=float(running)))
    return tiers


def tiers_from_step(anchor: float, count: int, from_top: bool) -> list[GoalTier]:
    """Return tiers stepped by 20% from whichever end is known.

    ``from_top`` treats ``anchor`` as the final target and works down;
    otherwise ``anchor`` is the first tier and the rest work up. This is
    the "calculate the rest for me" button: the organizer fills in the
    end they actually know.
    """
    count = max(1, min(count, MAX_GOAL_TIERS))
    if anchor <= 0:
        return []

    thresholds: list[float] = []
    if from_top:
        for index in range(count):
            thresholds.append(anchor * (1.0 - DEFAULT_TIER_STEP * index))
        thresholds.reverse()
    else:
        for index in range(count):
            thresholds.append(anchor * (1.0 + DEFAULT_TIER_STEP * index))

    return [
        GoalTier(label=f"Tier {index}", threshold=float(round(value)))
        for index, value in enumerate(thresholds, start=1)
    ]


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
    """What one reward band worked out to for the commanders in it."""

    band: RewardBand
    commanders: list[str]
    payout: float
    lowest_points: float = 0.0
    highest_points: float = 0.0

    @property
    def count(self) -> int:
        return len(self.commanders)

    def range_text(self) -> str:
        """Return the points range this band covers, Inara-style."""
        if not self.commanders:
            return "—"
        if self.lowest_points == self.highest_points:
            return f"{self.lowest_points:,.0f}"
        return f"{self.lowest_points:,.0f} to {self.highest_points:,.0f}"


@dataclass
class ProgressReport:
    """The state of a tiered event: progress, and who is owed what."""

    plan: TierPlan
    total: float
    participants: int
    tiers_reached: int
    awards: list[BandAward] = field(default_factory=list)

    @property
    def next_tier(self) -> GoalTier | None:
        """Return the next tier not yet reached, if any."""
        if self.tiers_reached >= len(self.plan.goal_tiers):
            return None
        return self.plan.goal_tiers[self.tiers_reached]

    @property
    def to_next_tier(self) -> float:
        """Return the points still needed for the next tier."""
        upcoming = self.next_tier
        return max(0.0, upcoming.threshold - self.total) if upcoming else 0.0

    @property
    def fraction(self) -> float:
        return self.plan.progress_fraction(self.total)

    @property
    def multiplier(self) -> float:
        return self.plan.multiplier_for(self.tiers_reached)

    @property
    def tier_text(self) -> str:
        """Return ``Tier 3/5``, as Frontier renders it."""
        return f"Tier {self.tiers_reached}/{len(self.plan.goal_tiers)}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "participants": self.participants,
            "tiers_reached": self.tiers_reached,
            "tier_count": len(self.plan.goal_tiers),
            "target": self.plan.target,
            "currency": self.plan.currency,
            "fraction": round(self.fraction, 6),
            "multiplier": self.multiplier,
            "to_next_tier": self.to_next_tier,
            "next_tier": self.next_tier.to_dict() if self.next_tier else None,
            "goal_tiers": [tier.to_dict() for tier in self.plan.goal_tiers],
            "awards": [
                {
                    "band": award.band.label,
                    "selects": award.band.describe(),
                    "commanders": award.commanders,
                    "commander_count": award.count,
                    "payout_each": award.payout,
                    "points_low": award.lowest_points,
                    "points_high": award.highest_points,
                }
                for award in self.awards
            ],
        }


def build_progress(plan: TierPlan, standings: list[Any]) -> ProgressReport:
    """Work out tier progress and per-band awards from ranked standings.

    ``standings`` comes from a :class:`StandingsReport`, already in rank
    order. Bands are filled by position: a fixed-count band takes the
    next N commanders, and a percentile band takes everyone down to that
    share of the field. Each commander lands in exactly one band, the
    best they qualify for — which is how Frontier's own tables read,
    with "Top 10 CMDRs" sitting above the "Top 25%" range rather than
    inside it.
    """
    total = float(sum(item.total_points for item in standings))
    participants = len(standings)
    tiers_reached = plan.tier_reached(total)
    multiplier = plan.multiplier_for(tiers_reached)

    awards: list[BandAward] = []
    assigned = 0
    for band in plan.reward_bands:
        if assigned >= participants:
            # Reported even when empty, so the board still shows what the
            # band would have paid had anyone reached it.
            awards.append(BandAward(band=band, commanders=[], payout=0.0))
            continue

        if band.is_fixed_count:
            end = min(assigned + int(band.top_count or 0), participants)
        else:
            share = (band.percentile or 100.0) / 100.0
            end = min(max(assigned + 1, math.ceil(participants * share)), participants)

        members = standings[assigned:end]
        if not members:
            awards.append(BandAward(band=band, commanders=[], payout=0.0))
            continue

        points = [item.total_points for item in members]
        awards.append(
            BandAward(
                band=band,
                commanders=[item.commander_name for item in members],
                payout=round(band.payout * multiplier, 2),
                lowest_points=min(points),
                highest_points=max(points),
            )
        )
        assigned = end

    return ProgressReport(
        plan=plan,
        total=total,
        participants=participants,
        tiers_reached=tiers_reached,
        awards=awards,
    )


__all__ = [
    "DEFAULT_TIER_STEP",
    "MAX_GOAL_TIERS",
    "MAX_REWARD_BANDS",
    "BandAward",
    "GoalTier",
    "ProgressReport",
    "RewardBand",
    "TierPlan",
    "build_progress",
    "default_reward_bands",
    "even_tiers",
    "tiers_from_step",
]
