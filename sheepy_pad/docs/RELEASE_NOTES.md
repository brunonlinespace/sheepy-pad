# Sheepy Pad 0.4.2 — Root README / AppImage Documentation Contract

Sheepy Pad 0.4.2 is a narrowly scoped publication and packaging-contract release based on 0.4.1.

- Install the approved public-facing `README.md` at source root next to `main.py`, with all existing wording preserved apart from the release number.
- Lock the approved root README content: subsequent releases may only update version numbers unless expressly authorised.
- Update the source-root release gate, source manifest, and packaging regression tests to require the public README.
- Require the root README during Fedora AppImage build, record its SHA-256 in build provenance, and include it as `PUBLIC-README.md` alongside the existing internal application `README.md` without replacing that application documentation.
- Advance application, Suite component, desktop, AppStream and AppImage release identities to **0.4.2**.
- No editor, syntax highlighter, Library, script execution, interpreter, file-handling, preference, shortcut or visual behaviour changes.

---

# Sheepy Pad 0.4.1 — Editor Scrolling / Gutter Corrective

Sheepy Pad 0.4.1 is a narrowly scoped editor-behaviour corrective based on 0.4.0.

## Changes

- Disables QPlainTextEdit's global `centerOnScroll` policy so the document no longer scrolls the final lines unusually high above the bottom edge, reducing the large scrollable blank area after end-of-file.
- Preserves deliberate centring for **Go To Line**, which still calls `centerCursor()` explicitly after moving the cursor.
- Ports Maqarony Pad's horizontal-scrollbar gutter geometry fix: when the native horizontal scrollbar is visible, the line-number gutter stops above the scrollbar instead of painting behind the scrollbar strip.
- The gutter fix is limited to geometry; line-number visibility, width calculation, colours, fonts, scrolling and editor themes are unchanged.
- No Library, runtime, shortcut, menu, file-handling or AppImage-hardening changes.

## Packaging

- Application/package version advances to **0.4.1**.
- Existing hardened AppImage build architecture and dependency exclusions are retained.
