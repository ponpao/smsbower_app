"""Bilingual support: English (en) and Khmer / ខ្មែរ (kh).

The UI never hard-codes a visible string. Controls register themselves with
:meth:`Translator.bind`, so switching language just re-applies every registered
label in place — no rebuild, no loss of queue state or scroll position.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Iterable

LOCALES_DIR = Path(__file__).resolve().parent / "locales"

LANGUAGES: dict[str, str] = {
    "en": "English",
    "kh": "ខ្មែរ",
}

DEFAULT_LANGUAGE = "en"


def _load_locale(code: str) -> dict[str, str]:
    path = LOCALES_DIR / f"{code}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): str(v) for k, v in data.items()}


class Translator:
    """Tiny translation table with live re-binding of Flet controls."""

    def __init__(self, language: str = DEFAULT_LANGUAGE) -> None:
        self._tables: dict[str, dict[str, str]] = {code: _load_locale(code) for code in LANGUAGES}
        self.language = language if language in LANGUAGES else DEFAULT_LANGUAGE
        # (control, attribute, key, kwargs) triples re-applied on language change.
        self._bindings: list[tuple[Any, str, str, dict]] = []
        self._callbacks: list[Callable[[], None]] = []

    # -- lookup --------------------------------------------------------------------
    def t(self, key: str, **kwargs: Any) -> str:
        """Translate ``key``; falls back to English, then to the key itself."""
        table = self._tables.get(self.language, {})
        text = table.get(key) or self._tables.get(DEFAULT_LANGUAGE, {}).get(key) or key
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                pass
        return text

    __call__ = t

    def missing_keys(self, keys: Iterable[str]) -> dict[str, list[str]]:
        """Diagnostic helper used by ``tools/check_locales.py``."""
        report: dict[str, list[str]] = {}
        for code, table in self._tables.items():
            missing = sorted(k for k in keys if k not in table)
            if missing:
                report[code] = missing
        return report

    # -- binding -------------------------------------------------------------------
    def bind(self, control: Any, attr: str, key: str, **kwargs: Any) -> Any:
        """Bind ``control.attr`` to a translation key and apply it immediately."""
        self._bindings.append((control, attr, key, kwargs))
        setattr(control, attr, self.t(key, **kwargs))
        return control

    def clear_bindings(self) -> None:
        """Drop every binding and callback.

        Called before the UI is rebuilt (theme switch) so that discarded controls
        are not kept alive by the translator.
        """
        self._bindings.clear()
        self._callbacks.clear()

    def on_change(self, callback: Callable[[], None]) -> None:
        """Register extra work to run after a language switch (e.g. rebuilt lists)."""
        self._callbacks.append(callback)

    def set_language(self, language: str) -> None:
        if language not in LANGUAGES or language == self.language:
            if language in LANGUAGES:
                self.refresh()
            return
        self.language = language
        self.refresh()

    def refresh(self) -> None:
        """Re-apply every bound label plus registered callbacks."""
        for control, attr, key, kwargs in self._bindings:
            try:
                setattr(control, attr, self.t(key, **kwargs))
            except Exception:  # a disposed control must not break the switch
                continue
        for callback in list(self._callbacks):
            try:
                callback()
            except Exception:
                continue
