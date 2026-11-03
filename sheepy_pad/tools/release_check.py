#!/usr/bin/env python3
"""Static release checks for Sheepy Pad 0.4.2."""

from __future__ import annotations

import ast
import hashlib
import os
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

PROGRAM_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROGRAM_ROOT.parent
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
OFFICIAL_MASTER_SHA256 = "9e6a96bccacfa8019a7cd8f6439895841204255a0e5dc9d81eb8d8d82117bb5a"
IGNORED_GENERATED_DIRS = {".git", ".venv", "venv", "build", "dist"}
# Approved public README, normalised only for future release-version changes.
APPROVED_README_NORMALIZED_SHA256 = "1fab15bb80a228c7feb01144932b418838be4a0b2123bb3229f0590dfa048976"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        fail(f"invalid PNG: {path.relative_to(SOURCE_ROOT)}")
    if header[12:16] != b"IHDR":
        fail(f"missing PNG IHDR: {path.relative_to(SOURCE_ROOT)}")
    return struct.unpack(">II", header[16:24])


def compile_python(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    ast.parse(source, filename=str(path))


def main() -> int:
    # Portable source root includes the approved public README beside
    # the launcher, Suite manifest, and program tree.
    root_entries = {path.name for path in SOURCE_ROOT.iterdir() if path.name != "__pycache__"}
    if root_entries != {"main.py", "README.md", "suite-pythoine-component.json", "sheepy_pad"}:
        fail(f"source root must contain only main.py, README.md, suite-pythoine-component.json and sheepy_pad/: {sorted(root_entries)}")

    required_program_entries = {
        "__init__.py",
        "app.py",
        "code_editor.py",
        "file_io.py",
        "runtime_launcher.py",
        "runtime_paths.py",
        "script_runtime.py",
        "script_library.py",
        "assets",
        "docs",
        "packaging",
        "portable",
        "tests",
        "tools",
        "requirements.txt",
        "LICENSE",
        ".gitignore",
        "SOURCE_MANIFEST.sha256",
        "sheepy-pad.json",
        "qa",
    }
    missing = required_program_entries - {p.name for p in PROGRAM_ROOT.iterdir()}
    if missing:
        fail(f"portable program tree is incomplete: {', '.join(sorted(missing))}")

    readme = SOURCE_ROOT / "README.md"
    if not readme.is_file():
        fail("approved public source-root README.md is missing")
    readme_bytes = readme.read_bytes()
    if b"0.4.2" not in readme_bytes:
        fail("public README is not updated to release 0.4.2")
    normalized_readme = readme_bytes.replace(b"0.4.2", b"@VERSION@")
    if hashlib.sha256(normalized_readme).hexdigest() != APPROVED_README_NORMALIZED_SHA256:
        fail("locked public README.md changed beyond release version numbers")

    compile_python(SOURCE_ROOT / "main.py")
    for path in sorted(PROGRAM_ROOT.glob("*.py")):
        compile_python(path)
    for path in sorted((PROGRAM_ROOT / "tests").glob("test_*.py")):
        compile_python(path)

    generated = []
    for path in SOURCE_ROOT.rglob("*"):
        relative = path.relative_to(SOURCE_ROOT)
        if any(part in IGNORED_GENERATED_DIRS for part in relative.parts):
            continue
        if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}:
            generated.append(relative)
    if generated:
        fail(f"generated Python cache files remain: {generated[0]}")

    init_source = (PROGRAM_ROOT / "__init__.py").read_text(encoding="utf-8")
    if 'APP_NAME = "Sheepy Pad"' not in init_source:
        fail("canonical application name is not Sheepy Pad")
    if 'APP_VERSION = "0.4.2"' not in init_source:
        fail("canonical application version is not 0.4.2")
    for fragment in (
        'APP_ID = "sheepy-pad"',
        'PUBLISHER_ID = "brunonlinespace"',
        'DESKTOP_ID = "io.github.brunonlinespace.sheepy-pad"',
    ):
        if fragment not in init_source:
            fail(f"canonical application identity fragment missing: {fragment}")

    project_manifest = PROGRAM_ROOT / "sheepy-pad.json"
    try:
        import json
        identity = json.loads(project_manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail(f"invalid Sheepy Pad project manifest: {exc}")
    expected_identity = {
        "name": "Sheepy Pad",
        "id": "sheepy-pad",
        "version": "0.4.2",
        "publisher_id": "brunonlinespace",
        "desktop_id": "io.github.brunonlinespace.sheepy-pad",
        "repository": "https://github.com/brunonlinespace/sheepy-pad",
        "tagline": "Friendly. Fast. Focused.",
    }
    for key, expected in expected_identity.items():
        if identity.get(key) != expected:
            fail(f"project manifest identity mismatch: {key}")

    component_manifest = SOURCE_ROOT / "suite-pythoine-component.json"
    try:
        component = json.loads(component_manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail(f"invalid Suite Pythoine component manifest: {exc}")
    expected_component = {
        "id": "sheepy-pad",
        "name": "Sheepy Pad",
        "description": "A lightweight Python and shell-script editor.",
        "component_kind": "editor",
        "extensions": [".py", ".sh"],
        "portable_command": ["main.py"],
        "icon": "sheepy_pad/assets/icons/sheepy-pad.png",
        "version": "0.4.2",
        "publisher": "brunonlinespace",
        "repository": "https://github.com/brunonlinespace/sheepy-pad",
        "desktop_id": "io.github.brunonlinespace.sheepy-pad",
        "tagline": "Friendly. Fast. Focused.",
        "publisher_id": "brunonlinespace",
        "capabilities": {"routing": True, "open": True, "create": True},
    }
    if component != expected_component:
        fail("Suite Pythoine component manifest does not match the canonical Sheepy Pad contract")

    launcher = (SOURCE_ROOT / "main.py").read_text(encoding="utf-8")
    if "from sheepy_pad.app import main" not in launcher:
        fail("root launcher is not location-independent through sheepy_pad.app")

    app_source = (PROGRAM_ROOT / "app.py").read_text(encoding="utf-8")
    editor_source = (PROGRAM_ROOT / "code_editor.py").read_text(encoding="utf-8")
    paths_source = (PROGRAM_ROOT / "runtime_paths.py").read_text(encoding="utf-8")
    launcher_source = (PROGRAM_ROOT / "runtime_launcher.py").read_text(encoding="utf-8")

    required_app_fragments = (
        'GITHUB_URL = "https://github.com/brunonlinespace/sheepy-pad"',
        'return f"{subject} — {APP_NAME}"',
        'application.setDesktopFileName("sheepy-pad")',
        'Friendly. Fast. Focused.',
        '"--sheepy-pad-smoke-test"',
        'print("GUI smoke test passed.", flush=True)',
        '"View Only"',
        '"Launch as Admin in Terminal"',
        '"Run with Arguments..."',
        'QKeySequence("Ctrl+1")',
        'QKeySequence("Ctrl+Shift+1")',
        'QKeySequence("Ctrl+2")',
        'QKeySequence("Ctrl+3")',
        'QKeySequence("Ctrl+4")',
        'QKeySequence("Ctrl+5")',
        'QKeySequence("Ctrl+6")',
        '"Syntax / Lint Check"',
        '"Select Interpreter..."',
        '"Working Directory..."',
        '"Environment Profiles..."',
        'QKeySequence("Ctrl+L")',
        'def toggle_library_shortcut(self) -> None:',
        'def set_library_sidebar_hidden(self, hidden: bool) -> None:',
        'self._library_sidebar_shortcut_hidden = bool(hidden)',
        'self.set_library_sidebar_hidden(not self._library_sidebar_shortcut_hidden)',
        'lambda: self.window.set_library_sidebar_hidden(True)',
        'QListWidgetItem(f"★ {entry.label}" if favourite else entry.label)',
        '"Exec: Yes"',
        'self.stop_button = self._action_button("Stop", self.stop_script)',
        'self.launch_button.setVisible(not running)',
        'self.stop_button.setVisible(running)',
        '"Terminal closed; script stopped."',
        '"Duplicate File"',
        'QKeySequence("Ctrl+Shift+D")',
        'QKeySequence("Ctrl+Shift+E")',
        'QKeySequence("F2")',
        'QKeySequence("Ctrl+Shift+O")',
        '"Documentation"',
        '"GitHub Repository"',
        '"Report an Issue"',
        '"Open Containing Folder"',
        '"More Actions"',
        '"Delete File"',
        'f"Ln: {current_line}/{total_lines}, "',
        'f"Col: {current_column}, Char: {total_characters}"',
        'os.environ["SHEEPY_PAD_APPIMAGE_THEME"]',
        'self.workspace_stack = QStackedWidget(self)',
        '"Start a Document"',
        'host.setEnabled(self.document_active)',
        'action.setEnabled(False)',
        '"Dark Editor"',
        'self.editor.set_color_scheme("dark" if self.dark_editor else "light")',
        'self.view_menu.addMenu("File Drag and Drop")',
        '"Opens on Active Window"',
        '"Opens on New Window"',
        'QKeySequence("Ctrl+Shift+X")',
        '"Duplicate Line / Selection"',
        '"Delete Line"',
        'QKeySequence("Ctrl+Shift+K")',
        'self.editor.delete_current_line_or_selection_lines',
        'self.library_menu = self.run_menu.addMenu("Library")',
        '"New Type..."',
        '"Default New Document..."',
        'self.document_type_menu = self.file_menu.addMenu("Document Type")',
        '"Use this type as my default"',
        '"Create Document"',
        '"Open Existing File..."',
        'self.favourites_menu = self.library_menu.addMenu("My Favourites")',
        'ScriptLibraryPanel(self, self, compact=True)',
        'ScriptLibraryPanel(window, self, compact=False)',
        'self.add_custom_button: QPushButton | None = None',
        'self.remove_custom_button: QPushButton | None = None',
        'self.import_button: QPushButton | None = None',
        'self.export_button: QPushButton | None = None',
        'self.category_combo = QComboBox(self)',
        'self.close_button.setText("×")',
        'self.editor_column_layout = QVBoxLayout(self.editor_column)',
        '"Library..."',
        '"Add Custom Snippet..."',
        '"Import Snippets..."',
        '"Export Snippets..."',
        '("left", "Left Sidebar")',
        '("right", "Right Sidebar")',
        '("disabled", "Floating Only")',
        'self.runtime_paths.package_root / "docs" / "README.md"',
        '/ "sheepy-pad" / "README.md"',
    )
    for fragment in required_app_fragments:
        if fragment not in app_source:
            fail(f"required Sheepy Pad application fragment missing: {fragment}")

    for obsolete_shortcut in (
        'QKeySequence("Ctrl+Shift+L")',
        'QKeySequence("Ctrl+Shift+R")',
        'QKeySequence("Ctrl+Alt+Shift+T")',
        'QKeySequence("Ctrl+Shift+T")',
        'QKeySequence("Ctrl+Alt+O")',
        'QKeySequence("Ctrl+Delete")',
        'QKeySequence("Alt+Enter")',
        'QKeySequence("Ctrl+Alt+E")',
        'QKeySequence("Ctrl+Alt+R")',
        'QKeySequence("Ctrl+Alt+D")',
        'QKeySequence("Ctrl+Alt+F")',
    ):
        if obsolete_shortcut in app_source:
            fail(f"obsolete file shortcut remains: {obsolete_shortcut}")

    for removed in (
        "PyQt6.QtPrintSupport",
        "QPrinter",
        "QPrintDialog",
        "QPageSetupDialog",
        '"Print..."',
        '"Page Setup..."',
    ):
        if removed in app_source:
            fail(f"removed printing feature remains: {removed}")

    for fragment in (
        'source_package_root = launcher_root / "sheepy_pad"',
        '/ "sheepy-pad"',
        'return self.config_root / "sheepy-pad.json"',
        'base / "pytshpad" / "pytshpad.json"',
        'base / "pythushy" / "pythushy.json"',
        'base / "pythy" / "pythy.json"',
        'return self.resource_root / "icons" / "sheepy-pad.png"',
    ):
        if fragment not in paths_source:
            fail(f"runtime path fragment missing: {fragment}")

    for fragment in (
        'PYTHON_OVERRIDE_VARIABLE = "SHEEPY_PAD_PYTHON"',
        'SHELL_OVERRIDE_VARIABLE = "SHEEPY_PAD_SHELL"',
        'EDITOR_OVERRIDE_VARIABLE = "SHEEPY_PAD_EDITOR"',
        '"SHEEPY_PAD_APPIMAGE_THEME"',
        'def resolve_interpreter(',
        'def detected_shebang(',
        'extra_arguments: tuple[str, ...] = ()',
        'environment: dict[str, str] | None = None',
        'signal.signal(signal.SIGHUP, forward)',
    ):
        if fragment not in launcher_source:
            fail(f"launcher identity fragment missing: {fragment}")

    if '"light": {' not in editor_source or '"dark": {' not in editor_source:
        fail("editor does not include both light and dark colour schemes")
    if "class FishHighlighter" not in editor_source or '"fish": FishHighlighter' not in editor_source:
        fail("dedicated Fish syntax highlighter is missing")
    for fragment in (
        "self.setCenterOnScroll(False)",
        "def _resize_gutter_above_horizontal_scrollbar(self) -> None:",
        "horizontal = self.horizontalScrollBar()",
        "gutter_height = max(0, gutter_height - horizontal.height())",
        "self.centerCursor()",
    ):
        if fragment not in editor_source:
            fail(f"0.4.2 editor scrolling/gutter corrective missing: {fragment}")
    if "self.setCenterOnScroll(True)" in editor_source:
        fail("legacy global center-on-scroll remains enabled")
    for colour in ("#ffffff", "#202124", "#7b2f91", "#a31515", "#2e7d32"):
        if colour not in editor_source.lower():
            fail(f"light editor contrast colour missing: {colour}")

    script_runtime_source = (PROGRAM_ROOT / "script_runtime.py").read_text(encoding="utf-8")
    for fragment in (
        'frozenset({".py", ".pyw"})',
        'frozenset({".sh", ".bash", ".zsh"})',
        'frozenset({".fish"})',
        'def parse_argument_string(',
        'def parse_environment_lines(',
        'return "fish"',
    ):
        if fragment not in script_runtime_source:
            fail(f"runnable-script feature fragment missing: {fragment}")

    library_source = (PROGRAM_ROOT / "script_library.py").read_text(encoding="utf-8")
    for fragment in (
        'SUPPORTED_LIBRARY_SUFFIXES = (".py", ".pyw", ".sh", ".bash", ".zsh", ".fish")',
        '"Favourites"',
        '"All"',
        '"Flow"',
        '"Arguments"',
        '"Environment"',
        '"Files"',
        '"Processes"',
        '"Custom"',
        "'py-main-guard'",
        "'shell-function'",
        "'fish-function'",
        "'py-subprocess-capture'",
        "'bash-strict'",
        "'zsh-strict'",
        "'fish-command-q'",
        'EXTRA_ENTRIES: tuple[LibraryEntry, ...]',
        'def custom_entries_from_preferences(',
        'def normalise_favourites(',
        'def matching_entries(',
        'def render_entry(',
        '"Syntax/Lint:',
    ):
        if fragment not in library_source and fragment not in app_source:
            fail(f"script Library fragment missing: {fragment}")

    for removed in (
        '"Templates"',
        '"From Template..."',
        '"New from Template..."',
        'show_template_library',
        'kind == "template"',
        'self.document_type_button = QToolButton',
        'self.app_menu_bar.addMenu("&Library")',
        '("Library", self.library_menu)',
    ):
        if removed in app_source or removed in library_source:
            fail(f"removed template/UI fragment remains: {removed}")

    panel_start = app_source.index("class ScriptLibraryPanel(QWidget):")
    panel_end = app_source.index("class ScriptLibraryDialog(QDialog):", panel_start)
    panel_source = app_source[panel_start:panel_end]
    if "self.type_combo" in panel_source:
        fail("Library panel must follow document type rather than display a separate Type selector")
    if 'setPlaceholderText("Search Script Library")' not in panel_source:
        fail("Library panel does not use the family-aligned search presentation")
    for fragment in (
        'self.category_combo.addItems(LIBRARY_CATEGORIES)',
        'self.close_button.setText("×")',
        'self.tabs = QTabWidget(self)',
    ):
        if fragment not in panel_source:
            fail(f"Library compact/floating presentation fragment missing: {fragment}")
    for removed in ('"Open Script..."', '"Open Library..."'):
        if removed in app_source:
            fail(f"superseded Start a Document control remains: {removed}")

    file_start = app_source.index("    def _make_file_menu(self) -> None:")
    file_end = app_source.index("    def _make_edit_menu(self) -> None:", file_start)
    file_menu_source = app_source[file_start:file_end]
    if not (
        file_menu_source.index('"New Type..."')
        < file_menu_source.index('"Default New Document..."')
        < file_menu_source.index('"Open..."')
        < file_menu_source.index('addMenu("Document Type")')
    ):
        fail("File creation/type actions are not in the Timblee/JSTS family order")

    run_start = app_source.index("    def _make_run_menu(self) -> None:")
    run_end = app_source.index("    def _populate_library_menu(self) -> None:", run_start)
    run_menu_source = app_source[run_start:run_end]
    if not (
        run_menu_source.index('"Environment Profiles..."')
        < run_menu_source.index('addMenu("Library")')
        < run_menu_source.index('"Stop"')
    ):
        fail("Run Library submenu is not directly after Environment Profiles and before Stop section")

    layout_start = app_source.index("    def _apply_layout_mode(self) -> None:")
    layout_end = app_source.index("    def set_drop_open_mode", layout_start)
    layout_source = app_source[layout_start:layout_end]
    for fragment in (
        'self.editor_column_layout.addWidget(self.bottom_search)',
        'self.editor_column_layout.addWidget(self.workspace_stack, 1)',
        'self.main_layout.addWidget(self.editor_workspace, 1)',
    ):
        if fragment not in layout_source:
            fail(f"split Library/Find geometry fragment missing: {fragment}")
    if 'self.main_layout.addWidget(self.bottom_search)' in layout_source:
        fail("split Find bar must stay inside the editor column, not span below the Library sidebar")

    view_start = app_source.index("    def _make_view_menu(self) -> None:")
    view_end = app_source.index("    def _make_run_menu(self) -> None:", view_start)
    view_menu_source = app_source[view_start:view_end]
    if view_menu_source.index('addMenu("Library")') > view_menu_source.index('addMenu("Layout")'):
        fail("View Library must appear above Layout")

    # Official approved Sheepy Pad logo and derived sizes.
    icon_root = PROGRAM_ROOT / "assets" / "icons"
    master = icon_root / "sheepy-pad-master.png"
    if sha256(master) != OFFICIAL_MASTER_SHA256:
        fail("official Sheepy Pad master icon changed")
    if png_dimensions(master) != (1024, 1024):
        fail("official Sheepy Pad master icon dimensions changed")
    for size in ICON_SIZES:
        icon = icon_root / f"sheepy-pad-{size}.png"
        if not icon.is_file() or png_dimensions(icon) != (size, size):
            fail(f"missing or invalid Sheepy Pad {size}px icon")
    if (icon_root / "sheepy-pad.png").read_bytes() != (icon_root / "sheepy-pad-512.png").read_bytes():
        fail("main Sheepy Pad icon is not the 512px asset")
    if (PROGRAM_ROOT / "packaging" / "appimage" / "sheepy-pad.png").read_bytes() != (icon_root / "sheepy-pad-512.png").read_bytes():
        fail("AppImage root icon does not match the approved 512px asset")

    desktop_path = PROGRAM_ROOT / "packaging" / "appimage" / "sheepy-pad.desktop"
    desktop = desktop_path.read_text(encoding="utf-8")
    for fragment in (
        "Name=Sheepy Pad",
        "Exec=sheepy-pad %F",
        "Icon=sheepy-pad",
        "StartupWMClass=sheepy-pad",
        "Categories=Development;",
    ):
        if fragment not in desktop:
            fail(f"desktop metadata fragment missing: {fragment}")
    categories = next((line for line in desktop.splitlines() if line.startswith("Categories=")), "")
    if categories.count(";") != 1:
        fail("desktop entry must declare exactly one main category")

    metainfo_path = PROGRAM_ROOT / "packaging" / "appimage" / "io.github.brunonlinespace.sheepy-pad.metainfo.xml"
    try:
        ET.parse(metainfo_path)
    except ET.ParseError as exc:
        fail(f"invalid AppStream XML: {exc}")
    metainfo = metainfo_path.read_text(encoding="utf-8")
    for fragment in (
        "<id>io.github.brunonlinespace.sheepy-pad</id>",
        "<name>Sheepy Pad</name>",
        "https://github.com/brunonlinespace/sheepy-pad",
        "<binary>sheepy-pad</binary>",
    ):
        if fragment not in metainfo:
            fail(f"AppStream identity fragment missing: {fragment}")

    apprun = (PROGRAM_ROOT / "packaging" / "appimage" / "AppRun").read_text(encoding="utf-8")
    for fragment in (
        'BUNDLE="$APPDIR/usr/lib/sheepy-pad"',
        'EXECUTABLE="$BUNDLE/sheepy-pad"',
        'export SHEEPY_PAD_APPIMAGE_THEME="dark"',
        'export SHEEPY_PAD_APPIMAGE_THEME="light"',
        'export SHEEPY_PAD_APPIMAGE_THEME="system"',
    ):
        if fragment not in apprun:
            fail(f"AppRun fragment missing: {fragment}")

    build_script = (PROGRAM_ROOT / "packaging" / "fedora" / "build-appimage.sh").read_text(encoding="utf-8")
    for fragment in (
        'umask 022',
        'APP_NAME="Sheepy Pad"',
        'APP_ID="sheepy-pad"',
        'APP_VERSION="0.4.2"',
        'PROGRAM_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd -P)"',
        'PROJECT_ROOT="$(cd -- "${PROGRAM_ROOT}/.." && pwd -P)"',
        'APPIMAGE="${DIST_DIR}/Sheepy-Pad-${APP_VERSION}-${ARCH}.AppImage"',
        'x86_64) HOST_ARCH="x86_64"',
        'aarch64|arm64) HOST_ARCH="aarch64"',
        'SHEEPY_PAD_ALLOW_UNSUPPORTED_HOST',
        'SHEEPY_PAD_RELEASE_BUILD',
        'check_non_privileged_policy()',
        'check_host_prerequisites()',
        'clean_source_python_caches()',
        'COMPONENT_MANIFEST="${PROJECT_ROOT}/suite-pythoine-component.json"',
        'PROJECT_MANIFEST="${PROGRAM_ROOT}/sheepy-pad.json"',
        'BUILD_REQUIREMENTS="${PROGRAM_ROOT}/packaging/pyinstaller/build-requirements.txt"',
        'validate_build_root()',
        'BUILD_ROOT must be a child directory beneath',
        'Unsafe BUILD_ROOT outside',
        'SOURCE_MANIFEST="${PROGRAM_ROOT}/SOURCE_MANIFEST.sha256"',
        'PUBLIC_README="${PROJECT_ROOT}/README.md"',
        '"$PUBLIC_README"',
        'README.md SHA-256:',
        '"$FINAL_APPDIR/usr/share/doc/sheepy-pad/PUBLIC-README.md"',
        'STATIC_QA="${PROGRAM_ROOT}/qa/static-qa.sh"',
        'bash "$STATIC_QA"',
        'PYTHONPYCACHEPREFIX="${BUILD_ROOT}/pycache"',
        '-m compileall -q',
        '"$VENV/bin/python" -m pip check',
        'validate_desktop_entry_basic()',
        'validate_appstream_basic()',
        'run_gui_smoke_test()',
        'run_version_smoke_test()',
        'run_theme_smoke_matrix()',
        'run_portapad_theme_version_checks()',
        '--sheepy-pad-smoke-test',
        'QT_QPA_PLATFORM=offscreen',
        'remove_unwanted_qt_payload()',
        'remove_unwanted_qt_payload "$FINAL_APPDIR/usr/lib/sheepy-pad"',
        'Qt PDF libraries were bundled unexpectedly',
        'Qt Print Support was bundled unexpectedly',
        'Qt WebEngine was bundled unexpectedly',
        'CACHE_DIR="${XDG_CACHE_HOME:-${HOME}/.cache}/sheepy-pad-appimage-tools"',
        'releases/download/continuous/appimagetool-${ARCH}.AppImage',
        'APPIMAGETOOL_PATH',
        'APPIMAGETOOL_SHA256',
        'APPIMAGETOOL_SHA256 must be 64 hexadecimal characters',
        '--max-time 300',
        'local part="${destination}.part"',
        'MAX_TOOL_BYTES=$((200 * 1024 * 1024))',
        '"7f454c46"',
        'sha256sum --check --status',
        'Fedora release:',
        'Privilege policy: non-privileged; no sudo/dnf/su/pkexec',
        'main.py SHA-256:',
        'SOURCE_MANIFEST.sha256 SHA-256:',
        'Suite component manifest SHA-256:',
        'Project manifest SHA-256:',
        'Runtime requirements SHA-256:',
        'Builder SHA-256:',
        'Source tree SHA-256:',
        'appimagetool SHA-256:',
        'Smoke tests: AppDir GUI PASS + Portapad-aligned version PASS (system/dark/light); final AppImage GUI PASS + Portapad-aligned version PASS (system/dark/light)',
        'Source cleanliness: __pycache__/pyc/pyo removed before QA/build and at exit',
        '"$PYINSTALLER_SPEC"',
    ):
        if fragment not in build_script:
            fail(f"portable AppImage build fragment missing: {fragment}")
    output_line = next((line for line in build_script.splitlines() if 'APPIMAGE="${DIST_DIR}/' in line), "")
    if "Fedora" in output_line:
        fail("AppImage filename is contaminated by host OS metadata")
    for forbidden_command in ("sudo", "dnf", "pkexec", "su"):
        for line in build_script.splitlines():
            stripped = line.lstrip()
            if stripped.startswith(forbidden_command + " "):
                fail(f"AppImage builder contains forbidden privileged command: {forbidden_command}")

    build_requirements = PROGRAM_ROOT / "packaging" / "pyinstaller" / "build-requirements.txt"
    if not build_requirements.is_file():
        fail("canonical PyInstaller build requirements are missing")
    if (PROGRAM_ROOT / "packaging" / "fedora" / "requirements-build.txt").exists():
        fail("legacy Fedora-local requirements-build.txt must not remain")

    spec = (PROGRAM_ROOT / "packaging" / "pyinstaller" / "sheepy-pad.spec").read_text(encoding="utf-8")
    for fragment in (
        'collect_submodules("sheepy_pad")',
        'source_root / "main.py"',
        '"sheepy_pad/assets"',
        '"sheepy_pad/docs"',
        'name="sheepy-pad"',
        '"PyQt6.QtPdf"',
        '"PyQt6.QtPdfWidgets"',
        '"PyQt6.QtPrintSupport"',
        '"PyQt6.QtWebEngineCore"',
        'forbidden_qt_payload_tokens',
        'a.binaries = [entry for entry in a.binaries if not is_forbidden_qt_payload(entry)]',
        'a.datas = [entry for entry in a.datas if not is_forbidden_qt_payload(entry)]',
    ):
        if fragment not in spec:
            fail(f"PyInstaller fragment missing: {fragment}")

    portable = (PROGRAM_ROOT / "portable" / "run-sheepy-pad.sh").read_text(encoding="utf-8")
    for fragment in (
        'PROGRAM_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"',
        'SOURCE_ROOT="$(CDPATH= cd -- "$PROGRAM_ROOT/.." && pwd)"',
        'SHEEPY_PAD_PORTABLE_PYTHON',
        '"$SOURCE_ROOT/main.py"',
    ):
        if fragment not in portable:
            fail(f"portable launcher fragment missing: {fragment}")

    static_qa = (PROGRAM_ROOT / "qa" / "static-qa.sh").read_text(encoding="utf-8")
    for fragment in (
        'python3 "$PROGRAM_ROOT/tools/release_check.py"',
        'python3 -m unittest discover -s sheepy_pad/tests -v',
        'bash -n "$script"',
    ):
        if fragment not in static_qa:
            fail(f"static QA wrapper fragment missing: {fragment}")

    docs = PROGRAM_ROOT / "docs"
    for name in (
        "README.md",
        "RELEASE_NOTES.md",
        "QA.md",
        "BUILDING.md",
        "APPIMAGE_THEMES.md",
        "SECURITY_AUDIT.md",
        "ASSET_NOTES.md",
    ):
        if not (docs / name).is_file():
            fail(f"documentation file missing: {name}")

    manifest_path = PROGRAM_ROOT / "SOURCE_MANIFEST.sha256"
    manifest_entries: dict[str, str] = {}
    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            digest, relative = raw_line.split("  ./", 1)
        except ValueError:
            fail("invalid SOURCE_MANIFEST.sha256 line")
        if len(digest) != 64 or not relative or relative.startswith("/") or ".." in Path(relative).parts:
            fail("unsafe or invalid source-manifest entry")
        manifest_entries[relative] = digest

    expected_files: set[str] = set()
    for path in SOURCE_ROOT.rglob("*"):
        if not path.is_file() or path == manifest_path:
            continue
        relative_path = path.relative_to(SOURCE_ROOT)
        if any(part in IGNORED_GENERATED_DIRS for part in relative_path.parts):
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        expected_files.add(relative_path.as_posix())
    if set(manifest_entries) != expected_files:
        missing = sorted(expected_files - set(manifest_entries))
        stale = sorted(set(manifest_entries) - expected_files)
        fail(f"source manifest file set mismatch; missing={missing[:1]}, stale={stale[:1]}")
    for relative, expected_digest in manifest_entries.items():
        if sha256(SOURCE_ROOT / relative) != expected_digest:
            fail(f"source manifest checksum mismatch: {relative}")

    print("Sheepy Pad 0.4.2 release checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
