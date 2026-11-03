#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROGRAM_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd -P)"
HOST_ARCH_RAW="$(uname -m)"
case "$HOST_ARCH_RAW" in
    x86_64) HOST_ARCH="x86_64" ;;
    aarch64|arm64) HOST_ARCH="aarch64" ;;
    *) printf 'Unsupported architecture: %s\n' "$HOST_ARCH_RAW" >&2; exit 2 ;;
esac
ARCH="${ARCH:-$HOST_ARCH}"
IMAGE="${1:-$PROGRAM_ROOT/dist/Sheepy-Pad-0.4.2-${ARCH}.AppImage}"
SMOKE_HOME="$(mktemp -d "${TMPDIR:-/tmp}/sheepy-pad-appimage-test.XXXXXX")"
trap 'rm -rf "$SMOKE_HOME"' EXIT

[[ -x "$IMAGE" ]] || { echo "AppImage not found or not executable: $IMAGE" >&2; exit 2; }
mkdir -p "$SMOKE_HOME/.config" "$SMOKE_HOME/.cache" "$SMOKE_HOME/.local/share" "$SMOKE_HOME/Documents"

run_image() {
    timeout 30s env \
        HOME="$SMOKE_HOME" \
        XDG_CONFIG_HOME="$SMOKE_HOME/.config" \
        XDG_CACHE_HOME="$SMOKE_HOME/.cache" \
        XDG_DATA_HOME="$SMOKE_HOME/.local/share" \
        QT_QPA_PLATFORM=offscreen \
        QT_QUICK_BACKEND=software \
        "$IMAGE" --appimage-extract-and-run "$@"
}

run_image --version
run_image --sheepy-pad-smoke-test
for theme in dark light system; do
    run_image --appimage-theme="$theme" --version
    run_image --appimage-theme="$theme" --sheepy-pad-smoke-test
done
if [[ -f "$IMAGE.sha256" ]]; then
    (cd "$(dirname -- "$IMAGE")" && sha256sum -c "$(basename -- "$IMAGE.sha256")")
fi
printf 'AppImage GUI/version/theme smoke tests passed.\n'
