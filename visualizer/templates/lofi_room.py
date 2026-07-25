# -*- coding: utf-8 -*-
"""
Design 2 — Cozy Lofi Room  (Lofi study / "1 hour chill mix")

    +----------------------------------------------------------+
    | [CASSETTE] (o)(o)                                        |
    |                  +------------------------+              |
    |                  |   POLAROID CONTAINER   |              |
    |                  |  +------------------+  |              |
    |                  |  |    ALBUM ART     |  |              |
    |                  |  +------------------+  |              |
    |                  |      "Autumn Mix"      |              |
    |                  +------------------------+              |
    |                                                          |
    |          [TRACKLIST]                                     |
    |          1. Sunrise Boulevard (Active)                   |
    |          2. Midnight Study Session                       |
    |          3. Raindrops & Coffee                           |
    |   ~~~~_.~~~.~~~_._~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~    |
    +----------------------------------------------------------+

Warm, low-contrast, slow. No neon, no hard glow — the visualizer is a soft
waveform ribbon along the floor and the motion is a gentle tape wobble.
"""

import math

import numpy as np
from PIL import Image, ImageChops

from .base import (Ctx, LyricStyle, Palette, Template, ease_in_out,
                   lerp_rgb, vertical_gradient)

PALETTE = Palette(
    bg_top=(58, 44, 38),
    bg_bottom=(30, 24, 26),
    primary=(232, 170, 106),       # warm lamp amber
    secondary=(166, 140, 196),     # dusty lilac
    text=(246, 238, 226),
    dim=(163, 146, 132),
    panel=(42, 32, 30),
    panel_alpha=150,
)

POLAROID = (0.365, 0.115, 0.635, 0.520)
TRACKLIST_ORIGIN = (0.100, 0.575)

_LABEL_CACHE = {}


def _font(ctx, scale=0.024):
    from .. import engine as _e
    px = max(10, int(ctx.S(scale)))
    if px not in _LABEL_CACHE:
        _LABEL_CACHE[px] = _e.TextEngine(px, "ABC 0123", None)
    return _LABEL_CACHE[px], px


_GRAIN_CACHE = {}
_GRAIN_PAD = 192


def _grain_field(shape, strength):
    """One oversized noise IMAGE, generated once and slid around per frame.

    Two costs were hiding here. Fresh RNG per frame was ~3.7M ints at 1440p,
    and the numpy round-trip (asarray -> add -> clip -> fromarray) touched 11M
    elements in Python-visible arrays. Caching a uint8 noise image lets the
    per-frame work happen entirely inside PIL's C blend path.
    """
    h, w = shape
    key = (h, w, strength)
    field = _GRAIN_CACHE.get(key)
    if field is None:
        rng = np.random.default_rng(1000)
        arr = rng.integers(0, 2 * strength + 1,
                           (h + _GRAIN_PAD, w + _GRAIN_PAD, 3), dtype=np.uint8)
        field = Image.fromarray(arr, "RGB")
        _GRAIN_CACHE.clear()
        _GRAIN_CACHE[key] = field
    return field


def _paper_grain(ctx: Ctx, strength=6):
    """Film grain — also breaks up banding in the warm gradient."""
    h, w = ctx.h, ctx.w
    field = _grain_field((h, w), strength)
    # Slide the window each frame so the grain crawls like real film.
    ox = (ctx.i * 53) % _GRAIN_PAD
    oy = (ctx.i * 37) % _GRAIN_PAD
    noise = field.crop((ox, oy, ox + w, oy + h))
    # (frame + noise) - strength, clipped, all in C.
    ctx.frame.paste(ImageChops.add(ctx.frame, noise, 1.0, -strength))


def _cassette(ctx: Ctx, pal):
    """Top-left cassette with two reels that turn with the track."""
    x0, y0 = ctx.X(0.055), ctx.Y(0.070)
    w, h = ctx.S(0.190), ctx.S(0.118)
    d = ctx.draw
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=ctx.S(0.010),
                        fill=(48, 38, 34, 235), outline=pal.primary + (120,),
                        width=max(1, int(ctx.S(0.0016))))
    d.rounded_rectangle((x0 + w * 0.10, y0 + h * 0.16,
                         x0 + w * 0.90, y0 + h * 0.56),
                        radius=ctx.S(0.005), fill=(28, 22, 22, 220))
    spin = ctx.t * 2.1
    for k, fx in enumerate((0.30, 0.70)):
        cx, cy = x0 + w * fx, y0 + h * 0.36
        r = h * 0.15
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(214, 200, 180, 240))
        for s in range(3):
            a = spin + s * (2 * math.pi / 3) + k * 0.6
            d.line((cx, cy, cx + math.cos(a) * r * 0.82,
                    cy + math.sin(a) * r * 0.82),
                   fill=(70, 56, 50, 230), width=max(1, int(ctx.S(0.0022))))
    eng, px = _font(ctx, 0.020)
    eng.draw(ctx.frame, (x0 + w * 0.10, y0 + h * 0.86),
             (ctx.artist or "MIXTAPE").upper()[:18], pal.dim + (215,))


def _polaroid(ctx: Ctx, pal):
    """White frame, album art inset, handwritten-ish caption under it."""
    x0, y0, x1, y1 = ctx.rect(POLAROID)
    d = ctx.draw
    tilt = math.sin(ctx.t * 0.5) * 0.004
    y0 += ctx.Y(tilt)
    y1 += ctx.Y(tilt)
    sh = ctx.S(0.012)
    d.rounded_rectangle((x0 + sh, y0 + sh, x1 + sh, y1 + sh),
                        radius=ctx.S(0.006), fill=(0, 0, 0, 90))
    d.rounded_rectangle((x0, y0, x1, y1), radius=ctx.S(0.006),
                        fill=(240, 234, 222, 252))
    pad = (x1 - x0) * 0.070
    ax0, ay0 = x0 + pad, y0 + pad
    side = (x1 - x0) - pad * 2
    if ctx.art is not None:
        art = ctx.art.convert("RGB").resize((int(side), int(side)))
        ctx.frame.paste(art, (int(ax0), int(ay0)))
    else:
        d.rectangle((ax0, ay0, ax0 + side, ay0 + side), fill=(120, 104, 96, 255))
    d.rectangle((ax0, ay0, ax0 + side, ay0 + side),
                outline=(90, 78, 70, 120), width=max(1, int(ctx.S(0.0012))))
    eng, px = _font(ctx, 0.030)
    cap = ctx.title or "Autumn Mix"
    cw = eng.width(cap)
    eng.draw(ctx.frame, ((x0 + x1) / 2 - cw / 2, ay0 + side + px * 1.55),
             cap, (74, 58, 50, 245))


def _tracklist(ctx: Ctx, pal):
    eng, px = _font(ctx, 0.026)
    hx, hy = ctx.X(TRACKLIST_ORIGIN[0]), ctx.Y(TRACKLIST_ORIGIN[1])
    small, spx = _font(ctx, 0.020)
    small.draw(ctx.frame, (hx, hy), "[TRACKLIST]", pal.primary + (215,))
    rows = list(ctx.tracks)[:4] or [(0, "Sunrise Boulevard"),
                                    (0, "Midnight Study Session"),
                                    (0, "Raindrops & Coffee")]
    active = 0
    for idx, (sec, _n) in enumerate(rows):
        if ctx.t >= sec:
            active = idx
    for idx, (_sec, name) in enumerate(rows):
        on = idx == active
        y = hy + px * (1.55 + idx * 1.32)
        col = pal.text[:3] if on else pal.dim
        mark = "•  " if on else "   "
        eng.draw(ctx.frame, (hx, y), f"{mark}{idx + 1}. {name}",
                 col + (240 if on else 165,))


def _waveform_floor(ctx: Ctx, pal):
    """Thin symmetric ribbon along the bottom — the only 'visualizer' here.

    Kept deliberately slight: a filled band this low in the frame turns to mud
    against the warm background and fights the lyric plate above it.
    """
    d = ctx.draw
    mid = ctx.Y(0.947)
    n = 190
    amp = ctx.S(0.026)
    top, bot = [], []
    for k in range(n):
        f = k / (n - 1)
        v = ctx.band(f * 0.8)
        # taper both ends so the ribbon fades out instead of butting the edge
        edge = ease_in_out(min(1.0, f * 5)) * ease_in_out(min(1.0, (1 - f) * 5))
        v = v * (0.20 + 0.80 * edge)
        wob = math.sin(f * 11 + ctx.t * 1.4) * 0.10
        dy = (v + wob * v) * amp
        x = ctx.X(f)
        top.append((x, mid - dy))
        bot.append((x, mid + dy * 0.72))
    d.polygon(top + bot[::-1], fill=pal.primary + (42,))
    d.line(top, fill=pal.primary + (150,), width=max(1, int(ctx.S(0.0014))),
           joint="curve")
    d.line(bot, fill=pal.secondary + (85,), width=max(1, int(ctx.S(0.0011))),
           joint="curve")


def _lamp_glow(ctx: Ctx, pal):
    """Warm vignette from the top-right, like a desk lamp."""
    d = ctx.draw
    cx, cy = ctx.X(0.86), ctx.Y(0.10)
    for k in range(7, 0, -1):
        r = ctx.S(0.10 + k * 0.075)
        d.ellipse((cx - r, cy - r, cx + r, cy + r),
                  fill=pal.primary + (max(1, int(8 - k)),))


def scene(ctx: Ctx):
    pal = PALETTE
    ctx.frame.paste(vertical_gradient((ctx.w, ctx.h), pal.bg_top, pal.bg_bottom))
    _lamp_glow(ctx, pal)
    _cassette(ctx, pal)
    _polaroid(ctx, pal)
    _tracklist(ctx, pal)
    _waveform_floor(ctx, pal)
    _paper_grain(ctx, strength=6)


TEMPLATE = Template(
    key="lofi_room",
    name="Cozy Lofi Room",
    name_km="បន្ទប់ឡូហ្វាយកក់ក្តៅ",
    niche="Lofi study / 1-hour chill mix",
    palette=PALETTE,
    safe_text_box=(0.120, 0.760, 0.880, 0.875),
    portrait_text_box=(0.080, 0.780, 0.920, 0.880),
    scene=scene,
    lyric=LyricStyle(mode="plate", enter="fade", exit="fade",
                     enter_s=0.45, exit_s=0.40, karaoke=False, max_lines=2),
)
