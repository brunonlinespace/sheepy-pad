# Sheepy Pad
# Copyright (C) 2026 Bruno Machado
# SPDX-License-Identifier: GPL-3.0-or-later
"""Launch host applications safely from source, frozen, and AppImage builds."""

from __future__ import annotations

import os
import shlex
import shutil
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, pyqtSignal

from sheepy_pad.file_io import (
    FileTooLargeError,
    UnsupportedFileError,
    absolute_user_path,
    ensure_private_directory,
    fsync_directory,
    read_regular_file,
)
from sheepy_pad.runtime_paths import RuntimePaths
from sheepy_pad.script_runtime import (
    FISH_SUFFIXES,
    POSIX_SHELL_SUFFIXES,
    PYTHON_SUFFIXES,
)


PYTHON_OVERRIDE_VARIABLE = "SHEEPY_PAD_PYTHON"
SHELL_OVERRIDE_VARIABLE = "SHEEPY_PAD_SHELL"
EDITOR_OVERRIDE_VARIABLE = "SHEEPY_PAD_EDITOR"

# AppImage/PyInstaller variables that should not leak into host applications.
# In particular, bundled Qt and Python library paths can make terminals,
# editors, file managers, and the host Python fail to start.
_SANITIZED_VARIABLES = frozenset(
    {
        "APPDIR",
        "APPIMAGE",
        "ARGV0",
        "OWD",
        "LD_LIBRARY_PATH",
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONEXECUTABLE",
        "SHEEPY_PAD_APPIMAGE_THEME",
        "QT_PLUGIN_PATH",
        "QT_QPA_PLATFORM_PLUGIN_PATH",
        "QML2_IMPORT_PATH",
        "QML_IMPORT_PATH",
    }
)


@dataclass(frozen=True, slots=True)
class LaunchCommand:
    """A resolved executable, arguments, working directory and environment."""

    program: str
    arguments: tuple[str, ...] = ()
    working_directory: Path | None = None
    environment: tuple[tuple[str, str], ...] = ()


class RuntimeLauncher(QObject):
    """
    Resolve and launch host-side tools without relaunching the AppImage.

    Portable/source mode preserves the interpreter that launched main.py,
    including an active virtual environment. Frozen/AppImage mode deliberately
    selects a host Python interpreter instead of sys.executable.
    """

    status_message = pyqtSignal(str)
    launch_error = pyqtSignal(str)

    def __init__(
        self,
        runtime_paths: RuntimePaths,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.runtime_paths = runtime_paths

    # ------------------------------------------------------------------
    # Interpreter and script execution
    # ------------------------------------------------------------------

    def python_executable(self) -> str | None:
        """Return the appropriate Python interpreter for user scripts."""
        override = os.environ.get(PYTHON_OVERRIDE_VARIABLE, "").strip()
        if override:
            resolved = self._resolve_executable(override)
            if resolved:
                return resolved

        if (
            not self.runtime_paths.running_as_appimage
            and not self.runtime_paths.running_frozen
        ):
            # Preserve an active virtual environment in portable/source mode.
            return os.path.abspath(os.path.expanduser(sys.executable))

        for candidate in ("python3", "python"):
            resolved = shutil.which(candidate, path=self._host_path())
            if resolved:
                return resolved
        return None

    def shell_executable(self) -> str | None:
        """Return the configured/default host shell for generic .sh scripts."""
        override = os.environ.get(SHELL_OVERRIDE_VARIABLE, "").strip()
        if override:
            resolved = self._resolve_executable(override)
            if resolved:
                return resolved
        for candidate in ("bash", "sh"):
            resolved = shutil.which(candidate, path=self._host_path())
            if resolved:
                return resolved
        return None

    def _read_shebang(self, script_path: Path) -> str:
        """Read only the first line of a previously validated regular script."""
        try:
            flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NONBLOCK", 0)
            descriptor = os.open(script_path, flags)
            try:
                raw = os.read(descriptor, 4096)
            finally:
                os.close(descriptor)
        except OSError:
            return ""
        first_line = raw.splitlines()[0] if raw else b""
        return first_line.decode("utf-8", errors="replace").strip()

    def detected_shebang(self, script_path: str | Path) -> str:
        """Return the current script shebang, or an empty string."""
        script = absolute_user_path(script_path)
        line = self._read_shebang(script)
        return line if line.startswith("#!") else ""

    def _shebang_interpreter(self, script_path: Path) -> tuple[str, tuple[str, ...]] | None:
        line = self.detected_shebang(script_path)
        if not line:
            return None
        try:
            parts = shlex.split(line[2:].strip())
        except ValueError:
            return None
        if not parts:
            return None

        executable = parts[0]
        arguments = list(parts[1:])
        if Path(executable).name == "env":
            while arguments and arguments[0].startswith("-"):
                option = arguments.pop(0)
                if option == "--":
                    break
                if option == "-S":
                    break
            while arguments and "=" in arguments[0] and not arguments[0].startswith("="):
                key = arguments[0].split("=", 1)[0]
                if not key.replace("_", "a").isalnum():
                    break
                arguments.pop(0)
            if not arguments:
                return None
            executable = arguments.pop(0)

        resolved = self._resolve_executable(executable)
        if resolved is None:
            return None
        return resolved, tuple(arguments)

    def _default_interpreter(self, script_path: Path) -> tuple[str, tuple[str, ...]] | None:
        suffix = script_path.suffix.casefold()
        if suffix in PYTHON_SUFFIXES:
            executable = self.python_executable()
            return (executable, ()) if executable else None
        if suffix == ".sh":
            executable = self.shell_executable()
            return (executable, ()) if executable else None
        candidates: tuple[str, ...]
        if suffix == ".bash":
            candidates = ("bash",)
        elif suffix == ".zsh":
            candidates = ("zsh",)
        elif suffix in FISH_SUFFIXES:
            candidates = ("fish",)
        else:
            return None
        for candidate in candidates:
            resolved = self._resolve_executable(candidate)
            if resolved:
                return resolved, ()
        return None

    def resolve_interpreter(
        self,
        script_path: str | Path,
        interpreter_override: str | None = None,
    ) -> tuple[str, tuple[str, ...], str] | None:
        """Resolve override, shebang, then extension default in that order."""
        script = absolute_user_path(script_path)
        suffix = script.suffix.casefold()
        if (
            suffix not in PYTHON_SUFFIXES
            and suffix not in POSIX_SHELL_SUFFIXES
            and suffix not in FISH_SUFFIXES
        ):
            return None
        override = (interpreter_override or "").strip()
        if override:
            resolved = self._resolve_executable(override)
            if resolved:
                return resolved, (), "Selected interpreter"
            return None
        shebang = self._shebang_interpreter(script)
        if shebang is not None:
            return shebang[0], shebang[1], "Shebang"
        default = self._default_interpreter(script)
        if default is None:
            return None
        return default[0], default[1], "File type"

    def python_command(self, script_path: str | Path) -> LaunchCommand | None:
        """Compatibility helper that explicitly uses the host Python interpreter."""
        python = self.python_executable()
        if python is None:
            return None
        return self.script_command(script_path, interpreter_override=python)

    def shell_command(self, script_path: str | Path) -> LaunchCommand | None:
        """Compatibility helper that explicitly uses the configured generic shell."""
        shell = self.shell_executable()
        if shell is None:
            return None
        return self.script_command(script_path, interpreter_override=shell)

    def script_command(
        self,
        script_path: str | Path,
        *,
        extra_arguments: tuple[str, ...] = (),
        interpreter_override: str | None = None,
        working_directory: str | Path | None = None,
        environment: dict[str, str] | None = None,
    ) -> LaunchCommand | None:
        """Build a direct no-shell command for any supported runnable script."""
        script = absolute_user_path(script_path)
        resolved = self.resolve_interpreter(script, interpreter_override)
        if resolved is None:
            return None
        program, prefix_arguments, _source = resolved
        cwd = (
            Path(working_directory).expanduser().resolve(strict=False)
            if working_directory is not None
            else script.parent
        )
        env_items = tuple(sorted((environment or {}).items()))
        return LaunchCommand(
            program=program,
            arguments=(*prefix_arguments, str(script), *extra_arguments),
            working_directory=cwd,
            environment=env_items,
        )

    def sudo_executable(self) -> str | None:
        """Return the host sudo executable used for explicit elevation."""
        return self._resolve_executable("sudo")

    def elevated_script_command(
        self,
        script_path: str | Path,
        *,
        extra_arguments: tuple[str, ...] = (),
        interpreter_override: str | None = None,
        working_directory: str | Path | None = None,
        environment: dict[str, str] | None = None,
    ) -> LaunchCommand | None:
        """Wrap a resolved script command in sudo without using a shell."""
        command = self.script_command(
            script_path,
            extra_arguments=extra_arguments,
            interpreter_override=interpreter_override,
            working_directory=working_directory,
            environment=environment,
        )
        sudo = self.sudo_executable()
        if command is None or sudo is None:
            return None
        return LaunchCommand(
            program=sudo,
            arguments=("-k", "--", command.program, *command.arguments),
            working_directory=command.working_directory,
            environment=command.environment,
        )

    # ------------------------------------------------------------------
    # Managed and detached process setup
    # ------------------------------------------------------------------

    def configure_process(
        self,
        process: QProcess,
        command: LaunchCommand,
    ) -> None:
        """Configure a QProcess with a host-safe environment."""
        process.setProgram(command.program)
        process.setArguments(list(command.arguments))
        if command.working_directory is not None:
            process.setWorkingDirectory(str(command.working_directory))
        environment = self.process_environment()
        for name, value in command.environment:
            environment.insert(name, value)
        process.setProcessEnvironment(environment)
        # Do not retain unbounded stdout/stderr in QProcess buffers when a
        # launched script is noisy. Forwarding also makes source-mode launches
        # useful from a terminal while remaining harmless from a desktop menu.
        process.setProcessChannelMode(QProcess.ProcessChannelMode.ForwardedChannels)
        process.setInputChannelMode(
            QProcess.InputChannelMode.ForwardedInputChannel
        )

    def start_detached_with_pid(
        self,
        command: LaunchCommand,
    ) -> tuple[bool, int | None]:
        """
        Start a detached host process and return its PID when Qt provides it.

        A concrete PID lets Sheepy Pad close a terminal window that it created
        specifically for a Force Stop operation.
        """
        process = QProcess(self)
        self.configure_process(process, command)
        try:
            try:
                result = process.startDetached()
            except TypeError:
                # Defensive compatibility with bindings exposing only the static
                # overload. This fallback may not preserve the custom environment.
                result = QProcess.startDetached(
                    command.program,
                    list(command.arguments),
                    (
                        str(command.working_directory)
                        if command.working_directory is not None
                        else ""
                    ),
                )
        finally:
            # A detached launch no longer needs its temporary QProcess wrapper.
            # Releasing it prevents one dormant QObject accumulating per folder,
            # editor, browser or terminal launch over a long session.
            process.deleteLater()

        if isinstance(result, tuple):
            started = bool(result[0])
            process_id = int(result[1]) if started and len(result) > 1 else None
            return started, process_id

        return bool(result), None

    def start_detached(self, command: LaunchCommand) -> bool:
        """Start a detached process, ignoring the optional returned PID."""
        started, _process_id = self.start_detached_with_pid(command)
        return started

    def subprocess_environment(
        self,
        extra: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Return the same host-safe environment as a plain subprocess mapping."""
        result = dict(os.environ)
        if (
            self.runtime_paths.running_as_appimage
            or self.runtime_paths.running_frozen
        ):
            for name in _SANITIZED_VARIABLES:
                result.pop(name, None)
            host_path = self._host_path()
            if host_path:
                result["PATH"] = host_path
            for name in ("LD_LIBRARY_PATH", "PYTHONHOME", "PYTHONPATH"):
                original_name = f"APPIMAGE_ORIGINAL_{name}"
                if original_name in os.environ:
                    result[name] = os.environ[original_name]
                result.pop(original_name, None)
        if extra:
            result.update(extra)
        return result

    def process_environment(self) -> QProcessEnvironment:
        """
        Return a clean environment for host Python and desktop applications.

        Source mode keeps the active environment intact. Bundled modes remove
        paths injected by the AppImage/PyInstaller runtime while retaining
        ordinary user variables such as DISPLAY, WAYLAND_DISPLAY, HOME and PATH.
        """
        environment = QProcessEnvironment.systemEnvironment()
        if (
            not self.runtime_paths.running_as_appimage
            and not self.runtime_paths.running_frozen
        ):
            return environment

        for name in _SANITIZED_VARIABLES:
            environment.remove(name)

        host_path = self._host_path()
        if host_path:
            environment.insert("PATH", host_path)

        # Some AppImage runtimes save original values under APPIMAGE_ORIGINAL_*.
        # Restore them when available instead of simply deleting them.
        for name in ("LD_LIBRARY_PATH", "PYTHONHOME", "PYTHONPATH"):
            original_name = f"APPIMAGE_ORIGINAL_{name}"
            original_value = os.environ.get(original_name)
            if original_value is not None:
                environment.insert(name, original_value)
            environment.remove(original_name)

        return environment

    # ------------------------------------------------------------------
    # Terminal execution
    # ------------------------------------------------------------------

    def script_terminal_command(
        self,
        script_path: str | Path,
        state_path: str | Path | None = None,
        session_token: str | None = None,
        *,
        elevated: bool = False,
        extra_arguments: tuple[str, ...] = (),
        interpreter_override: str | None = None,
        working_directory: str | Path | None = None,
        environment: dict[str, str] | None = None,
    ) -> LaunchCommand | None:
        """Build a terminal command with the selected interpreter/run settings."""
        script = absolute_user_path(script_path)
        if elevated and state_path is not None:
            # Root-owned descendants are deliberately not supervised.
            return None
        script_command = (
            self.elevated_script_command(
                script,
                extra_arguments=extra_arguments,
                interpreter_override=interpreter_override,
                working_directory=working_directory,
                environment=environment,
            )
            if elevated
            else self.script_command(
                script,
                extra_arguments=extra_arguments,
                interpreter_override=interpreter_override,
                working_directory=working_directory,
                environment=environment,
            )
        )
        if script_command is None:
            return None

        command_parts = [script_command.program, *script_command.arguments]
        cwd = script_command.working_directory or script.parent
        if state_path is not None:
            if not session_token:
                return None
            python = self.python_executable()
            runner = self._ensure_terminal_session_runner()
            if python is None or runner is None:
                return None
            command_parts = [
                python,
                str(runner),
                str(Path(state_path)),
                session_token,
                str(script),
                str(cwd),
                script_command.program,
                *script_command.arguments,
            ]

        quoted = " ".join(shlex.quote(part) for part in command_parts)
        candidates: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("ptyxis", ("--", *command_parts)),
            ("kgx", ("--", *command_parts)),
            ("gnome-terminal", ("--", *command_parts)),
            ("konsole", ("--nofork", "-e", *command_parts)),
            ("xfce4-terminal", ("--command", quoted)),
            ("tilix", ("-e", quoted)),
            ("terminator", ("-x", *command_parts)),
            ("alacritty", ("-e", *command_parts)),
            ("kitty", tuple(command_parts)),
            ("foot", tuple(command_parts)),
            ("xterm", ("-hold", "-e", *command_parts)),
        )
        terminal_command = self._first_available_command(candidates, cwd)
        if terminal_command is None:
            return None
        return LaunchCommand(
            terminal_command.program,
            terminal_command.arguments,
            terminal_command.working_directory,
            script_command.environment,
        )

    def folder_terminal_command(
        self,
        folder_path: str | Path,
    ) -> LaunchCommand | None:
        folder = Path(folder_path).expanduser().resolve(strict=False)
        candidates: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("ptyxis", ("--working-directory", str(folder))),
            ("kgx", ("--working-directory", str(folder))),
            ("gnome-terminal", ("--working-directory", str(folder))),
            ("konsole", ("--workdir", str(folder))),
            ("xfce4-terminal", ("--working-directory", str(folder))),
            ("tilix", ("--working-directory", str(folder))),
            ("kitty", ("--directory", str(folder))),
            ("alacritty", ("--working-directory", str(folder))),
            ("foot", ("--working-directory", str(folder))),
            ("xterm", ()),
        )
        return self._first_available_command(candidates, folder)

    def open_script_in_terminal(self, script_path: str | Path) -> bool:
        command = self.script_terminal_command(script_path)
        if command is None:
            return self._fail(
                "No supported terminal emulator or host script interpreter "
                "was found."
            )
        if not self.start_detached(command):
            return self._fail(
                f"Could not start terminal '{Path(command.program).name}'."
            )
        return True

    def open_folder_in_terminal(self, folder_path: str | Path) -> bool:
        command = self.folder_terminal_command(folder_path)
        if command is None:
            return self._fail("No supported terminal emulator was found.")
        if not self.start_detached(command):
            return self._fail(
                f"Could not start terminal '{Path(command.program).name}'."
            )
        return True

    # ------------------------------------------------------------------
    # Files, folders, editors and URLs
    # ------------------------------------------------------------------

    def open_path(self, path: str | Path) -> bool:
        """Open a file or folder with the host desktop's default application."""
        target = absolute_user_path(path)
        command = self._desktop_open_command(str(target))
        if command is None:
            return self._fail(
                "No host desktop opener was found (xdg-open or gio)."
            )
        if not self.start_detached(command):
            return self._fail(f"Could not open '{target}'.")
        return True

    def open_url(self, url: str) -> bool:
        """Open an HTTP(S) URL with the host browser."""
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return self._fail(f"Unsupported URL: {url}")
        command = self._desktop_open_command(url)
        if command is None:
            return self._fail(
                "No host desktop opener was found (xdg-open or gio)."
            )
        if not self.start_detached(command):
            return self._fail(f"Could not open '{url}'.")
        return True

    def open_in_external_editor(self, path: str | Path) -> bool:
        """
        Open a script in a visible host graphical editor.

        The desktop file association is preferred because it also works for
        Flatpak-installed editors that are not present in PATH. Generic
        $EDITOR values such as vim or nano are deliberately ignored here:
        starting them detached without a terminal appears to do nothing.
        """
        target = absolute_user_path(path)
        if not target.is_file():
            return self._fail(f"The script does not exist: {target}")

        # Sheepy Pad-specific override: users who want an exact editor can
        # configure one without the ambiguity of shell-oriented $EDITOR.
        explicit_override = os.environ.get(
            EDITOR_OVERRIDE_VARIABLE,
            "",
        ).strip()
        if explicit_override:
            try:
                parts = shlex.split(explicit_override)
            except ValueError as error:
                return self._fail(
                    f"Invalid {EDITOR_OVERRIDE_VARIABLE} value: {error}"
                )
            if parts:
                resolved = self._resolve_executable(parts[0])
                if resolved:
                    command = LaunchCommand(
                        resolved,
                        tuple(parts[1:] + [str(target)]),
                        target.parent,
                    )
                    if self.start_detached(command):
                        return True

        # Let Fedora/GNOME/KDE choose the registered graphical application.
        # This is the most reliable route for native and Flatpak editors.
        desktop_command = self._desktop_open_command(str(target))
        if (
            desktop_command is not None
            and self.start_detached(desktop_command)
        ):
            return True

        # PATH-based fallback for desktops without a registered association.
        candidates: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("gnome-text-editor", (str(target),)),
            ("kate", (str(target),)),
            ("code", (str(target),)),
            ("codium", (str(target),)),
            ("gedit", (str(target),)),
            ("geany", (str(target),)),
            ("mousepad", (str(target),)),
            ("xed", (str(target),)),
            ("pluma", (str(target),)),
        )
        command = self._first_available_command(candidates, target.parent)
        if command is not None and self.start_detached(command):
            return True

        return self._fail(
            "No graphical editor or desktop file association could be started."
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_terminal_session_runner(self) -> Path | None:
        """
        Create the terminal tracking helper in the writable config directory.

        Host Python cannot reliably execute a source-file path inside a
        PyInstaller/AppImage bundle because bundled modules may not exist as
        ordinary files.
        """
        runner_dir = self.runtime_paths.config_root / "runtime"
        runner_path = runner_dir / "terminal_session_runner.py"
        source = textwrap.dedent(
            """\
            from __future__ import annotations

            import json
            import os
            import signal
            import subprocess
            import sys
            from pathlib import Path

            def process_start_time(process_id: int):
                try:
                    raw = (Path("/proc") / str(process_id) / "stat").read_bytes()
                    closing = raw.rfind(b")")
                    if closing < 0:
                        return None
                    fields = raw[closing + 1 :].split()
                    return int(fields[19]) if len(fields) > 19 else None
                except (OSError, ValueError):
                    return None

            def main() -> int:
                if len(sys.argv) < 7:
                    return 2

                state_path = Path(sys.argv[1])
                token = sys.argv[2]
                script = sys.argv[3]
                working_directory = sys.argv[4]
                command = sys.argv[5:]
                state_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                try:
                    os.chmod(state_path.parent, 0o700)
                except OSError:
                    pass

                child = subprocess.Popen(
                    command,
                    cwd=working_directory,
                    start_new_session=True,
                )
                def forward(signum, _frame):
                    try:
                        os.killpg(child.pid, signum)
                    except OSError:
                        pass

                signal.signal(signal.SIGTERM, forward)
                signal.signal(signal.SIGINT, forward)
                if hasattr(signal, "SIGHUP"):
                    signal.signal(signal.SIGHUP, forward)

                payload = json.dumps(
                    {
                        "token": token,
                        "wrapper_pid": os.getpid(),
                        "child_pid": child.pid,
                        "child_pgid": child.pid,
                        "wrapper_start_time": process_start_time(os.getpid()),
                        "child_start_time": process_start_time(child.pid),
                        "script": script,
                    }
                ).encode("utf-8")
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
                flags |= getattr(os, "O_CLOEXEC", 0)
                flags |= getattr(os, "O_NOFOLLOW", 0)
                try:
                    descriptor = os.open(state_path, flags, 0o600)
                    with os.fdopen(descriptor, "wb") as handle:
                        handle.write(payload)
                        handle.flush()
                        os.fsync(handle.fileno())
                except OSError:
                    try:
                        os.killpg(child.pid, signal.SIGTERM)
                    except OSError:
                        pass
                    child.wait()
                    return 3

                try:
                    return child.wait()
                finally:
                    try:
                        state_path.unlink()
                    except OSError:
                        pass

            if __name__ == "__main__":
                raise SystemExit(main())
            """
        )

        temporary: Path | None = None
        descriptor: int | None = None
        try:
            ensure_private_directory(runner_dir)

            existing = None
            try:
                payload, _snapshot = read_regular_file(
                    runner_path,
                    128 * 1024,
                    follow_symlinks=False,
                )
                existing = payload.decode("utf-8")
            except FileNotFoundError:
                pass
            except (
                FileTooLargeError,
                UnsupportedFileError,
                UnicodeDecodeError,
                OSError,
            ):
                # Replace an invalid, oversized or stale helper only after the
                # destination directory itself has passed the private-directory
                # ownership and symlink checks above.
                existing = None
            if existing != source:
                descriptor, raw_path = tempfile.mkstemp(
                    prefix=".terminal-session-runner-",
                    suffix=".tmp",
                    dir=runner_dir,
                    text=True,
                )
                temporary = Path(raw_path)
                if hasattr(os, "fchmod"):
                    os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    descriptor = None
                    handle.write(source)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, runner_path)
                temporary = None
                fsync_directory(runner_dir)
            return runner_path
        except OSError as error:
            self._fail(f"Could not prepare terminal launcher: {error}")
            return None
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

    def _desktop_open_command(self, target: str) -> LaunchCommand | None:
        xdg_open = self._resolve_executable("xdg-open")
        if xdg_open:
            return LaunchCommand(xdg_open, (target,))

        gio = self._resolve_executable("gio")
        if gio:
            return LaunchCommand(gio, ("open", target))

        return None

    def _first_available_command(
        self,
        candidates: Iterable[tuple[str, tuple[str, ...]]],
        working_directory: Path,
    ) -> LaunchCommand | None:
        for executable, arguments in candidates:
            resolved = self._resolve_executable(executable)
            if resolved:
                return LaunchCommand(
                    program=resolved,
                    arguments=arguments,
                    working_directory=working_directory,
                )
        return None

    def find_host_executable(self, executable: str) -> str | None:
        """Public host-PATH resolver for optional syntax/lint tools."""
        return self._resolve_executable(executable)

    def _resolve_executable(self, executable: str) -> str | None:
        path = Path(executable).expanduser()
        if path.is_absolute():
            return str(path) if path.is_file() and os.access(path, os.X_OK) else None
        return shutil.which(executable, path=self._host_path())

    def _host_path(self) -> str | None:
        """Return a host PATH with AppImage/PyInstaller entries removed."""
        original = os.environ.get("APPIMAGE_ORIGINAL_PATH")
        if original:
            return original

        current = os.environ.get("PATH")
        if not current or (
            not self.runtime_paths.running_as_appimage
            and not self.runtime_paths.running_frozen
        ):
            return current

        blocked_roots = {
            str(self.runtime_paths.launcher_root),
            str(self.runtime_paths.package_root),
        }
        appdir = os.environ.get("APPDIR")
        if appdir:
            blocked_roots.add(str(Path(appdir).resolve(strict=False)))
        frozen_root = getattr(sys, "_MEIPASS", None)
        if frozen_root:
            blocked_roots.add(str(Path(frozen_root).resolve(strict=False)))

        clean_entries: list[str] = []
        for entry in current.split(os.pathsep):
            if not entry:
                continue
            resolved = str(Path(entry).expanduser().resolve(strict=False))
            if any(
                resolved == root or resolved.startswith(root + os.sep)
                for root in blocked_roots
            ):
                continue
            clean_entries.append(entry)
        return os.pathsep.join(clean_entries)

    def _fail(self, message: str) -> bool:
        self.launch_error.emit(message)
        self.status_message.emit(message)
        return False
