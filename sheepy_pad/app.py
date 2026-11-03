# Sheepy Pad
# Copyright (C) 2026 Bruno Machado
# SPDX-License-Identifier: GPL-3.0-or-later
"""Standalone lightweight editor for runnable Python, shell and Fish source files."""

from __future__ import annotations

import argparse
import bisect
import codecs
import html
import io
import json
import locale
import os
import re
import secrets
import signal
import subprocess
import stat
import sys
import tempfile
import time
import tokenize
from pathlib import Path
from uuid import uuid4

from PyQt6.QtCore import QProcess, QSize, QTimer, Qt
from PyQt6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QIntValidator,
    QKeySequence,
    QPainter,
    QPalette,
    QPixmap,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QComboBox,
    QFontDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStyle,
    QStyleFactory,
    QToolButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sheepy_pad import APP_NAME, APP_VERSION
from sheepy_pad.code_editor import CodeEditor
from sheepy_pad.file_io import (
    FileSnapshot,
    FileStateChangedError,
    FileTooLargeError,
    UnsupportedFileError,
    absolute_user_path,
    current_file_state,
    ensure_private_directory,
    fsync_directory,
    install_new_file_from_temp,
    path_identity_matches,
    path_lexists,
    read_regular_file,
    rename_path_no_replace,
    snapshot_from_payload,
    toggle_executable_permission,
    validated_symlink_target,
)
from sheepy_pad.runtime_launcher import RuntimeLauncher
from sheepy_pad.runtime_paths import RuntimePaths
from sheepy_pad.script_library import (
    LIBRARY_CATEGORIES,
    SUPPORTED_LIBRARY_SUFFIXES,
    LibraryEntry,
    custom_entries_from_preferences,
    default_library_category,
    entry_map,
    matching_entries,
    normalise_favourites,
    normalise_suffix,
    render_entry,
    serialise_custom_entries,
)
from sheepy_pad.script_runtime import (
    SCRIPT_FILE_FILTER,
    SUPPORTED_SCRIPT_SUFFIXES,
    file_type_label,
    format_environment_lines,
    normalise_environment_profiles,
    parse_argument_string,
    parse_environment_lines,
    source_language_for_path,
)

MAX_FILE_SIZE = 25 * 1024 * 1024
MAX_SEARCH_MATCHES = 10_000
MAX_SEARCH_QUERY_CHARACTERS = 4096
MAX_DOCUMENT_CHARACTERS = 25_000_000
MAX_CONFIG_SIZE = 1024 * 1024
GITHUB_URL = "https://github.com/brunonlinespace/sheepy-pad"
ISSUES_URL = f"{GITHUB_URL}/issues"
OPEN_WINDOWS: set["SheepyPadWindow"] = set()

DOCUMENT_TYPES: tuple[tuple[str, str], ...] = (
    ("Python", ".py"),
    ("Python Windowed", ".pyw"),
    ("Shell", ".sh"),
    ("Bash", ".bash"),
    ("Zsh", ".zsh"),
    ("Fish", ".fish"),
)
DOCUMENT_TYPE_LABEL = {suffix: label for label, suffix in DOCUMENT_TYPES}


def app_dialog_title(subject: str) -> str:
    """Return a Nuxpad-style title for application-owned dialogs."""
    return f"{subject} — {APP_NAME}"


def register_window(window: "SheepyPadWindow") -> None:
    OPEN_WINDOWS.add(window)
    window.destroyed.connect(
        lambda _object=None, registered=window: OPEN_WINDOWS.discard(registered)
    )



class ReplaceDialog(QDialog):
    """Modeless Nuxpad-style replace controls."""

    def __init__(self, window: "SheepyPadWindow") -> None:
        super().__init__(window)
        self.window = window
        self.setWindowTitle(app_dialog_title("Replace"))
        self.setModal(False)
        self.setMinimumWidth(430)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.find_input = QLineEdit(self)
        self.find_input.setMaxLength(MAX_SEARCH_QUERY_CHARACTERS)
        self.replace_input = QLineEdit(self)
        form.addRow("Find:", self.find_input)
        form.addRow("Replace with:", self.replace_input)
        layout.addLayout(form)

        self.match_case = QCheckBox("Match case", self)
        layout.addWidget(self.match_case)

        buttons = QHBoxLayout()
        find_next = QPushButton("Find Next", self)
        self.replace_button = QPushButton("Replace", self)
        self.replace_all_button = QPushButton("Replace All", self)
        close = QPushButton("Close", self)
        buttons.addWidget(find_next)
        buttons.addWidget(self.replace_button)
        buttons.addWidget(self.replace_all_button)
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        self.find_input.returnPressed.connect(self._find_next)
        find_next.clicked.connect(self._find_next)
        self.replace_button.clicked.connect(self._replace)
        self.replace_all_button.clicked.connect(self._replace_all)
        close.clicked.connect(self.close)
        self.find_input.textChanged.connect(self._sync_find_text)
        self.match_case.toggled.connect(self._sync_case)

    def prepare(self, query: str, match_case: bool) -> None:
        self.find_input.blockSignals(True)
        self.match_case.blockSignals(True)
        self.find_input.setText(query)
        self.match_case.setChecked(match_case)
        self.find_input.blockSignals(False)
        self.match_case.blockSignals(False)
        self.find_input.selectAll()
        self.find_input.setFocus()

    def set_view_only(self, enabled: bool) -> None:
        """Disable document-changing controls while preserving Find Next."""
        self.replace_button.setEnabled(not enabled)
        self.replace_all_button.setEnabled(not enabled)

    def _sync_find_text(self, text: str) -> None:
        self.window.set_search_query(text)

    def _sync_case(self, checked: bool) -> None:
        self.window.set_search_case_sensitive(checked)

    def _find_next(self) -> None:
        self.window.set_search_query(self.find_input.text())
        self.window.set_search_case_sensitive(self.match_case.isChecked())
        self.window.find_next()

    def _replace(self) -> None:
        self.window.set_search_query(self.find_input.text())
        self.window.set_search_case_sensitive(self.match_case.isChecked())
        self.window.replace_current(self.replace_input.text())

    def _replace_all(self) -> None:
        self.window.set_search_query(self.find_input.text())
        self.window.set_search_case_sensitive(self.match_case.isChecked())
        self.window.replace_all(self.replace_input.text())


class ScriptLibraryPanel(QWidget):
    """Searchable snippet Library shared by compact sidebar and floating dialog."""

    def __init__(
        self,
        window: "SheepyPadWindow",
        parent: QWidget | None = None,
        *,
        compact: bool = False,
    ) -> None:
        super().__init__(parent)
        self.window = window
        self.compact = bool(compact)
        self._lists: dict[str, QListWidget] = {}
        self._selected_key: str | None = None
        self._context_suffix = normalise_suffix(window.document_suffix)
        self.setMinimumWidth(250)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        if self.compact:
            # Timblee/Beespector compact-sidebar pattern: the embedded Library
            # uses a catalogue selector instead of consuming vertical space
            # with tabs, and exposes a small local close control.
            catalogue_row = QHBoxLayout()
            self.category_combo = QComboBox(self)
            self.category_combo.addItems(LIBRARY_CATEGORIES)
            self.category_combo.setToolTip("Library catalogue")
            catalogue_row.addWidget(self.category_combo, 1)
            self.close_button = QToolButton(self)
            self.close_button.setText("×")
            self.close_button.setToolTip("Close Library sidebar")
            self.close_button.setFixedSize(22, 22)
            self.close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.close_button.clicked.connect(
                lambda: self.window.set_library_sidebar_hidden(True)
            )
            catalogue_row.addWidget(self.close_button)
            layout.addLayout(catalogue_row)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search Script Library")
        self.search_input.setClearButtonEnabled(True)
        layout.addWidget(self.search_input)

        if self.compact:
            self.catalogue_list = QListWidget(self)
            self.catalogue_list.setAlternatingRowColors(True)
            self.catalogue_list.currentItemChanged.connect(self._selection_changed)
            self.catalogue_list.itemDoubleClicked.connect(
                lambda _item, self=self: self.activate_selected()
            )
            layout.addWidget(self.catalogue_list, 1)
            self.category_combo.currentIndexChanged.connect(self._category_changed)
        else:
            # The floating Library retains the established richer tabbed
            # catalogue, including Favourites as the first tab.
            self.tabs = QTabWidget(self)
            for category in LIBRARY_CATEGORIES:
                list_widget = QListWidget(self.tabs)
                list_widget.setAlternatingRowColors(True)
                list_widget.currentItemChanged.connect(self._selection_changed)
                list_widget.itemDoubleClicked.connect(
                    lambda _item, self=self: self.activate_selected()
                )
                self.tabs.addTab(list_widget, category)
                self._lists[category] = list_widget
            layout.addWidget(self.tabs, 1)

        self.description = QLabel("No snippet selected.", self)
        self.description.setWordWrap(True)
        self.description.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.description)

        self.lint_hint = QLabel("", self)
        self.lint_hint.setWordWrap(True)
        layout.addWidget(self.lint_hint)

        insert_row = QHBoxLayout()
        self.action_button = QPushButton("Insert", self)
        self.favourite_button = QPushButton("Add to My Favourites", self)
        insert_row.addWidget(self.action_button)
        insert_row.addWidget(self.favourite_button)
        layout.addLayout(insert_row)

        self.add_custom_button: QPushButton | None = None
        self.remove_custom_button: QPushButton | None = None
        self.import_button: QPushButton | None = None
        self.export_button: QPushButton | None = None
        if not self.compact:
            # Keep snippet management/import/export controls in the floating
            # Library only.  The embedded sidebar intentionally stays compact.
            custom_row = QHBoxLayout()
            self.add_custom_button = QPushButton("Add Custom Snippet...", self)
            self.remove_custom_button = QPushButton("Remove Custom", self)
            custom_row.addWidget(self.add_custom_button)
            custom_row.addWidget(self.remove_custom_button)
            layout.addLayout(custom_row)

            transfer_row = QHBoxLayout()
            self.import_button = QPushButton("Import Snippets...", self)
            self.export_button = QPushButton("Export Snippets...", self)
            transfer_row.addWidget(self.import_button)
            transfer_row.addWidget(self.export_button)
            layout.addLayout(transfer_row)

        # Library opens on Favourites only when the current document type has
        # at least one visible favourite; otherwise the family default is All.
        self._set_category_silently(self._default_category())

        self.search_input.textChanged.connect(self.refresh)
        if not self.compact:
            # Connect only after every detail/control used by refresh exists.
            self.tabs.currentChanged.connect(self._category_changed)
        self.action_button.clicked.connect(self.activate_selected)
        self.favourite_button.clicked.connect(self.toggle_favourite)
        if self.add_custom_button is not None:
            self.add_custom_button.clicked.connect(
                lambda: self.window.add_custom_snippet(self.selected_suffix())
            )
        if self.remove_custom_button is not None:
            self.remove_custom_button.clicked.connect(self.remove_selected_custom)
        if self.import_button is not None:
            self.import_button.clicked.connect(self.window.import_snippets)
        if self.export_button is not None:
            self.export_button.clicked.connect(self.window.export_snippets)
        self.refresh()

    def selected_suffix(self) -> str:
        return self._context_suffix

    def set_context_suffix(self, suffix: str) -> None:
        self._context_suffix = normalise_suffix(suffix)
        self.refresh()

    def _default_category(self) -> str:
        return default_library_category(
            self.selected_suffix(),
            self.window.library_favourites,
            self.window.custom_library_entries,
        )

    def _set_category_silently(self, category: str) -> None:
        target = category if category in LIBRARY_CATEGORIES else "All"
        if self.compact:
            index = self.category_combo.findText(target)
            if index >= 0:
                blocked = self.category_combo.blockSignals(True)
                self.category_combo.setCurrentIndex(index)
                self.category_combo.blockSignals(blocked)
            return
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == target:
                blocked = self.tabs.blockSignals(True)
                self.tabs.setCurrentIndex(index)
                self.tabs.blockSignals(blocked)
                break

    def _fallback_from_empty_favourites(self) -> None:
        if self._current_category() == "Favourites" and self._default_category() == "All":
            self._set_category_silently("All")

    def _current_category(self) -> str:
        if self.compact:
            text = self.category_combo.currentText()
            return text if text in LIBRARY_CATEGORIES else LIBRARY_CATEGORIES[0]
        return self.tabs.tabText(self.tabs.currentIndex())

    def _current_list_widget(self) -> QListWidget | None:
        if self.compact:
            return self.catalogue_list
        current = self.tabs.currentWidget()
        return current if isinstance(current, QListWidget) else None

    def _fill_list(self, list_widget: QListWidget, category: str) -> None:
        selected = self._selected_key
        list_widget.blockSignals(True)
        list_widget.clear()
        for entry in matching_entries(
            self.selected_suffix(),
            category=category,
            query=self.search_input.text(),
            favourites=tuple(self.window.library_favourites),
            custom_entries=tuple(self.window.custom_library_entries),
        ):
            favourite = entry.key in self.window.library_favourites
            item = QListWidgetItem(f"★ {entry.label}" if favourite else entry.label)
            item.setData(Qt.ItemDataRole.UserRole, entry.key)
            item.setToolTip(entry.description)
            list_widget.addItem(item)
            if entry.key == selected:
                list_widget.setCurrentItem(item)
        list_widget.blockSignals(False)
        if list_widget.currentItem() is None and list_widget.count():
            list_widget.setCurrentRow(0)

    def refresh(self) -> None:
        self._fallback_from_empty_favourites()
        if self.compact:
            self._fill_list(self.catalogue_list, self._current_category())
        else:
            for category, list_widget in self._lists.items():
                self._fill_list(list_widget, category)
        self._refresh_detail()

    def _category_changed(self, _index: int = -1) -> None:
        self.refresh()

    def _selection_changed(self, current: QListWidgetItem | None, _previous) -> None:
        if current is not None:
            key = current.data(Qt.ItemDataRole.UserRole)
            self._selected_key = key if isinstance(key, str) else None
        self._refresh_detail()

    def selected_entry(self) -> LibraryEntry | None:
        entries = entry_map(tuple(self.window.custom_library_entries))
        current = self._current_list_widget()
        if current is not None:
            item = current.currentItem()
            if item is not None:
                key = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(key, str):
                    return entries.get(key)
        if self._selected_key:
            entry = entries.get(self._selected_key)
            if entry is not None and self.selected_suffix() in entry.suffixes:
                return entry
        return None

    def _refresh_detail(self) -> None:
        entry = self.selected_entry()
        if entry is None:
            self.description.setText("No snippet selected.")
            self.lint_hint.clear()
            self.action_button.setEnabled(False)
            self.favourite_button.setEnabled(False)
            self.favourite_button.setText("Add to My Favourites")
            if self.remove_custom_button is not None:
                self.remove_custom_button.setEnabled(False)
            return
        self._selected_key = entry.key
        self.description.setText(entry.description)
        self.lint_hint.setText(f"Syntax/Lint: {entry.lint_hint}")
        favourite = entry.key in self.window.library_favourites
        self.favourite_button.setEnabled(True)
        self.favourite_button.setText(
            "Remove from My Favourites" if favourite else "Add to My Favourites"
        )
        self.action_button.setText("Insert")
        self.action_button.setEnabled(
            self.window.document_active
            and not self.window.view_only
            and self.window.document_suffix in entry.suffixes
        )
        if self.remove_custom_button is not None:
            self.remove_custom_button.setEnabled(entry.custom)

    def toggle_favourite(self) -> None:
        entry = self.selected_entry()
        if entry is not None:
            self.window.toggle_library_favourite(entry.key)

    def activate_selected(self) -> None:
        entry = self.selected_entry()
        if entry is not None:
            self.window.activate_library_entry(entry)

    def remove_selected_custom(self) -> None:
        entry = self.selected_entry()
        if entry is not None and entry.custom:
            self.window.remove_custom_snippet(entry.key)


class ScriptLibraryDialog(QDialog):
    """Modeless floating view of the same Sheepy Pad snippet Library."""

    def __init__(self, window: "SheepyPadWindow") -> None:
        super().__init__(window)
        self.window = window
        self.setWindowTitle(app_dialog_title("Library"))
        self.setModal(False)
        self.resize(560, 650)
        layout = QVBoxLayout(self)
        self.panel = ScriptLibraryPanel(window, self, compact=False)
        layout.addWidget(self.panel)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

    def set_context_suffix(self, suffix: str) -> None:
        self.panel.set_context_suffix(suffix)

    def refresh(self) -> None:
        self.panel.refresh()


class SheepyPadWindow(QMainWindow):
    """One independent Sheepy Pad document window."""

    def __init__(self, initial_file: str | Path | None = None) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        register_window(self)

        self.file_path: Path | None = None
        self.document_active = False
        self.document_suffix = ".py"
        self.file_encoding = "utf-8"
        self.file_bom = b""
        self.file_newline = "\n"
        self.file_disk_snapshot: FileSnapshot | None = None
        self._loading = False
        self.view_only = False
        self._view_only_edit_notice_shown = False

        self.search_query = ""
        self.search_case_sensitive = False
        self.search_matches: list[tuple[int, int]] = []
        self.search_match_starts: list[int] = []
        self.search_match_ends: list[int] = []
        self.current_search_index = -1
        self.search_results_truncated = False
        self._pending_search_preserve_position = False
        self._search_refresh_timer = QTimer(self)
        self._search_refresh_timer.setSingleShot(True)
        self._search_refresh_timer.setInterval(120)
        self._search_refresh_timer.timeout.connect(
            self._run_pending_search_refresh
        )
        self.search_icon_bindings: list[tuple[object, str, QStyle.StandardPixmap]] = []

        self.replace_dialog: ReplaceDialog | None = None
        self.library_dialog: ScriptLibraryDialog | None = None
        self.shortcuts_dialog: QDialog | None = None
        self.about_dialog: QDialog | None = None

        self.process = QProcess(self)
        self.process.started.connect(self._process_started)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)
        self.terminal_session: dict[str, object] | None = None

        self.runtime_paths = RuntimePaths.detect(
            Path(__file__).resolve().parents[1] / "main.py"
        )
        if self.runtime_paths.icon_path.is_file():
            self.setWindowIcon(QIcon(str(self.runtime_paths.icon_path)))
        self.runtime_launcher = RuntimeLauncher(self.runtime_paths, self)
        self.runtime_launcher.launch_error.connect(self._show_launch_error)
        self.runtime_launcher.status_message.connect(self.show_status)

        self.appimage_theme_files = self.runtime_paths.appimage_theme_paths
        self.appimage_theme_available = bool(self.appimage_theme_files)
        requested_theme = os.environ.get(
            "SHEEPY_PAD_APPIMAGE_THEME",
            "",
        ).strip().lower()
        self.appimage_theme_override = (
            requested_theme
            if requested_theme in ("dark", "light", "system")
            else None
        )

        self.config_file = self.runtime_paths.config_path
        self._load_preferences()
        if self.appimage_theme_available:
            self.apply_appimage_theme(
                self.effective_appimage_theme(),
                update_actions=False,
            )

        self.resize(940, 650)
        self.setMinimumSize(680, 440)
        self.setAcceptDrops(True)
        self._build_ui()
        self._apply_preferences()
        self._show_start_page()

        if initial_file is not None:
            self.load_file(initial_file, check_changes=False)

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------

    def _load_preferences(self) -> None:
        self.word_wrap = False
        self.show_line_numbers = True
        self.show_status_bar = True
        self.use_app_menu = True
        self.layout_mode = 1
        self.library_position = "disabled"
        self.library_width = 300
        # Ctrl+L may temporarily hide a configured Left/Right sidebar without
        # rewriting the user's View -> Library placement preference.
        self._library_sidebar_shortcut_hidden = False
        self.custom_library_entries: list[LibraryEntry] = []
        self.library_favourites: list[str] = []
        self.default_new_suffix: str | None = None
        self.drop_open_mode = "active_window"
        self.dark_editor = True
        fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.font_family = fixed.family()
        self.font_size = 10
        self.font_weight = int(QFont.Weight.Normal)
        self.font_italic = False
        self.tab_width_spaces = 4
        self.appimage_theme = "dark"
        self.interpreter_overrides: dict[str, str] = {}
        self.environment_profiles: dict[str, dict[str, str]] = {"Default": {}}
        self.active_environment_profile = "Default"
        self.working_directory_mode = "script"
        self.custom_working_directory = ""
        self.last_run_arguments = ""
        self.last_run_in_terminal = False

        config_source = self.config_file
        imported_legacy_preferences = False
        if not path_lexists(config_source):
            for legacy_config in self.runtime_paths.legacy_config_paths:
                if path_lexists(legacy_config):
                    config_source = legacy_config
                    imported_legacy_preferences = True
                    break

        try:
            raw_config, _snapshot = read_regular_file(
                config_source,
                MAX_CONFIG_SIZE,
                follow_symlinks=False,
            )
            loaded = json.loads(raw_config.decode("utf-8"))
        except (
            FileNotFoundError,
            FileTooLargeError,
            UnsupportedFileError,
            UnicodeDecodeError,
            OSError,
            ValueError,
            TypeError,
            json.JSONDecodeError,
        ):
            return
        if not isinstance(loaded, dict):
            return

        def bounded_int(
            key: str,
            default: int,
            minimum: int,
            maximum: int,
        ) -> int:
            try:
                value = int(loaded.get(key, default))
            except (TypeError, ValueError, OverflowError):
                return default
            return max(minimum, min(maximum, value))

        def boolean_value(key: str, default: bool) -> bool:
            value = loaded.get(key, default)
            return value if isinstance(value, bool) else default

        self.word_wrap = boolean_value("word_wrap", False)
        self.show_line_numbers = boolean_value("show_line_numbers", True)
        self.show_status_bar = boolean_value("show_status_bar", True)
        self.use_app_menu = boolean_value("use_app_menu", True)
        self.layout_mode = bounded_int("layout_mode", 1, 1, 4)
        if loaded.get("library_position") in ("left", "right", "disabled"):
            self.library_position = str(loaded["library_position"])
        self.library_width = bounded_int("library_width", 300, 220, 800)
        self.custom_library_entries = list(
            custom_entries_from_preferences(loaded.get("custom_library_snippets"))
        )
        self.library_favourites = normalise_favourites(
            loaded.get("library_favourites"), self.custom_library_entries
        )
        raw_default_suffix = loaded.get("default_new_suffix")
        if isinstance(raw_default_suffix, str) and raw_default_suffix.casefold() in SUPPORTED_LIBRARY_SUFFIXES:
            self.default_new_suffix = raw_default_suffix.casefold()
        if loaded.get("drop_open_mode") in ("active_window", "new_window"):
            self.drop_open_mode = str(loaded["drop_open_mode"])

        family = loaded.get("font_family")
        if isinstance(family, str) and family.strip():
            self.font_family = family.strip()
        self.font_size = bounded_int("font_size", 10, 6, 72)
        self.font_weight = bounded_int(
            "font_weight",
            int(QFont.Weight.Normal),
            int(QFont.Weight.Thin),
            int(QFont.Weight.Black),
        )
        self.font_italic = boolean_value("font_italic", False)
        self.tab_width_spaces = bounded_int("tab_width_spaces", 4, 1, 16)

        raw_overrides = loaded.get("interpreter_overrides")
        if isinstance(raw_overrides, dict):
            for raw_suffix, raw_interpreter in list(raw_overrides.items())[:16]:
                if (
                    isinstance(raw_suffix, str)
                    and raw_suffix.casefold() in SUPPORTED_SCRIPT_SUFFIXES
                    and isinstance(raw_interpreter, str)
                    and 0 < len(raw_interpreter.strip()) <= 4096
                ):
                    self.interpreter_overrides[raw_suffix.casefold()] = raw_interpreter.strip()

        self.environment_profiles = normalise_environment_profiles(
            loaded.get("environment_profiles")
        )
        active_profile = loaded.get("active_environment_profile")
        if isinstance(active_profile, str) and active_profile in self.environment_profiles:
            self.active_environment_profile = active_profile

        if loaded.get("working_directory_mode") in {"script", "custom"}:
            self.working_directory_mode = str(loaded["working_directory_mode"])
        raw_working_directory = loaded.get("custom_working_directory")
        if isinstance(raw_working_directory, str) and len(raw_working_directory) <= 4096:
            self.custom_working_directory = raw_working_directory
        raw_arguments = loaded.get("last_run_arguments")
        if isinstance(raw_arguments, str) and len(raw_arguments) <= 16384:
            self.last_run_arguments = raw_arguments
        self.last_run_in_terminal = boolean_value("last_run_in_terminal", False)
        self.dark_editor = boolean_value("dark_editor", True)

        saved_appimage_theme = str(loaded.get("appimage_theme", "")).lower()
        if saved_appimage_theme in ("dark", "light"):
            self.appimage_theme = saved_appimage_theme
        else:
            # Import the short-lived boolean preference used by r1-r16.
            self.appimage_theme = (
                "dark"
                if boolean_value("appimage_dark_mode", True)
                else "light"
            )

        # Preserve the former file as a backup while importing its settings
        # once into the new Sheepy Pad configuration location.
        if imported_legacy_preferences:
            self._save_preferences()

    def _save_preferences(self) -> None:
        data = {
            "word_wrap": self.word_wrap,
            "show_line_numbers": self.show_line_numbers,
            "show_status_bar": self.show_status_bar,
            "use_app_menu": self.use_app_menu,
            "layout_mode": self.layout_mode,
            "library_position": self.library_position,
            "library_width": self.library_width,
            "custom_library_snippets": serialise_custom_entries(self.custom_library_entries),
            "library_favourites": self.library_favourites,
            "default_new_suffix": self.default_new_suffix,
            "drop_open_mode": self.drop_open_mode,
            "dark_editor": self.dark_editor,
            "font_family": self.font_family,
            "font_size": self.font_size,
            "font_weight": self.font_weight,
            "font_italic": self.font_italic,
            "tab_width_spaces": self.tab_width_spaces,
            "interpreter_overrides": self.interpreter_overrides,
            "environment_profiles": self.environment_profiles,
            "active_environment_profile": self.active_environment_profile,
            "working_directory_mode": self.working_directory_mode,
            "custom_working_directory": self.custom_working_directory,
            "last_run_arguments": self.last_run_arguments,
            "last_run_in_terminal": self.last_run_in_terminal,
            # Preserve the AppImage choice even when source/portable mode saves
            # other preferences; those modes still do not apply or expose it.
            "appimage_theme": self.appimage_theme,
        }
        temporary: Path | None = None
        descriptor: int | None = None
        try:
            ensure_private_directory(self.config_file.parent)
            descriptor, raw_path = tempfile.mkstemp(
                prefix=".sheepy-pad-",
                suffix=".json.tmp",
                dir=self.config_file.parent,
                text=True,
            )
            temporary = Path(raw_path)
            if hasattr(os, "fchmod"):
                os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                descriptor = None
                json.dump(data, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.config_file)
            temporary = None
            fsync_directory(self.config_file.parent)
        except OSError:
            pass
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if temporary is not None:
                try:
                    temporary.unlink()
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        self.main_layout.setSpacing(6)

        self.toolbar = QWidget(self)
        self.toolbar_layout = QHBoxLayout(self.toolbar)
        self.toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self.toolbar_layout.setSpacing(6)
        self.main_layout.addWidget(self.toolbar)

        # The Edit menu binds several actions directly to CodeEditor methods,
        # so the editor must exist before the menus are constructed.
        self.editor = CodeEditor(self)
        self.editor.setObjectName("editor")
        self.editor.document().modificationChanged.connect(
            lambda _modified: self._update_title()
        )
        self.editor.textChanged.connect(self._on_document_text_changed)
        self.editor.cursorPositionChanged.connect(self._update_status)
        self.editor.overwrite_mode_changed.connect(
            lambda _enabled: self._update_status()
        )
        self.editor.go_to_line_requested.connect(self.go_to_line)
        self.editor.paste_rejected.connect(self.show_status)
        self.editor.view_only_edit_attempt.connect(
            self.show_view_only_edit_prompt
        )
        self.editor.files_dropped.connect(self.open_dropped_files)

        self.app_menu_bar = self.menuBar()
        self.app_menu_bar.clear()
        self._make_file_menu()
        self._make_edit_menu()
        self._make_view_menu()
        self._make_run_menu()
        self._make_help_menu()

        self.menu_buttons_container = QWidget(self.toolbar)
        menu_buttons_layout = QHBoxLayout(self.menu_buttons_container)
        menu_buttons_layout.setContentsMargins(0, 0, 0, 0)
        menu_buttons_layout.setSpacing(6)
        self.menu_buttons_container.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
        )
        for label, menu in (
            ("File", self.file_menu),
            ("Edit", self.edit_menu),
            ("View", self.view_menu),
            ("Run", self.run_menu),
            ("Help", self.help_menu),
        ):
            button = QToolButton(self.menu_buttons_container)
            button.setText(label)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            button.setMenu(menu)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            menu_buttons_layout.addWidget(button)

        self.primary_controls = QWidget(self.toolbar)
        self.primary_controls.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Preferred,
        )
        primary_layout = QHBoxLayout(self.primary_controls)
        primary_layout.setContentsMargins(0, 0, 0, 0)
        primary_layout.setSpacing(6)
        primary_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        primary_layout.addWidget(self.menu_buttons_container)

        # Keep the direct run controls inside Nuxpad's movable toolbar so all
        # four user-selected layouts position them naturally. The controls are
        # explicitly left-aligned.
        self.launch_button = self._action_button("Launch", self.launch_script)
        self.terminal_button = self._action_button(
            "In Terminal", self.launch_in_terminal
        )
        self.admin_button = self._action_button(
            "As Admin", self.launch_as_administrator_in_terminal
        )
        self.executable_button = self._action_button(
            "Make Exec", self.toggle_executable
        )
        self.stop_button = self._action_button("Stop", self.stop_script)
        self.force_stop_button = self._action_button(
            "Force Stop", self.force_stop_script
        )
        primary_layout.addWidget(self.executable_button)
        primary_layout.addWidget(self.launch_button)
        primary_layout.addWidget(self.terminal_button)
        primary_layout.addWidget(self.admin_button)
        primary_layout.addWidget(self.stop_button)
        primary_layout.addWidget(self.force_stop_button)
        self.toolbar_layout.addWidget(
            self.primary_controls,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )

        self.search_container = self._create_search_bar(bottom=False)
        self.toolbar_layout.addWidget(self.search_container, 1)

        # The document stack lives inside an editor column.  For split layouts
        # the split Find bar is placed inside this column, so a left/right
        # Library sidebar spans the full workspace height instead of ending at
        # the Find bar.  Inline layouts continue to keep Find in the toolbar.
        self.workspace_stack = QStackedWidget(self)
        self.start_page = self._create_start_page()
        self.workspace_stack.addWidget(self.start_page)
        self.workspace_stack.addWidget(self.editor)

        self.bottom_search = self._create_search_bar(bottom=True)
        self.editor_column = QWidget(self)
        self.editor_column_layout = QVBoxLayout(self.editor_column)
        self.editor_column_layout.setContentsMargins(0, 0, 0, 0)
        self.editor_column_layout.setSpacing(0)
        self.editor_column_layout.addWidget(self.workspace_stack, 1)
        self.editor_column_layout.addWidget(self.bottom_search)

        self.library_sidebar = ScriptLibraryPanel(self, self, compact=True)
        self.editor_workspace = QSplitter(Qt.Orientation.Horizontal, self)
        self.editor_workspace.setChildrenCollapsible(False)
        self.editor_workspace.addWidget(self.editor_column)
        self.editor_workspace.addWidget(self.library_sidebar)
        self.editor_workspace.setStretchFactor(0, 1)
        self.editor_workspace.setStretchFactor(1, 0)
        self.editor_workspace.splitterMoved.connect(self._library_splitter_moved)
        self.main_layout.addWidget(self.editor_workspace, 1)

        self.app_status_bar = self.statusBar()
        self.path_label = QLabel("Untitled", self.app_status_bar)
        self.path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.operation_mode_label = QLabel("Insert", self.app_status_bar)
        self.operation_mode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.operation_mode_label.setMinimumWidth(
            self.operation_mode_label.fontMetrics().horizontalAdvance("Overwrite") + 8
        )
        self.counter_label = QLabel(
            "Ln: 1/1, Col: 1, Char: 0", self.app_status_bar
        )
        self.encoding_label = QLabel("UTF-8", self.app_status_bar)
        self.executable_status_label = QLabel("Exec: N/A", self.app_status_bar)
        self.executable_status_label.setMinimumWidth(72)
        self.executable_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.app_status_bar.addWidget(self.path_label, 1)
        self.app_status_bar.addPermanentWidget(self.operation_mode_label)
        self.app_status_bar.addPermanentWidget(self.executable_status_label)
        self.app_status_bar.addPermanentWidget(self.counter_label)
        self.app_status_bar.addPermanentWidget(self.encoding_label)

        self.setStyleSheet(
            "QToolButton::menu-indicator { image: none; width: 0px; }"
        )

    def _create_start_page(self) -> QWidget:
        page = QWidget(self)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(36, 30, 36, 30)
        outer.addStretch(1)

        panel = QWidget(page)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(8)

        title = QLabel("Start a Document", panel)
        title_font = QFont(title.font())
        title_font.setPointSize(max(14, title_font.pointSize() + 5))
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_layout.addWidget(title)

        subtitle = QLabel(
            "Choose the kind of script you want to create, or\nopen an existing file.",
            panel,
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_layout.addWidget(subtitle)

        form = QFormLayout()
        form.setContentsMargins(0, 6, 0, 0)
        self.start_type_combo = QComboBox(panel)
        for label, suffix in DOCUMENT_TYPES:
            self.start_type_combo.addItem(label, suffix)
        form.addRow("Document type:", self.start_type_combo)
        panel_layout.addLayout(form)

        self.start_default_checkbox = QCheckBox(
            "Use this type as my default", panel
        )
        panel_layout.addWidget(
            self.start_default_checkbox, 0, Qt.AlignmentFlag.AlignCenter
        )
        self.start_type_combo.currentIndexChanged.connect(self._start_type_changed)

        action_row = QHBoxLayout()
        create_button = QPushButton("Create Document", panel)
        open_button = QPushButton("Open Existing File...", panel)
        create_button.clicked.connect(self.create_from_start_page)
        open_button.clicked.connect(self.open_file)
        action_row.addStretch(1)
        action_row.addWidget(create_button)
        action_row.addWidget(open_button)
        action_row.addStretch(1)
        panel_layout.addLayout(action_row)

        outer.addWidget(panel, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(2)
        return page

    def _library_splitter_moved(self, _position: int, _index: int) -> None:
        if self.library_position == "disabled" or not hasattr(self, "editor_workspace"):
            return
        sizes = self.editor_workspace.sizes()
        if len(sizes) != 2:
            return
        library_index = 0 if self.library_position == "left" else 1
        width = sizes[library_index]
        if width >= 220:
            self.library_width = min(800, width)

    def _apply_library_position(self) -> None:
        if not hasattr(self, "library_sidebar"):
            return
        # Match the established Timblee/JSTS no-document behavior: a saved
        # Left/Right Sidebar preference is retained, but the embedded Library
        # is never shown on Start a Document. It returns automatically when a
        # document becomes active. Floating Library access remains independent.
        if (
            self.library_position == "disabled"
            or not self.document_active
            or self._library_sidebar_shortcut_hidden
        ):
            self.library_sidebar.hide()
            return
        target_index = 0 if self.library_position == "left" else 1
        self.editor_workspace.insertWidget(target_index, self.library_sidebar)
        self.library_sidebar.show()
        total = max(self.editor_workspace.width(), self.library_width + 360)
        library_width = min(self.library_width, max(220, total - 360))
        editor_width = max(360, total - library_width)
        if self.library_position == "left":
            self.editor_workspace.setSizes([library_width, editor_width])
        else:
            self.editor_workspace.setSizes([editor_width, library_width])
        self.editor_workspace.setStretchFactor(
            1 if self.library_position == "left" else 0, 1
        )
        self.editor_workspace.setStretchFactor(target_index, 0)

    def set_library_position(self, position: str) -> None:
        if position not in {"left", "right", "disabled"}:
            return
        self.library_position = position
        self._library_sidebar_shortcut_hidden = False
        for value, action in self.library_position_actions.items():
            action.blockSignals(True)
            action.setChecked(value == position)
            action.blockSignals(False)
        self._apply_library_position()
        self._save_preferences()

    def set_library_sidebar_hidden(self, hidden: bool) -> None:
        """Transiently hide/show a configured sidebar without changing placement."""
        if self.library_position == "disabled":
            return
        self._library_sidebar_shortcut_hidden = bool(hidden)
        self._apply_library_position()

    def show_library_dialog(self) -> None:
        if self.library_dialog is None:
            self.library_dialog = ScriptLibraryDialog(self)
            self.library_dialog.finished.connect(
                lambda _result: setattr(self, "library_dialog", None)
            )
        self.library_dialog.set_context_suffix(self.document_suffix)
        self.library_dialog.refresh()
        self.library_dialog.show()
        self.library_dialog.raise_()
        self.library_dialog.activateWindow()

    def toggle_library_shortcut(self) -> None:
        """Toggle the Library according to the user's View -> Library placement."""
        if self.library_position == "disabled":
            if self.library_dialog is not None and self.library_dialog.isVisible():
                self.library_dialog.close()
            else:
                self.show_library_dialog()
            return

        # The Timblee/JSTS no-document contract wins over the shortcut: an
        # embedded sidebar never appears on Start a Document.
        if not self.document_active:
            self.show_status("Library sidebar is available when a document is active.")
            return

        self.set_library_sidebar_hidden(not self._library_sidebar_shortcut_hidden)

    def _sync_library_context(self) -> None:
        if hasattr(self, "library_sidebar"):
            self.library_sidebar.set_context_suffix(self.document_suffix)
        if self.library_dialog is not None:
            self.library_dialog.set_context_suffix(self.document_suffix)

    def _refresh_library_surfaces(self) -> None:
        if hasattr(self, "library_sidebar"):
            self.library_sidebar.refresh()
        if self.library_dialog is not None:
            self.library_dialog.refresh()
        self._refresh_favourites_menu()

    def _refresh_favourites_menu(self) -> None:
        menu = getattr(self, "favourites_menu", None)
        if menu is None:
            return
        menu.clear()
        entries = entry_map(tuple(self.custom_library_entries))
        visible = [entries[key] for key in self.library_favourites if key in entries]
        if not visible:
            empty = QAction("No favourites", self)
            empty.setEnabled(False)
            menu.addAction(empty)
            return
        for entry in visible:
            action = QAction(entry.label, self)
            action.setEnabled(
                self.document_active
                and not self.view_only
                and self.document_suffix in entry.suffixes
            )
            action.triggered.connect(
                lambda _checked=False, selected=entry: self.activate_library_entry(selected)
            )
            menu.addAction(action)

    def toggle_library_favourite(self, key: str) -> None:
        entries = entry_map(tuple(self.custom_library_entries))
        if key not in entries:
            return
        if key in self.library_favourites:
            self.library_favourites.remove(key)
        else:
            self.library_favourites.append(key)
        self.library_favourites = normalise_favourites(
            self.library_favourites, self.custom_library_entries
        )
        self._save_preferences()
        self._refresh_library_surfaces()

    def add_custom_snippet(self, suffix: str | None = None) -> None:
        selected_suffix = normalise_suffix(suffix or self.document_suffix)
        label, accepted = QInputDialog.getText(
            self,
            app_dialog_title("Add Custom Snippet"),
            "Snippet name:",
        )
        if not accepted:
            return
        label = label.strip()
        if not label or len(label) > 120:
            QMessageBox.warning(
                self,
                app_dialog_title("Add Custom Snippet"),
                "Enter a snippet name between 1 and 120 characters.",
            )
            return
        body, accepted = QInputDialog.getMultiLineText(
            self,
            app_dialog_title("Add Custom Snippet"),
            f"Snippet for {DOCUMENT_TYPE_LABEL[selected_suffix]} ({selected_suffix}):\n"
            "Use [[selection]] and [[cursor]] markers if useful.",
        )
        if not accepted:
            return
        if len(body.encode("utf-8")) > 8 * 1024:
            QMessageBox.warning(
                self,
                app_dialog_title("Add Custom Snippet"),
                "Custom snippets are limited to 8 KiB.",
            )
            return
        raw = serialise_custom_entries(self.custom_library_entries)
        raw.append(
            {
                "key": f"custom-{uuid4().hex}",
                "label": label,
                "suffix": selected_suffix,
                "description": "User-defined snippet.",
                "body": body,
            }
        )
        self.custom_library_entries = list(custom_entries_from_preferences(raw))
        self._save_preferences()
        self._refresh_library_surfaces()
        self.show_status(f"Added custom snippet: {label}")

    def remove_custom_snippet(self, key: str) -> None:
        target = next(
            (entry for entry in self.custom_library_entries if entry.key == key), None
        )
        if target is None:
            return
        answer = QMessageBox.question(
            self,
            app_dialog_title("Remove Custom Snippet"),
            f"Remove custom snippet '{target.label}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.custom_library_entries = [
            entry for entry in self.custom_library_entries if entry.key != key
        ]
        self.library_favourites = normalise_favourites(
            self.library_favourites, self.custom_library_entries
        )
        self._save_preferences()
        self._refresh_library_surfaces()

    def _snippet_collection_data(self) -> dict[str, object]:
        return {
            "format": "sheepy-pad-snippets",
            "version": 1,
            "custom_snippets": serialise_custom_entries(self.custom_library_entries),
            "favourites": list(self.library_favourites),
        }

    def import_snippets(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            app_dialog_title("Import Snippets"),
            str(Path.home()),
            "Sheepy Pad Snippets (*.sheepysnippets);;JSON Files (*.json);;All Files (*)",
        )
        if not selected:
            return
        path = absolute_user_path(selected)
        try:
            raw, _snapshot = read_regular_file(path, 1024 * 1024, follow_symlinks=True)
            data = json.loads(raw.decode("utf-8"))
        except (OSError, FileTooLargeError, UnicodeDecodeError, json.JSONDecodeError) as error:
            QMessageBox.warning(self, app_dialog_title("Import Snippets"), str(error))
            return
        if not isinstance(data, dict) or data.get("format") != "sheepy-pad-snippets" or data.get("version") != 1:
            QMessageBox.warning(
                self,
                app_dialog_title("Import Snippets"),
                "This is not a supported Sheepy Pad snippet collection.",
            )
            return
        incoming = list(custom_entries_from_preferences(data.get("custom_snippets")))
        if self.custom_library_entries or self.library_favourites:
            box = QMessageBox(self)
            box.setWindowTitle(app_dialog_title("Import Snippets"))
            box.setText("Merge the imported snippets with your current Library, or replace the current user layer?")
            box.addButton("Merge", QMessageBox.ButtonRole.AcceptRole)
            replace_button = box.addButton("Replace", QMessageBox.ButtonRole.DestructiveRole)
            cancel_button = box.addButton(QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(cancel_button)
            box.exec()
            clicked = box.clickedButton()
            if clicked is cancel_button:
                return
            replace = clicked is replace_button
        else:
            replace = True
        if replace:
            combined = incoming
        else:
            existing = {entry.key: entry for entry in self.custom_library_entries}
            for entry in incoming:
                if entry.key in existing:
                    entry = LibraryEntry(
                        f"custom-{uuid4().hex}", entry.label, entry.category,
                        entry.suffixes, entry.description, entry.lint_hint,
                        entry.body, True,
                    )
                existing[entry.key] = entry
            combined = list(existing.values())
        self.custom_library_entries = list(
            custom_entries_from_preferences(serialise_custom_entries(combined))
        )
        incoming_favourites = data.get("favourites")
        if replace:
            favourite_seed = incoming_favourites
        else:
            favourite_seed = [
                *self.library_favourites,
                *(incoming_favourites if isinstance(incoming_favourites, list) else []),
            ]
        self.library_favourites = normalise_favourites(
            favourite_seed, self.custom_library_entries
        )
        self._save_preferences()
        self._refresh_library_surfaces()
        self.show_status("Imported Sheepy Pad snippets.")

    def export_snippets(self) -> None:
        selected, _filter = QFileDialog.getSaveFileName(
            self,
            app_dialog_title("Export Snippets"),
            str(Path.home() / "sheepy-pad-snippets.sheepysnippets"),
            "Sheepy Pad Snippets (*.sheepysnippets);;JSON Files (*.json)",
        )
        if not selected:
            return
        path = absolute_user_path(selected)
        if not path.suffix:
            path = path.with_suffix(".sheepysnippets")

        expected_state = None
        existed = path_lexists(path)
        if existed:
            try:
                expected_state = current_file_state(path)
            except (OSError, UnsupportedFileError, FileStateChangedError) as error:
                QMessageBox.warning(self, app_dialog_title("Export Snippets"), str(error))
                return
            answer = QMessageBox.question(
                self,
                app_dialog_title("Replace File"),
                f"Replace '{path.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        payload = (json.dumps(self._snippet_collection_data(), indent=2) + "\n").encode("utf-8")
        temporary: Path | None = None
        descriptor: int | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, raw_path = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
            )
            temporary = Path(raw_path)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = None
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())

            # Match Timblee's collection-export safety: confirmation is not a
            # licence to overwrite a destination that changed while the dialog
            # or temporary write was in progress.
            if existed:
                if not path_lexists(path) or current_file_state(path) != expected_state:
                    raise FileStateChangedError(
                        "The destination changed before it could be replaced. Export was cancelled."
                    )
                os.replace(temporary, path)
            else:
                install_new_file_from_temp(temporary, path)
            temporary = None
            fsync_directory(path.parent)
        except (OSError, UnsupportedFileError, FileStateChangedError) as error:
            QMessageBox.warning(self, app_dialog_title("Export Snippets"), str(error))
            return
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if temporary is not None:
                try:
                    temporary.unlink()
                except OSError:
                    pass
        self.show_status(f"Exported snippets to {path.name}")

    def activate_library_entry(self, entry: LibraryEntry) -> None:
        if not self.document_active:
            self.show_status("Open or create a document before inserting a snippet.")
            return
        if self.document_suffix not in entry.suffixes:
            self.show_status("That snippet does not match the active document type.")
            return
        if self.view_only:
            self.show_view_only_edit_prompt()
            return
        cursor = self.editor.textCursor()
        selected = cursor.selectedText().replace("\u2029", "\n")
        text, cursor_offset = render_entry(entry, selected)
        resulting_size = max(0, self.editor.document().characterCount() - 1) - len(selected) + len(text)
        if resulting_size > MAX_DOCUMENT_CHARACTERS:
            QMessageBox.warning(
                self,
                app_dialog_title("Snippet Too Large"),
                "The Library insertion would exceed Sheepy Pad's document safety limit.",
            )
            return
        start = cursor.selectionStart()
        cursor.insertText(text)
        cursor.setPosition(start + cursor_offset)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def _action_button(self, text: str, callback) -> QPushButton:
        button = QPushButton(text, self.primary_controls)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(callback)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        return button

    def _create_search_bar(self, *, bottom: bool) -> QWidget:
        host = QWidget(self)
        layout = QHBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        entry = QLineEdit(host)
        entry.setMaxLength(MAX_SEARCH_QUERY_CHARACTERS)
        entry.setPlaceholderText("Find text")
        entry.returnPressed.connect(self.find_next)
        entry.textChanged.connect(self.set_search_query)

        # Restore Nuxpad's persistent search icons. Find remains icon-only
        # in Inline layouts and gains a text label in both Split layouts;
        # Previous and Next remain icon-only in every layout.
        find_button = QPushButton(host)
        previous_button = QToolButton(host)
        next_button = QToolButton(host)
        self._bind_search_icon(
            find_button,
            "edit-find",
            QStyle.StandardPixmap.SP_FileDialogContentsView,
            "Highlight all matches",
            "Find" if bottom else "",
        )
        self._bind_search_icon(
            previous_button,
            "go-previous",
            QStyle.StandardPixmap.SP_ArrowBack,
            "Previous match",
        )
        self._bind_search_icon(
            next_button,
            "go-next",
            QStyle.StandardPixmap.SP_ArrowForward,
            "Next match",
        )

        counter = QLabel("0/0", host)
        counter.setMinimumWidth(48)
        counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        find_button.clicked.connect(self.find_and_refocus)
        previous_button.clicked.connect(self.find_previous)
        next_button.clicked.connect(self.find_next)
        layout.addWidget(entry, 1)
        layout.addWidget(find_button)
        layout.addWidget(counter)
        layout.addWidget(previous_button)
        layout.addWidget(next_button)
        if bottom:
            self.bottom_search_entry = entry
            self.bottom_search_counter = counter
        else:
            self.search_entry = entry
            self.search_counter = counter
        return host

    def _bind_search_icon(
        self,
        target,
        theme_name: str,
        fallback: QStyle.StandardPixmap,
        tooltip: str,
        text: str = "",
    ) -> None:
        target.setText(text)
        target.setToolTip(tooltip)
        target.setAccessibleName(tooltip)
        target.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        target.setIconSize(QSize(16, 16))
        target.setMinimumWidth(68 if text else 30)
        self.search_icon_bindings.append((target, theme_name, fallback))
        self._refresh_search_icon(target, theme_name, fallback)

    def _refresh_search_icon(
        self,
        target,
        theme_name: str,
        fallback: QStyle.StandardPixmap,
    ) -> None:
        target.setIcon(self._search_icon(theme_name, fallback))

    @staticmethod
    def _tint_icon(icon: QIcon, colour: QColor) -> QIcon:
        """Return a monochrome copy suitable for the selected AppImage chrome."""
        if icon.isNull():
            return icon

        tinted_icon = QIcon()
        for logical_size in (16, 20, 24, 32):
            pixmap = icon.pixmap(logical_size, logical_size)
            if pixmap.isNull():
                continue
            tinted = QPixmap(pixmap.size())
            tinted.fill(Qt.GlobalColor.transparent)
            painter = QPainter(tinted)
            painter.drawPixmap(0, 0, pixmap)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceIn
            )
            painter.fillRect(tinted.rect(), colour)
            painter.end()
            tinted.setDevicePixelRatio(pixmap.devicePixelRatio())
            tinted_icon.addPixmap(tinted)
        return tinted_icon if not tinted_icon.isNull() else icon

    def _search_icon(
        self,
        theme_name: str,
        fallback: QStyle.StandardPixmap,
    ) -> QIcon:
        icon = QIcon.fromTheme(theme_name)
        if icon.isNull():
            icon = self.style().standardIcon(fallback)
        if self.appimage_theme_available:
            theme = self.effective_appimage_theme()
            if theme == "dark":
                return self._tint_icon(icon, QColor("#eff0f1"))
            if theme == "light":
                return self._tint_icon(icon, QColor("#232629"))
        return icon

    def _refresh_search_icons(self) -> None:
        for target, theme_name, fallback in tuple(self.search_icon_bindings):
            try:
                self._refresh_search_icon(target, theme_name, fallback)
            except RuntimeError:
                continue

    def _add_action(
        self,
        menu: QMenu,
        label: str,
        callback,
        shortcut: QKeySequence | str | None = None,
        *,
        checkable: bool = False,
    ) -> QAction:
        action = QAction(label, self)
        action.setCheckable(checkable)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(callback)
        menu.addAction(action)
        return action

    def _make_file_menu(self) -> None:
        self.file_menu = self.app_menu_bar.addMenu("&File")
        self.new_action = self._add_action(
            self.file_menu, "New", self.new_file, QKeySequence.StandardKey.New
        )
        self.new_type_action = self._add_action(
            self.file_menu, "New Type...", self.new_type_document
        )
        self.default_new_action = self._add_action(
            self.file_menu, "Default New Document...", self.choose_default_new_document
        )
        self.open_action = self._add_action(
            self.file_menu, "Open...", self.open_file, QKeySequence.StandardKey.Open
        )
        self.file_menu.addSeparator()

        self.document_type_menu = self.file_menu.addMenu("Document Type")
        document_type_group = QActionGroup(self)
        document_type_group.setExclusive(True)
        self.document_type_actions: dict[str, QAction] = {}
        for label, suffix in DOCUMENT_TYPES:
            action = QAction(label, self, checkable=True)
            action.triggered.connect(
                lambda _checked=False, selected=suffix: self.set_document_type(selected)
            )
            document_type_group.addAction(action)
            self.document_type_menu.addAction(action)
            self.document_type_actions[suffix] = action

        self.file_menu.addSeparator()
        self.save_action = self._add_action(
            self.file_menu, "Save", self.save_file, QKeySequence.StandardKey.Save
        )
        self.save_as_action = self._add_action(
            self.file_menu,
            "Save As...",
            self.save_as_file,
            QKeySequence.StandardKey.SaveAs,
        )
        self.file_menu.addSeparator()
        self.properties_action = self._add_action(
            self.file_menu,
            "Properties",
            self.show_properties_dialog,
        )
        self.more_actions_menu = self.file_menu.addMenu("More Actions")
        self.external_action = self._add_action(
            self.more_actions_menu,
            "Open in External Editor",
            self.open_external_editor,
            QKeySequence("Ctrl+Shift+E"),
        )
        self.more_actions_menu.addSeparator()
        self.rename_action = self._add_action(
            self.more_actions_menu,
            "Rename...",
            self.rename_current_file,
            QKeySequence("F2"),
        )
        self.delete_action = self._add_action(
            self.more_actions_menu,
            "Delete File",
            self.delete_file,
        )
        self.more_actions_menu.addSeparator()
        self.duplicate_file_action = self._add_action(
            self.more_actions_menu,
            "Duplicate File",
            self.duplicate_file,
            QKeySequence("Ctrl+Shift+D"),
        )
        self.folder_action = self._add_action(
            self.more_actions_menu,
            "Open Containing Folder",
            self.open_folder,
            QKeySequence("Ctrl+Shift+O"),
        )
        self.file_menu.addSeparator()
        self._add_action(
            self.file_menu,
            "New Window",
            self.new_window,
            QKeySequence("Ctrl+Shift+N"),
        )
        self._add_action(
            self.file_menu, "Exit", self.close, QKeySequence.StandardKey.Quit
        )

    def _make_edit_menu(self) -> None:
        self.edit_menu = self.app_menu_bar.addMenu("&Edit")
        self.undo_action = self._add_action(
            self.edit_menu,
            "Undo",
            self.editor_undo,
            QKeySequence.StandardKey.Undo,
        )
        self.redo_action = self._add_action(
            self.edit_menu, "Redo", self.editor_redo, QKeySequence("Ctrl+Y")
        )
        self.edit_menu.addSeparator()
        self.cut_action = self._add_action(
            self.edit_menu,
            "Cut",
            lambda: self.editor.cut(),
            QKeySequence.StandardKey.Cut,
        )
        self.copy_action = self._add_action(
            self.edit_menu,
            "Copy",
            lambda: self.editor.copy(),
            QKeySequence.StandardKey.Copy,
        )
        self.paste_action = self._add_action(
            self.edit_menu,
            "Paste",
            self.editor.paste_safely,
            QKeySequence.StandardKey.Paste,
        )
        self.delete_text_action = self._add_action(
            self.edit_menu,
            "Delete",
            self.editor.delete_selection_or_character,
            QKeySequence.StandardKey.Delete,
        )
        self.edit_menu.addSeparator()
        self.comment_action = self._add_action(
            self.edit_menu,
            "Toggle Comment",
            self.editor.toggle_comment,
            QKeySequence("Ctrl+/"),
        )
        self.edit_menu.addSeparator()
        self.duplicate_action = self._add_action(
            self.edit_menu,
            "Duplicate Line / Selection",
            self.editor.duplicate_current_line_or_selection,
            QKeySequence("Ctrl+D"),
        )
        self.delete_line_action = self._add_action(
            self.edit_menu,
            "Delete Line",
            self.editor.delete_current_line_or_selection_lines,
            QKeySequence("Ctrl+Shift+K"),
        )
        self.edit_menu.addSeparator()
        self.select_all_action = self._add_action(
            self.edit_menu,
            "Select All",
            self.editor.select_all_text,
            QKeySequence.StandardKey.SelectAll,
        )
        self.edit_menu.addSeparator()
        self.go_to_line_action = self._add_action(
            self.edit_menu,
            "Go To Line...",
            self.go_to_line,
            QKeySequence("Ctrl+G"),
        )
        self.replace_action = self._add_action(
            self.edit_menu,
            "Replace...",
            self.show_replace_dialog,
            QKeySequence("Ctrl+H"),
        )

        self.focus_find_action = QAction(self)
        self.focus_find_action.setShortcut(QKeySequence.StandardKey.Find)
        self.focus_find_action.triggered.connect(self.focus_search)
        self.addAction(self.focus_find_action)
        self.find_next_action = QAction(self)
        self.find_next_action.setShortcut(QKeySequence("F3"))
        self.find_next_action.triggered.connect(self.find_next)
        self.addAction(self.find_next_action)
        self.find_previous_action = QAction(self)
        self.find_previous_action.setShortcut(QKeySequence("Shift+F3"))
        self.find_previous_action.triggered.connect(self.find_previous)
        self.addAction(self.find_previous_action)
        self.clear_search_action = QAction(self)
        self.clear_search_action.setShortcut(QKeySequence("Esc"))
        self.clear_search_action.triggered.connect(self.clear_search)
        self.addAction(self.clear_search_action)

    def _make_view_menu(self) -> None:
        self.view_menu = self.app_menu_bar.addMenu("&View")
        self.view_only_action = self._add_action(
            self.view_menu,
            "View Only",
            self.toggle_view_only,
            checkable=True,
        )
        self.view_menu.addSeparator()
        self.wrap_action = self._add_action(
            self.view_menu,
            "Word Wrap",
            self.toggle_word_wrap,
            checkable=True,
        )
        self.line_numbers_action = self._add_action(
            self.view_menu,
            "Line Numbers",
            self.toggle_line_numbers,
            checkable=True,
        )
        self.view_menu.addSeparator()
        self.app_menu_action = self._add_action(
            self.view_menu,
            "Menu Only",
            self.toggle_menu_style,
            checkable=True,
        )
        self.status_bar_action = self._add_action(
            self.view_menu,
            "Status Bar",
            self.toggle_status_bar,
            checkable=True,
        )
        self.view_menu.addSeparator()

        library_menu = self.view_menu.addMenu("Library")
        library_group = QActionGroup(self)
        library_group.setExclusive(True)
        self.library_position_actions: dict[str, QAction] = {}
        for position, label in (
            ("left", "Left Sidebar"),
            ("right", "Right Sidebar"),
            ("disabled", "Floating Only"),
        ):
            action = QAction(label, self, checkable=True)
            action.triggered.connect(
                lambda _checked=False, selected=position: self.set_library_position(selected)
            )
            library_group.addAction(action)
            library_menu.addAction(action)
            self.library_position_actions[position] = action
        self.view_menu.addSeparator()

        layout_menu = self.view_menu.addMenu("Layout")
        layout_group = QActionGroup(self)
        layout_group.setExclusive(True)
        self.layout_actions: dict[int, QAction] = {}
        labels = {
            1: "Inline — Top",
            2: "Inline — Bottom",
            3: "Split — Toolbar Up / Search Down",
            4: "Split — Toolbar Down / Search Top",
        }
        for mode, label in labels.items():
            action = QAction(label, self, checkable=True)
            action.triggered.connect(
                lambda _checked=False, selected=mode: self.set_layout_mode(selected)
            )
            layout_group.addAction(action)
            layout_menu.addAction(action)
            self.layout_actions[mode] = action

        behaviour_menu = self.view_menu.addMenu("File Drag and Drop")
        behaviour_group = QActionGroup(self)
        behaviour_group.setExclusive(True)
        self.drop_behaviour_actions: dict[str, QAction] = {}
        behaviours = {
            "active_window": "Opens on Active Window",
            "new_window": "Opens on New Window",
        }
        for mode, label in behaviours.items():
            action = QAction(label, self, checkable=True)
            action.triggered.connect(
                lambda _checked=False, selected=mode: self.set_drop_open_mode(selected)
            )
            behaviour_group.addAction(action)
            behaviour_menu.addAction(action)
            self.drop_behaviour_actions[mode] = action

        self.view_menu.addSeparator()
        self.dark_editor_action = self._add_action(
            self.view_menu,
            "Dark Editor",
            self.toggle_dark_editor,
            checkable=True,
        )
        self.appimage_dark_action: QAction | None = None
        if self.appimage_theme_available:
            self.appimage_dark_action = self._add_action(
                self.view_menu,
                "Dark Mode",
                self.toggle_appimage_dark_mode,
                checkable=True,
            )
            self.appimage_dark_action.setToolTip(
                "Use the AppImage-only Breeze-inspired dark theme; "
                "turn off for light mode."
            )
        self._add_action(self.view_menu, "Display Font...", self.choose_font)

    def _make_run_menu(self) -> None:
        self.run_menu = self.app_menu_bar.addMenu("&Run")
        self.executable_action = self._add_action(
            self.run_menu,
            "Make Executable",
            self.toggle_executable,
            QKeySequence("Ctrl+Shift+X"),
        )
        self.run_menu.addSeparator()
        self.launch_action = self._add_action(
            self.run_menu, "Launch", self.launch_script, QKeySequence("F5")
        )
        self.terminal_action = self._add_action(
            self.run_menu,
            "Launch in Terminal",
            self.launch_in_terminal,
            QKeySequence("Ctrl+1"),
        )
        self.admin_action = self._add_action(
            self.run_menu,
            "Launch as Admin in Terminal",
            self.launch_as_administrator_in_terminal,
            QKeySequence("Ctrl+Shift+1"),
        )
        self.run_arguments_action = self._add_action(
            self.run_menu,
            "Run with Arguments...",
            self.run_with_arguments,
            QKeySequence("Ctrl+2"),
        )
        self.run_menu.addSeparator()
        self.lint_action = self._add_action(
            self.run_menu,
            "Syntax / Lint Check",
            self.syntax_lint_check,
            QKeySequence("Ctrl+3"),
        )
        self.interpreter_action = self._add_action(
            self.run_menu,
            "Select Interpreter...",
            self.select_interpreter,
            QKeySequence("Ctrl+4"),
        )
        self.working_directory_action = self._add_action(
            self.run_menu,
            "Working Directory...",
            self.select_working_directory,
            QKeySequence("Ctrl+5"),
        )
        self.environment_profiles_action = self._add_action(
            self.run_menu,
            "Environment Profiles...",
            self.manage_environment_profiles,
            QKeySequence("Ctrl+6"),
        )

        # Timblee-family placement: Library is a Run submenu directly after
        # Environment Profiles and before the process-control separator.
        self.library_menu = self.run_menu.addMenu("Library")
        self._populate_library_menu()
        self.run_menu.addSeparator()

        self.stop_action = self._add_action(
            self.run_menu, "Stop", self.stop_script, QKeySequence("Shift+F5")
        )
        self.force_stop_action = self._add_action(
            self.run_menu,
            "Force Stop",
            self.force_stop_script,
            QKeySequence("Ctrl+Shift+F5"),
        )

    def _populate_library_menu(self) -> None:
        self.favourites_menu = self.library_menu.addMenu("My Favourites")
        self.library_toggle_action = self._add_action(
            self.library_menu,
            "Library...",
            self.toggle_library_shortcut,
            QKeySequence("Ctrl+L"),
        )
        self.library_menu.addSeparator()
        self._add_action(
            self.library_menu,
            "Add Custom Snippet...",
            self.add_custom_snippet,
        )
        self._add_action(
            self.library_menu,
            "Import Snippets...",
            self.import_snippets,
        )
        self._add_action(
            self.library_menu,
            "Export Snippets...",
            self.export_snippets,
        )
        self._refresh_favourites_menu()

    def _make_help_menu(self) -> None:
        self.help_menu = self.app_menu_bar.addMenu("&Help")
        self._add_action(
            self.help_menu,
            "Documentation",
            self.open_documentation,
            QKeySequence("F1"),
        )
        self._add_action(
            self.help_menu, "Keyboard Shortcuts", self.show_shortcuts_dialog
        )
        self.help_menu.addSeparator()
        self._add_action(
            self.help_menu, "GitHub Repository", self.open_github_repository
        )
        self._add_action(
            self.help_menu, "Report an Issue", self.report_an_issue
        )
        self.help_menu.addSeparator()
        about_action = self._add_action(
            self.help_menu, "About Sheepy Pad", self.show_about_dialog
        )
        about_action.setMenuRole(QAction.MenuRole.AboutRole)

    def _apply_preferences(self) -> None:
        self.wrap_action.setChecked(self.word_wrap)
        self.line_numbers_action.setChecked(self.show_line_numbers)
        self.app_menu_action.setChecked(self.use_app_menu)
        self.status_bar_action.setChecked(self.show_status_bar)
        self.view_only_action.setChecked(self.view_only)
        self.dark_editor_action.setChecked(self.dark_editor)
        if self.appimage_dark_action is not None:
            self.appimage_dark_action.setChecked(
                self.effective_appimage_theme() == "dark"
            )
        for mode, action in self.layout_actions.items():
            action.setChecked(mode == self.layout_mode)
        for mode, action in self.drop_behaviour_actions.items():
            action.setChecked(mode == self.drop_open_mode)
        for position, action in self.library_position_actions.items():
            action.setChecked(position == self.library_position)
        self.editor.set_word_wrap_enabled(self.word_wrap)
        self.editor.set_line_numbers_visible(self.show_line_numbers)
        self.editor.set_tab_width_spaces(self.tab_width_spaces)
        self.editor.set_view_only(self.view_only)
        font = QFont(self.font_family, self.font_size)
        try:
            font_weight = QFont.Weight(self.font_weight)
        except (TypeError, ValueError):
            font_weight = QFont.Weight.Normal
            self.font_weight = int(font_weight)
        font.setWeight(font_weight)
        font.setItalic(self.font_italic)
        self.editor.set_editor_font(font)
        self.editor.set_color_scheme("dark" if self.dark_editor else "light")
        self.app_status_bar.setVisible(self.show_status_bar)
        self._apply_menu_style()
        self._apply_library_position()
        self._apply_layout_mode()

    def toggle_view_only(self, checked: bool) -> None:
        """Toggle the non-persistent document-editing protection mode."""
        requested = bool(checked)
        if self.view_only and not requested:
            dialog = QMessageBox(self)
            dialog.setIcon(QMessageBox.Icon.Warning)
            dialog.setWindowTitle(app_dialog_title("Disable View Only?"))
            dialog.setText(
                "View Only protects this file from accidental changes."
            )
            dialog.setInformativeText(
                "Disabling it will allow editing and could change the file. "
                "Do you want to continue?"
            )
            keep_button = dialog.addButton(
                "Keep View Only", QMessageBox.ButtonRole.RejectRole
            )
            continue_button = dialog.addButton(
                "Continue", QMessageBox.ButtonRole.AcceptRole
            )
            dialog.setDefaultButton(keep_button)
            dialog.setEscapeButton(keep_button)
            dialog.exec()
            if dialog.clickedButton() is not continue_button:
                self.view_only_action.blockSignals(True)
                self.view_only_action.setChecked(True)
                self.view_only_action.blockSignals(False)
                self.show_status("View Only mode remains enabled.")
                self.editor.setFocus()
                return

        self.view_only = requested
        if self.view_only:
            self._view_only_edit_notice_shown = False
        self.editor.set_view_only(self.view_only)
        self._update_edit_action_state()
        self._refresh_library_surfaces()
        if self.replace_dialog is not None:
            self.replace_dialog.set_view_only(self.view_only)
        self.show_status(
            "View Only mode enabled." if self.view_only else "View Only mode disabled."
        )
        self.editor.setFocus()

    def show_view_only_edit_prompt(self) -> None:
        """Explain the first blocked edit attempt in each View Only session."""
        if not self.view_only:
            return
        self.show_status("Editing is disabled while View Only mode is enabled.")
        if self._view_only_edit_notice_shown:
            return

        # Set this before opening the modal dialog so key auto-repeat or queued
        # input cannot create a cascade of identical prompts.
        self._view_only_edit_notice_shown = True
        QMessageBox.information(
            self,
            app_dialog_title("View Only Mode"),
            "Editing is disabled because View Only mode is enabled.\n\n"
            "To enable editing, open View → View Only, clear the check mark, "
            "and select Continue in the confirmation prompt.",
        )
        self.editor.setFocus()

    def _update_edit_action_state(self) -> None:
        all_actions = (
            getattr(self, "undo_action", None),
            getattr(self, "redo_action", None),
            getattr(self, "cut_action", None),
            getattr(self, "copy_action", None),
            getattr(self, "paste_action", None),
            getattr(self, "delete_text_action", None),
            getattr(self, "comment_action", None),
            getattr(self, "duplicate_action", None),
            getattr(self, "delete_line_action", None),
            getattr(self, "select_all_action", None),
            getattr(self, "go_to_line_action", None),
            getattr(self, "replace_action", None),
        )
        if not self.document_active:
            for action in all_actions:
                if action is not None:
                    action.setEnabled(False)
            return

        editing_enabled = not self.view_only
        for action in (
            getattr(self, "undo_action", None),
            getattr(self, "redo_action", None),
            getattr(self, "cut_action", None),
            getattr(self, "paste_action", None),
            getattr(self, "delete_text_action", None),
            getattr(self, "comment_action", None),
            getattr(self, "duplicate_action", None),
            getattr(self, "delete_line_action", None),
            getattr(self, "replace_action", None),
        ):
            if action is not None:
                action.setEnabled(editing_enabled)
        for action in (
            getattr(self, "copy_action", None),
            getattr(self, "select_all_action", None),
            getattr(self, "go_to_line_action", None),
        ):
            if action is not None:
                action.setEnabled(True)

    # ------------------------------------------------------------------
    # View behavior
    # ------------------------------------------------------------------

    def toggle_word_wrap(self, checked: bool) -> None:
        self.word_wrap = bool(checked)
        self.editor.set_word_wrap_enabled(self.word_wrap)
        self._save_preferences()

    def toggle_line_numbers(self, checked: bool) -> None:
        self.show_line_numbers = bool(checked)
        self.editor.set_line_numbers_visible(self.show_line_numbers)
        self._save_preferences()

    def toggle_menu_style(self, checked: bool) -> None:
        self.use_app_menu = bool(checked)
        self._apply_menu_style()
        self._save_preferences()

    def _apply_menu_style(self) -> None:
        self.app_menu_bar.setVisible(self.use_app_menu)
        self.menu_buttons_container.setVisible(not self.use_app_menu)

    def toggle_status_bar(self, checked: bool) -> None:
        self.show_status_bar = bool(checked)
        self.app_status_bar.setVisible(self.show_status_bar)
        self._save_preferences()

    def set_layout_mode(self, mode: int) -> None:
        if mode not in (1, 2, 3, 4):
            return
        self.layout_mode = mode
        for value, action in self.layout_actions.items():
            action.blockSignals(True)
            action.setChecked(value == mode)
            action.blockSignals(False)
        self._apply_layout_mode()
        self._save_preferences()

    def _apply_layout_mode(self) -> None:
        query = self.search_entry.text() or self.bottom_search_entry.text()
        self.search_entry.blockSignals(True)
        self.bottom_search_entry.blockSignals(True)
        self.search_entry.setText(query)
        self.bottom_search_entry.setText(query)
        self.search_entry.blockSignals(False)
        self.bottom_search_entry.blockSignals(False)

        for widget in (self.toolbar, self.editor_workspace):
            self.main_layout.removeWidget(widget)
        for widget in (self.workspace_stack, self.bottom_search):
            self.editor_column_layout.removeWidget(widget)

        split = self.layout_mode in (3, 4)
        self.search_container.setVisible(not split)
        self.bottom_search.setVisible(split)

        # Split Find belongs to the editor column only.  This deliberately
        # leaves the Library sidebar outside that vertical stack so it spans
        # the entire workspace height, matching the Timblee split geometry.
        if self.layout_mode == 4:
            self.editor_column_layout.addWidget(self.bottom_search)
            self.editor_column_layout.addWidget(self.workspace_stack, 1)
        else:
            self.editor_column_layout.addWidget(self.workspace_stack, 1)
            if self.layout_mode == 3:
                self.editor_column_layout.addWidget(self.bottom_search)

        if self.layout_mode in (1, 3):
            self.main_layout.addWidget(self.toolbar)
            self.main_layout.addWidget(self.editor_workspace, 1)
        else:
            self.main_layout.addWidget(self.editor_workspace, 1)
            self.main_layout.addWidget(self.toolbar)

    def set_drop_open_mode(self, mode: str) -> None:
        if mode not in ("active_window", "new_window"):
            return
        self.drop_open_mode = mode
        for value, action in self.drop_behaviour_actions.items():
            action.blockSignals(True)
            action.setChecked(value == mode)
            action.blockSignals(False)
        self._save_preferences()

    def choose_font(self) -> None:
        current = self.editor.font()
        selected, accepted = QFontDialog.getFont(current, self, app_dialog_title("Display Font"))
        if not accepted:
            return
        self.font_family = selected.family()
        self.font_size = selected.pointSize() if selected.pointSize() > 0 else 10
        self.font_weight = int(selected.weight())
        self.font_italic = selected.italic()
        self.editor.set_editor_font(selected)
        self._save_preferences()

    def toggle_dark_editor(self, checked: bool) -> None:
        """Switch the editor canvas/syntax independently of AppImage chrome."""
        selected = bool(checked)
        for window in tuple(OPEN_WINDOWS):
            window.dark_editor = selected
            if hasattr(window, "dark_editor_action"):
                window.dark_editor_action.blockSignals(True)
                window.dark_editor_action.setChecked(selected)
                window.dark_editor_action.blockSignals(False)
            if hasattr(window, "editor"):
                window.editor.set_color_scheme("dark" if selected else "light")
                window._apply_search_highlights()
        self._save_preferences()

    def effective_appimage_theme(self) -> str:
        """Return the one-launch override or the saved AppImage choice."""
        return self.appimage_theme_override or self.appimage_theme

    def apply_appimage_theme(
        self,
        theme: str,
        *,
        update_actions: bool = True,
    ) -> None:
        """Apply bundled AppImage QSS without changing portable/source builds."""
        if not self.appimage_theme_available:
            return
        if theme not in ("dark", "light", "system"):
            return

        application = QApplication.instance()
        if application is None:
            return

        original_palette = application.property("sheepy_pad_original_palette")
        if isinstance(original_palette, QPalette):
            application.setPalette(original_palette)

        if theme == "system":
            application.setStyleSheet("")
            original_style = application.property("sheepy_pad_original_style")
            restored_style = (
                QStyleFactory.create(str(original_style))
                if original_style
                else None
            )
            if restored_style is not None:
                application.setStyle(restored_style)
        else:
            stylesheet_path = self.appimage_theme_files.get(theme)
            if stylesheet_path is None:
                return
            try:
                stylesheet = stylesheet_path.read_text(encoding="utf-8")
            except OSError:
                return
            fusion_style = QStyleFactory.create("Fusion")
            if fusion_style is not None:
                application.setStyle(fusion_style)
            application.setStyleSheet(stylesheet)

        for window in tuple(OPEN_WINDOWS):
            if update_actions:
                action = window.appimage_dark_action
                if action is not None:
                    action.blockSignals(True)
                    action.setChecked(theme == "dark")
                    action.blockSignals(False)
                window._refresh_search_icons()

    def toggle_appimage_dark_mode(self, checked: bool) -> None:
        """Switch every AppImage window between bundled dark and light QSS."""
        if not self.appimage_theme_available:
            return
        selected_theme = "dark" if checked else "light"

        # A menu choice takes precedence over a launch-only override.
        os.environ.pop("SHEEPY_PAD_APPIMAGE_THEME", None)
        for window in tuple(OPEN_WINDOWS):
            window.appimage_theme = selected_theme
            window.appimage_theme_override = None
        self.apply_appimage_theme(selected_theme)
        self._save_preferences()

    # ------------------------------------------------------------------
    # File handling
    # ------------------------------------------------------------------

    @staticmethod
    def _document_type_items() -> tuple[str, ...]:
        return tuple(label for label, _suffix in DOCUMENT_TYPES)

    def _suffix_from_type_label(self, text: str) -> str:
        for label, suffix in DOCUMENT_TYPES:
            if text == label:
                return suffix
        return ".py"

    def _update_document_type_controls(self) -> None:
        active = self.document_active
        if hasattr(self, "document_type_menu"):
            self.document_type_menu.setEnabled(active)
        for suffix, action in getattr(self, "document_type_actions", {}).items():
            action.blockSignals(True)
            action.setChecked(active and suffix == self.document_suffix)
            action.setEnabled(active)
            action.blockSignals(False)

    def _start_type_changed(self, _index: int = -1) -> None:
        if not hasattr(self, "start_default_checkbox"):
            return
        value = self.start_type_combo.currentData()
        suffix = normalise_suffix(value if isinstance(value, str) else ".py")
        self.start_default_checkbox.blockSignals(True)
        self.start_default_checkbox.setChecked(self.default_new_suffix == suffix)
        self.start_default_checkbox.blockSignals(False)
        if not self.document_active:
            self.document_suffix = suffix
            self._sync_library_context()

    def create_from_start_page(self) -> None:
        suffix = self.start_type_combo.currentData()
        selected_suffix = normalise_suffix(suffix if isinstance(suffix, str) else ".py")
        old_default = self.default_new_suffix
        if self.start_default_checkbox.isChecked():
            self.default_new_suffix = selected_suffix
        elif self.default_new_suffix == selected_suffix:
            # Unchecking the currently configured default returns Ctrl+N to
            # the established Always Ask/New Type behaviour.
            self.default_new_suffix = None
        if self.default_new_suffix != old_default:
            self._save_preferences()
        self.new_script_document(selected_suffix)

    def new_type_document(self) -> None:
        current = self.document_suffix if self.document_active else (self.default_new_suffix or ".py")
        labels = self._document_type_items()
        current_label = next(
            (label for label, suffix in DOCUMENT_TYPES if suffix == current),
            labels[0],
        )
        selected, accepted = QInputDialog.getItem(
            self,
            app_dialog_title("New Type"),
            "Document type:",
            labels,
            labels.index(current_label),
            False,
        )
        if accepted:
            self.new_script_document(self._suffix_from_type_label(selected))

    def choose_default_new_document(self) -> None:
        labels = ("Always Ask", *self._document_type_items())
        if self.default_new_suffix is None:
            current_index = 0
        else:
            current_label = next(
                (label for label, suffix in DOCUMENT_TYPES if suffix == self.default_new_suffix),
                labels[1],
            )
            current_index = labels.index(current_label)
        selected, accepted = QInputDialog.getItem(
            self,
            app_dialog_title("Default New Document"),
            "New documents:",
            labels,
            current_index,
            False,
        )
        if not accepted:
            return
        self.default_new_suffix = (
            None if selected == "Always Ask" else self._suffix_from_type_label(selected)
        )
        self._save_preferences()
        if not self.document_active:
            self._prepare_start_page_defaults()

    def _prepare_start_page_defaults(self) -> None:
        if not hasattr(self, "start_type_combo"):
            return
        suffix = self.default_new_suffix or ".py"
        for index in range(self.start_type_combo.count()):
            if self.start_type_combo.itemData(index) == suffix:
                self.start_type_combo.setCurrentIndex(index)
                break
        self._start_type_changed()

    def set_document_type(self, suffix: str) -> None:
        if not self.document_active:
            return
        selected_suffix = normalise_suffix(suffix)
        if self.file_path is not None:
            QMessageBox.information(
                self,
                app_dialog_title("Document Type"),
                "A saved script's document type follows its filename extension. "
                "Use Save As to change the file type.",
            )
            self._update_document_type_controls()
            return
        self.document_suffix = selected_suffix
        first_line = self.editor.document().firstBlock().text()
        self.editor.set_source_language(
            source_language_for_path(f"untitled{selected_suffix}", first_line)
        )
        self._update_document_type_controls()
        self._sync_library_context()
        self._update_title()
        self._update_status()

    def _set_document_active(self, active: bool) -> None:
        """Switch between Start a Document and the real editor workspace."""
        self.document_active = bool(active)
        if hasattr(self, "workspace_stack"):
            self.workspace_stack.setCurrentWidget(
                self.editor if self.document_active else self.start_page
            )
        for host in (
            getattr(self, "search_container", None),
            getattr(self, "bottom_search", None),
        ):
            if host is not None:
                host.setEnabled(self.document_active)
        for action in (
            getattr(self, "focus_find_action", None),
            getattr(self, "find_next_action", None),
            getattr(self, "find_previous_action", None),
            getattr(self, "clear_search_action", None),
        ):
            if action is not None:
                action.setEnabled(self.document_active)
        if hasattr(self, "view_only_action"):
            self.view_only_action.setEnabled(self.document_active)
        # Re-evaluate the saved Library placement whenever document state
        # changes: no-document hides the sidebar; active documents restore it.
        self._apply_library_position()
        self._update_edit_action_state()
        self._update_file_action_state()
        self._update_document_type_controls()
        self._update_title()
        self._update_status()
        self._sync_library_context()
        self._refresh_favourites_menu()

    def _show_start_page(self) -> None:
        """Return the window to the explicit no-document state."""
        self._loading = True
        try:
            self.editor.load_text("")
        finally:
            self._loading = False
        self.file_path = None
        self.document_suffix = self.default_new_suffix or ".py"
        self.view_only = False
        self._view_only_edit_notice_shown = False
        if hasattr(self, "view_only_action"):
            self.view_only_action.blockSignals(True)
            self.view_only_action.setChecked(False)
            self.view_only_action.blockSignals(False)
        self.editor.set_view_only(False)
        self.file_encoding = "utf-8"
        self.file_bom = b""
        self.file_newline = "\n"
        self.file_disk_snapshot = None
        self.clear_search()
        if self.replace_dialog is not None:
            self.replace_dialog.close()
        self._prepare_start_page_defaults()
        self._set_document_active(False)

    def new_script_document(
        self,
        suffix: str = ".py",
        *,
        text: str = "",
        cursor_offset: int | None = None,
    ) -> None:
        """Create one unsaved runnable document with an explicit file type."""
        if self.document_active and not self.check_save_changes():
            return
        selected_suffix = normalise_suffix(suffix)
        self._loading = True
        try:
            self.editor.set_source_language(
                source_language_for_path(f"untitled{selected_suffix}", text.split("\n", 1)[0] if text else "")
            )
            self.editor.load_text(text)
        finally:
            self._loading = False
        self.file_path = None
        self.document_suffix = selected_suffix
        self.file_encoding = "utf-8"
        self.file_bom = b""
        self.file_newline = "\n"
        self.file_disk_snapshot = None
        self.clear_search()
        self._set_document_active(True)
        if cursor_offset is not None:
            cursor = self.editor.textCursor()
            cursor.setPosition(max(0, min(int(cursor_offset), len(text))))
            self.editor.setTextCursor(cursor)
        self.editor.document().setModified(bool(text))
        self._update_title()
        self.editor.setFocus()

    def _update_title(self) -> None:
        if not self.document_active:
            self.setWindowTitle(APP_NAME)
            return
        prefix = "*" if self.editor.document().isModified() else ""
        name = self.file_path.name if self.file_path else f"Untitled{self.document_suffix}"
        self.setWindowTitle(f"{prefix}{name} — {APP_NAME}")

    def _update_status(self) -> None:
        if not self.document_active:
            self.path_label.setText("No document")
            self.path_label.setToolTip("No document")
            self.operation_mode_label.setText("Insert")
            self.executable_status_label.setText("Exec: N/A")
            self.counter_label.setText("Ln: —/—, Col: —, Char: —")
            self.encoding_label.setText("—")
            return
        path = str(self.file_path) if self.file_path else f"Untitled{self.document_suffix}"
        self.path_label.setText(path)
        self.path_label.setToolTip(path)
        cursor = self.editor.textCursor()
        document = self.editor.document()
        current_line = cursor.blockNumber() + 1
        total_lines = max(1, document.blockCount())
        current_column = cursor.positionInBlock() + 1
        total_characters = max(0, document.characterCount() - 1)
        self.operation_mode_label.setText(
            "Overwrite" if self.editor.overwriteMode() else "Insert"
        )
        self.counter_label.setText(
            f"Ln: {current_line}/{total_lines}, "
            f"Col: {current_column}, Char: {total_characters}"
        )
        encoding = self.file_encoding.upper().replace("-", "-")
        if self.file_bom:
            encoding += " BOM"
        self.encoding_label.setText(encoding)

    def _on_document_text_changed(self) -> None:
        if self._loading:
            return
        if self.document_active:
            first_line = self.editor.document().firstBlock().text()
            language_path = self.file_path or Path(f"untitled{self.document_suffix}")
            self.editor.set_source_language(
                source_language_for_path(language_path, first_line)
            )
        self._update_status()
        self._schedule_search_refresh(preserve_position=True)

    def check_save_changes(self) -> bool:
        if not self.editor.document().isModified():
            return True
        answer = QMessageBox.question(
            self,
            app_dialog_title("Unsaved Changes"),
            "Do you want to save changes?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Save:
            return self.save_file()
        if answer == QMessageBox.StandardButton.Discard:
            return True
        return False

    def new_file(self) -> None:
        if self.default_new_suffix is None:
            self.new_type_document()
        else:
            self.new_script_document(self.default_new_suffix)

    def new_window(self) -> "SheepyPadWindow":
        window = SheepyPadWindow()
        window.show()
        return window

    def open_file(self) -> bool:
        start = str(self.file_path.parent if self.file_path else Path.home())
        selected, _filter = QFileDialog.getOpenFileName(
            self, app_dialog_title("Open Script File"), start, SCRIPT_FILE_FILTER
        )
        if not selected:
            return False
        return self.load_file(selected)

    def show_unsupported_file_dialog(self, rejected_count: int = 1) -> None:
        """Explain the deliberately narrow script-file scope in a visible dialog."""
        count = max(1, int(rejected_count))
        title = "Unsupported File Type" if count == 1 else "Unsupported File Types"
        detail = (
            "The selected item was not opened."
            if count == 1
            else f"{count} unsupported items were not opened."
        )
        QMessageBox.information(
            self,
            app_dialog_title(title),
            f"Sheepy Pad {APP_VERSION} opens runnable .py, .pyw, .sh, .bash, .zsh and .fish scripts only."
            f"\n\n{detail}",
            QMessageBox.StandardButton.Ok,
        )

    def load_file(
        self,
        file_path: str | Path,
        *,
        check_changes: bool = True,
        show_error: bool = True,
    ) -> bool:
        path = absolute_user_path(file_path)
        if path.suffix.casefold() not in SUPPORTED_SCRIPT_SUFFIXES:
            if show_error:
                self.show_unsupported_file_dialog()
            return False

        try:
            data, snapshot = read_regular_file(path, MAX_FILE_SIZE)
            text, encoding, bom = self._decode_source(data, path)
        except FileTooLargeError:
            if show_error:
                QMessageBox.warning(
                    self,
                    app_dialog_title("File Too Large"),
                    "Sheepy Pad does not open files larger than 25 MiB.",
                )
            return False
        except UnsupportedFileError as error:
            if show_error:
                QMessageBox.warning(self, app_dialog_title("Unsupported File"), str(error))
            return False
        except FileStateChangedError as error:
            if show_error:
                QMessageBox.warning(self, app_dialog_title("File Changed"), str(error))
            return False
        except UnicodeDecodeError as error:
            if show_error:
                QMessageBox.warning(self, app_dialog_title("Encoding Error"), str(error))
            return False
        except (OSError, MemoryError) as error:
            if show_error:
                QMessageBox.critical(self, app_dialog_title("Open Failed"), str(error))
            return False

        if self._looks_binary_text(text):
            if show_error:
                QMessageBox.warning(
                    self,
                    app_dialog_title("Unsupported File"),
                    "The file appears to contain binary control data.",
                )
            return False
        if check_changes and not self.check_save_changes():
            return False

        newline = self._detect_newline_style(text)
        normalised = text.replace("\r\n", "\n").replace("\r", "\n")
        self._loading = True
        try:
            first_line = normalised.split("\n", 1)[0] if normalised else ""
            self.editor.set_source_language(
                source_language_for_path(path, first_line)
            )
            self.editor.load_text(normalised)
        except MemoryError:
            if show_error:
                QMessageBox.critical(
                    self,
                    app_dialog_title("File Too Large"),
                    "The decoded file is too large to load safely.",
                )
            return False
        finally:
            self._loading = False

        self.file_path = path
        self.document_suffix = path.suffix.casefold()
        self.file_encoding = encoding
        self.file_bom = bom
        self.file_newline = newline
        self.file_disk_snapshot = snapshot
        self.clear_search()
        self._set_document_active(True)
        self._update_title()
        self._update_status()
        self._update_file_action_state()
        self.editor.setFocus()
        return True

    def _decode_source(
        self,
        data: bytes,
        path: Path,
    ) -> tuple[str, str, bytes]:
        bom_map = (
            (codecs.BOM_UTF32_LE, "utf-32-le"),
            (codecs.BOM_UTF32_BE, "utf-32-be"),
            (codecs.BOM_UTF8, "utf-8"),
            (codecs.BOM_UTF16_LE, "utf-16-le"),
            (codecs.BOM_UTF16_BE, "utf-16-be"),
        )
        for bom, encoding in bom_map:
            if data.startswith(bom):
                text = data[len(bom) :].decode(encoding, errors="strict")
                return text, encoding, bom

        try:
            if path.suffix.casefold() in {".py", ".pyw"}:
                detected, _lines = tokenize.detect_encoding(
                    io.BytesIO(data).readline
                )
            else:
                detected = "utf-8"
            return data.decode(detected, errors="strict"), detected, b""
        except (LookupError, SyntaxError, UnicodeDecodeError):
            system_encoding = locale.getpreferredencoding(False) or "utf-8"
            choices = [
                "Windows-1252",
                "ISO-8859-1",
                "UTF-16 LE",
                "UTF-16 BE",
                f"System encoding ({system_encoding})",
            ]
            selected, accepted = QInputDialog.getItem(
                self,
                app_dialog_title("Choose Source Encoding"),
                f"{path.name} is not valid UTF-8 or a recognised source encoding.\n\nOpen using:",
                choices,
                0,
                False,
            )
            if not accepted:
                raise UnicodeDecodeError("utf-8", data, 0, 1, "opening cancelled")
            encoding = {
                "Windows-1252": "cp1252",
                "ISO-8859-1": "iso-8859-1",
                "UTF-16 LE": "utf-16-le",
                "UTF-16 BE": "utf-16-be",
                f"System encoding ({system_encoding})": system_encoding,
            }[selected]
            return data.decode(encoding, errors="strict"), encoding, b""

    @staticmethod
    def _looks_binary_text(text: str) -> bool:
        if "\x00" in text:
            return True
        if not text:
            return False
        controls = sum(
            1
            for char in text
            if ord(char) < 32 and char not in "\t\n\r\f\b"
        )
        return controls / len(text) > 0.02

    @staticmethod
    def _detect_newline_style(content: str) -> str:
        crlf = content.count("\r\n")
        lf = content.count("\n") - crlf
        cr = content.count("\r") - crlf
        count, newline = max(((crlf, "\r\n"), (lf, "\n"), (cr, "\r")))
        return newline if count else "\n"

    @staticmethod
    def _default_created_file_mode() -> int:
        if sys.platform == "win32":
            return 0o666
        current_umask = os.umask(0)
        os.umask(current_umask)
        return 0o666 & ~current_umask

    def _external_change_action(self) -> tuple[str, FileSnapshot | None]:
        if self.file_path is None:
            return "overwrite", None
        try:
            _data, current = read_regular_file(self.file_path, MAX_FILE_SIZE)
        except FileNotFoundError:
            current = None
        except OSError as error:
            QMessageBox.warning(
                self,
                app_dialog_title("File Check Failed"),
                f"Sheepy Pad could not verify the file before saving:\n\n{error}",
            )
            return "cancel", None

        if current == self.file_disk_snapshot:
            return "overwrite", current

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle(app_dialog_title("File Changed on Disk"))
        dialog.setText("This file changed on disk after Sheepy Pad opened or saved it.")
        dialog.setInformativeText(
            "Reload discards the current Sheepy Pad edits. Save As keeps both versions. "
            "Overwrite replaces the disk copy."
        )
        reload_button = dialog.addButton(
            "Reload",
            QMessageBox.ButtonRole.AcceptRole,
        )
        save_as_button = dialog.addButton(
            "Save As",
            QMessageBox.ButtonRole.ActionRole,
        )
        overwrite_button = dialog.addButton(
            "Overwrite",
            QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_button = dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.setDefaultButton(cancel_button)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked is reload_button:
            return "reload", current
        if clicked is save_as_button:
            return "save_as", current
        if clicked is overwrite_button:
            return "overwrite", current
        return "cancel", current

    def save_file(self, *, check_external_change: bool = True) -> bool:
        if self.file_path is None:
            return self.save_as_file()

        expected = self.file_disk_snapshot
        if check_external_change:
            action, expected = self._external_change_action()
            if action == "reload":
                self.load_file(self.file_path, check_changes=False)
                return False
            if action == "save_as":
                return self.save_as_file()
            if action != "overwrite":
                return False

        content = self.editor.toPlainText()
        if self.file_newline != "\n":
            content = content.replace("\n", self.file_newline)
        try:
            payload = self.file_bom + content.encode(
                self.file_encoding,
                errors="strict",
            )
        except UnicodeEncodeError as error:
            QMessageBox.critical(
                self,
                app_dialog_title("Encoding Error"),
                f"The edited text cannot be represented as {self.file_encoding}:\n\n{error}",
            )
            return False
        if len(payload) > MAX_FILE_SIZE:
            QMessageBox.warning(
                self,
                app_dialog_title("File Too Large"),
                "The edited file exceeds Sheepy Pad's 25 MiB safety limit and was not saved.",
            )
            return False

        temporary: Path | None = None
        descriptor: int | None = None
        try:
            if expected is None:
                if path_lexists(self.file_path):
                    raise FileStateChangedError(
                        "A file appeared at the save location. Saving was cancelled."
                    )
                write_path = self.file_path
                existing_mode = self._default_created_file_mode()
            else:
                if current_file_state(self.file_path) != expected.state:
                    raise FileStateChangedError(
                        "The file changed again before Sheepy Pad could save it."
                    )
                write_path = (
                    validated_symlink_target(self.file_path, expected.state)
                    if expected.state.is_symlink
                    else self.file_path
                )
                existing_mode = expected.state.target_mode & 0o7777

            parent = write_path.parent
            descriptor, raw_path = tempfile.mkstemp(
                prefix=f".{write_path.name}.sheepy-pad-",
                suffix=".tmp",
                dir=parent,
            )
            temporary = Path(raw_path)
            if hasattr(os, "fchmod"):
                os.fchmod(descriptor, existing_mode)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = None
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())

            if expected is None:
                install_new_file_from_temp(temporary, write_path)
                temporary = None
            else:
                if current_file_state(self.file_path) != expected.state:
                    raise FileStateChangedError(
                        "The file changed again before Sheepy Pad could replace it."
                    )
                if expected.state.is_symlink and validated_symlink_target(
                    self.file_path,
                    expected.state,
                ) != write_path:
                    raise FileStateChangedError(
                        "The symbolic-link target changed before replacement."
                    )
                os.replace(temporary, write_path)
                temporary = None
            fsync_directory(parent)
        except FileStateChangedError as error:
            QMessageBox.warning(self, app_dialog_title("Save Cancelled"), str(error))
            return False
        except OSError as error:
            QMessageBox.critical(self, app_dialog_title("Save Failed"), str(error))
            return False
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if temporary is not None:
                try:
                    temporary.unlink()
                except OSError:
                    pass

        try:
            self.file_disk_snapshot = snapshot_from_payload(
                self.file_path,
                payload,
            )
        except OSError:
            self.file_disk_snapshot = None
        self.editor.mark_clean()
        self._update_title()
        self._update_status()
        self._update_file_action_state()
        self.show_status(f"Saved {self.file_path.name}")
        return True

    def save_as_file(self) -> bool:
        default_name = self.file_path if self.file_path else Path.home() / f"untitled{self.document_suffix}"
        selected, selected_filter = QFileDialog.getSaveFileName(
            self,
            app_dialog_title("Save Script File"),
            str(default_name),
            SCRIPT_FILE_FILTER,
        )
        if not selected:
            return False
        path = absolute_user_path(selected)
        if not path.suffix:
            if "Fish Scripts" in selected_filter:
                default_suffix = ".fish"
            elif "Zsh Scripts" in selected_filter:
                default_suffix = ".zsh"
            elif "Bash Scripts" in selected_filter:
                default_suffix = ".bash"
            elif "Shell Scripts" in selected_filter:
                default_suffix = ".sh"
            else:
                default_suffix = self.document_suffix
            path = path.with_suffix(default_suffix)
        if path.suffix.casefold() not in SUPPORTED_SCRIPT_SUFFIXES:
            QMessageBox.warning(
                self,
                app_dialog_title("Script Files Only"),
                "Sheepy Pad saves runnable .py, .pyw, .sh, .bash, .zsh and .fish scripts only.",
            )
            return False

        destination_snapshot: FileSnapshot | None = None
        if path_lexists(path):
            try:
                _data, destination_snapshot = read_regular_file(
                    path,
                    MAX_FILE_SIZE,
                )
            except FileTooLargeError:
                QMessageBox.warning(
                    self,
                    app_dialog_title("File Too Large"),
                    "The destination exceeds Sheepy Pad's 25 MiB safety limit.",
                )
                return False
            except OSError as error:
                QMessageBox.critical(self, app_dialog_title("Save As Failed"), str(error))
                return False
            answer = QMessageBox.question(
                self,
                app_dialog_title("Replace File"),
                f"Replace '{path.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False

        old_path = self.file_path
        old_snapshot = self.file_disk_snapshot
        self.file_path = path
        self.file_disk_snapshot = destination_snapshot
        if not self.save_file(check_external_change=False):
            self.file_path = old_path
            self.file_disk_snapshot = old_snapshot
            self._update_title()
            self._update_status()
            self._update_file_action_state()
            return False
        self.document_suffix = path.suffix.casefold()
        first_line = self.editor.toPlainText().split("\n", 1)[0]
        self.editor.set_source_language(source_language_for_path(path, first_line))
        self._update_document_type_controls()
        self._sync_library_context()
        self._refresh_favourites_menu()
        return True

    @staticmethod
    def _default_duplicate_path(source: Path) -> Path:
        """Return the first unused sibling name for a duplicate script."""
        candidate = source.with_name(f"{source.stem} copy{source.suffix}")
        number = 2
        while path_lexists(candidate):
            candidate = source.with_name(
                f"{source.stem} copy {number}{source.suffix}"
            )
            number += 1
        return candidate

    def duplicate_file(self) -> bool:
        """Write a safe copy of the current editor contents to a new path."""
        if self.file_path is None:
            QMessageBox.information(
                self,
                app_dialog_title("Duplicate File"),
                "Save the file before duplicating it.",
            )
            return False

        source = self.file_path
        try:
            _disk_payload, source_snapshot = read_regular_file(
                source,
                MAX_FILE_SIZE,
            )
        except OSError as error:
            QMessageBox.warning(
                self,
                app_dialog_title("Duplicate Cancelled"),
                str(error),
            )
            return False

        if (
            self.file_disk_snapshot is not None
            and source_snapshot != self.file_disk_snapshot
        ):
            answer = QMessageBox.question(
                self,
                app_dialog_title("File Changed on Disk"),
                "The source file changed on disk after Sheepy Pad opened or saved it.\n\n"
                "Duplicate the current editor contents anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False

        selected, _selected_filter = QFileDialog.getSaveFileName(
            self,
            app_dialog_title("Duplicate Script File"),
            str(self._default_duplicate_path(source)),
            SCRIPT_FILE_FILTER,
        )
        if not selected:
            return False

        destination = absolute_user_path(selected)
        if not destination.suffix:
            destination = destination.with_suffix(source.suffix)
        if destination.suffix.casefold() != source.suffix.casefold():
            QMessageBox.warning(
                self,
                app_dialog_title("Duplicate Cancelled"),
                f"The duplicate must keep the {source.suffix} file type.",
            )
            return False
        if destination == source:
            QMessageBox.warning(
                self,
                app_dialog_title("Duplicate Cancelled"),
                "Choose a different filename from the current file.",
            )
            return False

        content = self.editor.toPlainText()
        if self.file_newline != "\n":
            content = content.replace("\n", self.file_newline)
        try:
            payload = self.file_bom + content.encode(
                self.file_encoding,
                errors="strict",
            )
        except UnicodeEncodeError as error:
            QMessageBox.critical(
                self,
                app_dialog_title("Encoding Error"),
                f"The current text cannot be represented as {self.file_encoding}:\n\n{error}",
            )
            return False
        if len(payload) > MAX_FILE_SIZE:
            QMessageBox.warning(
                self,
                app_dialog_title("File Too Large"),
                "The duplicate would exceed Sheepy Pad's 25 MiB safety limit.",
            )
            return False

        destination_snapshot: FileSnapshot | None = None
        if path_lexists(destination):
            try:
                _existing_payload, destination_snapshot = read_regular_file(
                    destination,
                    MAX_FILE_SIZE,
                )
            except OSError as error:
                QMessageBox.warning(
                    self,
                    app_dialog_title("Duplicate Cancelled"),
                    str(error),
                )
                return False
            if (
                destination_snapshot.state.target_device
                == source_snapshot.state.target_device
                and destination_snapshot.state.target_inode
                == source_snapshot.state.target_inode
            ):
                QMessageBox.warning(
                    self,
                    app_dialog_title("Duplicate Cancelled"),
                    "The selected destination refers to the current file.",
                )
                return False
            answer = QMessageBox.question(
                self,
                app_dialog_title("Replace File"),
                f"Replace '{destination.name}' with the duplicate?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False

        temporary: Path | None = None
        descriptor: int | None = None
        try:
            descriptor, raw_path = tempfile.mkstemp(
                prefix=f".{destination.name}.sheepy-pad-duplicate-",
                suffix=".tmp",
                dir=destination.parent,
            )
            temporary = Path(raw_path)
            if hasattr(os, "fchmod"):
                os.fchmod(
                    descriptor,
                    source_snapshot.state.target_mode & 0o7777,
                )
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = None
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())

            if destination_snapshot is None:
                install_new_file_from_temp(temporary, destination)
                temporary = None
            else:
                if current_file_state(destination) != destination_snapshot.state:
                    raise FileStateChangedError(
                        "The destination changed after the replacement confirmation."
                    )
                os.replace(temporary, destination)
                temporary = None
            fsync_directory(destination.parent)
        except FileStateChangedError as error:
            QMessageBox.warning(
                self,
                app_dialog_title("Duplicate Cancelled"),
                str(error),
            )
            return False
        except OSError as error:
            QMessageBox.critical(
                self,
                app_dialog_title("Duplicate Failed"),
                str(error),
            )
            return False
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if temporary is not None:
                try:
                    temporary.unlink()
                except OSError:
                    pass

        self.show_status(f"Created duplicate {destination.name}")
        return True

    def rename_current_file(self) -> bool:
        if self.file_path is None:
            QMessageBox.information(
                self,
                app_dialog_title("Rename"),
                "Save the file before renaming it.",
            )
            return False
        if self.editor.document().isModified() and not self.save_file():
            return False

        current = self.file_path
        try:
            source_snapshot = (
                self.file_disk_snapshot
                if self.file_disk_snapshot is not None
                else read_regular_file(current, MAX_FILE_SIZE)[1]
            )
        except OSError as error:
            QMessageBox.warning(self, app_dialog_title("Rename Cancelled"), str(error))
            return False

        new_name, accepted = QInputDialog.getText(
            self,
            app_dialog_title("Rename Script File"),
            "New filename:",
            text=current.name,
        )
        if not accepted:
            return False
        new_name = new_name.strip()
        if not new_name:
            return False
        candidate = Path(new_name)
        if (
            candidate.name != new_name
            or candidate.suffix.casefold() not in SUPPORTED_SCRIPT_SUFFIXES
        ):
            QMessageBox.warning(
                self,
                app_dialog_title("Invalid Filename"),
                "Enter a filename ending in .py, .pyw, .sh, .bash, .zsh or .fish without folder separators.",
            )
            return False

        destination = current.with_name(new_name)
        if destination == current:
            return True

        destination_snapshot: FileSnapshot | None = None
        if path_lexists(destination):
            try:
                destination_snapshot = read_regular_file(
                    destination,
                    MAX_FILE_SIZE,
                )[1]
            except OSError as error:
                QMessageBox.warning(self, app_dialog_title("Rename Cancelled"), str(error))
                return False
            answer = QMessageBox.question(
                self,
                app_dialog_title("Replace File"),
                f"Replace '{destination.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False

        try:
            if current_file_state(current) != source_snapshot.state:
                raise FileStateChangedError(
                    "The source file changed before it could be renamed."
                )
            if destination_snapshot is None:
                rename_path_no_replace(current, destination)
            else:
                if current_file_state(destination) != destination_snapshot.state:
                    raise FileStateChangedError(
                        "The destination changed after the confirmation dialog."
                    )
                os.replace(current, destination)
            fsync_directory(destination.parent)
        except FileStateChangedError as error:
            QMessageBox.warning(self, app_dialog_title("Rename Cancelled"), str(error))
            return False
        except OSError as error:
            QMessageBox.critical(self, app_dialog_title("Rename Failed"), str(error))
            return False

        self.file_path = destination
        first_line = self.editor.toPlainText().split("\n", 1)[0]
        self.editor.set_source_language(
            source_language_for_path(destination, first_line)
        )
        try:
            self.file_disk_snapshot = FileSnapshot(
                state=current_file_state(self.file_path),
                digest=source_snapshot.digest,
            )
        except OSError:
            self.file_disk_snapshot = None
        self._update_title()
        self._update_status()
        self._update_file_action_state()
        self.show_status(f"Renamed file to {destination.name}")
        return True

    def delete_file(self) -> bool:
        if self.file_path is None:
            return False
        original_path = self.file_path
        if self.editor.document().isModified() and not self.check_save_changes():
            return False
        if self.file_path != original_path:
            QMessageBox.information(
                self,
                app_dialog_title("Delete Cancelled"),
                "The active file changed during Save As, so nothing was deleted.",
            )
            return False
        try:
            expected_state = (
                self.file_disk_snapshot.state
                if self.file_disk_snapshot is not None
                else current_file_state(original_path)
            )
        except OSError as error:
            QMessageBox.warning(self, app_dialog_title("Delete Cancelled"), str(error))
            return False
        answer = QMessageBox.question(
            self,
            app_dialog_title("Delete Script File"),
            f"Permanently delete '{original_path.name}'?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        if not path_identity_matches(original_path, expected_state):
            QMessageBox.warning(
                self,
                app_dialog_title("Delete Cancelled"),
                "The file was replaced after the confirmation dialog. Nothing was deleted.",
            )
            return False
        self.force_stop_script()
        try:
            original_path.unlink()
            fsync_directory(original_path.parent)
        except FileNotFoundError:
            pass
        except OSError as error:
            QMessageBox.critical(self, app_dialog_title("Delete Failed"), str(error))
            return False
        self.new_file_after_removal()
        return True

    def new_file_after_removal(self) -> None:
        self._show_start_page()
        self.show_status("File deleted from disk.")

    def set_search_query(self, query: str) -> None:
        if not self.document_active:
            return
        query = query[:MAX_SEARCH_QUERY_CHARACTERS]
        self.search_query = query
        for entry in (self.search_entry, self.bottom_search_entry):
            if entry.text() != query:
                entry.blockSignals(True)
                entry.setText(query)
                entry.blockSignals(False)
        self._schedule_search_refresh(preserve_position=False)

    def set_search_case_sensitive(self, enabled: bool) -> None:
        self.search_case_sensitive = bool(enabled)
        self._schedule_search_refresh(preserve_position=False)

    def _schedule_search_refresh(self, *, preserve_position: bool) -> None:
        if not self.search_query:
            self._search_refresh_timer.stop()
            self.search_matches = []
            self.search_match_starts = []
            self.search_match_ends = []
            self.current_search_index = -1
            self.search_results_truncated = False
            self.editor.clear_search_selections()
            self._update_search_counter()
            return
        if self._search_refresh_timer.isActive():
            self._pending_search_preserve_position = (
                self._pending_search_preserve_position and preserve_position
            )
        else:
            self._pending_search_preserve_position = preserve_position
        self._search_refresh_timer.start()

    def _run_pending_search_refresh(self) -> None:
        preserve = self._pending_search_preserve_position
        self._pending_search_preserve_position = False
        self._refresh_search_matches(preserve_position=preserve)

    def _refresh_search_matches(self, *, preserve_position: bool) -> None:
        self._search_refresh_timer.stop()
        query = self.search_query
        if not query:
            self.search_matches = []
            self.search_match_starts = []
            self.search_match_ends = []
            self.current_search_index = -1
            self.search_results_truncated = False
            self.editor.clear_search_selections()
            self._update_search_counter()
            return

        old_position = None
        if preserve_position and 0 <= self.current_search_index < len(
            self.search_matches
        ):
            old_position = self.search_matches[self.current_search_index][0]

        text = self.editor.toPlainText()
        flags = 0 if self.search_case_sensitive else re.IGNORECASE
        pattern = re.compile(re.escape(query), flags)
        matches: list[tuple[int, int]] = []
        self.search_results_truncated = False
        for match in pattern.finditer(text):
            if len(matches) >= MAX_SEARCH_MATCHES:
                self.search_results_truncated = True
                break
            matches.append(match.span())
        self.search_matches = matches
        self.search_match_starts = [start for start, _end in matches]
        self.search_match_ends = [end for _start, end in matches]

        if not matches:
            self.current_search_index = -1
        elif old_position is not None:
            insertion = bisect.bisect_left(self.search_match_starts, old_position)
            candidates = [
                index
                for index in (insertion - 1, insertion)
                if 0 <= index < len(matches)
            ]
            self.current_search_index = min(
                candidates,
                key=lambda index: abs(
                    self.search_match_starts[index] - old_position
                ),
            )
        elif not preserve_position or self.current_search_index >= len(matches):
            self.current_search_index = -1

        self._apply_search_highlights()
        self._update_search_counter()

    def _apply_search_highlights(self) -> None:
        selections = []
        (
            current_background,
            current_foreground,
            match_background,
            match_foreground,
        ) = self.editor.search_highlight_colors()
        for index, (start, end) in enumerate(self.search_matches):
            selection = QTextEdit.ExtraSelection()
            selection.cursor = QTextCursor(self.editor.document())
            selection.cursor.setPosition(start)
            selection.cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            if index == self.current_search_index:
                selection.format.setBackground(QColor(current_background))
                selection.format.setForeground(QColor(current_foreground))
            else:
                selection.format.setBackground(QColor(match_background))
                selection.format.setForeground(QColor(match_foreground))
            selections.append(selection)
        self.editor.set_search_selections(selections)

    def _update_search_counter(self) -> None:
        total = len(self.search_matches)
        current = self.current_search_index + 1 if self.current_search_index >= 0 else 0
        suffix = "+" if self.search_results_truncated else ""
        label = f"{current}/{total}{suffix}"
        self.search_counter.setText(label)
        self.bottom_search_counter.setText(label)

    def find_and_refocus(self) -> None:
        if not self.document_active:
            return
        self._refresh_search_matches(preserve_position=False)
        self.find_next()

    def find_next(self) -> bool:
        if not self.document_active:
            return False
        if not self.search_query:
            self.focus_search()
            return False
        if self._search_refresh_timer.isActive() or not self.search_matches:
            self._refresh_search_matches(preserve_position=False)
        if not self.search_matches:
            self.show_status("No matches found.")
            return False
        if self.current_search_index >= 0:
            next_index = (self.current_search_index + 1) % len(self.search_matches)
        else:
            cursor_position = self.editor.textCursor().selectionEnd()
            next_index = bisect.bisect_left(
                self.search_match_starts,
                cursor_position,
            )
            if next_index >= len(self.search_matches):
                next_index = 0
        self._select_search_match(next_index)
        return True

    def find_previous(self) -> bool:
        if not self.document_active:
            return False
        if not self.search_query:
            self.focus_search()
            return False
        if self._search_refresh_timer.isActive() or not self.search_matches:
            self._refresh_search_matches(preserve_position=False)
        if not self.search_matches:
            self.show_status("No matches found.")
            return False
        if self.current_search_index >= 0:
            index = (self.current_search_index - 1) % len(self.search_matches)
        else:
            cursor_position = self.editor.textCursor().selectionStart()
            index = bisect.bisect_right(
                self.search_match_ends,
                cursor_position,
            ) - 1
            if index < 0:
                index = len(self.search_matches) - 1
        self._select_search_match(index)
        return True

    def _select_search_match(self, index: int) -> None:
        if not (0 <= index < len(self.search_matches)):
            return
        self.current_search_index = index
        start, end = self.search_matches[index]
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)
        self.editor.ensureCursorVisible()
        self.editor.setFocus()
        self._apply_search_highlights()
        self._update_search_counter()

    def clear_search(self) -> None:
        self._search_refresh_timer.stop()
        self.search_query = ""
        self.search_matches = []
        self.search_match_starts = []
        self.search_match_ends = []
        self.current_search_index = -1
        self.search_results_truncated = False
        for entry in (self.search_entry, self.bottom_search_entry):
            entry.blockSignals(True)
            entry.clear()
            entry.blockSignals(False)
        self.editor.clear_search_selections()
        self._update_search_counter()

    def focus_search(self) -> None:
        if not self.document_active:
            return
        entry = self.bottom_search_entry if self.layout_mode in (3, 4) else self.search_entry
        entry.setFocus()
        entry.selectAll()

    def show_replace_dialog(self) -> None:
        if not self.document_active:
            return
        if self.replace_dialog is None:
            self.replace_dialog = ReplaceDialog(self)
            self.replace_dialog.finished.connect(
                lambda _result: setattr(self, "replace_dialog", None)
            )
        self.replace_dialog.prepare(self.search_query, self.search_case_sensitive)
        self.replace_dialog.set_view_only(self.view_only)
        self.replace_dialog.show()
        self.replace_dialog.raise_()
        self.replace_dialog.activateWindow()

    def replace_current(self, replacement: str) -> bool:
        if self.view_only:
            self.show_view_only_edit_prompt()
            return False
        query = self.search_query
        if not query:
            return False
        cursor = self.editor.textCursor()
        selected = cursor.selectedText().replace("\u2029", "\n")
        matches = (
            selected == query
            if self.search_case_sensitive
            else selected.casefold() == query.casefold()
        )
        if not matches:
            if not self.find_next():
                return False
            cursor = self.editor.textCursor()
            selected = cursor.selectedText().replace("\u2029", "\n")
        resulting_size = (
            max(0, self.editor.document().characterCount() - 1)
            - len(selected)
            + len(replacement)
        )
        if resulting_size > MAX_DOCUMENT_CHARACTERS:
            QMessageBox.warning(
                self,
                app_dialog_title("Replacement Too Large"),
                "The replacement would exceed Sheepy Pad's document safety limit.",
            )
            return False
        cursor.insertText(replacement)
        self.editor.setTextCursor(cursor)
        self._refresh_search_matches(preserve_position=False)
        self.find_next()
        return True

    def replace_all(self, replacement: str) -> int:
        if self.view_only:
            self.show_view_only_edit_prompt()
            return 0
        query = self.search_query
        if not query:
            return 0
        flags = 0 if self.search_case_sensitive else re.IGNORECASE
        pattern = re.compile(re.escape(query), flags)
        current = self.editor.toPlainText()
        count = sum(1 for _match in pattern.finditer(current))
        estimated_size = len(current) + count * (len(replacement) - len(query))
        if estimated_size > MAX_DOCUMENT_CHARACTERS:
            QMessageBox.warning(
                self,
                app_dialog_title("Replacement Too Large"),
                "Replace All would exceed Sheepy Pad's document safety limit.",
            )
            return 0
        updated, count = pattern.subn(lambda _match: replacement, current)
        if count:
            if not self.editor.replace_document_text(updated):
                return 0
            self._refresh_search_matches(preserve_position=False)
            suffix = "es" if count != 1 else ""
            self.show_status(f"Replaced {count:,} match{suffix}.")
        else:
            self.show_status("No matches found.")
        return count

    def go_to_line(self) -> None:
        """Move to a validated line using a plain text field without arrows."""
        maximum = max(1, self.editor.blockCount())
        current = self.editor.textCursor().blockNumber() + 1

        dialog = QDialog(self)
        dialog.setWindowTitle(app_dialog_title("Go To Line"))
        dialog.setWindowIcon(self.windowIcon())
        dialog.setModal(True)
        dialog.setMinimumWidth(310)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)
        prompt = QLabel(f"Line number (1–{maximum}):", dialog)
        line_input = QLineEdit(dialog)
        line_input.setValidator(QIntValidator(1, maximum, line_input))
        line_input.setText(str(current))
        line_input.selectAll()
        layout.addWidget(prompt)
        layout.addWidget(line_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            dialog,
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setEnabled(line_input.hasAcceptableInput())
        line_input.textChanged.connect(
            lambda _text: ok_button.setEnabled(line_input.hasAcceptableInput())
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        line_input.returnPressed.connect(
            lambda: dialog.accept() if line_input.hasAcceptableInput() else None
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.editor.go_to_line(int(line_input.text()))

    def _current_interpreter_override(self) -> str | None:
        if self.file_path is None:
            return None
        value = self.interpreter_overrides.get(self.file_path.suffix.casefold(), "").strip()
        return value or None

    def _active_environment(self, profile_name: str | None = None) -> dict[str, str]:
        selected = profile_name or self.active_environment_profile
        values = self.environment_profiles.get(selected, {})
        return dict(values)

    def _resolved_working_directory(
        self,
        *,
        show_error: bool = True,
    ) -> Path | None:
        if self.file_path is None:
            return None
        if self.working_directory_mode != "custom":
            return self.file_path.parent
        candidate = Path(self.custom_working_directory).expanduser()
        if candidate.is_dir():
            return candidate.resolve(strict=False)
        if show_error:
            QMessageBox.warning(
                self,
                app_dialog_title("Working Directory Unavailable"),
                "The selected working directory no longer exists. Choose another "
                "directory from Run → Working Directory, or return to the script folder.",
            )
        return None

    def select_interpreter(self) -> None:
        if self.file_path is None:
            QMessageBox.information(
                self,
                app_dialog_title("Select Interpreter"),
                "Open or save a runnable script first.",
            )
            return

        suffix = self.file_path.suffix.casefold()
        current_override = self.interpreter_overrides.get(suffix, "")
        shebang = self.runtime_launcher.detected_shebang(self.file_path)
        resolved = self.runtime_launcher.resolve_interpreter(
            self.file_path,
            current_override or None,
        )
        resolved_text = resolved[0] if resolved else "Not found"
        source_text = resolved[2] if resolved else "Unavailable"

        choices = ["Automatic (shebang / file type)"]
        candidates: list[str] = []
        if suffix in {".py", ".pyw"}:
            python = self.runtime_launcher.python_executable()
            if python:
                candidates.append(python)
            candidates.extend(("python3", "python"))
        elif suffix == ".sh":
            shell = self.runtime_launcher.shell_executable()
            if shell:
                candidates.append(shell)
            candidates.extend(("bash", "sh"))
        elif suffix == ".bash":
            candidates.append("bash")
        elif suffix == ".zsh":
            candidates.append("zsh")
        elif suffix == ".fish":
            candidates.append("fish")

        seen: set[str] = set()
        for candidate in candidates:
            found = self.runtime_launcher.find_host_executable(candidate)
            if found and found not in seen:
                seen.add(found)
                choices.append(found)
        if current_override and current_override not in seen:
            choices.append(current_override)
        choices.append("Choose executable...")

        prompt = (
            f"Current resolution: {resolved_text} ({source_text})\n"
            f"Shebang: {shebang or 'None'}\n\n"
            "Select the interpreter for this file type:"
        )
        current_index = 0
        if current_override in choices:
            current_index = choices.index(current_override)
        selected, accepted = QInputDialog.getItem(
            self,
            app_dialog_title("Select Interpreter"),
            prompt,
            choices,
            current_index,
            False,
        )
        if not accepted:
            return
        if selected == "Automatic (shebang / file type)":
            self.interpreter_overrides.pop(suffix, None)
        elif selected == "Choose executable...":
            start = current_override or str(Path.home())
            executable, _filter = QFileDialog.getOpenFileName(
                self,
                app_dialog_title("Choose Interpreter"),
                start,
                "Executable Files (*)",
            )
            if not executable:
                return
            resolved_custom = self.runtime_launcher.find_host_executable(executable)
            if resolved_custom is None:
                QMessageBox.warning(
                    self,
                    app_dialog_title("Invalid Interpreter"),
                    "The selected file is not an executable interpreter.",
                )
                return
            self.interpreter_overrides[suffix] = resolved_custom
        else:
            self.interpreter_overrides[suffix] = selected
        self._save_preferences()
        resolution = self.runtime_launcher.resolve_interpreter(
            self.file_path,
            self._current_interpreter_override(),
        )
        self.show_status(
            f"Interpreter: {resolution[0]} ({resolution[2]})"
            if resolution
            else "No usable interpreter is currently available."
        )

    def select_working_directory(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(app_dialog_title("Working Directory"))
        dialog.setWindowIcon(self.windowIcon())
        dialog.setModal(True)
        dialog.setMinimumWidth(560)

        layout = QVBoxLayout(dialog)
        explanation = QLabel(
            "Choose the working directory used when Sheepy Pad launches scripts. "
            "The default is the script's containing folder.",
            dialog,
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        use_script_folder = QCheckBox("Use script's containing folder", dialog)
        use_script_folder.setChecked(self.working_directory_mode != "custom")
        layout.addWidget(use_script_folder)

        row = QHBoxLayout()
        directory_input = QLineEdit(dialog)
        directory_input.setText(self.custom_working_directory)
        directory_input.setPlaceholderText(
            str(self.file_path.parent) if self.file_path is not None else str(Path.home())
        )
        browse = QPushButton("Browse...", dialog)
        row.addWidget(directory_input, 1)
        row.addWidget(browse)
        layout.addLayout(row)

        def sync_enabled() -> None:
            enabled = not use_script_folder.isChecked()
            directory_input.setEnabled(enabled)
            browse.setEnabled(enabled)

        def choose_directory() -> None:
            start = directory_input.text().strip() or (
                str(self.file_path.parent) if self.file_path is not None else str(Path.home())
            )
            selected = QFileDialog.getExistingDirectory(
                dialog,
                app_dialog_title("Choose Working Directory"),
                start,
            )
            if selected:
                directory_input.setText(selected)

        use_script_folder.toggled.connect(lambda _checked: sync_enabled())
        browse.clicked.connect(choose_directory)
        sync_enabled()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if use_script_folder.isChecked():
            self.working_directory_mode = "script"
        else:
            selected = Path(directory_input.text().strip()).expanduser()
            if not selected.is_dir():
                QMessageBox.warning(
                    self,
                    app_dialog_title("Invalid Working Directory"),
                    "Choose an existing directory.",
                )
                return
            self.working_directory_mode = "custom"
            self.custom_working_directory = str(selected.resolve(strict=False))
        self._save_preferences()
        selected_dir = self._resolved_working_directory(show_error=False)
        self.show_status(
            f"Working directory: {selected_dir}" if selected_dir else "Working directory updated."
        )

    def manage_environment_profiles(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(app_dialog_title("Environment Profiles"))
        dialog.setWindowIcon(self.windowIcon())
        dialog.setModal(True)
        dialog.setMinimumSize(640, 470)

        profiles = {name: dict(values) for name, values in self.environment_profiles.items()}
        active_profile = self.active_environment_profile
        layout = QVBoxLayout(dialog)
        intro = QLabel(
            "Profiles add environment variables to normal and terminal script launches. "
            "Use one NAME=value entry per line. Passwords and other secrets are stored "
            "as plain text in the Sheepy Pad preferences file, so do not store secrets here.",
            dialog,
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        top = QHBoxLayout()
        profile_combo = QComboBox(dialog)
        new_button = QPushButton("New", dialog)
        rename_button = QPushButton("Rename", dialog)
        delete_button = QPushButton("Delete", dialog)
        active_button = QPushButton("Set Active", dialog)
        top.addWidget(profile_combo, 1)
        top.addWidget(new_button)
        top.addWidget(rename_button)
        top.addWidget(delete_button)
        top.addWidget(active_button)
        layout.addLayout(top)

        active_label = QLabel(dialog)
        layout.addWidget(active_label)
        editor = QTextEdit(dialog)
        editor.setAcceptRichText(False)
        editor.setPlaceholderText("EXAMPLE=value\nANOTHER_VALUE=123")
        layout.addWidget(editor, 1)

        save_profile = QPushButton("Save Profile", dialog)
        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        bottom = QHBoxLayout()
        bottom.addWidget(save_profile)
        bottom.addStretch(1)
        bottom.addWidget(close_buttons)
        layout.addLayout(bottom)

        loading_profile = False

        def populate(selected_name: str | None = None) -> None:
            nonlocal loading_profile
            loading_profile = True
            profile_combo.clear()
            for name in sorted(profiles, key=lambda value: (value != "Default", value.casefold())):
                profile_combo.addItem(name)
            target = selected_name if selected_name in profiles else active_profile
            index = profile_combo.findText(target)
            if index >= 0:
                profile_combo.setCurrentIndex(index)
            loading_profile = False
            load_current()

        def load_current() -> None:
            if loading_profile:
                return
            name = profile_combo.currentText()
            editor.setPlainText(format_environment_lines(profiles.get(name, {})))
            delete_button.setEnabled(name != "Default")
            active_label.setText(f"Active profile: {active_profile}")

        def save_current(*_args) -> bool:
            name = profile_combo.currentText()
            if not name:
                return False
            raw = editor.toPlainText()
            if len(raw) > 16 * 1600:
                QMessageBox.warning(
                    dialog,
                    app_dialog_title("Profile Too Large"),
                    "The environment profile is too large.",
                )
                return False
            try:
                profiles[name] = parse_environment_lines(raw)
            except ValueError as error:
                QMessageBox.warning(
                    dialog,
                    app_dialog_title("Invalid Environment Profile"),
                    str(error),
                )
                return False
            self.environment_profiles = {key: dict(value) for key, value in profiles.items()}
            self.active_environment_profile = active_profile
            self._save_preferences()
            self.show_status(f"Saved environment profile {name}.")
            return True

        def new_profile() -> None:
            name, accepted = QInputDialog.getText(
                dialog,
                app_dialog_title("New Environment Profile"),
                "Profile name:",
            )
            name = name.strip()
            if not accepted or not name:
                return
            if len(name) > 64 or name in profiles:
                QMessageBox.warning(
                    dialog,
                    app_dialog_title("Invalid Profile Name"),
                    "Use a unique profile name of at most 64 characters.",
                )
                return
            profiles[name] = {}
            populate(name)

        def rename_profile() -> None:
            nonlocal active_profile
            old_name = profile_combo.currentText()
            if not old_name or old_name == "Default":
                return
            name, accepted = QInputDialog.getText(
                dialog,
                app_dialog_title("Rename Environment Profile"),
                "Profile name:",
                text=old_name,
            )
            name = name.strip()
            if not accepted or not name or name == old_name:
                return
            if len(name) > 64 or name in profiles:
                QMessageBox.warning(
                    dialog,
                    app_dialog_title("Invalid Profile Name"),
                    "Use a unique profile name of at most 64 characters.",
                )
                return
            profiles[name] = profiles.pop(old_name)
            if active_profile == old_name:
                active_profile = name
            populate(name)

        def delete_profile() -> None:
            nonlocal active_profile
            name = profile_combo.currentText()
            if not name or name == "Default":
                return
            answer = QMessageBox.question(
                dialog,
                app_dialog_title("Delete Environment Profile"),
                f"Delete environment profile '{name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            profiles.pop(name, None)
            if active_profile == name:
                active_profile = "Default"
            populate(active_profile)

        def set_active() -> None:
            nonlocal active_profile
            name = profile_combo.currentText()
            if not name:
                return
            if not save_current():
                return
            active_profile = name
            self.active_environment_profile = name
            self._save_preferences()
            active_label.setText(f"Active profile: {name}")
            self.show_status(f"Active environment profile: {name}")

        profile_combo.currentTextChanged.connect(lambda _name: load_current())
        save_profile.clicked.connect(save_current)
        new_button.clicked.connect(new_profile)
        rename_button.clicked.connect(rename_profile)
        delete_button.clicked.connect(delete_profile)
        active_button.clicked.connect(set_active)
        close_buttons.rejected.connect(dialog.accept)
        populate(active_profile)
        dialog.exec()
        self.environment_profiles = {key: dict(value) for key, value in profiles.items()}
        self.active_environment_profile = active_profile
        self._save_preferences()

    def run_with_arguments(self) -> bool:
        if not self._prepare_script_action() or self.file_path is None:
            return False
        if self._script_is_running():
            QMessageBox.information(
                self,
                app_dialog_title("Script Running"),
                "A script is already running in this window.",
            )
            return False

        dialog = QDialog(self)
        dialog.setWindowTitle(app_dialog_title("Run with Arguments"))
        dialog.setWindowIcon(self.windowIcon())
        dialog.setModal(True)
        dialog.setMinimumWidth(620)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        arguments_input = QLineEdit(dialog)
        arguments_input.setText(self.last_run_arguments)
        arguments_input.setPlaceholderText("--option value \"argument with spaces\"")
        form.addRow("Arguments:", arguments_input)

        profile_combo = QComboBox(dialog)
        for name in sorted(self.environment_profiles, key=str.casefold):
            profile_combo.addItem(name)
        profile_index = profile_combo.findText(self.active_environment_profile)
        if profile_index >= 0:
            profile_combo.setCurrentIndex(profile_index)
        form.addRow("Environment profile:", profile_combo)

        working_row = QWidget(dialog)
        working_layout = QHBoxLayout(working_row)
        working_layout.setContentsMargins(0, 0, 0, 0)
        working_input = QLineEdit(working_row)
        resolved_working = self._resolved_working_directory(show_error=False)
        working_input.setText(str(resolved_working) if resolved_working else "")
        browse = QPushButton("Browse...", working_row)
        working_layout.addWidget(working_input, 1)
        working_layout.addWidget(browse)
        form.addRow("Working directory:", working_row)

        interpreter = self.runtime_launcher.resolve_interpreter(
            self.file_path,
            self._current_interpreter_override(),
        )
        interpreter_label = QLabel(
            f"{interpreter[0]} ({interpreter[2]})" if interpreter else "Not available",
            dialog,
        )
        interpreter_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Interpreter:", interpreter_label)
        layout.addLayout(form)

        terminal_check = QCheckBox("Run in terminal", dialog)
        terminal_check.setChecked(self.last_run_in_terminal)
        layout.addWidget(terminal_check)

        def browse_working() -> None:
            selected = QFileDialog.getExistingDirectory(
                dialog,
                app_dialog_title("Choose Working Directory"),
                working_input.text().strip() or str(self.file_path.parent),
            )
            if selected:
                working_input.setText(selected)

        browse.clicked.connect(browse_working)
        buttons = QDialogButtonBox(dialog)
        run_button = buttons.addButton("Run", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_button = buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        run_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        layout.addWidget(buttons)
        arguments_input.setFocus()

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        try:
            extra_arguments = parse_argument_string(arguments_input.text())
        except ValueError as error:
            QMessageBox.warning(
                self,
                app_dialog_title("Invalid Arguments"),
                f"Could not parse the arguments: {error}",
            )
            return False
        working_directory = Path(working_input.text().strip()).expanduser()
        if not working_directory.is_dir():
            QMessageBox.warning(
                self,
                app_dialog_title("Invalid Working Directory"),
                "Choose an existing working directory.",
            )
            return False

        profile_name = profile_combo.currentText() or "Default"
        self.last_run_arguments = arguments_input.text()
        self.last_run_in_terminal = terminal_check.isChecked()
        self.active_environment_profile = profile_name
        self._save_preferences()
        return self._start_script_with_settings(
            extra_arguments=extra_arguments,
            terminal=terminal_check.isChecked(),
            profile_name=profile_name,
            working_directory=working_directory.resolve(strict=False),
        )

    def syntax_lint_check(self) -> bool:
        if not self._prepare_script_action() or self.file_path is None:
            return False
        resolved = self.runtime_launcher.resolve_interpreter(
            self.file_path,
            self._current_interpreter_override(),
        )
        if resolved is None:
            self._show_launch_error("No suitable interpreter was found for this script.")
            return False
        program, _prefix_arguments, source = resolved
        suffix = self.file_path.suffix.casefold()
        working_directory = self._resolved_working_directory()
        if working_directory is None:
            return False
        environment = self.runtime_launcher.subprocess_environment(
            self._active_environment()
        )

        basename = Path(program).name.casefold()
        if suffix in {".py", ".pyw"} or "python" in basename:
            compile_code = (
                "import sys,tokenize; f=tokenize.open(sys.argv[1]); "
                "s=f.read(); f.close(); compile(s,sys.argv[1],'exec')"
            )
            syntax_command = [program, "-c", compile_code, str(self.file_path)]
        elif "fish" in basename:
            syntax_command = [program, "-n", str(self.file_path)]
        elif any(shell in basename for shell in ("bash", "zsh", "sh")):
            syntax_command = [program, "-n", str(self.file_path)]
        else:
            QMessageBox.information(
                self,
                app_dialog_title("Syntax / Lint Check"),
                "The selected custom interpreter does not advertise a supported "
                "syntax-check mode. Choose Automatic or a Python, sh, bash, zsh or fish interpreter.",
            )
            return False

        try:
            syntax_result = subprocess.run(
                syntax_command,
                cwd=working_directory,
                env=environment,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            QMessageBox.critical(
                self,
                app_dialog_title("Syntax Check Failed"),
                str(error),
            )
            return False

        syntax_output = (syntax_result.stdout + syntax_result.stderr).strip()
        if syntax_result.returncode != 0:
            QMessageBox.warning(
                self,
                app_dialog_title("Syntax Check"),
                (syntax_output or "The interpreter reported a syntax error.")[:20000],
            )
            return False

        lint_command: list[str] | None = None
        lint_name = ""
        if suffix in {".py", ".pyw"} or "python" in basename:
            ruff = self.runtime_launcher.find_host_executable("ruff")
            if ruff:
                lint_command = [ruff, "check", "--no-cache", str(self.file_path)]
                lint_name = "Ruff"
        elif suffix in {".sh", ".bash"} and any(
            shell in basename for shell in ("bash", "sh")
        ):
            shellcheck = self.runtime_launcher.find_host_executable("shellcheck")
            if shellcheck:
                lint_command = [shellcheck, str(self.file_path)]
                lint_name = "ShellCheck"

        if lint_command is None:
            QMessageBox.information(
                self,
                app_dialog_title("Syntax / Lint Check"),
                f"Syntax OK using {program} ({source}).\n\n"
                "No compatible optional linter was found; the syntax check passed.",
            )
            return True

        try:
            lint_result = subprocess.run(
                lint_command,
                cwd=working_directory,
                env=environment,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            QMessageBox.warning(
                self,
                app_dialog_title("Lint Check"),
                f"Syntax OK, but {lint_name} could not complete: {error}",
            )
            return True

        lint_output = (lint_result.stdout + lint_result.stderr).strip()
        if lint_result.returncode == 0:
            QMessageBox.information(
                self,
                app_dialog_title("Syntax / Lint Check"),
                f"Syntax OK using {program} ({source}).\n{lint_name}: no issues reported.",
            )
            return True
        QMessageBox.warning(
            self,
            app_dialog_title("Lint Check"),
            (f"Syntax OK. {lint_name} reported:\n\n{lint_output}" if lint_output else f"Syntax OK. {lint_name} reported issues.")[:20000],
        )
        return True

    def _start_script_with_settings(
        self,
        *,
        extra_arguments: tuple[str, ...] = (),
        terminal: bool = False,
        profile_name: str | None = None,
        working_directory: Path | None = None,
    ) -> bool:
        if self.file_path is None:
            return False
        if self._script_is_running():
            QMessageBox.information(
                self,
                app_dialog_title("Script Running"),
                "A script is already running in this window.",
            )
            return False
        cwd = working_directory or self._resolved_working_directory()
        if cwd is None:
            return False
        environment = self._active_environment(profile_name)
        override = self._current_interpreter_override()
        if terminal:
            return self._start_terminal_run(
                extra_arguments=extra_arguments,
                interpreter_override=override,
                working_directory=cwd,
                environment=environment,
            )
        command = self.runtime_launcher.script_command(
            self.file_path,
            extra_arguments=extra_arguments,
            interpreter_override=override,
            working_directory=cwd,
            environment=environment,
        )
        if command is None:
            QMessageBox.critical(
                self,
                app_dialog_title("Launch Failed"),
                "No suitable host interpreter was found for this script. "
                "Check Run → Select Interpreter.",
            )
            return False
        self.runtime_launcher.configure_process(self.process, command)
        self.process.start()
        return True

    def _start_terminal_run(
        self,
        *,
        extra_arguments: tuple[str, ...] = (),
        interpreter_override: str | None = None,
        working_directory: Path,
        environment: dict[str, str],
    ) -> bool:
        if self.file_path is None:
            return False
        state_dir = self.runtime_paths.config_root / "terminal-sessions"
        try:
            ensure_private_directory(state_dir)
        except OSError as error:
            self._show_launch_error(f"Could not prepare terminal-session storage: {error}")
            return False

        session_token = secrets.token_hex(32)
        state_path = state_dir / f"{uuid4().hex}.json"
        command = self.runtime_launcher.script_terminal_command(
            self.file_path,
            state_path,
            session_token,
            extra_arguments=extra_arguments,
            interpreter_override=interpreter_override,
            working_directory=working_directory,
            environment=environment,
        )
        if command is None:
            self._show_launch_error(
                "No supported terminal emulator or host script interpreter was found."
            )
            return False
        started, terminal_pid = self.runtime_launcher.start_detached_with_pid(command)
        if not started:
            self._show_launch_error(f"Could not start terminal '{Path(command.program).name}'.")
            return False

        timer = QTimer(self)
        timer.setInterval(400)
        timer.timeout.connect(self._poll_terminal_session)
        self.terminal_session = {
            "state_path": state_path,
            "token": session_token,
            "script": str(absolute_user_path(self.file_path)),
            "runner": str(self.runtime_paths.config_root / "runtime" / "terminal_session_runner.py"),
            "terminal_program": command.program,
            "timer": timer,
            "started_at": time.monotonic(),
            "observed": False,
            "wrapper_pid": None,
            "child_pid": None,
            "child_pgid": None,
            "terminal_pid": terminal_pid,
            "terminal_start_time": (
                self._process_start_time(terminal_pid)
                if isinstance(terminal_pid, int)
                else None
            ),
        }
        timer.start()
        self.show_status(f"Launched {self.file_path.name} in a terminal.")
        self._update_file_action_state()
        return True


    # ------------------------------------------------------------------
    # Script actions
    # ------------------------------------------------------------------

    def _prepare_script_action(self) -> bool:
        if self.file_path is None:
            return self.save_as_file()
        if self.editor.document().isModified() and not self.save_file():
            return False
        try:
            _payload, current_snapshot = read_regular_file(
                self.file_path,
                MAX_FILE_SIZE,
            )
        except OSError:
            QMessageBox.warning(
                self,
                app_dialog_title("Script Unavailable"),
                "The script no longer exists or is not a regular file.",
            )
            self._update_file_action_state()
            return False

        if (
            self.file_disk_snapshot is not None
            and current_snapshot != self.file_disk_snapshot
        ):
            answer = QMessageBox.question(
                self,
                app_dialog_title("File Changed on Disk"),
                "The script changed on disk after Sheepy Pad loaded it. "
                "Reload the disk version before launching?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
            return self.load_file(self.file_path, check_changes=False)

        self.file_disk_snapshot = current_snapshot
        return True

    def launch_script(self) -> bool:
        if not self._prepare_script_action():
            return False
        return self._start_script_with_settings()

    def launch_in_terminal(self) -> bool:
        if not self._prepare_script_action():
            return False
        return self._start_script_with_settings(terminal=True)

    def launch_as_administrator_in_terminal(self) -> bool:
        """Explicitly launch the saved script through sudo in a terminal."""
        if not self._prepare_script_action() or self.file_path is None:
            return False
        if self._script_is_running():
            QMessageBox.information(
                self,
                app_dialog_title("Script Running"),
                "This script is already running.",
            )
            return False

        working_directory = self._resolved_working_directory()
        if working_directory is None:
            return False
        command = self.runtime_launcher.script_terminal_command(
            self.file_path,
            elevated=True,
            interpreter_override=self._current_interpreter_override(),
            working_directory=working_directory,
            environment=self._active_environment(),
        )
        if command is None:
            self._show_launch_error(
                "A supported terminal, sudo, and host script interpreter are "
                "required for an administrator launch."
            )
            return False

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle(app_dialog_title("Run as Administrator?"))
        dialog.setText(
            f"Run {self.file_path.name} with administrator privileges?"
        )
        dialog.setInformativeText(
            "The script could modify or delete system files. A terminal will "
            "open and sudo will request authentication when required; Sheepy Pad "
            "never reads or stores credentials. Elevated runs are not "
            "supervised by Sheepy Pad, so Stop "
            "and Force Stop will not control this process."
        )
        cancel_button = dialog.addButton(
            "Cancel", QMessageBox.ButtonRole.RejectRole
        )
        continue_button = dialog.addButton(
            "Continue", QMessageBox.ButtonRole.AcceptRole
        )
        dialog.setDefaultButton(cancel_button)
        dialog.setEscapeButton(cancel_button)
        dialog.exec()
        if dialog.clickedButton() is not continue_button:
            self.show_status("Administrator launch cancelled.")
            self.editor.setFocus()
            return False

        if not self.runtime_launcher.start_detached(command):
            self._show_launch_error(
                f"Could not start terminal '{Path(command.program).name}'."
            )
            return False

        self.show_status(
            f"Launched {self.file_path.name} as administrator in a terminal."
        )
        return True

    def stop_script(self) -> bool:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()
            self.show_status("Stop requested.")
            return True
        return self._stop_terminal_session(signal.SIGTERM)

    def force_stop_script(self) -> bool:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.show_status("Script force-stopped.")
            return True
        return self._stop_terminal_session(signal.SIGKILL)

    def _script_is_running(self) -> bool:
        return (
            self.process.state() != QProcess.ProcessState.NotRunning
            or self.terminal_session is not None
        )

    def _poll_terminal_session(self) -> None:
        session = self.terminal_session
        if session is None:
            return
        state_path = session.get("state_path")
        token = session.get("token")
        script = session.get("script")
        if (
            not isinstance(state_path, Path)
            or not isinstance(token, str)
            or not isinstance(script, str)
        ):
            self._finish_terminal_session()
            return
        if state_path.exists():
            payload = self._read_terminal_state(
                state_path,
                token=token,
                script=script,
            )
            if payload is not None:
                session["observed"] = True
                for key in (
                    "wrapper_pid",
                    "child_pid",
                    "child_pgid",
                    "wrapper_start_time",
                    "child_start_time",
                ):
                    try:
                        value = int(payload.get(key, 0))
                    except (TypeError, ValueError, OverflowError):
                        value = 0
                    session[key] = value if value > 0 else None

                # A terminal can disappear without letting the helper execute
                # its normal finally block (for example, when the user closes
                # a TUI terminal window). Do not trust the state file alone:
                # verify that the tracked child and wrapper still match the
                # exact processes Sheepy Pad launched. This also prevents a
                # stale state file from leaving the toolbar stuck in Stop mode.
                child_pid = session.get("child_pid")
                child_start_time = session.get("child_start_time")
                child_alive = (
                    isinstance(child_pid, int)
                    and child_pid > 0
                    and self._process_command_matches(
                        child_pid,
                        (script,),
                        expected_start_time=(
                            child_start_time
                            if isinstance(child_start_time, int)
                            else None
                        ),
                    )
                )
                runner = session.get("runner")
                wrapper_pid = session.get("wrapper_pid")
                wrapper_start_time = session.get("wrapper_start_time")
                wrapper_expected = tuple(
                    value
                    for value in (runner, token)
                    if isinstance(value, str)
                )
                wrapper_alive = (
                    isinstance(wrapper_pid, int)
                    and wrapper_pid > 0
                    and self._process_command_matches(
                        wrapper_pid,
                        wrapper_expected,
                        expected_start_time=(
                            wrapper_start_time
                            if isinstance(wrapper_start_time, int)
                            else None
                        ),
                    )
                )

                if child_alive and wrapper_alive:
                    return

                if not child_alive:
                    # Normal child completion can race very briefly with the
                    # helper's finally block removing the state file. Treat a
                    # dead child as an ordinary completed terminal run.
                    try:
                        state_path.unlink()
                    except OSError:
                        pass
                    self._finish_terminal_session()
                    self.show_status("Terminal run finished.")
                    return

                # If the terminal killed its tracking wrapper abruptly but the
                # child survived in its own session, terminate that now-orphaned
                # script group. Closing the terminal must count as stopping the
                # supervised TUI run.
                child_pgid = session.get("child_pgid")
                if (
                    isinstance(child_pgid, int)
                    and child_pgid == child_pid
                ):
                    try:
                        if hasattr(os, "killpg"):
                            os.killpg(child_pgid, signal.SIGTERM)
                        else:
                            os.kill(child_pid, signal.SIGTERM)
                    except (OSError, ProcessLookupError, PermissionError):
                        pass

                try:
                    state_path.unlink()
                except OSError:
                    pass
                self._finish_terminal_session()
                self.show_status("Terminal closed; script stopped.")
                return

        elapsed = time.monotonic() - float(session.get("started_at", 0.0))
        if bool(session.get("observed")) or elapsed > 8.0:
            if state_path.exists() and not bool(session.get("observed")):
                try:
                    state_path.unlink()
                except OSError:
                    pass
            self._finish_terminal_session()
            self.show_status("Terminal run finished.")

    @staticmethod
    def _read_terminal_state(
        state_path: Path,
        *,
        token: str,
        script: str,
    ) -> dict[str, object] | None:
        descriptor: int | None = None
        try:
            flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            flags |= getattr(os, "O_NONBLOCK", 0)
            flags |= getattr(os, "O_NOCTTY", 0)
            descriptor = os.open(state_path, flags)
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode) or details.st_size > 4096:
                return None
            if hasattr(os, "getuid") and details.st_uid != os.getuid():
                return None
            raw = os.read(descriptor, 4097)
            if len(raw) > 4096:
                return None
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                return None
            if payload.get("token") != token or payload.get("script") != script:
                return None
            return payload
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    def _finish_terminal_session(self) -> None:
        session = self.terminal_session
        self.terminal_session = None
        if session is not None:
            timer = session.get("timer")
            if isinstance(timer, QTimer):
                timer.stop()
                timer.deleteLater()
        self._update_file_action_state()

    @staticmethod
    def _process_start_time(process_id: int) -> int | None:
        """Return Linux /proc start ticks for PID-reuse protection."""
        if process_id <= 0 or not Path("/proc").is_dir():
            return None
        descriptor: int | None = None
        try:
            flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
            descriptor = os.open(Path("/proc") / str(process_id) / "stat", flags)
            raw = os.read(descriptor, 4097)
            if len(raw) > 4096:
                return None
            closing = raw.rfind(b")")
            if closing < 0:
                return None
            # Fields after the command name start at proc field 3. Start time is
            # field 22, therefore index 19 in this tail.
            fields = raw[closing + 1 :].split()
            if len(fields) <= 19:
                return None
            return int(fields[19])
        except (OSError, ValueError):
            return None
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    @classmethod
    def _process_command_matches(
        cls,
        process_id: int,
        expected_values: tuple[str, ...],
        *,
        expected_start_time: int | None = None,
        allow_program_basename: bool = False,
    ) -> bool:
        if expected_start_time is not None:
            if cls._process_start_time(process_id) != expected_start_time:
                return False
        proc_path = Path("/proc") / str(process_id) / "cmdline"
        if not Path("/proc").is_dir():
            # Never signal a detached PID that cannot be tied back to the
            # command Sheepy Pad launched. Terminal supervision is fully supported
            # on Linux, where /proc provides this identity information.
            return False
        descriptor: int | None = None
        try:
            flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
            descriptor = os.open(proc_path, flags)
            raw = os.read(descriptor, 65_537)
            if len(raw) > 65_536:
                return False
        except OSError:
            return False
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        arguments = [
            value.decode("utf-8", errors="surrogateescape")
            for value in raw.split(b"\0")
            if value
        ]
        if not arguments:
            return False
        for index, expected in enumerate(expected_values):
            if not expected:
                continue
            if expected in arguments:
                continue
            if (
                allow_program_basename
                and index == 0
                and Path(expected).name == Path(arguments[0]).name
            ):
                continue
            return False
        return True

    @classmethod
    def _signal_process(
        cls,
        process_id: object,
        sig: int,
        *,
        expected_values: tuple[str, ...] = (),
        expected_start_time: int | None = None,
        allow_program_basename: bool = False,
    ) -> bool:
        if not isinstance(process_id, int) or process_id <= 0:
            return False
        if expected_values and not cls._process_command_matches(
            process_id,
            expected_values,
            expected_start_time=expected_start_time,
            allow_program_basename=allow_program_basename,
        ):
            return False
        try:
            os.kill(process_id, sig)
            return True
        except (OSError, ProcessLookupError, PermissionError):
            return False

    def _stop_terminal_session(self, sig: int) -> bool:
        session = self.terminal_session
        if session is None:
            return False

        child_pid = session.get("child_pid")
        child_pgid = session.get("child_pgid")
        wrapper_pid = session.get("wrapper_pid")
        terminal_pid = session.get("terminal_pid")
        terminal_start_time = session.get("terminal_start_time")
        child_start_time = session.get("child_start_time")
        wrapper_start_time = session.get("wrapper_start_time")
        script = session.get("script")
        runner = session.get("runner")
        token = session.get("token")
        terminal_program = session.get("terminal_program")
        sent_signal = False

        close_terminal = sig == signal.SIGKILL or (
            not isinstance(child_pgid, int)
            and not isinstance(wrapper_pid, int)
        )
        if close_terminal:
            expected_terminal = (
                (terminal_program,)
                if isinstance(terminal_program, str)
                else ()
            )
            sent_signal = self._signal_process(
                terminal_pid,
                signal.SIGTERM,
                expected_values=expected_terminal,
                expected_start_time=(
                    terminal_start_time
                    if isinstance(terminal_start_time, int)
                    else None
                ),
                allow_program_basename=True,
            )

        child_expected = (
            (script,)
            if isinstance(script, str)
            else ()
        )
        if (
            isinstance(child_pid, int)
            and isinstance(child_pgid, int)
            and child_pid > 0
            and child_pgid == child_pid
            and self._process_command_matches(
                child_pid,
                child_expected,
                expected_start_time=(
                    child_start_time
                    if isinstance(child_start_time, int)
                    else None
                ),
            )
        ):
            try:
                if hasattr(os, "killpg"):
                    os.killpg(child_pgid, sig)
                else:
                    os.kill(child_pgid, sig)
                sent_signal = True
            except (OSError, ProcessLookupError, PermissionError):
                pass

        wrapper_expected = tuple(
            value
            for value in (runner, token)
            if isinstance(value, str)
        )
        if isinstance(wrapper_pid, int) and wrapper_pid > 0:
            wrapper_signal = (
                signal.SIGKILL if sig == signal.SIGKILL else signal.SIGTERM
            )
            sent_signal = self._signal_process(
                wrapper_pid,
                wrapper_signal,
                expected_values=wrapper_expected,
                expected_start_time=(
                    wrapper_start_time
                    if isinstance(wrapper_start_time, int)
                    else None
                ),
            ) or sent_signal

        state_path = session.get("state_path")
        if isinstance(state_path, Path):
            try:
                state_path.unlink()
            except OSError:
                pass

        self._finish_terminal_session()
        self.show_status(
            "Terminal session force-stopped."
            if sig == signal.SIGKILL
            else "Terminal session stopped."
        )
        return sent_signal

    def open_external_editor(self) -> bool:
        if self.file_path is None:
            QMessageBox.information(self, app_dialog_title("External Editor"), "Save the file first.")
            return False
        if self.editor.document().isModified() and not self.save_file():
            return False
        if self.runtime_launcher.open_in_external_editor(self.file_path):
            self.show_status(f"Opened {self.file_path.name} in an external editor.")
            return True
        return False

    def open_folder(self) -> bool:
        if self.file_path is None:
            QMessageBox.information(
                self, app_dialog_title("Open Containing Folder"), "Save the file first."
            )
            return False
        if self.runtime_launcher.open_path(self.file_path.parent):
            self.show_status(f"Opened {self.file_path.parent}.")
            return True
        return False

    def toggle_executable(self) -> bool:
        if self.file_path is None:
            QMessageBox.information(self, app_dialog_title("Executable Permission"), "Save the file first.")
            return False
        if sys.platform == "win32":
            QMessageBox.information(
                self,
                app_dialog_title("Executable Permission"),
                "Executable permission bits are not available on Windows.",
            )
            return False
        try:
            _payload, before = read_regular_file(self.file_path, MAX_FILE_SIZE)
            if (
                self.file_disk_snapshot is not None
                and before != self.file_disk_snapshot
            ):
                raise FileStateChangedError(
                    "The file changed on disk. Reload it before changing permissions."
                )
            after_state = toggle_executable_permission(
                self.file_path,
                expected=before.state,
            )
        except FileStateChangedError as error:
            QMessageBox.warning(self, app_dialog_title("Permission Change Cancelled"), str(error))
            return False
        except OSError as error:
            QMessageBox.critical(self, app_dialog_title("Permission Change Failed"), str(error))
            return False
        self.file_disk_snapshot = FileSnapshot(
            state=after_state,
            digest=before.digest,
        )
        self._update_file_action_state()
        return True

    def _update_file_action_state(self) -> None:
        exists = False
        executable = False
        if self.document_active and self.file_path is not None and path_lexists(self.file_path):
            try:
                state = current_file_state(self.file_path)
                exists = True
                executable = bool(state.target_mode & 0o111)
            except OSError:
                exists = False

        if hasattr(self, "save_action"):
            self.save_action.setEnabled(self.document_active)
            self.save_as_action.setEnabled(self.document_active)
            self.properties_action.setEnabled(self.document_active)

        for action in (
            getattr(self, "rename_action", None),
            getattr(self, "delete_action", None),
            getattr(self, "folder_action", None),
            getattr(self, "external_action", None),
            getattr(self, "duplicate_file_action", None),
            getattr(self, "executable_action", None),
        ):
            if action is not None:
                action.setEnabled(exists)

        text = "Remove Executable Permission" if executable else "Make Executable"
        if hasattr(self, "executable_action"):
            self.executable_action.setText(text)
        if hasattr(self, "executable_button"):
            self.executable_button.setEnabled(exists)
            self.executable_button.setText("Remove Exec" if executable else "Make Exec")
        if hasattr(self, "executable_status_label"):
            if sys.platform == "win32" or not exists:
                self.executable_status_label.setText("Exec: N/A")
            else:
                self.executable_status_label.setText(
                    "Exec: Yes" if executable else "Exec: No"
                )

        running = self._script_is_running()
        for action in (
            getattr(self, "launch_action", None),
            getattr(self, "terminal_action", None),
            getattr(self, "admin_action", None),
            getattr(self, "run_arguments_action", None),
            getattr(self, "lint_action", None),
            getattr(self, "interpreter_action", None),
            getattr(self, "working_directory_action", None),
            getattr(self, "environment_profiles_action", None),
        ):
            if action is not None:
                action.setEnabled(self.document_active and not running)
        if hasattr(self, "stop_action"):
            self.stop_action.setEnabled(self.document_active and running)
            self.force_stop_action.setEnabled(self.document_active and running)

        if hasattr(self, "launch_button"):
            self.launch_button.setEnabled(self.document_active and not running)
            self.terminal_button.setEnabled(self.document_active and not running)
            self.admin_button.setEnabled(self.document_active and not running)
            self.launch_button.setVisible(not running)
            self.terminal_button.setVisible(not running)
            self.admin_button.setVisible(not running)
            self.stop_button.setVisible(running)
            self.force_stop_button.setVisible(running)
            self.stop_button.setEnabled(self.document_active and running)
            self.force_stop_button.setEnabled(self.document_active and running)

        if hasattr(self, "library_sidebar"):
            self.library_sidebar._refresh_detail()
        if self.library_dialog is not None:
            self.library_dialog.panel._refresh_detail()
        self._refresh_favourites_menu()

    def _process_started(self) -> None:
        self.show_status("Script started.")
        self._update_file_action_state()

    def _process_finished(self, exit_code: int, _status) -> None:
        self.show_status(f"Script finished with exit code {exit_code}.")
        self._update_file_action_state()

    def _process_error(self, _error) -> None:
        self.show_status(self.process.errorString())
        self._update_file_action_state()

    def _show_launch_error(self, message: str) -> None:
        QMessageBox.critical(self, app_dialog_title("Launch Failed"), message)

    @staticmethod
    def _format_file_size(size: int) -> str:
        """Return a compact binary size while preserving the exact byte count."""
        if size < 1024:
            return f"{size} byte" if size == 1 else f"{size} bytes"
        units = ("KiB", "MiB", "GiB", "TiB")
        value = float(size)
        for unit in units:
            value /= 1024.0
            if value < 1024.0 or unit == units[-1]:
                return f"{value:.1f} {unit} ({size:,} bytes)"
        return f"{size:,} bytes"

    @staticmethod
    def _format_file_time(timestamp_ns: int) -> str:
        """Format a filesystem timestamp using the user's locale."""
        try:
            return time.strftime("%x %X", time.localtime(timestamp_ns / 1_000_000_000))
        except (OverflowError, OSError, ValueError):
            return "Unavailable"

    @staticmethod
    def _properties_value_label(
        text: str,
        parent: QWidget,
        *,
        wrap: bool = False,
    ) -> QLabel:
        label = QLabel(text, parent)
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        label.setWordWrap(wrap)
        return label

    def show_properties_dialog(self) -> None:
        """Show filesystem and in-editor details for the current document."""
        dialog = QDialog(self)
        dialog.setWindowTitle(app_dialog_title("Properties"))
        dialog.setWindowIcon(self.windowIcon())
        dialog.setModal(True)
        dialog.setMinimumWidth(520)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 20, 22, 16)
        layout.setSpacing(10)

        file_heading = QLabel("<b>File</b>", dialog)
        file_heading.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(file_heading)

        file_form = QFormLayout()
        file_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        file_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        path = self.file_path
        suffix = path.suffix.casefold() if path is not None else ""
        script_type = file_type_label(path) if path is not None else file_type_label(f"untitled{self.document_suffix}")

        if path is None:
            file_rows = (
                ("Name:", f"Untitled{self.document_suffix}", False),
                ("Type:", script_type, False),
                ("Location:", "Not saved", False),
                ("Size on disk:", "Not saved", False),
                ("Modified:", "Not saved", False),
                ("Permissions:", "Not available", False),
                ("Executable:", "Not available", False),
                ("Symbolic link:", "No", False),
            )
        else:
            try:
                state = current_file_state(path)
                permissions = (
                    f"{stat.filemode(state.target_mode)} "
                    f"({stat.S_IMODE(state.target_mode):04o})"
                )
                executable = "Yes" if state.target_mode & 0o111 else "No"
                symbolic_link = "Yes" if state.is_symlink else "No"
                if state.is_symlink:
                    try:
                        symbolic_link += f" → {os.readlink(path)}"
                    except OSError:
                        symbolic_link += " → target unavailable"
                file_rows = (
                    ("Name:", path.name, False),
                    ("Type:", script_type, False),
                    ("Location:", str(path.parent), True),
                    ("Full path:", str(path), True),
                    ("Size on disk:", self._format_file_size(state.size), False),
                    ("Modified:", self._format_file_time(state.mtime_ns), False),
                    ("Metadata changed:", self._format_file_time(state.ctime_ns), False),
                    ("Permissions:", permissions, False),
                    ("Executable:", executable, False),
                    ("Symbolic link:", symbolic_link, True),
                )
            except OSError as error:
                file_rows = (
                    ("Name:", path.name, False),
                    ("Type:", script_type, False),
                    ("Location:", str(path.parent), True),
                    ("Full path:", str(path), True),
                    ("Filesystem details:", f"Unavailable: {error}", True),
                )

        for title, value, wrap in file_rows:
            file_form.addRow(
                title,
                self._properties_value_label(value, dialog, wrap=wrap),
            )
        layout.addLayout(file_form)

        document_heading = QLabel("<b>Document</b>", dialog)
        document_heading.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(document_heading)

        document_form = QFormLayout()
        document_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        document_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        document = self.editor.document()
        encoding = self.file_encoding.upper()
        if self.file_bom:
            encoding += " with BOM"
        newline_name = {"\n": "LF", "\r\n": "CRLF", "\r": "CR"}.get(
            self.file_newline,
            "Unknown",
        )
        document_rows = (
            ("Encoding:", encoding),
            ("Line endings:", newline_name),
            ("Lines:", f"{max(1, document.blockCount()):,}"),
            ("Characters:", f"{max(0, document.characterCount() - 1):,}"),
            ("Unsaved changes:", "Yes" if document.isModified() else "No"),
            ("View Only:", "On" if self.view_only else "Off"),
        )
        for title, value in document_rows:
            document_form.addRow(
                title,
                self._properties_value_label(value, dialog),
            )
        layout.addLayout(document_form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, dialog)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def _documentation_path(self) -> Path | None:
        """Locate the bundled README in source, frozen and AppImage modes."""
        candidates = [
            self.runtime_paths.package_root / "docs" / "README.md",
            Path(__file__).resolve().parent / "docs" / "README.md",
        ]
        appdir = os.environ.get("APPDIR", "").strip()
        if appdir:
            candidates.append(
                Path(appdir) / "usr" / "share" / "doc" / "sheepy-pad" / "README.md"
            )
        seen: set[Path] = set()
        for candidate in candidates:
            path = absolute_user_path(candidate)
            if path in seen:
                continue
            seen.add(path)
            if path.is_file():
                return path
        return None

    def open_documentation(self) -> bool:
        """Open the bundled README with the host desktop application."""
        readme = self._documentation_path()
        if readme is None:
            QMessageBox.information(
                self,
                app_dialog_title("Documentation"),
                "The bundled README.md documentation could not be found.",
            )
            return False
        if self.runtime_launcher.open_path(readme):
            self.show_status("Opened Sheepy Pad documentation.")
            return True
        return False

    def open_github_repository(self) -> bool:
        """Open the official Sheepy Pad repository in the host browser."""
        if self.runtime_launcher.open_url(GITHUB_URL):
            self.show_status("Opened the Sheepy Pad GitHub repository.")
            return True
        return False

    def report_an_issue(self) -> bool:
        """Open the official issue tracker in the host browser."""
        if self.runtime_launcher.open_url(ISSUES_URL):
            self.show_status("Opened the Sheepy Pad issue tracker.")
            return True
        return False

    # ------------------------------------------------------------------
    # Informational dialogs
    # ------------------------------------------------------------------

    def show_shortcuts_dialog(self) -> None:
        if self.shortcuts_dialog is not None:
            self.shortcuts_dialog.show()
            self.shortcuts_dialog.raise_()
            self.shortcuts_dialog.activateWindow()
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(app_dialog_title("Keyboard Shortcuts"))
        dialog.setWindowIcon(self.windowIcon())
        dialog.setModal(False)
        dialog.setMinimumWidth(980)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(12)

        columns = QHBoxLayout()
        columns.setSpacing(22)
        layout.addLayout(columns)

        left_column = QVBoxLayout()
        middle_column = QVBoxLayout()
        right_column = QVBoxLayout()
        for column in (left_column, middle_column, right_column):
            column.setSpacing(12)
            columns.addLayout(column, 1)

        def add_section(
            column: QVBoxLayout,
            title: str,
            entries: tuple[tuple[str, str], ...],
        ) -> None:
            heading = QLabel(f"<b>{title}</b>", dialog)
            heading.setTextFormat(Qt.TextFormat.RichText)
            column.addWidget(heading)

            table = QFormLayout()
            table.setHorizontalSpacing(18)
            table.setVerticalSpacing(5)
            table.setFieldGrowthPolicy(
                QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
            )
            for action_name, shortcut in entries:
                action_label = QLabel(action_name, dialog)
                shortcut_label = QLabel(shortcut, dialog)
                shortcut_label.setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                table.addRow(action_label, shortcut_label)
            column.addLayout(table)

        add_section(
            left_column,
            "Application and Files",
            (
                ("New", "Ctrl+N"),
                ("New Window", "Ctrl+Shift+N"),
                ("Open", "Ctrl+O"),
                ("Save", "Ctrl+S"),
                ("Save As", "Ctrl+Shift+S"),
                ("Documentation", "F1"),
                ("Exit", "Ctrl+Q"),
            ),
        )
        add_section(
            left_column,
            "More Actions",
            (
                ("Open in External Editor", "Ctrl+Shift+E"),
                ("Rename", "F2"),
                ("Duplicate File", "Ctrl+Shift+D"),
                ("Open Containing Folder", "Ctrl+Shift+O"),
                ("Make / Remove Executable", "Ctrl+Shift+X"),
            ),
        )
        left_column.addStretch(1)

        add_section(
            middle_column,
            "Editing",
            (
                ("Undo", "Ctrl+Z"),
                ("Redo", "Ctrl+Y"),
                ("Cut", "Ctrl+X"),
                ("Copy", "Ctrl+C"),
                ("Paste", "Ctrl+V"),
                ("Delete", "Delete"),
                ("Toggle Comment", "Ctrl+/"),
                ("Duplicate Line / Selection", "Ctrl+D"),
                ("Delete Line", "Ctrl+Shift+K"),
                ("Select All", "Ctrl+A"),
            ),
        )
        middle_column.addStretch(1)

        add_section(
            right_column,
            "Search and Navigation",
            (
                ("Find", "Ctrl+F"),
                ("Next Match", "F3"),
                ("Previous Match", "Shift+F3"),
                ("Replace", "Ctrl+H"),
                ("Go To Line", "Ctrl+G"),
            ),
        )
        add_section(
            right_column,
            "Run",
            (
                ("Launch", "F5"),
                ("Launch in Terminal", "Ctrl+1"),
                ("Launch as Admin", "Ctrl+Shift+1"),
                ("Run with Arguments", "Ctrl+2"),
                ("Syntax / Lint Check", "Ctrl+3"),
                ("Select Interpreter", "Ctrl+4"),
                ("Working Directory", "Ctrl+5"),
                ("Environment Profiles", "Ctrl+6"),
                ("Library", "Ctrl+L"),
                ("Stop", "Shift+F5"),
                ("Force Stop", "Ctrl+Shift+F5"),
            ),
        )
        right_column.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        buttons.rejected.connect(dialog.close)
        layout.addWidget(buttons)
        dialog.finished.connect(
            lambda _result: setattr(self, "shortcuts_dialog", None)
        )
        self.shortcuts_dialog = dialog
        dialog.show()

    def show_about_dialog(self) -> None:
        if self.about_dialog is not None:
            self.about_dialog.show()
            self.about_dialog.raise_()
            self.about_dialog.activateWindow()
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(app_dialog_title("About"))
        dialog.setWindowIcon(self.windowIcon())
        dialog.setModal(False)
        dialog.setMinimumWidth(390)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(10)

        if self.runtime_paths.icon_path.is_file():
            logo = QLabel(dialog)
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = QPixmap(str(self.runtime_paths.icon_path))
            if not pixmap.isNull():
                logo.setPixmap(
                    pixmap.scaled(
                        112,
                        112,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                layout.addWidget(logo)

        application_name = QLabel(f"<h2>{APP_NAME}</h2>", dialog)
        application_name.setTextFormat(Qt.TextFormat.RichText)
        application_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(application_name)

        version = QLabel(f"Version {APP_VERSION}", dialog)
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        tagline = QLabel("<b>Friendly. Fast. Focused.</b>", dialog)
        tagline.setTextFormat(Qt.TextFormat.RichText)
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tagline)

        description = QLabel(
            "A lightweight standalone editor for runnable Python, shell and Fish scripts, "
            "combining focused source editing with practical launch tools.",
            dialog,
        )
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(description)

        preferences_path = html.escape(str(self.config_file))
        details = QLabel(
            f"<a href='{GITHUB_URL}'>"
            f"{GITHUB_URL}</a><br>"
            "Built on Python, PyQt6, Python Lair 2 and the Nuxpad 2 "
            "interface framework.<br>"
            f"<b>Preferences:</b> {preferences_path}<br><br>"
            "Copyright © 2026 Bruno Machado<br>"
            "[<a href='https://github.com/brunonlinespace/'>"
            "https://github.com/brunonlinespace/</a>]<br>"
            "Licensed under the GNU General Public License v3 or later.",
            dialog,
        )
        details.setTextFormat(Qt.TextFormat.RichText)
        details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        details.setOpenExternalLinks(True)
        details.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        layout.addWidget(details)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, dialog)
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText("OK")
        buttons.accepted.connect(dialog.close)
        layout.addWidget(buttons)
        dialog.finished.connect(lambda _result: setattr(self, "about_dialog", None))
        self.about_dialog = dialog
        dialog.show()

    # ------------------------------------------------------------------
    # Drag/drop and lifecycle
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls() and any(
            url.isLocalFile() for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls() and any(
            url.isLocalFile() for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        self.open_dropped_files(paths)
        event.acceptProposedAction()

    def open_dropped_files(self, paths: list[str]) -> None:
        script_files: list[Path] = []
        unsupported_types = 0
        invalid_items = 0
        for raw_path in paths:
            path = absolute_user_path(raw_path)
            if path.suffix.casefold() not in SUPPORTED_SCRIPT_SUFFIXES:
                unsupported_types += 1
                continue
            try:
                current_file_state(path)
            except OSError:
                invalid_items += 1
                continue
            script_files.append(path)

        if unsupported_types:
            self.show_unsupported_file_dialog(unsupported_types)
        rejected = unsupported_types + invalid_items
        if rejected:
            suffix = "s" if rejected != 1 else ""
            self.show_status(
                f"Ignored {rejected} item{suffix}; Sheepy Pad opens supported runnable script files only."
            )
        if not script_files:
            return

        remaining = iter(script_files)
        if self.drop_open_mode == "active_window":
            if not self.check_save_changes():
                return
            for first in remaining:
                if self.load_file(first, check_changes=False):
                    break
            else:
                return

        for path in remaining:
            window = SheepyPadWindow()
            if window.load_file(path, check_changes=False):
                window.show()
            else:
                window.close()

    def editor_undo(self) -> None:
        if not self.view_only:
            self.editor.undo()

    def editor_redo(self) -> None:
        if not self.view_only:
            self.editor.redo()

    def show_status(self, message: str) -> None:
        self.statusBar().showMessage(message, 5000)

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self.check_save_changes():
            event.ignore()
            return
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(1000):
                self.process.kill()
        if self.terminal_session is not None:
            self._stop_terminal_session(signal.SIGTERM)
        self._save_preferences()
        event.accept()


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sheepy Pad runnable script editor"
    )
    parser.add_argument("files", nargs="*", help="Runnable script files to open")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    parser.add_argument(
        "--appimage-theme",
        choices=("dark", "light", "system"),
        help="Override AppImage chrome theme for this launch.",
    )
    parser.add_argument(
        "--sheepy-pad-smoke-test",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(sys.argv[1:] if argv is None else argv)
    if arguments.appimage_theme:
        os.environ["SHEEPY_PAD_APPIMAGE_THEME"] = arguments.appimage_theme
    application = QApplication(sys.argv[:1])
    application.setApplicationName(APP_NAME)
    application.setApplicationVersion(APP_VERSION)
    application.setOrganizationName("brunonlinespace")
    application.setDesktopFileName("sheepy-pad")
    application.setQuitOnLastWindowClosed(True)
    runtime_paths = RuntimePaths.detect(
        Path(__file__).resolve().parents[1] / "main.py"
    )
    if runtime_paths.icon_path.is_file():
        application.setWindowIcon(QIcon(str(runtime_paths.icon_path)))
    application.setProperty("sheepy_pad_original_palette", QPalette(application.palette()))
    application.setProperty("sheepy_pad_original_style", application.style().objectName())

    valid_files = [
        absolute_user_path(value)
        for value in arguments.files
        if Path(value).suffix.casefold() in SUPPORTED_SCRIPT_SUFFIXES
    ]
    unsupported_files = [
        value
        for value in arguments.files
        if Path(value).suffix.casefold() not in SUPPORTED_SCRIPT_SUFFIXES
    ]
    window = SheepyPadWindow()
    if arguments.sheepy_pad_smoke_test:
        window.show()
        application.processEvents()
        if window.windowTitle() and application.applicationName() == APP_NAME:
            print("GUI smoke test passed.", flush=True)
            window.close()
            application.processEvents()
            return 0
        window.close()
        application.processEvents()
        return 1

    primary_loaded = False
    extra_windows: list[SheepyPadWindow] = []
    for path in valid_files:
        if not primary_loaded:
            primary_loaded = window.load_file(path, check_changes=False)
            continue
        extra = SheepyPadWindow()
        if extra.load_file(path, check_changes=False):
            extra_windows.append(extra)
        else:
            extra.close()

    window.show()
    for extra in extra_windows:
        extra.show()
    if unsupported_files:
        QTimer.singleShot(
            0,
            lambda count=len(unsupported_files): window.show_unsupported_file_dialog(
                count
            ),
        )
    return application.exec()
