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
    QComboBox,
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

from edsg.core.tiers import (
    MAX_GOAL_TIERS,
    MAX_REWARD_BANDS,
    RewardBand,
    TierPlan,
    band_weights,
    default_reward_bands,
)
from edsg.gui.widgets import button, label

#: How a reward tier picks its members.
BAND_MODES = (("percent", "Top % of field"), ("count", "Top N commanders"))

#: Column widths shared by the headings and the rows beneath them, so a
#: heading always sits over the control it names.
TIER_COLUMNS = (56, 150, 1)
BAND_COLUMNS = (56, 190, 170, 130, 1)

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


class RewardBandRow(QWidget):
    """One reward tier: who it covers, and its share of the pool."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(ROW_HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self.enabled = QCheckBox()
        self.enabled.setFixedWidth(BAND_COLUMNS[0])

        self.label_field = QLineEdit()
        self.label_field.setFixedWidth(BAND_COLUMNS[1])

        self.mode = QComboBox()
        for key, text in BAND_MODES:
            self.mode.addItem(text, key)
        self.mode.setFixedWidth(BAND_COLUMNS[2])
        self.mode.currentIndexChanged.connect(self._on_mode_changed)

        self.size_holder = QWidget()
        self.size_holder.setFixedWidth(BAND_COLUMNS[3])
        size_layout = QHBoxLayout(self.size_holder)
        size_layout.setContentsMargins(0, 0, 0, 0)
        size_layout.setSpacing(0)

        self.percent = QDoubleSpinBox()
        self.percent.setRange(0.1, 100.0)
        self.percent.setDecimals(1)
        self.percent.setSuffix(" %")
        self.count = QSpinBox()
        self.count.setRange(1, 10_000)
        self.count.setPrefix("top ")
        size_layout.addWidget(self.percent)
        size_layout.addWidget(self.count)

        self.share = QLabel("\u2014")
        self.share.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.share.setProperty("role", "hint")
        self.share.setToolTip(
            "Relative worth of one place in this tier. The pool is shared "
            "out so a place here always beats a place below."
        )

        for widget in (self.enabled, self.label_field, self.mode, self.size_holder):
            layout.addWidget(widget)
        layout.addWidget(self.share, 1)
        self._on_mode_changed()

    def _on_mode_changed(self) -> None:
        by_count = self.mode.currentData() == "count"
        self.count.setVisible(by_count)
        self.percent.setVisible(not by_count)

    def is_active(self) -> bool:
        return self.enabled.isChecked()

    def to_band(self) -> RewardBand:
        by_count = self.mode.currentData() == "count"
        return RewardBand(
            label=self.label_field.text().strip() or "Tier",
            top_count=int(self.count.value()) if by_count else None,
            percentile=None if by_count else float(self.percent.value()),
        )

    def load(self, band: RewardBand | None) -> None:
        self.enabled.setChecked(band is not None)
        if band is None:
            return
        self.label_field.setText(band.label)
        if band.is_fixed_count:
            self.mode.setCurrentIndex(self.mode.findData("count"))
            self.count.setValue(int(band.top_count or 1))
        else:
            self.mode.setCurrentIndex(self.mode.findData("percent"))
            self.percent.setValue(float(band.percentile or 100.0))
        self._on_mode_changed()


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

        # -- reward tiers -----------------------------------------------
        self.band_group = QGroupBox(f"Reward tiers (up to {MAX_REWARD_BANDS})")
        band_layout = QVBoxLayout(self.band_group)
        band_layout.addWidget(
            _heading_row(
                ("Use", "Name", "Selects", "Size", "Worth per place"),
                BAND_COLUMNS,
            )
        )

        self.band_rows: list[RewardBandRow] = []
        for _ in range(MAX_REWARD_BANDS):
            row = RewardBandRow()
            row.enabled.toggled.connect(self._refresh_preview)
            self.band_rows.append(row)
            band_layout.addWidget(row)

        band_layout.addWidget(
            label(
                "Tiers fill from the top down and each commander is paid "
                "from the best one they reach, so a 'Top 10 CMDRs' tier sits "
                "above 'Top 25%' rather than inside it. How much each "
                "commander actually receives depends on the turnout and the "
                "goal tier reached, and is worked out when the event closes.",
                "hint",
                wrap=True,
            )
        )
        reset = button("Reset to Frontier's layout")
        reset.clicked.connect(self._fill_default_bands)
        band_layout.addWidget(reset, 0, Qt.AlignLeft)
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

        active = [row for row in self.band_rows if row.is_active()]
        weights = band_weights(len(active))
        for row in self.band_rows:
            row.share.setText("\u2014")
        for row, weight in zip(active, weights, strict=True):
            row.share.setText(f"\u00d7 {weight:g}")

        pool = self.pool.value()
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

    def _fill_default_bands(self) -> None:
        defaults = default_reward_bands()
        for index, row in enumerate(self.band_rows):
            row.load(defaults[index] if index < len(defaults) else None)
        self._refresh_preview()

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

        bands = plan.reward_bands or default_reward_bands()
        for index, row in enumerate(self.band_rows):
            row.load(bands[index] if index < len(bands) else None)

        self._on_enabled(plan.enabled)
        self._refresh_preview()

    def collect(self) -> TierPlan:
        """Return the plan as currently entered."""
        return TierPlan(
            enabled=self.enabled.isChecked(),
            tier_count=max(1, self.tier_count()),
            reward_pool=float(self.pool.value()),
            currency=self.currency.text().strip() or "Cr",
            reward_bands=[row.to_band() for row in self.band_rows if row.is_active()],
        )


__all__ = ["BAND_MODES", "GoalTierRow", "RewardBandRow", "RewardsPanel"]
