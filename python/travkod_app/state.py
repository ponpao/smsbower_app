"""UI-side state: control definitions, export settings, and preset persistence.

The actual DSP parameter schema lives in ``travkod.params`` (shared with the
engine). This module holds the UI's mutable copy plus the slider metadata and a
small JSON preset store under the user config dir.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional

from travkod.params import Params, MasterStrip, EQ_BANDS


# (key, label, unit, min, max, step, is_float)
STRIP_CONTROLS = [
    ("bass", "Bass", "dB", -12, 12, 0.5, True),
    ("deep", "Deep", "dB", -12, 12, 0.5, True),
    ("mid", "Mid", "dB", -12, 12, 0.5, True),
    ("clear", "Clear", "dB", -12, 12, 0.5, True),
    ("treble", "Treble", "dB", -12, 12, 0.5, True),
    ("presence", "Pres", "dB", -12, 12, 0.5, True),
    ("low_cut", "LCut", "Hz", 20, 120, 1, False),
    ("gate", "Gate", "%", 0, 100, 1, False),
    ("de_ess", "DeEss", "%", 0, 100, 1, False),
    ("air", "Air", "%", 0, 100, 1, False),
    ("comp", "Comp", "%", 0, 100, 1, False),
    ("limit", "Limit", "%", 0, 100, 1, False),
    ("saturation", "Sat", "%", 0, 100, 1, False),
    ("reverb", "Verb", "%", 0, 100, 1, False),
    ("echo", "Echo", "%", 0, 100, 1, False),
    ("width", "Width", "%", -100, 100, 1, False),
    ("gain", "Gain", "dB", -12, 12, 0.5, True),
]

EQ_LABELS = ["30", "80", "150", "250", "500", "1k", "2k", "4k", "8k", "12k"]

QUICK_EQ = {
    "Flat": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "Vocal": [0, 0, -1, 0, 1, 2, 2, 1, 1, 0],
    "Bass+": [3, 3, 2, 1, 0, 0, 0, 0, 0, 0],
    "Bright": [0, 0, 0, 0, 0, 0, 1, 2, 3, 3],
    "Warm": [2, 2, 1, 0, 0, -1, -1, -2, -2, -1],
    "AI Tame": [0, 0, 0, 0, -1, -2, -2, -1, 0, 1],
    "Hip-Hop": [3, 2, 1, 0, -1, 0, 1, 1, 1, 1],
    "Pop": [1, 1, 0, 0, 0, 1, 1, 2, 2, 1],
    "R&B": [2, 2, 1, 0, 0, 0, 0, 1, 1, 0],
    "Rock": [1, 1, 1, 1, 1, 1, 1, 1, 0, 0],
    "Lo-Fi": [2, 1, 0, 0, -1, -2, -3, -4, -5, -6],
}


@dataclass
class ExportSettings:
    format: str = "wav"
    sample_rate: Optional[int] = None       # None = keep source
    bit_depth: int = 24
    mp3_bitrate: int = 320
    threads: int = 4                         # 1..8
    autotune: bool = False
    merge: bool = False
    lufs_target: Optional[float] = -14.0
    output_folder: Optional[str] = None


@dataclass
class QueueItem:
    id: str
    path: str
    filename: str
    status: str = "Idle"        # Idle/Queued/Processing/Done/Error/Paused
    progress: float = 0.0
    stage: str = ""
    meta: Optional[dict] = None
    error: Optional[str] = None
    output_path: Optional[str] = None
    is_ai: bool = False


@dataclass
class AppState:
    params: Params = field(default_factory=Params)
    export: ExportSettings = field(default_factory=ExportSettings)
    humanize_on: bool = True
    auto_intensity: bool = True
    template: str = "Default"


def config_dir() -> str:
    if os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif os.sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    d = os.path.join(base, "TRAVKOD")
    os.makedirs(d, exist_ok=True)
    return d


def default_output_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), "TRAVKOD Exports")
    os.makedirs(d, exist_ok=True)
    return d


class PresetStore:
    """User presets persisted as JSON next to the config dir."""

    def __init__(self):
        self.path = os.path.join(config_dir(), "presets.json")

    def load(self) -> List[dict]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def save(self, name: str, params: Params) -> List[dict]:
        items = self.load()
        entry = {"name": name, "params": params.to_dict()}
        for i, p in enumerate(items):
            if p.get("name") == name:
                items[i] = entry
                break
        else:
            items.append(entry)
        self._write(items)
        return items

    def delete(self, name: str) -> List[dict]:
        items = [p for p in self.load() if p.get("name") != name]
        self._write(items)
        return items

    def _write(self, items):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2)


class SettingsStore:
    """Remembers first-run acknowledgement and the last output folder."""

    def __init__(self):
        self.path = os.path.join(config_dir(), "settings.json")

    def load(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def set(self, key, value):
        d = self.load()
        d[key] = value
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
