"""APIClient — single module wrapping every xAI endpoint the app uses.

Endpoints:
    POST /v1/chat/completions          (streaming SSE supported)
    POST /v1/images/generations
    POST /v1/videos/generations        + GET /v1/videos/{id} polling
    POST /v1/tts

This module is plain Python (no Qt): all methods are blocking and are meant
to be called from QThread workers (see workers.py). Rate-limit (429)
responses are retried once after the server's Retry-After delay; the wait is
reported through the optional `on_retry_wait` callback so the UI can show a
countdown.
"""

from __future__ import annotations

import base64
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

import requests

from .constants import (
    CHAT_MODEL,
    IMAGE_ASPECT_RATIOS,
    VIDEO_ASPECT_RATIOS,
    VIDEO_MAX_REFERENCE_IMAGES,
    XAI_BASE_URL,
)

log = logging.getLogger("grok_studio.api")

_TIMEOUT = (10, 120)  # connect, read


class ApiError(Exception):
    def __init__(self, message: str, status: int | None = None,
                 moderation: bool = False):
        super().__init__(message)
        self.status = status
        self.moderation = moderation


class CancelledError(Exception):
    pass


@dataclass
class VideoJob:
    job_id: str
    status: str = "queued"          # queued | rendering | done | failed | expired
    video_url: str | None = None
    video_b64: str | None = None
    raw: dict = field(default_factory=dict)

    @property
    def finished(self) -> bool:
        return self.status in ("done", "failed", "expired")


def _normalize_video_status(value: str) -> str:
    value = (value or "").lower()
    if value in ("queued", "pending", "created", "accepted"):
        return "queued"
    if value in ("rendering", "processing", "in_progress", "running", "generating"):
        return "rendering"
    if value in ("done", "completed", "complete", "succeeded", "success", "finished"):
        return "done"
    if value in ("expired",):
        return "expired"
    if value in ("failed", "error", "cancelled", "canceled", "rejected"):
        return "failed"
    return value or "queued"


class APIClient:
    """Blocking client for the xAI API. Never call from the GUI thread."""

    def __init__(self, api_key_provider: Callable[[], str | None],
                 base_url: str = XAI_BASE_URL):
        # A provider (not a stored string) so a key saved in Settings takes
        # effect immediately and the key never lingers on this object.
        self._get_key = api_key_provider
        self._base = base_url.rstrip("/")
        self._session = requests.Session()

    # ------------------------------------------------------------ plumbing --
    def _headers(self) -> dict[str, str]:
        key = self._get_key()
        if not key:
            raise ApiError("No API key configured", status=401)
        return {"Authorization": f"Bearer {key}",
                "Content-Type": "application/json"}

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        stream: bool = False,
        on_retry_wait: Callable[[int], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> requests.Response:
        url = f"{self._base}{path}"
        for attempt in (1, 2):  # one automatic retry on 429
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError()
            try:
                resp = self._session.request(
                    method, url, headers=self._headers(),
                    json=json_body, stream=stream, timeout=_TIMEOUT,
                )
            except requests.RequestException as exc:
                log.warning("network error on %s %s: %s", method, path, exc)
                raise ApiError(f"Network error: {exc.__class__.__name__}") from exc

            if resp.status_code == 429 and attempt == 1:
                wait = _retry_after_seconds(resp)
                log.info("429 on %s, retrying in %ss", path, wait)
                if on_retry_wait:
                    on_retry_wait(wait)
                deadline = time.monotonic() + wait
                while time.monotonic() < deadline:
                    if cancel_event is not None and cancel_event.is_set():
                        raise CancelledError()
                    time.sleep(0.2)
                continue

            if resp.status_code >= 400:
                raise ApiError(_error_message(resp), status=resp.status_code)
            return resp
        raise ApiError("Rate limited (429) — retry also failed", status=429)

    # ---------------------------------------------------------------- chat --
    def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = CHAT_MODEL,
        cancel_event: threading.Event | None = None,
        on_retry_wait: Callable[[int], None] | None = None,
    ) -> Iterator[str]:
        """Yield content deltas from a streaming chat completion."""
        resp = self._request(
            "POST", "/chat/completions",
            json_body={"model": model, "messages": messages, "stream": True},
            stream=True, on_retry_wait=on_retry_wait, cancel_event=cancel_event,
        )
        try:
            for raw_line in resp.iter_lines(decode_unicode=True):
                if cancel_event is not None and cancel_event.is_set():
                    raise CancelledError()
                if not raw_line or not raw_line.startswith("data:"):
                    continue
                payload = raw_line[len("data:"):].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                for choice in chunk.get("choices", []):
                    delta = (choice.get("delta") or {}).get("content")
                    if delta:
                        yield delta
        finally:
            resp.close()

    def chat(self, messages: list[dict[str, str]], *,
             model: str = CHAT_MODEL,
             on_retry_wait: Callable[[int], None] | None = None) -> str:
        """Non-streaming fallback."""
        resp = self._request(
            "POST", "/chat/completions",
            json_body={"model": model, "messages": messages},
            on_retry_wait=on_retry_wait,
        )
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise ApiError("Empty response from chat endpoint")
        return choices[0].get("message", {}).get("content", "")

    def test_connection(self) -> bool:
        """Minimal grok-4.3 call used by Settings to validate a key."""
        self.chat([{"role": "user", "content": "ping"}])
        return True

    # -------------------------------------------------------------- images --
    def generate_images(
        self,
        prompt: str,
        *,
        model: str,
        aspect_ratio: str = "1:1",
        n: int = 1,
        resolution: str | None = None,   # "1k" | "2k", quality model only
        on_retry_wait: Callable[[int], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> list[bytes]:
        if aspect_ratio not in IMAGE_ASPECT_RATIOS:
            raise ApiError(f"Invalid image aspect ratio: {aspect_ratio}")
        body: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "n": max(1, min(int(n), 10)),
            "aspect_ratio": aspect_ratio,
            "response_format": "b64_json",
        }
        if resolution:
            body["resolution"] = resolution
        resp = self._request("POST", "/images/generations", json_body=body,
                             on_retry_wait=on_retry_wait,
                             cancel_event=cancel_event)
        data = resp.json()
        images: list[bytes] = []
        for item in data.get("data", []):
            if item.get("respect_moderation") or item.get("moderated"):
                raise ApiError("Image rejected by moderation", moderation=True)
            if item.get("b64_json"):
                images.append(base64.b64decode(item["b64_json"]))
            elif item.get("url"):
                images.append(self.download(item["url"]))
        if not images:
            raise ApiError("No images returned")
        return images

    # --------------------------------------------------------------- video --
    def create_video_job(
        self,
        prompt: str,
        *,
        model: str,
        aspect_ratio: str = "16:9",
        resolution: str = "720p",
        duration_seconds: int = 5,
        reference_images: list[bytes] | None = None,
        on_retry_wait: Callable[[int], None] | None = None,
    ) -> VideoJob:
        if aspect_ratio not in VIDEO_ASPECT_RATIOS:
            # video accepts a SUBSET of the image ratios — see constants.py
            raise ApiError(f"Invalid video aspect ratio: {aspect_ratio}")
        body: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "duration": int(duration_seconds),
        }
        if reference_images:
            refs = reference_images[:VIDEO_MAX_REFERENCE_IMAGES]
            body["image"] = [
                "data:image/png;base64," + base64.b64encode(img).decode("ascii")
                for img in refs
            ]
        resp = self._request("POST", "/videos/generations", json_body=body,
                             on_retry_wait=on_retry_wait)
        data = resp.json()
        job_id = data.get("id") or data.get("job_id") or data.get("request_id")
        if not job_id:
            raise ApiError("Video endpoint returned no job id")
        return VideoJob(job_id=str(job_id),
                        status=_normalize_video_status(data.get("status", "queued")),
                        raw=data)

    def get_video_job(self, job_id: str,
                      on_retry_wait: Callable[[int], None] | None = None) -> VideoJob:
        resp = self._request("GET", f"/videos/{job_id}",
                             on_retry_wait=on_retry_wait)
        data = resp.json()
        job = VideoJob(job_id=job_id,
                       status=_normalize_video_status(data.get("status", "")),
                       raw=data)
        video = data.get("video") or data.get("data") or {}
        if isinstance(video, list):
            video = video[0] if video else {}
        job.video_url = (data.get("url") or data.get("video_url")
                         or (video.get("url") if isinstance(video, dict) else None))
        job.video_b64 = (data.get("b64_json")
                         or (video.get("b64_json") if isinstance(video, dict) else None))
        if job.status == "done" and not (job.video_url or job.video_b64):
            # finished but nothing to fetch — treat as failure, not success
            job.status = "failed"
        return job

    # ----------------------------------------------------------------- tts --
    def tts(
        self,
        text: str,
        *,
        voice: str,
        language: str | None = None,
        on_retry_wait: Callable[[int], None] | None = None,
    ) -> bytes:
        """Generate speech, returning MP3 bytes."""
        body: dict[str, Any] = {"input": text, "voice": voice,
                                "response_format": "mp3"}
        if language:
            body["language"] = language
        resp = self._request("POST", "/tts", json_body=body,
                             on_retry_wait=on_retry_wait)
        ctype = resp.headers.get("Content-Type", "")
        if "json" in ctype:
            data = resp.json()
            nested = data.get("data") if isinstance(data.get("data"), dict) else {}
            b64 = (data.get("audio") or data.get("b64_json")
                   or nested.get("audio") or nested.get("b64_json"))
            if isinstance(b64, str):
                return base64.b64decode(b64)
            raise ApiError("TTS endpoint returned no audio")
        return resp.content

    # ------------------------------------------------------------ download --
    def download(self, url: str,
                 cancel_event: threading.Event | None = None) -> bytes:
        try:
            resp = self._session.get(url, timeout=_TIMEOUT, stream=True)
            resp.raise_for_status()
            buf = bytearray()
            for chunk in resp.iter_content(chunk_size=65536):
                if cancel_event is not None and cancel_event.is_set():
                    raise CancelledError()
                buf.extend(chunk)
            return bytes(buf)
        except requests.RequestException as exc:
            raise ApiError(f"Download failed: {exc.__class__.__name__}") from exc


def _retry_after_seconds(resp: requests.Response) -> int:
    try:
        return max(1, min(int(float(resp.headers.get("Retry-After", "5"))), 120))
    except (TypeError, ValueError):
        return 5


def _error_message(resp: requests.Response) -> str:
    try:
        data = resp.json()
        err = data.get("error")
        if isinstance(err, dict):
            return f"HTTP {resp.status_code}: {err.get('message') or err}"
        if isinstance(err, str):
            return f"HTTP {resp.status_code}: {err}"
        if data.get("message"):
            return f"HTTP {resp.status_code}: {data['message']}"
    except (ValueError, AttributeError):
        pass
    return f"HTTP {resp.status_code}: {resp.reason or 'request failed'}"
