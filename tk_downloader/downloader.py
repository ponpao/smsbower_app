"""yt-dlp integration: URL expansion, the worker pool and the download itself."""

from __future__ import annotations

import os
import shutil
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Iterable

from yt_dlp import YoutubeDL

from .config import Settings
from .cookies import cookie_options
from .models import ItemStatus, NamingMode, QueueItem, Quality, make_uid
from .naming import output_template, profile_subdir, sidecar_path_for, write_sidecar
from .state import StateStore
from .utils import guess_profile, parse_links

# How often (seconds) a downloading item is flushed to SQLite. Progress hooks fire
# many times per second; persisting every one of them would hammer the disk while
# buying nothing — a couple of seconds of lost progress simply means resuming from
# a slightly earlier byte offset, which yt-dlp handles anyway.
PERSIST_INTERVAL = 2.0

MAX_EXPAND_DEPTH = 2


class DownloadCancelled(Exception):
    """Raised inside a yt-dlp progress hook to abort a running transfer."""


# --------------------------------------------------------------------------------------
# yt-dlp option building
# --------------------------------------------------------------------------------------

# Common install locations that don't end up on PATH, checked as a last resort.
# winget's shim usually does land on PATH, but the underlying WinGet Links folder
# and a plain "install to Program Files, forget to add PATH" are both frequent
# enough on Windows to special-case.
_WINDOWS_FFMPEG_HINTS = (
    r"%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe",
    r"%LOCALAPPDATA%\Microsoft\WinGet\Packages",   # searched recursively, one level
    r"%ProgramFiles%\ffmpeg\bin\ffmpeg.exe",
    r"%ProgramFiles(x86)%\ffmpeg\bin\ffmpeg.exe",
    r"C:\ffmpeg\bin\ffmpeg.exe",
)


def find_ffmpeg(explicit_path: str = "") -> str:
    """Locate an ffmpeg executable. Returns its path, or "" if none was found.

    Search order: an explicit path the user set in Settings, then ``PATH``,
    then a short list of common Windows install locations that frequently
    aren't on ``PATH`` (a plain zip extraction, or WinGet's Links folder not
    yet picked up by the current shell).
    """
    if explicit_path:
        candidate = Path(explicit_path).expanduser()
        if candidate.is_dir():
            for name in ("ffmpeg.exe", "ffmpeg"):
                if (candidate / name).is_file():
                    return str(candidate / name)
        elif candidate.is_file():
            return str(candidate)

    found = shutil.which("ffmpeg")
    if found:
        return found

    if os.name == "nt":
        for hint in _WINDOWS_FFMPEG_HINTS:
            expanded = os.path.expandvars(hint)
            path = Path(expanded)
            if path.is_file():
                return str(path)
            if path.is_dir():
                try:
                    match = next(path.glob("**/ffmpeg.exe"))
                    return str(match)
                except StopIteration:
                    continue
    return ""


def has_ffmpeg(explicit_path: str = "") -> bool:
    """FFmpeg is required to merge separate video+audio streams and to remux to mp4."""
    return bool(find_ffmpeg(explicit_path))


_HEIGHTS = {
    Quality.P1080: 1080,
    Quality.P720: 720,
    Quality.P480: 480,
    Quality.P360: 360,
}


def format_selector(quality: Quality, ffmpeg: bool) -> str:
    """Translate the quality dropdown into a yt-dlp format expression.

    mp4/m4a streams are preferred so that the merged result is a real ``.mp4``
    (important for the ``ID.mp4`` promise); the trailing fallbacks make sure a
    site that only offers webm still downloads instead of failing.
    """
    if quality is Quality.AUDIO:
        return "bestaudio/best"
    height = _HEIGHTS.get(quality)
    if height is None:  # Quality.BEST
        if ffmpeg:
            return "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b[ext=mp4]/b"
        return "b[ext=mp4]/b"
    if ffmpeg:
        return (
            f"bv*[height<={height}][ext=mp4]+ba[ext=m4a]/"
            f"bv*[height<={height}]+ba/"
            f"b[height<={height}][ext=mp4]/b[height<={height}]/b"
        )
    return f"b[height<={height}][ext=mp4]/b[height<={height}]/b"


def ffmpeg_acceleration_args(use_cpu: bool, use_gpu: bool) -> dict[str, list[str]]:
    """FFmpeg arguments for the "Use CPU / Use GPU / Both" checkboxes.

    * **GPU**  -> ``-hwaccel auto`` on the *input* side, letting FFmpeg pick
      NVDEC/QSV/VideoToolbox/VAAPI depending on the machine.
    * **CPU**  -> ``-threads <cores>`` on the *output* side so muxing and audio
      extraction use every core.
    * **Both** -> both sets of flags at once.
    """
    input_args: list[str] = []
    output_args: list[str] = []
    if use_gpu:
        input_args += ["-hwaccel", "auto"]
    if use_cpu:
        output_args += ["-threads", str(os.cpu_count() or 4)]
    args: dict[str, list[str]] = {}
    if input_args:
        args["ffmpeg_i"] = input_args
    if output_args:
        args["ffmpeg"] = output_args
    return args


class _YdlLogger:
    """Routes yt-dlp's own messages into the app log panel."""

    def __init__(self, sink: Callable[[str], None] | None = None) -> None:
        self._sink = sink

    def _emit(self, msg: str) -> None:
        if self._sink and msg:
            self._sink(str(msg))

    def debug(self, msg: str) -> None:
        # yt-dlp routes info messages through debug() prefixed with "[debug] ".
        if msg and not msg.startswith("[debug]"):
            self._emit(msg)

    def info(self, msg: str) -> None:
        self._emit(msg)

    def warning(self, msg: str, only_once: bool = False) -> None:
        self._emit(f"⚠ {msg}")

    def error(self, msg: str) -> None:
        self._emit(f"✖ {msg}")


def build_ydl_opts(
    settings: Settings,
    item: QueueItem,
    archive_file: Path,
    progress_hook: Callable[[dict], None] | None = None,
    postprocessor_hook: Callable[[dict], None] | None = None,
    log_sink: Callable[[str], None] | None = None,
) -> dict:
    """Assemble the yt-dlp options for one queue item."""
    ffmpeg_bin = find_ffmpeg(settings.ffmpeg_path)
    ffmpeg = bool(ffmpeg_bin)
    quality = settings.quality_enum
    naming = settings.naming
    outdir = Path(settings.download_dir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)

    # Each profile gets its own subfolder by default (e.g. "<download_dir>/@user/"),
    # so videos from different profiles never land mixed together in one folder.
    filename_template = output_template(naming, item.profile_position or item.position)
    if settings.save_by_profile_folder:
        outtmpl = f"{profile_subdir(item.profile)}/{filename_template}"
    else:
        outtmpl = filename_template

    opts: dict = {
        # --- naming: for ID mode this is literally "%(id)s.%(ext)s" -------------
        "paths": {"home": str(outdir)},
        "outtmpl": {"default": outtmpl},
        "format": format_selector(quality, ffmpeg),
        "noplaylist": True,           # items are already single videos after expansion
        # --- Smart Resume -------------------------------------------------------
        "download_archive": str(archive_file),   # never re-download a finished video
        "continuedl": True,                      # resume half-finished .part files
        "part": True,
        "retries": settings.retries,
        "fragment_retries": settings.retries,
        "file_access_retries": 3,
        "concurrent_fragment_downloads": 4,
        # --- quiet, UI-driven output -------------------------------------------
        "quiet": True,
        "no_warnings": False,
        "noprogress": True,
        "consoletitle": False,
        "logger": _YdlLogger(log_sink),
        "ignoreerrors": False,
        "windowsfilenames": True,     # portable names on every OS
        "trim_file_name": 150,
        "overwrites": False,
    }

    if ffmpeg_bin:
        # Points yt-dlp at the exact binary we found, independent of PATH — fixes
        # the classic "ffmpeg is installed but not on PATH" case where quality
        # silently falls back to a single, lower-resolution progressive stream.
        opts["ffmpeg_location"] = ffmpeg_bin

    if progress_hook:
        opts["progress_hooks"] = [progress_hook]
    if postprocessor_hook:
        opts["postprocessor_hooks"] = [postprocessor_hook]

    if settings.rate_limit_kib > 0:
        opts["ratelimit"] = settings.rate_limit_kib * 1024

    opts.update(cookie_options(settings.cookies_browser, settings.cookies_file))

    postprocessors: list[dict] = []
    if quality is Quality.AUDIO:
        if ffmpeg:
            postprocessors.append(
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            )
    elif ffmpeg:
        # Guarantee ".mp4": merge separate streams into mp4 and remux any container
        # that is not already mp4. Remuxing is a stream copy, so it is fast and lossless.
        opts["merge_output_format"] = "mp4"
        postprocessors.append({"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"})

    if postprocessors:
        opts["postprocessors"] = postprocessors
        accel = ffmpeg_acceleration_args(settings.use_cpu, settings.use_gpu)
        if accel:
            opts["postprocessor_args"] = accel

    return opts


# --------------------------------------------------------------------------------------
# URL expansion (profiles -> individual videos)
# --------------------------------------------------------------------------------------

def _entry_url(entry: dict) -> str:
    return (
        entry.get("webpage_url")
        or entry.get("url")
        or entry.get("original_url")
        or ""
    )


def expand_url(
    url: str,
    settings: Settings,
    cancel: threading.Event | None = None,
    log_sink: Callable[[str], None] | None = None,
    depth: int = 0,
) -> list[QueueItem]:
    """Turn one pasted URL into concrete queue items.

    A single video URL yields one item. A profile / channel / playlist URL is
    expanded flatly (metadata only, no downloads) into every video it contains,
    and each resulting item is tagged with the profile it came from — that tag is
    what the table groups and filters by.
    """
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "ignoreerrors": True,
        "noprogress": True,
        "logger": _YdlLogger(log_sink),
    }
    if settings.fetch_limit > 0:
        # Cap how many videos are pulled from a single pasted profile/channel link.
        # yt-dlp still walks the listing in order, so this reliably means "the
        # N most recent uploads" rather than a random subset.
        opts["playlistend"] = settings.fetch_limit
    opts.update(cookie_options(settings.cookies_browser, settings.cookies_file))

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False, process=False)

    if not info:
        raise RuntimeError(f"Nothing could be extracted from {url}")

    fallback_profile = guess_profile(url)

    if info.get("_type") in ("playlist", "multi_video"):
        profile = (
            info.get("uploader_id")
            or info.get("channel_id")
            or info.get("uploader")
            or info.get("channel")
            or info.get("title")
            or fallback_profile
        )
        items: list[QueueItem] = []
        for entry in info.get("entries") or []:
            if cancel is not None and cancel.is_set():
                break
            if not entry:
                continue
            entry_url = _entry_url(entry)
            if not entry_url:
                continue
            if entry.get("_type") in ("playlist", "multi_video") and depth < MAX_EXPAND_DEPTH:
                items.extend(expand_url(entry_url, settings, cancel, log_sink, depth + 1))
                continue
            items.append(
                QueueItem(
                    url=entry_url,
                    profile=str(profile),
                    source_url=url,
                    uid=make_uid(entry_url),
                    video_id=str(entry.get("id") or ""),
                    title=str(entry.get("title") or entry_url),
                    uploader=str(entry.get("uploader") or info.get("uploader") or ""),
                    duration=float(entry.get("duration") or 0),
                )
            )
        return items

    # Single video.
    profile = (
        info.get("uploader_id")
        or info.get("channel_id")
        or info.get("uploader")
        or info.get("channel")
        or fallback_profile
    )
    return [
        QueueItem(
            url=_entry_url(info) or url,
            profile=str(profile),
            source_url=url,
            uid=make_uid(_entry_url(info) or url),
            video_id=str(info.get("id") or ""),
            title=str(info.get("title") or url),
            uploader=str(info.get("uploader") or ""),
            duration=float(info.get("duration") or 0),
        )
    ]


# --------------------------------------------------------------------------------------
# The manager
# --------------------------------------------------------------------------------------

class DownloadManager:
    """Owns the queue, the worker pool and all yt-dlp interaction.

    Every public method is safe to call from the Flet UI thread and returns
    immediately; the real work happens on background threads. The UI is notified
    through cheap callbacks (they only mark rows dirty) and repaints on its own
    timer, so a fast download can never flood or block the interface.
    """

    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        on_items_changed: Callable[[], None] | None = None,
        on_item_update: Callable[[QueueItem], None] | None = None,
        on_batch_finished: Callable[[dict], None] | None = None,
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.on_items_changed = on_items_changed or (lambda: None)
        self.on_item_update = on_item_update or (lambda item: None)
        self.on_batch_finished = on_batch_finished or (lambda stats: None)
        self.on_log = on_log or (lambda msg: None)

        self.items: list[QueueItem] = []
        self._lock = threading.RLock()
        self._executor: ThreadPoolExecutor | None = None
        self._futures: list[Future] = []
        self._cancel = threading.Event()      # set => abort in-flight downloads
        self._running = False
        self._expanding = False
        self._batch_started_at: float | None = None
        self._completed_durations: list[float] = []
        self._last_persist: dict[str, float] = {}
        # How many items have been seen per profile so far; drives QueueItem.profile_position
        # (the table's "No" column and the Num_Title numbering both restart at 1 per profile).
        self._profile_counts: dict[str, int] = {}

    # -- properties ------------------------------------------------------------------
    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_expanding(self) -> bool:
        return self._expanding

    def profiles(self) -> list[str]:
        with self._lock:
            return sorted({item.profile or "unknown" for item in self.items})

    # -- queue management --------------------------------------------------------------
    def load_from_store(self, items: Iterable[QueueItem], reset_active: bool = True) -> None:
        """Restore a previous session's queue (Smart Resume)."""
        with self._lock:
            self.items = list(items)
            self._profile_counts = {}
            for item in self.items:
                current = self._profile_counts.get(item.profile, 0)
                if item.profile_position > current:
                    self._profile_counts[item.profile] = item.profile_position
            if reset_active:
                for item in self.items:
                    # Anything that was mid-flight when the app died goes back to
                    # "queued"; the .part file and the archive make the retry cheap.
                    if item.status_enum.is_active or item.status_enum is ItemStatus.PAUSED:
                        item.set_status(ItemStatus.QUEUED)
                        item.speed = 0.0
                        item.eta = -1.0
                self.store.upsert_many(self.items)
        self.on_items_changed()

    def add_links_async(self, text: str, on_done: Callable[[int, list[str]], None] | None = None) -> None:
        """Expand a multi-line paste on a background thread and enqueue the results."""
        urls = parse_links(text)
        if not urls:
            if on_done:
                on_done(0, [])
            return

        def worker() -> None:
            self._expanding = True
            errors: list[str] = []
            added = 0
            try:
                for url in urls:
                    if self._cancel.is_set():
                        break
                    try:
                        new_items = expand_url(url, self.settings, self._cancel, self.on_log)
                    except Exception as exc:  # noqa: BLE001 - report, keep going
                        errors.append(f"{url}: {exc}")
                        self.on_log(f"✖ {url}: {exc}")
                        continue
                    added += self._append(new_items)
                    self.on_items_changed()
            finally:
                self._expanding = False
                if on_done:
                    on_done(added, errors)

        threading.Thread(target=worker, name="tkdl-expand", daemon=True).start()

    def _append(self, new_items: list[QueueItem]) -> int:
        """Add items, skipping URLs already in the queue. Returns how many were added."""
        with self._lock:
            existing = {item.uid for item in self.items}
            position = self.store.max_position()
            fresh: list[QueueItem] = []
            for item in new_items:
                if item.uid in existing:
                    continue
                position += 1
                item.position = position
                self._profile_counts[item.profile] = self._profile_counts.get(item.profile, 0) + 1
                item.profile_position = self._profile_counts[item.profile]
                item.session_id = self.store.session_id
                existing.add(item.uid)
                fresh.append(item)
            self.items.extend(fresh)
            if fresh:
                self.store.upsert_many(fresh)
        return len(fresh)

    def remove(self, uids: Iterable[str]) -> None:
        uid_set = set(uids)
        with self._lock:
            self.items = [item for item in self.items if item.uid not in uid_set]
        self.store.delete(uid_set)
        self.on_items_changed()

    def clear_finished(self) -> None:
        with self._lock:
            self.items = [item for item in self.items if not item.status_enum.is_finished]
        self.store.clear_finished()
        self.on_items_changed()

    def clear_all(self) -> None:
        self.stop()
        with self._lock:
            self.items = []
        self.store.clear_all()
        self.on_items_changed()

    def retry_failed(self) -> int:
        with self._lock:
            count = 0
            for item in self.items:
                if item.status_enum in (ItemStatus.ERROR, ItemStatus.CANCELLED):
                    item.set_status(ItemStatus.QUEUED)
                    item.error = ""
                    item.progress = 0.0
                    count += 1
            self.store.upsert_many(self.items)
        self.on_items_changed()
        return count

    # -- run control -------------------------------------------------------------------
    def start(self, subset_uids: set[str] | None = None) -> int:
        """Start (or resume) downloading.

        With ``subset_uids`` omitted, every queued/paused item runs (the normal
        "Start" button). Pass a set of uids — e.g. from a table selection — to
        download only those, leaving the rest of the queue untouched.
        """
        with self._lock:
            if self._running:
                return 0
            pending = [i for i in self.items if i.status_enum in (ItemStatus.QUEUED, ItemStatus.PAUSED)]
            if subset_uids is not None:
                pending = [i for i in pending if i.uid in subset_uids]
            for item in pending:
                item.set_status(ItemStatus.QUEUED)
            if not pending:
                return 0
            self.store.upsert_many(pending)
            self._cancel.clear()
            self._running = True
            self._batch_started_at = time.time()
            workers = max(1, min(int(self.settings.concurrency or 1), 16))
            self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="tkdl")
            self._futures = [self._executor.submit(self._run_item, item) for item in pending]

        threading.Thread(target=self._await_batch, name="tkdl-batch", daemon=True).start()
        self.on_items_changed()
        return len(self._futures)

    def pause(self) -> None:
        """Stop scheduling and abort in-flight transfers; ``.part`` files are kept."""
        self._cancel.set()
        with self._lock:
            for item in self.items:
                if item.status_enum is ItemStatus.QUEUED:
                    item.set_status(ItemStatus.PAUSED)
            self.store.upsert_many(self.items)
        self.on_items_changed()

    def stop(self) -> None:
        self.pause()
        executor = self._executor
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)

    def shutdown(self) -> None:
        """Called when the window closes: persist everything, drop the pool."""
        self._cancel.set()
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
        with self._lock:
            self.store.upsert_many(self.items)

    def _await_batch(self) -> None:
        for future in list(self._futures):
            try:
                future.result()
            except Exception:  # noqa: BLE001 - per-item errors already recorded
                pass
        with self._lock:
            self._running = False
            if self._executor is not None:
                self._executor.shutdown(wait=False)
                self._executor = None
            self.store.upsert_many(self.items)
        stats = self.stats()
        self.on_items_changed()
        self.on_batch_finished(stats)

    # -- the actual download -----------------------------------------------------------
    def _persist(self, item: QueueItem, force: bool = False) -> None:
        now = time.time()
        if force or now - self._last_persist.get(item.uid, 0.0) >= PERSIST_INTERVAL:
            self._last_persist[item.uid] = now
            self.store.upsert(item)

    def _run_item(self, item: QueueItem) -> None:
        if self._cancel.is_set():
            item.set_status(ItemStatus.PAUSED)
            self._persist(item, force=True)
            self.on_item_update(item)
            return

        started = time.time()
        item.set_status(ItemStatus.EXTRACTING)
        item.error = ""
        self.on_item_update(item)
        self._persist(item, force=True)

        info_holder: dict = {}

        def progress_hook(data: dict) -> None:
            # Called by yt-dlp many times per second, on the worker thread.
            if self._cancel.is_set():
                raise DownloadCancelled()
            status = data.get("status")
            info = data.get("info_dict") or {}
            if info:
                info_holder.update({k: info.get(k) for k in ("id", "title", "uploader")})
                if info.get("id") and not item.video_id:
                    item.video_id = str(info["id"])
                if info.get("title") and item.title == item.url:
                    item.title = str(info["title"])
            if status == "downloading":
                item.set_status(ItemStatus.DOWNLOADING)
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                done = data.get("downloaded_bytes") or 0
                item.total_bytes = int(total or 0)
                item.downloaded_bytes = int(done)
                item.progress = min(1.0, done / total) if total else 0.0
                item.speed = float(data.get("speed") or 0.0)
                item.eta = float(data.get("eta") if data.get("eta") is not None else -1)
            elif status == "finished":
                item.progress = 1.0
                item.speed = 0.0
                item.eta = 0.0
                item.set_status(ItemStatus.PROCESSING)
            self.on_item_update(item)
            self._persist(item)

        def postprocessor_hook(data: dict) -> None:
            if self._cancel.is_set():
                raise DownloadCancelled()
            if data.get("status") == "started":
                item.set_status(ItemStatus.PROCESSING)
                self.on_item_update(item)

        opts = build_ydl_opts(
            self.settings, item, self.store.archive_file,
            progress_hook=progress_hook,
            postprocessor_hook=postprocessor_hook,
            log_sink=self.on_log,
        )

        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(item.url, download=True)
                self._finalize(ydl, item, info)
        except DownloadCancelled:
            item.set_status(ItemStatus.PAUSED)
            item.speed = 0.0
            self.on_log(f"⏸ {item.title}")
        except Exception as exc:  # noqa: BLE001 - yt-dlp raises a wide range of errors
            item.set_status(ItemStatus.ERROR)
            item.error = f"{type(exc).__name__}: {exc}"
            item.speed = 0.0
            item.eta = -1.0
            self.on_log(f"✖ {item.title}: {exc}")
        finally:
            if item.status_enum is ItemStatus.COMPLETED:
                self._completed_durations.append(time.time() - started)
            self._persist(item, force=True)
            self.on_item_update(item)

    def _finalize(self, ydl: YoutubeDL, item: QueueItem, info: dict | None) -> None:
        """Resolve the produced file, write the ``.txt`` sidecar, set the final status."""
        if not info:
            # yt-dlp returns nothing when the video was filtered out — with our
            # options that means the download archive already had it.
            item.set_status(ItemStatus.SKIPPED)
            item.progress = 1.0
            return

        if info.get("id"):
            item.video_id = str(info["id"])
        if info.get("title"):
            item.title = str(info["title"])
        if info.get("uploader"):
            item.uploader = str(info["uploader"])
        if info.get("duration"):
            item.duration = float(info["duration"])

        filepath = ""
        requested = info.get("requested_downloads") or []
        if requested:
            filepath = requested[0].get("filepath") or requested[0].get("_filename") or ""
        if not filepath:
            try:
                filepath = ydl.prepare_filename(info)
            except Exception:  # noqa: BLE001
                filepath = ""

        if filepath and Path(filepath).exists():
            item.filepath = filepath
            item.set_status(ItemStatus.COMPLETED)
            item.progress = 1.0
            item.speed = 0.0
            item.eta = 0.0
            self._maybe_write_sidecar(item, info, Path(filepath))
            return

        # No new file: either it is already on disk from an earlier session
        # (Smart Resume) or the archive skipped it.
        existing = self._find_existing_file(item, info)
        already_archived = False
        try:
            already_archived = ydl.in_download_archive(info)
        except Exception:  # noqa: BLE001 - defensive, API is internal
            already_archived = False

        if existing is not None:
            item.filepath = str(existing)
            item.set_status(ItemStatus.SKIPPED)
            item.progress = 1.0
            # If the video survived but its sidecar did not, recreate it.
            self._maybe_write_sidecar(item, info, existing, only_if_missing=True)
        elif already_archived:
            item.set_status(ItemStatus.SKIPPED)
            item.progress = 1.0
        else:
            item.set_status(ItemStatus.ERROR)
            item.error = "Download finished but no output file was found."

    def _find_existing_file(self, item: QueueItem, info: dict) -> Path | None:
        """Locate a previously downloaded file for this item."""
        outdir = Path(self.settings.download_dir).expanduser()
        if self.settings.save_by_profile_folder:
            outdir = outdir / profile_subdir(item.profile)
        video_id = str(info.get("id") or item.video_id or "")
        candidates: list[Path] = []
        if self.settings.naming is NamingMode.ID_ONLY and video_id:
            candidates = sorted(outdir.glob(f"{video_id}.*"))
        elif info.get("title"):
            stem = str(info["title"])[:150]
            candidates = sorted(outdir.glob(f"{stem}.*"))
        for candidate in candidates:
            if candidate.suffix.lower() not in (".txt", ".part", ".ytdl"):
                return candidate
        return None

    def _maybe_write_sidecar(self, item: QueueItem, info: dict, video_path: Path,
                             only_if_missing: bool = False) -> None:
        """Write ``<stem>.txt`` for ID-only mode (or whenever the user asks for it).

        In ID-only mode the media file is named ``<id>.<ext>``, so the sidecar
        lands on ``<id>.txt`` — the exact ``ID.mp4`` + ``ID.txt`` pair.
        """
        wants_sidecar = self.settings.naming is NamingMode.ID_ONLY or self.settings.write_sidecar_always
        if not wants_sidecar:
            return
        target = sidecar_path_for(video_path)
        if only_if_missing and target.exists():
            return
        try:
            write_sidecar(video_path, info, item)
        except OSError as exc:
            self.on_log(f"⚠ Could not write {target.name}: {exc}")

    # -- statistics --------------------------------------------------------------------
    def stats(self) -> dict:
        """Counters plus the aggregate progress/speed/ETA driving the big timer."""
        with self._lock:
            items = list(self.items)

        counts = {status.value: 0 for status in ItemStatus}
        speed = 0.0
        active_etas: list[float] = []
        progress_sum = 0.0
        for item in items:
            counts[item.status] = counts.get(item.status, 0) + 1
            status = item.status_enum
            if status.is_finished:
                progress_sum += 1.0
            elif status is ItemStatus.DOWNLOADING:
                progress_sum += item.progress
                speed += max(0.0, item.speed)
                if item.eta and item.eta > 0:
                    active_etas.append(item.eta)

        total = len(items)
        done = counts.get(ItemStatus.COMPLETED.value, 0) + counts.get(ItemStatus.SKIPPED.value, 0)
        active = counts.get(ItemStatus.DOWNLOADING.value, 0) + \
            counts.get(ItemStatus.EXTRACTING.value, 0) + counts.get(ItemStatus.PROCESSING.value, 0)
        queued = counts.get(ItemStatus.QUEUED.value, 0) + counts.get(ItemStatus.PAUSED.value, 0)

        return {
            "total": total,
            "done": done,
            "active": active,
            "queued": queued,
            "failed": counts.get(ItemStatus.ERROR.value, 0),
            "overall_progress": (progress_sum / total) if total else 0.0,
            "speed": speed,
            "eta": self._aggregate_eta(active_etas, queued),
            "elapsed": (time.time() - self._batch_started_at) if self._batch_started_at else 0.0,
            "running": self._running,
            "counts": counts,
        }

    def _aggregate_eta(self, active_etas: list[float], queued: int) -> float | None:
        """Estimate the whole batch: slowest running item + queued items / workers.

        Returns ``None`` while there is not enough evidence yet, which the UI shows
        as ``--:--:--`` instead of a wildly wrong number.
        """
        if not active_etas and not queued:
            return 0.0 if self._running else None
        current = max(active_etas) if active_etas else None
        if not queued:
            return current
        if not self._completed_durations:
            return current  # no finished item yet -> cannot estimate the tail
        average = sum(self._completed_durations) / len(self._completed_durations)
        workers = max(1, int(self.settings.concurrency or 1))
        tail = (queued / workers) * average
        return (current or 0.0) + tail
