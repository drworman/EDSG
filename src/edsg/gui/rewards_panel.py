"""The Rewards panel: goal tiers and how the pool is shared out.

Every event is a community goal in Frontier's shape. Two things stack:

*Goal tiers* measure the **collective** total, and are derived from the
criteria rather than typed — the top tier in use is worth exactly what
every criterion's unit cap adds up to, and the rest step down in equal
shares of it. Nothing here can drift out of step with the criteria it
measures, because nothing here is entered by hand.

*Reward tiers* rank **individuals**. The organizer names a maximum pool;
EDSG unlocks a share of it per goal tier reached and shares that out so
a place in a higher tier is always worth more than a place in a lower
one.

Tiers are listed from the top down, the way a goal is read.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from edsg.core.tiers import MAX_GOAL_TIERS, TierPlan
from edsg.gui.widgets import label

#: Column widths shared by the headings and the rows beneath them, so a
#: heading always sits over the control it names.
TIER_COLUMNS = (56, 150, 1)
#: Enough height for a combo box and a spin box without clipping.
ROW_HEIGHT = 34


def _heading_row(labels: tuple[str, ...], widths: tuple[int, ...]) -> QWidget:
    """Return a heading strip whose columns match the rows below it."""
    holder = QWidget()
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 2)
    layout.setSpacing(8)
    for text, width in zip(labels, widths, strict=True):
        item = label(text, "hint")
        if width > 1:
            item.setFixedWidth(width)
            layout.addWidget(item)
        else:
            layout.addWidget(item, 1)
    return holder


class GoalTierRow(QWidget):
    """One goal tier. The threshold is shown, never typed."""

    def __init__(self, index: int) -> None:
        super().__init__()
        self.index = index
        # Without a floor the layout squeezes rows until their text is
        # clipped, which is what made the earlier panel unreadable.
        self.setMinimumHeight(ROW_HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self.enabled = QCheckBox()
        self.enabled.setFixedWidth(TIER_COLUMNS[0])
        self.enabled.setToolTip(
            "Untick to run the goal with fewer tiers. The rest rebalance."
        )

        self.name = label(f"Tier {index}")
        self.name.setFixedWidth(TIER_COLUMNS[1])

        self.threshold = QLabel("\u2014")
        self.threshold.setProperty("role", "fingerprint")
        self.threshold.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.threshold.setToolTip(
            "Worked out from the unit caps of your criteria. The top tier "
            "in use is worth every cap added together."
        )

        layout.addWidget(self.enabled)
        layout.addWidget(self.name)
        layout.addWidget(self.threshold, 1)

    def show_threshold(self, value: float | None) -> None:
        self.threshold.setText("\u2014" if value is None else f"{value:,.0f}")


class RewardsPanel(QWidget):
    """The Rewards tab, sitting between Criteria and Issue invitation."""

    def __init__(self) -> None:
        super().__init__()
        self.ceiling = 0.0

        # The whole panel scrolls: goal tiers, the pool and five reward
        # rows are taller than a small laptop screen, and Qt would
        # otherwise compress the rows until their text is clipped.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        outer.addWidget(area)

        body = QWidget()
        area.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setSpacing(12)

        layout.addWidget(
            label(
                "This event runs as a community goal, in the same shape as "
                "Frontier's. Everyone's points add into one total that "
                "climbs through goal tiers; commanders are then ranked into "
                "reward tiers and paid from the pool you set below.",
                "hint",
                wrap=True,
            )
        )

        self.enabled = QCheckBox("Award rewards for this event")
        self.enabled.setToolTip(
            "Leave unticked to run a plain leaderboard with no payouts"
        )
        self.enabled.toggled.connect(self._on_enabled)
        layout.addWidget(self.enabled)

        # -- goal tiers -------------------------------------------------
        self.tier_group = QGroupBox("Goal tiers")
        tier_layout = QVBoxLayout(self.tier_group)
        tier_layout.addWidget(
            label(
                "Thresholds are worked out from your criteria: the top tier "
                "in use is worth every unit cap added together, and the rest "
                "step down in equal shares. Untick the tiers you do not "
                "want \u2014 for a four-tier event, untick Tier 5 \u2014 and "
                "the remainder rebalance themselves.",
                "hint",
                wrap=True,
            )
        )
        tier_layout.addWidget(_heading_row(("Use", "Tier", "Reached at"), TIER_COLUMNS))

        # Listed from the top down, the way a goal is read.
        self.tier_rows: list[GoalTierRow] = []
        for index in range(MAX_GOAL_TIERS, 0, -1):
            row = GoalTierRow(index)
            row.enabled.toggled.connect(self._on_tier_toggled)
            self.tier_rows.append(row)
            tier_layout.addWidget(row)

        self.ceiling_label = label("", "hint", wrap=True)
        tier_layout.addWidget(self.ceiling_label)
        layout.addWidget(self.tier_group)

        # -- the pool ---------------------------------------------------
        self.pool_group = QGroupBox("Reward pool")
        pool_form = QFormLayout(self.pool_group)
        self.pool = QDoubleSpinBox()
        self.pool.setDecimals(0)
        self.pool.setRange(0, 1_000_000_000_000)
        self.pool.setGroupSeparatorShown(True)
        self.pool.setSingleStep(1_000_000)
        self.pool.setToolTip(
            "The most you are willing to pay out in total, across everyone"
        )
        self.pool.valueChanged.connect(self._refresh_preview)
        pool_form.addRow("Maximum Reward Pool in Credits", self.pool)

        self.currency = QLineEdit("Cr")
        self.currency.setFixedWidth(90)
        pool_form.addRow("Paid in", self.currency)

        self.pool_preview = label("", "hint", wrap=True)
        pool_form.addRow("", self.pool_preview)
        layout.addWidget(self.pool_group)

        # -- how the pool is shared -----------------------------------
        self.band_group = QGroupBox("How the pool is shared")
        share_form = QFormLayout(self.band_group)

        self.top_count = QSpinBox()
        self.top_count.setRange(0, 10_000)
        self.top_count.setFixedWidth(140)
        self.top_count.setToolTip(
            "How many leading commanders share the bonus. Set to 0 for a "
            "purely proportional split with no leaderboard bonus."
        )
        self.top_count.valueChanged.connect(self._refresh_preview)
        share_form.addRow("Bonus goes to the top", self.top_count)

        self.top_share = QSpinBox()
        self.top_share.setRange(0, 100)
        self.top_share.setSuffix(" %")
        self.top_share.setFixedWidth(140)
        self.top_share.setToolTip(
            "How much of the pool is taken off the top for that bonus"
        )
        self.top_share.valueChanged.connect(self._refresh_preview)
        share_form.addRow("Bonus share of the pool", self.top_share)

        self.share_preview = label("", "hint", wrap=True)
        share_form.addRow("", self.share_preview)

        share_form.addRow(
            "",
            label(
                "Both halves are shared out <b>in proportion to what each "
                "commander contributed</b>, so nobody can out-earn someone "
                "who did more. Commanders on equal points hold the same "
                "rank and are paid alike, which dilutes the bonus for "
                "everyone in a tie rather than breaking it arbitrarily.<br/>"
                "<br/>How much each commander receives depends on the "
                "turnout and the goal tier reached, and is worked out when "
                "the event closes.",
                "hint",
                wrap=True,
            ),
        )
        layout.addWidget(self.band_group)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        layout.addWidget(divider)
        layout.addStretch(1)

    # -- state ---------------------------------------------------------

    def _on_enabled(self, active: bool) -> None:
        for group in (self.tier_group, self.pool_group, self.band_group):
            group.setEnabled(active)

    def _on_tier_toggled(self) -> None:
        # At least one tier must remain, or there is no goal at all.
        if not any(row.enabled.isChecked() for row in self.tier_rows):
            self.tier_rows[-1].enabled.setChecked(True)
        self._refresh_preview()

    def tier_count(self) -> int:
        """Return how many tiers are ticked."""
        return sum(1 for row in self.tier_rows if row.enabled.isChecked())

    def set_ceiling(self, ceiling: float) -> None:
        """Tell the panel what the criteria are worth in total."""
        self.ceiling = ceiling
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        """Recompute every derived figure on show."""
        count = max(1, self.tier_count())

        if self.ceiling <= 0:
            self.ceiling_label.setText(
                "No unit caps are set yet, so there is nothing to measure. "
                "Give each criterion a unit cap on the Criteria tab."
            )
        else:
            step = 100.0 / count
            self.ceiling_label.setText(
                f"Criteria are worth {self.ceiling:,.0f} points in total, "
                f"which is Tier {count}. With {count} tier(s) in use each "
                f"step is {step:.0f}% of that."
            )

        # Tiers are numbered from the bottom up but shown top down, so
        # the ticked rows take the numbers 1..count in display order.
        rank = count
        for row in self.tier_rows:
            if row.enabled.isChecked():
                row.name.setText(f"Tier {rank}")
                row.show_threshold(
                    self.ceiling * rank / count if self.ceiling > 0 else None
                )
                rank -= 1
            else:
                row.name.setText("\u2014")
                row.show_threshold(None)

        pool = self.pool.value()
        top = self.top_count.value()
        bonus_pct = self.top_share.value()
        if pool > 0 and top > 0 and bonus_pct > 0:
            bonus = pool * bonus_pct / 100.0
            self.share_preview.setText(
                f"Of a full {pool:,.0f} pool, {bonus:,.0f} is shared among "
                f"the top {top} by contribution, and the remaining "
                f"{pool - bonus:,.0f} among everyone by contribution."
            )
        elif pool > 0:
            self.share_preview.setText(
                f"The whole {pool:,.0f} is shared among everyone in "
                f"proportion to what they contributed."
            )
        else:
            self.share_preview.setText("")

        if pool > 0 and count:
            per_tier = pool / count
            self.pool_preview.setText(
                f"Reaching Tier 1 unlocks {per_tier:,.0f}; every tier after "
                f"that adds the same again, up to {pool:,.0f} when all "
                f"{count} are reached. Nothing is paid below Tier 1."
            )
        else:
            self.pool_preview.setText(
                "Set a pool to award rewards. Nothing is paid if the goal "
                "does not reach Tier 1."
            )

    # -- load and save -------------------------------------------------

    def load(self, plan: TierPlan, ceiling: float) -> None:
        """Fill the panel from an event's plan."""
        self.ceiling = ceiling
        self.enabled.setChecked(plan.enabled)
        self.pool.setValue(plan.reward_pool)
        self.currency.setText(plan.currency or "Cr")

        count = max(1, min(plan.tier_count, MAX_GOAL_TIERS))
        for row in self.tier_rows:
            row.enabled.setChecked(row.index <= count)

        self.top_count.setValue(plan.top_count)
        self.top_share.setValue(round(plan.top_share * 100))

        self._on_enabled(plan.enabled)
        self._refresh_preview()

    def collect(self) -> TierPlan:
        """Return the plan as currently entered."""
        return TierPlan(
            enabled=self.enabled.isChecked(),
            tier_count=max(1, self.tier_count()),
            reward_pool=float(self.pool.value()),
            currency=self.currency.text().strip() or "Cr",
            top_count=int(self.top_count.value()),
            top_share=self.top_share.value() / 100.0,
        )


__all__ = ["GoalTierRow", "RewardsPanel"]
