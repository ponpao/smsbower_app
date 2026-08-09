"""Smart Resume — persistent queue state.

TK Downloader survives power cuts, dropped connections and plain app closes with
a **dual** mechanism:

1. **yt-dlp download archive** (``download_archive.txt``) — one line per finished
   video id. yt-dlp itself consults this file and refuses to re-download anything
   already listed, so completed work is never repeated even if the database is
   deleted.
2. **This SQLite queue database** — every item (url, profile, status, progress,
   resulting file path) is written as it changes. SQLite in WAL mode commits
   atomically, so an abrupt power loss leaves the last committed state intact,
   never a half-written row.

On top of both, yt-dlp keeps ``.part`` files with ``continuedl`` enabled, so an
interrupted transfer resumes from the byte it stopped at rather than from zero.

On start-up :meth:`StateStore.pending_items` reports unfinished work from earlier
sessions, which is what powers the "Resume previous session?" prompt.
"""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Iterable

from .models import ItemStatus, QueueItem

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    uid              TEXT PRIMARY KEY,
    url              TEXT NOT NULL,
    profile          TEXT DEFAULT '',
    source_url       TEXT DEFAULT '',
    video_id         TEXT DEFAULT '',
    title            TEXT DEFAULT '',
    uploader         TEXT DEFAULT '',
    duration         REAL DEFAULT 0,
    status           TEXT DEFAULT 'queued',
    progress         REAL DEFAULT 0,
    speed            REAL DEFAULT 0,
    eta              REAL DEFAULT -1,
    total_bytes      INTEGER DEFAULT 0,
    downloaded_bytes INTEGER DEFAULT 0,
    filepath         TEXT DEFAULT '',
    error            TEXT DEFAULT '',
    position         INTEGER DEFAULT 0,
    profile_position INTEGER DEFAULT 0,
    session_id       TEXT DEFAULT '',
    added_at         REAL DEFAULT 0,
    updated_at       REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_items_status  ON items(status);
CREATE INDEX IF NOT EXISTS idx_items_profile ON items(profile);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

_COLUMNS = (
    "uid", "url", "profile", "source_url", "video_id", "title", "uploader",
    "duration", "status", "progress", "speed", "eta", "total_bytes",
    "downloaded_bytes", "filepath", "error", "position", "profile_position",
    "session_id", "added_at", "updated_at",
)


class StateStore:
    """Thread-safe SQLite persistence for the download queue."""

    def __init__(self, db_path: str | Path, archive_file: str | Path) -> None:
        self.db_path = Path(db_path)
        self.archive_file = Path(archive_file)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.archive_file.parent.mkdir(parents=True, exist_ok=True)
        self.archive_file.touch(exist_ok=True)

        # A single connection guarded by a lock: downloads run on worker threads
        # and all of them persist progress through this store.
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            # WAL + NORMAL keeps commits fast while still being crash safe.
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(_SCHEMA)
            self._migrate()
            self._conn.commit()

        self.session_id = uuid.uuid4().hex[:12]

    def _migrate(self) -> None:
        """Add columns introduced after a user's database already exists.

        ``CREATE TABLE IF NOT EXISTS`` only helps on a brand new file — an
        existing ``queue_state.db`` from an earlier release keeps its old
        column set, so new columns are added here with ``ALTER TABLE`` when
        missing. Existing rows get the column's default value.
        """
        existing = {row["name"] for row in self._conn.execute("PRAGMA table_info(items)")}
        if "profile_position" not in existing:
            self._conn.execute("ALTER TABLE items ADD COLUMN profile_position INTEGER DEFAULT 0")

    # -- lifecycle -------------------------------------------------------------------
    def close(self) -> None:
        with self._lock:
            try:
                self._conn.commit()
                self._conn.close()
            except sqlite3.Error:
                pass

    # -- items -----------------------------------------------------------------------
    def upsert(self, item: QueueItem) -> None:
        self.upsert_many([item])

    def upsert_many(self, items: Iterable[QueueItem]) -> None:
        rows = []
        for item in items:
            item.updated_at = time.time()
            data = item.to_row()
            rows.append(tuple(data[col] for col in _COLUMNS))
        if not rows:
            return
        placeholders = ",".join("?" for _ in _COLUMNS)
        assignments = ",".join(f"{col}=excluded.{col}" for col in _COLUMNS if col != "uid")
        sql = (
            f"INSERT INTO items ({','.join(_COLUMNS)}) VALUES ({placeholders}) "
            f"ON CONFLICT(uid) DO UPDATE SET {assignments}"
        )
        with self._lock:
            self._conn.executemany(sql, rows)
            self._conn.commit()

    def load_all(self) -> list[QueueItem]:
        with self._lock:
            cursor = self._conn.execute("SELECT * FROM items ORDER BY position, added_at")
            return [QueueItem.from_row(dict(row)) for row in cursor.fetchall()]

    def pending_items(self) -> list[QueueItem]:
        """Unfinished work left behind by a previous run (drives the resume prompt)."""
        pending = tuple(s.value for s in ItemStatus if s.is_pending)
        marks = ",".join("?" for _ in pending)
        with self._lock:
            cursor = self._conn.execute(
                f"SELECT * FROM items WHERE status IN ({marks}) ORDER BY position, added_at",
                pending,
            )
            return [QueueItem.from_row(dict(row)) for row in cursor.fetchall()]

    def counts_by_status(self) -> dict[str, int]:
        with self._lock:
            cursor = self._conn.execute("SELECT status, COUNT(*) AS n FROM items GROUP BY status")
            return {row["status"]: row["n"] for row in cursor.fetchall()}

    def max_position(self) -> int:
        with self._lock:
            cursor = self._conn.execute("SELECT COALESCE(MAX(position), 0) AS p FROM items")
            return int(cursor.fetchone()["p"])

    def delete(self, uids: Iterable[str]) -> None:
        uids = list(uids)
        if not uids:
            return
        with self._lock:
            self._conn.executemany("DELETE FROM items WHERE uid=?", [(u,) for u in uids])
            self._conn.commit()

    def clear_all(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM items")
            self._conn.commit()

    def clear_finished(self) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM items WHERE status IN (?,?)",
                (ItemStatus.COMPLETED.value, ItemStatus.SKIPPED.value),
            )
            self._conn.commit()

    # -- meta ------------------------------------------------------------------------
    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            self._conn.commit()

    def get_meta(self, key: str, default: str = "") -> str:
        with self._lock:
            cursor = self._conn.execute("SELECT value FROM meta WHERE key=?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    # -- yt-dlp download archive -------------------------------------------------------
    def archive_size(self) -> int:
        """Number of videos yt-dlp already recorded as downloaded."""
        try:
            with self.archive_file.open("r", encoding="utf-8", errors="ignore") as handle:
                return sum(1 for line in handle if line.strip())
        except OSError:
            return 0

    def reset_archive(self) -> None:
        """Forget every previously downloaded video (forces a full re-download)."""
        try:
            self.archive_file.write_text("", encoding="utf-8")
        except OSError:
            pass
