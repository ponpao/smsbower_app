# -*- coding: utf-8 -*-
"""Chrome Profile Manager — entry point.

Launches Google Chrome with isolated --user-data-dir profiles.
Data (profiles.json, settings.json, backups) lives in ./data next to the
executable / this script.
"""

import os
import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.storage import ProfileStore


def data_dir() -> str:
    if getattr(sys, "frozen", False):  # PyInstaller build
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "data")


def main() -> int:
    app = QApplication(sys.argv)
    store = ProfileStore(data_dir())
    window = MainWindow(store)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
