# Sheepy Pad 0.4.2 — Porting Notes

Sheepy Pad is the renamed continuation of Pytshpad, which itself combined Python Lair 2's embedded code editor behaviour with the Nuxpad-style application framework.

The rebrand changes product identity, assets, package/resource names, desktop/AppStream metadata, configuration paths and release artifacts. It does not intentionally change the established editor feature set.

Python imports use the package name `sheepy_pad`; Linux executable and desktop resource names use `sheepy-pad`; the user-facing name is `Sheepy Pad`.

The source root is deliberately minimal for portability: only `main.py` and `sheepy_pad/` belong there.
