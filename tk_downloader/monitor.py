"""Live CPU / RAM monitoring with psutil — mandatory bottom status bar feature.

Design notes
------------
``psutil.cpu_percent(interval=1.0)`` *blocks* for a full second while it samples.
Calling it on the Flet UI thread would freeze the interface once per second, so
the sampling loop lives on its own daemon thread and simply hands a finished
snapshot to a callback. The UI callback does nothing but assign a few strings to
labels, which is cheap and keeps the window responsive even while a dozen
downloads are saturating the machine.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

import psutil


@dataclass(frozen=True)
class SystemSnapshot:
    """One sample of machine load."""

    cpu_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    ram_percent: float = 0.0
    disk_free_gb: float = 0.0

    def format_cpu(self) -> str:
        return f"{self.cpu_percent:.0f}%"

    def format_ram(self) -> str:
        return f"{self.ram_used_gb:.1f} / {self.ram_total_gb:.1f} GB ({self.ram_percent:.0f}%)"

    def as_line(self) -> str:
        """Exactly the format requested: ``CPU  28%  |  RAM  5.4 / 16.0 GB (34%)``."""
        return f"CPU  {self.format_cpu()}  |  RAM  {self.format_ram()}"


_GB = 1024 ** 3


class SystemMonitor:
    """Background sampler that pushes :class:`SystemSnapshot` to a callback."""

    def __init__(
        self,
        callback: Callable[[SystemSnapshot], None],
        interval: float = 1.5,
        disk_path: str | None = None,
    ) -> None:
        self._callback = callback
        # 1-2 seconds as specified: responsive without wasting CPU on the monitor itself.
        self.interval = max(1.0, min(float(interval), 2.0))
        self.disk_path = disk_path
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.latest = SystemSnapshot()

    # -- lifecycle -------------------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        # Prime the counter: the first cpu_percent() call always returns 0.0 because
        # it has no previous sample to compare against.
        psutil.cpu_percent(interval=None)
        self._thread = threading.Thread(target=self._loop, name="tkdl-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def set_disk_path(self, path: str | None) -> None:
        """Track free space on the folder downloads are written to."""
        self.disk_path = path

    # -- worker ----------------------------------------------------------------------
    def _loop(self) -> None:
        while not self._stop.is_set():
            snapshot = self.sample()
            self.latest = snapshot
            try:
                self._callback(snapshot)
            except Exception:  # noqa: BLE001 - a UI hiccup must not kill the monitor
                pass
            # cpu_percent(interval=...) already slept for us; wait out the remainder.
            self._stop.wait(max(0.0, self.interval - 1.0))

    def sample(self) -> SystemSnapshot:
        """Take one blocking sample (safe: only ever runs on the monitor thread)."""
        cpu = psutil.cpu_percent(interval=1.0)
        memory = psutil.virtual_memory()
        free_gb = 0.0
        if self.disk_path:
            try:
                free_gb = psutil.disk_usage(self.disk_path).free / _GB
            except (OSError, PermissionError):
                free_gb = 0.0
        return SystemSnapshot(
            cpu_percent=cpu,
            ram_used_gb=(memory.total - memory.available) / _GB,
            ram_total_gb=memory.total / _GB,
            ram_percent=memory.percent,
            disk_free_gb=free_gb,
        )
