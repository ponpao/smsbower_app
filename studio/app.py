# -*- coding: utf-8 -*-
"""Application entry point.

Fonts are registered with Qt from the bundled folder before any widget is
built, so the UI renders Khmer, Thai, Devanagari, Tamil and Hangul labels
correctly with no dependency on what the user has installed. Qt embeds
HarfBuzz, so complex-script shaping in the interface is correct by default —
the same guarantee the render pipeline gets from uharfbuzz.
"""

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication

from . import theme

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "visualizer", "fonts")

# One face per script is enough for the interface; the renderer picks its own.
UI_FONTS = (
    "NotoSansKhmer-VF.ttf",
    "NotoSansThai-Regular.ttf",
    "NotoSansDevanagari-Regular.ttf",
    "NotoSansTamil-Regular.ttf",
    "NanumSquare-Regular.ttf",
)


def load_fonts():
    loaded = []
    for name in UI_FONTS:
        path = os.path.join(FONT_DIR, name)
        if not os.path.exists(path):
            continue
        fid = QFontDatabase.addApplicationFont(path)
        if fid != -1:
            loaded += QFontDatabase.applicationFontFamilies(fid)
    return loaded


def build_app(argv=None):
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Pulse Rail Lyric Studio")
    app.setOrganizationName("TRAVKOD CODEs")
    load_fonts()
    app.setStyleSheet(theme.stylesheet())
    return app


def main():
    app = build_app()
    from .main_window import MainWindow
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
