"""Colonisation contribution and completion metrics."""

from __future__ import annotations

from conftest import commander_events
from edsg.core.criteria import Criterion, Filters, Measure, MetricKind
from edsg.core.metrics import scan_journals

SITE_A = 3955868162
SITE_B = 3955872514


def score(journal_dir, criteria, window):
    return {r.label: r for r in scan_journals(journal_dir, criteria, window).results}


def docked(market_id, station, system="Kimuchok", when="2026-06-01T12:00:05Z"):
    return {
        "timestamp": when,
        "event": "Docked",
        "MarketID": market_id,
        "StationName": station,
        "StationType": "SurfaceStation",
        "StarSystem": system,
    }


def contribution(market_id, items, when="2026-06-05T10:00:00Z"):
    return {
        "timestamp": when,
        "event": "ColonisationContribution",
        "MarketID": market_id,
        "Contributions": [
            {
                "Name": f"${name.lower().replace(' ', '')}_name;",
                "Name_Localised": name,
                "Amount": amount,
            }
            for name, amount in items
        ],
    }


def depot(market_id, progress, complete, when="2026-06-06T10:00:00Z"):
    return {
        "timestamp": when,
        "event": "ColonisationConstructionDepot",
        "MarketID": market_id,
        "ConstructionProgress": progress,
        "ConstructionComplete": complete,
        "ConstructionFailed": False,
        "ResourcesRequired": [],
    }


def site_journal(make_journal):
    return make_journal(
        [
            *commander_events(),
            docked(SITE_A, "Orbital Construction Site: Paxton Enterprise"),
            docked(SITE_B, "Orbital Construction Site: Potter Hub"),
            contribution(SITE_A, [("Steel", 1280), ("CMM Composite", 18)]),
            contribution(SITE_A, [("Titanium", 700)]),
            contribution(SITE_B, [("Steel", 400)]),
        ]
    )


def test_tonnage_sums_every_commodity(make_journal, window):
    results = score(
        site_journal(make_journal),
        [
            Criterion(
                label="T",
                kind=MetricKind.COLONISATION_CONTRIBUTION,
                measure=Measure.TONNAGE,
            )
        ],
        window,
    )
    assert results["T"].raw_units == 2398


def test_count_measures_deliveries_not_line_items(make_journal, window):
    """A delivery of three commodities is one delivery, not three."""
    results = score(
        site_journal(make_journal),
        [
            Criterion(
                label="D",
                kind=MetricKind.COLONISATION_CONTRIBUTION,
                measure=Measure.COUNT,
            )
        ],
        window,
    )
    assert results["D"].raw_units == 3


def test_distinct_counts_commodities(make_journal, window):
    results = score(
        site_journal(make_journal),
        [
            Criterion(
                label="C",
                kind=MetricKind.COLONISATION_CONTRIBUTION,
                measure=Measure.DISTINCT,
            )
        ],
        window,
    )
    assert results["C"].raw_units == 3


def test_commodity_filter_matches_either_spelling(make_journal, window):
    for spelling in ("Steel", "$steel_name;", "steel"):
        results = score(
            site_journal(make_journal),
            [
                Criterion(
                    label="S",
                    kind=MetricKind.COLONISATION_CONTRIBUTION,
                    measure=Measure.TONNAGE,
                    filters=Filters(commodities=[spelling]),
                )
            ],
            window,
        )
        assert results["S"].raw_units == 1680, spelling


def test_deliveries_are_attributed_to_the_construction_site(make_journal, window):
    """The site name comes from a Docked event, not the delivery itself."""
    journal = site_journal(make_journal)
    paxton = score(
        journal,
        [
            Criterion(
                label="P",
                kind=MetricKind.COLONISATION_CONTRIBUTION,
                measure=Measure.TONNAGE,
                filters=Filters(stations=["Paxton Enterprise"]),
            )
        ],
        window,
    )
    potter = score(
        journal,
        [
            Criterion(
                label="P",
                kind=MetricKind.COLONISATION_CONTRIBUTION,
                measure=Measure.TONNAGE,
                filters=Filters(market_ids=[SITE_B]),
            )
        ],
        window,
    )
    assert paxton["P"].raw_units == 1998
    assert potter["P"].raw_units == 400


def test_completion_counts_each_site_once(make_journal, window):
    """The depot event repeats on every visit; re-docking must not score."""
    journal = make_journal(
        [
            *commander_events(),
            docked(SITE_A, "Site A"),
            contribution(SITE_A, [("Steel", 100)]),
            depot(SITE_A, 0.5, False),
            depot(SITE_A, 1.0, True),
            depot(SITE_A, 1.0, True),
            depot(SITE_A, 1.0, True),
        ]
    )
    results = score(
        journal,
        [
            Criterion(
                label="B",
                kind=MetricKind.COLONISATION_COMPLETION,
                measure=Measure.DISTINCT,
            )
        ],
        window,
    )
    assert results["B"].raw_units == 1


def test_completion_requires_having_supplied_the_site(make_journal, window):
    """Docking at somebody else's finished build must not score."""
    journal = make_journal(
        [
            *commander_events(),
            docked(SITE_A, "Site A"),
            docked(SITE_B, "Site B"),
            contribution(SITE_A, [("Steel", 100)]),
            depot(SITE_A, 1.0, True),
            depot(SITE_B, 1.0, True),  # never delivered to this one
        ]
    )
    results = score(
        journal,
        [
            Criterion(
                label="B",
                kind=MetricKind.COLONISATION_COMPLETION,
                measure=Measure.DISTINCT,
            )
        ],
        window,
    )
    assert results["B"].raw_units == 1
    assert "Site A" in results["B"].samples[0]


def test_incomplete_construction_does_not_score(make_journal, window):
    journal = make_journal(
        [
            *commander_events(),
            docked(SITE_A, "Site A"),
            contribution(SITE_A, [("Steel", 100)]),
            depot(SITE_A, 0.95, False),
        ]
    )
    results = score(
        journal,
        [
            Criterion(
                label="B",
                kind=MetricKind.COLONISATION_COMPLETION,
                measure=Measure.DISTINCT,
            )
        ],
        window,
    )
    assert results["B"].raw_units == 0


def test_contributions_outside_the_window_do_not_score(make_journal, window):
    journal = make_journal(
        [
            *commander_events(),
            docked(SITE_A, "Site A"),
            contribution(SITE_A, [("Steel", 500)], when="2026-06-05T10:00:00Z"),
            contribution(SITE_A, [("Steel", 900)], when="2026-08-05T10:00:00Z"),
        ]
    )
    results = score(
        journal,
        [
            Criterion(
                label="T",
                kind=MetricKind.COLONISATION_CONTRIBUTION,
                measure=Measure.TONNAGE,
            )
        ],
        window,
    )
    assert results["T"].raw_units == 500


def test_supply_outside_the_window_still_qualifies_a_completion(make_journal, window):
    """Delivering before the event opened still makes the build yours."""
    journal = make_journal(
        [
            *commander_events(),
            docked(SITE_A, "Site A"),
            contribution(SITE_A, [("Steel", 100)], when="2026-01-05T10:00:00Z"),
            depot(SITE_A, 1.0, True, when="2026-06-06T10:00:00Z"),
        ]
    )
    results = score(
        journal,
        [
            Criterion(
                label="B",
                kind=MetricKind.COLONISATION_COMPLETION,
                measure=Measure.DISTINCT,
            )
        ],
        window,
    )
    assert results["B"].raw_units == 1
