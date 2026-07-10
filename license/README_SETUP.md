# 🔑 TRAVKOD CODEs — License System (Setup Guide)

A complete licensing system for the **Video Visualizer**. The app **opens
normally but its functions stay LOCKED** (a 🔒 overlay + a **🔑 Activate**
button in the header) until a valid code is entered. You (admin) generate
codes in a Google Sheet (or the Keyadmin phone app); each code locks to the
**first PC** that activates it, runs for the days you choose
(1 / 7 / 30 / 365 / custom), carries an **Owner name** that is shown in the
app, and you can **revoke** it any time. Expiry is **strict** — a 30-day
code ending **10 July 2026** stops on **11 July 2026**, no extra day.

Sheet columns: `License_Key · Duration · Device_UID · Phone_Model · Status ·
Activation_Date · Expiry_Date · Owner`.

```
User's PC ──activate(code, PC-ID)──▶ Google Apps Script Web App ──▶ Google Sheet
   ▲                                        │  (bind PC, set expiry, sign)
   └────────── signed OK / expiry ──────────┘
Admin ──generate / revoke──▶ same Web App  (Sheet sidebar button OR Keyadmin APK)
```

## Part A — Google Sheet + Apps Script (the server)

1. Create a new **Google Sheet**.
2. **Extensions ▸ Apps Script**. Delete the sample, paste
   **`apps_script/Code.gs`**. Add a file **`Sidebar.html`** (＋ ▸ HTML) and
   paste **`apps_script/Sidebar.html`**.
3. At the top of `Code.gs` set:
   - `LICENSE_SECRET` — a long random string. **Must exactly equal**
     `TRAVKOD_LICENSE_SECRET` in `license_client.py`.
   - `ADMIN_KEY` — a private password (used by the Keyadmin app).
4. Run **`setupSheet`** once (▶ Run; approve permissions). It creates the
   `Licenses` header row.
5. **Deploy ▸ New deployment ▸ Web app**
   - *Execute as*: **Me**
   - *Who has access*: **Anyone**
   - Deploy, copy the **`/exec` URL**.
6. Reload the Sheet — a **🔑 TRAVKOD License** menu appears. Use
   *Generate / Manage Codes* to open the sidebar with a **Generate Code**
   button and the live list.

> Re-deploy note: after editing `Code.gs`, do **Deploy ▸ Manage deployments
> ▸ Edit ▸ Version: New** so the `/exec` URL serves the new code.

## Part B — Wire the Visualizer (the client)

In `visualizer/../license/license_client.py` set (or use env vars):
- `WEB_APP_URL` = the `/exec` URL from step A5.
- `LICENSE_SECRET` = the same secret as the Apps Script.

That's it — `run_standalone()` already calls the gate. On launch the app
shows the **License Activation** window (with the PC ID to send you and a
code box) until a valid code is entered. After that it validates silently
each launch. During development you can bypass the gate with the env var
`TRAVKOD_LICENSE_OPTIONAL=1`.

**Packaging:** ship a compiled build so the secret isn't in plain `.py`:
```
pyinstaller your_app.spec --add-data "license;license" \
    --add-data "visualizer/fonts;visualizer/fonts" \
    --collect-binaries imageio_ffmpeg
```

## Part C — Keyadmin Flutter APK (admin on your phone)

Source in `keyadmin/`. It talks to the **same** Web App URL with the
`ADMIN_KEY`.

```bash
cd keyadmin
flutter create .            # generate android/ ios/ scaffolding (once)
flutter pub get
flutter build apk --release # Universal APK
# -> build/app/outputs/flutter-apk/app-release.apk
```
First launch asks for the **Web App URL** and **Admin Key**. Then you can
Generate (with day presets or custom), see all licenses live, Copy a code,
**Revoke / Un-revoke**, or **Reset PC lock** (to move a code to a new PC).

> App icon: `assets/logo.png` is included. To set it as the launcher icon,
> add `flutter_launcher_icons` and run it, or drop the PNG into the Android
> `mipmap` folders.

## How the strict expiry works (important)

- The server stamps `ExpiryAt = ActivatedAt + PlanDays` (a date).
- The client allows use only while **today ≤ ExpiryAt**. The day *after*
  ExpiryAt it refuses — verified by tests. No grace day.
- The clock can't be rolled back: the client records the last date it saw
  (server date when online) and blocks if the PC clock jumps backward.
- Offline still works until the exact expiry (thanks to the signed cache),
  but a **Revoke** takes effect the next time the PC is online.

## Files

| File | What |
|------|------|
| `license/license_client.py` | Core check/activate logic (no UI) |
| `license/license_gate.py` | Activation window shown before the app |
| `license/apps_script/Code.gs` | Web App server (validate/generate/revoke) |
| `license/apps_script/Sidebar.html` | Generate-code button inside the Sheet |
| `license/SHEET_TEMPLATE.md` | Column layout of the `Licenses` sheet |
| `keyadmin/` | Flutter admin app (Universal APK) |
| `assets/logo.svg` / `.png` | App logo |
