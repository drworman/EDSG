# Building EDSG

The official binaries are built by GitHub Actions from `packaging/*.spec`.
These are the same commands, so a local build matches a release build.

## Requirements

- Python 3.11 or newer
- A C toolchain is **not** required; every dependency ships wheels

## From source, without building a binary

```bash
git clone https://github.com/drworman/EDSG.git
cd EDSG
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .

python -m edsg.gui.organizer
python -m edsg.gui.participant
edsg --help                       # headless interface
```

This is also the answer to "how do I run EDSG against my own build of Qt?" —
install your Qt build in place of the PySide6 wheel and run the above.

## Building the binaries

```bash
pip install -r requirements-dev.txt

pyinstaller packaging/organizer.spec   --noconfirm --clean
pyinstaller packaging/participant.spec --noconfirm --clean
```

Artefacts land in `dist/`. Roughly 75–80 MB each; most of that is Qt.

For a directory layout instead of a single file, add `-D`:

```bash
pyinstaller packaging/organizer.spec --noconfirm -D
```

Build on the platform you are targeting. PyInstaller does not cross-compile.

## Verifying a build

Every binary carries the headless interface, which is the quickest way to
confirm it works:

```bash
./dist/EDSG-Organizer --cli version         # must match the `version` file
./dist/EDSG-Organizer --cli inspect some-event.edsgi
```

The release workflow runs this check on all three platforms and fails the
build on a mismatch — a binary that compiles but cannot import its own
modules is a real failure mode, and it will not show up any other way.

On a headless Linux machine, the GUI needs a virtual display:

```bash
xvfb-run -a ./dist/EDSG-Participant
```

## What the spec files do

`packaging/build_common.py` holds everything shared, so the two builds cannot
drift apart. Points worth knowing before changing it:

- **Qt modules are aggressively excluded.** EDSG uses QtCore, QtGui and
  QtWidgets. Everything else — WebEngine, Quick, 3D, Multimedia, SQL — is
  excluded by name. This roughly halves the binary.
- **ReportLab is organizer-only.** The participant never writes a PDF, so it
  does not carry ReportLab or Pillow. The report writers are imported lazily
  in `cli.py` to keep it that way; moving that import to module scope would
  silently re-add tens of megabytes to the participant build.
- **UPX is disabled.** It corrupts signed Qt libraries on Windows, and it
  would obscure the Qt shared libraries that the LGPL expects to remain
  replaceable. Leave it off.
- **`licenses/` is bundled as data.** LGPLv3 section 4(b) requires the licence
  texts to accompany the binary. See [LICENSING.md](LICENSING.md).
- **Console is off.** These are GUI applications; a console window would flash
  up on Windows. The `--cli` interface still works and still prints to stdout
  when run from a terminal.

## Before you release

There is no CI workflow, so nothing checks a commit before it is tagged. Run
the full set locally first:

```bash
ruff check src tests scripts
ruff format --check src tests scripts
mypy src/edsg/core src/edsg/reports src/edsg/cli.py \
     src/edsg/version.py src/edsg/docs_gen.py src/edsg/win_console.py
QT_QPA_PLATFORM=offscreen pytest -q
```

The release workflow does smoke-test each built binary — it runs
`--cli version` on all three platforms and fails on a mismatch — but that
catches a broken build, not a broken change.

## Releasing

Versions are `YYYYMMDD` datestamps, so a release is identified by the day it
was cut.

1. Update `CHANGELOG.md` under a new version heading, e.g. `## [20260810]`.
2. Write the datestamp into the `version` file — it is the single source of
   truth, and nothing else needs editing.
3. Commit, tag, and push both:

```bash
date -u +%Y%m%d > version
git commit -am "chore(release): $(cat version)"
git tag "$(cat version)"
git push && git push --tags
```

Tags carry no `v` prefix: the tag is the datestamp itself, `20260810`. The
release workflow triggers on any tag starting with a digit, and refuses to
publish when the tag and the `version` file disagree, so the two cannot
drift. CI also rejects a datestamp that is not a
real calendar date, which catches transposed digits.

Two releases on the same day need a suffix, `20260810-1`, because the tag has
to be unique. A suffix also marks the release as a prerelease on GitHub.

## Code signing

Signing steps are skipped when their secrets are absent, so forks build
without any credentials configured.

| Secret | Purpose |
|---|---|
| `WINDOWS_CERT_PFX_BASE64` | Authenticode certificate, base64-encoded `.pfx` |
| `WINDOWS_CERT_PASSWORD` | Its password |
| `MACOS_CERT_P12_BASE64` | Developer ID Application certificate, base64 `.p12` |
| `MACOS_CERT_PASSWORD` | Its password |
| `MACOS_SIGN_IDENTITY` | e.g. `Developer ID Application: Name (TEAMID)` |
| `MACOS_NOTARY_APPLE_ID` | Apple ID for notarisation |
| `MACOS_NOTARY_PASSWORD` | An app-specific password |
| `MACOS_NOTARY_TEAM_ID` | Apple Developer team ID |

To encode a certificate:

```bash
base64 -i certificate.pfx | tr -d '\n' | pbcopy      # macOS
base64 -w0 certificate.p12                            # Linux
```

macOS notarisation requires the hardened runtime, which by default blocks
PyInstaller's unpack-and-load behaviour. `packaging/entitlements.plist` grants
the three entitlements that allow it and no more.

Unsigned macOS builds are quarantined by Gatekeeper; users must right-click and
choose Open on first launch. Unsigned Windows builds raise a SmartScreen
warning until the certificate accrues reputation.
