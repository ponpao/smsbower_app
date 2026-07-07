# Grok Studio

Compact Windows desktop client for the xAI (Grok) API — Chat, Image, Video
and Voice (TTS) in a single 420×720 frameless window. Built with PyQt6.

![icon](assets/icons/grok_studio.png)

## Features

- **Chat** — `grok-4.3`, streaming responses, editable system prompt,
  per-message copy.
- **Image** — `grok-imagine-image` / `grok-imagine-image-quality`, live price
  estimate, 14 aspect ratios, 1K/2K, batches of 1–4, hover-zoom grid,
  Save / Copy / *Send to Video*.
- **Video** — `grok-imagine-video`, up to 7 drag-and-drop reference images,
  video-only aspect-ratio list, 480p/720p, 1–15 s duration slider with live
  cost estimate (`duration/60 × $4.20`), 5 s background polling with progress
  + cancel, inline preview player and download.
- **Voice** — TTS to MP3 with play/pause/scrub and Save As.
- **Bilingual UI** — English / ខ្មែរ (Khmer, default), switchable in Settings.
- **Secure key storage** — the API key lives only in Windows Credential
  Manager (via `keyring`); it is validated with a minimal `grok-4.3` call
  before saving and is never written to files or logs (log redaction filter
  included). Until a key is stored, the app locks you into Settings.
- Non-blocking error toasts, automatic single retry with countdown on 429,
  rotating log file in `%LOCALAPPDATA%\GrokStudio\logs`.

## Run from source

```bash
pip install -r requirements.txt
python scripts/fetch_font.py     # optional: bundle Kantumruy Pro
python main.py
```

## Build the .exe

```bat
build.bat
```

produces `dist\GrokStudio.exe` (PyInstaller, onefile + windowed, assets and
font bundled via `--add-data`).

## Architecture

| Module | Role |
|---|---|
| `grok_studio/api_client.py` | `APIClient` — every xAI endpoint (chat/completions with SSE streaming, images/generations, videos/generations + `/videos/{id}` polling, tts), 429 auto-retry, moderation detection |
| `grok_studio/workers.py` | `QThread` workers — no `requests` call ever runs on the GUI thread; signals: `progress/status`, `success(data)`, `error(message)` |
| `grok_studio/settings_manager.py` | `SettingsManager` — persisted prefs (QSettings) + keyring-only API key |
| `grok_studio/constants.py` | models, prices and the **separate** image vs video aspect-ratio lists |
| `grok_studio/i18n.py` | EN/KH string tables |
| `grok_studio/ui/` | frameless main window, title bar, sidebar, toast and the five tabs |

> **Note:** the image endpoint accepts 14 aspect ratios, the video endpoint
> only 7. The two lists are deliberately separate constants
> (`IMAGE_ASPECT_RATIOS` vs `VIDEO_ASPECT_RATIOS`) — do not merge them.
