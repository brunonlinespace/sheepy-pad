# Sheepy Pad changelog

## 0.4.2 — 2026-11-03

- Publish the approved, locked GitHub `README.md` at source root; subsequent editions may change only its version number unless explicitly instructed.
- Update Fedora AppImage build-input preflight, include the public README alongside the existing internal application documentation, and record its SHA-256 in build provenance.
- Extend source manifest/QA and advance release identities. No editor, Library, run, UI or preferences changes.

## 0.4.1 — 2026-10-18

- Disabled global center-on-scroll so end-of-file no longer leaves an excessive scrollable blank region below short documents.
- Ported Maqarony Pad's gutter geometry fix so the line-number gutter stops above the native horizontal scrollbar rather than showing behind it.
- Preserved explicit Go To Line centring and all 0.4.0 runtime/UI/Library/AppImage behavior otherwise.

## 0.4.0 — 2026-09-23

- AppImage/portable packaging alignment with the canonical Suite Pythoine component contract.
- Pad-family slogan corrected to “Friendly. Fast. Focused.”
- Application behavior otherwise unchanged from 0.3.0-r8.

## 0.3.0-r8
- Library defaults to Favourites only when the current document type has visible favourites; otherwise it defaults to All.
- Removing the final visible favourite while Favourites is selected immediately falls back to All.

## 0.3.0-r7
- Changed the embedded Library × to transiently hide the current Left/Right sidebar while preserving the saved View → Library placement; Ctrl+L restores it.
- Added Ctrl+4 for Select Interpreter, Ctrl+5 for Working Directory, and Ctrl+6 for Environment Profiles.

## 0.3.0-r6
- Remapped Open in External Editor to Ctrl+Shift+E.
- Remapped Launch in Terminal to Ctrl+1, Launch as Admin in Terminal to Ctrl+Shift+1, Run with Arguments to Ctrl+2, and Syntax / Lint Check to Ctrl+3.

# Sheepy Pad 0.3.0-r5 — 2026-08-23

- Removed Add/Remove Custom and Import/Export controls from the embedded Left/Right Library sidebar only; floating Library remains unchanged.
- Removed the non-working Alt+Enter keybinding from File → Properties; Properties now has no shortcut.
- Preserved r4 Library contents, favourites, Ctrl+L behavior, runtime behavior and hardened AppImage packaging.

# Sheepy Pad 0.3.0-r4 — 2026-08-23

- Preserved all 37 previous built-in snippets and expanded the catalogue to 156 practical, type-aware snippets spanning Python/Python Windowed, sh, Bash, Zsh and Fish.
- Added Timblee/JSTS-style leading ★ favourite markers to Library rows.
- Added placement-aware `Ctrl+L`: floating-dialog toggle for Floating Only, transient sidebar hide/show for Left/Right with an active document.
- Remapped file actions: Properties Alt+Enter; External Editor Ctrl+Alt+O; Rename F2; Duplicate File Ctrl+Shift+D; Open Containing Folder Ctrl+Shift+O; removed Delete File shortcut.
- Preserved no-document Library suppression, split geometry, runtime behavior and hardened AppImage packaging.

# Sheepy Pad 0.3.0

- r3: hide the embedded Left/Right Library sidebar on Start a Document while preserving/restoring the saved placement when a document becomes active.

# Changelog

## 0.3.0-r2 — 2026-08-23

- Moved the Library command surface into **Run → Library**, directly after **Environment Profiles...** and before the Stop/Force Stop separator; removed the top-level Library menu/button.
- Removed the permanent toolbar Document Type shortcut; File → Document Type remains the canonical type control.
- Sidebar Library now uses a compact catalogue dropdown plus small × close button; floating Library remains tabbed.
- Updated split layouts so the split Find bar lives inside the editor column while left/right Library sidebars span the full workspace height.
- Preserved snippet/favourites behavior, no-document state, Dark Editor, runtime behavior and hardened AppImage packaging.

## 0.3.0-r1 — 2026-08-22

- Corrected Start a Document to the established Timblee/JSTS compact type/default creation form.
- Added the matching File → New Type..., Default New Document..., and Document Type model.
- Purged all templates; Library is now snippet-only and follows the active document type.
- Restored Favourites-first Library behavior and Library → My Favourites synchronization.
- Added custom snippet add/remove plus versioned import/export user collections.
- Corrected View → Library to Left Sidebar / Right Sidebar / Floating Only, with Floating Only as the default.
- Preserved the shared stacked no-document workspace, disabled Find/Edit state, Dark Editor, runtime features and hardened AppImage packaging.

## 0.3.0 — 2026-08-22

- Initial 0.3.0 Library/startup experiment; its template layer and non-standard presentation are superseded by 0.3.0-r1.
- Added Start a Document no-document workspace; Find stays visible/disabled and Edit stays visible/disabled until a document is active.
- Added independent persistent Dark Editor, default on.
- Harmonised File Drag and Drop wording.
- Moved Make/Remove Executable to top of Run and changed shortcut to Ctrl+Shift+X.
- Harmonised Edit with Timblee: Duplicate Line / Selection and Delete Line (Ctrl+Shift+K).
- Preserved hardened AppImage dependency exclusions and smoke-test architecture.


## 0.2.0-r4

- Toolbar-only hotfix: move the dynamic `Make Exec` / `Remove Exec` control before the launch/stop control bank.
- Idle order: `Make/Remove Exec | Launch | In Terminal | As Admin`; running order: `Make/Remove Exec | Stop | Force Stop`.
- No runtime, menu, shortcut, theme or AppImage-packaging changes.

# Changelog

## 0.2.0-r1

- Packaging-only hotfix: prevent unused Qt PDF, Qt PrintSupport and Qt WebEngine payloads from entering the Sheepy Pad AppImage.
- Added PyInstaller module exclusions, defensive TOC filtering and pre-validation AppDir trimming while retaining strict negative bundle checks and GUI/theme smoke tests.

# Sheepy Pad Changelog

## 0.2.0

Application-version release aligning AppImage dark/light/system validation with the latest Portapad builder. The Portapad-style version probes run against both AppDir and final AppImage, while Sheepy Pad retains its stronger real-GUI themed smoke matrix and all r3 packaging hardening.

## 0.1.0-r3

Packaging/QA-only refresh aligned with the newer Suite Pythoine hardening: project identity manifest, static-QA wrapper, full-source build-Python compilation, guaranteed cache cleanup, real offscreen GUI smoke tests, download total timeout and richer build provenance. Application behavior remains 0.1.0.

# Changelog

## Sheepy Pad 0.1.0-r2 — Source / Packaging Refresh

- Adapted the newer hardened Portapad/Ricopad AppImage-builder architecture to Sheepy Pad.
- Added non-privileged-policy and host-prerequisite preflight checks.
- Added native `x86_64`/`aarch64` architecture detection and cross-build refusal.
- Added explicit Fedora 43/44 host gating with an intentional-test override.
- Added `pip check`, built-in desktop/AppStream validation and isolated offscreen smoke tests.
- Added Qt bundle validation requiring XCB and rejecting Qt PDF, PrintSupport and WebEngine.
- Moved reusable appimagetool caching to the XDG cache directory and hardened HTTPS download handling.
- Added formal release mode requiring a pinned appimagetool SHA-256.
- Expanded build provenance while preserving Sheepy Pad's cache-clean QA and two-item portable root.
- Kept the application version at 0.1.0.

## Sheepy Pad 0.1.0-r1 — Source / Packaging Refresh

- Adopted the current standardized Fedora AppImage build script without changing the application version.
- Added local `APPIMAGETOOL_PATH` override support.
- Added optional `APPIMAGETOOL_SHA256` verification.
- Switched the default appimagetool source to the continuous release URL.
- Added `.part` download staging, 200 MiB size guard and ELF-header validation.
- Added appimagetool SHA-256 recording to build-info.
- Retained the non-privileged builder, Ricopad-style two-item source root and `Sheepy-Pad-0.1.0-x86_64.AppImage` output name.


## Sheepy Pad 0.1.0

- Adopted the approved transparent-background Sheepy Pad master logo.
- Expanded runnable file support to `.py`, `.pyw`, `.sh`, `.bash`, `.zsh` and `.fish`.
- Added a dedicated Fish syntax highlighter.
- Added shebang-aware interpreter detection.
- Added persistent interpreter selection by script type.
- Added Run with Arguments (`Ctrl+Shift+R`) with direct argument-vector parsing.
- Added environment-variable profiles.
- Added syntax/lint checking (`Ctrl+Shift+L`) with optional host Ruff/ShellCheck integration.
- Added persistent working-directory selection.
- Added executable-permission status to the status bar.
- Retained View Only, AppImage-only dark/light themes, safe file handling, launch supervision and the Ricopad-style two-item portable root.
