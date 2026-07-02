# 🎬 Video Visualizer — Tab 4 (next to AI Song)

Drop an **image** + an **audio file** (for example a song from the AI Song
tab), watch the **live preview**, style it, and export a modern
music-visualizer **MP4** — ready for YouTube, TikTok or Reels.

## Features

- 📱 **Compact modern UI** (450×840, like a phone app): live video preview
  on top, then tidy tab pages — 📁 Files / 🎨 Style / 🏷 Title / 💬 Subs /
  ✨ More — with a fixed ⚡ Create Video bar at the bottom

- 🖱️ **Drag & drop** zones for image and audio (click-to-browse also works)
- ▶️ **Live preview player** right in the app — play/pause, seek bar, with
  sound (pygame); every setting updates the preview instantly
- 🎨 **12 visualizer styles**: Neon Bars, Mirror Bars, Butterfly Bars,
  LED Dots, Line Spectrum, Area Glow, Waveform, Dual Wave, Circular
  Spectrum, Circular Wave, Pulse Rings, **Custom**
- ⚙️ **Custom visualizer builder**: element (bars/dots/line), position,
  bar count, thickness, height, mirror, reflection, rounded caps
- 🏷️ **Title controls**: your own text, 7 preset positions **or drag it
  anywhere on the live preview**, size slider — full Khmer support
  (mixed ខ្មែរ + English OK)
- 🧲 **Move the visualizer anywhere**: Move X / Move Y / Scale sliders
  relocate and resize any style (30%–170%)
- 🔤 **9 bundled Khmer fonts** with pickers for title and captions:
  Noto Sans Khmer, Battambang, Moul, Koulen, Bokor, Dangrek, Suwannaphum,
  Preahvihear, Fasthand (all Google Fonts, SIL OFL license)
- 💬 **Auto Captions like CapCut** — 🎙 Generate converts the audio's
  speech/singing into timed text (speech-to-text); on first use the app
  offers to install its AI engine (faster-whisper) automatically. Pick the
  language (ខ្មែរ, English, …), tick *Show subtitles*, choose a caption
  style (Box / Bold Outline / Neon Glow), caption **size** and **vertical
  position** sliders, fix words/timing in the built-in SRT editor, or
  import/export `.srt`
- 📐 **CapCut-style ratios**: Original (match your image), 16:9, 9:16,
  1:1, 4:3, 3:4, 2:1, 1.85:1, 2.35:1, 5.8-inch, 720p — plus Custom…
  (type any width × height)
- ✨ **Pro extras**: beat-zoom background, on-video progress bar,
  fade in/out (video + audio), logo/watermark with corner placement
- 🌈 7 color themes, blur + darken sliders
- ⚡ Threaded ffmpeg rendering with progress and cancel — UI never freezes
- 📦 No system ffmpeg needed — `imageio-ffmpeg` bundles the binary

## Install

```bash
pip install -r visualizer/requirements.txt
# optional, enables the 🎙 Generate-from-audio button:
pip install faster-whisper
```

## Run standalone (to try it)

```bash
python visualizer/visualizer_tab.py
```

## Integrate into the main app as Tab 4

```python
from visualizer.visualizer_tab import add_visualizer_tab, enable_dnd

app = ctk.CTk()
enable_dnd(app)                   # once, enables drag & drop on the window

self.tabview.add("Home")          # Tab 1
self.tabview.add("SMS")           # Tab 2
self.tabview.add("AI Song")       # Tab 3
add_visualizer_tab(self.tabview)  # Tab 4  🎬 Visualizer
```

For a plain `ttk.Notebook`:

```python
from visualizer.visualizer_tab import VisualizerFrame
frame = VisualizerFrame(notebook)
notebook.insert(3, frame, text="🎬 Visualizer")   # position 3 = Tab 4
```

> **Drag & drop:** `tkinterdnd2` must be initialised on the *main* window
> (`enable_dnd(app)`). Without it the drop cards fall back to
> click-to-browse.
>
> **Khmer text:** titles and subtitles use the bundled fonts in
> `visualizer/fonts/` (SIL OFL license) — no Windows font setup needed.
> Ship the `fonts/` folder together with the module.
>
> **Khmer looks scrambled (ជើង/ស្រៈ in wrong places)?** The app ships its
> own HarfBuzz text shaper (`uharfbuzz` + `freetype-py`, both in
> requirements.txt) so Khmer renders correctly on **any** Pillow build.
> If you see the red warning, install the two packages:
> `pip install uharfbuzz freetype-py`

## PyInstaller packaging

```bash
pyinstaller your_app.spec \
  --collect-binaries imageio_ffmpeg \
  --collect-data tkinterdnd2 \
  --add-data "visualizer/fonts;visualizer/fonts"
```
