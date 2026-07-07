"""Rotating local log file with API-key redaction.

The API key must never reach the log: a filter scrubs both the literal key
(if known) and anything shaped like an xAI key or bearer token.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import re
from pathlib import Path

_KEY_PATTERNS = [
    re.compile(r"xai-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{8,}", re.IGNORECASE),
    re.compile(r"(api[_-]?key[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9_\-\.]{8,}", re.IGNORECASE),
]

_known_secrets: set[str] = set()


def register_secret(secret: str) -> None:
    """Tell the redactor about a literal secret value to scrub."""
    if secret and len(secret) >= 8:
        _known_secrets.add(secret)


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        redacted = _redact(msg)
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        return True


def _redact(text: str) -> str:
    for secret in _known_secrets:
        text = text.replace(secret, "***REDACTED***")
    for pat in _KEY_PATTERNS:
        text = pat.sub(lambda m: (m.group(1) if m.lastindex else "") + "***REDACTED***", text)
    return text


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / ".local" / "share"
    path = root / "GrokStudio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def setup_logging() -> logging.Logger:
    log_dir = app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        log_dir / "grok_studio.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    )
    handler.addFilter(RedactFilter())

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    # never let third-party libs log request headers at debug level
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return logging.getLogger("grok_studio")
