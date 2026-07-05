# Magic Studio — Local Audio Toolkit

A PyQt6 desktop app with a dark, tabbed UI for working with **your own** audio
files, entirely **on your machine**:

- **Local Master** — light EQ + loudness normalization on a queue of files.
- **Batch Master** — pick an EQ profile and output format, process the queue.
- **Audio Analysis** — real technical stats (duration, LUFS, true peak, RMS,
  sample rate).
- **Metadata** — batch-write accurate tags + cover art via `mutagen`.
- **Settings** — the tag/cover defaults used by the Metadata tab.

## What this app deliberately does *not* do

This was built from a spec whose original "cloud" features were abuse-oriented,
and those were intentionally left out:

- **No session/cookie automation.** There is no cookie field, no
  "auto-detect cookies", and no code that uploads your tracks to DistroKid,
  TuneCore, or any other account/service by impersonating a browser session.
- **No AI-detection evasion.** There is no "anti-detector shift" and no
  "bypass" toggle. The analysis tab reports honest measurements; it makes no
  claim about a track's origin and does nothing to hide one.
- **No provenance spoofing.** The tag editor writes exactly what you type. It
  does not forge a DAW/"software encoder" or strip origin metadata to disguise
  a file.

Everything runs locally on files you own.

## Install & run

```bash
pip install -r requirements.txt
python main.py
```

Optional dependencies degrade gracefully: without `psutil` the CPU/RAM readout
is disabled; without `numpy`/`soundfile`/`pyloudnorm` the mastering/analysis
tabs show a clear "install these" message instead of crashing.

## Layout

```
magic_studio_app/
├── main.py                    # entry point
├── controller.py              # QMainWindow, signal wiring, worker lifecycle
├── workers.py                 # QThread workers (mastering / analysis / tagging)
├── requirements.txt
├── views/
│   ├── main_window_ui.py      # frameless shell, title bar, 5 tab panels
│   └── styles.qss             # dark theme
└── modules/
    ├── local_mastering.py     # on-device EQ + loudness normalization
    ├── audio_analysis.py      # loudness / peak / RMS measurements
    └── tag_editor.py          # mutagen tag + cover writing
```

All heavy work runs in `QThread` workers, so the UI never freezes.
