"""Parameter schema and defaults for the TRAVKOD humanize + master engine.

Every DSP stage is driven from these parameters, which mirror the UI console
one-to-one (mastering strip + 10-band EQ + humanize amount + autotune + LUFS
target). Keeping the schema in one place lets the UI, the orchestrator, and the
Python worker agree on names, ranges and defaults.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


# Center frequencies for the 10-band graphic EQ (Hz).
EQ_BANDS: List[int] = [30, 80, 150, 250, 500, 1000, 2000, 4000, 8000, 12000]


@dataclass
class MasterStrip:
    """The mastering strip. Values are user-facing units.

    dB gains default to 0 (no change); percent-style controls default to 0%.
    """

    bass: float = 0.0        # dB  low shelf ~80 Hz
    deep: float = 0.0        # dB  sub weight ~45 Hz
    mid: float = 0.0         # dB  mid bell ~800 Hz
    clear: float = 0.0       # dB  presence/clarity bell ~3 kHz (gentle)
    treble: float = 0.0      # dB  high shelf ~8 kHz
    presence: float = 0.0    # dB  presence bell ~5 kHz
    low_cut: float = 25.0    # Hz  high-pass corner (20-120)
    gate: float = 0.0        # %   downward expansion depth for noise floor
    de_ess: float = 0.0      # %   sibilance reduction amount (5-9 kHz)
    air: float = 0.0         # %   very-high shelf lift ~14 kHz
    comp: float = 0.0        # %   bus compression amount
    limit: float = 85.0      # %   limiter ceiling engagement / drive
    saturation: float = 0.0  # %   harmonic saturation drive
    reverb: float = 0.0      # %   subtle plate reverb mix
    echo: float = 0.0        # %   slap/echo mix
    width: float = 0.0       # %   stereo width (0 = unchanged, negative = narrow)
    gain: float = 0.0        # dB  output trim (applied pre-limiter)


@dataclass
class Params:
    """Full parameter set handed to the engine for one file."""

    strip: MasterStrip = field(default_factory=MasterStrip)
    eq: List[float] = field(default_factory=lambda: [0.0] * len(EQ_BANDS))  # dB per band

    humanize: float = 35.0   # %  scales wow/flutter depth + micro-dynamics

    # Gentle vocal pitch correction. Off by default (see NON-GOALS: purely a
    # quality tool, never used to fabricate authorship).
    autotune_enabled: bool = False
    autotune_strength: float = 30.0   # % correction toward nearest scale note
    autotune_key: str = "C"
    autotune_scale: str = "major"

    # Mastering loudness target. None => no LUFS normalize ("Off").
    lufs_target: Optional[float] = -14.0     # -14 streaming, -9 loud, or custom
    true_peak_ceiling: float = -1.0          # dBTP hard ceiling for the limiter

    def to_dict(self) -> Dict:
        d = asdict(self)
        return d

    @staticmethod
    def from_dict(d: Optional[Dict]) -> "Params":
        d = d or {}
        strip_d = d.get("strip", {}) or {}
        strip = MasterStrip(**{k: strip_d[k] for k in strip_d if k in MasterStrip().__dict__})
        eq = d.get("eq") or [0.0] * len(EQ_BANDS)
        if len(eq) != len(EQ_BANDS):
            eq = (eq + [0.0] * len(EQ_BANDS))[: len(EQ_BANDS)]
        p = Params(strip=strip, eq=[float(x) for x in eq])
        for k in (
            "humanize", "autotune_enabled", "autotune_strength", "autotune_key",
            "autotune_scale", "lufs_target", "true_peak_ceiling",
        ):
            if k in d and d[k] is not None:
                setattr(p, k, d[k])
        # lufs_target may legitimately be None ("Off"); honor an explicit null.
        if "lufs_target" in d:
            p.lufs_target = d["lufs_target"]
        return p


# Built-in factory templates surfaced in the Template dropdown. Each is a partial
# override applied on top of Params() defaults.
FACTORY_TEMPLATES: Dict[str, Dict] = {
    "Default": {},
    "Warm & Round": {
        "strip": {"bass": 1.5, "deep": 1.0, "saturation": 22, "clear": -1.5,
                   "de_ess": 20, "air": 8, "comp": 25, "width": 8},
        "humanize": 45,
    },
    "Vocal Focus": {
        "strip": {"mid": 1.0, "presence": 1.5, "clear": 1.0, "de_ess": 35,
                   "comp": 30, "air": 12, "low_cut": 60},
        "humanize": 30,
    },
    "AI De-Harsh": {
        "strip": {"clear": -2.5, "presence": -1.5, "de_ess": 40, "saturation": 30,
                   "air": 6, "comp": 20, "treble": -1.0},
        "humanize": 55,
    },
    "Bright": {
        "strip": {"treble": 2.0, "air": 25, "presence": 1.5, "clear": 1.0},
        "humanize": 20,
    },
    "Warm": {
        "strip": {"bass": 2.0, "saturation": 28, "treble": -1.5, "clear": -1.5, "air": 4},
        "humanize": 50,
    },
    "Hip-Hop": {
        "strip": {"deep": 2.5, "bass": 1.5, "saturation": 18, "comp": 35, "width": 5},
        "humanize": 25, "lufs_target": -9.0,
    },
    "Pop": {
        "strip": {"presence": 1.5, "air": 18, "comp": 32, "width": 10, "de_ess": 25},
        "humanize": 30,
    },
    "R&B": {
        "strip": {"bass": 1.5, "deep": 1.0, "mid": 0.5, "saturation": 20, "air": 10,
                   "comp": 28, "width": 8},
        "humanize": 40,
    },
    "Rock": {
        "strip": {"mid": 1.5, "comp": 30, "saturation": 25, "presence": 1.0, "width": 6},
        "humanize": 35,
    },
    "Lo-Fi": {
        "strip": {"treble": -3.0, "air": -10, "saturation": 40, "bass": 1.0, "width": -5},
        "humanize": 80,
    },
}
