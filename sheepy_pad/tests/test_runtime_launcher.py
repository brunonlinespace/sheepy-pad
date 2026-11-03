# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless regression tests for process-command resolution and identity checks."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

try:
    import PyQt6.QtCore  # type: ignore[import-not-found]  # noqa: F401
except ModuleNotFoundError:
    qtcore = types.ModuleType("PyQt6.QtCore")

    class _Signal:
        def emit(self, *_args, **_kwargs) -> None:
            return None

    class _QObject:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

    class _QProcess:
        pass

    class _QProcessEnvironment:
        pass

    qtcore.QObject = _QObject
    qtcore.QProcess = _QProcess
    qtcore.QProcessEnvironment = _QProcessEnvironment
    qtcore.pyqtSignal = lambda *_args, **_kwargs: _Signal()
    package = types.ModuleType("PyQt6")
    package.QtCore = qtcore
    sys.modules.setdefault("PyQt6", package)
    sys.modules.setdefault("PyQt6.QtCore", qtcore)

from sheepy_pad.runtime_launcher import LaunchCommand, RuntimeLauncher
from sheepy_pad.runtime_paths import RuntimePaths


class RuntimeLauncherTests(unittest.TestCase):
    def _source_paths(self, root: Path) -> RuntimePaths:
        return RuntimePaths(
            launcher_root=root,
            package_root=root / "sheepy_pad",
            resource_root=root / "sheepy_pad" / "assets",
            config_root=root / "config",
            running_as_appimage=False,
            running_frozen=False,
        )

    def test_source_mode_preserves_virtual_environment_symlink(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symbolic links are unavailable")
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            interpreter = root / "venv-python"
            interpreter.symlink_to(Path(sys.executable))
            launcher = RuntimeLauncher(self._source_paths(root))
            with mock.patch.object(sys, "executable", str(interpreter)):
                self.assertEqual(
                    launcher.python_executable(),
                    os.path.abspath(str(interpreter)),
                )

    def test_python_command_preserves_final_script_symlink(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symbolic links are unavailable")
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            target = root / "target.py"
            link = root / "link.py"
            target.write_text("print('ok')\n", encoding="utf-8")
            link.symlink_to(target.name)
            launcher = RuntimeLauncher(self._source_paths(root))
            command = launcher.python_command(link)
            self.assertIsNotNone(command)
            assert command is not None
            self.assertEqual(command.arguments, (str(link.absolute()),))
            self.assertEqual(command.working_directory, root)

    def test_shell_command_uses_host_shell_and_preserves_script_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            script = root / "sample.sh"
            script.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
            launcher = RuntimeLauncher(self._source_paths(root))
            with mock.patch.object(
                launcher, "shell_executable", return_value="/bin/bash"
            ):
                command = launcher.shell_command(script)
            self.assertIsNotNone(command)
            assert command is not None
            self.assertEqual(command.program, "/bin/bash")
            self.assertEqual(command.arguments, (str(script.absolute()),))
            self.assertEqual(command.working_directory, root)

    def test_script_command_supports_all_runnable_suffixes(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            launcher = RuntimeLauncher(self._source_paths(root))
            candidates = {
                ".py": "/usr/bin/python3",
                ".pyw": "/usr/bin/python3",
                ".sh": "/bin/sh",
                ".bash": "/bin/bash",
                ".zsh": "/usr/bin/zsh",
                ".fish": "/usr/bin/fish",
            }
            for suffix, executable in candidates.items():
                script = root / f"sample{suffix}"
                script.write_text("echo ok\n", encoding="utf-8")
                with mock.patch.object(
                    launcher,
                    "resolve_interpreter",
                    return_value=(executable, (), "File type"),
                ):
                    command = launcher.script_command(script)
                self.assertIsNotNone(command, suffix)
                assert command is not None
                self.assertEqual(command.program, executable)
                self.assertEqual(command.arguments, (str(script.absolute()),))
            self.assertIsNone(launcher.script_command(root / "sample.txt"))

    def test_shebang_precedes_extension_default(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            script = root / "sample.sh"
            script.write_text("#!/usr/bin/env fish\necho ok\n", encoding="utf-8")
            launcher = RuntimeLauncher(self._source_paths(root))
            with mock.patch.object(
                launcher, "_resolve_executable", side_effect=lambda value: "/usr/bin/fish" if value == "fish" else None
            ):
                resolved = launcher.resolve_interpreter(script)
            self.assertEqual(resolved, ("/usr/bin/fish", (), "Shebang"))

    def test_script_command_carries_arguments_environment_and_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            script = root / "sample.py"
            script.write_text("print('ok')\n", encoding="utf-8")
            work = root / "work"
            work.mkdir()
            launcher = RuntimeLauncher(self._source_paths(root))
            with mock.patch.object(
                launcher,
                "resolve_interpreter",
                return_value=("/usr/bin/python3", ("-I",), "Selected interpreter"),
            ):
                command = launcher.script_command(
                    script,
                    extra_arguments=("--name", "hello world"),
                    working_directory=work,
                    environment={"DEMO": "1"},
                )
            self.assertIsNotNone(command)
            assert command is not None
            self.assertEqual(
                command.arguments,
                ("-I", str(script.absolute()), "--name", "hello world"),
            )
            self.assertEqual(command.working_directory, work)
            self.assertEqual(command.environment, (("DEMO", "1"),))


    def test_elevated_script_command_wraps_with_sudo_without_shell(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            script = root / "sample.py"
            script.write_text("print('ok')\n", encoding="utf-8")
            launcher = RuntimeLauncher(self._source_paths(root))
            with (
                mock.patch.object(
                    launcher,
                    "script_command",
                    return_value=LaunchCommand(
                        program="/usr/bin/python3",
                        arguments=(str(script.absolute()),),
                        working_directory=root,
                    ),
                ),
                mock.patch.object(
                    launcher, "sudo_executable", return_value="/usr/bin/sudo"
                ),
            ):
                command = launcher.elevated_script_command(script)
            self.assertIsNotNone(command)
            assert command is not None
            self.assertEqual(command.program, "/usr/bin/sudo")
            self.assertEqual(
                command.arguments,
                (
                    "-k",
                    "--",
                    "/usr/bin/python3",
                    str(script.absolute()),
                ),
            )
            self.assertEqual(command.working_directory, root)

    def test_elevated_terminal_command_cannot_be_tracked(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            script = root / "sample.sh"
            script.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
            launcher = RuntimeLauncher(self._source_paths(root))
            self.assertIsNone(
                launcher.script_terminal_command(
                    script,
                    root / "state.json",
                    "token",
                    elevated=True,
                )
            )

    @unittest.skipUnless(hasattr(signal, "SIGHUP"), "SIGHUP unavailable")
    def test_terminal_runner_forwards_terminal_hangup_and_cleans_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            launcher = RuntimeLauncher(self._source_paths(root))
            runner = launcher._ensure_terminal_session_runner()
            self.assertIsNotNone(runner)
            assert runner is not None
            state = root / "terminal-state.json"
            wrapper = subprocess.Popen(
                [
                    sys.executable,
                    str(runner),
                    str(state),
                    "test-token",
                    str(root / "sample.py"),
                    str(root),
                    sys.executable,
                    "-c",
                    "import time; time.sleep(30)",
                ]
            )
            try:
                deadline = time.monotonic() + 5.0
                while not state.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(state.exists(), "terminal runner did not create state")
                os.kill(wrapper.pid, signal.SIGHUP)
                wrapper.wait(timeout=5)
                deadline = time.monotonic() + 2.0
                while state.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertFalse(state.exists(), "terminal runner left stale state after SIGHUP")
            finally:
                if wrapper.poll() is None:
                    wrapper.kill()
                    wrapper.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
