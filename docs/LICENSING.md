# Licensing

**Short version:** EDSG is MIT. You can do essentially anything with it. The
one obligation that needs care is Qt's LGPL, and it is met by publishing the
source and shipping the licence texts.

## EDSG itself — MIT

Everything in this repository written for EDSG is under the
[MIT licence](../LICENSE). Use it, fork it, sell it, embed it in something
proprietary. Keep the copyright notice.

## Dependencies

| Component | Licence | Bundled in |
|---|---|---|
| PySide6 / Qt | **LGPL v3** | both binaries |
| cryptography | Apache 2.0 | both binaries |
| ReportLab | BSD 3-Clause | organizer only |
| Pillow | MIT-CMU | organizer only |
| PyInstaller | GPL 2.0 with bootloader exception | build tool only, not shipped |

Only one of these constrains how EDSG is packaged.

## Why PySide6 and not PyQt

PyQt6 is GPL-or-commercial. Using it would force EDSG itself to be GPL,
which conflicts with keeping the project permissive.

PySide6 is Qt's own binding and is **LGPL v3**. The LGPL explicitly permits a
work under any licence — MIT included — to use the library, subject to
conditions that are straightforward for a project like this one.

## Meeting the LGPL

LGPLv3 section 4 governs a "Combined Work" — an application that uses an LGPL
library. Its conditions, and how EDSG meets each:

**4(a) — Give notice that the library is used.**
`THIRD-PARTY-NOTICES.md` and the About dialog in both applications.

**4(b) — Include a copy of the GPL and the LGPL.**
`licenses/LGPL-3.0-only.txt` and `licenses/GPL-3.0-only.txt` are bundled inside
every binary and included in every release archive. A hyperlink does not
satisfy this; an actual copy is required. This is the condition most often
missed.

**4(c) — Display attribution where the application shows copyright notices.**
The About dialog names Qt for Python, states the LGPL, and points at the
bundled texts.

**4(d) — Let the recipient relink against their own Qt.**
Two options; EDSG relies on **4(d)(1)**: convey the application code in a form
that permits recombining it with a modified version of the library.

This is where a Python application is in an unusually comfortable position.
"Relinking" for EDSG is not a link step at all — it is `pip install` and
`python -m edsg.gui.organizer`. Since:

- the complete source is public under the MIT licence,
- the exact PyInstaller specifications used for the official binaries are in
  `packaging/`, and
- PySide6 is a standard package anyone can install, patch, or build from
  source,

anyone receiving a binary can rebuild an equivalent one against their own Qt.
[BUILDING.md](BUILDING.md) gives the commands. That satisfies 4(d)(1).

**4(e) — Installation Information.**
Not applicable. This clause applies to User Products with installed firmware,
not to downloadable desktop software.

### On single-file binaries

A single-file PyInstaller build is compatible with all of the above. It does
not statically link Qt: the Qt shared libraries are stored in the executable's
archive, extracted to a temporary directory at launch, and loaded dynamically
by the operating system's normal mechanism.

Two rules keep this true, and both are enforced in `packaging/`:

- **Never statically link Qt.** Nothing in the build does this today; do not
  add it.
- **UPX stays disabled.** It also corrupts signed Qt libraries on Windows, so
  there are two reasons.

An earlier draft of this project also published a `--onedir` archive for every
release, on the theory that visibly separate `.so` files were needed to satisfy
the relinking requirement. That was belt-and-braces rather than necessity:
4(d)(1) is met by the source being available, so the extra artefacts were
dropped. Anyone who wants a directory layout can produce one with `-D`.

### If you fork EDSG and distribute binaries

You inherit the LGPL obligations. Concretely:

1. Keep your source public and genuinely buildable, including your packaging
   configuration.
2. Keep `licenses/` inside your bundles.
3. Keep `THIRD-PARTY-NOTICES.md` accurate for whatever you actually ship.
4. Do not statically link Qt.

If you make your fork's source private, you lose the 4(d)(1) route and must
instead satisfy 4(d)(0), which is considerably more work. Keeping the source
open is by far the easier path.

## Adding a dependency

Before adding one, check its licence. Acceptable: MIT, BSD, Apache 2.0, ISC,
and similar permissive terms; or LGPL where the library is dynamically linked
and the source stays public.

Not acceptable: GPL or AGPL, which would force EDSG's own licence to change,
and anything with a non-commercial or field-of-use restriction, which would
stop it being open source at all.

Record every addition in `THIRD-PARTY-NOTICES.md`, and add the licence text to
`licenses/` if the licence requires a copy to accompany distribution.

## Elite Dangerous

Elite Dangerous is a trademark of Frontier Developments plc. EDSG reads journal
files the game writes to the local filesystem, in the documented format
Frontier publishes for exactly this purpose. It does not modify the game,
inject code, read process memory, or interact with Frontier's servers.

EDSG is an unofficial community tool, not affiliated with, endorsed by, or
supported by Frontier Developments plc. Do not imply otherwise in a fork.

## Not legal advice

This document explains the reasoning behind the project's licensing choices. It
was written by the project's contributors, who are not lawyers. If you are
redistributing EDSG in a context where the answer matters commercially, take
your own advice.
