# Sheepy Pad 0.4.2 — QA Test Plan


## 0.3.0-r4 startup / Library / editor-palette checks

| ID | Area | Procedure | Expected result |
|---|---|---|---|
| LIB-01 | Startup | Launch with no file. | Compact Start a Document form is shown with Document type, default checkbox, Create Document and Open Existing File; no template controls are present. |
| LIB-02 | Default | Select a type, tick **Use this type as my default**, create it, then use `Ctrl+N`. | The saved type becomes the default. Use **File → Default New Document... → Always Ask** to restore the chooser. |
| LIB-03 | File | Inspect File. | `New`, `New Type...`, `Default New Document...`, `Open...`, separator, then `Document Type` appear in the established order. |
| LIB-04 | Layout | Cycle all four layouts on Start a Document. | Toolbar/Find vertical ordering matches the saved layout exactly. |
| LIB-05 | Find | Inspect Start a Document, then create/open a file. | Visible Find host is greyed/disabled on Start and enabled with an active document. |
| LIB-06 | Edit | Open Edit on Start, then on an active document and in View Only. | All Edit items disabled on Start; normal actions restore on activation; View Only disables mutating actions while Copy/Select All/Go To Line remain enabled. |
| LIB-07 | Snippets | Inspect Library for each runnable type. | No Templates category or template creation exists; only compatible snippets are shown and Syntax/Lint guidance matches the type. |
| LIB-08 | Favourites | Favourite/unfavourite snippets from floating/sidebar Library and use **Run → Library → My Favourites**. | Favourites tab is first and all Library surfaces/menu stay synchronized across restart. |
| LIB-09 | Custom | Add/remove a custom snippet using `[[selection]]`/`[[cursor]]`. | Custom tab updates and insertion follows the active document type. |
| LIB-10 | Transfer | Export/import `.sheepysnippets`; test Merge, Replace and Cancel. | Only custom snippets/favourites form the user collection; bounded validation and safe replacement behavior apply. |
| LIB-11 | Sidebar | Cycle **Left Sidebar**, **Right Sidebar**, **Floating Only**, resize, restart. | Labels/placement match Timblee; position and useful width persist; Floating Only hides embedded panel but **Run → Library → Library...** still opens. |
| LIB-12 | Sidebar controls | Enable Left/Right Sidebar. | Sidebar uses a compact catalogue dropdown (not tabs) and a small × close button; × transiently hides the sidebar without changing the saved Left/Right placement. Ctrl+L restores that same sidebar. Floating Library remains tabbed. |
| LIB-13 | No-document sidebar | Save Left or Right Sidebar, close/reopen to Start a Document, then create/open a script. | Embedded Library is hidden on Start a Document without changing the saved placement; it reappears automatically once a document is active. |
| LIB-14 | Split geometry | Test both split layouts with Left Sidebar and Right Sidebar. | Sidebar spans the full workspace height; split Find bar is confined to the editor column at its configured top/bottom edge. |
| LIB-15 | Catalogue depth | Inspect/search every runnable type and compare against r3 favourites/custom data. | All prior snippets still exist; the enriched catalogue exposes high-frequency Python/Python Windowed, sh, Bash, Zsh and Fish patterns with type-appropriate Syntax/Lint guidance. |
| LIB-16 | Favourite stars | Favourite and unfavourite entries in sidebar and floating Library. | Favourite rows gain a leading ★ immediately on both surfaces; removing the favourite removes the marker. |
| LIB-17 | Ctrl+L — Floating | Set **Floating Only**, press `Ctrl+L` twice. | Floating Library opens, then closes. |
| LIB-18 | Ctrl+L — Sidebar | Set Left/Right Sidebar with an active document, press `Ctrl+L` twice. | Configured sidebar hides then returns without changing the checked View → Library placement. On Start a Document the embedded sidebar remains hidden. |
| LIB-R5 | Sidebar management controls | Compare embedded Left/Right Library with floating Library. | Sidebar omits Add/Remove Custom and Import/Export buttons; floating Library still shows all four controls. |
| MEN-34 | File shortcuts | Test Properties, External Editor, Rename, Duplicate and Containing Folder; inspect Delete File. | Properties and Delete File have no shortcut; Ctrl+Shift+E, F2, Ctrl+Shift+D and Ctrl+Shift+O work for External Editor, Rename, Duplicate and Containing Folder respectively. |
| MEN-35 | Run shortcuts | Trigger Run actions from keyboard. | Ctrl+1 Launch in Terminal; Ctrl+Shift+1 Launch as Admin; Ctrl+2 Run with Arguments; Ctrl+3 Syntax / Lint Check; Ctrl+4 Select Interpreter; Ctrl+5 Working Directory; Ctrl+6 Environment Profiles. |
| MEN-33 | Run/Library | Inspect toolbar and Run menu. | No permanent document-type toolbar shortcut exists; Run → Library is immediately after Environment Profiles... and before the Stop/Force Stop separator. |
| EDT-30 | Palette | Toggle Dark Editor. | Editor canvas, gutter, selection/search colours and syntax switch dark/light independently of AppImage chrome. |
| EDT-31 | Persistence | Untick Dark Editor, restart. | Light editor is restored; fresh config defaults to Dark Editor checked. |
| MEN-30 | View | Inspect drag/drop submenu. | `File Drag and Drop → Opens on Active Window / Opens on New Window`. |
| MEN-31 | Run | Inspect Run. | Make/Remove Executable is first, separator follows it, shortcut is Ctrl+Shift+X. |
| MEN-32 | Edit | Inspect Edit and test normal/View Only/no-document states. | Toggle Comment is followed by a separator; Duplicate Line / Selection is Ctrl+D; Delete Line is Ctrl+Shift+K and is treated as mutating. |
| PKG-30 | AppImage | Run existing hardened build/smoke matrix. | 0.3.0 AppImage builds with existing theme checks and optional-Qt exclusions intact. |

Use **P** pass, **F** fail, **B** blocked, **N/R** not run.

| ID | Area | Procedure | Expected result |
|---|---|---|---|
| BLD-01 | Source | Extract archive and list root. | Root contains only `main.py`, `README.md`, `suite-pythoine-component.json`, and `sheepy_pad/`. |
| BLD-02 | Source | `python main.py`. | Sheepy Pad opens normally. |
| BLD-03 | AppImage | Run Fedora build script. | Produces `Sheepy-Pad-0.4.2-<native-arch>.AppImage` and metadata/checksum files. |
| BLD-04 | Assets | Inspect taskbar, window and About icons. | Approved transparent Sheepy Pad logo is used without surrounding backdrop. |
| FIL-01 | Python | Open/save/rename/duplicate `.py` and `.pyw`. | Both types remain fully supported. |
| FIL-02 | Shell | Open/save/rename/duplicate `.sh`, `.bash`, `.zsh`. | All remain fully supported. |
| FIL-03 | Fish | Open/save/rename/duplicate `.fish`. | Fish remains fully supported. |
| FIL-04 | Scope | Try `.txt`, `.toml`, `.ini`, `.env`. | Visible unsupported-file prompt; active document is not replaced. |
| HIL-01 | Python | Open representative Python. | Python colours are applied. |
| HIL-02 | Shell | Open sh/bash/zsh samples. | Shell colours are applied. |
| HIL-03 | Fish | Open Fish sample with `set`, `function`, variables and comments. | Dedicated Fish colouring is applied. |
| HIL-04 | Shebang | Open `.sh` containing `#!/usr/bin/env fish`. | Fish highlighting is selected. |
| RUN-01 | Python | Launch `.py` and `.pyw`. | Selected/shebang/default Python resolution works. |
| RUN-02 | sh | Launch `.sh`. | Selected interpreter, shebang or bash/sh fallback works. |
| RUN-03 | Bash | Launch `.bash`. | Bash is used unless explicitly overridden/shebang-selected. |
| RUN-04 | Zsh | Launch `.zsh`. | Zsh is used unless explicitly overridden/shebang-selected. |
| RUN-05 | Fish | Launch `.fish`. | Fish is used unless explicitly overridden/shebang-selected. |
| RUN-06 | Shebang | Give `.sh` a valid Fish/Python shebang. | Shebang takes priority over extension default. |
| RUN-07 | Selector | Run → Select Interpreter. | Automatic and explicit interpreter selection work and persist by suffix. |
| RUN-08 | Arguments | Press `Ctrl+2`, use quoted/spaced arguments. | Script receives the intended argument vector; no shell expansion occurs. |
| RUN-09 | Arguments terminal | Choose Run in terminal in Run with Arguments. | Script launches in terminal with the same arguments. |
| RUN-10 | Working dir | Select custom working directory and launch. | Script starts with that working directory. |
| RUN-11 | Working dir | Restore script-folder mode. | Script starts in its containing folder. |
| ENV-01 | Profiles | Create profile with multiple NAME=value entries and set active. | Values persist and are passed to a normal launch. |
| ENV-02 | Profiles | Launch in terminal with active profile. | Values are visible to the child script. |
| ENV-03 | Profiles | Enter invalid variable name. | Save is rejected with clear validation message. |
| CHK-01 | Python | Syntax / Lint Check valid/invalid Python. | Valid source passes; syntax error is reported without importing script. |
| CHK-02 | Shell | Syntax / Lint Check sh/bash/zsh. | Interpreter syntax-only check reports correctly. |
| CHK-03 | Fish | Syntax / Lint Check Fish. | `fish -n`-style validation reports correctly. |
| CHK-04 | Linters | Repeat with Ruff/ShellCheck absent and present. | Optional linter is used when available and safely skipped otherwise. |
| STA-01 | Status | Inspect saved executable/non-executable scripts. | `Exec: Yes`/`Exec: No` appears before Ln/Col/Char. |
| STA-02 | Status | Open untitled or Windows build. | `Exec: N/A` is shown where appropriate. |
| VIE-01 | View Only | Enable and attempt edit. | Edit blocked; first attempt explains View → View Only. |
| VIE-02 | View Only | Disable View Only. | Confirmation offers Keep View Only or Continue. |
| THM-01 | AppImage | Toggle View → Dark Mode. | AppImage chrome changes; editor palette remains controlled independently by View → Dark Editor. |
| THM-02 | AppImage | Inspect Python/shell/Fish colours in light mode. | Good foreground/background contrast remains. |
| SEC-01 | Launch | Use arguments containing spaces/metacharacters. | Arguments are passed as values, not evaluated by a shell. |
| SEC-02 | Config | Inspect environment profile JSON. | Permissions remain private; UI warns profiles are not a secret store. |
## Standardized AppImage builder (0.1.0-r1)

| ID | Platform | Procedure | Expected result |
|---|---|---|---|
| STD-01 | Fedora | Build with no `APPIMAGETOOL_PATH`. | Builder stages the continuous appimagetool download through `.part`, checks the 200 MiB ceiling and ELF header, then creates the normal 0.1.0 AppImage. |
| STD-02 | Fedora | Set `APPIMAGETOOL_PATH` to a valid local x86_64 appimagetool. | Builder uses that exact file and does not download another copy. |
| STD-03 | Fedora | Set `APPIMAGETOOL_PATH` to a missing path. | Build stops before AppImage creation with a clear error. |
| STD-04 | Fedora | Set a correct `APPIMAGETOOL_SHA256`. | Hash verification succeeds and build continues. |
| STD-05 | Fedora | Set an incorrect `APPIMAGETOOL_SHA256`. | Build stops with `appimagetool SHA-256 verification failed.` |
| STD-06 | Fedora | Inspect generated build-info. | The resolved `appimagetool SHA-256` is recorded. |
| STD-07 | Fedora | Inspect final filename. | Output remains `Sheepy-Pad-0.1.0-x86_64.AppImage`; host Fedora/desktop version does not leak into it. |


## Hardened AppImage builder (0.1.0-r2)

| ID | Platform | Procedure | Expected result |
|---|---|---|---|
| HRD-01 | Fedora | Run builder normally on supported host. | Preflight checks host commands/Python venv support before build work begins. |
| HRD-02 | Fedora | Inspect builder and run static QA. | No host package installer or privilege-elevation command is executed by the builder. |
| HRD-03 | x86_64/aarch64 | Build natively. | Host architecture is selected automatically; requested cross-builds are rejected. |
| HRD-04 | Unsupported host | Run without override, then with `SHEEPY_PAD_ALLOW_UNSUPPORTED_HOST=1`. | First run stops; explicit intentional-test override permits continuation. |
| HRD-05 | Dependencies | Complete venv installation. | `pip check` passes before PyInstaller runs. |
| HRD-06 | Metadata | Hide/remove optional `desktop-file-validate`/`appstreamcli` from PATH. | Built-in desktop/AppStream checks still run; optional external checks are skipped with info message. |
| HRD-07 | Bundle | Inspect frozen Qt payload. | XCB exists; Qt PDF, PrintSupport and WebEngine are absent. |
| HRD-08 | Smoke | Build AppDir and final AppImage. | Isolated offscreen `--version` passes for system/dark/light modes at both stages. |
| HRD-09 | Tool cache | Build twice without `APPIMAGETOOL_PATH`. | Valid cached appimagetool is reused on the second build. |
| HRD-10 | Release mode | Set `SHEEPY_PAD_RELEASE_BUILD=1` without a hash, then with correct `APPIMAGETOOL_SHA256`. | Unpinned release build stops; pinned release build continues. |
| HRD-11 | Provenance | Inspect build-info. | Host, architecture, Python/PyInstaller/PyQt/Qt, source tree, tool/output hashes and smoke-test status are recorded. |
| HRD-12 | Source | Inspect extracted source after QA/build. | Root remains only `main.py` and `sheepy_pad/`; source caches are cleaned. |


## Suite-aligned packaging/QA refresh (0.1.0-r3)

| ID | Platform | Procedure | Expected result |
|---|---|---|---|
| R3-01 | Source | Inspect extracted root and `sheepy_pad/sheepy-pad.json`. | Root remains only `main.py` + `sheepy_pad/`; identity manifest matches Sheepy Pad 0.1.0 metadata. |
| R3-02 | QA | Run `bash sheepy_pad/qa/static-qa.sh`. | Release checker, full unit suite and shell syntax checks pass. |
| R3-03 | Source | Seed `__pycache__`, `.pyc` or `.pyo`, then run/exit the builder. | Source caches are removed before QA/build and again by the EXIT cleanup trap. |
| R3-04 | Build venv | Observe environment preparation. | Full source compile runs with build Python and redirected bytecode; `pip check` passes. |
| R3-05 | AppDir GUI | Let builder run AppDir smoke matrix. | Real offscreen GUI initialization prints `GUI smoke test passed.` in base/system/dark/light launches. |
| R3-06 | AppDir CLI | Let builder run AppDir version matrix. | Exact `Sheepy Pad 0.1.0` is returned in base/system/dark/light launches. |
| R3-07 | Final GUI | Let builder run final AppImage smoke matrix. | Real offscreen GUI initialization passes in base/system/dark/light launches. |
| R3-08 | Final CLI | Let builder run final AppImage version matrix. | Exact `Sheepy Pad 0.1.0` is returned in base/system/dark/light launches. |
| R3-09 | Download | Force appimagetool download. | Curl uses HTTPS/TLS restrictions, retries, 30-second connect timeout, 300-second total timeout, 200 MiB ceiling, ELF validation and `.part` staging. |
| R3-10 | Provenance | Inspect build-info. | Fedora, privilege policy, main/source/project manifests, requirements, builder, source tree, tool/output hashes and smoke status are present. |
| R3-11 | Bundle | Inspect final Qt payload. | XCB is present; PDF, PrintSupport and WebEngine remain absent. |

## 0.2.0 Portapad-aligned theme checks

| ID | Area | Action | Expected |
|---|---|---|---|
| THM-20 | AppDir | Run builder theme matrix. | Exact `Sheepy Pad 0.2.0` version probe passes for dark, light and system modes. |
| THM-21 | AppDir GUI | Run themed GUI smoke matrix. | Real Sheepy Pad window initializes successfully in dark, light and system modes. |
| THM-22 | Final AppImage | Run builder theme matrix. | Exact `Sheepy Pad 0.2.0` version probe passes for dark, light and system modes. |
| THM-23 | Final AppImage GUI | Run themed GUI smoke matrix. | Real Sheepy Pad window initializes successfully in dark, light and system modes. |
| THM-24 | Source/portable | Launch outside AppImage. | No AppImage-only Dark Mode action is exposed; host Qt theme remains authoritative. |


## 0.2.0-r1 optional Qt payload hotfix

| ID | Area | Action | Expected |
|---|---|---|---|
| PDF-01 | PyInstaller | Inspect `sheepy-pad.spec`. | QtPdf/QtPdfWidgets, PrintSupport and WebEngine modules are explicitly excluded and binary/data TOCs are defensively filtered. |
| PDF-02 | AppDir assembly | Build with a PyQt/PyInstaller combination that would otherwise contribute Qt PDF. | Optional PDF/printing/WebEngine files are removed before validation. |
| PDF-03 | Bundle | Run `validate_bundle`. | No Qt PDF, PrintSupport or WebEngine payload remains; XCB remains present. |
| PDF-04 | GUI | Complete AppDir and final-AppImage smoke matrices. | Base plus dark/light/system real GUI and version probes all pass after trimming. |
## 0.2.0-r3 run-control / terminal-supervision hotfix

| ID | Area | Action | Expected |
|---|---|---|---|
| RUN-30 | Toolbar idle | Open a saved runnable script without launching it. | Toolbar shows `Launch`, `In Terminal`, `As Admin`; `Stop` and `Force Stop` are hidden. |
| RUN-31 | Toolbar running | Launch a supervised script normally. | Launch controls hide; `Stop` and `Force Stop` appear in their place. |
| RUN-32 | Toolbar finish | Let the supervised script exit normally. | `Stop`/`Force Stop` disappear and the three launch controls return automatically. |
| RUN-33 | Terminal/TUI | Launch a TUI script in terminal, then close the terminal window. | TUI child stops, terminal-session state clears, and the idle launch controls return. |
| RUN-34 | Stop | During a supervised run press `Stop`. | Graceful stop is requested; toolbar remains in running state until the tracked process/session is actually cleared. |
| RUN-35 | Force Stop | During a supervised run press `Force Stop`. | Tracked process/session is force-stopped and idle launch controls return. |
| RUN-36 | AppImage regression | Compare critical packaging files with 0.2.0-r2. | AppImage builder/spec/AppRun/desktop/AppStream files are byte-for-byte unchanged. |
| EDT-31 | EOF scrolling | Open a short document with many empty viewport rows, move to the last line and scroll. | Final lines remain naturally near the bottom; the document cannot be centered high enough to expose the former excessive EOF blank scroll region. |
| EDT-32 | Horizontal scrollbar gutter | Disable wrapping, create a line wider than the editor and show the horizontal scrollbar. | The line-number gutter stops above the native horizontal scrollbar and is not painted behind its strip. |



## 0.4.2 public README / AppImage packaging checks

| ID | Area | Procedure | Expected result |
|---|---|---|---|
| PUB-01 | Source root | Extract 0.4.2 source ZIP and inspect top-level entries. | Approved `README.md` sits beside `main.py` and Suite manifest. |
| PUB-02 | Locked README | Compare release README with approved 0.4.1 version after normalising release-number occurrences. | Content and formatting are otherwise byte-identical; static QA rejects any non-version modification. |
| PUB-03 | Builder preflight | Temporarily omit `README.md` in a QA copy of source; invoke builder input validation. | Builder rejects missing root README before building. |
| PUB-04 | AppDir docs | Inspect staged AppDir documentation directory. | `README.md` retains internal application help; `PUBLIC-README.md` is the root GitHub-facing README. |
| PUB-05 | Build provenance | Build AppImage and inspect `*.build-info.txt`. | `README.md SHA-256` matches approved source-root README. |
| PUB-06 | Release identity | Inspect app, Suite manifest, desktop, AppStream and AppImage name. | All current-release identities consistently use 0.4.2. |
