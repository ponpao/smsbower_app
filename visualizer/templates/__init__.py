# -*- coding: utf-8 -*-
"""
Pulse Rail Lyric Studio — template pack
=======================================

Five templates, one shared lyric layer. Nothing here modifies engine.py or
visualizer_tab.py; this package only *reads* the text engine from engine.py
(fit_text / wrap_text / TextEngine) so Khmer, Thai, Devanagari, Tamil, Hangul
and Latin all measure and wrap the same way.

    from visualizer.templates import TEMPLATES, render_frame, Ctx

    ctx = Ctx(frame=img, w=2560, h=1440, i=frame_index, fps=30,
              duration=song_seconds, bands=spectrum_row, bass=0.4,
              art=cover, cue=(start, end, "..."))
    render_frame(TEMPLATES["auraflow"], ctx)

Design rules every template obeys:
  * geometry is normalized 0..1, so 1080p / 1440p / 2160p and 16:9 / 9:16 all
    work from the same numbers;
  * no template picks a font size, line count, or pixel text position;
  * a frame is a pure function of its index — no wall clock, so export is
    reproducible and cannot drift against the audio.
"""

from .base import (Ctx, LyricStyle, Palette, SAFE_BOTTOM, SAFE_TOP,
                   SAFE_WIDTH, Template, box_violations, clamp_to_safe_area,
                   draw_lyrics, render_frame)
from . import auraflow, boombox_deck, lofi_room, orbit_ring, pulse_stage

_MODULES = (auraflow, lofi_room, pulse_stage, orbit_ring, boombox_deck)

#: Ordered registry, keyed by template key. Order matches the design doc.
TEMPLATES = {m.TEMPLATE.key: m.TEMPLATE for m in _MODULES}

#: Display order for a UI picker.
TEMPLATE_KEYS = [m.TEMPLATE.key for m in _MODULES]

#: "Cyber-HUD Auraflow" -> key, for menus that show the human name.
TEMPLATE_NAMES = {m.TEMPLATE.name: m.TEMPLATE.key for m in _MODULES}


def get(key_or_name):
    """Look a template up by key or by display name."""
    if key_or_name in TEMPLATES:
        return TEMPLATES[key_or_name]
    if key_or_name in TEMPLATE_NAMES:
        return TEMPLATES[TEMPLATE_NAMES[key_or_name]]
    raise KeyError(f"unknown template: {key_or_name!r}. "
                   f"Known: {', '.join(TEMPLATE_KEYS)}")


def audit_safe_areas():
    """Report any template whose text box breaks the YouTube safe area.

    Returns {key: [problem, ...]} — empty when everything is clean.
    """
    bad = {}
    for key, tpl in TEMPLATES.items():
        for label, box in (("landscape", tpl.safe_text_box),
                           ("portrait", tpl.portrait_text_box)):
            if box is None:
                continue
            probs = box_violations(box)
            if probs:
                bad.setdefault(key, []).extend(f"{label}: {p}" for p in probs)
    return bad


__all__ = [
    "TEMPLATES", "TEMPLATE_KEYS", "TEMPLATE_NAMES", "get", "audit_safe_areas",
    "render_frame", "draw_lyrics", "Ctx", "Template", "LyricStyle", "Palette",
    "clamp_to_safe_area", "box_violations",
    "SAFE_TOP", "SAFE_BOTTOM", "SAFE_WIDTH",
]
