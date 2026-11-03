#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROGRAM_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
SOURCE_ROOT="$(CDPATH= cd -- "$PROGRAM_ROOT/.." && pwd)"
PYTHON="${SHEEPY_PAD_PORTABLE_PYTHON:-python3}"
exec "$PYTHON" "$SOURCE_ROOT/main.py" "$@"
