# Changelog

All notable changes to ED: Squad Goals are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/);
see [CONTRIBUTING.md](CONTRIBUTING.md).

**Versions are `YYYYMMDD` datestamps**. The version
lives in the plain-text `version` file at the repository root, and a release
tag must match it exactly or the release workflow fails.

Because a datestamp carries no compatibility signal, anything affecting
compatibility between builds is called out here explicitly. Two constants
govern it: `SCHEMA_VERSION` in `core/models.py` for the structure of
invitations and submissions, and `CANONICAL_FORM` in `core/canonical.py` for
the encoding signatures are computed over.

## [20260816]

Everything below closes out feedback from external testing, plus the goal
tier system. Document schema is unchanged at `SCHEMA_VERSION` 1 and
signatures still use `edsg-canonical-json-1`, so invitations and
submissions issued by the previous release still verify.

### Added
- **Goal tiers and reward bands.** An event can now carry a collective
  target broken into up to five goal tiers, with up to five reward bands
  ranking the commanders who contributed. The shape follows Frontier's own
  community goals: everyone's points add into one total that climbs through
  tiers, and each commander is paid by the best band they reach. Tiers can
  be typed, split evenly from the target, or stepped in 20% increments from
  whichever end you know. Rewards escalate by a multiplier per tier reached,
  which keeps the configuration to ten inputs rather than a five-by-five
  grid. See [docs/GOALS.md](docs/GOALS.md).
- **Progress board in every report.** The HTML, PDF, Markdown and JSON
  outputs all show the tier reached, a meter marked with each threshold,
  how far the next tier is, and the reward band table with the points range
  each band covers.
- **Advisory name checking.** The criterion editor can look typed system
  and station names up on Spansh. A misspelled filter scores zero in
  silence and a signed invitation cannot be corrected afterwards, so it is
  worth catching first. Purely advisory: no API key, never blocks saving,
  and an unreachable Spansh is reported as "could not check" rather than as
  a spelling problem.
- **Commander picker.** A journal folder holding more than one account is
  now a choice rather than a dead end. Elite writes every account on a
  machine into the same folder, and the previous behaviour made EDSG
  unusable for anyone in that position. EDSG never guesses: the Frontier ID
  decides who a submission belongs to.
- **Quick-set period buttons** — whole day, this month, this year — and the
  event period now shows seconds, because it was storing them.
- **Autosave.** The working event is written into its own workspace folder
  whenever it changes, so closing the window no longer loses it.
- **Back and Next buttons** on the organizer, alongside the tabs.
- **Copy button** for the signing fingerprint, and a note in the interface
  explaining what the fingerprint is and where it comes from.
- Examples on the systems, stations and factions filter fields, and a
  standing note that the filter options follow the metric above them.

### Changed
- **Standings are presented as commander cards** rather than one very wide
  table. A column per criterion became unreadable past three or four
  criteria and pushed the totals away from the names; a card keeps each
  commander's rank, total and per-criterion breakdown together.
- **Events are stored in the user's Documents folder** — `Documents/EDSG/
  Events/` — rather than beside the binary. Writing next to the executable
  fails outright in Program Files and breaks the signature of a notarised
  macOS bundle. An `EDSG-portable.txt` marker beside a frozen binary
  restores the old behaviour for memory-stick use, and `EDSG_HOME` still
  overrides both.
- Event subfolders are numbered `1 - Invitation`, `2 - Submissions` and
  `3 - Standings`, so they list in the order they are used. Alphabetically,
  "standings" previously sorted between the other two.
- Participant submissions are written to `Documents/EDSG/Submissions`
  rather than inside Frontier's Saved Games tree.
- The organizer header now says what state the event is in and what to do
  next, which the previous `DRAFT`/`OPEN`/`CLOSED` label did not.
- The standings folder opens automatically once reports are published.

### Fixed
- **The event period defaulted to the current time of day, silently
  excluding part of the first day.** An event created at 10:39 and meant to
  cover a whole year began at `2026-01-01T10:39:36`, so anything logged that
  morning scored nothing. Periods now default to `00:00:00` and `23:59:59`.
- The organizer's Points column was the stretched last column, so its
  right-aligned value sat hundreds of pixels from its own header and the
  column read as empty. Commander now takes the slack.


### Added
- **Commander picker.** A journal folder holding more than one account is
  now a choice rather than a dead end. Elite writes every account on a
  machine into the same folder, and the previous behaviour made EDSG
  unusable for anyone in that position. EDSG never guesses: the Frontier ID
  decides who a submission belongs to.
- **Quick-set period buttons** — whole day, this month, this year — and the
  event period now shows seconds, because it was storing them.
- **Autosave.** The working event is written into its own workspace folder
  whenever it changes, so closing the window no longer loses it.
- **Back and Next buttons** on the organizer, alongside the tabs.
- **Copy button** for the signing fingerprint, and a note in the interface
  explaining what the fingerprint is and where it comes from.
- Examples on the systems, stations and factions filter fields, and a
  standing note that the filter options follow the metric above them.

### Changed
- **Events are stored in the user's Documents folder** — `Documents/EDSG/
  Events/` — rather than beside the binary. Writing next to the executable
  fails outright in Program Files and breaks the signature of a notarised
  macOS bundle. An `EDSG-portable.txt` marker beside a frozen binary
  restores the old behaviour for memory-stick use, and `EDSG_HOME` still
  overrides both.
- Event subfolders are numbered `1 - Invitation`, `2 - Submissions` and
  `3 - Standings`, so they list in the order they are used. Alphabetically,
  "standings" previously sorted between the other two.
- Participant submissions are written to `Documents/EDSG/Submissions`
  rather than inside Frontier's Saved Games tree.
- The organizer header now says what state the event is in and what to do
  next, which the previous `DRAFT`/`OPEN`/`CLOSED` label did not.
- The standings folder opens automatically once reports are published.

### Fixed
- **The event period defaulted to the current time of day, silently
  excluding part of the first day.** An event created at 10:39 and meant to
  cover a whole year began at `2026-01-01T10:39:36`, so anything logged that
  morning scored nothing. Periods now default to `00:00:00` and `23:59:59`.
- The organizer's Points column was the stretched last column, so its
  right-aligned value sat hundreds of pixels from its own header and the
  column read as empty. Commander now takes the slack.

## [20260811]

### Added
- **Per-binary configuration directories.** Each build now keeps everything it
  saves under `EDSG/Organizer/` or `EDSG/Participant/` in the OS-appropriate
  per-user location, rather than sharing one folder. An organizer's signing
  key is the one whose fingerprint participants have been told to trust, so
  copying a configuration between machines must not carry it into a
  participant install.
- **The organizer remembers its squadron.** A detected squadron, and the
  organizer's own name, are stored and offered as the default for every
  subsequent event. Detecting again overwrites them. Nothing here affects an
  already-issued invitation, which has the squadron baked into its signature.
- **Themes for both binaries and the reports.** Seven palettes ported from
  ED Linux Dash, plus per-colour overrides for a squadron's own scheme. Set
  per build, since each keeps its own configuration. See
  [docs/THEMES.md](docs/THEMES.md).
- **Squadron branding on every report.** Name, tag, up to four contact
  details and a logo, printed top-left. The logo is embedded in the HTML as
  a data URI so the report stays self-contained when it is shared.
- **An event workspace beside the binary.** Issuing an invitation creates
  `Events/<Event Name>/{invitation,submissions,standings}` and points the
  close tab at the new folders, so there is nowhere to guess. Event names are
  sanitised for the filesystem, including Windows reserved device names.
- **Full menu bars on both builds.** File, Options and Help, with
  preferences, the workspace and settings folders, documentation, the
  repository, issues, releases and an About dialog. A quiet "Support EDSG
  development" strip in the header carries the Patreon, Ko-fi and PayPal
  links from `.github/FUNDING.yml`, and a test fails if the two drift apart.
- **Standings preview.** Choosing the submissions folder scores every file
  and fills the standings table immediately, without closing the event or
  writing anything. Submissions that would be rejected are listed with their
  reason, so a problem is found while it can still be fixed rather than
  after the one irreversible action in the application.
- Wiki publishing: `.github/workflows/sync-wiki.yml` and
  `scripts/sync_wiki.sh` mirror the README and `docs/` to the GitHub wiki,
  rewriting internal links, pointing images at raw.githubusercontent, and
  generating the sidebar and footer. New docs are picked up automatically.
- Icon set and README artwork, generated by `scripts/generate_icons.py`:
  application icons for Windows (`.ico`), macOS (`.icns`) and Linux (`.png`),
  plus avatars in seven accent colours at 512 and 4096 px. Detail is dropped
  progressively below 64 px so the icon stays legible at taskbar size.
- Colonisation metrics: `colonisation_contribution` scores commodities
  delivered to a construction site, by tonnage, deliveries or distinct
  commodities; `colonisation_completion` scores construction sites that
  reached completion **and** which the commander actually supplied.
- GUI smoke tests covering every metric in the criterion dialog.

### Fixed
- **Menus were destroyed shortly after being built.** Qt menus created by
  `bar.addMenu(title)` are owned by Python, and PySide6 returns a fresh
  wrapper on every `QAction.menu()` call, so releasing any one of them
  destroyed the menu the others pointed at. Menus are now parented to the
  window and held by reference. They rendered at startup only because
  nothing had triggered a collection yet.
- **Report table headers were close to unreadable.** Header text was the
  muted body tone on a dark fill. Header colours are now derived from the
  palette and checked for contrast; every built-in theme clears 9.7:1,
  against a 4.5:1 requirement. The PDF prints dark-on-tint rather than
  white-on-near-black.
- **The organizer could segfault when closing an event.** Background tasks
  were left for Qt's thread pool to destroy, which could tear down the
  signals object while a queued result was still being delivered to the UI
  thread — a crash inside the event loop with no Python traceback. Workers
  now disable `autoDelete`, are held by reference until they report, and are
  drained when a window closes. Reproduced at roughly one run in six before
  the fix, zero in twenty afterwards.
- **CI never installed the package, so no test ever ran.** The test job
  installed the dependencies but not `edsg` itself, and pytest exited 4 on a
  `ModuleNotFoundError` in `conftest.py` before collecting anything. All nine
  matrix jobs had been failing this way.
- `Accumulator.breakdown` was a `Counter`, whose values are typed as `int`,
  but it accumulates tonnage and credits. Now a `dict[str, float]`, with the
  same ordering behaviour.
- **Windows release builds failed their smoke test.** The binaries are built
  windowed so no console flashes up, which on Windows leaves `sys.stdout`
  unusable, so `--cli` produced no output at all and exited with
  `OSError: [Errno 22]`. The `--cli` path now picks up the inherited
  standard handles when output is redirected, and only borrows the parent
  process's console when nothing was inherited — attaching first would
  have replaced a redirected handle and sent the output to the console
  instead of the caller's pipe. Affected every Windows user of the
  headless interface, not only CI.
- Journal files renamed with underscores — as cloud sync, upload forms and
  email clients routinely do — are now read instead of silently ignored,
  which had scored affected participants zero.
- Combo box selections lost their type after the `StrEnum` migration,
  because Qt round-trips user data through `QVariant` as a plain string.
  This broke the criterion dialog entirely.
- `colonisation_contribution` measured in `count` counted commodity line
  items rather than deliveries.

### Changed
- The Linux configuration directory is `~/.config/EDSG` rather than
  `~/.config/edsg`, matching the other platforms and the folder name the
  documentation tells people to look for.
- Versions are `YYYYMMDD` datestamps; tags are the bare datestamp with no
  `v` prefix, and the release workflow triggers on any tag starting with a
  digit.
- **`LICENSE` now contains the MIT text and nothing else**, so GitHub
  identifies the licence and shows it on the repository page. The
  attribution, trademark notice and warranty disclaimer that used to trail
  it have moved to the licence section of the README. Measured against the
  SPDX template, the file went from 90.6% to 100% similarity — GitHub's
  detector needs about 98%.
- mypy is scoped to the Qt-free layer rather than run across the GUI.
  PySide6's stubs do not describe the enum access the interface uses, which
  produced 63 false errors out of 64.

### Removed
- **The continuous integration workflow.** It was reporting more noise than
  signal, and the checks it ran — `ruff check`, `ruff format --check`,
  `mypy` and `pytest` — are the same ones described in
  [CONTRIBUTING.md](CONTRIBUTING.md) for running locally before a push. The
  release workflow is unaffected and still builds, signs and smoke-tests
  every binary on all three platforms.

### Known limitations
- **Operations has no dedicated metric yet.** Operations launched on
  30 June 2026 (game version 4.4.0.0). No journal available during
  development contains Operations activity, most likely because the
  commander concerned never ran one, so the event names are unconfirmed.
  Operations start from the mission board, so `missions` and
  `powerplay_merits` may already cover them; `event_count` scores any event
  by name meanwhile. The `Squadron_Leaderboard_*` fields in `Statistics` are
  not used, because the sample cannot show whether they are per-commander or
  squadron-wide. See
  [docs/COLONISATION_AND_OPERATIONS.md](docs/COLONISATION_AND_OPERATIONS.md).

## [20260810]

First release. Everything below is new.

Document schema `SCHEMA_VERSION` 1, signing encoding
`edsg-canonical-json-1`.

### Added

**Event definition and distribution**
- Organizer application for defining events: name, description, UTC period
  with optional open-ended bounds, eligibility, and tie-break rule.
- Fourteen scoring metrics covering mining, trade, exploration, exobiology,
  combat, missions and Powerplay, plus a catch-all metric that counts any
  journal event by name so unreleased event types can still be scored.
- Filters for systems, stations, station types, market IDs, commodities,
  factions, mission names and outcomes, genera, species and powers. Filters
  match both Frontier's internal names and the localised in-game names.
- Per-criterion unit caps and qualifying minimums.
- Ed25519-signed `.edsgi` invitation files.
- Editable `.edsgevent` drafts so an event can be built over several sittings.

**Participation**
- Participant application: verifies an invitation's signature before anything
  else, then scans the commander's journals and produces a signed `.edsgs`
  submission named for their Frontier ID.
- Automatic journal folder discovery on Windows, macOS, and Linux including
  Steam Proton and Wine prefixes.
- Squadron eligibility checking: a join event for the organizer's squadron
  with no later leave, kick or disband.

**Closing and reporting**
- Submission verification with per-file rejection reasons; newer submissions
  from the same commander supersede older ones.
- Standings with standard competition ranking and three tie-break rules.
- Reports in JSON, Markdown, HTML and PDF.
- Closing an event is permanent; reports can be regenerated indefinitely from
  retained submissions.

**Platform**
- Single-file binaries for Windows, macOS and Linux, two per platform.
- Headless `--cli` interface in both binaries for scripting and CI.
- GitHub Actions workflows for CI and for signed, notarised releases.

### Security
- Document type and signing key are bound into the signed bytes, so a
  signature cannot be transplanted between document types or re-attributed to
  a substituted key.
- Canonical JSON encoding is versioned, so a future change to the encoding
  cannot silently invalidate old signatures.
- Private keys are written with owner-only permissions on POSIX systems.

### Known limitations
- Signing protects files in transit. It cannot attest that a participant's
  journal files were themselves unmodified. See [docs/SECURITY.md](docs/SECURITY.md).
- Colonisation and Operations journal events are not yet covered by dedicated
  metrics; the catch-all event metric can score them by name in the meantime.
- Squadron departure events are implemented against Frontier's documented
  schema and covered by synthetic tests, having not appeared in the journal
  corpus used during development.

[Unreleased]: https://github.com/drworman/EDSG/compare/20260816...HEAD
[20260816]: https://github.com/drworman/EDSG/compare/20260811...20260816
[20260811]: https://github.com/drworman/EDSG/compare/20260810...20260811
[20260810]: https://github.com/drworman/EDSG/releases/tag/20260810
