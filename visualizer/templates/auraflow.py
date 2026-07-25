# -*- coding: utf-8 -*-
"""
Design 1 — Cyber-HUD "AURAFLOW"  (Synthwave / Phonk / EDM)

From the design doc:
  Vibe      Retro-futuristic, high-tech HUD overlay.
  Layout    Split. LEFT a frequency oscilloscope. CENTER a spinning vinyl
            carrying the album art, wrapped in a circular neon visualizer.
            RIGHT a frosted glass playlist.
  Bars      Circular neon radial, 64 bands, double-sided.
  Particles Rising vertical neon grids + horizontal glitch dust.

    +----------------------------------------------------------+
    | [AURAFLOW HUD]                              [PLAYLIST]   |
    | +--------------------+  +-------------+  +------------+  |
    | | WebGL Oscilloscope |  |  Circular   |  | Track 01 * |  |
    | |     ~~~~^~~~~      |  | Neon Visual |  | Track 02   |  |
    | |                    |  |  ( ART )    |  | Track 03   |  |
    | +--------------------+  +-------------+  +------------+  |
    |                                                          |
    | [NOW PLAYING] Track 01                                   |
    | [||] [>] [<]  01:45 / 05:30 ----------o----  [X-FADE]    |
    +----------------------------------------------------------+
"""

import math

import numpy as np

from .base import (Ctx, LyricStyle, Palette, Template, circular_bars,
                   glass_panel, glow_dot, grid_floor, lerp_rgb, neon_line,
                   particles_rising, progress_bar, vertical_gradient,
                   vinyl_disc)

PALETTE = Palette(
    bg_top=(12, 6, 34),
    bg_bottom=(38, 8, 58),
    primary=(34, 211, 238),        # cyber cyan
    secondary=(217, 70, 239),      # magenta
    text=(240, 247, 255),
    dim=(128, 138, 170),
    panel=(8, 10, 26),
    panel_alpha=140,
)

# Panels, normalized. Everything below derives from these.
OSC_BOX = (0.045, 0.155, 0.335, 0.470)
PLAYLIST_BOX = (0.680, 0.155, 0.955, 0.470)
CENTER = (0.505, 0.312)
TRANSPORT_BOX = (0.075, 0.905, 0.925, 0.921)


def _hud_corner(ctx, box, palette, label, right=False):
    """Bracket corners + caption, the HUD tell of this template."""
    x0, y0, x1, y1 = ctx.rect(box)
    d = ctx.draw
    arm = ctx.S(0.022)
    lw = max(1, int(ctx.S(0.0018)))
    for cx, cy, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1),
                           (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line((cx, cy, cx + arm * sx, cy), fill=palette.primary + (200,), width=lw)
        d.line((cx, cy, cx, cy + arm * sy), fill=palette.primary + (200,), width=lw)
    te = _label_engine(ctx, palette)
    if te:
        eng, px = te
        tw = eng.width(label)
        lx = (x1 - tw) if right else x0
        eng.draw(ctx.frame, (lx, y0 - px * 0.45), label,
                 palette.primary + (215,))


_LABEL_CACHE = {}


def _label_engine(ctx, palette):
    """Small HUD caption font. Cached per pixel size."""
    from .. import engine as _e
    px = max(9, int(ctx.S(0.021)))
    key = px
    if key not in _LABEL_CACHE:
        _LABEL_CACHE[key] = _e.TextEngine(px, "ABC 0123", None)
    return _LABEL_CACHE[key], px


def _oscilloscope(ctx: Ctx, palette):
    """Linear waveform trace across the left panel."""
    x0, y0, x1, y1 = ctx.rect(OSC_BOX)
    glass_panel(ctx, OSC_BOX, palette, radius_n=0.014)
    mid = (y0 + y1) / 2
    n = 120
    amp = (y1 - y0) * 0.36
    pts = []
    for k in range(n):
        f = k / (n - 1)
        v = ctx.band(f * 0.75)
        wobble = math.sin(f * 14 + ctx.t * 5.0) * 0.35
        pts.append((x0 + (x1 - x0) * f, mid - (v * 1.4 + wobble * v) * amp))
    neon_line(ctx.draw, pts, palette.primary, max(1, ctx.S(0.0022)))
    ctx.draw.line((x0, mid, x1, mid), fill=palette.primary + (45,),
                  width=max(1, int(ctx.S(0.001))))
    _hud_corner(ctx, OSC_BOX, palette, "[ OSCILLOSCOPE ]")


def _playlist(ctx: Ctx, palette):
    """Frosted glass track list on the right."""
    glass_panel(ctx, PLAYLIST_BOX, palette, radius_n=0.014)
    x0, y0, x1, y1 = ctx.rect(PLAYLIST_BOX)
    eng, px = _label_engine(ctx, palette)
    rows = list(ctx.tracks)[:6] or [(0, "Track 01"), (0, "Track 02"),
                                    (0, "Track 03")]
    active = 0
    for idx, (sec, _n) in enumerate(rows):
        if ctx.t >= sec:
            active = idx
    pad = ctx.S(0.016)
    row_h = (y1 - y0 - pad * 2) / max(1, len(rows))
    for idx, (_sec, name) in enumerate(rows):
        ry = y0 + pad + idx * row_h
        on = idx == active
        if on:
            ctx.draw.rounded_rectangle(
                (x0 + pad * 0.5, ry, x1 - pad * 0.5, ry + row_h * 0.86),
                radius=max(3, int(ctx.S(0.006))),
                fill=palette.primary + (42,))
        label = f"{idx + 1:02d}  {name}"
        col = palette.primary if on else palette.dim
        eng.draw(ctx.frame, (x0 + pad * 1.2, ry + row_h * 0.62), label,
                 col + (240 if on else 175,))
    _hud_corner(ctx, PLAYLIST_BOX, palette, "[ PLAYLIST ]", right=True)


def _glitch_dust(ctx: Ctx, palette, count=26):
    """Horizontal glitch streaks, deterministic per frame index."""
    rng = np.random.default_rng(99)
    ys = rng.random(count)
    ph = rng.random(count)
    ln = rng.random(count)
    d = ctx.draw
    for k in range(count):
        x = ((ph[k] + ctx.t * (0.10 + 0.22 * ln[k])) % 1.25) - 0.12
        w = ctx.S(0.012 + 0.05 * ln[k])
        y = ctx.Y(ys[k])
        a = int(30 + 90 * ln[k] * (0.4 + ctx.bass))
        col = palette.primary if k % 2 else palette.secondary
        d.line((ctx.X(x), y, ctx.X(x) + w, y), fill=col + (a,),
               width=max(1, int(ctx.S(0.0012))))


def _transport(ctx: Ctx, palette):
    eng, px = _label_engine(ctx, palette)
    y = ctx.Y(0.862)
    now = ctx.title or "Now Playing"
    eng.draw(ctx.frame, (ctx.X(0.075), y), f"[NOW PLAYING]  {now}",
             palette.text[:3] + (225,))
    if ctx.artist:
        tw = eng.width(ctx.artist)
        eng.draw(ctx.frame, (ctx.X(0.925) - tw, y), ctx.artist,
                 palette.dim + (200,))
    progress_bar(ctx, TRANSPORT_BOX, palette, ctx.progress)
    t_now, t_end = _clock(ctx.t), _clock(ctx.duration)
    eng.draw(ctx.frame, (ctx.X(0.075), ctx.Y(0.958)),
             f"[||] [>] [<]   {t_now} / {t_end}", palette.dim + (195,))
    xf = "[X-FADE]"
    eng.draw(ctx.frame, (ctx.X(0.925) - eng.width(xf), ctx.Y(0.958)), xf,
             palette.secondary + (200,))


def _clock(sec):
    sec = max(0, int(sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def scene(ctx: Ctx):
    pal = PALETTE
    ctx.frame.paste(vertical_gradient((ctx.w, ctx.h), pal.bg_top, pal.bg_bottom))
    grid_floor(ctx, pal, horizon=0.66, lines=13, speed=0.30)
    particles_rising(ctx, pal, count=46, speed=0.055)
    _glitch_dust(ctx, pal)

    _oscilloscope(ctx, pal)
    _playlist(ctx, pal)

    # Centre: spinning vinyl inside a double-sided 64-band neon ring.
    cx, cy = ctx.X(CENTER[0]), ctx.Y(CENTER[1])
    r_disc = ctx.S(0.115)
    rot = ctx.t * 1.35
    ring_in = r_disc * 1.20
    ring_out = r_disc * 1.92
    circular_bars(ctx, (cx, cy), ring_in, ring_out, pal,
                  count=64, double=True, rotate=-rot * 0.25)
    vinyl_disc(ctx, (cx, cy), r_disc, ctx.art, pal, rotation=rot)
    halo = ring_out * (1.0 + 0.05 * ctx.bass)
    ctx.draw.ellipse((cx - halo, cy - halo, cx + halo, cy + halo),
                     outline=pal.primary + (70,),
                     width=max(1, int(ctx.S(0.0018))))
    _transport(ctx, pal)


TEMPLATE = Template(
    key="auraflow",
    name="Cyber-HUD Auraflow",
    name_km="ស៊ីបឺរ-ហ៊ូឌី អូរ៉ាហ្វ្លូ",
    niche="Synthwave / phonk / EDM",
    palette=PALETTE,
    safe_text_box=(0.100, 0.560, 0.900, 0.760),
    portrait_text_box=(0.070, 0.640, 0.930, 0.800),
    scene=scene,
    lyric=LyricStyle(mode="glow", enter="rise", exit="sink",
                     karaoke=True, max_lines=3),
)
