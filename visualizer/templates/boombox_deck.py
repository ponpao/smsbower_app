# -*- coding: utf-8 -*-
"""
Design 5 — VU Boombox Deck  (Retro / oldies collections)

NOTE: the design document supplied wireframes for designs 1-4 only. This
layout is a PROPOSAL built in the same idiom as the other four — swap the
geometry constants below if the intended look differs.

    +----------------------------------------------------------+
    |  ,--------------------------------------------------.    |
    |  |  ( L )  .-'''-.        .-'''-.   ( R )           |    |
    |  |  VU    /   |   \      /   |   \   VU             |    |
    |  |       '--------'     '--------'                  |    |
    |  |   .---------.   +--------------+   .---------.   |    |
    |  |  |  SPEAKER  |  |  CASSETTE /  |  |  SPEAKER  |  |    |
    |  |  |   GRILLE  |  |  ALBUM ART   |  |   GRILLE  |  |    |
    |  |   '---------'   +--------------+   '---------'   |    |
    |  |  [TAPE] A-SIDE   01. Track name        02:15     |    |
    |  '--------------------------------------------------'    |
    +----------------------------------------------------------+

Warm chrome and amber. The two VU needles are ballistic-damped so they swing
like real meters instead of snapping to the FFT.
"""

import math

from .base import (Ctx, LyricStyle, Palette, Template, lerp_rgb,
                   vertical_gradient)

PALETTE = Palette(
    bg_top=(46, 34, 24),
    bg_bottom=(20, 15, 12),
    primary=(251, 191, 36),        # amber
    secondary=(239, 108, 68),      # warm orange
    text=(250, 243, 230),
    dim=(166, 146, 120),
    panel=(34, 26, 20),
    panel_alpha=210,
)

DECK = (0.055, 0.105, 0.945, 0.772)
VU_L = (0.300, 0.290)
VU_R = (0.700, 0.290)
CASSETTE = (0.395, 0.455, 0.605, 0.660)

_LABEL_CACHE = {}
# Needle state is ballistic: it lags the signal, like a real moving coil.
_NEEDLE = {"l": 0.0, "r": 0.0, "i": -1}


def _font(ctx, scale=0.024):
    from .. import engine as _e
    px = max(10, int(ctx.S(scale)))
    if px not in _LABEL_CACHE:
        _LABEL_CACHE[px] = _e.TextEngine(px, "ABC 0123", None)
    return _LABEL_CACHE[px], px


def _needle_levels(ctx: Ctx):
    """Damped needle positions. Deterministic: re-derived if frames rewind."""
    lo = sum(float(ctx.bands[k]) for k in range(0, max(1, len(ctx.bands) // 3)))
    lo /= max(1, len(ctx.bands) // 3)
    hi = sum(float(ctx.bands[k]) for k in
             range(len(ctx.bands) * 2 // 3, len(ctx.bands))) or 0.0
    hi /= max(1, len(ctx.bands) - len(ctx.bands) * 2 // 3)

    if _NEEDLE["i"] != ctx.i - 1:          # seek / first frame -> snap
        _NEEDLE["l"], _NEEDLE["r"] = lo, hi
    else:
        rise, fall = 0.55, 0.12            # fast attack, slow release
        for key, target in (("l", lo), ("r", hi)):
            cur = _NEEDLE[key]
            k = rise if target > cur else fall
            _NEEDLE[key] = cur + (target - cur) * k
    _NEEDLE["i"] = ctx.i
    return _NEEDLE["l"], _NEEDLE["r"]


def _chrome_deck(ctx: Ctx, pal):
    x0, y0, x1, y1 = ctx.rect(DECK)
    d = ctx.draw
    r = ctx.S(0.024)
    d.rounded_rectangle((x0 + ctx.S(0.008), y0 + ctx.S(0.010),
                         x1 + ctx.S(0.008), y1 + ctx.S(0.010)),
                        radius=r, fill=(0, 0, 0, 120))
    d.rounded_rectangle((x0, y0, x1, y1), radius=r, fill=(58, 44, 34, 255))
    d.rounded_rectangle((x0, y0, x1, y1), radius=r,
                        outline=(196, 168, 120, 210),
                        width=max(2, int(ctx.S(0.0026))))
    # brushed highlight along the top lip
    d.rounded_rectangle((x0 + ctx.S(0.012), y0 + ctx.S(0.010),
                         x1 - ctx.S(0.012), y0 + ctx.S(0.034)),
                        radius=ctx.S(0.010), fill=(255, 240, 210, 26))


def _vu_meter(ctx: Ctx, centre_n, level, pal, label):
    cx, cy = ctx.X(centre_n[0]), ctx.Y(centre_n[1])
    r = ctx.S(0.088)
    d = ctx.draw
    # Meter face: a lit cream rectangle, like a real moving-coil window.
    fx0, fy0 = cx - r * 1.10, cy - r * 0.86
    fx1, fy1 = cx + r * 1.10, cy + r * 0.46
    d.rounded_rectangle((fx0 - ctx.S(0.006), fy0 - ctx.S(0.006),
                         fx1 + ctx.S(0.006), fy1 + ctx.S(0.006)),
                        radius=ctx.S(0.008), fill=(28, 22, 16, 255),
                        outline=(150, 126, 88, 200),
                        width=max(1, int(ctx.S(0.0016))))
    d.rounded_rectangle((fx0, fy0, fx1, fy1), radius=ctx.S(0.005),
                        fill=(238, 224, 190, 255))
    # warm backlight pooling at the bottom of the window
    for k in range(5, 0, -1):
        d.rounded_rectangle((fx0, fy1 - (fy1 - fy0) * 0.10 * k, fx1, fy1),
                            radius=ctx.S(0.004),
                            fill=(252, 206, 120, 16))
    # arc scale; the last third is the red zone
    arc_r = r * 0.80
    for k in range(21):
        f = k / 20.0
        a = math.radians(208 + 124 * f)
        major = (k % 5 == 0)
        r0 = arc_r * (0.80 if major else 0.88)
        col = (176, 52, 40) if f > 0.72 else (60, 48, 36)
        d.line((cx + math.cos(a) * r0, cy + math.sin(a) * r0,
                cx + math.cos(a) * arc_r, cy + math.sin(a) * arc_r),
               fill=col + (235,),
               width=max(1, int(ctx.S(0.0022 if major else 0.0012))))
    d.arc((cx - arc_r, cy - arc_r, cx + arc_r, cy + arc_r), 208, 332,
          fill=(88, 72, 54, 200), width=max(1, int(ctx.S(0.0012))))
    d.arc((cx - arc_r, cy - arc_r, cx + arc_r, cy + arc_r), 297, 332,
          fill=(176, 52, 40, 230), width=max(2, int(ctx.S(0.0022))))
    # needle
    a = math.radians(208 + 124 * min(1.0, max(0.0, level)))
    nx, ny = cx + math.cos(a) * r * 0.76, cy + math.sin(a) * r * 0.76
    d.line((cx, cy, nx, ny), fill=(150, 30, 26, 250),
           width=max(2, int(ctx.S(0.0026))))
    hub = ctx.S(0.008)
    d.ellipse((cx - hub, cy - hub, cx + hub, cy + hub), fill=(52, 40, 30, 255))
    eng, px = _font(ctx, 0.018)
    tw = eng.width(label)
    eng.draw(ctx.frame, (cx - tw / 2, cy + r * 0.36), label, (74, 58, 42, 240))
    if level > 0.82:                                  # clip lamp
        lr = ctx.S(0.006)
        lx, ly = cx + r * 0.92, cy - r * 0.62
        d.ellipse((lx - lr, ly - lr, lx + lr, ly + lr),
                  fill=(240, 70, 50, 240))


def _speaker(ctx: Ctx, cx_n, pal):
    cx, cy = ctx.X(cx_n), ctx.Y(0.560)
    r = ctx.S(0.115) * (1.0 + 0.045 * ctx.bass)
    d = ctx.draw
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(26, 20, 16, 255),
              outline=(150, 126, 88, 190), width=max(1, int(ctx.S(0.002))))
    rings = 7
    for k in range(rings):
        rr = r * (0.16 + 0.115 * k)
        a = int(70 - k * 6 + 60 * ctx.bass)
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr),
                  outline=pal.primary + (max(10, a),),
                  width=max(1, int(ctx.S(0.0014))))
    cone = r * 0.20
    d.ellipse((cx - cone, cy - cone, cx + cone, cy + cone),
              fill=(64, 50, 38, 255))


def _cassette_window(ctx: Ctx, pal):
    x0, y0, x1, y1 = ctx.rect(CASSETTE)
    d = ctx.draw
    d.rounded_rectangle((x0, y0, x1, y1), radius=ctx.S(0.010),
                        fill=(22, 18, 14, 255),
                        outline=(168, 142, 100, 220),
                        width=max(1, int(ctx.S(0.002))))
    pad = (x1 - x0) * 0.055
    if ctx.art is not None:
        w_, h_ = int(x1 - x0 - pad * 2), int(y1 - y0 - pad * 2)
        im = ctx.art.convert("RGB").resize((w_, h_))
        ctx.frame.paste(im, (int(x0 + pad), int(y0 + pad)))
    # tape reels turning over the art
    spin = ctx.t * 1.9
    for fx in (0.31, 0.69):
        cx, cy = x0 + (x1 - x0) * fx, y0 + (y1 - y0) * 0.50
        rr = (y1 - y0) * 0.17
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr),
                  fill=(30, 24, 18, 205), outline=(210, 190, 150, 190),
                  width=max(1, int(ctx.S(0.0014))))
        for s in range(3):
            a = spin + s * (2 * math.pi / 3)
            d.line((cx, cy, cx + math.cos(a) * rr * 0.8,
                    cy + math.sin(a) * rr * 0.8),
                   fill=(214, 196, 158, 220),
                   width=max(1, int(ctx.S(0.0018))))
    # glass reflection
    d.polygon([(x0, y1), (x0 + (x1 - x0) * 0.42, y0), (x0 + (x1 - x0) * 0.60, y0),
               (x0, y1 - (y1 - y0) * 0.30)], fill=(255, 255, 255, 14))


def _tape_row(ctx: Ctx, pal):
    eng, px = _font(ctx, 0.024)
    y = ctx.Y(0.716)
    x = ctx.X(0.090)
    eng.draw(ctx.frame, (x, y), "[TAPE]  A-SIDE", pal.primary + (225,))
    rows = list(ctx.tracks) or [(0, ctx.title or "Track 01")]
    active, name = 0, rows[0][1]
    for idx, (sec, n) in enumerate(rows):
        if ctx.t >= sec:
            active, name = idx, n
    eng.draw(ctx.frame, (ctx.X(0.290), y), f"{active + 1:02d}.  {name}",
             pal.text[:3] + (240,))
    clock = f"{int(ctx.t) // 60:02d}:{int(ctx.t) % 60:02d}"
    eng.draw(ctx.frame, (ctx.X(0.905) - eng.width(clock), y), clock,
             pal.dim + (215,))


def scene(ctx: Ctx):
    pal = PALETTE
    ctx.frame.paste(vertical_gradient((ctx.w, ctx.h), pal.bg_top, pal.bg_bottom))
    _chrome_deck(ctx, pal)
    lvl_l, lvl_r = _needle_levels(ctx)
    _vu_meter(ctx, VU_L, lvl_l, pal, "L")
    _vu_meter(ctx, VU_R, lvl_r, pal, "R")
    _speaker(ctx, 0.165, pal)
    _speaker(ctx, 0.835, pal)
    _cassette_window(ctx, pal)
    _tape_row(ctx, pal)


TEMPLATE = Template(
    key="boombox_deck",
    name="VU Boombox Deck",
    name_km="ដិចប៊ូមបុកស៍ VU",
    niche="Retro / oldies collections",
    palette=PALETTE,
    safe_text_box=(0.090, 0.792, 0.910, 0.878),
    portrait_text_box=(0.070, 0.800, 0.930, 0.878),
    scene=scene,
    lyric=LyricStyle(mode="plate", enter="fade", exit="fade",
                     enter_s=0.35, exit_s=0.30, karaoke=False, max_lines=2),
)
