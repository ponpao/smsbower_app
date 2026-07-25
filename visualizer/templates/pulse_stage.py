# -*- coding: utf-8 -*-
"""
Design 3 — EDM Pulse Stage  (Single-track hype / NCS-style)

    +----------------------------------------------------------+
    |  +------------------+   [NOW PLAYING HUD]                |
    |  |                  |   Artist: Hyperion                 |
    |  |    ALBUM ART     |   Track:  Digital Horizon          |
    |  |    (PULSING)     |   Tempo:  140 BPM                  |
    |  |                  |   Time:   02:15 / 04:30            |
    |  +------------------+   +--------------------------+     |
    |                         |==================>       |     |
    |  |||  ||||  |||||  ||||||  |||||  ||||  |||  ||||||       |
    +----------------------------------------------------------+

Hard, bright, beat-locked. The art scales on bass, the stage lights sweep on
the beat, and a wide mirrored bar spectrum fills the lower third.
"""

import math

from .base import (Ctx, LyricStyle, Palette, Template, ease_out_cubic,
                   glow_dot, lerp_rgb, progress_bar, vertical_gradient)

PALETTE = Palette(
    bg_top=(6, 10, 30),
    bg_bottom=(2, 4, 12),
    primary=(56, 189, 248),        # electric blue
    secondary=(244, 63, 94),       # hot red
    text=(255, 255, 255),
    dim=(130, 148, 178),
    panel=(8, 14, 32),
    panel_alpha=125,
)

ART_BOX = (0.060, 0.150, 0.400, 0.545)
HUD_ORIGIN = (0.455, 0.190)
HUD_BAR = (0.455, 0.470, 0.930, 0.492)

_LABEL_CACHE = {}


def _font(ctx, scale=0.026):
    from .. import engine as _e
    px = max(10, int(ctx.S(scale)))
    if px not in _LABEL_CACHE:
        _LABEL_CACHE[px] = _e.TextEngine(px, "ABC 0123", None)
    return _LABEL_CACHE[px], px


def _stage_lights(ctx: Ctx, pal):
    """Two sweeping beams from above, locked to the beat phase."""
    d = ctx.draw
    for k, (ox, col, sign) in enumerate(
            ((0.28, pal.primary, 1.0), (0.72, pal.secondary, -1.0))):
        a = math.sin(ctx.phase * 0.9 + k * 1.7) * 0.30 * sign
        apex = (ctx.X(ox), ctx.Y(-0.05))
        spread = ctx.S(0.16) * (0.65 + 0.6 * ctx.bass)
        base_y = ctx.Y(0.72)
        bx = ctx.X(ox + a)
        d.polygon([apex, (bx - spread, base_y), (bx + spread, base_y)],
                  fill=col + (int(16 + 26 * ctx.bass),))


def _album(ctx: Ctx, pal):
    """Album art that pulses with the bass, ringed in accent."""
    x0, y0, x1, y1 = ctx.rect(ART_BOX)
    side = min(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    grow = 1.0 + 0.075 * ctx.bass
    s = side * grow
    d = ctx.draw
    for k in range(4, 0, -1):
        pad = s * 0.5 + ctx.S(0.006) * k * (1 + ctx.bass)
        d.rounded_rectangle((cx - pad, cy - pad, cx + pad, cy + pad),
                            radius=ctx.S(0.016),
                            outline=pal.primary + (int(60 / k),),
                            width=max(1, int(ctx.S(0.0022))))
    if ctx.art is not None:
        im = ctx.art.convert("RGB").resize((int(s), int(s)))
        ctx.frame.paste(im, (int(cx - s / 2), int(cy - s / 2)))
    else:
        d.rectangle((cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2),
                    fill=(24, 30, 52, 255))
    d.rounded_rectangle((cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2),
                        radius=ctx.S(0.010),
                        outline=pal.primary + (200,),
                        width=max(2, int(ctx.S(0.0028))))


def _hud(ctx: Ctx, pal):
    eng, px = _font(ctx, 0.027)
    small, spx = _font(ctx, 0.021)
    x = ctx.X(HUD_ORIGIN[0])
    y = ctx.Y(HUD_ORIGIN[1])
    small.draw(ctx.frame, (x, y), "[ NOW PLAYING ]", pal.primary + (225,))
    bpm = int(ctx.opts.get("bpm") or 0)
    rows = [("Artist", ctx.artist or "—"),
            ("Track", ctx.title or "—"),
            ("Tempo", f"{bpm} BPM" if bpm else "—"),
            ("Time", f"{_clock(ctx.t)} / {_clock(ctx.duration)}")]
    for idx, (k, v) in enumerate(rows):
        ry = y + px * (1.55 + idx * 1.30)
        eng.draw(ctx.frame, (x, ry), f"{k}:", pal.dim + (205,))
        eng.draw(ctx.frame, (x + ctx.S(0.115), ry), v, pal.text[:3] + (245,))
    progress_bar(ctx, HUD_BAR, pal, ctx.progress)


def _clock(sec):
    sec = max(0, int(sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def _bars(ctx: Ctx, pal):
    """Wide mirrored spectrum across the lower third."""
    d = ctx.draw
    n = 56
    left, right = ctx.X(0.045), ctx.X(0.955)
    base = ctx.Y(0.905)
    slot = (right - left) / n
    bw = slot * 0.62
    max_h = ctx.S(0.170)
    for k in range(n):
        v = ctx.band(k / n)
        hgt = max(ctx.S(0.004), v * max_h)
        x = left + k * slot + (slot - bw) / 2
        col = lerp_rgb(pal.primary, pal.secondary, k / (n - 1))
        d.rounded_rectangle((x, base - hgt, x + bw, base),
                            radius=bw * 0.35, fill=col + (240,))
        # reflection
        d.rounded_rectangle((x, base + ctx.S(0.004),
                             x + bw, base + ctx.S(0.004) + hgt * 0.40),
                            radius=bw * 0.35, fill=col + (60,))
        if v > 0.72:
            glow_dot(d, (x + bw / 2, base - hgt - ctx.S(0.008)),
                     bw * 0.30, col, layers=2)


def scene(ctx: Ctx):
    pal = PALETTE
    ctx.frame.paste(vertical_gradient((ctx.w, ctx.h), pal.bg_top, pal.bg_bottom))
    _stage_lights(ctx, pal)
    _album(ctx, pal)
    _hud(ctx, pal)
    _bars(ctx, pal)


TEMPLATE = Template(
    key="pulse_stage",
    name="EDM Pulse Stage",
    name_km="ឆាកអ៊ីឌីអឹម ផាល់",
    niche="Single-track hype / NCS style",
    palette=PALETTE,
    safe_text_box=(0.060, 0.600, 0.940, 0.740),
    portrait_text_box=(0.060, 0.620, 0.940, 0.780),
    scene=scene,
    lyric=LyricStyle(mode="outline", enter="scale", exit="fade",
                     enter_s=0.18, exit_s=0.16, karaoke=True, max_lines=2),
)
