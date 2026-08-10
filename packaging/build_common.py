"""Shared PyInstaller configuration for both EDSG binaries.

Imported by ``organizer.spec`` and ``participant.spec`` so the two builds
cannot drift apart. Anything that differs between them is a parameter.

On excluding Qt modules
-----------------------
PySide6 ships a very large surface: WebEngine alone is hundreds of
megabytes. EDSG uses QtCore, QtGui and QtWidgets and nothing else, so
everything else is excluded explicitly. This is a size decision, not a
licensing one.

On the Qt licence
-----------------
Qt is LGPL v3 and is never statically linked; PyInstaller bundles it as
ordinary shared libraries loaded at runtime. The licence texts are added
to DATA_FILES below so a copy travels inside every binary, and the
relinking requirement is met by publishing the complete source. See
docs/LICENSING.md.
"""

from __future__ import annotations

from pathlib import Path

#: Repository root, derived from this file's own location. PyInstaller
#: injects SPECPATH into the spec's namespace only, not into modules the
#: spec imports, so it cannot be relied on here.
ROOT = Path(__file__).resolve().parent.parent

#: The version file is bundled so a frozen binary can report its version.
VERSION_FILE = ROOT / "version"

#: Files shipped alongside the code inside the bundle.
DATA_FILES = [
    (str(VERSION_FILE), "."),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "THIRD-PARTY-NOTICES.md"), "."),
    (str(ROOT / "licenses"), "licenses"),
]

#: Qt modules EDSG never touches. Excluding them roughly halves the
#: binary and removes components with their own licensing questions.
QT_EXCLUDES = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtLocation",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetworkAuth",
    "PySide6.QtNfc",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSql",
    "PySide6.QtStateMachine",
    "PySide6.QtSvgWidgets",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
]

#: Other heavyweight packages that may be present in a build environment
#: but are never imported by EDSG.
OTHER_EXCLUDES = [
    "IPython",
    "matplotlib",
    "numpy",
    "pandas",
    "pytest",
    "scipy",
    "setuptools",
    "tkinter",
]

EXCLUDES = QT_EXCLUDES + OTHER_EXCLUDES

#: Imported lazily, so PyInstaller cannot see them by static analysis.
HIDDEN_IMPORTS = ["edsg.cli"]

#: ReportLab pulls these in at runtime. Only the organizer writes PDFs,
#: so only that build carries them.
REPORT_IMPORTS = [
    "reportlab.graphics.barcode",
    "reportlab.pdfbase._fontdata",
]


def analysis_kwargs(entry_point: str, extra_hidden: list[str] | None = None) -> dict:
    """Return the keyword arguments for a PyInstaller ``Analysis``."""
    return {
        "scripts": [str(ROOT / "src" / "edsg" / entry_point)],
        "pathex": [str(ROOT / "src")],
        "binaries": [],
        "datas": DATA_FILES,
        "hiddenimports": HIDDEN_IMPORTS + list(extra_hidden or []),
        "hookspath": [],
        "hooksconfig": {},
        "runtime_hooks": [],
        "excludes": EXCLUDES,
        "noarchive": False,
        "optimize": 0,
    }
