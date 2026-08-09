#!/usr/bin/env python3
"""Headless self-test for the non-UI parts of TK Downloader.

Covers the three things that matter most:

1. ``ID.mp4`` + ``ID.txt`` naming and the sidecar contents,
2. Smart Resume persistence (SQLite round-trip + pending detection),
3. the psutil monitor producing sane, non-blocking samples.

Run with::

    python tools/selftest.py
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
import time as _time

from tk_downloader.config import Settings                     # noqa: E402
from tk_downloader.downloader import (                         # noqa: E402
    DownloadManager, ffmpeg_acceleration_args, format_selector,
)
from tk_downloader.i18n import LANGUAGES, Translator           # noqa: E402
from tk_downloader.models import ItemStatus, NamingMode, QueueItem, Quality  # noqa: E402
from tk_downloader.monitor import SystemMonitor                # noqa: E402
from tk_downloader.naming import (                             # noqa: E402
    naming_example, output_template, profile_subdir, sidecar_path_for, write_sidecar,
)
from tk_downloader.state import StateStore                     # noqa: E402
from tk_downloader.utils import format_clock, human_bytes, parse_links  # noqa: E402

FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f"  ({detail})" if detail else ""))
    if not condition:
        FAILURES.append(label)


# ---------------------------------------------------------------------------------------
def test_naming() -> None:
    print("\n== Naming: ID.mp4 + ID.txt ==")
    check("ID template is exactly %(id)s.%(ext)s",
          output_template(NamingMode.ID_ONLY) == "%(id)s.%(ext)s")
    check("Title template", output_template(NamingMode.TITLE_ONLY) == "%(title)s.%(ext)s")
    check("Num_Title template uses the queue position",
          output_template(NamingMode.NUM_TITLE, 7) == "007_%(title)s.%(ext)s")

    video, text = naming_example(NamingMode.ID_ONLY)
    check("Example pair shares one stem", Path(video).stem == Path(text).stem, f"{video} / {text}")
    check("Example video is .mp4", video.endswith(".mp4"))
    check("Example sidecar is .txt", text.endswith(".txt"))

    with tempfile.TemporaryDirectory() as tmp:
        video_path = Path(tmp) / "7192843091823.mp4"
        video_path.write_bytes(b"fake mp4 payload")
        info = {
            "id": "7192843091823",
            "title": "ដំណើរកម្សាន្តនៅសៀមរាប / Trip to Siem Reap",
            "uploader": "example_user",
            "uploader_url": "https://www.tiktok.com/@example_user",
            "webpage_url": "https://www.tiktok.com/@example_user/video/7192843091823",
            "upload_date": "20250131",
            "duration": 187,
            "width": 1080, "height": 1920,
            "view_count": 120345,
            "like_count": 4210,
            "description": "Line one\nLine two",
            "extractor_key": "TikTok",
        }
        item = QueueItem(url=info["webpage_url"], profile="@example_user")
        written = write_sidecar(video_path, info, item)

        check("Sidecar path == video stem + .txt",
              written == sidecar_path_for(video_path) == video_path.with_suffix(".txt"),
              str(written.name))
        check("Sidecar exists on disk", written.exists())
        body = written.read_text(encoding="utf-8")
        check("First line is the original title", body.splitlines()[0] == info["title"])
        check("Sidecar carries the video id", "7192843091823" in body)
        check("Sidecar carries the profile", "@example_user" in body)
        check("Sidecar carries the description", "Line two" in body)
        siblings = sorted(p.name for p in Path(tmp).iterdir())
        check("Folder holds exactly ID.mp4 + ID.txt",
              siblings == ["7192843091823.mp4", "7192843091823.txt"], str(siblings))


def test_formats() -> None:
    print("\n== Quality & acceleration ==")
    with_ffmpeg = format_selector(Quality.P1080, True)
    check("1080p caps the height", "height<=1080" in with_ffmpeg, with_ffmpeg)
    check("1080p prefers mp4/m4a", "ext=mp4" in with_ffmpeg and "ext=m4a" in with_ffmpeg)
    check("No-ffmpeg selector avoids stream merging",
          "+" not in format_selector(Quality.P720, False))
    check("Audio selector", format_selector(Quality.AUDIO, True) == "bestaudio/best")

    both = ffmpeg_acceleration_args(True, True)
    check("Both -> hwaccel + threads", "ffmpeg_i" in both and "ffmpeg" in both, str(both))
    check("GPU only -> hwaccel only", ffmpeg_acceleration_args(False, True).keys() == {"ffmpeg_i"})
    check("CPU only -> threads only", ffmpeg_acceleration_args(True, False).keys() == {"ffmpeg"})
    check("Neither -> no extra args", ffmpeg_acceleration_args(False, False) == {})


def test_profile_numbering_and_folders() -> None:
    print("\n== Per-profile numbering & output folders ==")
    with tempfile.TemporaryDirectory() as tmp:
        store = StateStore(Path(tmp) / "q.db", Path(tmp) / "a.txt")
        settings = Settings()
        settings.download_dir = tmp
        manager = DownloadManager(settings, store)

        added = manager._append([
            QueueItem(url="https://x/@alice/1", profile="@alice"),
            QueueItem(url="https://x/@alice/2", profile="@alice"),
            QueueItem(url="https://x/@bob/1", profile="@bob"),
            QueueItem(url="https://x/@alice/3", profile="@alice"),
        ])
        check("All 4 fresh items were added", added == 4)
        by_url = {i.url: i for i in manager.items}
        check("Alice's 1st video is No. 1",
              by_url["https://x/@alice/1"].profile_position == 1)
        check("Alice's 2nd video is No. 2",
              by_url["https://x/@alice/2"].profile_position == 2)
        check("Bob's video restarts at No. 1 despite being added 3rd overall",
              by_url["https://x/@bob/1"].profile_position == 1)
        check("Alice's 3rd video is No. 3 (not disturbed by Bob's item)",
              by_url["https://x/@alice/3"].profile_position == 3)
        check("Global queue position still increases monotonically",
              [manager.items[i].position for i in range(4)] == [1, 2, 3, 4])

        check("Profile folder name is filesystem-safe",
              profile_subdir("@weird/name:1") not in ("", "@weird/name:1"))
        check("Profile folder name is stable for a normal handle",
              profile_subdir("@mechdesign98") == "@mechdesign98")

        store.close()


def test_selection_start() -> None:
    print("\n== Table-selection download (start with a subset) ==")
    with tempfile.TemporaryDirectory() as tmp:
        store = StateStore(Path(tmp) / "q.db", Path(tmp) / "a.txt")
        settings = Settings()
        settings.download_dir = tmp
        manager = DownloadManager(settings, store)
        manager._append([
            QueueItem(url="https://x/1", profile="@p"),
            QueueItem(url="https://x/2", profile="@p"),
            QueueItem(url="https://x/3", profile="@p"),
        ])
        target = manager.items[1]

        # Stand in for the real network call: mark whichever item start() hands
        # us as completed, so we can see exactly which ones it decided to run.
        ran: list[str] = []

        def fake_run_item(item: QueueItem) -> None:
            ran.append(item.uid)
            item.set_status(ItemStatus.COMPLETED)

        manager._run_item = fake_run_item  # type: ignore[method-assign]
        started = manager.start(subset_uids={target.uid})
        for _ in range(50):
            if not manager.is_running:
                break
            _time.sleep(0.05)

        check("Only the selected item was submitted", started == 1, str(started))
        check("Only the selected item actually ran", ran == [target.uid], str(ran))
        check("Unselected items are still queued",
              all(i.status_enum is ItemStatus.QUEUED for i in manager.items if i is not target))
        check("Selected item completed", target.status_enum is ItemStatus.COMPLETED)

        store.close()


def test_db_migration() -> None:
    print("\n== Database migration (old schema -> current) ==")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "q.db"
        # Build a database exactly like a pre-upgrade release would have left
        # behind: every current column *except* profile_position.
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE items (
                uid TEXT PRIMARY KEY, url TEXT NOT NULL, profile TEXT DEFAULT '',
                source_url TEXT DEFAULT '', video_id TEXT DEFAULT '', title TEXT DEFAULT '',
                uploader TEXT DEFAULT '', duration REAL DEFAULT 0, status TEXT DEFAULT 'queued',
                progress REAL DEFAULT 0, speed REAL DEFAULT 0, eta REAL DEFAULT -1,
                total_bytes INTEGER DEFAULT 0, downloaded_bytes INTEGER DEFAULT 0,
                filepath TEXT DEFAULT '', error TEXT DEFAULT '', position INTEGER DEFAULT 0,
                session_id TEXT DEFAULT '', added_at REAL DEFAULT 0, updated_at REAL DEFAULT 0
            )
        """)
        conn.execute(
            "INSERT INTO items (uid, url, profile, position) VALUES ('abc','https://x/1','@old',1)"
        )
        conn.commit()
        conn.close()

        # Opening it with the current StateStore must not raise, must add the
        # missing column, and must keep the pre-existing row intact.
        store = StateStore(db_path, Path(tmp) / "a.txt")
        rows = store.load_all()
        check("Old database opens without error", len(rows) == 1)
        check("Pre-existing row survived the migration",
              rows and rows[0].url == "https://x/1", str(rows))
        check("New column defaulted to 0 on the old row",
              rows and rows[0].profile_position == 0)
        store.upsert(QueueItem(url="https://x/2", profile="@old", profile_position=2))
        check("New rows can use the migrated column", len(store.load_all()) == 2)
        store.close()


def test_state() -> None:
    print("\n== Smart Resume ==")
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "queue_state.db"
        archive = Path(tmp) / "download_archive.txt"
        store = StateStore(db, archive)

        items = [
            QueueItem(url="https://example.com/watch/1", profile="@alpha", position=1),
            QueueItem(url="https://example.com/watch/2", profile="@alpha", position=2),
            QueueItem(url="https://example.com/watch/3", profile="@beta", position=3),
        ]
        items[0].set_status(ItemStatus.COMPLETED)
        items[0].filepath = "/videos/1.mp4"
        items[1].set_status(ItemStatus.DOWNLOADING)
        items[1].progress = 0.42
        store.upsert_many(items)
        store.close()

        # Simulate an app restart: brand new store over the same files.
        reopened = StateStore(db, archive)
        loaded = reopened.load_all()
        check("All rows survived a restart", len(loaded) == 3, f"{len(loaded)} rows")
        check("Progress survived", any(abs(i.progress - 0.42) < 1e-9 for i in loaded))
        check("Completed row kept its file path",
              any(i.filepath == "/videos/1.mp4" for i in loaded))

        pending = reopened.pending_items()
        check("Only unfinished work is offered for resume",
              len(pending) == 2 and all(not i.status_enum.is_finished for i in pending),
              f"{len(pending)} pending")

        archive.write_text("tiktok 111\ntiktok 222\n", encoding="utf-8")
        check("Archive size is counted", reopened.archive_size() == 2)

        reopened.clear_finished()
        check("clear_finished keeps unfinished rows", len(reopened.load_all()) == 2)
        reopened.close()


def test_settings_and_i18n() -> None:
    print("\n== Settings & translations ==")
    settings = Settings()
    check("Default naming is ID only", settings.naming is NamingMode.ID_ONLY)
    check("Default quality is Best", settings.quality_enum is Quality.BEST)

    translator = Translator("en")
    english = translator.t("action.start")
    translator.set_language("kh")
    khmer = translator.t("action.start")
    check("Both languages load", bool(english) and bool(khmer) and english != khmer,
          f"{english!r} / {khmer!r}")
    check("Unknown keys fall back to the key itself", translator.t("nope.nope") == "nope.nope")
    check("Placeholders are filled", "5" in translator.t("msg.added", count=5))
    check("Language list", set(LANGUAGES) == {"en", "kh"})

    class Dummy:
        value = ""

    dummy = Dummy()
    translator.set_language("en")
    translator.bind(dummy, "value", "action.pause")
    before = dummy.value
    translator.set_language("kh")
    check("Bound controls follow the language switch", dummy.value != before,
          f"{before!r} -> {dummy.value!r}")


def test_monitor() -> None:
    print("\n== psutil monitor ==")
    samples: list = []
    monitor = SystemMonitor(samples.append, interval=1.0, disk_path=str(Path.cwd()))
    started = time.time()
    monitor.start()
    # The UI thread would keep running here; we just wait for two samples.
    while len(samples) < 2 and time.time() - started < 8:
        time.sleep(0.1)
    monitor.stop()

    check("Monitor produced samples", len(samples) >= 2, f"{len(samples)} samples")
    if samples:
        snapshot = samples[-1]
        check("CPU percent in range", 0.0 <= snapshot.cpu_percent <= 100.0,
              snapshot.format_cpu())
        check("RAM total looks real", snapshot.ram_total_gb > 0.1, snapshot.format_ram())
        check("RAM used <= total", snapshot.ram_used_gb <= snapshot.ram_total_gb + 0.01)
        check("Status line format", snapshot.as_line().startswith("CPU ") and
              "RAM" in snapshot.as_line(), snapshot.as_line())


def test_utils() -> None:
    print("\n== Helpers ==")
    text = """Check these:
    https://www.tiktok.com/@alpha
    https://www.facebook.com/beta/videos, https://www.instagram.com/reel/xyz/
    https://www.tiktok.com/@alpha
    """
    links = parse_links(text)
    check("Multi-line paste parsed", len(links) == 3, str(links))
    check("Duplicates dropped", len(set(links)) == len(links))
    check("Trailing comma stripped", all(not link.endswith(",") for link in links))
    check("human_bytes", human_bytes(1536 * 1024) == "1.5 MB", human_bytes(1536 * 1024))
    check("format_clock", format_clock(3725) == "01:02:05", format_clock(3725))
    check("format_clock unknown", format_clock(None) == "--:--:--")


def main() -> int:
    test_naming()
    test_formats()
    test_profile_numbering_and_folders()
    test_selection_start()
    test_db_migration()
    test_state()
    test_settings_and_i18n()
    test_monitor()
    test_utils()

    print("\n" + "=" * 60)
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED:")
        for name in FAILURES:
            print(f"  - {name}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
