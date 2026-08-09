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

import shutil
import subprocess
import threading
from collections import deque
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
    gpu_percent: float | None = None   # None = no supported GPU detected
    gpu_name: str = ""

    def format_cpu(self) -> str:
        return f"{self.cpu_percent:.0f}%"

    def format_ram(self) -> str:
        return f"{self.ram_used_gb:.1f} / {self.ram_total_gb:.1f} GB ({self.ram_percent:.0f}%)"

    def format_gpu(self) -> str:
        return f"{self.gpu_percent:.0f}%" if self.gpu_percent is not None else "-"

    def as_line(self) -> str:
        """Exactly the format requested: ``CPU  28%  |  RAM  5.4 / 16.0 GB (34%)``."""
        return f"CPU  {self.format_cpu()}  |  RAM  {self.format_ram()}"


_GB = 1024 ** 3


class _GpuProbe:
    """Best-effort NVIDIA GPU utilization via ``nvidia-smi`` — no extra pip dependency.

    ``nvidia-smi`` ships with every NVIDIA driver install (Windows, Linux); on a
    machine without an NVIDIA GPU it simply won't be on PATH, which is detected
    once and cached so a missing GPU never costs a subprocess spawn on every tick.
    """

    def __init__(self) -> None:
        self._binary = shutil.which("nvidia-smi")
        self._unavailable = self._binary is None
        # Hide the console flash Windows would otherwise show for each call.
        # (CREATE_NO_WINDOW only exists in the stdlib's Windows build of subprocess.)
        self._creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def sample(self) -> tuple[float | None, str]:
        if self._unavailable or not self._binary:
            return None, ""
        try:
            out = subprocess.check_output(
                [self._binary, "--query-gpu=utilization.gpu,name", "--format=csv,noheader,nounits"],
                stderr=subprocess.DEVNULL,
                timeout=2,
                creationflags=self._creationflags,
            )
            line = out.decode("utf-8", errors="ignore").splitlines()[0]
            percent_str, name = (part.strip() for part in line.split(",", 1))
            return float(percent_str), name
        except (OSError, subprocess.SubprocessError, ValueError, IndexError):
            # A single failure (e.g. driver hiccup) shouldn't permanently disable
            # the probe, but a binary that plain doesn't work is treated as absent.
            return None, ""


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
        self._gpu = _GpuProbe()
        # A short rolling average so one busy instant (an FFmpeg remux, a burst of
        # concurrent fragment downloads) doesn't make the readout jump around —
        # the underlying psutil sample is still a true, unmodified measurement.
        self._cpu_history: deque[float] = deque(maxlen=3)

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
        # cpu_percent() can read a hair over 100.0 on some platforms during a
        # timing edge case; clamp so the bar/label never show something absurd.
        cpu = max(0.0, min(100.0, cpu))
        self._cpu_history.append(cpu)
        smoothed_cpu = sum(self._cpu_history) / len(self._cpu_history)

        memory = psutil.virtual_memory()
        free_gb = 0.0
        if self.disk_path:
            try:
                free_gb = psutil.disk_usage(self.disk_path).free / _GB
            except (OSError, PermissionError):
                free_gb = 0.0

        gpu_percent, gpu_name = self._gpu.sample()

        return SystemSnapshot(
            cpu_percent=smoothed_cpu,
            ram_used_gb=(memory.total - memory.available) / _GB,
            ram_total_gb=memory.total / _GB,
            ram_percent=memory.percent,
            disk_free_gb=free_gb,
            gpu_percent=gpu_percent,
            gpu_name=gpu_name,
        )
