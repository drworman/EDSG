"""Metric extraction and scoring."""

from __future__ import annotations

from conftest import commander_events
from edsg.core.criteria import Criterion, Filters, Measure, MetricKind
from edsg.core.metrics import scan_journals
from edsg.core.models import EventWindow


def score(journal_dir, criteria, window):
    return {r.label: r for r in scan_journals(journal_dir, criteria, window).results}


def mining(commodity_raw, commodity_local, count, when="2026-06-05T10:00:00Z"):
    return [
        {
            "timestamp": when,
            "event": "MiningRefined",
            "Type": commodity_raw,
            "Type_Localised": commodity_local,
        }
        for _ in range(count)
    ]


def test_each_mining_event_is_one_tonne(make_journal, window):
    journal = make_journal(
        [*commander_events(), *mining("$tritium_name;", "Tritium", 7)]
    )
    results = score(
        journal,
        [Criterion(label="T", kind=MetricKind.MINING_REFINED, measure=Measure.TONNAGE)],
        window,
    )
    assert results["T"].raw_units == 7


def test_commodity_filter_matches_localised_name(make_journal, window):
    journal = make_journal(
        [
            *commander_events(),
            *mining("$tritium_name;", "Tritium", 3),
            *mining("$platinum_name;", "Platinum", 5),
        ]
    )
    results = score(
        journal,
        [
            Criterion(
                label="T",
                kind=MetricKind.MINING_REFINED,
                measure=Measure.TONNAGE,
                filters=Filters(commodities=["Tritium"]),
            )
        ],
        window,
    )
    assert results["T"].raw_units == 3


def test_commodity_filter_matches_internal_name(make_journal, window):
    """Organizers copy internal names from wikis; both spellings must work."""
    journal = make_journal(
        [
            *commander_events(),
            {
                "timestamp": "2026-06-05T10:00:00Z",
                "event": "MarketSell",
                "MarketID": 1,
                "Type": "lowtemperaturediamond",
                "Type_Localised": "Low Temp. Diamonds",
                "Count": 10,
                "TotalSale": 1_000_000,
            },
        ]
    )
    for spelling in ("lowtemperaturediamond", "Low Temp. Diamonds"):
        results = score(
            journal,
            [
                Criterion(
                    label="LTD",
                    kind=MetricKind.MARKET_SELL,
                    measure=Measure.TONNAGE,
                    filters=Filters(commodities=[spelling]),
                )
            ],
            window,
        )
        assert results["LTD"].raw_units == 10, spelling


def test_events_outside_the_window_do_not_score(make_journal, window):
    journal = make_journal(
        [
            *commander_events(),
            *mining("$tritium_name;", "Tritium", 4, when="2026-06-05T10:00:00Z"),
            *mining("$tritium_name;", "Tritium", 9, when="2026-07-15T10:00:00Z"),
        ]
    )
    results = score(
        journal,
        [Criterion(label="T", kind=MetricKind.MINING_REFINED, measure=Measure.TONNAGE)],
        window,
    )
    assert results["T"].raw_units == 4


def test_unbounded_window_counts_everything(make_journal):
    journal = make_journal(
        [*commander_events(), *mining("$t;", "Tritium", 3, when="2019-01-01T00:00:00Z")]
    )
    results = score(
        journal,
        [Criterion(label="T", kind=MetricKind.MINING_REFINED, measure=Measure.TONNAGE)],
        EventWindow(),
    )
    assert results["T"].raw_units == 3


def test_sale_is_attributed_to_the_station_that_bought(make_journal, window):
    """MarketSell carries only a MarketID; the station comes from Docked."""
    journal = make_journal(
        [
            *commander_events(),
            {
                "timestamp": "2026-06-05T09:00:00Z",
                "event": "Docked",
                "MarketID": 42,
                "StationName": "Hutton Orbital",
                "StationType": "Outpost",
                "StarSystem": "Alpha Centauri",
            },
            {
                "timestamp": "2026-06-05T09:05:00Z",
                "event": "MarketSell",
                "MarketID": 42,
                "Type": "gold",
                "Count": 20,
                "TotalSale": 100,
            },
        ]
    )
    hit = score(
        journal,
        [
            Criterion(
                label="H",
                kind=MetricKind.MARKET_SELL,
                measure=Measure.TONNAGE,
                filters=Filters(stations=["Hutton Orbital"]),
            )
        ],
        window,
    )
    miss = score(
        journal,
        [
            Criterion(
                label="H",
                kind=MetricKind.MARKET_SELL,
                measure=Measure.TONNAGE,
                filters=Filters(stations=["Jameson Memorial"]),
            )
        ],
        window,
    )
    assert hit["H"].raw_units == 20
    assert miss["H"].raw_units == 0


def test_sale_before_its_docking_event_still_resolves(make_journal, window):
    """The market pre-pass exists so file-order cannot lose an attribution."""
    journal = make_journal(
        [
            *commander_events(),
            {
                "timestamp": "2026-06-05T09:05:00Z",
                "event": "MarketSell",
                "MarketID": 77,
                "Type": "gold",
                "Count": 15,
                "TotalSale": 100,
            },
            {
                "timestamp": "2026-06-05T11:00:00Z",
                "event": "Docked",
                "MarketID": 77,
                "StationName": "Carrier X9K-T2L",
                "StationType": "FleetCarrier",
                "StarSystem": "Sol",
            },
        ]
    )
    results = score(
        journal,
        [
            Criterion(
                label="C",
                kind=MetricKind.MARKET_SELL,
                measure=Measure.TONNAGE,
                filters=Filters(station_types=["FleetCarrier"]),
            )
        ],
        window,
    )
    assert results["C"].raw_units == 15


def test_only_analysed_organics_count(make_journal, window):
    """Log and Sample are partial; counting them would treble every score."""
    journal = make_journal(
        [
            *commander_events(),
            *(
                {
                    "timestamp": "2026-06-05T10:00:00Z",
                    "event": "ScanOrganic",
                    "ScanType": scan,
                    "Genus": "$g;",
                    "Genus_Localised": "Bacterium",
                    "Species": "$s;",
                    "Species_Localised": "Bacterium Tela",
                }
                for scan in ("Log", "Sample", "Analyse")
            ),
        ]
    )
    results = score(
        journal,
        [Criterion(label="B", kind=MetricKind.EXOBIO_SCANNED, measure=Measure.COUNT)],
        window,
    )
    assert results["B"].raw_units == 1


def test_first_discovery_filter(make_journal, window):
    journal = make_journal(
        [
            *commander_events(),
            {
                "timestamp": "2026-06-05T10:00:00Z",
                "event": "Scan",
                "ScanType": "Detailed",
                "BodyName": "A 1",
                "BodyID": 1,
                "SystemAddress": 100,
                "StarSystem": "A",
                "WasDiscovered": False,
            },
            {
                "timestamp": "2026-06-05T10:01:00Z",
                "event": "Scan",
                "ScanType": "Detailed",
                "BodyName": "A 2",
                "BodyID": 2,
                "SystemAddress": 100,
                "StarSystem": "A",
                "WasDiscovered": True,
            },
        ]
    )
    results = score(
        journal,
        [
            Criterion(
                label="D",
                kind=MetricKind.BODIES_SCANNED,
                measure=Measure.DISTINCT,
                filters=Filters(first_discovery_only=True),
            )
        ],
        window,
    )
    assert results["D"].raw_units == 1


def test_distinct_measure_deduplicates_rescans(make_journal, window):
    journal = make_journal(
        [
            *commander_events(),
            *(
                {
                    "timestamp": f"2026-06-05T10:0{i}:00Z",
                    "event": "Scan",
                    "ScanType": "AutoScan",
                    "BodyName": "A 1",
                    "BodyID": 1,
                    "SystemAddress": 100,
                    "StarSystem": "A",
                }
                for i in range(3)
            ),
        ]
    )
    distinct = score(
        journal,
        [
            Criterion(
                label="X", kind=MetricKind.BODIES_SCANNED, measure=Measure.DISTINCT
            )
        ],
        window,
    )
    counted = score(
        journal,
        [Criterion(label="X", kind=MetricKind.BODIES_SCANNED, measure=Measure.COUNT)],
        window,
    )
    assert distinct["X"].raw_units == 1
    assert counted["X"].raw_units == 3


def test_mission_outcome_filter(make_journal, window):
    journal = make_journal(
        [
            *commander_events(),
            {
                "timestamp": "2026-06-05T10:00:00Z",
                "event": "MissionCompleted",
                "Name": "Mission_Massacre_name",
                "LocalisedName": "Kill pirates",
                "MissionID": 1,
                "Reward": 1_000_000,
            },
            {
                "timestamp": "2026-06-05T11:00:00Z",
                "event": "MissionFailed",
                "Name": "Mission_Massacre_name",
                "MissionID": 2,
            },
        ]
    )
    done = score(
        journal,
        [
            Criterion(
                label="M",
                kind=MetricKind.MISSIONS,
                measure=Measure.COUNT,
                filters=Filters(mission_outcomes=["completed"]),
            )
        ],
        window,
    )
    failed = score(
        journal,
        [
            Criterion(
                label="M",
                kind=MetricKind.MISSIONS,
                measure=Measure.COUNT,
                filters=Filters(mission_outcomes=["failed"]),
            )
        ],
        window,
    )
    assert done["M"].raw_units == 1
    assert failed["M"].raw_units == 1


def test_event_count_scores_arbitrary_events(make_journal, window):
    """The catch-all must handle event types EDSG knows nothing about."""
    journal = make_journal(
        [
            *commander_events(),
            *(
                {"timestamp": "2026-06-05T10:00:00Z", "event": "SomeFutureEvent"}
                for _ in range(4)
            ),
        ]
    )
    results = score(
        journal,
        [
            Criterion(
                label="F",
                kind=MetricKind.EVENT_COUNT,
                measure=Measure.COUNT,
                filters=Filters(event_names=["SomeFutureEvent"]),
            )
        ],
        window,
    )
    assert results["F"].raw_units == 4


def test_cap_limits_points_but_records_the_raw_total(make_journal, window):
    journal = make_journal([*commander_events(), *mining("$t;", "Tritium", 100)])
    results = score(
        journal,
        [
            Criterion(
                label="T",
                kind=MetricKind.MINING_REFINED,
                measure=Measure.TONNAGE,
                points_per_unit=2.0,
                unit_cap=30,
            )
        ],
        window,
    )
    assert results["T"].raw_units == 100
    assert results["T"].counted_units == 30
    assert results["T"].points == 60


def test_minimum_threshold_blocks_scoring(make_journal, window):
    journal = make_journal([*commander_events(), *mining("$t;", "Tritium", 5)])
    results = score(
        journal,
        [
            Criterion(
                label="T",
                kind=MetricKind.MINING_REFINED,
                measure=Measure.TONNAGE,
                points_per_unit=1.0,
                minimum_units=10,
            )
        ],
        window,
    )
    assert results["T"].raw_units == 5
    assert results["T"].points == 0


def test_malformed_lines_are_skipped_not_fatal(tmp_path, window):
    directory = tmp_path / "broken"
    directory.mkdir()
    path = directory / "Journal.2026-06-01T120000.01.log"
    lines = [__import__("json").dumps(e) for e in commander_events()]
    lines.append("{not valid json")
    lines.append(
        __import__("json").dumps(
            {
                "timestamp": "2026-06-05T10:00:00Z",
                "event": "MiningRefined",
                "Type": "$t;",
                "Type_Localised": "Tritium",
            }
        )
    )
    path.write_text("\n".join(lines), encoding="utf-8")

    outcome = scan_journals(
        directory,
        [Criterion(label="T", kind=MetricKind.MINING_REFINED, measure=Measure.TONNAGE)],
        window,
    )
    assert outcome.stats.malformed_lines == 1
    assert outcome.results[0].raw_units == 1


def test_samples_and_breakdown_are_recorded(make_journal, window):
    journal = make_journal(
        [
            *commander_events(),
            *mining("$t;", "Tritium", 2),
            *mining("$p;", "Platinum", 3),
        ]
    )
    results = score(
        journal,
        [
            Criterion(
                label="Ore", kind=MetricKind.MINING_REFINED, measure=Measure.TONNAGE
            )
        ],
        window,
    )
    detail = results["Ore"].detail["breakdown"]
    assert detail["Platinum"] == 3
    assert detail["Tritium"] == 2
    assert results["Ore"].samples


def test_renamed_journal_files_are_still_read(tmp_path, window):
    """Files that arrive with underscores must not be silently ignored.

    Cloud sync, upload forms and email clients routinely rewrite
    ``Journal.2026-06-01T120000.01.log`` to
    ``Journal_2026-06-01T120000_01.log``. Skipping those would score a
    participant zero on perfectly good journals.
    """
    import json as _json

    from edsg.core.journal import find_journal_files

    directory = tmp_path / "renamed"
    directory.mkdir()
    events = [
        *commander_events(),
        {
            "timestamp": "2026-06-05T10:00:00Z",
            "event": "MiningRefined",
            "Type": "$tritium_name;",
            "Type_Localised": "Tritium",
        },
    ]
    path = directory / "Journal_2026-06-01T120000_01.log"
    path.write_text("\n".join(_json.dumps(event) for event in events), encoding="utf-8")
    (directory / "Status.json").write_text("{}", encoding="utf-8")

    assert [item.name for item in find_journal_files(directory)] == [path.name]
    outcome = scan_journals(
        directory,
        [
            Criterion(
                label="T",
                kind=MetricKind.MINING_REFINED,
                measure=Measure.TONNAGE,
            )
        ],
        window,
    )
    assert outcome.results[0].raw_units == 1


def test_windows_console_helper_is_safe_everywhere():
    """The console shim must never raise, whatever the streams look like.

    Windows release builds failed their smoke test because a windowed
    binary has no usable stdout. The fix runs on every start of the
    ``--cli`` path, so it must degrade quietly rather than take the
    command down with it.
    """
    import sys as _sys

    from edsg.win_console import _is_usable, enable_console_output

    assert _is_usable(_sys.stdout)
    assert not _is_usable(None)

    class Broken:
        def fileno(self):
            raise OSError("no descriptor")

    assert not _is_usable(Broken())

    original = _sys.stdout
    try:
        _sys.stdout = None
        enable_console_output()  # must not raise
    finally:
        _sys.stdout = original
