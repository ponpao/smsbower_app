# TRAVKOD

**Honest humanize + master + batch-export for finished music (including AI renders).**

TRAVKOD takes finished stereo tracks — including AI-generated renders (e.g. from
Suno) — and makes them warmer, less brittle and release-ready, then batch-exports
them to WAV / FLAC / MP3. It is a **sound-quality** tool.

![console](docs/console.png)

---

## Honest-use note (read this first)

TRAVKOD improves audio quality. **If your track uses AI, disclose it** where your
distributor requires.

TRAVKOD deliberately does **not**:

- try to evade, defeat, or "fool" any AI-detection system;
- help falsely attest human authorship to a distributor;
- help bypass a distributor's or streaming platform's AI-disclosure checks.

The **Authenticity Report** is informational only: it returns a *calibrated
probability with a confidence range* and is clearly labelled **Beta —
experimental, may be wrong**. It never guarantees a result and never frames its
output as "how to pass a check." Where a release would require AI disclosure, the
app **prompts you to disclose** — it does not help you hide it.

All processing runs **locally** on your machine by default. Nothing is uploaded.

---

## Architecture

```
React UI ──IPC──> Job Orchestrator (Node/Electron) ──> Python DSP Worker Pool
   ▲                     │                                   │
   └──── progress ◄──────┴──────── per-file events ◄─────────┘
Files: import queue -> humanize + master -> export (WAV/FLAC/MP3)
```

- **Frontend** — React + TypeScript + Tailwind (dark theme), Vite.
- **Shell** — Electron (frameless window matching the reference UI).
- **Orchestrator** — Node manages the batch queue and a pool of Python worker
  processes (one child per "Thread", 1–8). Statuses: Idle / Queued / Processing /
  Done / Error / Paused.
- **DSP backend** — Python 3.11 workers speaking newline-delimited JSON over
  stdio; they stream per-file progress events for the queue.
- **Engine** — `python/travkod/humanize_master.py`: low-cut → humanize
  (wow/flutter + micro-dynamics) → saturation → parametric + 10-band EQ → de-ess →
  gate → compression → air → reverb/echo → stereo width → true-peak limiter →
  LUFS normalize. Every stage is driven by the UI sliders.

The engine runs on `numpy`/`scipy`/`soundfile`/`pyloudnorm` alone; `librosa`
(key/pitch), `lameenc`/`ffmpeg` (MP3) and `pedalboard` are optional accelerators.

---

## Features

- **Batch Queue** — `#, Filename, Duration, Type, Key/Major, Sample Rate/Bits,
  Loudness (LUFS), True Peak, Channels, Status`. Right-click: select all, add
  files/folder, remove, clear, analyze, start/stop export, open output.
- **Setting Console** — Template dropdown, Presets (save/load), Quick EQ, the full
  mastering strip and 10-band graphic EQ.
- **Humanize & Master** toggle — the main processing switch (Auto/Manual
  intensity). Its job is sound quality.
- **Export Settings** — Format (WAV/FLAC/MP3), sample rate, bit depth, threads
  (1–8), autotune, merge-to-one-file, LUFS target, output folder.
- **Release Readiness Check** — validates LUFS range, true-peak ≤ −1 dBTP, sample
  rate/bit depth, metadata; reminds you to disclose AI use where required.
- **Authenticity Report (Beta)** — calibrated `P(AI)` with a confidence interval
  and a plain-language "this is probabilistic" note.
- **Transport bar** — play/next, Effect toggle (A/B processed vs original),
  waveform scrubber, volume. Shortcuts: `Space` play/pause, `Cmd/Ctrl+E` export.

---

## Setup (development)

Requirements: **Node 18+**, **Python 3.11**.

```bash
# 1. Python DSP backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r python/requirements.txt      # or requirements-core.txt for the minimal engine

# 2. Frontend + shell
npm install

# 3. Run the app (Vite dev server + Electron)
npm run dev
```

### Verifying the engine without the GUI

```bash
python python/tests/test_engine.py           # acceptance checks (LUFS, true-peak, de-harsh)
node scripts/batch_smoke.mjs /path/to/folder /path/to/out 4   # batch worker-pool smoke test
```

---

## Building installers

```bash
npm run dist          # current platform
npm run dist:win      # Windows NSIS installer
npm run dist:mac      # macOS dmg
```

Packaging embeds the Python worker (`extraResources`). For a self-contained
installer, place a portable Python 3.11 runtime with the deps installed at
`python-embed/` before building (see `scripts/prepare_python.md`); otherwise the
app falls back to a system `python3`. **Code-signing** requires your own
certificates — see `scripts/signing.md`.

---

## Parameter reference

| Control | Unit | What it does |
| --- | --- | --- |
| Bass / Deep | dB | Low shelf (~80 Hz) / sub weight (~45 Hz) |
| Mid / Clear / Presence | dB | Mid bell (~800 Hz) / clarity (~3 kHz) / presence (~5 kHz) |
| Treble | dB | High shelf (~8 kHz) |
| Low-Cut | Hz | High-pass corner |
| Gate | % | Noise-floor downward expansion |
| De-Ess | % | Sibilance reduction (5–9 kHz) |
| Air | % | Very-high shelf shimmer (~14 kHz) |
| Comp | % | Bus compression amount |
| Limit | % | True-peak limiter drive (ceiling −1 dBTP) |
| Saturation | % | Analog-style harmonic warmth |
| Reverb / Echo | % | Subtle plate reverb / slap echo |
| Width | % | Stereo width (−100 narrow … +100 wide) |
| Gain | dB | Output trim (pre-limiter) |
| Humanize | % | Wow/flutter depth + micro-dynamic drift |
| EQ | dB | 10 bands: 30/80/150/250/500/1k/2k/4k/8k/12k Hz |

---

## License

MIT. See `LICENSE`.
