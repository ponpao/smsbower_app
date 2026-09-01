# TMIRROR

A light, modern desktop app for mirroring and managing the **Android phones you own**,
built on the official [`adb`](https://developer.android.com/tools/adb) (Android
platform-tools) and [`scrcpy`](https://github.com/Genymobile/scrcpy) projects.

TMIRROR is a lab / personal-device tool. It is not a RAT, not a pentest payload
toolkit, and does not connect to any device that hasn't been unlocked and
explicitly authorized by its owner on the device's own screen.

## Authorized devices only

Every feature in this app assumes the device is already visible to `adb` because
its owner unlocked it and tapped **Allow** on the USB debugging prompt. TMIRROR:

- **Never** generates or bundles an APK payload, reverse shell, or exploit.
- **Never** bypasses the Android USB-debugging consent dialog.
- **Never** connects to a device over the internet — the optional QR pairing
  server binds only to this PC's LAN address and refuses to run without one.
- **Never** allows Wi-Fi (ADB-over-TCP) access to a device until that same
  device was already authorized once over USB, on this PC.
- Ships with **no QR-to-payload flow**. The "Connect via QR" screen only opens
  a short-lived, single-use, same-Wi-Fi confirmation page — it cannot install
  anything and it cannot reach a stranger's phone.
- Treats iPhone as out of scope for v1. The Settings page shows a disabled
  card pointing to Apple's own **iPhone Mirroring** on macOS — TMIRROR does
  not attempt iOS jailbreak, sideloading, or remote control.

If a request would enable unauthorized access to a device, that feature does
not exist in this codebase, on purpose.

## Requirements

- Node.js 20+
- [Android platform-tools](https://developer.android.com/tools/releases/platform-tools)
  (`adb`) — official Google download, on your `PATH` or pointed to from Settings.
- [scrcpy](https://github.com/Genymobile/scrcpy) — official project, on your
  `PATH` or pointed to from Settings.
- An Android 9+ phone, owned by you, with **Developer options → USB debugging**
  enabled.

TMIRROR does not download, bundle, or patch either tool. It only shells out to
whatever official binaries you already have installed.

## Run in dev

```bash
npm install
npm run dev
```

This starts Vite for the renderer and launches the Electron window with hot reload.

## Type-check and build

```bash
npm run typecheck   # tsc --noEmit for both the main/preload and renderer projects
npm run build        # electron-vite build -> out/
```

## Package a distributable

```bash
npm run build:win    # Windows NSIS installer via electron-builder
npm run build:mac    # macOS dmg via electron-builder
```

> These commands were validated with `npm run typecheck` and `npm run build`
> in this environment. Packaging and on-device testing (`build:win`/`build:mac`,
> plugging in a real phone, scrcpy windows) need to be run on your own machine —
> this development environment has no attached Android hardware, no display
> server, and no Windows/macOS packaging target.

## Project layout

```
src/
  main/        Electron main process: adb + scrcpy child-process wrappers,
               tool detection, settings store, the local LAN pairing server,
               and all IPC handlers.
  preload/     contextBridge API exposed to the renderer as window.tmirror.
  renderer/    React + TypeScript + Tailwind UI (Devices, Connect, Files,
               Clipboard, Settings pages), Khmer/English i18n, flag switcher.
  shared/      Types and IPC channel names shared between processes.
```

## Feature checklist

- [x] **Device list** — polls `adb devices`, shows serial / model / Android
      version / battery / USB vs Wi-Fi, with Ready / Unauthorized / Offline
      status and the "Unlock your phone and tap Allow USB debugging" hint.
- [x] **Mirror windows** — one real `scrcpy` process per selected device,
      window title set to the device name, multiple devices at once.
- [x] **Arrange** — Arrange grid, Arrange side-by-side, Close all mirrors
      (computed from your primary display's work area).
- [x] **Drag and drop** — drop an `.apk` on a device card to `adb install -r`
      it; drop a photo/video/document to `adb push` it to `/sdcard/Download`.
      Every transfer reports progress and a success/fail toast. Nothing is
      ever auto-installed from the internet.
- [x] **Clipboard** — scrcpy syncs the device clipboard to the PC clipboard
      automatically while a mirror window is open; the Clipboard page reads
      that PC clipboard on demand and can type text into the field currently
      focused on the device (`adb shell input text`) — no keylogger, no
      background capture.
- [x] **QR Connect (pairing only)** — the desktop generates a random,
      5-minute, single-use token and a local HTTP server bound to this PC's
      LAN IP; the QR encodes `http://<lan-ip>:<port>/pair?token=...`. Opening
      it and tapping Confirm only tells the desktop "the owner said yes" —
      the actual device link still goes through already-authorized adb/scrcpy.
      Android 9 has no official QR wireless-debugging pairing, so the Connect
      page always shows the USB-first instructions and the Android 9 notice.
- [x] **Files panel** — This PC pane (drag-drop or Browse…) next to a Phone
      pane with tabs for `/sdcard/Download` and `/sdcard/Pictures`, with
      Pull/Push per file.
- [x] **Extras** — Screenshot (`adb shell screencap` + pull), Screen record
      (`scrcpy --record`), Uninstall by package name.
- [x] **Setup** — Settings page detects `adb`/`scrcpy` on `PATH` or lets you
      point at their folder, and shows found/not-found + version per tool.
- [x] **i18n** — Khmer (Kantumruy Pro) and English (Inter), default follows
      OS locale, persisted to `localStorage["tmirror.lang"]`, switched only
      by the Cambodia/US flag buttons (real SVG flags, `aria-label`
      `"ខ្មែរ"` / `"English"`, accent ring on the selected flag).

## Security notes

- The pairing HTTP server binds to this machine's LAN interface address
  (never `0.0.0.0`), serves exactly two routes (`GET /pair`, `POST
  /pair/confirm`), and self-destructs its token after 5 minutes or first use.
- There is no ngrok/Cloudflare tunnel, no public-internet relay, and no code
  path that exposes ADB outside this LAN.
- Logs only ever contain local device serials — no phone numbers, contacts,
  or private app data are read.
- "Send text to phone" is a literal `adb shell input text` keystroke
  simulation, not a hidden clipboard/keylogger channel — it only affects
  whatever field is already focused on the device's own screen.
