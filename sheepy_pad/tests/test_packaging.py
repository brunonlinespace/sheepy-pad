#!/usr/bin/env python3
"""Static regressions for Sheepy Pad packaging and removed optional features."""

from __future__ import annotations

import ast
import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPROVED_README_NORMALIZED_SHA256 = "1fab15bb80a228c7feb01144932b418838be4a0b2123bb3229f0590dfa048976"


class PackagingRegressionTests(unittest.TestCase):
    def test_approved_public_readme_at_source_root_is_version_only(self) -> None:
        readme_path = ROOT.parent / "README.md"
        self.assertTrue(readme_path.is_file())
        readme_bytes = readme_path.read_bytes()
        self.assertIn(b"0.4.2", readme_bytes)
        normalized = readme_bytes.replace(b"0.4.2", b"@VERSION@")
        self.assertEqual(
            hashlib.sha256(normalized).hexdigest(),
            APPROVED_README_NORMALIZED_SHA256,
            "The locked GitHub README changed beyond release version numbers",
        )

    def test_public_readme_appimage_packaging_contract(self) -> None:
        script = (ROOT / "packaging" / "fedora" / "build-appimage.sh").read_text(encoding="utf-8")
        self.assertIn('PUBLIC_README="${PROJECT_ROOT}/README.md"', script)
        self.assertIn('"$SOURCE_ENTRY" "$PUBLIC_README" "$COMPONENT_MANIFEST"', script)
        self.assertIn('install -m 0644 "$PUBLIC_README" "$FINAL_APPDIR/usr/share/doc/sheepy-pad/PUBLIC-README.md"', script)
        self.assertIn('install -m 0644 "${DOCS_DIR}/README.md" "$FINAL_APPDIR/usr/share/doc/sheepy-pad/README.md"', script)
        self.assertIn('README.md SHA-256:', script)

    def test_appimage_filename_uses_application_version(self) -> None:
        script = (ROOT / "packaging" / "fedora" / "build-appimage.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('APP_VERSION="0.4.2"', script)
        self.assertIn(
            'APPIMAGE="${DIST_DIR}/Sheepy-Pad-${APP_VERSION}-${ARCH}.AppImage"',
            script,
        )
        self.assertIn('ARCH="$ARCH" VERSION="$APP_VERSION"', script)
        self.assertNotIn(
            'APPIMAGE="${DIST_DIR}/Sheepy-Pad-${VERSION}-${ARCH}.AppImage"',
            script,
        )

    def test_appimage_builder_matches_suite_hardened_generation(self) -> None:
        script = (ROOT / "packaging" / "fedora" / "build-appimage.sh").read_text(
            encoding="utf-8"
        )
        for fragment in (
            'umask 022',
            'APP_NAME="Sheepy Pad"',
            'APP_ID="sheepy-pad"',
            'APP_VERSION="0.4.2"',
            'DESKTOP_ID="io.github.brunonlinespace.sheepy-pad"',
            'PUBLISHER_ID="brunonlinespace"',
            'COMPONENT_MANIFEST="${PROJECT_ROOT}/suite-pythoine-component.json"',
            'PROJECT_MANIFEST="${PROGRAM_ROOT}/sheepy-pad.json"',
            'BUILD_REQUIREMENTS="${PROGRAM_ROOT}/packaging/pyinstaller/build-requirements.txt"',
            'validate_build_root()',
            'SOURCE_MANIFEST="${PROGRAM_ROOT}/SOURCE_MANIFEST.sha256"',
            'STATIC_QA="${PROGRAM_ROOT}/qa/static-qa.sh"',
            'x86_64) HOST_ARCH="x86_64"',
            'aarch64|arm64) HOST_ARCH="aarch64"',
            'SHEEPY_PAD_ALLOW_UNSUPPORTED_HOST',
            'SHEEPY_PAD_RELEASE_BUILD',
            'check_non_privileged_policy()',
            'check_host_prerequisites()',
            'validate_desktop_entry_basic()',
            'validate_appstream_basic()',
            'run_gui_smoke_test()',
            'run_version_smoke_test()',
            'run_theme_smoke_matrix()',
            'run_portapad_theme_version_checks()',
            '--sheepy-pad-smoke-test',
            'QT_QPA_PLATFORM=offscreen',
            'PYTHONPYCACHEPREFIX="${BUILD_ROOT}/pycache"',
            ' -m compileall -q \\',
            'Qt PDF libraries were bundled unexpectedly',
            'Qt Print Support was bundled unexpectedly',
            'Qt WebEngine was bundled unexpectedly',
            'CACHE_DIR="${XDG_CACHE_HOME:-${HOME}/.cache}/sheepy-pad-appimage-tools"',
            'releases/download/continuous/appimagetool-${ARCH}.AppImage',
            'APPIMAGETOOL_PATH',
            'APPIMAGETOOL_SHA256',
            'APPIMAGETOOL_SHA256 must be 64 hexadecimal characters',
            "curl --proto '=https' --tlsv1.2",
            '--max-time 300',
            'local part="${destination}.part"',
            'MAX_TOOL_BYTES=$((200 * 1024 * 1024))',
            '"7f454c46"',
            'sha256sum --check --status',
            '"$VENV/bin/python" -m pip check',
            'main.py SHA-256:',
            'SOURCE_MANIFEST.sha256 SHA-256:',
            'Suite component manifest SHA-256:',
            'Project manifest SHA-256:',
            'Runtime requirements SHA-256:',
            'Builder SHA-256:',
            'Source tree SHA-256:',
            'appimagetool SHA-256:',
            'Source cleanliness: __pycache__/pyc/pyo removed before QA/build and at exit',
        ):
            self.assertIn(fragment, script)
        self.assertNotIn(
            'releases/latest/download/appimagetool-${ARCH}.AppImage', script
        )

    def test_appimage_builder_preserves_sheepy_specific_packaging_rules(self) -> None:
        script = (ROOT / "packaging" / "fedora" / "build-appimage.sh").read_text(
            encoding="utf-8"
        )
        for fragment in (
            'clean_source_python_caches()',
            'bash "$STATIC_QA"',
            'run_theme_smoke_matrix "AppDir"',
            'run_portapad_theme_version_checks "$label"',
            'run_theme_smoke_matrix "final AppImage"',
            'OUTPUT_DIR:-${PROGRAM_ROOT}/dist',
            'Sheepy-Pad-${APP_VERSION}-${ARCH}.AppImage',
            'text/x-python',
            'application/x-shellscript',
            'for size in 16 24 32 48 64 128 256 512',
            'remove_unwanted_qt_payload()',
            'remove_unwanted_qt_payload "$FINAL_APPDIR/usr/lib/sheepy-pad"',
            "-iname '*Qt6Pdf*'",
            "-iname '*Qt6PrintSupport*'",
            "-iname '*Qt6WebEngine*'",
        ):
            self.assertIn(fragment, script)


    def test_pyinstaller_explicitly_excludes_and_filters_unused_qt_stacks(self) -> None:
        spec = (ROOT / "packaging" / "pyinstaller" / "sheepy-pad.spec").read_text(encoding="utf-8")
        for fragment in (
            '"PyQt6.QtPdf"',
            '"PyQt6.QtPdfWidgets"',
            '"PyQt6.QtPrintSupport"',
            '"PyQt6.QtWebEngineCore"',
            '"PyQt6.QtWebEngineQuick"',
            '"PyQt6.QtWebEngineWidgets"',
            'forbidden_qt_payload_tokens',
            'a.binaries = [entry for entry in a.binaries if not is_forbidden_qt_payload(entry)]',
            'a.datas = [entry for entry in a.datas if not is_forbidden_qt_payload(entry)]',
        ):
            self.assertIn(fragment, spec)

    def test_suite_style_identity_manifest_and_gui_smoke_hook_are_present(self) -> None:
        import json
        manifest = json.loads((ROOT / "sheepy-pad.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "Sheepy Pad")
        self.assertEqual(manifest["id"], "sheepy-pad")
        self.assertEqual(manifest["version"], "0.4.2")
        self.assertEqual(manifest["publisher_id"], "brunonlinespace")
        self.assertEqual(manifest["desktop_id"], "io.github.brunonlinespace.sheepy-pad")
        self.assertEqual(manifest["tagline"], "Friendly. Fast. Focused.")
        component = json.loads((ROOT.parent / "suite-pythoine-component.json").read_text(encoding="utf-8"))
        self.assertEqual(component["id"], "sheepy-pad")
        self.assertEqual(component["component_kind"], "editor")
        self.assertEqual(component["version"], "0.4.2")
        self.assertEqual(component["extensions"], [".py", ".sh"])
        self.assertEqual(component["portable_command"], ["main.py"])
        self.assertEqual(component["tagline"], "Friendly. Fast. Focused.")
        self.assertEqual(component["capabilities"], {"routing": True, "open": True, "create": True})
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('"--sheepy-pad-smoke-test"', app_source)
        self.assertIn('print("GUI smoke test passed.", flush=True)', app_source)
        static_qa = (ROOT / "qa" / "static-qa.sh").read_text(encoding="utf-8")
        self.assertIn('python3 "$PROGRAM_ROOT/tools/release_check.py"', static_qa)
        self.assertIn('python3 -m unittest discover -s sheepy_pad/tests -v', static_qa)

    def test_printing_stack_is_absent(self) -> None:
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        for fragment in (
            "PyQt6.QtPrintSupport",
            "QPrinter",
            "QPrintDialog",
            "QPageSetupDialog",
            '"Print..."',
            '"Page Setup..."',
        ):
            self.assertNotIn(fragment, app_source)

    def test_light_editor_palette_is_complete(self) -> None:
        editor_source = (ROOT / "code_editor.py").read_text(
            encoding="utf-8"
        )
        for fragment in (
            '"light": {',
            '"background": "#ffffff"',
            '"foreground": "#202124"',
            '"keyword": "#7b2f91"',
            '"string": "#a31515"',
            '"comment": "#2e7d32"',
            "def set_color_scheme(self, color_scheme: str)",
        ):
            self.assertIn(fragment, editor_source)

    def test_light_editor_syntax_colours_meet_contrast_floor(self) -> None:
        editor_source = (ROOT / "code_editor.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(editor_source)
        schemes = None
        for node in tree.body:
            if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "EDITOR_COLOR_SCHEMES":
                schemes = ast.literal_eval(node.value)
                break
        self.assertIsNotNone(schemes)
        light = schemes["light"]

        def luminance(colour: str) -> float:
            channels = [int(colour[index:index + 2], 16) / 255 for index in (1, 3, 5)]
            linear = [
                value / 12.92
                if value <= 0.04045
                else ((value + 0.055) / 1.055) ** 2.4
                for value in channels
            ]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        background = luminance(light["background"])
        for role in (
            "foreground",
            "keyword",
            "builtin",
            "number",
            "string",
            "comment",
            "definition",
            "self",
            "shebang",
        ):
            foreground = luminance(light[role])
            lighter, darker = max(background, foreground), min(background, foreground)
            contrast = (lighter + 0.05) / (darker + 0.05)
            self.assertGreaterEqual(contrast, 4.5, role)

    def test_go_to_line_uses_validated_plain_text_field(self) -> None:
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        start = app_source.index("    def go_to_line(self) -> None:")
        end = app_source.index("    # ------------------------------------------------------------------\n    # Script actions", start)
        implementation = app_source[start:end]
        self.assertIn("QLineEdit(dialog)", implementation)
        self.assertIn("QIntValidator(1, maximum, line_input)", implementation)
        self.assertNotIn("QSpinBox", implementation)
        self.assertNotIn("QInputDialog.getInt", implementation)

    def test_runnable_scope_and_run_tools_are_present(self) -> None:
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        runtime_source = (ROOT / "script_runtime.py").read_text(encoding="utf-8")
        editor_source = (ROOT / "code_editor.py").read_text(encoding="utf-8")
        for suffix in (".py", ".pyw", ".sh", ".bash", ".zsh", ".fish"):
            self.assertIn(f'"{suffix}"', runtime_source)
        for fragment in (
            '"Run with Arguments..."',
            'QKeySequence("Ctrl+1")',
            'QKeySequence("Ctrl+Shift+1")',
            'QKeySequence("Ctrl+2")',
            'QKeySequence("Ctrl+3")',
            '"Syntax / Lint Check"',
            '"Select Interpreter..."',
            '"Working Directory..."',
            '"Environment Profiles..."',
            '"Exec: Yes"',
        ):
            self.assertIn(fragment, app_source)
        self.assertIn("class FishHighlighter", editor_source)
        self.assertIn('"fish": FishHighlighter', editor_source)

    def test_non_runnable_config_formats_are_not_supported(self) -> None:
        runtime_source = (ROOT / "script_runtime.py").read_text(encoding="utf-8")
        scope_start = runtime_source.index("PYTHON_SUFFIXES")
        scope_end = runtime_source.index("SCRIPT_FILE_FILTER")
        scope = runtime_source[scope_start:scope_end]
        for suffix in (".toml", ".ini", ".env"):
            self.assertNotIn(suffix, scope)

    def test_toolbar_swaps_launch_controls_for_stop_controls_while_running(self) -> None:
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        for fragment in (
            'self.stop_button = self._action_button("Stop", self.stop_script)',
            '"Force Stop", self.force_stop_script',
            'self.launch_button.setVisible(not running)',
            'self.terminal_button.setVisible(not running)',
            'self.admin_button.setVisible(not running)',
            'self.stop_button.setVisible(running)',
            'self.force_stop_button.setVisible(running)',
        ):
            self.assertIn(fragment, app_source)

    def test_terminal_supervision_recovers_when_terminal_window_closes(self) -> None:
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        launcher_source = (ROOT / "runtime_launcher.py").read_text(encoding="utf-8")
        for fragment in (
            'child_alive and wrapper_alive',
            'if not child_alive:',
            'os.killpg(child_pgid, signal.SIGTERM)',
            '"Terminal closed; script stopped."',
        ):
            self.assertIn(fragment, app_source)
        self.assertIn('signal.signal(signal.SIGHUP, forward)', launcher_source)



    def test_r7_library_toggle_stars_and_shortcuts(self) -> None:
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        for fragment in (
            'QListWidgetItem(f"★ {entry.label}" if favourite else entry.label)',
            'self._library_sidebar_shortcut_hidden = False',
            'def toggle_library_shortcut(self) -> None:',
            'self.library_position == "disabled"',
            'self.library_dialog.isVisible()',
            'def set_library_sidebar_hidden(self, hidden: bool) -> None:',
            'self._library_sidebar_shortcut_hidden = bool(hidden)',
            'self.set_library_sidebar_hidden(not self._library_sidebar_shortcut_hidden)',
            'lambda: self.window.set_library_sidebar_hidden(True)',
            'QKeySequence("Ctrl+L")',
            'QKeySequence("Ctrl+Shift+E")',
            'QKeySequence("F2")',
            'QKeySequence("Ctrl+Shift+D")',
            'QKeySequence("Ctrl+Shift+O")',
            'QKeySequence("Ctrl+3")',
            'QKeySequence("Ctrl+4")',
            'QKeySequence("Ctrl+5")',
            'QKeySequence("Ctrl+6")',
            'QKeySequence("Ctrl+2")',
            'QKeySequence("Ctrl+Shift+1")',
            'QKeySequence("Ctrl+1")',
        ):
            self.assertIn(fragment, app_source)
        self.assertNotIn('QKeySequence("Ctrl+Delete")', app_source)
        self.assertNotIn('QKeySequence("Alt+Enter")', app_source)
        for obsolete in (
            'QKeySequence("Ctrl+Shift+L")',
            'QKeySequence("Ctrl+Shift+R")',
            'QKeySequence("Ctrl+Alt+Shift+T")',
            'QKeySequence("Ctrl+Shift+T")',
            'QKeySequence("Ctrl+Alt+O")',
            'QKeySequence("Ctrl+Alt+E")',
            'QKeySequence("Ctrl+Alt+R")',
            'QKeySequence("Ctrl+Alt+D")',
            'QKeySequence("Ctrl+Alt+F")',
        ):
            self.assertNotIn(obsolete, app_source)

        apply_library_start = app_source.index("    def _apply_library_position(self) -> None:")
        apply_library_end = app_source.index("    def set_library_position", apply_library_start)
        apply_library_source = app_source[apply_library_start:apply_library_end]
        self.assertIn('or self._library_sidebar_shortcut_hidden', apply_library_source)
        self.assertIn('or not self.document_active', apply_library_source)
        self.assertNotIn('set_library_position("disabled")', app_source)

    def test_r5_sidebar_management_buttons_are_floating_only(self) -> None:
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        panel_start = app_source.index("class ScriptLibraryPanel(QWidget):")
        panel_end = app_source.index("class ScriptLibraryDialog(QDialog):", panel_start)
        panel_source = app_source[panel_start:panel_end]
        for fragment in (
            "self.add_custom_button: QPushButton | None = None",
            "self.remove_custom_button: QPushButton | None = None",
            "self.import_button: QPushButton | None = None",
            "self.export_button: QPushButton | None = None",
            "if not self.compact:",
            'self.add_custom_button = QPushButton("Add Custom Snippet...", self)',
            'self.remove_custom_button = QPushButton("Remove Custom", self)',
            'self.import_button = QPushButton("Import Snippets...", self)',
            'self.export_button = QPushButton("Export Snippets...", self)',
        ):
            self.assertIn(fragment, panel_source)
        # Sidebar-only compact mode must never construct those four controls.
        controls_start = panel_source.index("self.add_custom_button: QPushButton | None = None")
        controls_end = panel_source.index("self.search_input.textChanged.connect", controls_start)
        controls_source = panel_source[controls_start:controls_end]
        self.assertIn("if not self.compact:", controls_source)

    def test_030_r2_library_start_layout_and_editor_palette_contract(self) -> None:
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        for fragment in (
            'self.workspace_stack = QStackedWidget(self)',
            'self.editor_column_layout = QVBoxLayout(self.editor_column)',
            '"Start a Document"',
            'host.setEnabled(self.document_active)',
            'self.view_only_action.setEnabled(self.document_active)',
            'self.dark_editor = True',
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
            'ScriptLibraryPanel(self, self, compact=True)',
            'ScriptLibraryPanel(window, self, compact=False)',
            'self.category_combo = QComboBox(self)',
            'self.close_button.setText("×")',
            'lambda: self.window.set_library_sidebar_hidden(True)',
            '"New Type..."',
            '"Default New Document..."',
            'self.document_type_menu = self.file_menu.addMenu("Document Type")',
            '"Use this type as my default"',
            '"Create Document"',
            '"Open Existing File..."',
            'self.favourites_menu = self.library_menu.addMenu("My Favourites")',
            '"Add Custom Snippet..."',
            '"Import Snippets..."',
            '"Export Snippets..."',
            '("left", "Left Sidebar")',
            '("right", "Right Sidebar")',
            '("disabled", "Floating Only")',
        ):
            self.assertIn(fragment, app_source)

        # The permanent document-type toolbar shortcut and top-level Library
        # menu/button are intentionally absent; File remains the type owner.
        self.assertNotIn('self.document_type_button = QToolButton', app_source)
        self.assertNotIn('self.app_menu_bar.addMenu("&Library")', app_source)
        self.assertNotIn('("Library", self.library_menu)', app_source)

        run_start = app_source.index('    def _make_run_menu(self) -> None:')
        run_end = app_source.index('    def _populate_library_menu(self) -> None:', run_start)
        run_menu = app_source[run_start:run_end]
        self.assertLess(run_menu.index('"Make Executable"'), run_menu.index('"Launch"'))
        self.assertLess(run_menu.index('"Environment Profiles..."'), run_menu.index('addMenu("Library")'))
        self.assertLess(run_menu.index('addMenu("Library")'), run_menu.index('"Stop"'))

        self.assertNotIn('"From Template..."', app_source)
        self.assertNotIn('"New from Template..."', app_source)
        self.assertNotIn('"Templates"', app_source)
        panel_start = app_source.index("class ScriptLibraryPanel(QWidget):")
        panel_end = app_source.index("class ScriptLibraryDialog(QDialog):", panel_start)
        panel_source = app_source[panel_start:panel_end]
        self.assertNotIn("self.type_combo", panel_source)
        self.assertIn('setPlaceholderText("Search Script Library")', panel_source)
        self.assertIn('if self.compact:', panel_source)
        self.assertIn('self.category_combo.addItems(LIBRARY_CATEGORIES)', panel_source)
        self.assertIn('self.tabs = QTabWidget(self)', panel_source)

        library_source = (ROOT / "script_library.py").read_text(encoding="utf-8")
        self.assertNotIn('"Templates"', library_source)
        self.assertLess(library_source.index('"Favourites"'), library_source.index('"All"'))

        file_start = app_source.index("    def _make_file_menu(self) -> None:")
        file_end = app_source.index("    def _make_edit_menu(self) -> None:", file_start)
        file_menu = app_source[file_start:file_end]
        self.assertLess(file_menu.index('"New Type..."'), file_menu.index('"Default New Document..."'))
        self.assertLess(file_menu.index('"Default New Document..."'), file_menu.index('"Open..."'))
        self.assertLess(file_menu.index('"Open..."'), file_menu.index('addMenu("Document Type")'))

        view_start = app_source.index("    def _make_view_menu(self) -> None:")
        view_end = app_source.index("    def _make_run_menu(self) -> None:", view_start)
        view_menu = app_source[view_start:view_end]
        self.assertLess(view_menu.index('addMenu("Library")'), view_menu.index('addMenu("Layout")'))

        layout_start = app_source.index("    def _apply_layout_mode(self) -> None:")
        layout_end = app_source.index("    def set_drop_open_mode", layout_start)
        layout_source = app_source[layout_start:layout_end]
        self.assertIn('self.editor_column_layout.addWidget(self.bottom_search)', layout_source)
        self.assertIn('self.editor_column_layout.addWidget(self.workspace_stack, 1)', layout_source)
        self.assertNotIn('self.main_layout.addWidget(self.bottom_search)', layout_source)
        self.assertIn('self.main_layout.addWidget(self.editor_workspace, 1)', layout_source)

        self.assertNotIn('"Open Script..."', app_source)
        self.assertNotIn('"Open Library..."', app_source)

        # A persisted Left/Right Library preference must not leak the sidebar
        # onto Start a Document. Document activation restores that preference.
        apply_library_start = app_source.index("    def _apply_library_position(self) -> None:")
        apply_library_end = app_source.index("    def set_library_position", apply_library_start)
        apply_library_source = app_source[apply_library_start:apply_library_end]
        self.assertIn('or not self.document_active', apply_library_source)
        self.assertIn('self.library_sidebar.hide()', apply_library_source)
        doc_state_start = app_source.index("    def _set_document_active(self, active: bool) -> None:")
        doc_state_end = app_source.index("    def _show_start_page", doc_state_start)
        doc_state_source = app_source[doc_state_start:doc_state_end]
        self.assertIn('self._apply_library_position()', doc_state_source)


if __name__ == "__main__":
    unittest.main()
