# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-folder bundle for Sheepy Pad."""

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

program_root = Path(SPECPATH).resolve().parents[1]
source_root = program_root.parent
excluded_qt_bindings = [
    "PySide2",
    "PySide6",
    "PyQt5",
    # Sheepy Pad is a runnable-script editor.  Keep PDF, printing and
    # WebEngine modules out of the analysis even when a PyQt/PyInstaller hook
    # discovers them transitively.
    "PyQt6.QtPdf",
    "PyQt6.QtPdfWidgets",
    "PyQt6.QtPrintSupport",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineQuick",
    "PyQt6.QtWebEngineWidgets",
]

forbidden_qt_payload_tokens = (
    "qtpdf",
    "qt6pdf",
    "qtprintsupport",
    "qt6printsupport",
    "qtwebengine",
    "qt6webengine",
)

def is_forbidden_qt_payload(entry) -> bool:
    return any(
        token in " ".join(str(part) for part in entry).lower()
        for token in forbidden_qt_payload_tokens
    )
hiddenimports = collect_submodules("sheepy_pad")
datas = [
    (str(program_root / "LICENSE"), "sheepy_pad"),
    (str(program_root / "docs"), "sheepy_pad/docs"),
    (str(program_root / "assets"), "sheepy_pad/assets"),
]

a = Analysis(
    [str(source_root / "main.py")],
    pathex=[str(source_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_qt_bindings,
    noarchive=False,
    optimize=1,
)
# Excludes prevent normal collection; this second filter is deliberately
# defensive against binary/data additions made by third-party hook versions.
a.binaries = [entry for entry in a.binaries if not is_forbidden_qt_payload(entry)]
a.datas = [entry for entry in a.datas if not is_forbidden_qt_payload(entry)]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="sheepy-pad",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="sheepy-pad",
)
