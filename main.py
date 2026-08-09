#!/usr/bin/env python3
"""TK Downloader — entry point.

    python main.py

Everything else lives in the :mod:`tk_downloader` package.
"""

from __future__ import annotations

import sys

MIN_PYTHON = (3, 11)


def _check_python() -> None:
    if sys.version_info < MIN_PYTHON:
        raise SystemExit(
            f"TK Downloader needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer "
            f"(running {sys.version.split()[0]})."
        )


def _check_dependencies() -> None:
    missing: list[str] = []
    for module, package in (("flet", "flet"), ("yt_dlp", "yt-dlp"), ("psutil", "psutil")):
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    if missing:
        raise SystemExit(
            "Missing dependencies: " + ", ".join(missing) +
            "\nInstall them with:  pip install -r requirements.txt"
        )


def main() -> None:
    _check_python()
    _check_dependencies()
    from tk_downloader.ui.app import run
    run()


if __name__ == "__main__":
    main()
