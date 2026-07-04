# Building TRAVKOD with PyInstaller

Produces a self-contained app (Python + PyQt6 + DSP stack bundled) — the target
machine needs no Python install.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r python/requirements.txt pyinstaller
pyinstaller travkod.spec          # -> dist/TRAVKOD/
```

## Per-platform notes
- **Windows** — run on Windows to get a `.exe`. Wrap `dist/TRAVKOD` with Inno
  Setup or NSIS for an installer. Put an icon at `resources/icon.ico`.
- **macOS** — add `BUNDLE(...)` to the spec (or `--windowed`) for a `.app`, then
  `hdiutil` / `create-dmg` for a `.dmg`. Sign + notarize (see `signing.md`).
- **Linux** — `dist/TRAVKOD/TRAVKOD` runs directly; package as AppImage/Flatpak
  if desired. Ensure Qt libs (`libegl1 libgl1 libxkbcommon0`) are present.

## MP3 export in the bundle
Install `lameenc` (already in requirements) so MP3 works without a system
ffmpeg. Otherwise the app tells the user to pick WAV/FLAC or install ffmpeg.
