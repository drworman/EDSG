# Contributing to ED: Squad Goals

## Getting set up

```bash
git clone https://github.com/drworman/EDSG.git
cd EDSG
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -e .

pytest                       # run the suite
QT_QPA_PLATFORM=offscreen pytest   # if you have no display
python -m edsg.gui.organizer       # run the organizer from source
```

Python 3.11 or newer. The GUI needs a display; tests do not, thanks to Qt's
offscreen platform plugin.

## Conventional Commits

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).
This is not decoration: the changelog and the version bump are both derived
from these prefixes.

```
<type>(<optional scope>): <description>

[optional body]

[optional footer]
```

| Type | Use for |
|---|---|
| `feat` | A new capability |
| `fix` | A bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no behaviour change |
| `refactor` | Restructuring, no behaviour change |
| `perf` | A performance improvement |
| `test` | Adding or correcting tests |
| `build` | Build system, packaging, dependencies |
| `ci` | Workflow changes |
| `chore` | Anything else |

Add `!` after the type, or a `BREAKING CHANGE:` footer, for anything that
breaks compatibility with files earlier builds produced. That does not change
how the version is formed — see below — but it must be called out loudly in
the changelog, because a participant running an older build will be affected.

Useful scopes: `core`, `metrics`, `crypto`, `squadron`, `gui`, `reports`,
`cli`, `packaging`, `docs`.

```
feat(metrics): score colonisation contributions

fix(crypto): reject signatures transplanted between document types

The signed bytes did not include the document type, so a valid invitation
signature could be replayed onto a submission.

feat(reports)!: rename per-criterion JSON keys

BREAKING CHANGE: consumers reading `per_criterion` must migrate to
`per_criterion_points`.
```

## Versioning

**Versions are `YYYYMMDD` datestamps**, matching ED Linux Dash. A release is
identified by the day it was cut: `20260810`. Pre-releases may carry a suffix,
`20260810-rc1`, which the release workflow marks as a prerelease on GitHub.

The version lives in the plain-text `version` file at the repository root, and
nowhere else. Bump it in its own commit:

```bash
date -u +%Y%m%d > version
git commit -am "chore(release): $(cat version)"
git tag "$(cat version)"
git push && git push --tags
```

Tags are the bare datestamp — `20260810`, **not** `v20260810`. The release
workflow triggers on any tag starting with a digit and refuses to publish if
the tag and the `version` file disagree, so the two cannot drift. CI additionally checks that the datestamp
is a real calendar date, which catches transposed digits.

Two releases on the same day need a suffix — `20260810-1` — since the tag must
be unique.

### What replaces a major version bump

Datestamps carry no compatibility signal, so compatibility is tracked
explicitly by two constants, and these are what actually matter:

- **`SCHEMA_VERSION`** in `core/models.py` — the structure of invitations and
  submissions. Raise it when a field changes meaning or disappears. A build
  reading a document with a higher schema version refuses it and tells the
  user to update, rather than silently misreading it.
- **`CANONICAL_FORM`** in `core/canonical.py` — the byte encoding that
  signatures are computed over. **Changing this invalidates every signature
  ever issued.** It needs a migration path and a prominent changelog entry,
  never a quiet bump.

Neither is derived from the release date. An event issued last month must keep
working with a build cut today unless one of these deliberately changed.

## Code style

PEP 8, enforced by `ruff`:

```bash
ruff check src tests
ruff format src tests
mypy
```

Beyond what the linter checks:

- **Type-annotate public functions.** `from __future__ import annotations` is
  at the top of every module.
- **Comment the "why", not the "what".** If a line needs explaining, explain
  the reason it exists, not what it does. The comments worth keeping in this
  codebase are the ones recording a Frontier journal quirk or a decision that
  looks wrong until you know the constraint.
- **Errors are read by commanders, not developers.** Every exception derived
  from `EDSGError` is shown verbatim in a dialog. Write the message for the
  person who has to act on it, and say what to do next.
- **Keep the core free of Qt.** Nothing under `edsg/core/` or `edsg/reports/`
  may import PySide6. That boundary is what lets the CLI, the tests and both
  GUIs drive identical logic.

## Tests

New behaviour needs a test. Journal fixtures are synthesised in
`tests/conftest.py` rather than checked in, so the suite depends on no real
commander's play history and can exercise events that Frontier's own logs
happen not to contain.

Areas where a test is not optional:

- Anything in `core/crypto.py`. Include the negative case: what a forger tries.
- Any new metric. Cover the filter matching both internal and localised names,
  and the boundary of the event window.
- Squadron membership logic.

## Adding a metric

1. Add the member to `MetricKind` in `core/criteria.py`, with a label and a
   description written for an organizer rather than a developer.
2. Add its allowed measures to `ALLOWED_MEASURES`. Put the measure most people
   will want first; it becomes the default.
3. Add the journal events it reads to `METRIC_EVENTS` in `core/metrics.py`.
4. Write a `_handle_*` method and register it in `_HANDLERS`.
5. Add the filter groups it exposes to `FILTER_GROUPS` in
   `gui/criterion_dialog.py`.
6. Write tests, and add a row to `docs/CRITERIA.md`.

Adding a metric is a `feat`. It does not need a `SCHEMA_VERSION` bump, because
existing invitations keep working and a build that does not recognise a metric
refuses the invitation with a clear message rather than scoring it zero.

## Documentation and the wiki

The [wiki](https://github.com/drworman/EDSG/wiki) is generated. Never edit a
page there — the next push to `main` overwrites it. Edit the file in `docs/`
and let `.github/workflows/sync-wiki.yml` publish it.

A new file in `docs/` is picked up automatically: it is published, linked from
the sidebar under **Reference**, and its internal links are rewritten. Two
things need a change to `scripts/sync_wiki.sh`:

- **A nicer page title than the automatic one.** `SOME_DOC.md` becomes
  `Some-Doc`; add a line to `to_wiki_name()` to override that.
- **A different sidebar section.** Add the page name to `section_for()`.

To rehearse a sync without pushing:

```bash
mkdir /tmp/wiki-preview
WIKI_DIR=/tmp/wiki-preview bash scripts/sync_wiki.sh
```

Note that `docs/CRITERIA.md` is itself generated from the source — run
`python scripts/generate_criteria_doc.py` rather than editing it.

## Reporting bugs

Include the EDSG version, your platform, what you expected, what happened, and
the relevant lines from the in-application log pane.

**Never attach journal files or `.edsgs` submissions to a public issue.** They
contain your Frontier ID and your play history. If a maintainer needs one,
they will arrange a private channel.

## Licence

Contributions are accepted under the [MIT licence](LICENSE). Adding a
dependency requires a licence check first: it must be permissive or, like Qt,
LGPL and dynamically linked, and it must be recorded in
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). Copyleft dependencies that
would change EDSG's own licence will not be accepted.
