# Sheepy Pad 0.4.2 — Security Notes

The 0.2.0 release retains the guarded runnable-script file and process model while strengthening AppImage theme validation.

- Only regular `.py`, `.pyw`, `.sh`, `.bash`, `.zsh` and `.fish` files are accepted.
- Reads are bounded at 25 MiB and reject FIFOs/devices/special files.
- Save, rename, delete and executable-permission operations use file-state/identity checks to reduce path-replacement races.
- Preferences are size-bounded, written atomically and kept in a private configuration directory.
- Run with Arguments uses `shlex` only to split the user's text into an argument vector; the resulting launch uses QProcess/subprocess argument arrays and never evaluates the arguments through a shell.
- Interpreter resolution accepts an explicit executable, a parsed shebang or a known extension default; executable lookup is performed against the host environment rather than bundled AppImage paths.
- Environment profiles validate variable names and are bounded, but values are stored as plain text in `sheepy-pad.json`. They must not be treated as a credential vault.
- Custom Library snippets/favourites are a bounded user layer. Imports are limited to 1 MiB and validated; export uses a temporary file, fsync and destination-state recheck before replacement. Snippet insertion edits text only and does not execute the snippet.
- Syntax checking never imports the target Python script. Optional Ruff/ShellCheck integration runs host tools as the current user.
- Administrator launch remains explicit, warns before elevation and delegates authentication to `sudo` in a terminal. Sheepy Pad does not read or store credentials and does not claim to supervise the elevated descendant.
- Sheepy Pad is an editor/launcher, not a sandbox. Running a script executes that script with the user's permissions (or root permissions after an explicit administrator launch).


## 0.1.0-r2 packaging hardening

- The AppImage builder performs no host package installation or privilege elevation and statically checks itself for such command lines.
- Supported-host and native-architecture checks prevent accidental cross-builds or unreviewed host combinations unless an explicit testing override is supplied.
- `appimagetool` downloads require HTTPS, are size/ELF checked, can be SHA-256 pinned, and formal release mode requires that pin.
- AppDir and final AppImage smoke tests run under isolated HOME/XDG directories and offscreen Qt settings rather than the user's live profile.
- Bundle inspection rejects Qt PDF, Qt PrintSupport and Qt WebEngine because Sheepy Pad does not require them.


## 0.1.0-r3 Suite-aligned packaging controls

- A canonical in-tree identity manifest is validated before dependency installation, preventing a mismatched name/version/publisher/desktop-ID build from proceeding.
- `SOURCE_MANIFEST.sha256` is a required build input and its digest, along with the builder and project-manifest digests, is recorded in build provenance.
- Source cache cleanup is guaranteed by the EXIT trap as well as explicit pre/post-QA stages.
- The isolated build Python compiles the complete source with bytecode redirected into the disposable build tree before PyInstaller is invoked.
- AppDir and final AppImage tests now initialize the real Sheepy Pad GUI offscreen under an isolated HOME/XDG profile rather than relying on `--version` alone; version and dark/light/system checks are retained.
- Curl-based appimagetool downloads additionally enforce a 300-second total transfer timeout.


## 0.2.0-r1 packaging minimization

The PyInstaller/AppImage pipeline now excludes and defensively removes Qt PDF, Qt PrintSupport and Qt WebEngine payloads that Sheepy Pad does not use. The negative bundle assertions remain in place after removal, and the full GUI/theme smoke matrix verifies that minimization did not remove required runtime components.
