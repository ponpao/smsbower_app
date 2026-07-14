# កម្មវិធីគ្រប់គ្រង Chrome Profile — Chrome Profile Manager v1.1.0

Desktop launcher that opens Google Chrome using isolated `--user-data-dir`
profiles (uses the system-installed Chrome; Chromium is not bundled).
Built with **PySide6** (LGPL — safe for closed-source commercial distribution,
unlike the GPL-licensed PyQt6 the v1.0.1 app used).

> This is a clean rebuild of v1.0.1 from the v1.1 dev brief — the original
> source only existed as a compiled .exe.

## Run

```
pip install -r requirements.txt
python main.py
```

## Build a Windows .exe

```
pip install pyinstaller
pyinstaller --noconsole --onefile --name ChromeProfileManager main.py
```

## Features

**Carried over from v1.0.1**

- Tabs: ទាំងអស់ (All) / សំណព្វចិត្ត (Favorites) / custom groups, with profile-count badges
- Table: running indicator (#), favorite star, name, Profile Key, Gmail, password
- Search by name / key / Gmail
- Per-profile context menu: launch, favorite, edit, set launch URL, export,
  create Gmail account, move to group, delete
- Bottom toolbar: Add Group, New Profile, Import/Export, Close All Chrome,
  Create Gmail checkbox, Exit — the ឧបត្ថម្ភ (sponsor) button was removed per the brief
- 7 languages: ភាសាខ្មែរ / English / Tiếng Việt / हिन्दी / 한국어 / 日本語 / 简体中文

**Modern UI (v1.1)**

- Light-green modern theme (pill tabs, rounded search bar, styled table)
- Menu-driven layout: **View** (refresh, new profile, add group, scan,
  import/export, close all, logs), **Session** (backups, restore, data
  folder), **Optimize** (cache cleaner with dry-run preview)
- Status bar: session uptime + live CPU/RAM usage, Create Gmail toggle
- **Scan & Import Chrome Profiles**: reads the system Chrome `User Data`
  folder (names + Gmail from Local State/Preferences) and imports existing
  profiles — they keep launching with your existing Chrome data via
  `--profile-directory`, nothing is copied
- **Optimize**: clears disposable cache folders (Cache, Code Cache, GPUCache,
  Service Worker cache…) per profile or for all; logins/bookmarks/history are
  kept; "Preview only (dry run)" shows what would be freed
- **Backup / Restore Profile Data**: zip the whole data folder and restore it
  later (with a safety backup first)
- Logs viewer (View → Logs, stored in `data/logs/app.log`)
- Notes column (searchable) on every profile

**New in v1.1**

- Group management (right-click a group tab): rename, edit color, delete —
  the delete dialog offers "delete group only" vs "delete group AND profiles",
  and Chrome data folders on disk are only removed after a separate explicit
  confirmation
- Drag-and-drop group tab reordering (persisted); All/Favorites stay pinned
- Group color picker in the create/edit group dialog
- Bulk actions: Ctrl+click multi-select → move selected to group / delete selected
- Group-level bulk actions: launch all in group (confirms above 5 windows),
  close all in group, export group list (CSV/JSON)
- Duplicate-launch prevention + live running indicator (green row, 2 s poll)
- Auto-backup of `profiles.json` on every change (`data/backups/`, last 20 kept)
- Keyboard shortcuts: `Ctrl+F` search, `Ctrl+N` new profile, `Del` delete, `F5` refresh

## Data layout

```
data/
  profiles.json          groups + profiles (schema_version 2; legacy v1 lists
                         are migrated automatically with a pre-migration backup)
  settings.json          language, chrome_path override, Create Gmail flag
  backups/               rotating auto-backups
  chrome_profiles/<key>/ Chrome --user-data-dir folders
```

If Chrome is installed somewhere unusual, set `"chrome_path"` in
`data/settings.json`.
