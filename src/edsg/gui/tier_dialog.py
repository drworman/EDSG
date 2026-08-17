"""Configuring an event's goal tiers and reward bands.

Kept in its own dialog rather than on the criteria tab, because it is
optional: plenty of events are a straight leaderboard with no target and
no payouts.

The layout follows Frontier's own community goals — a collective target
broken into tiers, and reward bands ranking individuals — because that
is the format squadrons already know how to read.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from edsg.core.tiers import (
    MAX_GOAL_TIERS,
    MAX_REWARD_BANDS,
    GoalTier,
    RewardBand,
    TierPlan,
    default_reward_bands,
    even_tiers,
    tiers_from_step,
)
from edsg.gui.widgets import button, label, show_error

#: How a reward band picks its members.
BAND_MODES = (("percent", "Top % of field"), ("count", "Top N commanders"))


class GoalTierRow(QWidget):
    """One goal tier: a name and the points that reach it."""

    def __init__(self, index: int) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.enabled = QCheckBox()
        self.enabled.setToolTip("Include this tier")
        self.label_field = QLineEdit(f"Tier {index}")
        self.label_field.setMaximumWidth(150)
        self.threshold = QDoubleSpinBox()
        self.threshold.setDecimals(0)
        self.threshold.setRange(0, 1_000_000_000_000)
        self.threshold.setGroupSeparatorShown(True)
        self.threshold.setSingleStep(1000)

        layout.addWidget(self.enabled)
        layout.addWidget(self.label_field)
        layout.addWidget(self.threshold, 1)

    def is_active(self) -> bool:
        return self.enabled.isChecked() and self.threshold.value() > 0

    def to_tier(self) -> GoalTier:
        return GoalTier(
            label=self.label_field.text().strip() or "Tier",
            threshold=float(self.threshold.value()),
        )

    def load(self, tier: GoalTier | None) -> None:
        self.enabled.setChecked(tier is not None)
        if tier is not None:
            self.label_field.setText(tier.label)
            self.threshold.setValue(tier.threshold)


class RewardBandRow(QWidget):
    """One reward band: who it covers and what it pays."""

    def __init__(self) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.enabled = QCheckBox()
        self.enabled.setToolTip("Include this band")
        self.label_field = QLineEdit()
        self.label_field.setMaximumWidth(140)

        self.mode = QComboBox()
        for key, text in BAND_MODES:
            self.mode.addItem(text, key)
        self.mode.setMinimumWidth(160)
        self.mode.currentIndexChanged.connect(self._on_mode_changed)

        self.percent = QDoubleSpinBox()
        self.percent.setRange(0.1, 100.0)
        self.percent.setDecimals(1)
        self.percent.setSuffix(" %")
        self.percent.setMaximumWidth(90)

        self.count = QSpinBox()
        self.count.setRange(1, 10_000)
        self.count.setPrefix("top ")
        self.count.setMaximumWidth(90)

        self.payout = QDoubleSpinBox()
        self.payout.setDecimals(0)
        self.payout.setRange(0, 1_000_000_000_000)
        self.payout.setGroupSeparatorShown(True)
        self.payout.setSingleStep(1_000_000)

        for widget in (
            self.enabled,
            self.label_field,
            self.mode,
            self.percent,
            self.count,
        ):
            layout.addWidget(widget)
        layout.addWidget(self.payout, 1)
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
            label=self.label_field.text().strip() or "Band",
            payout=float(self.payout.value()),
            top_count=int(self.count.value()) if by_count else None,
            percentile=None if by_count else float(self.percent.value()),
        )

    def load(self, band: RewardBand | None) -> None:
        self.enabled.setChecked(band is not None)
        if band is None:
            return
        self.label_field.setText(band.label)
        self.payout.setValue(band.payout)
        if band.is_fixed_count:
            self.mode.setCurrentIndex(self.mode.findData("count"))
            self.count.setValue(int(band.top_count or 1))
        else:
            self.mode.setCurrentIndex(self.mode.findData("percent"))
            self.percent.setValue(float(band.percentile or 100.0))
        self._on_mode_changed()


class TierDialog(QDialog):
    """Edit an event's goal tiers, reward bands and escalation."""

    def __init__(self, parent: QWidget | None, plan: TierPlan) -> None:
        super().__init__(parent)
        self.setWindowTitle("Goal tiers and rewards")
        self.setMinimumSize(880, 700)
        self.result_plan: TierPlan | None = None

        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setSpacing(12)
        outer.addWidget(scroll, 1)

        layout.addWidget(
            label(
                "Optional. A tiered event works like one of Frontier's "
                "community goals: everyone's points add into a single total "
                "that climbs through goal tiers, and commanders are then "
                "ranked into reward bands. Leave this off for a plain "
                "leaderboard.",
                "hint",
                wrap=True,
            )
        )

        self.enabled = QCheckBox("Track goal tiers and rewards for this event")
        self.enabled.toggled.connect(self._on_enabled)
        layout.addWidget(self.enabled)

        # -- the goal --------------------------------------------------
        self.goal_group = QGroupBox("The goal")
        goal_form = QFormLayout(self.goal_group)
        self.target = QDoubleSpinBox()
        self.target.setDecimals(0)
        self.target.setRange(0, 1_000_000_000_000)
        self.target.setGroupSeparatorShown(True)
        self.target.setSingleStep(1000)
        self.target.setToolTip(
            "Total points from everyone combined that completes the goal"
        )
        goal_form.addRow("Target points", self.target)

        self.currency = QLineEdit("Cr")
        self.currency.setMaximumWidth(90)
        self.currency.setToolTip("What rewards are paid in")
        goal_form.addRow("Reward unit", self.currency)
        layout.addWidget(self.goal_group)

        # -- goal tiers -------------------------------------------------
        self.tier_group = QGroupBox(f"Goal tiers (up to {MAX_GOAL_TIERS})")
        tier_layout = QVBoxLayout(self.tier_group)

        headings = QGridLayout()
        headings.addWidget(label("Use", "hint"), 0, 0)
        headings.addWidget(label("Name", "hint"), 0, 1)
        headings.addWidget(label("Reached at (points)", "hint"), 0, 2)
        tier_layout.addLayout(headings)

        self.tier_rows: list[GoalTierRow] = []
        for index in range(1, MAX_GOAL_TIERS + 1):
            row = GoalTierRow(index)
            self.tier_rows.append(row)
            tier_layout.addWidget(row)

        auto = QHBoxLayout()
        auto.addWidget(label("Calculate", "hint"))
        self.tier_count = QSpinBox()
        self.tier_count.setRange(1, MAX_GOAL_TIERS)
        self.tier_count.setValue(5)
        self.tier_count.setPrefix("tiers: ")
        auto.addWidget(self.tier_count)

        even_button = button("Even split of target")
        even_button.setToolTip(
            "Divide the target into equal steps; any remainder goes into the first tier"
        )
        even_button.clicked.connect(self._fill_even)
        auto.addWidget(even_button)

        down_button = button("20% steps down from target")
        down_button.setToolTip("Work downward from the target in 20% steps")
        down_button.clicked.connect(lambda: self._fill_stepped(True))
        auto.addWidget(down_button)

        up_button = button("20% steps up from Tier 1")
        up_button.setToolTip("Work upward from whatever Tier 1 is set to, in 20% steps")
        up_button.clicked.connect(lambda: self._fill_stepped(False))
        auto.addWidget(up_button)
        auto.addStretch(1)
        tier_layout.addLayout(auto)
        layout.addWidget(self.tier_group)

        # -- reward bands ----------------------------------------------
        self.band_group = QGroupBox(f"Reward tiers (up to {MAX_REWARD_BANDS})")
        band_layout = QVBoxLayout(self.band_group)
        band_headings = QGridLayout()
        for column, text in enumerate(
            ("Use", "Name", "Selects", "Size", "Reward each")
        ):
            band_headings.addWidget(label(text, "hint"), 0, column)
        band_layout.addLayout(band_headings)

        self.band_rows: list[RewardBandRow] = []
        for _ in range(MAX_REWARD_BANDS):
            row = RewardBandRow()
            self.band_rows.append(row)
            band_layout.addWidget(row)

        band_layout.addWidget(
            label(
                "Bands are filled from the top down, and each commander is "
                "paid by the best band they reach \u2014 so a 'Top 10 CMDRs' "
                "band sits above 'Top 25%' rather than inside it.",
                "hint",
                wrap=True,
            )
        )
        reset = button("Reset to Frontier's layout")
        reset.clicked.connect(self._fill_default_bands)
        band_layout.addWidget(reset, 0, Qt.AlignLeft)
        layout.addWidget(self.band_group)

        # -- escalation -------------------------------------------------
        self.escalation_group = QGroupBox("Escalation")
        escalation_layout = QVBoxLayout(self.escalation_group)
        escalation_layout.addWidget(
            label(
                "Every band's reward is multiplied by this when the goal "
                "reaches each tier. Leave them at 1 for flat rewards.",
                "hint",
                wrap=True,
            )
        )
        grid = QGridLayout()
        self.escalation_spins: list[QDoubleSpinBox] = []
        for index in range(MAX_GOAL_TIERS):
            spin = QDoubleSpinBox()
            spin.setDecimals(2)
            spin.setRange(0.01, 1000.0)
            spin.setValue(1.0)
            spin.setPrefix("\u00d7 ")
            self.escalation_spins.append(spin)
            grid.addWidget(label(f"At tier {index + 1}", "hint"), 0, index)
            grid.addWidget(spin, 1, index)
        escalation_layout.addLayout(grid)
        layout.addWidget(self.escalation_group)
        layout.addStretch(1)

        buttons = QDialogButtonBox()
        save = buttons.addButton("Save", QDialogButtonBox.AcceptRole)
        save.setProperty("role", "primary")
        buttons.addButton(QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._load(plan)

    # -- helpers -----------------------------------------------------

    def _on_enabled(self, active: bool) -> None:
        for group in (
            self.goal_group,
            self.tier_group,
            self.band_group,
            self.escalation_group,
        ):
            group.setEnabled(active)

    def _apply_tiers(self, tiers: list[GoalTier]) -> None:
        for index, row in enumerate(self.tier_rows):
            row.load(tiers[index] if index < len(tiers) else None)

    def _fill_even(self) -> None:
        self._apply_tiers(even_tiers(self.target.value(), self.tier_count.value()))

    def _fill_stepped(self, from_top: bool) -> None:
        if from_top:
            anchor = self.target.value()
        else:
            anchor = self.tier_rows[0].threshold.value()
            if anchor <= 0:
                show_error(
                    self,
                    "Set Tier 1 first",
                    "Stepping up needs a value in the first tier to start from.",
                )
                return
        tiers = tiers_from_step(anchor, self.tier_count.value(), from_top)
        self._apply_tiers(tiers)
        if tiers and from_top is False:
            # Working upward can overshoot; keep the target consistent.
            self.target.setValue(max(self.target.value(), tiers[-1].threshold))

    def _fill_default_bands(self) -> None:
        defaults = default_reward_bands()
        for index, row in enumerate(self.band_rows):
            row.load(defaults[index] if index < len(defaults) else None)

    # -- load and save -----------------------------------------------

    def _load(self, plan: TierPlan) -> None:
        self.enabled.setChecked(plan.enabled)
        self.target.setValue(plan.target)
        self.currency.setText(plan.currency or "Cr")
        self._apply_tiers(plan.goal_tiers)

        bands = plan.reward_bands or default_reward_bands()
        for index, row in enumerate(self.band_rows):
            row.load(bands[index] if index < len(bands) else None)

        for index, spin in enumerate(self.escalation_spins):
            if index < len(plan.escalation):
                spin.setValue(plan.escalation[index])
        self._on_enabled(plan.enabled)

    def collect(self) -> TierPlan:
        """Return the plan as currently entered."""
        tiers = [row.to_tier() for row in self.tier_rows if row.is_active()]
        bands = [row.to_band() for row in self.band_rows if row.is_active()]
        return TierPlan(
            enabled=self.enabled.isChecked(),
            target=float(self.target.value()),
            currency=self.currency.text().strip() or "Cr",
            goal_tiers=tiers,
            reward_bands=bands,
            escalation=[
                spin.value() for spin in self.escalation_spins[: max(len(tiers), 1)]
            ],
        )

    def _save(self) -> None:
        plan = self.collect()
        problems = plan.validate()
        if problems:
            show_error(
                self,
                "This goal is not valid",
                problems[0],
                "\n".join(problems[1:]),
            )
            return
        self.result_plan = plan
        self.accept()


def edit_tiers(parent: QWidget | None, plan: TierPlan) -> TierPlan | None:
    """Open the dialog and return the saved plan, or ``None``."""
    dialog = TierDialog(parent, plan)
    if dialog.exec() == QDialog.Accepted:
        return dialog.result_plan
    return None


__all__ = ["BAND_MODES", "GoalTierRow", "RewardBandRow", "TierDialog", "edit_tiers"]
