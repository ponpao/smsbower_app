# TK Downloader

A modern desktop downloader for video profiles and single links, built entirely in
Python with [Flet](https://flet.dev) and [yt-dlp](https://github.com/yt-dlp/yt-dlp).

Paste a mix of profile URLs and individual video URLs, pick a naming style, and let
it work through the queue — with a live CPU/RAM readout, a large countdown timer,
and a resume system that survives a power cut.

The whole interface is available in **English** and **ខ្មែរ (Khmer)**, in light and
dark mode.

---

## Highlights

| | |
|---|---|
| **`ID.mp4` + `ID.txt`** | The default naming style saves `7192843091823.mp4` next to `7192843091823.txt`, where the `.txt` holds the original title and full metadata. |
| **Smart Resume** | A yt-dlp download archive *and* a SQLite queue database, both written atomically. Close the app, lose power, lose Wi-Fi — reopen and continue. |
| **Live CPU & RAM** | `CPU  28%  \|  RAM  5.4 / 16.0 GB (34%)` in the bottom bar, sampled off the UI thread so it never stutters. |
| **Multi-profile paste** | Many profiles and loose links at once; every video is tagged with the profile it came from, and the table can group or filter by it. |
| **Facebook & Instagram** | One-click cookie import from an installed browser. |
| **Big ETA timer** | Whole-batch countdown, total speed, elapsed time and per-item progress. |
| **Concurrency + quality** | 1–8 parallel downloads; Best / 1080p / 720p / 480p / 360p / audio-only. |
| **CPU / GPU acceleration** | Checkboxes that map to real FFmpeg flags. |
| **Shutdown when done** | Optional, always behind a cancelable 60-second warning. |

---

## Install

Requires **Python 3.11 or newer**.

```bash
git clone <this-repo>
cd smsbower_app

python -m venv .venv
# Windows:  .venv\Scripts\activate
source .venv/bin/activate

pip install -r requirements.txt
```

### FFmpeg (strongly recommended)

FFmpeg is what merges separate video+audio streams (needed for 1080p and above) and
what converts audio-only downloads to mp3. Without it the app still runs, but it
falls back to single-file formats and shows a warning in the Performance section.

* **Windows** — `winget install Gyan.FFmpeg` (or download from ffmpeg.org and add it to `PATH`)
* **macOS** — `brew install ffmpeg`
* **Debian/Ubuntu** — `sudo apt install ffmpeg`

## Run

```bash
python main.py
```

The first launch shows a short legal notice; it is recorded once and not shown again.

---

## The `ID.mp4` + `ID.txt` naming style

This is the default and the style the app is built around.

```
📁 TK Downloader/
   ├── 7192843091823.mp4     ← the video, named with nothing but its platform ID
   ├── 7192843091823.txt     ← same stem: title + metadata
   ├── 7192843091824.mp4
   └── 7192843091824.txt
```

Internally the yt-dlp output template is literally `%(id)s.%(ext)s`. mp4/m4a streams
are preferred, `merge_output_format` is `mp4`, and a remux pass guarantees the
extension really is `.mp4` when FFmpeg is available.

The sidecar starts with the original title on line 1, so it stays greppable:

```
ដំណើរកម្សាន្តនៅសៀមរាប / Trip to Siem Reap

========================================================================
TK Downloader - video metadata
========================================================================
Title           : ដំណើរកម្សាន្តនៅសៀមរាប / Trip to Siem Reap
Video ID        : 7192843091823
Profile         : @example_user
Uploader        : example_user
Source URL      : https://www.tiktok.com/@example_user/video/7192843091823
Upload date     : 2025-01-31
Duration        : 00:03:07
Resolution      : 1080x1920
View count      : 120345
...
------------------------------------------------------------------------
Description
------------------------------------------------------------------------
...
```

The other two styles are `Title only` (`My holiday clip.mp4`) and `Num_Title`
(`007_My holiday clip.mp4`, numbered by queue position, not by finish order). Tick
**“Always write the .txt metadata file”** to get a sidecar in those modes too.

---

## Smart Resume

Two independent mechanisms, so one can fail without losing your work:

1. **yt-dlp download archive** — `download_archive.txt` gets one line per finished
   video. yt-dlp reads it before every download and refuses to fetch anything
   already listed. Delete the file (or press nothing — there is no UI button, by
   design) only if you want to re-download everything.
2. **SQLite queue database** — `queue_state.db` in WAL mode. Every status change is
   committed; progress is flushed every ~2 seconds while downloading. SQLite's
   commits are atomic, so an abrupt power loss leaves the last committed state, never
   a half-written row.

On top of both, partial transfers keep their `.part` file and resume from the byte
they stopped at instead of restarting.

When unfinished work from an earlier run is found on start-up, the app offers
**“Resume previous session”**. Choosing *Start fresh* clears the list but keeps the
files already on disk.

Both files live in the per-user app data folder:

| OS | Location |
|---|---|
| Windows | `%APPDATA%\tk_downloader\` |
| macOS | `~/Library/Application Support/tk_downloader/` |
| Linux | `~/.local/share/tk_downloader/` |

---

## Live CPU & RAM monitoring

`psutil.cpu_percent(interval=1.0)` blocks for a full second while it samples, so
calling it on the UI thread would freeze the window once per second. Instead:

* a daemon thread samples every 1.5 s and stores a `SystemSnapshot`;
* the UI's async tick (a few times a second) reads that snapshot and paints it.

Downloads follow the same rule: yt-dlp progress hooks on worker threads only mark a
row dirty, and the tick syncs the dirty rows. Nothing blocking ever touches a
control.

The bar turns amber above 70 % and red above 90 %, and also shows free disk space
on the download drive plus the number of videos in the archive.

---

## Facebook & Instagram

Both sites serve almost nothing to logged-out clients. In the **Cookies** section
pick the browser you are logged into and press *Import cookies from browser* — the
button verifies the import and reports how many cookies it read. yt-dlp then reuses
that browser's cookie store for every download.

If your browser keeps its cookie store locked (or you are on a machine without a
keyring), export a `cookies.txt` with a browser extension and set `cookies_file` in
`settings.json`; it takes precedence over the browser setting.

---

## CPU / GPU acceleration

| Checkboxes | FFmpeg flags |
|---|---|
| CPU | `-threads <core count>` on the output side |
| GPU | `-hwaccel auto` on the input side (NVDEC / QSV / VideoToolbox / VAAPI) |
| Both | both sets at once |
| Neither | FFmpeg defaults |

These matter for merging and for mp3 conversion; the network transfer itself is not
affected.

---

## Language & fonts

Switch between **English** and **ខ្មែរ** from the dropdown in the title bar — every
label updates in place, without losing your queue.

Translations live in plain JSON:

```
tk_downloader/locales/en.json
tk_downloader/locales/kh.json
```

To add a language, copy `en.json`, translate the values, and add the code to
`LANGUAGES` in `tk_downloader/i18n.py`.

Windows and macOS ship a Khmer font, so ខ្មែរ renders out of the box. If Khmer shows
as empty boxes (some minimal Linux installs), drop any Khmer-capable `.ttf` into
`tk_downloader/assets/fonts/` — the first font found there becomes the app-wide UI
font automatically. See `tk_downloader/assets/fonts/README.md`.

---

## Packaging a standalone app

**With Flet's own packager** (produces a native app bundle):

```bash
pip install flet[all]
flet pack main.py --name "TK Downloader" --add-data "tk_downloader/locales:tk_downloader/locales"
```

**With PyInstaller:**

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name "TK Downloader" \
    --add-data "tk_downloader/locales:tk_downloader/locales" \
    --add-data "tk_downloader/assets:tk_downloader/assets" \
    main.py
```

On Windows use `;` instead of `:` in `--add-data`. Ship `ffmpeg.exe` next to the
executable (or tell users to install it) so merging and mp3 conversion keep working.

---

## Project layout

```
main.py                        entry point + dependency check
requirements.txt
tk_downloader/
├── config.py                  app data paths, settings (atomic JSON)
├── models.py                  QueueItem, NamingMode, Quality, ItemStatus
├── state.py                   Smart Resume: SQLite queue + download archive
├── naming.py                  ID.mp4 / ID.txt logic and the metadata sidecar
├── downloader.py              yt-dlp options, URL expansion, worker pool
├── cookies.py                 browser cookie import (Facebook / Instagram)
├── monitor.py                 psutil CPU + RAM sampler (own thread)
├── system_actions.py          shutdown / open folder
├── i18n.py                    translator with live re-binding
├── utils.py                   formatting + filesystem helpers
├── locales/{en,kh}.json       every visible string
├── assets/fonts/              optional bundled UI font
└── ui/
    ├── app.py                 the application shell and all event handling
    ├── theme.py               high-contrast light/dark palettes
    └── widgets.py             queue table rows, cards, stat chips
tools/
├── selftest.py                headless checks (naming, resume, monitor, i18n)
└── check_locales.py           verifies both locales cover every key
```

## Development checks

```bash
python tools/selftest.py        # naming, Smart Resume, psutil, i18n, helpers
python tools/check_locales.py   # no missing translation keys
```

---

## Legal

TK Downloader is for **personal and educational use only**. Download only content
you own or have permission to save, respect each platform's Terms of Service and
your local copyright law, and do not redistribute downloaded material without the
owner's consent. You alone are responsible for how you use this software.
