# -*- coding: utf-8 -*-
"""Application log: data/logs/app.log, viewable via View → Logs."""

import logging
import os
from logging.handlers import RotatingFileHandler

_log = logging.getLogger("chrome_profile_manager")
_log_path = ""


def setup(data_dir: str) -> logging.Logger:
    global _log_path
    logs_dir = os.path.join(data_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    _log_path = os.path.join(logs_dir, "app.log")
    if not _log.handlers:
        handler = RotatingFileHandler(_log_path, maxBytes=512 * 1024,
                                      backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s"))
        _log.addHandler(handler)
        _log.setLevel(logging.INFO)
    return _log


def log() -> logging.Logger:
    return _log


def read_log(max_bytes: int = 256 * 1024) -> str:
    if not _log_path or not os.path.exists(_log_path):
        return ""
    with open(_log_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - max_bytes))
        return f.read().decode("utf-8", errors="replace")
