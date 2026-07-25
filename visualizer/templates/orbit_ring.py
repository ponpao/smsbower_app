# -*- coding: utf-8 -*-
"""
Design 4 — NCS Orbit Ring  (Playlist / collection videos)

    +----------------------------------------------------------+
    | [TRACKLIST]                                              |
    | 01. Skyline Drive                    ,-''''-.            |
    | >> 02. Horizon Pulse (Playing)     .'   __   '.          |
    | 03. Oceanic Echo                  /   /[  ]\   \         |
    | 04. Zenith Heights                |  | [ART] |  |        |
    | 05. Aurora Gliss                   \  \[__]/  /          |
    |                                     '.      .'           |
    |                                       '-....-'           |
    | [==========================================] 45%         |
    +----------------------------------------------------------+

Built for long playlists: the tracklist is the primary element and the orbit
ring on the right carries the art. Orbiting satellites mark the beat so a
60-minute upload never looks static.
"""

import math

from .base import (Ctx, LyricStyle, Palette, Template, circle_art,
                   circular_bars, glow_dot, lerp_rgb, progress_bar,
                   particles_rising, vertical_gradient)

PALETTE = Palette(
    bg_top=(10, 14, 40),
    bg_bottom=(4, 6, 18),
    primary=(129, 140, 248),       # indigo
    secondary=(45, 212, 191),      # teal
    text=(238, 242, 255),
    dim=(124, 136, 168),
    panel=(10, 14, 34),
    panel_alpha=120,
)

TRACK_ORIGIN = (0.060, 0.170)
ORBIT_CENTRE = (0.740, 0.400)
PROGRESS = (0.060, 0.905, 0.885, 0.923)

_LABEL_CACHE = {}


def _font(ctx, scale=0.027):
    from .. import engine as _e
    px = max(10, int(ctx.S(scale)))
    if px not in _LABEL_CACHE:
        _LABEL_CACHE[px] = _e.TextEngine(px, "ABC 0123", None)
    return _LABEL_CACHE[px], px


def _tracklist(ctx: Ctx, pal):
    eng, px = _font(ctx, 0.027)
    small, spx = _font(ctx, 0.021)
    x, y = ctx.X(TRACK_ORIGIN[0]), ctx.Y(TRACK_ORIGIN[1])
    small.draw(ctx.frame, (x, y), "[ TRACKLIST ]", pal.secondary + (220,))

    rows = list(ctx.tracks)[:7] or [
        (0, "Skyline Drive"), (0, "Horizon Pulse"), (0, "Oceanic Echo"),
        (0, "Zenith Heights"), (0, "Aurora Gliss")]
    active = 0
    for idx, (sec, _n) in enumerate(rows):
        if ctx.t >= sec:
            active = idx

    for idx, (_sec, name) in enumerate(rows):
        on = idx == active
        ry = y + px * (1.75 + idx * 1.42)
        if on:
            pulse = 0.5 + 0.5 * math.sin(ctx.t * 3.0)
            ctx.draw.rounded_rectangle(
                (x - px * 0.45, ry - px * 0.92,
                 x + ctx.S(0.400), ry + px * 0.34),
                radius=px * 0.30,
                fill=pal.primary + (int(30 + 22 * pulse),))
            eng.draw(ctx.frame, (x - px * 0.10, ry), ">>",
                     pal.secondary + (245,))
        label = f"{idx + 1:02d}.  {name}"
        eng.draw(ctx.frame, (x + px * 1.35, ry), label,
                 (pal.text[:3] if on else pal.dim) + (245 if on else 170,))
        if on:
            tw = eng.width(label)
            eng.draw(ctx.frame, (x + px * 1.35 + tw + px * 0.6, ry),
                     "(Playing)", pal.secondary + (200,))


def _orbit(ctx: Ctx, pal):
    cx, cy = ctx.X(ORBIT_CENTRE[0]), ctx.Y(ORBIT_CENTRE[1])
    r_art = ctx.S(0.098)
    d = ctx.draw

    # dotted outer orbit
    r_orbit = r_art * 2.05
    dots = 96
    for k in range(dots):
        a = 2 * math.pi * k / dots + ctx.t * 0.12
        rr = max(1, ctx.S(0.0022))
        px_ = cx + math.cos(a) * r_orbit
        py_ = cy + math.sin(a) * r_orbit
        d.ellipse((px_ - rr, py_ - rr, px_ + rr, py_ + rr),
                  fill=pal.primary + (110,))

    circular_bars(ctx, (cx, cy), r_art * 1.22, r_art * 1.92, pal,
                  count=64, double=False, rotate=ctx.t * 0.20, width_frac=0.44)

    # album art disc
    if ctx.art is not None:
        disc = circle_art(ctx.art, int(r_art * 2))
        ctx.frame.paste(disc, (int(cx - r_art), int(cy - r_art)), disc)
    else:
        d.ellipse((cx - r_art, cy - r_art, cx + r_art, cy + r_art),
                  fill=(20, 26, 56, 255))
    d.ellipse((cx - r_art, cy - r_art, cx + r_art, cy + r_art),
              outline=pal.secondary + (200,), width=max(2, int(ctx.S(0.0026))))

    # beat satellites
    for k in range(3):
        a = ctx.t * (0.55 + k * 0.22) + k * 2.09
        rr = r_orbit * (1.0 + 0.05 * math.sin(ctx.t * 1.3 + k))
        sx, sy = cx + math.cos(a) * rr, cy + math.sin(a) * rr
        glow_dot(d, (sx, sy), ctx.S(0.005) * (1 + 0.7 * ctx.bass),
                 pal.secondary if k % 2 else pal.primary)


def _progress(ctx: Ctx, pal):
    progress_bar(ctx, PROGRESS, pal, ctx.progress)
    eng, px = _font(ctx, 0.023)
    pct = f"{int(ctx.progress * 100)}%"
    eng.draw(ctx.frame, (ctx.X(0.900), ctx.Y(0.923)), pct,
             pal.text[:3] + (225,))


def scene(ctx: Ctx):
    pal = PALETTE
    ctx.frame.paste(vertical_gradient((ctx.w, ctx.h), pal.bg_top, pal.bg_bottom))
    particles_rising(ctx, pal, count=34, seed=21, speed=0.035)
    _tracklist(ctx, pal)
    _orbit(ctx, pal)
    _progress(ctx, pal)


TEMPLATE = Template(
    key="orbit_ring",
    name="NCS Orbit Ring",
    name_km="រង្វង់គន្លង NCS",
    niche="Playlist / collection videos",
    palette=PALETTE,
    safe_text_box=(0.060, 0.735, 0.940, 0.865),
    portrait_text_box=(0.060, 0.700, 0.940, 0.850),
    scene=scene,
    lyric=LyricStyle(mode="box", enter="slide_left", exit="fade",
                     enter_s=0.30, exit_s=0.22, karaoke=False, max_lines=2),
)
