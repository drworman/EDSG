"""Generating reference documentation from the criteria definitions.

Keeping this in the package rather than in a standalone script means the
documentation reads the very same tables the application does, so
``docs/CRITERIA.md`` cannot describe a metric that no longer exists or
omit one that does. Deliberately free of any Qt import.
"""

from __future__ import annotations

from edsg.core.criteria import (
    ALLOWED_MEASURES,
    FILTER_GROUPS,
    Measure,
    MetricKind,
)
from edsg.core.metrics import METRIC_EVENTS

#: Human wording for each filter group identifier.
GROUP_LABELS = {
    "events": "journal event names",
    "commodities": "commodities",
    "location": "systems, stations, station types",
    "market": "market IDs",
    "bio": "genera, species",
    "systems": "systems",
    "missions": "mission names, outcomes",
    "factions": "factions",
    "powers": "powers",
    "discovery": "first discoveries only",
    "mapping": "first mappings only",
}


def render_criteria_reference() -> str:
    """Return the full Markdown text of the criteria reference."""
    parts: list[str] = [
        '# Criteria reference\n\nA criterion pairs a **metric** (what to count) with **filters** (which events\ncount) and a **scoring rule** (what those units are worth). Keeping the three\nseparate means a small set of metrics covers a very large space of events:\n"tritium mined", "tritium sold to our carrier" and "anything sold at Jameson\nMemorial" are the same two metrics with different filters.\n\nThis page is generated from the source, so it cannot drift from what the\napplication actually does.\n\n## How filters combine\n\nWithin one field, values are **OR**-ed. Across fields, they are **AND**-ed.\nSo systems `Sol, Deciat` with commodities `Tritium` means *tritium, in Sol or\nDeciat*. An empty field means no restriction.\n\nName matching is forgiving on purpose: it is case-insensitive, ignores\nFrontier\'s `$name;` decoration, and matches on substrings. It also checks\n**both** the internal name and the localised in-game name, so a filter written\nas `lowtemperaturediamond` and one written as `Low Temp. Diamonds` behave\nidentically. Type whichever you have to hand.\n\n## Measures\n\n'
    ]

    parts.append("| Measure | Meaning |\n|---|---|")
    for measure in Measure:
        parts.append(f"| `{measure.value}` | {measure.label} |")
    parts.append(
        "\n`distinct` is the one worth understanding. It counts each unique thing once\nhowever often it recurs, so a body scanned three times contributes one unit.\nFor exploration criteria this is almost always what you want; `count` would\nreward re-scanning the same body.\n\n## Scoring\n\nEach criterion has:\n\n- **Points per unit** — may be fractional. For credit-based measures use\n  something small, e.g. `0.000001` to make one point per million credits.\n- **Cap** *(optional)* — the maximum units that convert to points. The raw\n  total is still recorded and reported, so a capped result shows both figures.\n- **Minimum** *(optional)* — a qualifying threshold. Below it the criterion\n  scores nothing at all.\n\nCaps are the main tool for keeping an event balanced: without one, a single\ncategory with a high unit count can decide the whole standings.\n\n## Metrics\n"
    )

    for kind in MetricKind:
        parts.append(f"### {kind.label}\n")
        parts.append(f"`{kind.value}`\n")
        parts.append(kind.description + "\n")

        measures = ", ".join(f"`{m.value}`" for m in ALLOWED_MEASURES[kind])
        default = ALLOWED_MEASURES[kind][0].value
        parts.append(f"- **Measures:** {measures} (default `{default}`)")

        events = METRIC_EVENTS[kind]
        if events:
            names = ", ".join(f"`{name}`" for name in sorted(events))
            parts.append(f"- **Journal events read:** {names}")
        elif kind is MetricKind.EVENT_COUNT:
            parts.append("- **Journal events read:** whichever you name in the filter")

        filters = sorted({GROUP_LABELS[group] for group in FILTER_GROUPS[kind]})
        parts.append(f"- **Filters:** {'; '.join(filters)}\n")

    parts.append(
        "## Worked examples\n\n**Mine 1,000 tonnes of tritium, capped**\n\n> Metric `mining_refined`, measure `tonnage`, commodities `Tritium`,\n> 1 point per unit, cap `1000`.\n\nEach `MiningRefined` event is exactly one tonne leaving the refinery, so\ntonnage is a straight count of those events.\n\n**Sell painite to one specific fleet carrier**\n\n> Metric `market_sell`, measure `tonnage`, commodities `Painite`,\n> market IDs `3705689088`.\n\nMarket ID is the surest way to pin a carrier, because carrier names change and\ncallsigns repeat. Find it in the organizer's own journal after docking there,\nor filter on station types `FleetCarrier` to accept any carrier.\n\n**Reward genuine exploration, not tourism**\n\n> Metric `bodies_scanned`, measure `distinct`, first discoveries only,\n> 5 points per unit.\n\nWithout *first discoveries only*, re-scanning well-travelled systems scores as\nwell as going somewhere new.\n\n**Completed massacre missions for one faction**\n\n> Metric `missions`, measure `count`, mission name contains `massacre`,\n> outcomes `completed`, factions `Nobles of Dagr`.\n\nMission names are matched against both the internal name\n(`Mission_MassacreWing_name`) and the player-facing one, so `massacre` catches\nthe wing and solo variants together.\n\n**Something EDSG has no metric for yet**\n\n> Metric `event_count`, measure `count`, journal events\n> `ColonisationContribution`.\n\nThe catch-all counts any journal event by name, including event types released\nafter this build of EDSG. It accepts the location filters too, so it can be\nscoped to a system or station.\n\n## A note on completeness\n\nThe purpose-built metrics cover mining, trade, exploration, exobiology,\ncombat, missions and Powerplay. Colonisation and Operations events do not yet\nhave dedicated metrics; score them with `event_count` in the meantime.\n\nIf you find yourself using `event_count` for the same thing repeatedly, that is\na good argument for a proper metric — see\n[CONTRIBUTING.md](../CONTRIBUTING.md#adding-a-metric).\n"
    )
    return "\n".join(parts)


__all__ = ["GROUP_LABELS", "render_criteria_reference"]
