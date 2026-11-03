# Sheepy Pad
# Copyright (C) 2026 Bruno Machado
# SPDX-License-Identifier: GPL-3.0-or-later
"""Runnable-script metadata and argument/profile helpers for Sheepy Pad."""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

PYTHON_SUFFIXES = frozenset({".py", ".pyw"})
POSIX_SHELL_SUFFIXES = frozenset({".sh", ".bash", ".zsh"})
FISH_SUFFIXES = frozenset({".fish"})
SUPPORTED_SCRIPT_SUFFIXES = frozenset(
    PYTHON_SUFFIXES | POSIX_SHELL_SUFFIXES | FISH_SUFFIXES
)

SCRIPT_FILE_FILTER = (
    "Runnable Scripts (*.py *.pyw *.sh *.bash *.zsh *.fish);;"
    "Python Files (*.py *.pyw);;"
    "Shell Scripts (*.sh *.bash *.zsh *.fish);;"
    "Bash Scripts (*.bash);;Zsh Scripts (*.zsh);;Fish Scripts (*.fish);;"
    "All Files (*)"
)

_FILE_TYPE_LABELS = {
    ".py": "Python script (.py)",
    ".pyw": "Python windowed script (.pyw)",
    ".sh": "Shell script (.sh)",
    ".bash": "Bash script (.bash)",
    ".zsh": "Zsh script (.zsh)",
    ".fish": "Fish script (.fish)",
}

_ENVIRONMENT_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def file_type_label(path: str | Path) -> str:
    """Return a user-facing type label for a supported script path."""
    suffix = Path(path).suffix.casefold()
    return _FILE_TYPE_LABELS.get(suffix, "Runnable script")


def source_language_for_path(
    path: str | Path,
    first_line: str = "",
) -> str:
    """Return the editor highlighter family for a script path/shebang."""
    suffix = Path(path).suffix.casefold()
    if suffix in PYTHON_SUFFIXES:
        return "python"
    if suffix in FISH_SUFFIXES:
        return "fish"

    lower = first_line.casefold()
    if lower.startswith("#!"):
        if "fish" in lower:
            return "fish"
        if "python" in lower:
            return "python"
    return "shell"


def parse_argument_string(value: str) -> tuple[str, ...]:
    """Split one user-entered argument string without invoking a shell."""
    if not value.strip():
        return ()
    return tuple(shlex.split(value, posix=os.name != "nt"))


def parse_environment_lines(text: str) -> dict[str, str]:
    """Parse KEY=value lines used by the environment-profile editor."""
    result: dict[str, str] = {}
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Line {line_number} must use NAME=value format.")
        key, value = line.split("=", 1)
        key = key.strip()
        if not _ENVIRONMENT_KEY.fullmatch(key):
            raise ValueError(f"Line {line_number} has an invalid variable name: {key!r}.")
        if len(value) > 1536:
            raise ValueError(f"Line {line_number} has a value longer than 1536 characters.")
        result[key] = value
        if len(result) > 16:
            raise ValueError("A profile may contain at most 16 variables.")
    return result


def format_environment_lines(values: dict[str, str]) -> str:
    """Format an environment profile as stable NAME=value lines."""
    return "\n".join(f"{key}={values[key]}" for key in sorted(values))


def normalise_environment_profiles(value: object) -> dict[str, dict[str, str]]:
    """Return a bounded, JSON-safe environment-profile mapping."""
    profiles: dict[str, dict[str, str]] = {"Default": {}}
    if not isinstance(value, dict):
        return profiles
    for raw_name, raw_values in list(value.items())[:8]:
        if not isinstance(raw_name, str) or not isinstance(raw_values, dict):
            continue
        name = raw_name.strip()
        if not name or len(name) > 64:
            continue
        cleaned: dict[str, str] = {}
        for raw_key, raw_value in list(raw_values.items())[:16]:
            if not isinstance(raw_key, str) or not _ENVIRONMENT_KEY.fullmatch(raw_key):
                continue
            if not isinstance(raw_value, str) or len(raw_value) > 1536:
                continue
            cleaned[raw_key] = raw_value
        profiles[name] = cleaned
    profiles.setdefault("Default", {})
    return profiles
