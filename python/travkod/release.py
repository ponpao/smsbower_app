"""Release Readiness Check.

Validates a finished master against common distributor/streaming requirements and
returns a pass/warn checklist. If the source is flagged AI-generated, it adds a
reminder to DISCLOSE AI use on the chosen distributor.

Honest-design contract: this never tells a user how to "pass" a check or hide AI
use. It surfaces objective facts (loudness, true peak, format) and, where a
release would require disclosure, it prompts disclosure.
"""
from __future__ import annotations

from typing import Dict, List, Optional


def check(meta: Dict, *, lufs_target: Optional[float] = -14.0,
          is_ai: bool = False, has_metadata: bool = True) -> Dict:
    items: List[Dict] = []

    def add(name, status, detail):
        items.append({"name": name, "status": status, "detail": detail})

    # Loudness within a sane streaming window.
    lufs = meta.get("loudness_lufs")
    if lufs is None:
        add("Integrated loudness", "warn", "Could not measure loudness.")
    elif lufs_target is None:
        add("Integrated loudness", "pass", f"{lufs} LUFS (no target set).")
    else:
        delta = abs(lufs - lufs_target)
        if delta <= 1.0:
            add("Integrated loudness", "pass", f"{lufs} LUFS (target {lufs_target}).")
        elif delta <= 2.5:
            add("Integrated loudness", "warn",
                f"{lufs} LUFS is {delta:.1f} LU off target {lufs_target}.")
        else:
            add("Integrated loudness", "warn",
                f"{lufs} LUFS is far from target {lufs_target}; re-master recommended.")

    # True peak must be <= -1 dBTP.
    tp = meta.get("true_peak_dbtp")
    if tp is None:
        add("True peak", "warn", "Could not measure true peak.")
    elif tp <= -1.0:
        add("True peak", "pass", f"{tp} dBTP (<= -1 dBTP).")
    else:
        add("True peak", "warn", f"{tp} dBTP exceeds -1 dBTP ceiling.")

    # Sample rate.
    sr = meta.get("sample_rate")
    if sr and sr >= 44100:
        add("Sample rate", "pass", f"{sr} Hz.")
    else:
        add("Sample rate", "warn", f"{sr} Hz is below 44.1 kHz.")

    # Bit depth.
    bits = meta.get("bit_depth")
    if bits is None:
        add("Bit depth", "warn", "Unknown bit depth (lossy source?).")
    elif bits >= 16:
        add("Bit depth", "pass", f"{bits}-bit.")
    else:
        add("Bit depth", "warn", f"{bits}-bit is below 16-bit.")

    # Channels.
    ch = meta.get("channels")
    if ch in (1, 2):
        add("Channels", "pass", meta.get("channel_label", str(ch)))
    else:
        add("Channels", "warn", f"{ch} channels; most stores expect mono/stereo.")

    # Metadata presence.
    if has_metadata:
        add("Metadata", "pass", "Title/artist metadata present.")
    else:
        add("Metadata", "warn", "Add title, artist and ISRC before release.")

    # AI disclosure reminder (never a bypass — a prompt to disclose).
    if is_ai:
        add("AI disclosure", "warn",
            "This track appears AI-assisted. Disclose AI use where your "
            "distributor requires it (e.g. the AI/GenAI field at upload).")

    warns = sum(1 for i in items if i["status"] == "warn")
    return {
        "items": items,
        "passed": warns == 0,
        "warn_count": warns,
        "summary": ("Ready to release." if warns == 0
                    else f"{warns} item(s) need attention before release."),
    }
