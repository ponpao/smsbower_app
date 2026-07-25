# -*- coding: utf-8 -*-
"""
Template exporter — renders the template pack to an MP4.

Separate from engine.render_video(), which drives the twelve legacy styles
through compose_frame(). This one drives visualizer.templates instead, and
leaves engine.py untouched. What it *does* reuse from engine is the parts
worth sharing: audio analysis, the encoder ladder, and the H.264 level table.

Frames are produced from their index, so an export is reproducible and a
resumed or re-run job yields identical bytes.
"""

from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np
from PIL import Image
from PyQt6.QtCore import QThread, pyqtSignal

from visualizer import engine
from visualizer import templates as T


@dataclass
class ExportJob:
    audio_path: str
    out_path: str
    template_key: str
    image_path: Optional[str] = None
    size: tuple = (2560, 1440)
    fps: int = 30
    use_gpu: bool = False
    title: str = ""
    artist: str = ""
    tracks: Sequence = field(default_factory=tuple)
    cues: Sequence = field(default_factory=tuple)
    font_family: Optional[str] = None


def _no_window():
    """Hide the console window ffmpeg would otherwise flash on Windows."""
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def build_ffmpeg_cmd(job: ExportJob) -> list:
    """Delivery-quality command. Mirrors the flags used by engine.render_video
    after the export-quality fix: bt709 tagged, dither before the 8-bit
    conversion, level derived from frame size."""
    w, h = job.size
    codec, opts = engine.pick_video_codec(job.use_gpu, (w, h))
    return [
        engine.ffmpeg_exe(), "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
        "-r", str(job.fps), "-i", "-",
        "-i", job.audio_path,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", codec, *opts,
        "-vf", "noise=alls=2:allf=t+u,format=yuv420p",
        "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709", "-color_trc", "bt709",
        "-colorspace", "bt709",
        "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
        "-shortest", "-movflags", "+faststart", job.out_path,
    ]


def load_art(path, size) -> Optional[Image.Image]:
    """Square cover art, centre-cropped, at a size the templates can use."""
    if not path:
        return None
    im = Image.open(path).convert("RGB")
    side = min(im.size)
    l = (im.width - side) // 2
    t = (im.height - side) // 2
    im = im.crop((l, t, l + side, t + side))
    target = max(256, int(min(size) * 0.75))
    return im.resize((target, target), Image.LANCZOS)


class ExportWorker(QThread):
    """Runs a render+encode off the GUI thread."""

    progress = pyqtSignal(int, int)          # frames done, total
    stage = pyqtSignal(str)                  # human-readable step
    finished_ok = pyqtSignal(str)            # output path
    failed = pyqtSignal(str)                 # message
    cancelled = pyqtSignal()

    def __init__(self, job: ExportJob, parent=None):
        super().__init__(parent)
        self.job = job
        self._cancel = threading.Event()
        self._proc = None

    def cancel(self):
        self._cancel.set()
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass

    # ------------------------------------------------------------------
    def run(self):
        job = self.job
        try:
            self.stage.emit("Analyzing audio…")
            an = engine.analyze([job.audio_path], job.fps)
            if self._cancel.is_set():
                self.cancelled.emit()
                return

            self.stage.emit("Preparing art…")
            art = load_art(job.image_path, job.size)
            tpl = T.TEMPLATES[job.template_key]
            w, h = job.size
            total = int(an.num_frames)

            cmd = build_ffmpeg_cmd(job)
            self.stage.emit("Encoding…")
            self._proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=_no_window())

            # Drain stderr so a full pipe can never deadlock the encoder.
            err_lines = []

            def drain():
                for line in self._proc.stderr:
                    err_lines.append(line)
            t_err = threading.Thread(target=drain, daemon=True)
            t_err.start()

            cues = list(job.cues)
            try:
                for i in range(total):
                    if self._cancel.is_set():
                        break
                    ctx = self._make_ctx(i, an, art, job, w, h, cues)
                    T.render_frame(tpl, ctx)
                    self._proc.stdin.write(ctx.frame.tobytes())
                    if i % 5 == 0 or i == total - 1:
                        self.progress.emit(i + 1, total)
            except BrokenPipeError:
                pass
            finally:
                try:
                    self._proc.stdin.close()
                except Exception:
                    pass

            code = self._proc.wait()
            t_err.join(timeout=2.0)

            if self._cancel.is_set():
                self._remove_partial()
                self.cancelled.emit()
                return
            if code != 0:
                msg = b"".join(err_lines).decode(errors="replace")[-500:]
                self.failed.emit(f"ffmpeg exited {code}\n{msg}")
                return
            self.finished_ok.emit(job.out_path)

        except Exception as exc:                      # noqa: BLE001
            import traceback
            self.failed.emit(f"{type(exc).__name__}: {exc}\n"
                             f"{traceback.format_exc(limit=3)}")

    def _remove_partial(self):
        try:
            if os.path.exists(self.job.out_path):
                os.remove(self.job.out_path)
        except OSError:
            pass

    @staticmethod
    def _cue_at(cues, t):
        for start, end, text in cues:
            if start <= t <= end:
                return (start, end, text)
        return None

    def _make_ctx(self, i, an, art, job, w, h, cues):
        bands = an.spectra[min(i, len(an.spectra) - 1)]
        return T.Ctx(
            frame=Image.new("RGB", (w, h)), w=w, h=h,
            i=i, fps=job.fps, duration=an.duration,
            bands=bands,
            bass=float(an.bass[min(i, len(an.bass) - 1)]),
            phase=float(an.phase[min(i, len(an.phase) - 1)]),
            art=art, title=job.title, artist=job.artist,
            tracks=job.tracks, cue=self._cue_at(cues, i / float(job.fps)),
            font_family=job.font_family,
        )
