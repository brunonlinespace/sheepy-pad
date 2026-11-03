#!/usr/bin/env python3
"""Regression tests for Sheepy Pad runtime and preference paths."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sheepy_pad.runtime_paths import RuntimePaths


class RuntimePathsTests(unittest.TestCase):
    def test_linux_paths_use_sheepy_pad_and_expose_legacy_import_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sheepy_pad").mkdir()
            home = root / "home"
            with (
                patch.object(sys, "platform", "linux"),
                patch.object(Path, "home", return_value=home),
                patch.dict(os.environ, {}, clear=True),
            ):
                paths = RuntimePaths.detect(root / "main.py")
                legacy_config_paths = paths.legacy_config_paths

            self.assertEqual(paths.package_root, root / "sheepy_pad")
            self.assertEqual(
                paths.icon_path,
                root / "sheepy_pad" / "assets" / "icons" / "sheepy-pad.png",
            )
            self.assertEqual(
                paths.config_path,
                home
                / ".config"
                / "brunonlinespace"
                / "sheepy-pad"
                / "sheepy-pad.json",
            )
            self.assertEqual(
                legacy_config_paths,
                (
                    home
                    / ".config"
                    / "brunonlinespace"
                    / "pytshpad"
                    / "pytshpad.json",
                    home
                    / ".config"
                    / "brunonlinespace"
                    / "pythushy"
                    / "pythushy.json",
                    home
                    / ".config"
                    / "brunonlinespace"
                    / "pythy"
                    / "pythy.json",
                ),
            )

    def test_windows_paths_use_sheepy_pad_and_expose_legacy_import_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sheepy_pad").mkdir()
            appdata = root / "AppData" / "Roaming"
            with (
                patch.object(sys, "platform", "win32"),
                patch.dict(
                    os.environ,
                    {"APPDATA": str(appdata)},
                    clear=True,
                ),
            ):
                paths = RuntimePaths.detect(root / "main.py")
                legacy_config_paths = paths.legacy_config_paths

            self.assertEqual(
                paths.config_path,
                appdata
                / "brunonlinespace"
                / "Sheepy Pad"
                / "sheepy-pad.json",
            )
            self.assertEqual(
                legacy_config_paths,
                (
                    appdata
                    / "brunonlinespace"
                    / "Pytshpad"
                    / "pytshpad.json",
                    appdata
                    / "brunonlinespace"
                    / "Pythushy"
                    / "pythushy.json",
                    appdata / "brunonlinespace" / "Pythy" / "pythy.json",
                ),
            )

    def test_appimage_theme_paths_require_both_bundled_styles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sheepy_pad").mkdir()
            appdir = root / "Sheepy-Pad.AppDir"
            styles = appdir / "usr" / "share" / "sheepy-pad" / "styles"
            styles.mkdir(parents=True)
            dark = styles / "breeze-dark.qss"
            light = styles / "breeze-light.qss"
            dark.write_text("QWidget { color: white; }", encoding="utf-8")

            with patch.dict(
                os.environ,
                {"APPDIR": str(appdir)},
                clear=True,
            ):
                missing = RuntimePaths.detect(root / "main.py")
                self.assertTrue(missing.running_as_appimage)
                self.assertEqual(missing.appimage_theme_paths, {})

                light.write_text("QWidget { color: black; }", encoding="utf-8")
                complete = RuntimePaths.detect(root / "main.py")
                self.assertEqual(
                    complete.appimage_theme_paths,
                    {"dark": dark, "light": light},
                )

    def test_source_runtime_does_not_expose_appimage_themes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sheepy_pad").mkdir()
            with patch.dict(os.environ, {}, clear=True):
                paths = RuntimePaths.detect(root / "main.py")
            self.assertFalse(paths.running_as_appimage)
            self.assertEqual(paths.appimage_theme_paths, {})


if __name__ == "__main__":
    unittest.main()
