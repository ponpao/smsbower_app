"""
main.py — Entry point for Magic Studio (local audio toolkit).

A local-only PyQt6 desktop tool: on-device mastering, honest audio analysis,
and an accurate metadata/tag editor. No cloud uploads, no session/cookie
automation, no AI-detection evasion.
"""

from __future__ import annotations

import os
import sys

from PyQt6.QtWidgets import QApplication

from controller import MainController


def _load_stylesheet():
    qss_path = os.path.join(os.path.dirname(__file__), "views", "styles.qss")
    try:
        with open(qss_path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Magic Studio")
    window = MainController(stylesheet=_load_stylesheet())
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
