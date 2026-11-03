# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import unittest
from pathlib import Path

from sheepy_pad.script_runtime import (
    SUPPORTED_SCRIPT_SUFFIXES,
    format_environment_lines,
    normalise_environment_profiles,
    parse_argument_string,
    parse_environment_lines,
    source_language_for_path,
)


class ScriptRuntimeTests(unittest.TestCase):
    def test_supported_runnable_suffixes_are_exact(self) -> None:
        self.assertEqual(
            SUPPORTED_SCRIPT_SUFFIXES,
            frozenset({".py", ".pyw", ".sh", ".bash", ".zsh", ".fish"}),
        )

    def test_source_language_assigns_fish_its_own_family(self) -> None:
        self.assertEqual(source_language_for_path(Path("sample.fish")), "fish")
        self.assertEqual(source_language_for_path(Path("sample.bash")), "shell")
        self.assertEqual(source_language_for_path(Path("sample.pyw")), "python")
        self.assertEqual(
            source_language_for_path(Path("sample.sh"), "#!/usr/bin/env fish"),
            "fish",
        )

    def test_argument_parser_preserves_quoted_argument(self) -> None:
        self.assertEqual(
            parse_argument_string('--name "hello world" --count 2'),
            ("--name", "hello world", "--count", "2"),
        )

    def test_environment_profiles_validate_names_and_round_trip(self) -> None:
        values = parse_environment_lines("ALPHA=one\nBETA=two words\n")
        self.assertEqual(values, {"ALPHA": "one", "BETA": "two words"})
        self.assertEqual(format_environment_lines(values), "ALPHA=one\nBETA=two words")
        with self.assertRaises(ValueError):
            parse_environment_lines("BAD-NAME=value")
        profiles = normalise_environment_profiles({"Dev": values})
        self.assertEqual(profiles["Dev"], values)
        self.assertIn("Default", profiles)


if __name__ == "__main__":
    unittest.main()
