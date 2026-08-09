"""File naming rules and the ``ID.txt`` metadata sidecar.

--------------------------------------------------------------------------------
ID ONLY MODE  (default / recommended — the main style this app is built for)
--------------------------------------------------------------------------------
Output template  : ``%(id)s.%(ext)s``
Result on disk   : ``7192843091823.mp4``  +  ``7192843091823.txt``

The video keeps *only* the platform id as its name (no title, no numbering), and
the original title plus all useful metadata is written into a plain-text file
with **exactly the same stem**. Because both files share a stem, the pair can be
matched later with a single ``Path(video).with_suffix('.txt')``.

To guarantee the extension really is ``.mp4`` (and not ``.webm``/``.mkv``), the
downloader prefers mp4/m4a streams, sets ``merge_output_format='mp4'`` and
remuxes when FFmpeg is available. See :mod:`tk_downloader.downloader`.

Other modes
-----------
``TITLE_ONLY``  -> ``%(title)s.%(ext)s``            e.g. ``My holiday clip.mp4``
``NUM_TITLE``   -> ``NNN_%(title)s.%(ext)s``        e.g. ``007_My holiday clip.mp4``

The number in ``NUM_TITLE`` comes from the item's queue position rather than
yt-dlp's ``%(autonumber)s`` — with concurrent downloads autonumber is assigned in
completion order, which would scramble the sequence.
"""

from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path

from .models import NamingMode, QueueItem
from .utils import atomic_write_text, human_bytes, safe_filename

SIDECAR_SUFFIX = ".txt"


def output_template(mode: NamingMode, position: int = 0) -> str:
    """yt-dlp ``outtmpl`` fragment (file name only, the folder is set separately).

    ``position`` is the item's rank *within its own profile* (see
    ``QueueItem.profile_position``), not the global queue order — so numbering
    for ``NUM_TITLE`` restarts at 1 for every new profile, matching the
    per-profile output folder below.
    """
    if mode is NamingMode.ID_ONLY:
        # Exactly "<id>.<ext>" — nothing else, ever.
        return "%(id)s.%(ext)s"
    if mode is NamingMode.TITLE_ONLY:
        return "%(title)s.%(ext)s"
    # NUM_TITLE: stable, per-profile numbering.
    return f"{position:03d}_%(title)s.%(ext)s"


def profile_subdir(profile: str) -> str:
    """Filesystem-safe folder name for a profile, e.g. ``@mechdesign98``."""
    return safe_filename(profile or "unknown", max_len=80) or "unknown"


def naming_example(mode: NamingMode, video_ext: str = "mp4", position: int = 1) -> tuple[str, str]:
    """Live example shown in the UI's Naming section: ``(video_name, txt_name)``.

    Returns an empty string as the second element when no sidecar is written.
    """
    if mode is NamingMode.ID_ONLY:
        return (f"7192843091823.{video_ext}", f"7192843091823{SIDECAR_SUFFIX}")
    if mode is NamingMode.TITLE_ONLY:
        return (f"My holiday clip.{video_ext}", "")
    return (f"{position:03d}_My holiday clip.{video_ext}", "")


def sidecar_path_for(video_path: str | os.PathLike[str]) -> Path:
    """``/videos/1234.mp4`` -> ``/videos/1234.txt`` (same stem, always)."""
    path = Path(video_path)
    return path.with_suffix(SIDECAR_SUFFIX)


def _fmt_duration(seconds: float | None) -> str:
    if not seconds:
        return "unknown"
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _fmt_date(raw: str | None) -> str:
    """yt-dlp gives ``YYYYMMDD``; render it as ``YYYY-MM-DD`` when possible."""
    if not raw or len(str(raw)) != 8:
        return str(raw or "unknown")
    raw = str(raw)
    return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"


def build_metadata_text(info: dict, item: QueueItem | None = None) -> str:
    """Human-readable content of the ``<id>.txt`` sidecar.

    The very first line is the **original title** verbatim — that is the whole
    point of the file: the media keeps a machine-friendly id name while the human
    title stays recoverable next to it.
    """
    info = info or {}
    title = info.get("title") or (item.title if item else "") or "unknown"

    resolution = info.get("resolution")
    if not resolution and info.get("width") and info.get("height"):
        resolution = f"{info['width']}x{info['height']}"

    size = info.get("filesize") or info.get("filesize_approx")
    tags = info.get("tags") or []
    categories = info.get("categories") or []

    lines: list[str] = [
        title,
        "",
        "=" * 72,
        "TK Downloader - video metadata",
        "=" * 72,
        f"Title           : {title}",
        f"Video ID        : {info.get('id') or (item.video_id if item else '') or 'unknown'}",
        f"Profile         : {(item.profile if item else '') or info.get('uploader_id') or 'unknown'}",
        f"Uploader        : {info.get('uploader') or info.get('channel') or 'unknown'}",
        f"Uploader URL    : {info.get('uploader_url') or info.get('channel_url') or 'unknown'}",
        f"Source URL      : {info.get('webpage_url') or (item.url if item else '') or 'unknown'}",
        f"Extractor       : {info.get('extractor_key') or info.get('extractor') or 'unknown'}",
        f"Upload date     : {_fmt_date(info.get('upload_date'))}",
        f"Duration        : {_fmt_duration(info.get('duration'))}",
        f"Resolution      : {resolution or 'unknown'}",
        f"FPS             : {info.get('fps') or 'unknown'}",
        f"Format          : {info.get('format') or info.get('format_id') or 'unknown'}",
        f"File size       : {human_bytes(size) if size else 'unknown'}",
        f"View count      : {info.get('view_count') if info.get('view_count') is not None else 'unknown'}",
        f"Like count      : {info.get('like_count') if info.get('like_count') is not None else 'unknown'}",
        f"Comment count   : {info.get('comment_count') if info.get('comment_count') is not None else 'unknown'}",
        f"Categories      : {', '.join(map(str, categories)) if categories else '-'}",
        f"Tags            : {', '.join(map(str, tags[:40])) if tags else '-'}",
        f"Downloaded at   : {_dt.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "",
        "-" * 72,
        "Description",
        "-" * 72,
        (info.get("description") or "").strip() or "(no description)",
        "",
    ]
    return "\n".join(lines)


def write_sidecar(video_path: str | os.PathLike[str], info: dict,
                  item: QueueItem | None = None) -> Path:
    """Write ``<same stem>.txt`` next to the downloaded media, atomically.

    Called right after a successful download in ID-only mode (and for any mode
    when the user ticks "always write the .txt file").
    """
    target = sidecar_path_for(video_path)
    atomic_write_text(target, build_metadata_text(info, item))
    return target
