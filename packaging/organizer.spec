# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the organizer binary.

Build with:
    pyinstaller packaging/organizer.spec --noconfirm

Two layouts are produced from the same analysis. ONEFILE is the headline
artefact users download. ONEDIR is also published because it keeps the Qt
shared libraries as separate, replaceable files, which is the cleanest way
to satisfy the LGPL relinking requirement. See docs/LICENSING.md.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(SPECPATH)))
from build_common import REPORT_IMPORTS, ROOT, analysis_kwargs  # noqa: E402

APP_NAME = "EDSG-Organizer"
ICON = ROOT / "packaging" / "icons" / "edsg.ico"
ICNS = ROOT / "packaging" / "icons" / "edsg.icns"

a = Analysis(**analysis_kwargs("organizer_main.py", REPORT_IMPORTS + ["edsg.gui.organizer"]))
pyz = PYZ(a.pure)

icon = None
if sys.platform == "win32" and ICON.is_file():
    icon = str(ICON)
elif sys.platform == "darwin" and ICNS.is_file():
    icon = str(ICNS)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX corrupts signed Qt libraries on Windows
    runtime_tmpdir=None,
    console=False,      # GUI application: no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name=f"{APP_NAME}.app",
        icon=icon,
        bundle_identifier="com.edsg.organizer",
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": "ED: Squad Goals - Event Organizer",
            "CFBundleShortVersionString": (ROOT / "version").read_text().strip(),
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSHumanReadableCopyright": (
                "MIT licensed. Uses Qt for Python under the LGPL v3."
            ),
        },
    )
