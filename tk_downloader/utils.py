"""Small, dependency-free helpers shared across TK Downloader."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

# --------------------------------------------------------------------------------------
# Formatting helpers
# --------------------------------------------------------------------------------------

_UNITS = ("B", "KB", "MB", "GB", "TB")


def human_bytes(num: float | None) -> str:
    """Return a compact human readable size, e.g. ``12.4 MB``."""
    if not num or num < 0:
        return "-"
    value = float(num)
    for unit in _UNITS:
        if value < 1024 or unit == _UNITS[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TB"


def human_speed(bytes_per_sec: float | None) -> str:
    """Return a download speed such as ``2.3 MB/s``."""
    if not bytes_per_sec or bytes_per_sec <= 0:
        return "-"
    return f"{human_bytes(bytes_per_sec)}/s"


def human_eta(seconds: float | None) -> str:
    """Short ETA string (``5m 12s``) used inside the queue table."""
    if seconds is None or seconds < 0:
        return "-"
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def format_clock(seconds: float | None) -> str:
    """``HH:MM:SS`` clock used by the big countdown timer.

    Returns ``--:--:--`` when the value is unknown so the large timer never
    flickers between an empty string and a number.
    """
    if seconds is None or seconds < 0:
        return "--:--:--"
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def gb(num_bytes: float) -> float:
    """Bytes -> gigabytes (1024-based), rounded to one decimal by the caller."""
    return num_bytes / (1024 ** 3)


# --------------------------------------------------------------------------------------
# Filesystem helpers
# --------------------------------------------------------------------------------------

_INVALID_FS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(name: str, max_len: int = 120) -> str:
    """Strip characters that Windows/macOS/Linux refuse inside a file name."""
    cleaned = _INVALID_FS_CHARS.sub("_", (name or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return (cleaned or "untitled")[:max_len]


def atomic_write_text(path: str | os.PathLike[str], text: str, encoding: str = "utf-8") -> None:
    """Write ``text`` to ``path`` atomically.

    Used for settings and any sidecar metadata: a temporary file in the same
    directory is written, flushed, ``fsync``-ed and then ``os.replace``-d over
    the target. ``os.replace`` is atomic on POSIX and Windows, so a power cut can
    never leave a half-written file behind — a cornerstone of Smart Resume.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".tmp_", suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        # Never leave stray temp files around if something goes wrong.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def ensure_dir(path: str | os.PathLike[str]) -> Path:
    directory = Path(path).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


# --------------------------------------------------------------------------------------
# URL / profile helpers
# --------------------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)


def parse_links(text: str) -> list[str]:
    """Extract every URL from a multi-line paste, de-duplicated, order preserved.

    The input box is deliberately permissive: users paste a mix of profile URLs
    and single video URLs, sometimes with numbering or commentary around them.
    """
    seen: set[str] = set()
    result: list[str] = []
    for match in _URL_RE.finditer(text or ""):
        url = match.group(0).rstrip(".,;)]}")
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


def guess_profile(url: str) -> str:
    """Best-effort profile / channel label derived from a URL.

    Used before extraction so the table can already group items; yt-dlp metadata
    later overrides it with the real uploader name when available.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return "unknown"
    host = (parsed.netloc or "").lower().removeprefix("www.").removeprefix("m.")
    parts = [p for p in (parsed.path or "").split("/") if p]

    # TikTok / Twitter / Threads style: /@username/...
    for part in parts:
        if part.startswith("@"):
            return part
    if not parts:
        return host or "unknown"

    known_prefixes = {
        "channel", "c", "user", "watch", "shorts", "video", "videos", "reel",
        "reels", "p", "tv", "stories", "share", "playlist", "status", "posts",
    }
    for part in parts:
        if part.lower() in known_prefixes:
            continue
        return part
    return host or "unknown"


def unique_preserve(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def truncate(text: str, limit: int = 60) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"
