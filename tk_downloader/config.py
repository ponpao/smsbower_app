"""Application paths and user settings (atomically persisted)."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, asdict, field, fields
from pathlib import Path

from .models import NamingMode, Quality
from .utils import atomic_write_text, ensure_dir

APP_NAME = "TK Downloader"
APP_SLUG = "tk_downloader"

# Name of the yt-dlp download archive. Kept next to the state database (not in the
# download folder) so it survives users cleaning out their videos directory.
ARCHIVE_FILENAME = "download_archive.txt"
STATE_FILENAME = "queue_state.db"
SETTINGS_FILENAME = "settings.json"


def app_data_dir() -> Path:
    """Per-user directory holding settings, the queue database and the archive."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return ensure_dir(Path(base) / APP_SLUG)


def default_download_dir() -> Path:
    downloads = Path.home() / "Downloads"
    base = downloads if downloads.exists() else Path.home()
    return base / "TK Downloader"


def settings_path() -> Path:
    return app_data_dir() / SETTINGS_FILENAME


def state_path() -> Path:
    return app_data_dir() / STATE_FILENAME


def archive_path() -> Path:
    return app_data_dir() / ARCHIVE_FILENAME


@dataclass
class Settings:
    """Everything the user can configure, persisted to ``settings.json``."""

    language: str = "en"                       # "en" | "kh"
    theme_mode: str = "dark"                   # "dark" | "light"
    download_dir: str = field(default_factory=lambda: str(default_download_dir()))
    naming_mode: str = NamingMode.ID_ONLY.value
    quality: str = Quality.BEST.value
    concurrency: int = 3
    use_cpu: bool = True
    use_gpu: bool = False
    shutdown_when_done: bool = False
    cookies_browser: str = ""                  # "", "chrome", "firefox", ...
    cookies_file: str = ""                     # optional cookies.txt path
    write_sidecar_always: bool = False         # write the .txt for every naming mode
    disclaimer_accepted: bool = False
    group_by_profile: bool = False
    rate_limit_kib: int = 0                    # 0 = unlimited
    retries: int = 5
    save_by_profile_folder: bool = True        # <download_dir>/<profile>/<file> instead of flat
    fetch_limit: int = 0                       # max videos pulled per pasted profile link, 0 = all
    ffmpeg_path: str = ""                      # explicit ffmpeg.exe/binary, overrides PATH search

    # -- persistence ---------------------------------------------------------------
    @classmethod
    def load(cls) -> "Settings":
        path = settings_path()
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # A corrupted settings file must never stop the app from launching.
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})

    def save(self) -> None:
        atomic_write_text(settings_path(), json.dumps(asdict(self), indent=2, ensure_ascii=False))

    # -- typed accessors -----------------------------------------------------------
    @property
    def naming(self) -> NamingMode:
        try:
            return NamingMode(self.naming_mode)
        except ValueError:
            return NamingMode.ID_ONLY

    @property
    def quality_enum(self) -> Quality:
        try:
            return Quality(self.quality)
        except ValueError:
            return Quality.BEST
