# 🎬 Video Visualizer — Tab 4 (next to AI Song)

Drop an **image** + an **audio file** (for example a song exported from the
AI Song tab) and render a modern music-visualizer **MP4 video** — ready for
YouTube, TikTok or Reels.

![styles](https://img.shields.io/badge/styles-Neon%20Bars%20%7C%20Circular%20Spectrum%20%7C%20Waveform-8b5cf6)

## Features

- 🖱️ **Drag & drop** zones for image and audio (click-to-browse also works)
- 🎨 3 visualizer styles: **Neon Bars**, **Circular Spectrum** (pulsing round
  album art), **Waveform**
- 🌈 5 color themes, background **blur** + **darken** sliders
- 📐 Resolutions: YouTube 1080p, HD 720p, Square, TikTok/Reels vertical
- 🏷️ Optional song-title overlay
- ⚡ Threaded rendering with live progress bar and cancel
- 📦 No system ffmpeg needed — `imageio-ffmpeg` bundles the binary

## Install

```bash
pip install -r visualizer/requirements.txt
```

## Run standalone (to try it)

```bash
python visualizer/visualizer_tab.py
```

## Integrate into the main app as Tab 4

The tab is one function call. Add it **right after the AI Song tab** so it
appears next to it as Tab 4:

```python
from visualizer.visualizer_tab import add_visualizer_tab, enable_dnd

# 1) (optional, for drag & drop) enable DnD on the main window once,
#    right after creating it:
app = ctk.CTk()
enable_dnd(app)

# 2) add the tab in order — after the AI Song tab:
self.tabview.add("Home")          # Tab 1
self.tabview.add("SMS")           # Tab 2
self.tabview.add("AI Song")       # Tab 3
visual_tab = add_visualizer_tab(self.tabview)   # Tab 4  🎬 Visualizer
```

If the app uses a plain `ttk.Notebook` instead of `CTkTabview`:

```python
from visualizer.visualizer_tab import VisualizerFrame
frame = VisualizerFrame(notebook)
notebook.insert(3, frame, text="🎬 Visualizer")   # position 3 = Tab 4
```

> **Note on drag & drop:** `tkinterdnd2` must be initialised on the *main*
> window (`enable_dnd(app)`). If it isn't installed or can't load, the drop
> cards automatically fall back to click-to-browse — everything else works
> the same.

## PyInstaller packaging

Add these to the build so the bundled ffmpeg and DnD library ship with the exe:

```bash
pyinstaller your_app.spec --collect-binaries imageio_ffmpeg --collect-data tkinterdnd2
```
