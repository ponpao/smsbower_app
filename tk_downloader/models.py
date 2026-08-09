"""Data model for the download queue.

Everything the UI shows and everything Smart Resume persists lives on
:class:`QueueItem`. The object is deliberately a plain dataclass of primitives so
it round-trips to SQLite (and back) without any conversion layer.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field, asdict
from enum import Enum


class NamingMode(str, Enum):
    """How output files are named.

    ``ID_ONLY`` is the default and the primary style this app is built around:
    it yields exactly ``<id>.mp4`` plus a matching ``<id>.txt`` sidecar holding
    the original title and metadata.
    """

    ID_ONLY = "id_only"
    TITLE_ONLY = "title_only"
    NUM_TITLE = "num_title"


class Quality(str, Enum):
    BEST = "best"
    P1080 = "1080p"
    P720 = "720p"
    P480 = "480p"
    P360 = "360p"
    AUDIO = "audio"


class ItemStatus(str, Enum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"      # merging / remuxing / writing the .txt sidecar
    COMPLETED = "completed"
    SKIPPED = "skipped"            # already present in the yt-dlp download archive
    ERROR = "error"
    PAUSED = "paused"
    CANCELLED = "cancelled"

    @property
    def is_finished(self) -> bool:
        return self in (ItemStatus.COMPLETED, ItemStatus.SKIPPED)

    @property
    def is_active(self) -> bool:
        return self in (
            ItemStatus.EXTRACTING,
            ItemStatus.DOWNLOADING,
            ItemStatus.PROCESSING,
        )

    @property
    def is_pending(self) -> bool:
        """Work that still has to happen — what "Resume previous session" restores."""
        return self in (
            ItemStatus.QUEUED,
            ItemStatus.EXTRACTING,
            ItemStatus.DOWNLOADING,
            ItemStatus.PROCESSING,
            ItemStatus.PAUSED,
        )


# Statuses that must never be silently retried without the user asking.
TERMINAL_STATUSES = (ItemStatus.COMPLETED, ItemStatus.SKIPPED, ItemStatus.CANCELLED)


def make_uid(url: str) -> str:
    """Stable identifier for an item, derived from its URL.

    Deterministic on purpose: re-pasting the same link after a crash maps onto
    the same database row instead of creating a duplicate.
    """
    return hashlib.sha1(url.strip().encode("utf-8")).hexdigest()[:16]


@dataclass
class QueueItem:
    """A single downloadable video plus its live progress state."""

    url: str
    profile: str = "unknown"
    source_url: str = ""              # the profile/playlist URL the item came from
    uid: str = ""
    video_id: str = ""
    title: str = ""
    uploader: str = ""
    duration: float = 0.0
    status: str = ItemStatus.QUEUED.value
    progress: float = 0.0             # 0.0 - 1.0
    speed: float = 0.0                # bytes/second
    eta: float = -1.0                 # seconds remaining, -1 = unknown
    total_bytes: int = 0
    downloaded_bytes: int = 0
    filepath: str = ""
    error: str = ""
    position: int = 0                 # global queue insertion order
    profile_position: int = 0         # 1-based rank *within its own profile*
    session_id: str = ""
    added_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.uid:
            self.uid = make_uid(self.url)
        if not self.title:
            self.title = self.url

    # -- convenience ---------------------------------------------------------------
    @property
    def status_enum(self) -> ItemStatus:
        try:
            return ItemStatus(self.status)
        except ValueError:
            return ItemStatus.QUEUED

    def set_status(self, status: ItemStatus) -> None:
        self.status = status.value
        self.updated_at = time.time()

    def to_row(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> "QueueItem":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in row.items() if k in known})
