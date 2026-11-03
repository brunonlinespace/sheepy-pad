#!/usr/bin/env python3
"""Dependency-free regressions for Sheepy Pad's snippet-only Library."""

from __future__ import annotations

import unittest

from sheepy_pad.script_library import (
    BUILTIN_ENTRY_BY_KEY,
    ENTRIES,
    LIBRARY_CATEGORIES,
    LibraryEntry,
    custom_entries_from_preferences,
    default_library_category,
    matching_entries,
    normalise_favourites,
    render_entry,
    serialise_custom_entries,
)


class ScriptLibraryTests(unittest.TestCase):
    def test_library_is_snippet_only_and_favourites_first(self) -> None:
        self.assertEqual(LIBRARY_CATEGORIES[0:2], ("Favourites", "All"))
        self.assertEqual(LIBRARY_CATEGORIES[-1], "Custom")
        self.assertNotIn("Templates", LIBRARY_CATEGORIES)
        self.assertTrue(ENTRIES)
        self.assertTrue(all(entry.category != "Templates" for entry in ENTRIES))

    def test_each_supported_type_has_relevant_snippets(self) -> None:
        for suffix in (".py", ".pyw", ".sh", ".bash", ".zsh", ".fish"):
            self.assertTrue(matching_entries(suffix), suffix)
        self.assertIn("py-main-guard", {e.key for e in matching_entries(".py")})
        self.assertNotIn("fish-function", {e.key for e in matching_entries(".py")})
        self.assertIn("fish-function", {e.key for e in matching_entries(".fish")})

    def test_library_search_includes_lint_metadata(self) -> None:
        matches = matching_entries(".bash", query="shellcheck")
        self.assertTrue(matches)
        self.assertTrue(any("ShellCheck" in entry.lint_hint for entry in matches))

    def test_marker_rendering_is_stable(self) -> None:
        entry = BUILTIN_ENTRY_BY_KEY["py-main-guard"]
        rendered, cursor = render_entry(entry, "print('hello')\n")
        self.assertNotIn("[[selection]]", rendered)
        self.assertNotIn("[[cursor]]", rendered)
        self.assertIn("print('hello')", rendered)
        self.assertGreaterEqual(cursor, rendered.index("print('hello')"))
        self.assertLessEqual(cursor, len(rendered))

    def test_custom_snippet_round_trip_and_file_type_filtering(self) -> None:
        raw = [{
            "key": "custom-example",
            "label": "My Bash snippet",
            "suffix": ".bash",
            "description": "A user snippet.",
            "body": "printf '%s\\n' [[cursor]]\n",
        }]
        custom = custom_entries_from_preferences(raw)
        self.assertEqual(len(custom), 1)
        self.assertTrue(custom[0].custom)
        self.assertEqual(custom[0].category, "Custom")
        self.assertEqual(serialise_custom_entries(custom), raw)
        self.assertIn(
            "custom-example",
            {e.key for e in matching_entries(".bash", category="Custom", custom_entries=custom)},
        )
        self.assertNotIn(
            "custom-example",
            {e.key for e in matching_entries(".py", category="Custom", custom_entries=custom)},
        )

    def test_favourites_are_bounded_known_and_include_custom(self) -> None:
        custom = (
            LibraryEntry(
                "custom-x", "Custom X", "Custom", (".py",),
                "User-defined snippet.", "Python syntax check.", "pass\n", True,
            ),
        )
        value = ["py-main-guard", "unknown", "py-main-guard", "custom-x"]
        self.assertEqual(
            normalise_favourites(value, custom),
            ["py-main-guard", "custom-x"],
        )
        favourites = matching_entries(
            ".py", category="Favourites",
            favourites=("py-main-guard", "custom-x"), custom_entries=custom,
        )
        self.assertEqual({e.key for e in favourites}, {"py-main-guard", "custom-x"})

    def test_library_defaults_to_all_until_visible_favourites_exist(self) -> None:
        self.assertEqual(default_library_category(".py", []), "All")
        self.assertEqual(
            default_library_category(".py", ["py-main-guard"]),
            "Favourites",
        )
        # A favourite for another document type must not produce an empty
        # Favourites default in the current Library context.
        self.assertEqual(
            default_library_category(".fish", ["py-main-guard"]),
            "All",
        )

    def test_entry_keys_are_unique(self) -> None:
        self.assertEqual(len(ENTRIES), len(BUILTIN_ENTRY_BY_KEY))

    def test_r4_catalogue_is_deep_and_preserves_original_snippets(self) -> None:
        original_keys = {
            "py-main-guard", "py-try-except", "py-argparse", "py-env", "py-path",
            "py-subprocess", "shell-function", "shell-case", "shell-env-default",
            "shell-temp-file", "shell-cleanup", "fish-function", "fish-switch",
            "fish-env", "fish-path", "fish-cleanup", "py-function", "py-if",
            "py-for", "py-argparse-flag", "py-env-required", "py-read-text",
            "py-write-text", "py-json-load", "shell-if", "shell-for-args",
            "shell-getopts", "shell-env-required", "shell-script-dir",
            "shell-read-lines", "shell-background", "fish-if", "fish-for",
            "fish-argparse", "fish-env-required", "fish-temp-dir",
            "fish-background",
        }
        current_keys = {entry.key for entry in ENTRIES}
        self.assertTrue(original_keys <= current_keys)
        self.assertGreaterEqual(len(ENTRIES), 150)
        minimums = {".py": 55, ".pyw": 48, ".sh": 34, ".bash": 45, ".zsh": 42, ".fish": 35}
        for suffix, minimum in minimums.items():
            self.assertGreaterEqual(len(matching_entries(suffix)), minimum, suffix)

    def test_r4_high_value_language_specific_entries_exist(self) -> None:
        expected = {
            ".py": {"py-subprocess-capture", "py-csv-read", "py-temp-dir", "py-argparse-subcommands"},
            ".pyw": {"py-tk-window", "py-tk-messagebox"},
            ".sh": {"shell-strict-portable", "shell-command-v", "shell-signal-trap"},
            ".bash": {"bash-strict", "bash-script-dir", "bash-mapfile", "bash-assoc-array"},
            ".zsh": {"zsh-strict", "zsh-script-dir", "zsh-zparseopts", "zsh-glob-qualifier"},
            ".fish": {"fish-command-q", "fish-argparse-value", "fish-string-match", "fish-signal-handler"},
        }
        for suffix, keys in expected.items():
            visible = {entry.key for entry in matching_entries(suffix)}
            self.assertTrue(keys <= visible, (suffix, keys - visible))


if __name__ == "__main__":
    unittest.main()
