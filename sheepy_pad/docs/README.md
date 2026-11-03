# Sheepy Pad

**Friendly. Fast. Focused.**

Sheepy Pad 0.4.2 is a lightweight standalone PyQt6 editor and launcher for runnable Python and shell scripts.

Repository: https://github.com/brunonlinespace/sheepy-pad

## Supported files

- Python: `.py`, `.pyw`
- Shell: `.sh`, `.bash`, `.zsh`
- Fish: `.fish`

Sheepy Pad intentionally remains runnable-script-only; general `.txt`, `.toml`, `.ini` and `.env` files are out of scope.

## 0.3.0-r4 highlights

- Carries the established Timblee/JSTS presentation forward and applies the later Timblee sidebar/split-layout refinements without changing Sheepy Pad's runnable-script scope.
- **Start a Document** is the compact no-document form: **Document type**, **Use this type as my default**, **Create Document**, and **Open Existing File...**. The available types are Python (`.py`), Python Windowed (`.pyw`), Shell (`.sh`), Bash (`.bash`), Zsh (`.zsh`) and Fish (`.fish`).
- **File** now follows the family creation model with **New**, **New Type...**, **Default New Document...**, **Open...**, and **Document Type**. `Ctrl+N` uses the configured default or asks for a type when **Always Ask** is selected.
- Start a Document and the editor share one document stack inside the editor column. In split layouts the Find bar is inside that editor column, so a left/right Library sidebar spans the full workspace height.
- Find remains visible but disabled on Start a Document; `Ctrl+F`, `F3`, `Shift+F3` and `Esc` follow document-active state.
- The Edit menu remains visible but every Edit action is disabled with no document. View Only remains a separate active-document restriction that still permits Copy, Select All and Go To Line.
- The **Library is snippet-only**. The initial 0.3.0 template experiment has been removed completely.
- Library tabs are **Favourites**, **All**, **Flow**, **Arguments**, **Environment**, **Files**, **Processes**, **Custom**. Snippets are automatically filtered to the active document type and include matching Syntax/Lint guidance.
- Favourites are persistent and shared between the **Favourites** catalogue and **Run → Library → My Favourites**.
- User snippets can be added/removed and imported/exported as a bounded `.sheepysnippets` user collection with Merge/Replace handling.
- **View → Library** is above Layout and offers exactly **Left Sidebar**, **Right Sidebar**, **Floating Only**. Floating Only is the default and leaves **Run → Library → Library...** available as the modeless floating Library. Sidebar mode uses a compact catalogue dropdown and small × close button; × only hides the current sidebar transiently and does not change the saved Left/Right placement. Ctrl+L restores it. Its custom-snippet and import/export management buttons are intentionally omitted. The floating Library remains tabbed and retains those management controls. The embedded sidebar is suppressed on **Start a Document** even when Left/Right is the saved preference, and returns automatically when a document becomes active.
- Persistent **View → Dark Editor**, enabled by default, independently controls the editor canvas, gutter, selections, search highlighting and Python/shell/Fish syntax colours. AppImage **Dark Mode** controls application chrome only.
- **View → File Drag and Drop → Opens on Active Window / Opens on New Window**.
- **Run → Make/Remove Executable** remains first in Run and uses `Ctrl+Shift+X`; the **Library** submenu now sits directly after **Environment Profiles...** and before the Stop/Force Stop separator.
- The snippet catalogue is substantially enriched while preserving every prior built-in entry: **156 built-in snippets** across Python/Python Windowed, POSIX shell, Bash, Zsh and Fish, all filtered to the active type with Syntax/Lint guidance.
- Favourite snippets display a leading **★** in both embedded and floating Library lists, synchronized with **My Favourites**.
- `Ctrl+L` follows the saved Library view: it toggles the floating Library in **Floating Only**, or temporarily hides/shows the configured left/right sidebar for an active document without changing that saved placement.
- File shortcuts: **Open in External Editor Ctrl+Shift+E**, **Rename F2**, **Duplicate File Ctrl+Shift+D**, **Open Containing Folder Ctrl+Shift+O**. **Properties** and **Delete File** intentionally have no keyboard shortcut.
- The permanent toolbar Document Type shortcut is removed; document type remains available from **File → Document Type**.
- Edit harmonisation retains **Duplicate Line / Selection** (`Ctrl+D`) and **Delete Line** (`Ctrl+Shift+K`).
- The hardened AppImage/PyInstaller policy and Qt PDF/PrintSupport/WebEngine exclusions are preserved.

## Portable source layout

The extracted source root intentionally contains only:

```text
main.py
sheepy_pad/
```

Launch from source with:

```bash
python main.py
```

or:

```bash
./sheepy_pad/portable/run-sheepy-pad.sh
```

Build the Fedora AppImage with:

```bash
./sheepy_pad/packaging/fedora/build-appimage.sh
```

Expected AppImage output:

```text
sheepy_pad/dist/Sheepy-Pad-0.4.2-x86_64.AppImage
```

Preferences on Linux:

```text
~/.config/brunonlinespace/sheepy-pad/sheepy-pad.json
```

Environment profiles are stored in that JSON file as plain text. Do not put passwords, tokens or other secrets in them.

Licensed under GPLv3-or-later.
