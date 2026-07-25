# -*- coding: utf-8 -*-
"""
Pulse Rail Lyric Studio — shared template foundation
====================================================

Everything the five templates have in common lives here. A template supplies
ONLY:

  * a palette,
  * a normalized safe text box,
  * a scene painter (the visualizer art),
  * entrance/exit animation choices for the lyric layer.

A template never picks a font size, a line count, or a pixel text position.
All of that belongs to the shared lyric layer below, which drives the text
engine in engine.py (fit_text / wrap_text / TextEngine). That is what keeps a
Khmer cue and an English cue inside the same box at every resolution.

Geometry is normalized 0..1 on both axes, so the same template renders at
1080p / 1440p / 2160p and at 16:9 / 9:16 with no per-resolution constants.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

try:                                    # normal package import
    from .. import engine
except ImportError:                     # running the folder directly
    import engine                       # type: ignore


# --------------------------------------------------------------------------
# YouTube safe area
# --------------------------------------------------------------------------
# The player chrome eats the top and bottom of the frame: the title/share
# overlay on hover at the top, the scrubber and control bar at the bottom.
SAFE_TOP = 0.05
SAFE_BOTTOM = 0.12
SAFE_WIDTH = 0.90


def clamp_to_safe_area(box):
    """Clip a normalized (l, t, r, b) box into YouTube's safe area."""
    l, t, r, b = box
    margin = (1.0 - SAFE_WIDTH) / 2.0
    return (max(l, margin), max(t, SAFE_TOP),
            min(r, 1.0 - margin), min(b, 1.0 - SAFE_BOTTOM))


def box_violations(box):
    """Human-readable list of safe-area problems with a normalized box."""
    l, t, r, b = box
    out = []
    margin = (1.0 - SAFE_WIDTH) / 2.0
    if l < margin - 1e-6:
        out.append(f"left edge {l:.3f} inside {margin:.3f} margin")
    if r > 1.0 - margin + 1e-6:
        out.append(f"right edge {r:.3f} past {1.0 - margin:.3f}")
    if t < SAFE_TOP - 1e-6:
        out.append(f"top {t:.3f} inside the {SAFE_TOP:.0%} title overlay")
    if b > 1.0 - SAFE_BOTTOM + 1e-6:
        out.append(f"bottom {b:.3f} under the {SAFE_BOTTOM:.0%} control bar")
    if r <= l or b <= t:
        out.append("box is empty or inverted")
    return out


# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Palette:
    bg_top: tuple
    bg_bottom: tuple
    primary: tuple          # main accent / bar colour
    secondary: tuple        # gradient partner
    text: tuple = (245, 245, 248)
    dim: tuple = (150, 150, 165)
    panel: tuple = (10, 12, 20)
    panel_alpha: int = 150


# --------------------------------------------------------------------------
# Lyric layer configuration
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class LyricStyle:
    """How the shared lyric layer presents a cue for this template.

    Note what is NOT here: font size, line count, x/y pixels. Those are
    derived from the safe box by fit_text at render time.
    """
    mode: str = "outline"        # outline | box | glow | plate
    enter: str = "rise"          # rise | fade | scale | slide_left
    exit: str = "sink"           # sink | fade | scale
    enter_s: float = 0.28        # seconds of entrance animation
    exit_s: float = 0.22
    karaoke: bool = False        # progressive highlight across the cue
    max_lines: int = 3
    align: str = "center"        # center | left
    shadow: bool = True


# --------------------------------------------------------------------------
# Render context
# --------------------------------------------------------------------------

@dataclass
class Ctx:
    """Everything a template needs to paint one frame.

    Frame-indexed, never wall-clock: `i` is the authority and `t` is derived
    from it, so an export is reproducible and never drifts against the audio.
    """
    frame: Image.Image
    w: int
    h: int
    i: int
    fps: int
    duration: float
    bands: np.ndarray                     # NUM_BARS values, 0..1
    bass: float = 0.0
    phase: float = 0.0
    art: Optional[Image.Image] = None     # square album art
    title: str = ""
    artist: str = ""
    tracks: Sequence = field(default_factory=tuple)   # [(seconds, name), ...]
    cue: Optional[tuple] = None           # (start_s, end_s, text)
    font_family: Optional[str] = None
    opts: dict = field(default_factory=dict)

    # -- derived ----------------------------------------------------------
    @property
    def t(self) -> float:
        return self.i / float(self.fps)

    @property
    def progress(self) -> float:
        return min(1.0, self.t / self.duration) if self.duration else 0.0

    @property
    def draw(self) -> ImageDraw.ImageDraw:
        return ImageDraw.Draw(self.frame, "RGBA")

    # -- normalized -> pixels ---------------------------------------------
    def X(self, nx: float) -> float:
        return nx * self.w

    def Y(self, ny: float) -> float:
        return ny * self.h

    def S(self, n: float) -> float:
        """Scale by the short edge — keeps circles round on any aspect."""
        return n * min(self.w, self.h)

    def rect(self, box):
        l, t, r, b = box
        return (l * self.w, t * self.h, r * self.w, b * self.h)

    def band(self, idx_frac: float) -> float:
        """Sample the spectrum at a 0..1 position, safely."""
        if self.bands is None or not len(self.bands):
            return 0.0
        n = len(self.bands)
        return float(self.bands[min(n - 1, max(0, int(idx_frac * n)))])


# --------------------------------------------------------------------------
# Template
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Template:
    key: str
    name: str
    name_km: str
    niche: str
    palette: Palette
    safe_text_box: tuple                 # normalized, landscape
    scene: Callable[[Ctx], None]
    lyric: LyricStyle = field(default_factory=LyricStyle)
    portrait_text_box: Optional[tuple] = None
    needs_art: bool = True

    def text_box(self, w: int, h: int) -> tuple:
        box = self.safe_text_box
        if h > w and self.portrait_text_box:
            box = self.portrait_text_box
        return clamp_to_safe_area(box)


# --------------------------------------------------------------------------
# Easing
# --------------------------------------------------------------------------

def ease_out_cubic(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1.0 - (1.0 - x) ** 3


def ease_in_cubic(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * x


def ease_in_out(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 3 * x * x - 2 * x * x * x


# --------------------------------------------------------------------------
# Paint primitives shared by the templates
# --------------------------------------------------------------------------

def vertical_gradient(size, top, bottom, dither=True):
    """Background gradient. Dithered, because 8-bit neon ramps band badly and
    the encoder cannot recover detail that was never rendered."""
    w, h = size
    ramp = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    col = (np.array(top, dtype=np.float32)[None, :] * (1 - ramp)
           + np.array(bottom, dtype=np.float32)[None, :] * ramp)
    img = np.repeat(col[:, None, :], w, axis=1)
    if dither:
        # +-0.5 LSB of ordered-ish noise breaks up the ramp contours
        rng = np.random.default_rng(1234)
        img = img + rng.random(img.shape, dtype=np.float32) - 0.5
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")


def glass_panel(ctx: Ctx, box, palette: Palette, radius_n=0.018,
                alpha=None, border=True):
    """Frosted-glass panel: blurred backdrop + translucent fill + hairline."""
    x0, y0, x1, y1 = ctx.rect(box)
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    if x1 <= x0 or y1 <= y0:
        return
    radius = max(2, int(ctx.S(radius_n)))

    region = ctx.frame.crop((x0, y0, x1, y1)).filter(
        ImageFilter.GaussianBlur(max(2, int(ctx.S(0.012)))))
    mask = Image.new("L", (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, x1 - x0 - 1, y1 - y0 - 1), radius=radius, fill=255)
    ctx.frame.paste(region, (x0, y0), mask)

    d = ctx.draw
    a = palette.panel_alpha if alpha is None else alpha
    d.rounded_rectangle((x0, y0, x1, y1), radius=radius,
                        fill=palette.panel + (a,))
    if border:
        d.rounded_rectangle((x0, y0, x1, y1), radius=radius,
                            outline=palette.primary + (90,),
                            width=max(1, int(ctx.S(0.0015))))


def neon_line(draw, pts, colour, width, glow=3):
    """Polyline with an additive-looking glow, drawn widest-first."""
    if len(pts) < 2:
        return
    for k in range(glow, 0, -1):
        a = int(40 / k)
        draw.line(pts, fill=colour + (a,), width=int(width * (1 + k * 0.9)),
                  joint="curve")
    draw.line(pts, fill=colour + (240,), width=max(1, int(width)),
              joint="curve")


def glow_dot(draw, xy, r, colour, layers=3):
    x, y = xy
    for k in range(layers, 0, -1):
        rr = r * (1 + k * 0.8)
        draw.ellipse((x - rr, y - rr, x + rr, y + rr),
                     fill=colour + (int(38 / k),))
    draw.ellipse((x - r, y - r, x + r, y + r), fill=colour + (245,))


def circular_bars(ctx: Ctx, centre, r_inner, r_outer, palette,
                  count=64, double=True, rotate=0.0, width_frac=0.55):
    """Radial spectrum ring — the Auraflow / Orbit signature element."""
    cx, cy = centre
    d = ctx.draw
    step = 2 * math.pi / count
    for k in range(count):
        v = ctx.band(k / count)
        ang = k * step + rotate
        length = (r_outer - r_inner) * (0.12 + 0.88 * v)
        x0 = cx + math.cos(ang) * r_inner
        y0 = cy + math.sin(ang) * r_inner
        x1 = cx + math.cos(ang) * (r_inner + length)
        y1 = cy + math.sin(ang) * (r_inner + length)
        mix = k / max(1, count - 1)
        col = lerp_rgb(palette.primary, palette.secondary, mix)
        w = max(1, int(step * r_inner * width_frac))
        d.line((x0, y0, x1, y1), fill=col + (235,), width=w)
        if double:
            xi = cx - math.cos(ang) * (r_inner * 0.62)
            yi = cy - math.sin(ang) * (r_inner * 0.62)
            xj = cx - math.cos(ang) * (r_inner * 0.62 - length * 0.45)
            yj = cy - math.sin(ang) * (r_inner * 0.62 - length * 0.45)
            d.line((xi, yi, xj, yj), fill=col + (110,), width=max(1, w // 2))


def lerp_rgb(a, b, t):
    t = min(1.0, max(0.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def circle_art(art: Image.Image, diameter: int, rotation=0.0):
    """Album art as a round vinyl label, optionally spun."""
    d = max(8, int(diameter))
    im = art.convert("RGB").resize((d, d), Image.LANCZOS)
    if rotation:
        im = im.rotate(-math.degrees(rotation), resample=Image.BICUBIC)
    mask = Image.new("L", (d * 4, d * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, d * 4 - 1, d * 4 - 1), fill=255)
    mask = mask.resize((d, d), Image.LANCZOS)
    out = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def vinyl_disc(ctx: Ctx, centre, radius, art, palette, rotation=0.0):
    """Spinning record carrying the album art on its label."""
    cx, cy = centre
    r = int(radius)
    d = ctx.draw
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(9, 9, 12, 255))
    for k in range(6, 0, -1):
        rr = r * (0.42 + k * 0.093)
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr),
                  outline=(38, 38, 48, 190), width=max(1, int(ctx.S(0.0012))))
    # sheen sweep so the spin reads even on a dark disc
    sheen_a = int(30 + 22 * math.sin(rotation * 2))
    d.pieslice((cx - r, cy - r, cx + r, cy + r),
               math.degrees(rotation) % 360, (math.degrees(rotation) + 55) % 360,
               fill=(255, 255, 255, max(0, sheen_a)))
    if art is not None:
        lab = int(r * 0.62)
        disc = circle_art(art, lab * 2, rotation)
        ctx.frame.paste(disc, (int(cx - lab), int(cy - lab)), disc)
    hole = max(2, int(r * 0.045))
    d.ellipse((cx - hole, cy - hole, cx + hole, cy + hole),
              fill=palette.bg_bottom + (255,))


def progress_bar(ctx: Ctx, box, palette, fraction, show_knob=True):
    x0, y0, x1, y1 = ctx.rect(box)
    d = ctx.draw
    h = max(2, y1 - y0)
    r = h / 2
    d.rounded_rectangle((x0, y0, x1, y1), radius=r, fill=(255, 255, 255, 45))
    fx = x0 + (x1 - x0) * min(1.0, max(0.0, fraction))
    if fx > x0 + 1:
        d.rounded_rectangle((x0, y0, fx, y1), radius=r,
                            fill=palette.primary + (235,))
    if show_knob:
        glow_dot(d, (fx, (y0 + y1) / 2), h * 0.9, palette.secondary, layers=2)


def particles_rising(ctx: Ctx, palette, count=42, seed=7, speed=0.06):
    """Slow vertical drift — deterministic from the frame index."""
    rng = np.random.default_rng(seed)
    xs = rng.random(count)
    phases = rng.random(count)
    sizes = rng.random(count)
    d = ctx.draw
    for k in range(count):
        y = (phases[k] - ctx.t * speed) % 1.0
        r = ctx.S(0.0016 + 0.0032 * sizes[k]) * (0.7 + 0.8 * ctx.bass)
        a = int(70 + 120 * (1.0 - y))
        col = palette.secondary if k % 3 else palette.primary
        cx, cy = ctx.X(xs[k]), ctx.Y(y)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col + (a,))


def grid_floor(ctx: Ctx, palette, horizon=0.62, lines=14, speed=0.35):
    """Synthwave perspective grid below the horizon."""
    d = ctx.draw
    hy = ctx.Y(horizon)
    w, h = ctx.w, ctx.h
    lw = max(1, int(ctx.S(0.0012)))
    for k in range(lines):
        f = ((k / lines) + (ctx.t * speed) % (1.0 / lines))
        if f <= 0 or f > 1:
            continue
        y = hy + (h - hy) * (f ** 2.2)
        a = int(120 * (1 - f) + 25)
        d.line((0, y, w, y), fill=palette.primary + (a,), width=lw)
    for k in range(-9, 10):
        x_bottom = w / 2 + k * (w / 9.0)
        d.line((w / 2, hy, x_bottom, h), fill=palette.primary + (55,), width=lw)


# --------------------------------------------------------------------------
# The shared lyric layer — the ONLY place a cue is measured or positioned
# --------------------------------------------------------------------------

def _cue_animation(style: LyricStyle, cue, t):
    """(alpha 0..1, dx, dy in box-height units) for the current time."""
    start, end, _ = cue
    dur = max(1e-3, end - start)
    since, until = t - start, end - t
    a, dx, dy = 1.0, 0.0, 0.0

    if since < style.enter_s:
        p = ease_out_cubic(since / max(1e-3, style.enter_s))
        a = p
        if style.enter == "rise":
            dy = (1 - p) * 0.55
        elif style.enter == "scale":
            dy = (1 - p) * 0.12
        elif style.enter == "slide_left":
            dx = (1 - p) * -0.35
    elif until < style.exit_s and dur > style.enter_s + style.exit_s:
        p = ease_in_cubic(1.0 - until / max(1e-3, style.exit_s))
        a = 1.0 - p
        if style.exit == "sink":
            dy = p * 0.35
        elif style.exit == "scale":
            dy = p * -0.10
    return max(0.0, min(1.0, a)), dx, dy


def _karaoke_split(te, text, frac):
    """Split `text` at a grapheme-cluster boundary nearest `frac` of its width.

    Advancing by measured prefix width — not by character index — is what
    keeps this correct for Devanagari, where the matra of a cluster renders
    to the LEFT of the consonant it logically follows. The reordering happens
    inside a cluster, so a cluster-boundary prefix is always visually sound.
    """
    if frac <= 0:
        return "", text
    if frac >= 1:
        return text, ""
    clusters = engine.split_clusters(text) if engine.text_is_spaceless(text) \
        else _word_clusters(text)
    total = te.width(text) or 1.0
    target = total * frac
    acc = ""
    for cl in clusters:
        nxt = acc + cl
        if te.width(nxt) > target:
            break
        acc = nxt
    return acc, text[len(acc):]


def _word_clusters(text):
    """Spaced scripts advance word by word, which reads better than letters."""
    out, cur = [], ""
    for ch in text:
        cur += ch
        if ch == " ":
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


def draw_lyrics(ctx: Ctx, tpl: Template):
    """Render the active cue inside the template's safe box.

    Font size and line count come from fit_text against real measured
    metrics, so the same call is correct for Khmer, Thai, Devanagari, Tamil,
    Hangul and Latin, at any output resolution.
    """
    if not ctx.cue:
        return
    start, end, text = ctx.cue
    if not text or not (start <= ctx.t <= end):
        return

    style, pal = tpl.lyric, tpl.palette
    l, t_, r, b = ctx.rect(tpl.text_box(ctx.w, ctx.h))
    box_w, box_h = r - l, b - t_
    if box_w <= 4 or box_h <= 4:
        return

    alpha, dxf, dyf = _cue_animation(style, ctx.cue, ctx.t)
    if alpha <= 0.01:
        return

    te, px, lines = engine.fit_text(
        text, box_w, box_h,
        start_px=int(box_h * 0.52), family=ctx.font_family,
        min_px=max(9, int(box_h * 0.14)), max_lines=style.max_lines)

    lh = int((te.ascent + te.descent) * engine.line_height_for(text))
    block_h = lh * len(lines)
    y = t_ + (box_h - block_h) / 2.0 + dyf * box_h
    A = lambda v: int(max(0, min(255, v * alpha)))          # noqa: E731

    if style.mode in ("box", "plate"):
        widest = max(te.width(x) for x in lines)
        pad = px * 0.55
        bx0 = l + (box_w - widest) / 2 - pad + dxf * box_w
        fill = (pal.panel + (A(pal.panel_alpha),)) if style.mode == "box" \
            else ((12, 12, 18) + (A(120),))
        ctx.draw.rounded_rectangle(
            (bx0, y - pad * 0.55, bx0 + widest + pad * 2, y + block_h + pad * 0.5),
            radius=max(6, int(px * 0.30)), fill=fill,
            outline=pal.primary + (A(110),), width=max(1, int(px / 18)))

    stroke = max(2, int(px / 11))
    frac = ((ctx.t - start) / max(1e-3, end - start)) if style.karaoke else 0.0

    for line in lines:
        lw = te.width(line)
        x = (l + (box_w - lw) / 2.0) if style.align == "center" else l
        x += dxf * box_w
        base = y + te.ascent

        if style.shadow:
            te.draw(ctx.frame, (x + px * 0.045, base + px * 0.05), line,
                    (0, 0, 0, A(150)))

        if style.mode == "outline":
            te.draw(ctx.frame, (x, base), line, pal.text[:3] + (A(250),),
                    stroke_width=stroke, stroke_fill=(0, 0, 0, A(235)))
        elif style.mode == "glow":
            te.draw(ctx.frame, (x, base), line, pal.text[:3] + (A(250),),
                    stroke_width=stroke + 1, stroke_fill=pal.primary + (A(200),))
        else:
            te.draw(ctx.frame, (x, base), line, pal.text[:3] + (A(250),),
                    stroke_width=max(1, stroke // 2),
                    stroke_fill=(0, 0, 0, A(150)))

        if style.karaoke and frac > 0:
            lit, _ = _karaoke_split(te, line, frac)
            if lit:
                te.draw(ctx.frame, (x, base), lit, pal.primary + (A(255),),
                        stroke_width=max(1, stroke // 2),
                        stroke_fill=(0, 0, 0, A(170)))
        y += lh


# --------------------------------------------------------------------------
# Frame entry point
# --------------------------------------------------------------------------

def render_frame(tpl: Template, ctx: Ctx):
    """Paint one frame: scene first, shared lyric layer on top.

    Pure function of ctx.i — no wall clock anywhere, so preview and export
    produce identical pixels for the same frame index.
    """
    tpl.scene(ctx)
    draw_lyrics(ctx, tpl)
    return ctx.frame
