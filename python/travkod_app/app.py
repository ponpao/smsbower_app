"""TRAVKOD PyQt6 desktop app entry point."""
from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from .theme import build_qss
from .i18n import I18N, load_fonts, font_stack
from .state import SettingsStore
from .main_window import MainWindow


def _apply_style(app: QApplication) -> None:
    app.setStyleSheet(build_qss(font_stack(I18N.lang)))


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("TRAVKOD")
    app.setApplicationDisplayName("TRAVKOD")

    load_fonts()

    # Restore the saved language before building the UI so first render is right.
    settings = SettingsStore()
    saved = settings.load().get("lang", "en")
    I18N.lang = saved if saved in ("en", "kh") else "en"

    _apply_style(app)
    # Re-apply the stylesheet (font family) and persist on every language switch.
    I18N.changed.connect(lambda: (_apply_style(app), settings.set("lang", I18N.lang)))

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
