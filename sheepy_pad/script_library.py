# Sheepy Pad
# Copyright (C) 2026 Bruno Machado
# SPDX-License-Identifier: GPL-3.0-or-later
"""Built-in and user script snippets for Sheepy Pad's Library."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SUPPORTED_LIBRARY_SUFFIXES = (".py", ".pyw", ".sh", ".bash", ".zsh", ".fish")
CURSOR_MARKER = "[[cursor]]"
SELECTION_MARKER = "[[selection]]"
MAX_CUSTOM_SNIPPETS = 64
MAX_SNIPPET_BODY = 8 * 1024


@dataclass(frozen=True, slots=True)
class LibraryEntry:
    key: str
    label: str
    category: str
    suffixes: tuple[str, ...]
    description: str
    lint_hint: str
    body: str
    custom: bool = False


ENTRIES: tuple[LibraryEntry, ...] = (
    LibraryEntry(
        'py-main-guard', 'Python main guard', 'Flow', ('.py', '.pyw'),
        'Insert a main function and conventional __main__ guard.',
        "Valid Python; suitable for Sheepy Pad's Python syntax check and Ruff when installed.",
        'def main() -> int:\n    [[selection]][[cursor]]return 0\n\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n',
    ),
    LibraryEntry(
        'py-try-except', 'Python try / except', 'Flow', ('.py', '.pyw'),
        'Wrap selected code in a simple exception-handling block.',
        'Valid Python; broad Exception catch is intentionally visible for editing.',
        'try:\n    [[selection]][[cursor]]pass\nexcept Exception as error:\n    print(error)\n',
    ),
    LibraryEntry(
        'py-argparse', 'Python argparse parser', 'Arguments', ('.py',),
        'Insert a compact argparse parser using only the standard library.',
        'Valid Python; suitable for the built-in syntax check and Ruff when installed.',
        'import argparse\n\nparser = argparse.ArgumentParser()\nparser.add_argument("[[cursor]]name")\nargs = parser.parse_args()\n',
    ),
    LibraryEntry(
        'py-env', 'Python environment variable', 'Environment', ('.py', '.pyw'),
        'Read an environment variable without adding dependencies.',
        'Valid Python; import os if it is not already present.',
        'import os\n\nvalue = os.environ.get("[[cursor]]NAME", "")\n',
    ),
    LibraryEntry(
        'py-path', 'Python pathlib path', 'Files', ('.py', '.pyw'),
        'Create a pathlib Path relative to the current script.',
        'Valid Python; standard-library only.',
        'from pathlib import Path\n\nbase_dir = Path(__file__).resolve().parent\npath = base_dir / "[[cursor]]file.txt"\n',
    ),
    LibraryEntry(
        'py-subprocess', 'Python subprocess run', 'Processes', ('.py', '.pyw'),
        'Run a child command without invoking a shell.',
        'Valid Python; argument-vector form avoids shell evaluation.',
        'import subprocess\n\nresult = subprocess.run(["[[cursor]]command"], check=False)\n',
    ),
    LibraryEntry(
        'shell-function', 'Shell function', 'Flow', ('.sh', '.bash', '.zsh'),
        'Insert a portable-style shell function.',
        'Compatible with sh/bash/zsh syntax-only checks.',
        'main() {\n    [[selection]][[cursor]]:\n}\n',
    ),
    LibraryEntry(
        'shell-case', 'Shell argument case', 'Arguments', ('.sh', '.bash', '.zsh'),
        'Handle a first positional argument with case/esac.',
        'Compatible with sh/bash/zsh syntax-only checks and ShellCheck where supported.',
        'case "${1:-}" in\n    start)\n        [[cursor]];;\n    *)\n        printf \'%s\\n\' "Usage: $0 start" >&2\n        exit 2\n        ;;\nesac\n',
    ),
    LibraryEntry(
        'shell-env-default', 'Shell environment default', 'Environment', ('.sh', '.bash', '.zsh'),
        'Read an environment variable with a safe default value.',
        'Compatible with sh/bash/zsh syntax-only checks.',
        'value=${[[cursor]]NAME:-default}\n',
    ),
    LibraryEntry(
        'shell-temp-file', 'Shell temporary file', 'Files', ('.sh', '.bash', '.zsh'),
        'Create a temporary file and arrange cleanup on exit.',
        'Compatible with sh/bash/zsh syntax-only checks; mktemp is an external utility.',
        'tmp_file=$(mktemp) || exit 1\ntrap \'rm -f -- "$tmp_file"\' EXIT\n[[cursor]]\n',
    ),
    LibraryEntry(
        'shell-cleanup', 'Shell cleanup trap', 'Processes', ('.sh', '.bash', '.zsh'),
        'Register a small EXIT cleanup function.',
        'Compatible with sh/bash/zsh syntax-only checks.',
        'cleanup() {\n    [[selection]][[cursor]]:\n}\ntrap cleanup EXIT\n',
    ),
    LibraryEntry(
        'fish-function', 'Fish function', 'Flow', ('.fish',),
        'Insert a Fish function block.',
        'Compatible with fish -n.',
        'function main\n    [[selection]][[cursor]]echo "Hello"\nend\n',
    ),
    LibraryEntry(
        'fish-switch', 'Fish argument switch', 'Arguments', ('.fish',),
        'Handle an argument with Fish switch/case syntax.',
        'Compatible with fish -n.',
        'switch "$argv[1]"\n    case start\n        [[cursor]]\n    case \'*\'\n        echo "Usage: (status filename) start" >&2\n        return 2\nend\n',
    ),
    LibraryEntry(
        'fish-env', 'Fish environment variable', 'Environment', ('.fish',),
        'Read an exported environment variable in Fish.',
        'Compatible with fish -n.',
        'set -l value "$[[cursor]]NAME"\n',
    ),
    LibraryEntry(
        'fish-path', 'Fish script directory', 'Files', ('.fish',),
        'Resolve the directory containing the current Fish script.',
        'Compatible with fish -n.',
        'set -l script_dir (path dirname (status filename))\nset -l path "$script_dir/[[cursor]]file.txt"\n',
    ),
    LibraryEntry(
        'fish-cleanup', 'Fish exit cleanup event', 'Processes', ('.fish',),
        'Register a cleanup handler for Fish process exit.',
        'Compatible with fish -n.',
        'function cleanup --on-event fish_exit\n    [[selection]][[cursor]]\nend\n',
    ),
    LibraryEntry(
        'py-function', 'Python function', 'Flow', ('.py', '.pyw'),
        'Insert a typed Python function skeleton.',
        "Valid Python; suitable for Sheepy Pad's Python syntax check and Ruff when installed.",
        'def [[cursor]]function_name() -> None:\n    [[selection]]pass\n',
    ),
    LibraryEntry(
        'py-if', 'Python if / elif / else', 'Flow', ('.py', '.pyw'),
        'Insert a complete conditional skeleton.',
        "Valid Python; suitable for Sheepy Pad's Python syntax check.",
        'if [[cursor]]condition:\n    [[selection]]pass\nelif other_condition:\n    pass\nelse:\n    pass\n',
    ),
    LibraryEntry(
        'py-for', 'Python for loop', 'Flow', ('.py', '.pyw'),
        'Iterate over an existing iterable.',
        "Valid Python; suitable for Sheepy Pad's Python syntax check.",
        'for item in [[cursor]]items:\n    [[selection]]pass\n',
    ),
    LibraryEntry(
        'py-argparse-flag', 'Python argparse flag', 'Arguments', ('.py',),
        'Add a boolean command-line flag to an existing ArgumentParser.',
        'Valid Python; expects a parser variable named parser.',
        'parser.add_argument("--[[cursor]]verbose", action="store_true")\n',
    ),
    LibraryEntry(
        'py-env-required', 'Python required environment variable', 'Environment', ('.py', '.pyw'),
        'Read an environment variable and fail clearly when it is absent.',
        'Valid Python; import os if it is not already present.',
        'import os\n\nvalue = os.environ["[[cursor]]NAME"]\n',
    ),
    LibraryEntry(
        'py-read-text', 'Python read text file', 'Files', ('.py', '.pyw'),
        'Read UTF-8 text with pathlib.',
        'Valid Python; standard-library only.',
        'from pathlib import Path\n\ntext = Path("[[cursor]]file.txt").read_text(encoding="utf-8")\n',
    ),
    LibraryEntry(
        'py-write-text', 'Python write text file', 'Files', ('.py', '.pyw'),
        'Write UTF-8 text with pathlib.',
        'Valid Python; standard-library only.',
        'from pathlib import Path\n\nPath("[[cursor]]file.txt").write_text(text, encoding="utf-8")\n',
    ),
    LibraryEntry(
        'py-json-load', 'Python load JSON', 'Files', ('.py', '.pyw'),
        'Load a UTF-8 JSON document with the standard library.',
        'Valid Python; standard-library only.',
        'import json\nfrom pathlib import Path\n\ndata = json.loads(Path("[[cursor]]data.json").read_text(encoding="utf-8"))\n',
    ),
    LibraryEntry(
        'shell-if', 'Shell if / else', 'Flow', ('.sh', '.bash', '.zsh'),
        'Insert a portable-style conditional block.',
        'Compatible with sh/bash/zsh syntax-only checks.',
        'if [[cursor]]command; then\n    [[selection]]:\nelse\n    :\nfi\n',
    ),
    LibraryEntry(
        'shell-for-args', 'Shell iterate arguments', 'Arguments', ('.sh', '.bash', '.zsh'),
        'Iterate safely over all positional arguments.',
        'Compatible with sh/bash/zsh syntax-only checks and ShellCheck where supported.',
        'for arg in "$@"; do\n    [[selection]][[cursor]]printf \'%s\\n\' "$arg"\ndone\n',
    ),
    LibraryEntry(
        'shell-getopts', 'Shell getopts option', 'Arguments', ('.sh', '.bash', '.zsh'),
        'Parse a simple option with POSIX getopts.',
        'Compatible with sh/bash/zsh syntax-only checks and ShellCheck where supported.',
        'while getopts \'[[cursor]]v\' option; do\n    case "$option" in\n        v) verbose=1 ;;\n        *) exit 2 ;;\n    esac\ndone\nshift $((OPTIND - 1))\n',
    ),
    LibraryEntry(
        'shell-env-required', 'Shell required environment variable', 'Environment', ('.sh', '.bash', '.zsh'),
        'Require an environment variable using parameter expansion.',
        'Compatible with sh/bash/zsh syntax-only checks.',
        ': "${[[cursor]]NAME:?NAME must be set}"\n',
    ),
    LibraryEntry(
        'shell-script-dir', 'Shell script directory', 'Files', ('.sh', '.bash', '.zsh'),
        'Resolve the directory containing the current script without changing directory.',
        'Compatible with sh/bash/zsh syntax-only checks.',
        'script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1\n[[cursor]]\n',
    ),
    LibraryEntry(
        'shell-read-lines', 'Shell read file lines', 'Files', ('.sh', '.bash', '.zsh'),
        'Read a text file line by line without losing backslashes.',
        'Compatible with sh/bash/zsh syntax-only checks and ShellCheck where supported.',
        'while IFS= read -r line; do\n    [[selection]][[cursor]]printf \'%s\\n\' "$line"\ndone < "file.txt"\n',
    ),
    LibraryEntry(
        'shell-background', 'Shell background job and wait', 'Processes', ('.sh', '.bash', '.zsh'),
        'Start one command in the background and wait for it.',
        'Compatible with sh/bash/zsh syntax-only checks.',
        '[[cursor]]command &\nchild_pid=$!\nwait "$child_pid"\n',
    ),
    LibraryEntry(
        'fish-if', 'Fish if / else', 'Flow', ('.fish',),
        'Insert a Fish conditional block.',
        'Compatible with fish -n.',
        'if [[cursor]]command\n    [[selection]]\nelse\n    \nend\n',
    ),
    LibraryEntry(
        'fish-for', 'Fish iterate arguments', 'Arguments', ('.fish',),
        "Iterate over Fish's argv list.",
        'Compatible with fish -n.',
        'for arg in $argv\n    [[selection]][[cursor]]echo $arg\nend\n',
    ),
    LibraryEntry(
        'fish-argparse', 'Fish argparse flag', 'Arguments', ('.fish',),
        "Parse a simple flag with Fish's argparse builtin.",
        'Compatible with fish -n.',
        "argparse '[[cursor]]v/verbose' -- $argv; or return 2\n",
    ),
    LibraryEntry(
        'fish-env-required', 'Fish required environment variable', 'Environment', ('.fish',),
        'Require an exported environment variable before continuing.',
        'Compatible with fish -n.',
        "if not set -q [[cursor]]NAME\n    echo 'NAME must be set' >&2\n    return 2\nend\n",
    ),
    LibraryEntry(
        'fish-temp-dir', 'Fish temporary directory', 'Files', ('.fish',),
        'Create a temporary directory and keep its path in a local variable.',
        'Compatible with fish -n; mktemp is an external utility.',
        'set -l temp_dir (mktemp -d); or return 1\n[[cursor]]\n',
    ),
    LibraryEntry(
        'fish-background', 'Fish background job and wait', 'Processes', ('.fish',),
        'Start a command in the background and wait for it.',
        'Compatible with fish -n.',
        '[[cursor]]command &\nset -l child_pid $last_pid\nwait $child_pid\n',
    ),
)

# Additional high-frequency script building blocks.  Kept separate so the
# original 0.3.0-r3 catalogue remains byte-for-byte represented above.
EXTRA_ENTRIES: tuple[LibraryEntry, ...] = (
    LibraryEntry(
        'py-try-finally', 'Python try / finally', 'Flow', ('.py', '.pyw'),
        'Run cleanup code whether or not the guarded block succeeds.',
        'Valid Python; standard-library syntax only.',
        'try:\n    [[selection]][[cursor]]pass\nfinally:\n    pass\n',
    ),
    LibraryEntry(
        'py-while', 'Python while loop', 'Flow', ('.py', '.pyw'),
        'Insert a while loop with an explicit condition.',
        'Valid Python; suitable for Sheepy Pad syntax checking.',
        'while [[cursor]]condition:\n    [[selection]]pass\n',
    ),
    LibraryEntry(
        'py-enumerate', 'Python enumerate loop', 'Flow', ('.py', '.pyw'),
        'Iterate with both index and value using enumerate.',
        'Valid Python; standard-library builtin.',
        'for index, value in enumerate([[cursor]]items):\n    [[selection]]pass\n',
    ),
    LibraryEntry(
        'py-dict-items', 'Python dictionary items loop', 'Flow', ('.py', '.pyw'),
        'Iterate over dictionary keys and values together.',
        'Valid Python; standard dictionary API.',
        'for key, value in [[cursor]]mapping.items():\n    [[selection]]pass\n',
    ),
    LibraryEntry(
        'py-list-comprehension', 'Python list comprehension', 'Flow', ('.py', '.pyw'),
        'Build a list from an iterable with a compact comprehension.',
        'Valid Python; edit the expression and iterable to fit the task.',
        'result = [item for item in [[cursor]]items]\n',
    ),
    LibraryEntry(
        'py-match-case', 'Python match / case', 'Flow', ('.py', '.pyw'),
        'Dispatch values with structural pattern matching.',
        'Valid on Python 3.10 and newer.',
        'match [[cursor]]value:\n    case "start":\n        [[selection]]pass\n    case _:\n        pass\n',
    ),
    LibraryEntry(
        'py-generator', 'Python generator function', 'Flow', ('.py', '.pyw'),
        'Create a generator function that yields values lazily.',
        'Valid Python; suitable for Ruff when installed.',
        'def [[cursor]]generate(items):\n    for item in items:\n        yield item\n',
    ),
    LibraryEntry(
        'py-contextlib-suppress', 'Python suppress exception', 'Flow', ('.py', '.pyw'),
        'Ignore one narrowly selected exception with contextlib.suppress.',
        'Valid Python; standard-library only.',
        'from contextlib import suppress\n\nwith suppress([[cursor]]FileNotFoundError):\n    [[selection]]pass\n',
    ),
    LibraryEntry(
        'py-dataclass', 'Python dataclass', 'Flow', ('.py', '.pyw'),
        'Define a compact data container with dataclasses.',
        'Valid Python; standard-library only.',
        'from dataclasses import dataclass\n\n@dataclass\nclass [[cursor]]Record:\n    name: str\n    value: int = 0\n',
    ),
    LibraryEntry(
        'py-tk-window', 'Python Windowed Tkinter window', 'Flow', ('.pyw',),
        'Create a minimal standard-library Tkinter application window.',
        'Valid Python Windowed code; Tkinter must be available in the Python installation.',
        'import tkinter as tk\n\nroot = tk.Tk()\nroot.title("[[cursor]]Sheepy Pad")\n[[selection]]\nroot.mainloop()\n',
    ),
    LibraryEntry(
        'py-tk-messagebox', 'Python Windowed message box', 'Flow', ('.pyw',),
        'Show a simple Tkinter information dialog.',
        'Valid Python Windowed code; Tkinter must be available.',
        'from tkinter import messagebox\n\nmessagebox.showinfo("[[cursor]]Title", "Message")\n',
    ),
    LibraryEntry(
        'py-argparse-positional', 'Python argparse positional', 'Arguments', ('.py',),
        'Add a required positional argument to an existing parser.',
        'Valid Python; expects a variable named parser.',
        'parser.add_argument("[[cursor]]path")\n',
    ),
    LibraryEntry(
        'py-argparse-int', 'Python argparse integer', 'Arguments', ('.py',),
        'Add an integer command-line option.',
        'Valid Python; expects a variable named parser.',
        'parser.add_argument("--[[cursor]]count", type=int, default=1)\n',
    ),
    LibraryEntry(
        'py-argparse-choice', 'Python argparse choices', 'Arguments', ('.py',),
        'Restrict an option to a known set of values.',
        'Valid Python; expects a variable named parser.',
        'parser.add_argument("--[[cursor]]mode", choices=("fast", "safe"), default="safe")\n',
    ),
    LibraryEntry(
        'py-argparse-default', 'Python argparse option with default', 'Arguments', ('.py',),
        'Add a string option with a default value.',
        'Valid Python; expects a variable named parser.',
        'parser.add_argument("--[[cursor]]output", default="output.txt")\n',
    ),
    LibraryEntry(
        'py-argparse-append', 'Python argparse repeated option', 'Arguments', ('.py',),
        'Collect a repeated command-line option into a list.',
        'Valid Python; expects a variable named parser.',
        'parser.add_argument("--[[cursor]]include", action="append", default=[])\n',
    ),
    LibraryEntry(
        'py-argparse-subcommands', 'Python argparse subcommands', 'Arguments', ('.py',),
        'Add a compact subcommand dispatcher to an ArgumentParser.',
        'Valid Python; expects a variable named parser.',
        'subparsers = parser.add_subparsers(dest="command", required=True)\nsubparsers.add_parser("[[cursor]]run")\nsubparsers.add_parser("check")\n',
    ),
    LibraryEntry(
        'py-sys-argv', 'Python raw argv', 'Arguments', ('.py',),
        'Read command-line arguments directly when argparse would be excessive.',
        'Valid Python; standard-library only.',
        'import sys\n\narguments = sys.argv[1:]\n[[cursor]]\n',
    ),
    LibraryEntry(
        'py-env-set', 'Python set environment variable', 'Environment', ('.py', '.pyw'),
        'Set one environment variable for this process and child processes.',
        'Valid Python; standard-library only.',
        'import os\n\nos.environ["[[cursor]]NAME"] = "value"\n',
    ),
    LibraryEntry(
        'py-home-dir', 'Python home directory', 'Environment', ('.py', '.pyw'),
        'Get the current user home directory as a pathlib Path.',
        'Valid Python; standard-library only.',
        'from pathlib import Path\n\nhome = Path.home()\n[[cursor]]\n',
    ),
    LibraryEntry(
        'py-expand-vars', 'Python expand environment variables', 'Environment', ('.py', '.pyw'),
        'Expand $NAME-style variables in a string.',
        'Valid Python; standard-library only.',
        'import os\n\nexpanded = os.path.expandvars("$[[cursor]]HOME/path")\n',
    ),
    LibraryEntry(
        'py-env-copy', 'Python child environment copy', 'Environment', ('.py', '.pyw'),
        'Create a modified environment mapping for subprocess calls.',
        'Valid Python; pass env=environment to subprocess APIs.',
        'import os\n\nenvironment = os.environ.copy()\nenvironment["[[cursor]]NAME"] = "value"\n',
    ),
    LibraryEntry(
        'py-file-exists', 'Python test file exists', 'Files', ('.py', '.pyw'),
        'Check whether a path exists before using it.',
        'Valid Python; standard-library pathlib.',
        'from pathlib import Path\n\npath = Path("[[cursor]]file.txt")\nif path.exists():\n    [[selection]]pass\n',
    ),
    LibraryEntry(
        'py-mkdir', 'Python create directory', 'Files', ('.py', '.pyw'),
        'Create a directory tree without failing when it already exists.',
        'Valid Python; standard-library pathlib.',
        'from pathlib import Path\n\nPath("[[cursor]]output").mkdir(parents=True, exist_ok=True)\n',
    ),
    LibraryEntry(
        'py-glob', 'Python glob files', 'Files', ('.py', '.pyw'),
        'Iterate over matching files using pathlib glob.',
        'Valid Python; standard-library pathlib.',
        'from pathlib import Path\n\nfor path in Path(".").glob("[[cursor]]*.txt"):\n    [[selection]]print(path)\n',
    ),
    LibraryEntry(
        'py-json-dump', 'Python write JSON', 'Files', ('.py', '.pyw'),
        'Write JSON with indentation and a trailing newline.',
        'Valid Python; standard-library only.',
        'import json\nfrom pathlib import Path\n\nPath("[[cursor]]data.json").write_text(json.dumps(data, indent=2) + "\\n", encoding="utf-8")\n',
    ),
    LibraryEntry(
        'py-csv-read', 'Python read CSV', 'Files', ('.py', '.pyw'),
        'Read CSV rows with csv.DictReader.',
        'Valid Python; standard-library only.',
        'import csv\n\nwith open("[[cursor]]data.csv", newline="", encoding="utf-8") as handle:\n    for row in csv.DictReader(handle):\n        [[selection]]print(row)\n',
    ),
    LibraryEntry(
        'py-csv-write', 'Python write CSV', 'Files', ('.py', '.pyw'),
        'Write dictionary rows to a CSV file.',
        'Valid Python; update fieldnames and rows for the task.',
        'import csv\n\nwith open("[[cursor]]data.csv", "w", newline="", encoding="utf-8") as handle:\n    writer = csv.DictWriter(handle, fieldnames=["name", "value"])\n    writer.writeheader()\n    writer.writerows(rows)\n',
    ),
    LibraryEntry(
        'py-toml-read', 'Python read TOML', 'Files', ('.py', '.pyw'),
        'Read TOML from a Python script using tomllib.',
        'Valid on Python 3.11 and newer; standard-library only.',
        'import tomllib\nfrom pathlib import Path\n\ndata = tomllib.loads(Path("[[cursor]]config.toml").read_text(encoding="utf-8"))\n',
    ),
    LibraryEntry(
        'py-config-read', 'Python read INI config', 'Files', ('.py', '.pyw'),
        'Read an INI-style configuration file with configparser.',
        'Valid Python; standard-library only.',
        'import configparser\n\nconfig = configparser.ConfigParser()\nconfig.read("[[cursor]]config.ini", encoding="utf-8")\n',
    ),
    LibraryEntry(
        'py-temp-dir', 'Python temporary directory', 'Files', ('.py', '.pyw'),
        'Create and automatically clean a temporary directory.',
        'Valid Python; standard-library only.',
        'from tempfile import TemporaryDirectory\n\nwith TemporaryDirectory() as temp_dir:\n    [[selection]][[cursor]]pass\n',
    ),
    LibraryEntry(
        'py-temp-file', 'Python temporary file', 'Files', ('.py', '.pyw'),
        'Create a named temporary file that closes automatically.',
        'Valid Python; standard-library only.',
        'from tempfile import NamedTemporaryFile\n\nwith NamedTemporaryFile(mode="w+", encoding="utf-8") as handle:\n    [[selection]][[cursor]]pass\n',
    ),
    LibraryEntry(
        'py-copy-file', 'Python copy file', 'Files', ('.py', '.pyw'),
        'Copy a file while preserving metadata where possible.',
        'Valid Python; standard-library shutil.',
        'from shutil import copy2\n\ncopy2("[[cursor]]source.txt", "destination.txt")\n',
    ),
    LibraryEntry(
        'py-move-file', 'Python move file', 'Files', ('.py', '.pyw'),
        'Move or rename a file with shutil.move.',
        'Valid Python; standard-library shutil.',
        'from shutil import move\n\nmove("[[cursor]]source.txt", "destination.txt")\n',
    ),
    LibraryEntry(
        'py-delete-file', 'Python remove file', 'Files', ('.py', '.pyw'),
        'Remove a file with pathlib.',
        'Valid Python; missing_ok requires Python 3.8+.',
        'from pathlib import Path\n\nPath("[[cursor]]file.txt").unlink(missing_ok=True)\n',
    ),
    LibraryEntry(
        'py-read-bytes', 'Python read binary file', 'Files', ('.py', '.pyw'),
        'Read an entire file as bytes.',
        'Valid Python; standard-library pathlib.',
        'from pathlib import Path\n\ndata = Path("[[cursor]]file.bin").read_bytes()\n',
    ),
    LibraryEntry(
        'py-write-bytes', 'Python write binary file', 'Files', ('.py', '.pyw'),
        'Write bytes to a file.',
        'Valid Python; standard-library pathlib.',
        'from pathlib import Path\n\nPath("[[cursor]]file.bin").write_bytes(data)\n',
    ),
    LibraryEntry(
        'py-subprocess-capture', 'Python capture command output', 'Processes', ('.py', '.pyw'),
        'Run a command safely and capture text stdout/stderr.',
        'Valid Python; argument-vector form avoids shell parsing.',
        'import subprocess\n\nresult = subprocess.run(["[[cursor]]command"], check=True, text=True, capture_output=True)\noutput = result.stdout\n',
    ),
    LibraryEntry(
        'py-subprocess-timeout', 'Python subprocess timeout', 'Processes', ('.py', '.pyw'),
        'Bound how long an external command may run.',
        'Valid Python; subprocess.TimeoutExpired may be handled by the caller.',
        'import subprocess\n\nsubprocess.run(["[[cursor]]command"], check=True, timeout=30)\n',
    ),
    LibraryEntry(
        'py-popen', 'Python start background process', 'Processes', ('.py', '.pyw'),
        'Start a child process without waiting immediately.',
        'Valid Python; remember to manage or wait for the returned process.',
        'import subprocess\n\nprocess = subprocess.Popen(["[[cursor]]command"])\n',
    ),
    LibraryEntry(
        'py-run-python', 'Python launch current interpreter', 'Processes', ('.py', '.pyw'),
        'Run another Python script with the same interpreter as Sheepy launched.',
        'Valid Python; standard-library only.',
        'import subprocess\nimport sys\n\nsubprocess.run([sys.executable, "[[cursor]]script.py"], check=True)\n',
    ),
    LibraryEntry(
        'py-signal-handler', 'Python signal handler', 'Processes', ('.py', '.pyw'),
        'Register a SIGTERM handler for graceful shutdown.',
        'Valid Python on platforms providing SIGTERM.',
        'import signal\n\ndef handle_term(signum, frame):\n    [[selection]][[cursor]]raise SystemExit(0)\n\nsignal.signal(signal.SIGTERM, handle_term)\n',
    ),
    LibraryEntry(
        'py-logging-basic', 'Python basic logging', 'Processes', ('.py', '.pyw'),
        'Configure a concise standard-library logger.',
        'Valid Python; standard-library logging.',
        'import logging\n\nlogging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")\nlogger = logging.getLogger(__name__)\nlogger.info("[[cursor]]Started")\n',
    ),
    LibraryEntry(
        'py-sleep', 'Python sleep', 'Processes', ('.py', '.pyw'),
        'Pause the current thread for a number of seconds.',
        'Valid Python; standard-library time.',
        'import time\n\ntime.sleep([[cursor]]1.0)\n',
    ),
    LibraryEntry(
        'py-thread', 'Python background thread', 'Processes', ('.py', '.pyw'),
        'Start a lightweight background thread.',
        'Valid Python; coordinate shared state carefully.',
        'from threading import Thread\n\nthread = Thread(target=[[cursor]]worker, daemon=True)\nthread.start()\n',
    ),
    LibraryEntry(
        'py-process-exit', 'Python exit with status', 'Processes', ('.py', '.pyw'),
        'Exit explicitly with a process status code.',
        'Valid Python; SystemExit is preferred to os._exit for normal scripts.',
        'raise SystemExit([[cursor]]0)\n',
    ),
    LibraryEntry(
        'py-current-dir', 'Python current working directory', 'Processes', ('.py', '.pyw'),
        'Read the process working directory as a pathlib Path.',
        'Valid Python; standard-library pathlib.',
        'from pathlib import Path\n\nworking_directory = Path.cwd()\n[[cursor]]\n',
    ),
    LibraryEntry(
        'shell-while', 'Shell while loop', 'Flow', ('.sh', '.bash', '.zsh'),
        'Insert a portable while loop.',
        'Compatible with sh/bash/zsh syntax checks.',
        'while [[cursor]]command; do\n    [[selection]]:\ndone\n',
    ),
    LibraryEntry(
        'shell-until', 'Shell until loop', 'Flow', ('.sh', '.bash', '.zsh'),
        'Repeat until a command succeeds.',
        'Compatible with sh/bash/zsh syntax checks.',
        'until [[cursor]]command; do\n    [[selection]]sleep 1\ndone\n',
    ),
    LibraryEntry(
        'shell-command-success', 'Shell command success branch', 'Flow', ('.sh', '.bash', '.zsh'),
        'Branch directly on whether a command succeeds.',
        'Compatible with sh/bash/zsh syntax checks and ShellCheck.',
        'if [[cursor]]command; then\n    [[selection]]printf \'%s\\n\' "success"\nelse\n    printf \'%s\\n\' "failed" >&2\nfi\n',
    ),
    LibraryEntry(
        'shell-strict-portable', 'Shell strict portable mode', 'Flow', ('.sh', '.bash'),
        'Enable exit-on-error and unset-variable checks without non-POSIX pipefail.',
        'Compatible with sh/bash syntax checks; intentionally omits pipefail for portability.',
        'set -eu\n[[cursor]]\n',
    ),
    LibraryEntry(
        'shell-usage', 'Shell usage function', 'Arguments', ('.sh', '.bash', '.zsh'),
        'Add a reusable usage message function.',
        'Compatible with sh/bash/zsh syntax checks.',
        'usage() {\n    printf \'Usage: %s [[cursor]][options]\\n\' "$0" >&2\n}\n',
    ),
    LibraryEntry(
        'shell-require-arg', 'Shell require argument', 'Arguments', ('.sh', '.bash', '.zsh'),
        'Require at least one positional argument.',
        'Compatible with sh/bash/zsh syntax checks and ShellCheck.',
        'if [ "$#" -lt 1 ]; then\n    printf \'Usage: %s [[cursor]]ARG\\n\' "$0" >&2\n    exit 2\nfi\n',
    ),
    LibraryEntry(
        'shell-default-arg', 'Shell argument with default', 'Arguments', ('.sh', '.bash', '.zsh'),
        'Read a positional argument with a fallback value.',
        'Compatible with sh/bash/zsh syntax checks.',
        'value=${1:-[[cursor]]default}\n',
    ),
    LibraryEntry(
        'shell-shift-loop', 'Shell option shift loop', 'Arguments', ('.sh', '.bash', '.zsh'),
        'Walk positional arguments manually with shift.',
        'Compatible with sh/bash/zsh syntax checks.',
        'while [ "$#" -gt 0 ]; do\n    case "$1" in\n        --[[cursor]]verbose) verbose=1 ;;\n        --) shift; break ;;\n        *) break ;;\n    esac\n    shift\ndone\n',
    ),
    LibraryEntry(
        'shell-export', 'Shell export environment variable', 'Environment', ('.sh', '.bash', '.zsh'),
        'Set and export an environment variable to child processes.',
        'Compatible with sh/bash/zsh syntax checks.',
        'export [[cursor]]NAME="value"\n',
    ),
    LibraryEntry(
        'shell-path-prepend', 'Shell prepend PATH', 'Environment', ('.sh', '.bash', '.zsh'),
        'Prepend a directory to PATH without discarding the existing value.',
        'Compatible with sh/bash/zsh syntax checks.',
        'PATH="[[cursor]]/path/to/bin:$PATH"\nexport PATH\n',
    ),
    LibraryEntry(
        'shell-unset', 'Shell unset variable', 'Environment', ('.sh', '.bash', '.zsh'),
        'Remove a shell/environment variable.',
        'Compatible with sh/bash/zsh syntax checks.',
        'unset [[cursor]]NAME\n',
    ),
    LibraryEntry(
        'shell-file-exists', 'Shell test file exists', 'Files', ('.sh', '.bash', '.zsh'),
        'Check whether a regular file exists.',
        'Compatible with sh/bash/zsh syntax checks and ShellCheck.',
        'if [ -f "[[cursor]]file.txt" ]; then\n    [[selection]]:\nfi\n',
    ),
    LibraryEntry(
        'shell-dir-exists', 'Shell test directory exists', 'Files', ('.sh', '.bash', '.zsh'),
        'Check whether a directory exists.',
        'Compatible with sh/bash/zsh syntax checks and ShellCheck.',
        'if [ -d "[[cursor]]directory" ]; then\n    [[selection]]:\nfi\n',
    ),
    LibraryEntry(
        'shell-mkdir', 'Shell create directory', 'Files', ('.sh', '.bash', '.zsh'),
        'Create a directory tree with mkdir -p.',
        'Compatible with sh/bash/zsh syntax checks; mkdir is an external utility.',
        'mkdir -p -- "[[cursor]]output"\n',
    ),
    LibraryEntry(
        'shell-copy-file', 'Shell copy file', 'Files', ('.sh', '.bash', '.zsh'),
        'Copy a file using cp with option terminator.',
        'Compatible with sh/bash/zsh syntax checks; cp is an external utility.',
        'cp -- "[[cursor]]source" "destination"\n',
    ),
    LibraryEntry(
        'shell-atomic-write', 'Shell temporary write then move', 'Files', ('.sh', '.bash', '.zsh'),
        'Write through a temporary file and replace the destination only at the end.',
        'Compatible with sh/bash/zsh syntax checks; mktemp/mv are external utilities.',
        'tmp_file=$(mktemp) || exit 1\ntrap \'rm -f -- "$tmp_file"\' EXIT\nprintf \'%s\\n\' "[[cursor]]value" > "$tmp_file"\nmv -- "$tmp_file" "output.txt"\ntrap - EXIT\n',
    ),
    LibraryEntry(
        'shell-find-files', 'Shell find files loop', 'Files', ('.sh', '.bash', '.zsh'),
        'Read NUL-delimited paths from find safely.',
        'find -print0 is widely available but not required by POSIX; ShellCheck can analyse quoting.',
        'find "[[cursor]]." -type f -print0 | while IFS= read -r -d \'\' path; do\n    [[selection]]printf \'%s\\n\' "$path"\ndone\n',
    ),
    LibraryEntry(
        'shell-command-v', 'Shell command availability', 'Processes', ('.sh', '.bash', '.zsh'),
        'Check whether a command is available on PATH.',
        'Compatible with sh/bash/zsh syntax checks and ShellCheck.',
        'if command -v [[cursor]]git >/dev/null 2>&1; then\n    [[selection]]:\nfi\n',
    ),
    LibraryEntry(
        'shell-capture-output', 'Shell capture command output', 'Processes', ('.sh', '.bash', '.zsh'),
        'Capture stdout from a command substitution.',
        'Compatible with sh/bash/zsh syntax checks.',
        'output=$([[cursor]]command) || exit $?\n',
    ),
    LibraryEntry(
        'shell-status', 'Shell preserve exit status', 'Processes', ('.sh', '.bash', '.zsh'),
        'Capture and test a command exit status.',
        'Compatible with sh/bash/zsh syntax checks.',
        '[[cursor]]command\nstatus=$?\nif [ "$status" -ne 0 ]; then\n    exit "$status"\nfi\n',
    ),
    LibraryEntry(
        'shell-signal-trap', 'Shell INT/TERM trap', 'Processes', ('.sh', '.bash', '.zsh'),
        'Handle interruption and termination signals.',
        'Compatible with sh/bash/zsh syntax checks.',
        'on_signal() {\n    [[selection]][[cursor]]exit 130\n}\ntrap on_signal INT TERM\n',
    ),
    LibraryEntry(
        'shell-retry', 'Shell retry loop', 'Processes', ('.sh', '.bash', '.zsh'),
        'Retry a command a bounded number of times.',
        'Compatible with sh/bash/zsh syntax checks.',
        'attempt=1\nwhile [ "$attempt" -le 3 ]; do\n    [[cursor]]command && break\n    attempt=$((attempt + 1))\n    sleep 1\ndone\n',
    ),
    LibraryEntry(
        'shell-pid-alive', 'Shell test PID alive', 'Processes', ('.sh', '.bash', '.zsh'),
        'Probe whether a process ID still exists using signal 0.',
        'Compatible with sh/bash/zsh syntax checks.',
        'if kill -0 "[[cursor]]$pid" 2>/dev/null; then\n    [[selection]]:\nfi\n',
    ),
    LibraryEntry(
        'shell-read-prompt', 'Shell read prompt', 'Arguments', ('.sh', '.bash', '.zsh'),
        'Prompt and read one line without interpreting backslashes.',
        'Compatible with sh/bash/zsh syntax checks.',
        "printf '[[cursor]]Continue? [y/N] '\nIFS= read -r answer\n",
    ),
    LibraryEntry(
        'bash-strict', 'Bash strict mode', 'Flow', ('.bash',),
        'Enable Bash ERR tracing, exit-on-error, unset-variable and pipefail behavior.',
        'Bash -n compatible; ShellCheck can analyse this pattern.',
        'set -Eeuo pipefail\n[[cursor]]\n',
    ),
    LibraryEntry(
        'bash-script-dir', 'Bash BASH_SOURCE script directory', 'Files', ('.bash',),
        'Resolve the directory containing the current Bash script.',
        'Bash -n compatible; robust against a different working directory.',
        'SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"\n[[cursor]]\n',
    ),
    LibraryEntry(
        'bash-double-bracket', 'Bash [[ ]] conditional', 'Flow', ('.bash',),
        'Use Bash extended conditional syntax without word-splitting.',
        'Bash -n compatible; ShellCheck can analyse the condition.',
        'if [[ [[cursor]]-n "$value" ]]; then\n    [[selection]]:\nfi\n',
    ),
    LibraryEntry(
        'bash-regex', 'Bash regex match', 'Flow', ('.bash',),
        'Match a string with Bash =~ regular-expression syntax.',
        'Bash -n compatible.',
        'if [[ "$value" =~ [[cursor]]^[0-9]+$ ]]; then\n    [[selection]]:\nfi\n',
    ),
    LibraryEntry(
        'bash-array', 'Bash indexed array', 'Flow', ('.bash',),
        'Create and iterate a Bash indexed array.',
        'Bash -n compatible.',
        'items=("one" "two" "[[cursor]]three")\nfor item in "${items[@]}"; do\n    [[selection]]printf \'%s\\n\' "$item"\ndone\n',
    ),
    LibraryEntry(
        'bash-assoc-array', 'Bash associative array', 'Flow', ('.bash',),
        'Create and read a Bash associative array.',
        'Bash -n compatible on modern Bash.',
        'declare -A values=([name]="[[cursor]]Sheepy" [mode]="safe")\nprintf \'%s\\n\' "${values[name]}"\n',
    ),
    LibraryEntry(
        'bash-mapfile', 'Bash mapfile lines', 'Files', ('.bash',),
        'Read a file into an indexed array with mapfile.',
        'Bash -n compatible; ShellCheck may suggest portability alternatives for sh.',
        'mapfile -t lines < "[[cursor]]file.txt"\n',
    ),
    LibraryEntry(
        'bash-process-substitution', 'Bash process substitution', 'Processes', ('.bash',),
        'Feed command output to a loop without a pipeline subshell.',
        'Bash -n compatible.',
        'while IFS= read -r line; do\n    [[selection]][[cursor]]printf \'%s\\n\' "$line"\ndone < <(command)\n',
    ),
    LibraryEntry(
        'bash-read-prompt', 'Bash read prompt', 'Arguments', ('.bash',),
        'Prompt with Bash read -p and preserve backslashes.',
        'Bash -n compatible.',
        'read -r -p "[[cursor]]Continue? [y/N] " answer\n',
    ),
    LibraryEntry(
        'bash-err-trap', 'Bash ERR trap', 'Processes', ('.bash',),
        'Report the line and status when a command triggers ERR.',
        'Bash -n compatible; intended with ERR-trace/errexit policies as appropriate.',
        'on_error() {\n    local status=$?\n    printf \'Error at line %s (status %s)\\n\' "$LINENO" "$status" >&2\n}\ntrap on_error ERR\n[[cursor]]\n',
    ),
    LibraryEntry(
        'bash-select', 'Bash select menu', 'Arguments', ('.bash',),
        'Create a simple interactive numbered choice menu.',
        'Bash -n compatible.',
        'select choice in "one" "two" "[[cursor]]quit"; do\n    [[selection]]break\ndone\n',
    ),
    LibraryEntry(
        'bash-parameter-replace', 'Bash parameter replacement', 'Environment', ('.bash',),
        'Replace text inside a variable using Bash parameter expansion.',
        'Bash -n compatible.',
        'result=${value//[[cursor]]old/new}\n',
    ),
    LibraryEntry(
        'zsh-strict', 'Zsh strict options', 'Flow', ('.zsh',),
        'Enable Zsh error, unset-variable and pipeline-failure options.',
        'Compatible with zsh -n.',
        'setopt ERR_EXIT NO_UNSET PIPE_FAIL\n[[cursor]]\n',
    ),
    LibraryEntry(
        'zsh-script-dir', 'Zsh script directory', 'Files', ('.zsh',),
        'Resolve the current Zsh script directory with a native modifier.',
        'Compatible with zsh -n.',
        'SCRIPT_DIR=${0:A:h}\n[[cursor]]\n',
    ),
    LibraryEntry(
        'zsh-array', 'Zsh array', 'Flow', ('.zsh',),
        'Create and iterate a native Zsh array.',
        'Compatible with zsh -n.',
        'items=(one two [[cursor]]three)\nfor item in $items; do\n    [[selection]]print -r -- "$item"\ndone\n',
    ),
    LibraryEntry(
        'zsh-assoc', 'Zsh associative array', 'Flow', ('.zsh',),
        'Create a Zsh associative array with typeset -A.',
        'Compatible with zsh -n.',
        'typeset -A values\nvalues=(name "[[cursor]]Sheepy" mode safe)\nprint -r -- "$values[name]"\n',
    ),
    LibraryEntry(
        'zsh-glob-qualifier', 'Zsh glob qualifier files', 'Files', ('.zsh',),
        'Select regular files with a Zsh glob qualifier.',
        'Compatible with zsh -n; NOMATCH behavior depends on options.',
        'for path in [[cursor]]*.txt(.); do\n    [[selection]]print -r -- "$path"\ndone\n',
    ),
    LibraryEntry(
        'zsh-recursive-glob', 'Zsh recursive glob', 'Files', ('.zsh',),
        'Recursively iterate matching files with Zsh **/.',
        'Compatible with zsh -n.',
        'for path in **/[[cursor]]*.py(.); do\n    [[selection]]print -r -- "$path"\ndone\n',
    ),
    LibraryEntry(
        'zsh-zparseopts', 'Zsh zparseopts flag', 'Arguments', ('.zsh',),
        'Parse a simple Zsh option with zparseopts.',
        'Compatible with zsh -n; zparseopts is a Zsh builtin module feature.',
        'zmodload zsh/zutil\nzparseopts -D -E -- [[cursor]]v=verbose\n',
    ),
    LibraryEntry(
        'zsh-path-modifiers', 'Zsh path modifiers', 'Files', ('.zsh',),
        'Split a path into directory and filename using Zsh modifiers.',
        'Compatible with zsh -n.',
        'directory=${[[cursor]]path:h}\nfilename=${path:t}\n',
    ),
    LibraryEntry(
        'zsh-read-prompt', 'Zsh read prompt', 'Arguments', ('.zsh',),
        'Prompt and read one line using Zsh read syntax.',
        'Compatible with zsh -n.',
        'read "answer?[[cursor]]Continue? [y/N] "\n',
    ),
    LibraryEntry(
        'zsh-autoload', 'Zsh autoload function', 'Flow', ('.zsh',),
        'Autoload a standard or user function in Zsh style.',
        'Compatible with zsh -n.',
        'autoload -Uz [[cursor]]function_name\n',
    ),
    LibraryEntry(
        'fish-while', 'Fish while loop', 'Flow', ('.fish',),
        'Insert a Fish while loop.',
        'Compatible with fish -n.',
        'while [[cursor]]command\n    [[selection]]\nend\n',
    ),
    LibraryEntry(
        'fish-begin', 'Fish begin block', 'Flow', ('.fish',),
        'Group commands into a Fish begin/end block.',
        'Compatible with fish -n.',
        'begin\n    [[selection]][[cursor]]\nend\n',
    ),
    LibraryEntry(
        'fish-and-or', 'Fish and / or chain', 'Flow', ('.fish',),
        'Run follow-up commands based on the previous status.',
        'Compatible with fish -n.',
        '[[cursor]]command\nand echo success\nor echo failed >&2\n',
    ),
    LibraryEntry(
        'fish-string-match', 'Fish string match', 'Flow', ('.fish',),
        'Match text with Fish string match.',
        'Compatible with fish -n.',
        'if string match -q -- "[[cursor]]pattern" "$value"\n    [[selection]]\nend\n',
    ),
    LibraryEntry(
        'fish-string-replace', 'Fish string replace', 'Flow', ('.fish',),
        'Replace text using the Fish string builtin.',
        'Compatible with fish -n.',
        'set -l result (string replace -- "[[cursor]]old" "new" "$value")\n',
    ),
    LibraryEntry(
        'fish-require-arg', 'Fish require argument', 'Arguments', ('.fish',),
        'Require at least one command-line argument.',
        'Compatible with fish -n.',
        'if test (count $argv) -lt 1\n    echo "Usage: (status filename) [[cursor]]ARG" >&2\n    return 2\nend\n',
    ),
    LibraryEntry(
        'fish-argparse-value', 'Fish argparse value option', 'Arguments', ('.fish',),
        'Parse an option that requires a value.',
        'Compatible with fish -n.',
        "argparse '[[cursor]]o/output=' -- $argv; or return 2\nset -l output $_flag_output\n",
    ),
    LibraryEntry(
        'fish-usage', 'Fish usage function', 'Arguments', ('.fish',),
        'Add a reusable Fish usage function.',
        'Compatible with fish -n.',
        'function usage\n    echo "Usage: "(status filename)" [[cursor]][options]" >&2\nend\n',
    ),
    LibraryEntry(
        'fish-export', 'Fish export variable', 'Environment', ('.fish',),
        'Set and export a variable to child processes.',
        'Compatible with fish -n.',
        'set -gx [[cursor]]NAME "value"\n',
    ),
    LibraryEntry(
        'fish-unset', 'Fish erase variable', 'Environment', ('.fish',),
        'Remove a Fish variable.',
        'Compatible with fish -n.',
        'set -e [[cursor]]NAME\n',
    ),
    LibraryEntry(
        'fish-env-default', 'Fish environment default', 'Environment', ('.fish',),
        'Use a fallback value when a variable is unset.',
        'Compatible with fish -n.',
        'set -q [[cursor]]NAME; or set -l NAME default\n',
    ),
    LibraryEntry(
        'fish-path-prepend', 'Fish prepend PATH', 'Environment', ('.fish',),
        'Prepend a directory using fish_add_path.',
        'Compatible with fish -n on modern Fish.',
        'fish_add_path --prepend "[[cursor]]/path/to/bin"\n',
    ),
    LibraryEntry(
        'fish-file-exists', 'Fish test file exists', 'Files', ('.fish',),
        'Check whether a regular file exists.',
        'Compatible with fish -n.',
        'if test -f "[[cursor]]file.txt"\n    [[selection]]\nend\n',
    ),
    LibraryEntry(
        'fish-dir-exists', 'Fish test directory exists', 'Files', ('.fish',),
        'Check whether a directory exists.',
        'Compatible with fish -n.',
        'if test -d "[[cursor]]directory"\n    [[selection]]\nend\n',
    ),
    LibraryEntry(
        'fish-mkdir', 'Fish create directory', 'Files', ('.fish',),
        'Create a directory tree with mkdir -p.',
        'Compatible with fish -n; mkdir is an external utility.',
        'mkdir -p -- "[[cursor]]output"\n',
    ),
    LibraryEntry(
        'fish-read-lines', 'Fish read file lines', 'Files', ('.fish',),
        'Read a text file line by line in Fish.',
        'Compatible with fish -n.',
        'while read -l line\n    [[selection]][[cursor]]echo "$line"\nend < file.txt\n',
    ),
    LibraryEntry(
        'fish-write-file', 'Fish write text file', 'Files', ('.fish',),
        'Write text to a file with printf redirection.',
        'Compatible with fish -n.',
        'printf \'%s\\n\' "[[cursor]]value" > output.txt\n',
    ),
    LibraryEntry(
        'fish-temp-file', 'Fish temporary file', 'Files', ('.fish',),
        'Create a temporary file and keep its path locally.',
        'Compatible with fish -n; mktemp is an external utility.',
        'set -l temp_file (mktemp); or return 1\n[[cursor]]\n',
    ),
    LibraryEntry(
        'fish-glob', 'Fish glob files', 'Files', ('.fish',),
        'Iterate over files matching a Fish glob.',
        'Compatible with fish -n; unmatched glob behavior depends on command context.',
        'for path in [[cursor]]*.txt\n    [[selection]]echo "$path"\nend\n',
    ),
    LibraryEntry(
        'fish-command-q', 'Fish command availability', 'Processes', ('.fish',),
        'Check whether a command is available.',
        'Compatible with fish -n.',
        'if command -q [[cursor]]git\n    [[selection]]\nend\n',
    ),
    LibraryEntry(
        'fish-capture-output', 'Fish capture command output', 'Processes', ('.fish',),
        'Capture command output with Fish command substitution.',
        'Compatible with fish -n.',
        'set -l output ([[cursor]]command)\n',
    ),
    LibraryEntry(
        'fish-status-check', 'Fish check command status', 'Processes', ('.fish',),
        'Branch on the previous command status.',
        'Compatible with fish -n.',
        '[[cursor]]command\nif test $status -ne 0\n    return $status\nend\n',
    ),
    LibraryEntry(
        'fish-signal-handler', 'Fish signal handler', 'Processes', ('.fish',),
        'Handle SIGTERM with a Fish event function.',
        'Compatible with fish -n.',
        'function on_term --on-signal TERM\n    [[selection]][[cursor]]exit 0\nend\n',
    ),
    LibraryEntry(
        'fish-sleep', 'Fish sleep', 'Processes', ('.fish',),
        'Pause execution for a number of seconds.',
        'Compatible with fish -n; sleep is an external utility on typical systems.',
        'sleep [[cursor]]1\n',
    ),
    LibraryEntry(
        'fish-pid-alive', 'Fish test PID alive', 'Processes', ('.fish',),
        'Probe a process ID with signal 0.',
        'Compatible with fish -n.',
        'if kill -0 $[[cursor]]pid 2>/dev/null\n    [[selection]]\nend\n',
    ),
    LibraryEntry(
        'fish-read-prompt', 'Fish read prompt', 'Arguments', ('.fish',),
        'Prompt and read a value into a local variable.',
        'Compatible with fish -n.',
        'read -l -P "[[cursor]]Continue? [y/N] " answer\n',
    ),
)

ENTRIES = (*ENTRIES, *EXTRA_ENTRIES)

BUILTIN_ENTRY_BY_KEY = {entry.key: entry for entry in ENTRIES}
LIBRARY_CATEGORIES = (
    "Favourites",
    "All",
    "Flow",
    "Arguments",
    "Environment",
    "Files",
    "Processes",
    "Custom",
)


def normalise_suffix(value: str | Path | None) -> str:
    """Return one supported Library suffix, defaulting to Python."""
    if value is None:
        return ".py"
    if isinstance(value, Path):
        suffix = value.suffix.casefold()
    else:
        raw = str(value).strip().casefold()
        suffix = raw if raw.startswith(".") else Path(raw).suffix.casefold()
    return suffix if suffix in SUPPORTED_LIBRARY_SUFFIXES else ".py"


def custom_entries_from_preferences(value: object) -> tuple[LibraryEntry, ...]:
    """Validate and convert the persisted custom-snippet user layer."""
    if not isinstance(value, list):
        return ()
    result: list[LibraryEntry] = []
    seen: set[str] = set()
    for raw in value[:MAX_CUSTOM_SNIPPETS]:
        if not isinstance(raw, dict):
            continue
        key = raw.get("key")
        label = raw.get("label")
        suffix = normalise_suffix(raw.get("suffix"))
        body = raw.get("body")
        description = raw.get("description", "User-defined snippet.")
        if not isinstance(key, str) or not key.startswith("custom-") or key in seen:
            continue
        if not isinstance(label, str) or not (1 <= len(label.strip()) <= 120):
            continue
        if not isinstance(body, str) or len(body.encode("utf-8")) > MAX_SNIPPET_BODY:
            continue
        if not isinstance(description, str) or len(description) > 500:
            description = "User-defined snippet."
        seen.add(key)
        result.append(
            LibraryEntry(
                key,
                label.strip(),
                "Custom",
                (suffix,),
                description.strip() or "User-defined snippet.",
                lint_hint_for_suffix(suffix),
                body,
                True,
            )
        )
    return tuple(result)


def serialise_custom_entries(entries: tuple[LibraryEntry, ...] | list[LibraryEntry]) -> list[dict[str, str]]:
    """Return the bounded JSON-safe custom-snippet user layer."""
    result: list[dict[str, str]] = []
    for entry in list(entries)[:MAX_CUSTOM_SNIPPETS]:
        if not entry.custom:
            continue
        result.append(
            {
                "key": entry.key,
                "label": entry.label,
                "suffix": entry.suffixes[0],
                "description": entry.description,
                "body": entry.body,
            }
        )
    return result


def lint_hint_for_suffix(suffix: str) -> str:
    suffix = normalise_suffix(suffix)
    if suffix in {".py", ".pyw"}:
        return "Python syntax check; Ruff when installed."
    if suffix == ".fish":
        return "fish -n syntax check."
    if suffix in {".sh", ".bash"}:
        return "Interpreter -n syntax check; ShellCheck when installed."
    return "zsh -n syntax check."


def entry_map(custom_entries: tuple[LibraryEntry, ...] | list[LibraryEntry] = ()) -> dict[str, LibraryEntry]:
    result = dict(BUILTIN_ENTRY_BY_KEY)
    result.update({entry.key: entry for entry in custom_entries if entry.custom})
    return result


def normalise_favourites(
    value: object,
    custom_entries: tuple[LibraryEntry, ...] | list[LibraryEntry] = (),
) -> list[str]:
    """Return a stable bounded list containing only known snippet keys."""
    if not isinstance(value, list):
        return []
    known = set(entry_map(custom_entries))
    result: list[str] = []
    for item in value[:128]:
        if isinstance(item, str) and item in known and item not in result:
            result.append(item)
    return result


def matching_entries(
    suffix: str | Path | None,
    *,
    category: str = "All",
    query: str = "",
    favourites: tuple[str, ...] | list[str] = (),
    custom_entries: tuple[LibraryEntry, ...] | list[LibraryEntry] = (),
) -> tuple[LibraryEntry, ...]:
    """Return snippets filtered by file type/category/search text."""
    selected_suffix = normalise_suffix(suffix)
    favourite_set = set(favourites)
    needle = query.strip().casefold()
    matched: list[LibraryEntry] = []
    for entry in (*ENTRIES, *tuple(custom_entries)):
        if selected_suffix not in entry.suffixes:
            continue
        if category == "Favourites" and entry.key not in favourite_set:
            continue
        if category == "Custom" and not entry.custom:
            continue
        if category not in {"All", "Favourites", "Custom"} and entry.category != category:
            continue
        if needle:
            haystack = " ".join(
                (entry.label, entry.category, entry.description, entry.lint_hint)
            ).casefold()
            if needle not in haystack:
                continue
        matched.append(entry)
    return tuple(matched)


def default_library_category(
    suffix: str | Path | None,
    favourites: tuple[str, ...] | list[str] = (),
    custom_entries: tuple[LibraryEntry, ...] | list[LibraryEntry] = (),
) -> str:
    """Return Favourites only when that category has visible entries; otherwise All."""
    visible = matching_entries(
        suffix,
        category="Favourites",
        favourites=favourites,
        custom_entries=custom_entries,
    )
    return "Favourites" if visible else "All"


def render_entry(entry: LibraryEntry, selection: str = "") -> tuple[str, int]:
    """Render selection/cursor markers and return text plus desired cursor offset."""
    body = entry.body.replace(SELECTION_MARKER, selection)
    marker = body.find(CURSOR_MARKER)
    if marker < 0:
        return body, len(body)
    rendered = body.replace(CURSOR_MARKER, "", 1).replace(CURSOR_MARKER, "")
    return rendered, marker
