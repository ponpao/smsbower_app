"""Central persisted preferences + secure API-key storage.

Preferences live in QSettings (registry / ini). The API key never touches
QSettings, files or logs: it is stored exclusively through `keyring`, which
wraps Windows Credential Manager on Windows.
"""

from __future__ import annotations

import logging
from pathlib import Path

import keyring
from PyQt6.QtCore import QObject, QSettings, QStandardPaths, pyqtSignal

from . import ORG_NAME, APP_NAME
from .constants import IMAGE_ASPECT_RATIOS, VIDEO_ASPECT_RATIOS, TTS_VOICES
from .i18n import DEFAULT_LANGUAGE
from .logging_setup import register_secret

log = logging.getLogger("grok_studio.settings")

_KEYRING_SERVICE = "GrokStudio"
_KEYRING_USER = "xai_api_key"


class SettingsManager(QObject):
    language_changed = pyqtSignal(str)      # "en" | "kh"
    api_key_changed = pyqtSignal(bool)      # True if a key is now stored

    def __init__(self) -> None:
        super().__init__()
        self._qs = QSettings(ORG_NAME, APP_NAME)

    # ------------------------------------------------------------- api key --
    def get_api_key(self) -> str | None:
        try:
            key = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
        except Exception:  # noqa: BLE001 — a broken backend must not crash the app
            log.exception("keyring read failed")
            return None
        if key:
            register_secret(key)
        return key

    def set_api_key(self, key: str) -> bool:
        register_secret(key)
        try:
            keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, key)
        except Exception:  # noqa: BLE001
            log.exception("keyring write failed")
            return False
        self.api_key_changed.emit(True)
        return True

    def delete_api_key(self) -> None:
        try:
            keyring.delete_password(_KEYRING_SERVICE, _KEYRING_USER)
        except Exception:  # noqa: BLE001
            pass
        self.api_key_changed.emit(False)

    def has_api_key(self) -> bool:
        return bool(self.get_api_key())

    # --------------------------------------------------------- preferences --
    @property
    def language(self) -> str:
        return str(self._qs.value("ui/language", DEFAULT_LANGUAGE))

    @language.setter
    def language(self, lang: str) -> None:
        self._qs.setValue("ui/language", lang)
        self.language_changed.emit(lang)

    @property
    def default_image_ratio(self) -> str:
        val = str(self._qs.value("image/default_ratio", "1:1"))
        return val if val in IMAGE_ASPECT_RATIOS else "1:1"

    @default_image_ratio.setter
    def default_image_ratio(self, ratio: str) -> None:
        self._qs.setValue("image/default_ratio", ratio)

    @property
    def default_video_ratio(self) -> str:
        val = str(self._qs.value("video/default_ratio", "16:9"))
        return val if val in VIDEO_ASPECT_RATIOS else "16:9"

    @default_video_ratio.setter
    def default_video_ratio(self, ratio: str) -> None:
        self._qs.setValue("video/default_ratio", ratio)

    @property
    def last_voice(self) -> str:
        val = str(self._qs.value("voice/last_voice", TTS_VOICES[0]))
        return val if val in TTS_VOICES else TTS_VOICES[0]

    @last_voice.setter
    def last_voice(self, voice: str) -> None:
        self._qs.setValue("voice/last_voice", voice)

    @property
    def last_tts_language(self) -> str:
        return str(self._qs.value("voice/last_language", "en"))

    @last_tts_language.setter
    def last_tts_language(self, lang: str) -> None:
        self._qs.setValue("voice/last_language", lang)

    @property
    def theme(self) -> str:
        return str(self._qs.value("ui/theme", "dark"))

    @theme.setter
    def theme(self, theme: str) -> None:
        self._qs.setValue("ui/theme", theme)

    @property
    def output_dir(self) -> Path:
        default = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation
        ) or str(Path.home())
        path = Path(str(self._qs.value("io/output_dir", default)))
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            path = Path(default)
        return path

    @output_dir.setter
    def output_dir(self, path: str) -> None:
        self._qs.setValue("io/output_dir", str(path))

    # -------------------------------------------------------------- danger --
    def reset(self) -> None:
        """Clear every preference and the stored key."""
        self._qs.clear()
        self._qs.sync()
        self.delete_api_key()
