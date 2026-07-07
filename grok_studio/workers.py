"""QThread workers — every network call in the app goes through one of these.

Nothing here ever runs `requests` on the GUI thread. Workers communicate
exclusively through signals: progress / success(data) / error(message).
"""

from __future__ import annotations

import inspect
import logging
import threading
import time
from typing import Any, Callable

from PyQt6.QtCore import QThread, pyqtSignal

from .api_client import APIClient, ApiError, CancelledError, VideoJob
from .constants import VIDEO_POLL_INTERVAL_S

log = logging.getLogger("grok_studio.workers")


class ApiWorker(QThread):
    """Run one blocking APIClient call off the GUI thread."""

    success = pyqtSignal(object)
    error = pyqtSignal(str)
    retry_wait = pyqtSignal(int)     # seconds until the automatic 429 retry

    def __init__(self, fn: Callable[..., Any], /, *args, parent=None, **kwargs):
        super().__init__(parent)
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        kwargs = dict(self._kwargs)
        params = inspect.signature(self._fn).parameters
        if "on_retry_wait" in params:
            kwargs.setdefault("on_retry_wait", self.retry_wait.emit)
        if "cancel_event" in params:
            kwargs.setdefault("cancel_event", self.cancel_event)
        try:
            result = self._fn(*self._args, **kwargs)
        except CancelledError:
            return
        except ApiError as exc:
            self.error.emit(str(exc))
            return
        except Exception:  # noqa: BLE001 — surface anything unexpected
            log.exception("worker crashed")
            self.error.emit("Unexpected error — see log file")
            return
        if not self.cancel_event.is_set():
            self.success.emit(result)


class ChatStreamWorker(QThread):
    """Streaming chat completion; emits text deltas as they arrive."""

    chunk = pyqtSignal(str)
    done = pyqtSignal(str)           # full assistant message
    error = pyqtSignal(str)
    retry_wait = pyqtSignal(int)

    def __init__(self, client: APIClient, messages: list[dict[str, str]],
                 parent=None):
        super().__init__(parent)
        self._client = client
        self._messages = messages
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        parts: list[str] = []
        try:
            for delta in self._client.chat_stream(
                self._messages,
                cancel_event=self.cancel_event,
                on_retry_wait=self.retry_wait.emit,
            ):
                parts.append(delta)
                self.chunk.emit(delta)
        except CancelledError:
            return
        except ApiError as exc:
            # fall back to a plain (non-streaming) request once if streaming
            # itself is what failed and nothing has arrived yet
            if not parts:
                try:
                    text = self._client.chat(self._messages,
                                             on_retry_wait=self.retry_wait.emit)
                    self.done.emit(text)
                    return
                except ApiError as exc2:
                    self.error.emit(str(exc2))
                    return
            self.error.emit(str(exc))
            return
        except Exception:  # noqa: BLE001
            log.exception("chat stream crashed")
            self.error.emit("Unexpected error — see log file")
            return
        if not self.cancel_event.is_set():
            self.done.emit("".join(parts))


class VideoPollWorker(QThread):
    """Create a video job, then poll GET /videos/{id} every 5 s.

    Cancelling stops the polling only — the job may still complete (and be
    billed) server-side; the UI notes this in the Cancel button tooltip.
    """

    status = pyqtSignal(str, int)    # normalized status, elapsed seconds
    completed = pyqtSignal(object)   # VideoJob with url/b64 set
    error = pyqtSignal(str)
    retry_wait = pyqtSignal(int)

    def __init__(self, client: APIClient, create_kwargs: dict, parent=None):
        super().__init__(parent)
        self._client = client
        self._create_kwargs = create_kwargs
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        started = time.monotonic()
        try:
            job = self._client.create_video_job(
                on_retry_wait=self.retry_wait.emit, **self._create_kwargs
            )
        except CancelledError:
            return
        except ApiError as exc:
            self.error.emit(str(exc))
            return
        except Exception:  # noqa: BLE001
            log.exception("video create crashed")
            self.error.emit("Unexpected error — see log file")
            return

        self.status.emit(job.status, 0)
        while not self.cancel_event.is_set():
            deadline = time.monotonic() + VIDEO_POLL_INTERVAL_S
            while time.monotonic() < deadline:
                if self.cancel_event.is_set():
                    return
                time.sleep(0.2)
            try:
                job = self._client.get_video_job(
                    job.job_id, on_retry_wait=self.retry_wait.emit
                )
            except ApiError as exc:
                self.error.emit(str(exc))
                return
            except Exception:  # noqa: BLE001
                log.exception("video poll crashed")
                self.error.emit("Unexpected error — see log file")
                return

            elapsed = int(time.monotonic() - started)
            self.status.emit(job.status, elapsed)
            if job.finished:
                break

        if self.cancel_event.is_set():
            return
        if job.status == "done":
            self.completed.emit(job)
        else:
            self.error.emit(f"Video job {job.status}")


class DownloadWorker(QThread):
    """Download a URL (e.g. finished video) to bytes off the GUI thread."""

    success = pyqtSignal(bytes)
    error = pyqtSignal(str)

    def __init__(self, client: APIClient, url: str, parent=None):
        super().__init__(parent)
        self._client = client
        self._url = url
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            data = self._client.download(self._url,
                                         cancel_event=self.cancel_event)
        except CancelledError:
            return
        except ApiError as exc:
            self.error.emit(str(exc))
            return
        if not self.cancel_event.is_set():
            self.success.emit(bytes(data))
