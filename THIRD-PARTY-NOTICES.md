# Third-party notices

ED: Squad Goals is licensed under the MIT licence (see `LICENSE`). The
distributed binaries additionally contain the components below. This file is
bundled inside every released binary and must stay accurate.

---

## Qt for Python (PySide6) and Qt — LGPL v3

- Upstream: https://www.qt.io/qt-for-python
- Licence: GNU Lesser General Public License version 3
- Full text: `licenses/LGPL-3.0-only.txt`, included in this distribution
- The LGPL also incorporates the GPL by reference: `licenses/GPL-3.0-only.txt`

**How EDSG satisfies the LGPL.** The LGPL lets a work under any licence —
including MIT, as EDSG is — use an LGPL library, provided the recipient of a
binary can replace that library with their own version. LGPLv3 section 4 lists
the conditions; EDSG meets them as follows.

- **Section 4(a) — notice.** This file, and the About dialog in both
  applications, state that Qt is used and under what licence.
- **Section 4(b) — licence copies.** The LGPL and GPL texts ship inside every
  binary and inside every release archive, in `licenses/`. A hyperlink would
  not be sufficient; an actual copy is required.
- **Section 4(c) — attribution on display.** The About dialog names Qt for
  Python and points to the bundled texts.
- **Section 4(d)(1) — relinking.** EDSG's complete source is published under
  the MIT licence at the project repository, the PyInstaller specifications
  used to produce the official binaries are in `packaging/`, and PySide6 is a
  standard `pip install`. Anyone may therefore rebuild these binaries against
  their own build of Qt. `docs/BUILDING.md` gives the exact commands.
- **Section 4(e) — installation information.** Not applicable; EDSG is
  downloadable desktop software, not a User Product with installed firmware.

**Qt is never statically linked.** PyInstaller bundles it as ordinary shared
libraries (`.so`, `.dll`, `.dylib`) which are extracted at launch and loaded
dynamically. UPX compression is disabled in the build specifications, partly
because it corrupts signed Qt libraries on Windows and partly because it would
obscure those libraries. Neither Qt nor PySide6 has been modified.

**If you fork EDSG and distribute binaries,** you inherit these obligations.
Keep your source public and buildable, keep `licenses/` in the bundle, keep
this file accurate, and do not statically link Qt.

---

## cryptography — Apache 2.0 OR BSD-3-Clause

- Upstream: https://github.com/pyca/cryptography
- Licence: dual-licensed; EDSG relies on it under Apache License 2.0
- Full text: https://www.apache.org/licenses/LICENSE-2.0

Provides the Ed25519 primitives used to sign invitations and submissions.
Bundling is permitted; attribution is required and given here.

---

## ReportLab — BSD-3-Clause

- Upstream: https://www.reportlab.com/
- Licence: BSD 3-Clause

Generates the PDF standings report. Present only in the organizer binary; the
participant binary never writes PDFs and does not bundle it.

---

## Pillow — MIT-CMU

- Upstream: https://github.com/python-pillow/Pillow
- Licence: MIT-CMU

A required dependency of ReportLab. Organizer binary only.

---

## PyInstaller (build tool)

- Upstream: https://pyinstaller.org/
- Licence: GPL 2.0 **with a bootloader exception**

PyInstaller is not a runtime dependency; it produces the binaries. Its
bootloader exception expressly permits distributing the resulting executables
under any licence, so EDSG's MIT licence is unaffected.

---

## Elite Dangerous

Elite Dangerous is a trademark of Frontier Developments plc. EDSG reads the
journal files the game writes to the local filesystem. It does not modify the
game, inject code, read process memory, or interact with Frontier's servers.
It is an unofficial community tool, not affiliated with, endorsed by, or
supported by Frontier Developments plc.
