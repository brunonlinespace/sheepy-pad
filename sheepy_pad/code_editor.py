# Python Lair 2
# Copyright (C) 2026 Bruno Machado
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
"""
Python Lair 2
widgets/code_editor.py

Optimized Python, POSIX-shell and Fish source-code editor used by Sheepy Pad.

Features:
- line-number gutter
- Python, POSIX-shell and Fish syntax highlighting
- current-line highlighting
- matching-bracket highlighting
- automatic indentation
- Tab / Shift+Tab indentation
- Ctrl+/ comment toggling
- Ctrl+D line duplication
- Ctrl+G go-to-line signal
- Qt-native document modification tracking

The editor does not know about Module objects, the repository, or files on disk.
Those responsibilities remain in the editor-page/controller layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from PyQt6.QtCore import QMimeData, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QInputMethodEvent,
    QKeyEvent,
    QKeySequence,
    QPainter,
    QTextCharFormat,
    QTextCursor,
    QSyntaxHighlighter,
    QTextDocument,
)
from PyQt6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget


@dataclass(frozen=True, slots=True)
class HighlightRule:
    """One regular-expression syntax-highlighting rule."""

    pattern: re.Pattern[str]
    text_format: QTextCharFormat


EDITOR_COLOR_SCHEMES: dict[str, dict[str, str]] = {
    "dark": {
        "background": "#1e1e1e",
        "foreground": "#d4d4d4",
        "border": "#3f3f46",
        "selection_background": "#264f78",
        "selection_foreground": "#ffffff",
        "gutter_background": "#181818",
        "gutter_current": "#c6c6c6",
        "gutter_foreground": "#858585",
        "current_line": "#2a2d2e",
        "bracket_background": "#3b514d",
        "bracket_foreground": "#ffffff",
        "search_current_background": "#d7ba7d",
        "search_current_foreground": "#1e1e1e",
        "search_background": "#5a4a00",
        "search_foreground": "#ffffff",
        "keyword": "#c586c0",
        "builtin": "#4ec9b0",
        "number": "#b5cea8",
        "string": "#ce9178",
        "comment": "#6a9955",
        "definition": "#dcdcaa",
        "self": "#9cdcfe",
        "shebang": "#569cd6",
    },
    "light": {
        "background": "#ffffff",
        "foreground": "#202124",
        "border": "#aeb4ba",
        "selection_background": "#b8d7f0",
        "selection_foreground": "#101214",
        "gutter_background": "#f0f2f4",
        "gutter_current": "#202124",
        "gutter_foreground": "#687078",
        "current_line": "#eef5fb",
        "bracket_background": "#c8e6c9",
        "bracket_foreground": "#16351b",
        "search_current_background": "#f4c95d",
        "search_current_foreground": "#202124",
        "search_background": "#fff1a8",
        "search_foreground": "#202124",
        "keyword": "#7b2f91",
        "builtin": "#006b6b",
        "number": "#805000",
        "string": "#a31515",
        "comment": "#2e7d32",
        "definition": "#795e26",
        "self": "#005a9c",
        "shebang": "#005a9c",
    },
}


def _normalise_color_scheme(name: str) -> str:
    return "light" if name == "light" else "dark"


class SourceHighlighter(QSyntaxHighlighter):
    """Shared helpers for lightweight source-code highlighters."""

    @staticmethod
    def _format(
        color: str,
        *,
        bold: bool = False,
        italic: bool = False,
    ) -> QTextCharFormat:
        text_format = QTextCharFormat()
        text_format.setForeground(QColor(color))
        text_format.setFontWeight(
            QFont.Weight.Bold if bold else QFont.Weight.Normal
        )
        text_format.setFontItalic(italic)
        return text_format

    def _apply_rules(self, text: str, rules: tuple[HighlightRule, ...]) -> None:
        for rule in rules:
            for match in rule.pattern.finditer(text):
                if match.lastindex:
                    start, end = match.span(match.lastindex)
                else:
                    start, end = match.span()
                self.setFormat(start, end - start, rule.text_format)


class PythonHighlighter(SourceHighlighter):
    """Lightweight Python syntax highlighter using Python Lair colours."""

    _KEYWORDS = (
        "False", "None", "True", "and", "as", "assert", "async", "await",
        "break", "class", "continue", "def", "del", "elif", "else", "except",
        "finally", "for", "from", "global", "if", "import", "in", "is",
        "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
        "while", "with", "yield", "match", "case",
    )

    _BUILTINS = (
        "abs", "all", "any", "ascii", "bin", "bool", "breakpoint", "bytearray",
        "bytes", "callable", "chr", "classmethod", "compile", "complex", "delattr",
        "dict", "dir", "divmod", "enumerate", "eval", "exec", "filter", "float",
        "format", "frozenset", "getattr", "globals", "hasattr", "hash", "help",
        "hex", "id", "input", "int", "isinstance", "issubclass", "iter", "len",
        "list", "locals", "map", "max", "memoryview", "min", "next", "object",
        "oct", "open", "ord", "pow", "print", "property", "range", "repr",
        "reversed", "round", "set", "setattr", "slice", "sorted", "staticmethod",
        "str", "sum", "super", "tuple", "type", "vars", "zip", "__import__",
    )

    def __init__(
        self,
        document: QTextDocument,
        color_scheme: str = "dark",
    ) -> None:
        super().__init__(document)
        colors = EDITOR_COLOR_SCHEMES[_normalise_color_scheme(color_scheme)]

        keyword_format = self._format(colors["keyword"], bold=True)
        builtin_format = self._format(colors["builtin"])
        number_format = self._format(colors["number"])
        string_format = self._format(colors["string"])
        comment_format = self._format(colors["comment"], italic=True)
        decorator_format = self._format(colors["definition"])
        definition_format = self._format(colors["definition"], bold=True)
        self_format = self._format(colors["self"], italic=True)

        keyword_pattern = (
            r"\b(?:" + "|".join(map(re.escape, self._KEYWORDS)) + r")\b"
        )
        builtin_pattern = (
            r"\b(?:" + "|".join(map(re.escape, self._BUILTINS)) + r")\b"
        )

        self._rules = (
            HighlightRule(re.compile(keyword_pattern), keyword_format),
            HighlightRule(re.compile(builtin_pattern), builtin_format),
            HighlightRule(
                re.compile(
                    r"\b(?:0[xX][0-9a-fA-F]+|0[bB][01]+|0[oO][0-7]+|"
                    r"\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)\b"
                ),
                number_format,
            ),
            HighlightRule(re.compile(r"#[^\n]*"), comment_format),
            HighlightRule(
                re.compile(r"@[A-Za-z_][A-Za-z0-9_.]*"),
                decorator_format,
            ),
            HighlightRule(
                re.compile(r"\b(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)"),
                definition_format,
            ),
            HighlightRule(re.compile(r"\bself\b|\bcls\b"), self_format),
            HighlightRule(re.compile(r"'(?:\\.|[^'\\])*'"), string_format),
            HighlightRule(re.compile(r'"(?:\\.|[^"\\])*"'), string_format),
        )

        self._multiline_string_format = string_format
        self._triple_single = re.compile("'''")
        self._triple_double = re.compile('\"\"\"')

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt API name
        self._apply_rules(text, self._rules)
        self.setCurrentBlockState(0)

        # State 1 = triple single-quoted string; state 2 = triple double-quoted.
        if self.previousBlockState() == 1:
            start = 0
            delimiter = self._triple_single
        elif self.previousBlockState() == 2:
            start = 0
            delimiter = self._triple_double
        else:
            single_match = self._triple_single.search(text)
            double_match = self._triple_double.search(text)
            candidates = [
                (match.start(), delimiter, state)
                for match, delimiter, state in (
                    (single_match, self._triple_single, 1),
                    (double_match, self._triple_double, 2),
                )
                if match is not None
            ]
            if not candidates:
                return

            start, delimiter, state = min(candidates, key=lambda item: item[0])
            start += 3
            end_match = delimiter.search(text, start)
            if end_match is None:
                self.setFormat(
                    start - 3,
                    len(text) - start + 3,
                    self._multiline_string_format,
                )
                self.setCurrentBlockState(state)
                return
            self.setFormat(
                start - 3,
                end_match.end() - start + 3,
                self._multiline_string_format,
            )
            return

        state = 1 if delimiter is self._triple_single else 2
        end_match = delimiter.search(text, start)
        if end_match is None:
            self.setFormat(0, len(text), self._multiline_string_format)
            self.setCurrentBlockState(state)
        else:
            self.setFormat(0, end_match.end(), self._multiline_string_format)


class ShellHighlighter(SourceHighlighter):
    """Lightweight POSIX/Bash shell syntax highlighter."""

    _KEYWORDS = (
        "if", "then", "elif", "else", "fi", "for", "while", "until", "do",
        "done", "case", "esac", "in", "select", "function", "time", "coproc",
    )
    _BUILTINS = (
        "alias", "bg", "bind", "break", "builtin", "caller", "cd", "command",
        "compgen", "complete", "continue", "declare", "dirs", "disown", "echo",
        "enable", "eval", "exec", "exit", "export", "false", "fc", "fg",
        "getopts", "hash", "help", "history", "jobs", "kill", "let", "local",
        "logout", "mapfile", "popd", "printf", "pushd", "pwd", "read",
        "readarray", "readonly", "return", "set", "shift", "shopt", "source",
        "suspend", "test", "times", "trap", "true", "type", "typeset",
        "ulimit", "umask", "unalias", "unset", "wait",
    )

    def __init__(
        self,
        document: QTextDocument,
        color_scheme: str = "dark",
    ) -> None:
        super().__init__(document)
        colors = EDITOR_COLOR_SCHEMES[_normalise_color_scheme(color_scheme)]
        keyword_format = self._format(colors["keyword"], bold=True)
        builtin_format = self._format(colors["builtin"])
        number_format = self._format(colors["number"])
        string_format = self._format(colors["string"])
        comment_format = self._format(colors["comment"], italic=True)
        function_format = self._format(colors["definition"], bold=True)
        variable_format = self._format(colors["self"])
        shebang_format = self._format(colors["shebang"], bold=True)

        keyword_pattern = (
            r"\b(?:" + "|".join(map(re.escape, self._KEYWORDS)) + r")\b"
        )
        builtin_pattern = (
            r"\b(?:" + "|".join(map(re.escape, self._BUILTINS)) + r")\b"
        )
        self._rules = (
            HighlightRule(re.compile(keyword_pattern), keyword_format),
            HighlightRule(re.compile(builtin_pattern), builtin_format),
            HighlightRule(
                re.compile(r"\b(?:0[xX][0-9a-fA-F]+|\d+)\b"),
                number_format,
            ),
            HighlightRule(
                re.compile(
                    r"\$\{[^}\n]+\}|\$[A-Za-z_][A-Za-z0-9_]*|"
                    r"\$[?#@*!$0-9-]"
                ),
                variable_format,
            ),
            HighlightRule(
                re.compile(
                    r"(?:^|[;\s])(?:function\s+)?"
                    r"([A-Za-z_][A-Za-z0-9_]*)\s*\(\)"
                ),
                function_format,
            ),
            HighlightRule(re.compile(r"#[^\n]*"), comment_format),
            HighlightRule(re.compile(r"'(?:[^']*)'"), string_format),
            HighlightRule(re.compile(r'"(?:\\.|[^"\\])*"'), string_format),
            HighlightRule(re.compile(r"^#!.*$"), shebang_format),
        )

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt API name
        self._apply_rules(text, self._rules)


class FishHighlighter(SourceHighlighter):
    """Fish-shell syntax highlighter with Fish-specific commands and variables."""

    _KEYWORDS = (
        "and", "begin", "break", "case", "command", "continue", "else", "end",
        "for", "function", "if", "in", "not", "or", "return", "switch", "while",
    )
    _BUILTINS = (
        "abbr", "argparse", "bg", "bind", "block", "builtin", "cd", "command",
        "commandline", "complete", "contains", "count", "disown", "echo", "emit",
        "eval", "exec", "exit", "fg", "fish", "fish_add_path", "fish_config",
        "fish_indent", "fish_key_reader", "functions", "history", "jobs", "math",
        "path", "printf", "pwd", "random", "read", "realpath", "set", "source",
        "status", "string", "test", "time", "trap", "type", "ulimit", "umask",
        "wait",
    )

    def __init__(
        self,
        document: QTextDocument,
        color_scheme: str = "dark",
    ) -> None:
        super().__init__(document)
        colors = EDITOR_COLOR_SCHEMES[_normalise_color_scheme(color_scheme)]
        keyword_format = self._format(colors["keyword"], bold=True)
        builtin_format = self._format(colors["builtin"])
        number_format = self._format(colors["number"])
        string_format = self._format(colors["string"])
        comment_format = self._format(colors["comment"], italic=True)
        function_format = self._format(colors["definition"], bold=True)
        variable_format = self._format(colors["self"])
        shebang_format = self._format(colors["shebang"], bold=True)

        keyword_pattern = r"\b(?:" + "|".join(map(re.escape, self._KEYWORDS)) + r")\b"
        builtin_pattern = r"\b(?:" + "|".join(map(re.escape, self._BUILTINS)) + r")\b"
        self._rules = (
            HighlightRule(re.compile(keyword_pattern), keyword_format),
            HighlightRule(re.compile(builtin_pattern), builtin_format),
            HighlightRule(re.compile(r"\b(?:0[xX][0-9a-fA-F]+|\d+(?:\.\d+)?)\b"), number_format),
            HighlightRule(
                re.compile(r"\$\$|\$[A-Za-z_][A-Za-z0-9_]*|\$argv(?:\[[^]\n]+\])?"),
                variable_format,
            ),
            HighlightRule(
                re.compile(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_:-]*)"),
                function_format,
            ),
            HighlightRule(re.compile(r"#[^\n]*"), comment_format),
            HighlightRule(re.compile(r"'(?:\\.|[^'\\])*'"), string_format),
            HighlightRule(re.compile(r'"(?:\\.|[^"\\])*"'), string_format),
            HighlightRule(re.compile(r"^#!.*$"), shebang_format),
        )

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt API name
        self._apply_rules(text, self._rules)


class LineNumberArea(QWidget):
    """Narrow child widget that paints visible line numbers."""

    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API name
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API name
        self._editor.paint_line_number_area(event)


class CodeEditor(QPlainTextEdit):
    """Reusable source-code editor for Python, shell and Fish scripts."""

    go_to_line_requested = pyqtSignal()
    paste_rejected = pyqtSignal(str)
    view_only_edit_attempt = pyqtSignal()
    overwrite_mode_changed = pyqtSignal(bool)
    files_dropped = pyqtSignal(list)

    BRACKET_PAIRS = {
        "(": ")",
        "[": "]",
        "{": "}",
        ")": "(",
        "]": "[",
        "}": "{",
    }

    OPENING_BRACKETS = "([{"
    CLOSING_BRACKETS = ")] }".replace(" ", "")
    MAX_PASTE_CHARACTERS = 5_000_000
    MAX_DOCUMENT_CHARACTERS = 25_000_000
    MAX_BRACKET_SCAN_CHARACTERS = 250_000

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._line_number_area = LineNumberArea(self)
        self._language = "python"
        self._color_scheme = "dark"
        self._highlighter: QSyntaxHighlighter = PythonHighlighter(
            self.document(), self._color_scheme
        )
        self._tab_width_spaces = 4
        self._line_numbers_visible = True
        self._search_selections: list[QTextEdit.ExtraSelection] = []
        self._refreshing_extra_selections = False
        self._pending_full_paste: str | None = None
        self._full_paste_generation = 0

        fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        fixed_font.setPointSize(10)
        self.setFont(fixed_font)

        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(
            self.fontMetrics().horizontalAdvance(" ") * self._tab_width_spaces
        )
        self.setUndoRedoEnabled(True)
        self.setCenterOnScroll(False)

        self._decoration_timer = QTimer(self)
        self._decoration_timer.setSingleShot(True)
        self._decoration_timer.setInterval(0)
        self._decoration_timer.timeout.connect(self._refresh_extra_selections)

        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._schedule_decoration_refresh)
        self.textChanged.connect(self._schedule_decoration_refresh)

        self._update_line_number_area_width()
        self._schedule_decoration_refresh()

        self._apply_color_scheme()

    def set_source_language(self, language: str) -> None:
        """Switch syntax colouring and language-aware indentation."""
        selected = language if language in {"python", "shell", "fish"} else "python"
        if selected == self._language:
            return
        self._language = selected
        self._replace_highlighter()

    def set_color_scheme(self, color_scheme: str) -> None:
        """Apply a complete dark or light editor and syntax palette."""
        selected = _normalise_color_scheme(color_scheme)
        if selected == self._color_scheme:
            self._apply_color_scheme()
            return
        self._color_scheme = selected
        self._replace_highlighter()
        self._apply_color_scheme()

    @property
    def color_scheme(self) -> str:
        """Return the active editor colour scheme."""
        return self._color_scheme

    def search_highlight_colors(self) -> tuple[str, str, str, str]:
        """Return current-match and ordinary-match colours for the scheme."""
        colors = EDITOR_COLOR_SCHEMES[self._color_scheme]
        return (
            colors["search_current_background"],
            colors["search_current_foreground"],
            colors["search_background"],
            colors["search_foreground"],
        )

    def _replace_highlighter(self) -> None:
        old_highlighter = self._highlighter
        old_highlighter.setDocument(None)
        highlighter_type = {
            "python": PythonHighlighter,
            "shell": ShellHighlighter,
            "fish": FishHighlighter,
        }[self._language]
        self._highlighter = highlighter_type(
            self.document(), self._color_scheme
        )
        old_highlighter.deleteLater()
        self._schedule_decoration_refresh()

    def _apply_color_scheme(self) -> None:
        colors = EDITOR_COLOR_SCHEMES[self._color_scheme]
        self.setStyleSheet(
            f"""
            QPlainTextEdit {{
                background: {colors['background']};
                color: {colors['foreground']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                selection-background-color: {colors['selection_background']};
                selection-color: {colors['selection_foreground']};
                padding: 4px 4px 4px 0;
            }}
            """
        )
        self._line_number_area.update()
        self.viewport().update()
        self._schedule_decoration_refresh()

    def set_view_only(self, enabled: bool) -> None:
        """Enable or disable the hardened read-only editor mode."""
        enabled = bool(enabled)
        if enabled:
            self._pending_full_paste = None
            self._full_paste_generation += 1
        self.setReadOnly(enabled)
        self._schedule_decoration_refresh()

    def set_tab_width_spaces(self, spaces: int) -> None:
        """Set logical Tab width and update the displayed tab stop."""
        self._tab_width_spaces = max(1, spaces)
        self.setTabStopDistance(
            self.fontMetrics().horizontalAdvance(" ") * self._tab_width_spaces
        )

    def line_number_area_width(self) -> int:
        """Calculate the gutter width for the current line count."""
        if not self._line_numbers_visible:
            return 0
        digits = max(1, len(str(max(1, self.blockCount()))))
        return 14 + self.fontMetrics().horizontalAdvance("9") * digits

    def set_line_numbers_visible(self, visible: bool) -> None:
        """Show or hide the line-number gutter."""
        self._line_numbers_visible = bool(visible)
        self._line_number_area.setVisible(self._line_numbers_visible)
        self._update_line_number_area_width()
        self._line_number_area.update()

    def set_word_wrap_enabled(self, enabled: bool) -> None:
        """Enable or disable editor word wrapping."""
        mode = (
            QPlainTextEdit.LineWrapMode.WidgetWidth
            if enabled
            else QPlainTextEdit.LineWrapMode.NoWrap
        )
        self.setLineWrapMode(mode)

    def set_editor_font(self, font: QFont) -> None:
        """Apply a display font while retaining the configured logical Tab width."""
        self.setFont(font)
        self.setTabStopDistance(
            self.fontMetrics().horizontalAdvance(" ") * self._tab_width_spaces
        )
        self._update_line_number_area_width()

    def set_search_selections(
        self, selections: list[QTextEdit.ExtraSelection]
    ) -> None:
        """Install search highlights without replacing editor decorations."""
        self._search_selections = list(selections)
        self._schedule_decoration_refresh()

    def clear_search_selections(self) -> None:
        """Clear search highlights and retain current-line/bracket decorations."""
        self._search_selections = []
        self._schedule_decoration_refresh()

    def paint_line_number_area(self, event) -> None:
        """Paint only line numbers intersecting the exposed area."""
        if not self._line_numbers_visible:
            return
        painter = QPainter(self._line_number_area)
        painter.fillRect(
            event.rect(),
            QColor(EDITOR_COLOR_SCHEMES[self._color_scheme]["gutter_background"]),
        )

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        current_block_number = self.textCursor().blockNumber()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                colors = EDITOR_COLOR_SCHEMES[self._color_scheme]
                painter.setPen(
                    QColor(colors["gutter_current"])
                    if block_number == current_block_number
                    else QColor(colors["gutter_foreground"])
                )
                painter.drawText(
                    0,
                    top,
                    self._line_number_area.width() - 7,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    str(block_number + 1),
                )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        super().resizeEvent(event)
        self._resize_gutter_above_horizontal_scrollbar()

    def _resize_gutter_above_horizontal_scrollbar(self) -> None:
        """Keep the line-number gutter out of the native horizontal scrollbar strip."""
        contents = self.contentsRect()
        horizontal = self.horizontalScrollBar()
        gutter_height = contents.height()
        if horizontal.isVisible():
            gutter_height = max(0, gutter_height - horizontal.height())
        self._line_number_area.setGeometry(
            QRect(
                contents.left(),
                contents.top(),
                self.line_number_area_width(),
                gutter_height,
            )
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API name
        modifiers = event.modifiers()
        key = event.key()

        if modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_G:
            self.go_to_line_requested.emit()
            return

        if key == Qt.Key.Key_Insert and modifiers in (
            Qt.KeyboardModifier.NoModifier,
            Qt.KeyboardModifier.KeypadModifier,
        ):
            enabled = not self.overwriteMode()
            self.setOverwriteMode(enabled)
            self.overwrite_mode_changed.emit(enabled)
            event.accept()
            return

        # Preserve navigation, selection and copying in View Only mode, but
        # explain the mode when the user presses a key that would modify text.
        if self.isReadOnly():
            if self._is_mutating_key_event(event):
                self.view_only_edit_attempt.emit()
                event.accept()
                return
            super().keyPressEvent(event)
            return

        if modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_Slash:
            self.toggle_comment()
            return

        if modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_D:
            self.duplicate_current_line_or_selection()
            return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._insert_newline_with_indent()
            return

        if key == Qt.Key.Key_Tab and not (modifiers & Qt.KeyboardModifier.ControlModifier):
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self._unindent_selection_or_line()
            else:
                self._indent_selection_or_insert_spaces()
            return

        if key == Qt.Key.Key_Backtab:
            self._unindent_selection_or_line()
            return

        super().keyPressEvent(event)

    @staticmethod
    def _is_mutating_key_event(event: QKeyEvent) -> bool:
        """Return whether a key event would normally change the document."""
        key = event.key()
        if key in (
            Qt.Key.Key_Backspace,
            Qt.Key.Key_Delete,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Tab,
            Qt.Key.Key_Backtab,
        ):
            return True

        for standard_key in (
            QKeySequence.StandardKey.Cut,
            QKeySequence.StandardKey.Paste,
            QKeySequence.StandardKey.Undo,
            QKeySequence.StandardKey.Redo,
        ):
            if event.matches(standard_key):
                return True

        modifiers = event.modifiers()
        if modifiers == Qt.KeyboardModifier.ControlModifier and key in (
            Qt.Key.Key_D,
            Qt.Key.Key_Slash,
        ):
            return True

        # Printable text includes normal typing and AltGr-composed characters.
        text = event.text()
        return bool(text and any(character.isprintable() for character in text))

    def inputMethodEvent(self, event: QInputMethodEvent) -> None:  # noqa: N802
        """Report blocked input-method text while retaining read-only safety."""
        if self.isReadOnly() and (event.commitString() or event.preeditString()):
            self.view_only_edit_attempt.emit()
            event.accept()
            return
        super().inputMethodEvent(event)

    def insertFromMimeData(self, source: QMimeData) -> None:  # noqa: N802
        """
        Insert clipboard/drop content as guarded plain text.

        Rich HTML, images, binary payloads and extremely large clipboard
        contents are not useful in a source-code editor and have triggered
        instability in some bundled Qt clipboard integrations.
        """
        if self.isReadOnly():
            self.view_only_edit_attempt.emit()
            return
        if source is None or not source.hasText():
            self.paste_rejected.emit(
                "Clipboard content is not plain text and was not pasted."
            )
            return

        try:
            text = source.text()
        except Exception as error:
            self.paste_rejected.emit(
                f"Clipboard text could not be read: {error}"
            )
            return

        if len(text) > self.MAX_PASTE_CHARACTERS:
            self.paste_rejected.emit(
                "Clipboard text is too large to paste safely."
            )
            return

        # NUL characters are invalid in normal script source and can cause
        # surprising behavior in downstream APIs.
        text = text.replace("\x00", "")
        if not text:
            return

        cursor = self.textCursor()
        document_length = max(0, self.document().characterCount() - 1)
        selected_length = abs(cursor.selectionEnd() - cursor.selectionStart())
        resulting_length = document_length - selected_length + len(text)
        if resulting_length > self.MAX_DOCUMENT_CHARACTERS:
            self.paste_rejected.emit(
                "The paste would exceed Sheepy Pad's document safety limit."
            )
            return
        selection_start = min(cursor.selectionStart(), cursor.selectionEnd())
        selection_end = max(cursor.selectionStart(), cursor.selectionEnd())
        replaces_entire_document = (
            cursor.hasSelection()
            and selection_start == 0
            and selection_end >= document_length
        )

        if replaces_entire_document:
            # Replacing a full selected document during the same native Qt
            # event that created the selection can crash bundled Qt builds.
            # Complete the selection event first, then perform one guarded edit.
            self._pending_full_paste = text
            self._full_paste_generation += 1
            generation = self._full_paste_generation
            self._decoration_timer.stop()
            self.setExtraSelections([])
            QTimer.singleShot(
                0,
                lambda: self._apply_pending_full_paste(generation),
            )
            return

        plain = QMimeData()
        plain.setText(text)
        super().insertFromMimeData(plain)
        self._schedule_decoration_refresh()

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt API name
        mime = event.mimeData()
        if mime.hasUrls() and any(url.isLocalFile() for url in mime.urls()):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802 - Qt API name
        mime = event.mimeData()
        if mime.hasUrls() and any(url.isLocalFile() for url in mime.urls()):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt API name
        mime = event.mimeData()
        if mime.hasUrls():
            paths = [
                url.toLocalFile()
                for url in mime.urls()
                if url.isLocalFile()
            ]
            if paths:
                self.files_dropped.emit(paths)
                event.acceptProposedAction()
                return
        super().dropEvent(event)

    def _apply_pending_full_paste(self, generation: int) -> None:
        """Replace the whole document after Qt's selection event has settled."""
        if generation != self._full_paste_generation or self.isReadOnly():
            return

        text = self._pending_full_paste
        self._pending_full_paste = None
        if text is None:
            return

        self.replace_document_text(text)
        self.setFocus()

    def replace_document_text(self, text: str) -> bool:
        """Replace the complete document through the hardened editor path."""
        if self.isReadOnly():
            self.view_only_edit_attempt.emit()
            return False
        if len(text) > self.MAX_DOCUMENT_CHARACTERS:
            self.paste_rejected.emit(
                "The replacement would exceed Sheepy Pad's document safety limit."
            )
            return False

        self._decoration_timer.stop()
        self.setExtraSelections([])

        # Temporarily detach the highlighter while the document structure is
        # replaced. It is reattached immediately and rehighlights afterwards.
        highlighter = self._highlighter
        highlighter.setDocument(None)
        cursor = QTextCursor(self.document())
        cursor.beginEditBlock()
        try:
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.insertText(text)
            self.setTextCursor(cursor)
        finally:
            cursor.endEditBlock()
            highlighter.setDocument(self.document())

        self.document().setModified(True)
        self._schedule_decoration_refresh()
        return True

    def paste_safely(self) -> None:
        """Route programmatic Paste through the guarded MIME handler."""
        if self.isReadOnly():
            self.view_only_edit_attempt.emit()
            return
        from PyQt6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            self.insertFromMimeData(clipboard.mimeData())

    def delete_selection_or_character(self) -> None:
        """Delete the selection or the character after the cursor."""
        if self.isReadOnly():
            self.view_only_edit_attempt.emit()
            return

        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()
        else:
            cursor.deleteChar()
        self.setTextCursor(cursor)
        self.setFocus()

    def select_all_text(self) -> None:
        """Select the complete document using the guarded decoration path."""
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        self.setTextCursor(cursor)
        self.setFocus()
        self._decoration_timer.stop()
        self.setExtraSelections([])

    def toggle_comment(self) -> None:
        """Comment or uncomment all selected lines using '# '."""
        if self.isReadOnly():
            self.view_only_edit_attempt.emit()
            return
        cursor = self.textCursor()
        start, end = self._selected_block_range(cursor)

        probe = QTextCursor(self.document())
        probe.setPosition(start)
        probe.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        lines = probe.selectedText().replace("\u2029", "\n").splitlines()
        non_empty = [line for line in lines if line.strip()]
        should_uncomment = bool(non_empty) and all(line.lstrip().startswith("#") for line in non_empty)

        cursor.beginEditBlock()
        cursor.setPosition(start)

        while cursor.position() <= end:
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            line_text = cursor.block().text()

            if should_uncomment:
                indentation = len(line_text) - len(line_text.lstrip())
                if line_text[indentation:].startswith("# "):
                    cursor.setPosition(cursor.block().position() + indentation)
                    cursor.deleteChar()
                    cursor.deleteChar()
                    end -= 2
                elif line_text[indentation:].startswith("#"):
                    cursor.setPosition(cursor.block().position() + indentation)
                    cursor.deleteChar()
                    end -= 1
            elif line_text.strip():
                indentation = len(line_text) - len(line_text.lstrip())
                cursor.setPosition(cursor.block().position() + indentation)
                cursor.insertText("# ")
                end += 2

            if not cursor.movePosition(QTextCursor.MoveOperation.NextBlock):
                break

        cursor.endEditBlock()

    def delete_current_line_or_selection_lines(self) -> None:
        """Delete the current line, or every complete line touched by a selection."""
        if self.isReadOnly():
            self.view_only_edit_attempt.emit()
            return

        cursor = self.textCursor()
        document = self.document()
        if cursor.hasSelection():
            start = min(cursor.selectionStart(), cursor.selectionEnd())
            end = max(cursor.selectionStart(), cursor.selectionEnd())
            start_block = document.findBlock(start)
            # A selection ending exactly at the start of the next block should
            # not unexpectedly delete that next line.
            end_probe = max(start, end - 1)
            end_block = document.findBlock(end_probe)
        else:
            start_block = cursor.block()
            end_block = start_block

        if not start_block.isValid() or not end_block.isValid():
            return

        start_pos = start_block.position()
        next_block = end_block.next()
        if next_block.isValid():
            end_pos = next_block.position()
        else:
            # Last line: include the preceding paragraph separator when there
            # is one, so deleting the last line does not leave a blank tail.
            end_pos = max(0, document.characterCount() - 1)
            if start_pos > 0:
                start_pos -= 1

        edit = QTextCursor(document)
        edit.beginEditBlock()
        edit.setPosition(start_pos)
        edit.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)
        edit.removeSelectedText()
        edit.endEditBlock()
        self.setTextCursor(edit)
        self.setFocus()

    def duplicate_current_line_or_selection(self) -> None:
        """Duplicate the selected text or the current complete line."""
        if self.isReadOnly():
            self.view_only_edit_attempt.emit()
            return
        cursor = self.textCursor()
        cursor.beginEditBlock()

        if cursor.hasSelection():
            selected = cursor.selectedText().replace("\u2029", "\n")
            addition = len(selected)
            insertion = selected
            cursor.setPosition(cursor.selectionEnd())
        else:
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.movePosition(
                QTextCursor.MoveOperation.EndOfBlock,
                QTextCursor.MoveMode.KeepAnchor,
            )
            line = cursor.selectedText()
            addition = len(line) + 1
            insertion = "\n" + line
            cursor.clearSelection()
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)

        document_length = max(0, self.document().characterCount() - 1)
        if document_length + addition > self.MAX_DOCUMENT_CHARACTERS:
            cursor.endEditBlock()
            self.paste_rejected.emit(
                "Duplication would exceed Sheepy Pad's document safety limit."
            )
            return
        cursor.insertText(insertion)

        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def go_to_line(self, line_number: int) -> bool:
        """Move the cursor to a one-based line number."""
        if line_number < 1 or line_number > self.blockCount():
            return False

        block = self.document().findBlockByNumber(line_number - 1)
        if not block.isValid():
            return False

        cursor = QTextCursor(block)
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus()
        return True

    def load_text(self, text: str) -> None:
        """Load text efficiently and mark the Qt document clean."""
        self._decoration_timer.stop()
        self.setExtraSelections([])
        highlighter = self._highlighter
        highlighter.setDocument(None)
        try:
            self.setPlainText(text)
        finally:
            highlighter.setDocument(self.document())
        self.document().setModified(False)
        self._schedule_decoration_refresh()

    def mark_clean(self) -> None:
        """Mark the current document state as saved."""
        self.document().setModified(False)

    @property
    def is_modified(self) -> bool:
        """Return Qt's efficient native dirty-state flag."""
        return self.document().isModified()

    def _update_line_number_area_width(self, _new_count: int = 0) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width()

    def _schedule_decoration_refresh(self, *_args) -> None:
        """Repaint decorations only after Qt has completed the current edit."""
        if not self._decoration_timer.isActive():
            self._decoration_timer.start()

    def _refresh_extra_selections(self) -> None:
        """
        Refresh visual-only decorations without allowing a bad cursor snapshot
        to escape through Qt's event loop.

        Cursor and document lengths can briefly disagree immediately after a
        large replacement. Decorations are optional, so any transient failure
        clears them rather than terminating the application.
        """
        if self._refreshing_extra_selections:
            return

        self._refreshing_extra_selections = True
        try:
            selections: list[QTextEdit.ExtraSelection] = list(
                self._search_selections
            )
            cursor = self.textCursor()

            if not cursor.hasSelection():
                if not self.isReadOnly():
                    current_line = QTextEdit.ExtraSelection()
                    current_line.format.setBackground(
                        QColor(
                            EDITOR_COLOR_SCHEMES[self._color_scheme][
                                "current_line"
                            ]
                        )
                    )
                    current_line.format.setProperty(
                        QTextCharFormat.Property.FullWidthSelection,
                        True,
                    )
                    current_line.cursor = QTextCursor(cursor)
                    current_line.cursor.clearSelection()
                    selections.append(current_line)

                selections.extend(self._matching_bracket_selections())

            self.setExtraSelections(selections)
        except (IndexError, RuntimeError, ValueError):
            # A stale cursor position is harmless; retry on the next cursor or
            # text event after Qt has fully synchronized the document.
            self.setExtraSelections([])
        finally:
            self._line_number_area.update()
            self._refreshing_extra_selections = False

    def _matching_bracket_selections(self) -> list[QTextEdit.ExtraSelection]:
        document = self.document()
        text_length = max(0, document.characterCount() - 1)
        if text_length == 0:
            return []

        cursor = self.textCursor()
        position = max(0, min(cursor.position(), text_length))
        candidate_positions: list[int] = []
        if position > 0:
            candidate_positions.append(position - 1)
        if position < text_length:
            candidate_positions.append(position)

        bracket_position: int | None = None
        bracket = ""
        for index in candidate_positions:
            character = document.characterAt(index)
            if character in self.BRACKET_PAIRS:
                bracket_position = index
                bracket = character
                break
        if bracket_position is None:
            return []

        match_position = self._find_matching_bracket(
            document,
            bracket_position,
            bracket,
            text_length,
        )
        if match_position is None:
            return []

        selections: list[QTextEdit.ExtraSelection] = []
        for index in (bracket_position, match_position):
            selection = QTextEdit.ExtraSelection()
            colors = EDITOR_COLOR_SCHEMES[self._color_scheme]
            selection.format.setBackground(QColor(colors["bracket_background"]))
            selection.format.setForeground(QColor(colors["bracket_foreground"]))
            selection.cursor = QTextCursor(document)
            selection.cursor.setPosition(index)
            selection.cursor.movePosition(
                QTextCursor.MoveOperation.NextCharacter,
                QTextCursor.MoveMode.KeepAnchor,
            )
            selections.append(selection)
        return selections

    def _find_matching_bracket(
        self,
        document: QTextDocument,
        position: int,
        bracket: str,
        text_length: int,
    ) -> int | None:
        if not (0 <= position < text_length):
            return None
        partner = self.BRACKET_PAIRS.get(bracket)
        if partner is None:
            return None

        if bracket in self.OPENING_BRACKETS:
            depth = 1
            stop = min(
                text_length,
                position + 1 + self.MAX_BRACKET_SCAN_CHARACTERS,
            )
            for index in range(position + 1, stop):
                character = document.characterAt(index)
                if character == bracket:
                    depth += 1
                elif character == partner:
                    depth -= 1
                    if depth == 0:
                        return index
        else:
            depth = 1
            stop = max(-1, position - self.MAX_BRACKET_SCAN_CHARACTERS - 1)
            for index in range(position - 1, stop, -1):
                character = document.characterAt(index)
                if character == bracket:
                    depth += 1
                elif character == partner:
                    depth -= 1
                    if depth == 0:
                        return index
        return None

    def _insert_newline_with_indent(self) -> None:
        if self.isReadOnly():
            self.view_only_edit_attempt.emit()
            return
        cursor = self.textCursor()
        current_line = cursor.block().text()
        leading = current_line[: len(current_line) - len(current_line.lstrip())]
        before_cursor = current_line[: cursor.positionInBlock()].rstrip()

        if self._language == "python":
            increase_indent = before_cursor.endswith(":")
        elif self._language == "fish":
            fish_line = before_cursor.strip()
            increase_indent = bool(
                re.search(
                    r"^(?:if|for|while|function|switch|begin)\b|\b(?:else|case)\b",
                    fish_line,
                )
            )
        else:
            shell_line = before_cursor.strip()
            increase_indent = bool(
                re.search(r"(?:\bthen|\bdo|\bin|\{)\s*(?:#.*)?$", shell_line)
            )
        if increase_indent:
            leading += " " * self._tab_width_spaces

        cursor.insertText("\n" + leading)
        self.setTextCursor(cursor)

    def _indent_selection_or_insert_spaces(self) -> None:
        if self.isReadOnly():
            self.view_only_edit_attempt.emit()
            return
        cursor = self.textCursor()
        if not cursor.hasSelection():
            cursor.insertText(" " * self._tab_width_spaces)
            return

        start, end = self._selected_block_range(cursor)
        cursor.beginEditBlock()
        cursor.setPosition(start)

        while cursor.position() <= end:
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.insertText(" " * self._tab_width_spaces)
            end += self._tab_width_spaces

            if not cursor.movePosition(QTextCursor.MoveOperation.NextBlock):
                break

        cursor.endEditBlock()

    def _unindent_selection_or_line(self) -> None:
        if self.isReadOnly():
            self.view_only_edit_attempt.emit()
            return
        cursor = self.textCursor()
        start, end = self._selected_block_range(cursor)
        cursor.beginEditBlock()
        cursor.setPosition(start)

        while cursor.position() <= end:
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            block_text = cursor.block().text()

            remove_count = 0
            if block_text.startswith("\t"):
                remove_count = 1
            else:
                remove_count = min(
                    self._tab_width_spaces,
                    len(block_text) - len(block_text.lstrip(" ")),
                )

            for _ in range(remove_count):
                cursor.deleteChar()
            end -= remove_count

            if not cursor.movePosition(QTextCursor.MoveOperation.NextBlock):
                break

        cursor.endEditBlock()

    def _selected_block_range(self, cursor: QTextCursor) -> tuple[int, int]:
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        start_cursor = QTextCursor(self.document())
        start_cursor.setPosition(start)
        start_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)

        end_cursor = QTextCursor(self.document())
        end_cursor.setPosition(end)
        if end > start and end_cursor.positionInBlock() == 0:
            end_cursor.movePosition(QTextCursor.MoveOperation.PreviousBlock)
        end_cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)

        return start_cursor.position(), end_cursor.position()
