"""Load the bundled Kantumruy Pro font, falling back to Segoe UI.

The .ttf files are looked up in assets/fonts/ (both in the source tree and
inside a PyInstaller bundle via sys._MEIPASS). Run scripts/fetch_font.py once
before building to download the font from the google/fonts repository.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PyQt6.QtGui import QFontDatabase

from .constants import FONT_FAMILY_FALLBACK, FONT_FAMILY_PRIMARY

log = logging.getLogger("grok_studio.fonts")


def assets_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):  # PyInstaller onefile extraction dir
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).resolve().parent.parent / "assets"


def load_app_font() -> str:
    """Register bundled fonts and return the family name to use app-wide."""
    fonts_dir = assets_dir() / "fonts"
    loaded_families: set[str] = set()
    if fonts_dir.is_dir():
        for ttf in sorted(fonts_dir.glob("*.ttf")):
            font_id = QFontDatabase.addApplicationFont(str(ttf))
            if font_id >= 0:
                loaded_families.update(QFontDatabase.applicationFontFamilies(font_id))
            else:
                log.warning("failed to load font %s", ttf.name)

    for family in loaded_families:
        if FONT_FAMILY_PRIMARY.lower() in family.lower():
            return family
    if loaded_families:
        return sorted(loaded_families)[0]
    log.info("Kantumruy Pro not bundled — falling back to %s", FONT_FAMILY_FALLBACK)
    return FONT_FAMILY_FALLBACK
