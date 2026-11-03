# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression tests for Sheepy Pad's filesystem safety helpers."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from sheepy_pad.file_io import (
    FileStateChangedError,
    FileTooLargeError,
    UnsupportedFileError,
    absolute_user_path,
    current_file_state,
    ensure_private_directory,
    install_new_file_from_temp,
    path_identity_matches,
    path_lexists,
    read_regular_file,
    rename_path_no_replace,
    snapshot_from_payload,
    toggle_executable_permission,
    validated_symlink_target,
)


class FileIoTests(unittest.TestCase):
    def test_regular_file_snapshot_and_payload_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            path = Path(raw_root) / "sample.py"
            path.write_bytes(b"print('ok')\n")
            data, snapshot = read_regular_file(path, 1024)
            self.assertEqual(data, b"print('ok')\n")
            self.assertEqual(snapshot, snapshot_from_payload(path, data))

    def test_size_limit_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            path = Path(raw_root) / "large.py"
            path.write_bytes(b"x" * 17)
            with self.assertRaises(FileTooLargeError):
                read_regular_file(path, 16)

    def test_absolute_path_does_not_resolve_final_symlink(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symbolic links are unavailable")
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            target = root / "target.py"
            link = root / "link.py"
            target.write_text("old\n", encoding="utf-8")
            link.symlink_to(target.name)
            resolved = absolute_user_path(link)
            self.assertEqual(resolved, link)
            self.assertTrue(resolved.is_symlink())

    def test_symlink_target_update_is_guarded(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symbolic links are unavailable")
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            first = root / "first.py"
            second = root / "second.py"
            link = root / "link.py"
            first.write_text("first\n", encoding="utf-8")
            second.write_text("second\n", encoding="utf-8")
            link.symlink_to(first.name)
            state = current_file_state(link)
            link.unlink()
            link.symlink_to(second.name)
            with self.assertRaises(FileStateChangedError):
                validated_symlink_target(link, state)
            self.assertEqual(second.read_text(encoding="utf-8"), "second\n")

    def test_dangling_symlink_is_visible_to_lexists(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symbolic links are unavailable")
        with tempfile.TemporaryDirectory() as raw_root:
            link = Path(raw_root) / "dangling.py"
            link.symlink_to("missing.py")
            self.assertTrue(path_lexists(link))
            self.assertFalse(link.exists())

    def test_private_read_rejects_symbolic_link(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symbolic links are unavailable")
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            target = root / "target.json"
            link = root / "config.json"
            target.write_bytes(b"{}")
            link.symlink_to(target.name)
            with self.assertRaises(UnsupportedFileError):
                read_regular_file(link, 1024, follow_symlinks=False)

    def test_fifo_is_rejected_without_blocking(self) -> None:
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFOs are unavailable")
        with tempfile.TemporaryDirectory() as raw_root:
            fifo = Path(raw_root) / "pipe.py"
            os.mkfifo(fifo)
            with self.assertRaises(UnsupportedFileError):
                read_regular_file(fifo, 1024)

    def test_new_file_install_does_not_overwrite_raced_destination(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            temporary = root / ".new.tmp"
            destination = root / "sample.py"
            temporary.write_bytes(b"new\n")
            destination.write_bytes(b"existing\n")
            with self.assertRaises(FileStateChangedError):
                install_new_file_from_temp(temporary, destination)
            self.assertEqual(destination.read_bytes(), b"existing\n")
            self.assertTrue(temporary.exists())

    def test_new_file_install_creates_destination(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            temporary = root / ".new.tmp"
            destination = root / "sample.py"
            temporary.write_bytes(b"new\n")
            install_new_file_from_temp(temporary, destination)
            self.assertEqual(destination.read_bytes(), b"new\n")
            self.assertFalse(temporary.exists())

    def test_rename_no_replace_preserves_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "source.py"
            destination = root / "destination.py"
            source.write_bytes(b"source\n")
            destination.write_bytes(b"destination\n")
            with self.assertRaises(FileStateChangedError):
                rename_path_no_replace(source, destination)
            self.assertEqual(source.read_bytes(), b"source\n")
            self.assertEqual(destination.read_bytes(), b"destination\n")

    def test_path_identity_detects_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            path = Path(raw_root) / "sample.py"
            path.write_bytes(b"one\n")
            state = current_file_state(path)
            replacement = path.with_suffix(".replacement")
            replacement.write_bytes(b"two\n")
            os.replace(replacement, path)
            self.assertFalse(path_identity_matches(path, state))

    def test_private_directory_rejects_symlink(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symbolic links are unavailable")
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            real = root / "real"
            real.mkdir()
            link = root / "link"
            link.symlink_to(real, target_is_directory=True)
            with self.assertRaises(OSError):
                ensure_private_directory(link)


    def test_executable_permission_toggle_updates_snapshot_state(self) -> None:
        if not hasattr(os, "fchmod"):
            self.skipTest("descriptor permission changes are unavailable")
        with tempfile.TemporaryDirectory() as raw_root:
            path = Path(raw_root) / "sample.py"
            path.write_bytes(b"print('ok')\n")
            os.chmod(path, 0o600)
            before = current_file_state(path)
            after = toggle_executable_permission(path, expected=before)
            self.assertEqual(after.target_mode & 0o111, 0o111)
            final = toggle_executable_permission(path, expected=after)
            self.assertEqual(final.target_mode & 0o111, 0)

    def test_executable_permission_toggle_follows_stable_symlink_safely(self) -> None:
        if not hasattr(os, "fchmod") or not hasattr(os, "symlink"):
            self.skipTest("required POSIX file APIs are unavailable")
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            target = root / "target.py"
            link = root / "link.py"
            target.write_bytes(b"print('ok')\n")
            os.chmod(target, 0o600)
            link.symlink_to(target.name)
            before = current_file_state(link)
            after = toggle_executable_permission(link, expected=before)
            self.assertTrue(link.is_symlink())
            self.assertEqual(after.target_mode & 0o111, 0o111)
            self.assertEqual(target.stat().st_mode & 0o111, 0o111)

    def test_executable_permission_toggle_rejects_replaced_path(self) -> None:
        if not hasattr(os, "fchmod"):
            self.skipTest("descriptor permission changes are unavailable")
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            path = root / "sample.py"
            path.write_bytes(b"one\n")
            os.chmod(path, 0o600)
            expected = current_file_state(path)
            replacement = root / "replacement.py"
            replacement.write_bytes(b"two\n")
            os.chmod(replacement, 0o600)
            os.replace(replacement, path)
            with self.assertRaises(FileStateChangedError):
                toggle_executable_permission(path, expected=expected)
            self.assertEqual(path.stat().st_mode & 0o111, 0)


if __name__ == "__main__":
    unittest.main()
