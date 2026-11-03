# Sheepy Pad 0.4.2 — Building

The hardened AppImage build architecture from 0.2.0-r4 is preserved. The new Library/start-state/editor-palette features do not add Qt PDF, PrintSupport, WebEngine or other heavy optional dependencies.


## Source layout

The source root intentionally contains only `main.py` and `sheepy_pad/`. Do not move build tooling back to the root; keeping it under the program directory is part of the portable-source design.

## Source run

From the extracted root:

```bash
python3 -m venv sheepy_pad/.venv
source sheepy_pad/.venv/bin/activate
python -m pip install -r sheepy_pad/requirements.txt
python main.py
```

## Fedora AppImage

Install dependencies:

```bash
./sheepy_pad/packaging/fedora/install-build-deps.sh
```

Build:

```bash
./sheepy_pad/packaging/fedora/build-appimage.sh
```

Expected output:

```text
sheepy_pad/dist/Sheepy-Pad-0.4.2-<arch>.AppImage
sheepy_pad/dist/Sheepy-Pad-0.4.2-<arch>.AppImage.sha256
sheepy_pad/dist/Sheepy-Pad-0.4.2-<arch>.build-info.txt
sheepy_pad/dist/Sheepy-Pad-0.4.2-<arch>.build-python-lock.txt
```

`<arch>` is the detected native `x86_64` or `aarch64` architecture.

The application version is stored separately from `/etc/os-release`, so Fedora or desktop-edition labels cannot replace `0.4.2` in the AppImage filename.

The build removes generated Python bytecode before release validation and keeps all build products under `sheepy_pad/build` and `sheepy_pad/dist`.

Printing support remains excluded from the PyInstaller bundle.

## Sheepy Pad 0.2.0 theme-validation alignment

The 0.2.0 builder retains the Suite-aligned r3 GUI smoke infrastructure and explicitly carries forward the latest Portapad AppImage theme-version probes. Both the AppDir and final AppImage are checked in `dark`, `light`, and `system` modes, while Sheepy Pad additionally constructs the real GUI under each theme. The application artifact is `Sheepy-Pad-0.2.0-<arch>.AppImage`.

## Suite-aligned hardened AppImage builder (0.1.0-r3)

The r3 source refresh retains application version `0.1.0` and adds the newer Suite Pythoine QA/provenance layer. `sheepy_pad/sheepy-pad.json` is the build identity manifest, `sheepy_pad/SOURCE_MANIFEST.sha256` is a required integrity input, and `sheepy_pad/qa/static-qa.sh` is the canonical static QA wrapper. These remain under `sheepy_pad/`, so the extracted root is still only `main.py` plus `sheepy_pad/`.

Before PyInstaller runs, the builder cleans source caches, runs static/release QA, creates an isolated venv, installs requirements, compiles the complete Python source with bytecode redirected to `sheepy_pad/build/`, and runs `pip check`.

The application exposes a hidden packaging-only smoke hook:

```text
--sheepy-pad-smoke-test
```

The builder uses it offscreen with an isolated HOME/XDG profile to construct the actual GUI. AppDir and final-AppImage checks include real GUI initialization plus `--version` in Sheepy Pad's system, dark and light theme modes.

AppImage tool downloads retain HTTPS/TLS hardening, `.part` staging, the 200 MiB ceiling, ELF verification and optional/release-required SHA-256 pinning, and now also have a 300-second total curl timeout. Build-info records the builder, source/project manifests, requirements, source tree, tool and output hashes.

## Hardened Pad-family AppImage builder (0.1.0-r2)

The r2 source refresh keeps the application version at `0.1.0` and adopts the newer hardened Pad-family builder architecture. The builder remains non-privileged and does not install host packages.

It auto-detects native `x86_64` or `aarch64` builds and refuses cross-building. Fedora 43/44 are the validated hosts. Intentional testing elsewhere requires:

```bash
SHEEPY_PAD_ALLOW_UNSUPPORTED_HOST=1 \
  ./sheepy_pad/packaging/fedora/build-appimage.sh
```

By default, `appimagetool` is cached under `${XDG_CACHE_HOME:-~/.cache}/sheepy-pad-appimage-tools/`. A known local tool can be supplied with:

```bash
APPIMAGETOOL_PATH=/path/to/appimagetool-x86_64.AppImage \
  ./sheepy_pad/packaging/fedora/build-appimage.sh
```

For audited builds, pin the expected tool SHA-256:

```bash
APPIMAGETOOL_SHA256=<expected-sha256> \
  ./sheepy_pad/packaging/fedora/build-appimage.sh
```

Formal release mode requires that pin:

```bash
SHEEPY_PAD_RELEASE_BUILD=1 \
APPIMAGETOOL_SHA256=<expected-sha256> \
  ./sheepy_pad/packaging/fedora/build-appimage.sh
```

The builder performs host preflight checks, cache-clean release QA, `pip check`, built-in desktop/AppStream checks, Qt-bundle validation and isolated AppDir/final-AppImage smoke tests. It rejects unexpected Qt PDF, Qt PrintSupport and Qt WebEngine payloads. The resolved appimagetool, source tree and final output hashes are recorded in build-info.


### Optional Qt payload trimming (0.2.0-r1)

Sheepy Pad does not use Qt PDF, Qt PrintSupport or Qt WebEngine. The PyInstaller spec excludes these modules and filters matching collected binary/data entries. As an additional packaging boundary, the AppImage assembler removes any matching optional Qt payload that a PyQt/PyInstaller hook still contributes transitively. The subsequent bundle validation and real-GUI smoke matrix remain mandatory; the build fails rather than shipping an unvalidated trimmed bundle.


## Public README (0.4.2 onward)

The project-root `README.md` is the approved, locked GitHub-facing README.
The Fedora builder requires it, includes its SHA-256 in the build-information
file, and places a copy at `usr/share/doc/sheepy-pad/PUBLIC-README.md` in
AppDir. The internal `sheepy_pad/docs/README.md` remains the separate
application Help documentation and is packaged as `usr/share/doc/sheepy-pad/README.md`.
No changes to the public README are permitted beyond the version number unless
explicitly authorised.
