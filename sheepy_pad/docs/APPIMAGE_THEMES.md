# Sheepy Pad AppImage themes

Theme switching is intentionally an AppImage-only feature. Source and portable launches follow the host Qt theme.

Inside an AppImage, **View → Dark Mode** switches only the bundled Breeze-inspired application chrome. The editor palette is controlled separately by persistent **View → Dark Editor**, which defaults to checked and supplies matching dark/light Python, shell and Fish syntax colours.

Bundled styles are installed at:

```text
usr/share/sheepy-pad/styles/breeze-dark.qss
usr/share/sheepy-pad/styles/breeze-light.qss
```

One-launch overrides:

```bash
Sheepy-Pad-0.4.2-x86_64.AppImage --appimage-theme=dark
Sheepy-Pad-0.4.2-x86_64.AppImage --appimage-theme=light
Sheepy-Pad-0.4.2-x86_64.AppImage --appimage-theme=system
```

Environment override:

```bash
SHEEPY_PAD_APPIMAGE_THEME=light Sheepy-Pad-0.4.2-x86_64.AppImage
```

## Editor palette is independent

`View → Dark Editor` is a persistent editor-only preference and defaults to checked. It controls the editor canvas, gutter, selections, search highlighting and syntax colours in source, portable and AppImage builds. `View → Dark Mode` remains AppImage-only and controls application chrome; changing it does not override Dark Editor.
