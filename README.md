# TK Story Studio

A static web app for turning a raw story into a cinematic article, a viral title, a
Facebook caption, and ready-to-paste AI image/video prompts.

> This repository also hosts `version.json`, the update manifest for the TRAVKOD desktop
> app. That file is unrelated to the web app and is left untouched.

## Running it

No build step, no dependencies.

- **Locally:** open `index.html` directly, or serve the folder
  (`python3 -m http.server 8000`) and visit `http://localhost:8000`.
- **Hosting:** any static host. On GitHub Pages, point Pages at the repository root.

Serving over HTTP(S) additionally enables the service worker (offline app shell) and
the Clipboard API; from `file://` the app still works, with a copy fallback.

## Setup

Open **Settings → Anthropic connection** and paste an API key, then press
*Test connection*. The key is kept in this browser's `localStorage` and is sent only to
`api.anthropic.com`.

⚠️ A key embedded in client-side code is visible in the browser's network tab. This is
fine for a personal or internal tool; do **not** deploy it on a public site.

## Workflow

1. **Studio** — paste the raw story and generate. Output streams in live; every sentence
   you wrote is preserved, the model only expands around it. Title, caption, and article
   fill in as they arrive.
2. **Visuals** — trim the article to a target length (cut at a sentence end, a word
   boundary, or an exact character count), pick one of 11 styles, then copy or download
   the generated prompt. Each style has a static-image and an animate+music variant, in
   1:1 / 4:5 / 9:16 / 16:9.
3. **Library** — the last 25 generations, restorable with one click.

## Features

- **Streaming generation** with a stop button, elapsed time, and output-token count.
- **Khmer/English UI**, switchable at any time; Khmer-aware word counts via
  `Intl.Segmenter` where available.
- **Light / dark / system** theming.
- **Autosave** of drafts, trim settings, and generation parameters.
- **Keyboard**: `Ctrl`/`⌘` + `Enter` to generate or stop, `Esc` to close the drawer or
  abort a run.
- **Accessibility**: skip link, focus-trapped drawer, live status regions, and
  `prefers-reduced-motion` support.
- **PWA**: installable, with the app shell cached for offline use. API calls are never
  cached.

## Models

| Model | Notes |
| --- | --- |
| `claude-opus-5` (default) | Highest quality; adaptive thinking at `medium` effort, 32K max output |
| `claude-sonnet-5` | Balanced quality, speed, and cost; same thinking/effort settings |
| `claude-haiku-4-5` | Fastest and cheapest; sent without `thinking`/`effort`, which it does not accept |

Per-model request options live in `MODELS` in `assets/js/prompts.js`.

## Layout

```
index.html               app shell and views
manifest.webmanifest     PWA manifest
sw.js                    offline app-shell cache
assets/css/app.css       design tokens, layout, components
assets/js/prompts.js     style presets, prompt templates, km/en dictionary, model specs
assets/js/app.js         state, streaming API client, trimming, history, UI wiring
version.json             TRAVKOD desktop-app update manifest (unrelated)
```

All data — drafts, history, settings, API key — stays in the browser. **Settings → Data →
Clear all local data** removes it.
