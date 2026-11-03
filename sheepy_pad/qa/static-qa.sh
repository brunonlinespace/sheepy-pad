#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROGRAM_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
PROJECT_ROOT="$(cd -- "$PROGRAM_ROOT/.." && pwd -P)"
export PYTHONDONTWRITEBYTECODE=1

python3 "$PROGRAM_ROOT/tools/release_check.py"
(cd "$PROJECT_ROOT" && python3 -m unittest discover -s sheepy_pad/tests -v)

for script in \
    "$PROGRAM_ROOT/packaging/fedora/build-appimage.sh" \
    "$PROGRAM_ROOT/packaging/fedora/install-build-deps.sh" \
    "$PROGRAM_ROOT/packaging/fedora/test-appimage.sh" \
    "$PROGRAM_ROOT/portable/run-sheepy-pad.sh"; do
    bash -n "$script"
done

printf 'Sheepy Pad static QA passed.\n'
