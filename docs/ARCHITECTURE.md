# Architecture

## Layout

```
src/edsg/
├── version.py            Reads the root `version` file; the only source of truth
├── cli.py                Headless interface, reached via `--cli` in both binaries
├── win_console.py        Reattaches stdout for `--cli` on windowed Windows builds
├── docs_gen.py           Generates docs/CRITERIA.md from the criteria tables
├── organizer_main.py     Entry point for the organizer binary
├── participant_main.py   Entry point for the participant binary
│
├── core/                 Domain logic. No Qt, no I/O beyond files.
│   ├── canonical.py      Deterministic JSON encoding — the signing input
│   ├── crypto.py         Ed25519 identities, signed envelopes, verification
│   ├── criteria.py       Metrics, measures, filters, scoring rules
│   ├── errors.py         Exception hierarchy; messages are user-facing
│   ├── journal.py        Journal discovery, parsing, commander identity
│   ├── location.py       Tracks position; resolves MarketID to a station
│   ├── metrics.py        Single-pass scoring engine
│   ├── models.py         Event, invitation and submission documents
│   ├── palettes.py       Theme colours, with derived, contrast-checked tones
│   ├── paths.py          Per-role config dirs, journal discovery, workspace
│   ├── settings.py       Appearance and branding, shared by both binaries
│   ├── squadron.py       Membership reconciliation from journal evidence
│   ├── standings.py      Verification, ranking, tie-breaks
│   └── workflow.py       issue → participate → close
│
├── reports/              Output writers. No Qt.
│   ├── common.py         Shared formatting so all four formats agree
│   ├── style.py          Theme and branding passed to every writer
│   ├── json_report.py    Complete machine-readable record
│   ├── markdown_report.py
│   ├── html_report.py    Self-contained, no external assets
│   └── pdf_report.py     ReportLab; organizer build only
│
└── gui/                  PySide6. Imports core; core never imports this.
    ├── about.py          About dialog and the funding links
    ├── menus.py          The menu bar shared by both windows
    ├── preferences.py    Theme, custom colours and squadron branding
    ├── theme.py          Stylesheet, driven by core.palettes
    ├── widgets.py        Shared widgets and the background worker
    ├── criterion_dialog.py
    ├── organizer.py
    └── participant.py
```

## The one rule

**Nothing in `core/` or `reports/` may import Qt.**

That boundary is what lets the CLI, the test suite and both GUIs drive
identical logic. It also means the participant binary can omit ReportLab
entirely, and that `docs_gen.py` can generate reference documentation without a
display. `FILTER_GROUPS` lives in `core/criteria.py` rather than in the dialog
for exactly this reason.

## Two binaries, one codebase

Both entry points ship the whole package; the difference is which GUI module
they launch, and what PyInstaller therefore pulls in. The report writers are
imported lazily inside `cli.py` so the participant build does not carry
ReportLab — moving that import to module scope would silently add tens of
megabytes.

## Scoring: one pass

`MetricEvaluator` walks the journals once, offering each event to every
criterion that cares about it. Criteria are indexed by the event names they
consume, so the hot loop rejects irrelevant events with a single dict lookup.
This matters: the corpus EDSG was developed against holds 261,896 events for
two commanders over three months, and an event may define a dozen criteria.
A full scan of 157,131 events runs in about 1.6 seconds.

Each criterion owns an `Accumulator` holding its running total, a per-key
breakdown for the report, and a bounded set of sample events for the audit
trail.

### Why there is a market pre-pass

Several scoring-relevant events carry no location. `MarketSell` records only a
`MarketID`; `MiningRefined` records nothing but the commodity. Yet organizers
want rules like "ore sold to this specific fleet carrier".

`LocationTracker` replays location-bearing events to maintain the current
system and station. But a sale can appear *before* the `Docked` event that
names its market, whenever a journal file boundary falls between them. So
`build_market_directory()` makes a cheap first pass indexing every
`MarketID` → station seen anywhere in the folder, and scoring consults that
first. Against the development corpus this resolves 161 of 161 sales.

### Why filters match two spellings

Frontier emits both an internal name and a localised one: `lowtemperaturediamond`
and `Low Temp. Diamonds`. Organizers copy whichever they find — wikis and
third-party tools disagree about which to show. Filters therefore match against
both, case-insensitively, ignoring `$name;` decoration, on substrings.

Matching only the localised name was a real bug found in testing: a filter
written with the internal name matched nothing at all and scored a silent zero.

## Squadron membership

`SquadronStartup` is the strongest signal available, because the game emits it
at login for the squadron the commander is in *now*. `JoinedSquadron` only
proves membership at that moment and must be reconciled against later
departures.

The rule is chronological: take the newest join and the newest departure for
the squadron in question; whichever is later wins. Ties favour departure, since
a same-second join and leave is far more likely a leave recorded at login.

Departure events did not appear in the development corpus, so that path is
written against Frontier's documented schema and covered by synthetic tests.

## Robustness

Journals are read with `errors="replace"` and malformed lines are counted and
skipped rather than raising. A journal being written by a running game can end
mid-line, and one bad byte should not cost a participant their entire event.
The count travels into the submission so an organizer can see it.

Unknown event types are simply carried through — Frontier adds them with every
update, and the catch-all `event_count` metric can score them by name without a
new EDSG release.

## Qt object ownership

Two crashes in this codebase had the same root cause, and both are worth
knowing about before adding Qt objects.

**Background workers.** A `QRunnable` handed to `QThreadPool` is destroyed in
C++ the moment `run` returns, which could tear down the signals object while
a queued result was still in flight — a segfault inside the event loop with
no Python traceback. Workers now set `autoDelete(False)`, are held in
`_ACTIVE_WORKERS` until they report, and are drained on window close.

**Menus.** A menu created by `bar.addMenu(title)` is owned by Python, and
PySide6 returns a fresh wrapper on every `QAction.menu()` call, so releasing
any one of them destroys the menu the others still point at. Menus are built
with the window as parent *and* kept in a list on the window; both halves are
needed.

The general rule: if Qt hands back an object whose owner is ambiguous, give
it a parent and keep a reference.

## Threading

Journal scanning takes seconds, so it runs on a `QThreadPool` worker. Qt
widgets may only be touched from the UI thread, so the worker never receives
one; it gets a `report` callable whose payload arrives back as a signal on the
UI thread. See `gui/widgets.py`.

## Configuration is per role

The two binaries share an `EDSG` directory in the per-user configuration
location, and each keeps its own configuration in a subdirectory of it:

```
EDSG/
├── Organizer/
│   ├── keys/organizer.key
│   └── settings.json      appearance, branding, remembered squadron
└── Participant/
    ├── keys/participant.key
    └── settings.json      appearance
```

`paths.set_role()` is called once at start-up by each entry point, and
`config_dir()` resolves against it, so nothing downstream has to thread a role
through. The shared CLI sets the role per command — `issue` and `close` are
organizer actions, `participate` is not — because both binaries carry it.

The separation is not tidiness. An organizer's signing key is the one whose
fingerprint participants have been told to trust, and mixing the two roles in
one folder means copying a configuration drags that key along with it.

## Settings and theming

`core/palettes.py` holds the colour definitions and `core/settings.py` reads
and writes the one settings file both binaries share. Neither imports Qt, so
the report writers and the documentation generator can use them in a build
with no GUI toolkit at all.

Three colours — the table header background, its text, and the alternating
row tint — are *derived* from the palette rather than chosen, and the header
text is picked for contrast against its own background. That is deliberate: a
custom accent cannot produce an unreadable table.

`gui/theme.py` expands a palette into the stylesheet and mutates `COLOURS` in
place, so modules that imported that dict at import time follow a theme
change without needing a refresh hook.

## Error handling

Every deliberately raised error derives from `EDSGError`, and its message is
shown verbatim in a dialog. Messages are written for the commander who has to
act on them, and say what to do next.

`SignatureError` and `DocumentError` are deliberately distinct: one means a
tampered file, the other means the wrong file. Those call for very different
responses from the person reading them.
