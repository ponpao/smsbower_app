"""Grok Studio — entry point.

Run:    python main.py
Build:  pyinstaller grok_studio.spec
"""

from __future__ import annotations

import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from grok_studio import APP_NAME, ORG_NAME
from grok_studio.fonts import assets_dir, load_app_font
from grok_studio.logging_setup import setup_logging
from grok_studio.settings_manager import SettingsManager
from grok_studio.theme import build_stylesheet
from grok_studio.ui.main_window import MainWindow


def main() -> int:
    log = setup_logging()
    log.info("starting %s", APP_NAME)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)

    icon_path = assets_dir() / "icons" / "grok_studio.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    font_family = load_app_font()
    app.setStyleSheet(build_stylesheet(font_family))

    settings = SettingsManager()
    window = MainWindow(settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
