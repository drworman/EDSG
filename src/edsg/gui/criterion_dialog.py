"""Dialog for creating and editing a single scoring criterion.

The filter fields shown adapt to the chosen metric. A mining criterion
has no use for a mission-outcome row, and showing one invites the
organizer to set it and wonder why nothing changed. Irrelevant fields
are hidden rather than disabled, which keeps the dialog compact.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from edsg.core.criteria import (
    ALLOWED_MEASURES,
    FILTER_GROUPS,
    Criterion,
    Filters,
    Measure,
    MetricKind,
    MissionOutcome,
)
from edsg.core.namecheck import check_names, summarise
from edsg.gui.widgets import (
    CheckRow,
    TagField,
    button,
    label,
    run_in_background,
    show_error,
)

COMMON_EVENTS = "e.g. Bounty, Died, Docked, FSDJump, MarketSell, MissionCompleted"
STATION_TYPES = "e.g. Coriolis, Orbis, Ocellus, Outpost, AsteroidBase, FleetCarrier"

MEASURE_HELP = {
    Measure.COUNT: "One unit per matching event.",
    Measure.TONNAGE: "Units are tonnes of cargo.",
    Measure.CREDITS: "Units are credits. Use a small points-per-unit value.",
    Measure.DISTINCT: "Each distinct thing counts once, however often it recurs.",
}


class CriterionDialog(QDialog):
    """Modal editor producing a :class:`Criterion`."""

    def __init__(self, parent: QWidget | None, criterion: Criterion | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edit criterion" if criterion else "Add criterion")
        self.setMinimumSize(660, 620)
        self.result_criterion: Criterion | None = None
        self._existing = criterion

        self._build()
        if criterion is not None:
            self._load(criterion)
        else:
            self.kind_box.setCurrentIndex(
                self.kind_box.findData(MetricKind.MINING_REFINED)
            )
            self._on_kind_changed()

    # -- construction ---------------------------------------------------

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setSpacing(12)
        outer.addWidget(scroll, 1)

        # -- what to measure ------------------------------------------
        measure_group = QGroupBox("What to measure")
        form = QFormLayout(measure_group)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)

        self.label_field = QLineEdit()
        self.label_field.setPlaceholderText(
            "Shown as a column heading in the standings"
        )
        form.addRow("Label", self.label_field)

        self.kind_box = QComboBox()
        for kind in MetricKind:
            self.kind_box.addItem(kind.label, kind)
        self.kind_box.currentIndexChanged.connect(self._on_kind_changed)
        form.addRow("Metric", self.kind_box)

        self.kind_help = label("", "hint", wrap=True)
        form.addRow("", self.kind_help)

        self.measure_box = QComboBox()
        self.measure_box.currentIndexChanged.connect(self._on_measure_changed)
        form.addRow("Measured in", self.measure_box)

        self.measure_help = label("", "hint", wrap=True)
        form.addRow("", self.measure_help)
        layout.addWidget(measure_group)

        # -- filters ---------------------------------------------------
        self.filters_group = QGroupBox("Which events count")
        filter_form = QFormLayout(self.filters_group)
        filter_form.setSpacing(8)
        self.filter_form = filter_form

        self.fields: dict[str, QWidget] = {}
        self.rows: dict[str, tuple[QWidget, QWidget]] = {}

        def add_tag(key: str, caption: str, placeholder: str = "") -> TagField:
            field = TagField(placeholder)
            caption_widget = label(caption)
            filter_form.addRow(caption_widget, field)
            self.fields[key] = field
            self.rows[key] = (caption_widget, field)
            return field

        self.events_field = add_tag("events", "Journal events", COMMON_EVENTS)
        self.commodities_field = add_tag(
            "commodities", "Commodities", "in-game or internal names both work"
        )
        self.genera_field = add_tag("genera", "Genera", "e.g. Bacterium")
        self.species_field = add_tag("species", "Species", "e.g. Bacterium Tela")
        self.mission_names_field = add_tag(
            "mission_names", "Mission name contains", "e.g. massacre, courier"
        )

        self.outcomes_row = CheckRow("", [item.value for item in MissionOutcome])
        self.outcomes_row.boxes[MissionOutcome.COMPLETED.value].setChecked(True)
        outcomes_caption = label("Outcomes")
        filter_form.addRow(outcomes_caption, self.outcomes_row)
        self.fields["outcomes"] = self.outcomes_row
        self.rows["outcomes"] = (outcomes_caption, self.outcomes_row)

        self.factions_field = add_tag("factions", "Factions", "e.g. Nobles of Dagr")
        self.powers_field = add_tag("powers", "Powers", "e.g. Nakato Kaine")
        self.systems_field = add_tag(
            "systems", "Systems", "e.g. Sol, Deciat \u2014 exactly as in the galaxy map"
        )
        self.stations_field = add_tag("stations", "Stations", "e.g. Jameson Memorial")
        self.station_types_field = add_tag(
            "station_types", "Station types", STATION_TYPES
        )
        self.market_ids_field = add_tag(
            "market_ids",
            "Market IDs",
            "exact match \u2014 the surest way to pin a carrier",
        )

        self.discovery_row = CheckRow("", ["Only bodies nobody had discovered before"])
        discovery_caption = label("First discovery")
        filter_form.addRow(discovery_caption, self.discovery_row)
        self.fields["discovery"] = self.discovery_row
        self.rows["discovery"] = (discovery_caption, self.discovery_row)

        self.mapping_row = CheckRow("", ["Only bodies nobody had mapped before"])
        mapping_caption = label("First mapping")
        filter_form.addRow(mapping_caption, self.mapping_row)
        self.fields["mapping"] = self.mapping_row
        self.rows["mapping"] = (mapping_caption, self.mapping_row)

        check_row = QHBoxLayout()
        self.check_button = button("Check names against Spansh")
        self.check_button.setToolTip(
            "Look up the systems and stations you have typed. Advisory "
            "only \u2014 EDSG never blocks on this, and a name Spansh has "
            "not heard of may still be perfectly valid."
        )
        self.check_button.clicked.connect(self._check_names)
        self.check_result = label("", "hint", wrap=True)
        check_row.addWidget(self.check_button)
        check_row.addWidget(self.check_result, 1)
        layout.addLayout(check_row)

        layout.addWidget(self.filters_group)
        layout.addWidget(
            label(
                "These options change with the metric chosen above. Leave a "
                "field blank to place no restriction on it. Names are "
                "matched loosely \u2014 case and punctuation are ignored \u2014 "
                "but a misspelling will silently score zero, so check them "
                "against the standings preview before the event closes.",
                "hint",
                wrap=True,
            )
        )

        # -- scoring ---------------------------------------------------
        scoring_group = QGroupBox("How it scores")
        scoring_layout = QVBoxLayout(scoring_group)

        row = QHBoxLayout()
        row.setSpacing(16)

        self.points_spin = QDoubleSpinBox()
        self.points_spin.setDecimals(6)
        self.points_spin.setRange(-1_000_000.0, 1_000_000.0)
        self.points_spin.setValue(1.0)
        row.addWidget(label("Points per unit"))
        row.addWidget(self.points_spin)

        self.cap_field = QLineEdit()
        self.cap_field.setPlaceholderText("no cap")
        self.cap_field.setMaximumWidth(120)
        row.addWidget(label("Cap at"))
        row.addWidget(self.cap_field)

        self.minimum_field = QLineEdit()
        self.minimum_field.setPlaceholderText("none")
        self.minimum_field.setMaximumWidth(120)
        row.addWidget(label("Minimum"))
        row.addWidget(self.minimum_field)
        row.addStretch(1)
        scoring_layout.addLayout(row)

        scoring_layout.addWidget(
            label(
                "A cap limits how many units can convert to points, so one "
                "runaway category cannot decide the whole event. A minimum "
                "must be reached before any units score at all.",
                "hint",
                wrap=True,
            )
        )

        self.notes_field = QPlainTextEdit()
        self.notes_field.setPlaceholderText(
            "Optional. Shown to participants and printed in the reports."
        )
        self.notes_field.setMaximumHeight(60)
        scoring_layout.addWidget(label("Notes"))
        scoring_layout.addWidget(self.notes_field)
        layout.addWidget(scoring_group)
        layout.addStretch(1)

        # -- buttons ---------------------------------------------------
        buttons = QDialogButtonBox()
        save = buttons.addButton("Save criterion", QDialogButtonBox.AcceptRole)
        save.setProperty("role", "primary")
        buttons.addButton(QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    # -- behaviour ------------------------------------------------------

    # Qt round-trips combo box user data through QVariant, which turns a
    # StrEnum member back into a plain str. These two helpers convert it
    # back rather than letting a bare string escape into the core layer.
    def _current_kind(self) -> MetricKind:
        return MetricKind(self.kind_box.currentData())

    def _current_measure(self) -> Measure:
        return Measure(self.measure_box.currentData())

    def _on_kind_changed(self) -> None:
        kind = self._current_kind()
        self.kind_help.setText(kind.description)

        previous = self.measure_box.currentData()  # plain str, or None
        self.measure_box.blockSignals(True)
        self.measure_box.clear()
        allowed = ALLOWED_MEASURES[kind]
        for measure in allowed:
            self.measure_box.addItem(measure.label, measure)
        index = self.measure_box.findData(previous)
        self.measure_box.setCurrentIndex(index if index >= 0 else 0)
        self.measure_box.blockSignals(False)
        self._on_measure_changed()

        groups = FILTER_GROUPS[kind]
        visible: set[str] = set()
        if "events" in groups:
            visible.add("events")
        if "commodities" in groups:
            visible.add("commodities")
        if "bio" in groups:
            visible.update({"genera", "species"})
        if "missions" in groups:
            visible.update({"mission_names", "outcomes"})
        if "factions" in groups:
            visible.add("factions")
        if "powers" in groups:
            visible.add("powers")
        if "systems" in groups or "location" in groups:
            visible.add("systems")
        if "location" in groups:
            visible.update({"stations", "station_types"})
        if "market" in groups:
            visible.add("market_ids")
        if "discovery" in groups:
            visible.add("discovery")
        if "mapping" in groups:
            visible.add("mapping")

        for key, (caption, field) in self.rows.items():
            show = key in visible
            caption.setVisible(show)
            field.setVisible(show)

    def _on_measure_changed(self) -> None:
        if self.measure_box.currentIndex() < 0:
            self.measure_help.setText("")
            return
        self.measure_help.setText(MEASURE_HELP.get(self._current_measure(), ""))

    def _load(self, criterion: Criterion) -> None:
        self.label_field.setText(criterion.label)
        self.kind_box.setCurrentIndex(self.kind_box.findData(criterion.kind))
        self._on_kind_changed()
        index = self.measure_box.findData(criterion.measure)
        if index >= 0:
            self.measure_box.setCurrentIndex(index)

        filters = criterion.filters
        self.events_field.set_values(filters.event_names)
        self.commodities_field.set_values(filters.commodities)
        self.genera_field.set_values(filters.genera)
        self.species_field.set_values(filters.species)
        self.mission_names_field.set_values(filters.mission_names)
        self.factions_field.set_values(filters.factions)
        self.powers_field.set_values(filters.powers)
        self.systems_field.set_values(filters.systems)
        self.stations_field.set_values(filters.stations)
        self.station_types_field.set_values(filters.station_types)
        self.market_ids_field.set_values(filters.market_ids)
        self.outcomes_row.set_checked(filters.mission_outcomes)

        for name, box in self.discovery_row.boxes.items():
            box.setChecked(filters.first_discovery_only)
            del name
        for name, box in self.mapping_row.boxes.items():
            box.setChecked(filters.first_mapped_only)
            del name

        self.points_spin.setValue(criterion.points_per_unit)
        self.cap_field.setText(
            "" if criterion.unit_cap is None else f"{criterion.unit_cap:g}"
        )
        self.minimum_field.setText(
            "" if criterion.minimum_units is None else f"{criterion.minimum_units:g}"
        )
        self.notes_field.setPlainText(criterion.notes)

    @staticmethod
    def _optional_float(field: QLineEdit, name: str) -> float | None:
        text = field.text().strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError(f"{name} must be a number, not '{text}'.") from exc

    def _check_names(self) -> None:
        """Look the typed system and station names up on Spansh.

        A misspelling here scores zero in silence, and a signed
        invitation cannot be corrected afterwards without asking everyone
        to rescan, so it is worth catching now. The check never blocks
        saving: Spansh does not know every name, and being offline says
        nothing about spelling.
        """
        systems = self.systems_field.values()
        stations = self.stations_field.values()
        if not systems and not stations:
            self.check_result.setText("No system or station names to check.")
            return

        self.check_button.setEnabled(False)
        self.check_result.setText("Asking Spansh\u2026")

        def work(_report):
            return check_names(systems, stations)

        def finished(checks) -> None:
            self.check_button.setEnabled(True)
            problems, answered = summarise(checks)
            if not answered:
                self.check_result.setText(
                    "Could not reach Spansh, so nothing was checked. This "
                    "says nothing about your spelling."
                )
                return
            if not problems:
                self.check_result.setText(f"All {len(checks)} name(s) found on Spansh.")
                self.check_result.setProperty("role", "good")
            else:
                self.check_result.setText(" ".join(item.message() for item in problems))
                self.check_result.setProperty("role", "warn")
            self.check_result.style().unpolish(self.check_result)
            self.check_result.style().polish(self.check_result)

        def failed(exc: BaseException) -> None:
            self.check_button.setEnabled(True)
            self.check_result.setText(f"Could not check the names: {exc}")

        run_in_background(work, finished, failed)

    def _save(self) -> None:
        try:
            cap = self._optional_float(self.cap_field, "Cap")
            minimum = self._optional_float(self.minimum_field, "Minimum")
        except ValueError as exc:
            show_error(self, "Check the scoring values", exc)
            return

        kind = self._current_kind()
        filters = Filters(
            systems=self.systems_field.values(),
            stations=self.stations_field.values(),
            station_types=self.station_types_field.values(),
            market_ids=self.market_ids_field.int_values(),
            commodities=self.commodities_field.values(),
            event_names=self.events_field.values(),
            mission_names=self.mission_names_field.values(),
            mission_outcomes=(
                self.outcomes_row.checked() if kind is MetricKind.MISSIONS else []
            ),
            factions=self.factions_field.values(),
            genera=self.genera_field.values(),
            species=self.species_field.values(),
            powers=self.powers_field.values(),
            first_discovery_only=bool(self.discovery_row.checked()),
            first_mapped_only=bool(self.mapping_row.checked()),
        )

        template = Criterion(label="", kind=kind, measure=Measure.COUNT)
        criterion = Criterion(
            criterion_id=(
                self._existing.criterion_id
                if self._existing is not None
                else template.criterion_id
            ),
            label=self.label_field.text().strip(),
            kind=kind,
            measure=self._current_measure(),
            filters=filters,
            points_per_unit=self.points_spin.value(),
            unit_cap=cap,
            minimum_units=minimum,
            notes=self.notes_field.toPlainText().strip(),
        )

        problems = criterion.validate()
        if problems:
            show_error(
                self,
                "This criterion is not valid",
                problems[0],
                "\n".join(problems[1:]),
            )
            return

        self.result_criterion = criterion
        self.accept()


def edit_criterion(
    parent: QWidget | None, criterion: Criterion | None = None
) -> Criterion | None:
    """Open the dialog and return the saved criterion, or ``None``."""
    dialog = CriterionDialog(parent, criterion)
    if dialog.exec() == QDialog.Accepted:
        return dialog.result_criterion
    return None


__all__ = ["COMMON_EVENTS", "FILTER_GROUPS", "CriterionDialog", "edit_criterion"]
