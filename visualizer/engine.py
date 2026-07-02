# -*- coding: utf-8 -*-
"""
Visualizer rendering engine — UI-independent.

Everything that draws pixels or touches audio lives here so the live UI
preview and the final video export share the exact same pipeline:

- audio decoding + spectrum analysis          -> analyze()
- 12 visualizer styles (incl. user "Custom")  -> draw_style()
- overlays: title, subtitles (CapCut-style boxes), progress bar, watermark
- Khmer-aware font loading (bundled Noto Sans Khmer)
- SRT parse/format + optional AI transcription (faster-whisper)
- final MP4 export                            -> render_video()
"""

import bisect
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

SAMPLE_RATE = 44100
FFT_SIZE = 2048
NUM_BARS = 64

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

THEMES = {
    "Neon Purple": ((168, 85, 247), (59, 130, 246)),
    "Cyber Cyan": ((34, 211, 238), (16, 185, 129)),
    "Sunset": ((251, 146, 60), (236, 72, 153)),
    "Emerald": ((52, 211, 153), (250, 204, 21)),
    "Crimson": ((239, 68, 68), (251, 191, 36)),
    "Ocean": ((56, 189, 248), (99, 102, 241)),
    "Pure White": ((245, 245, 245), (160, 160, 160)),
}

# CapCut-style aspect-ratio presets. The UI adds "Original (image)" and
# "Custom…" on top of these.
RESOLUTIONS = {
    "16:9 — YouTube (1920×1080)": (1920, 1080),
    "9:16 — TikTok/Reels (1080×1920)": (1080, 1920),
    "1:1 — Square (1080×1080)": (1080, 1080),
    "4:3 (1440×1080)": (1440, 1080),
    "3:4 (1080×1440)": (1080, 1440),
    "2:1 (1920×960)": (1920, 960),
    "1.85:1 — Cinema (1920×1038)": (1920, 1038),
    "2.35:1 — Cinemascope (1920×816)": (1920, 816),
    "5.8-inch (1080×2340)": (1080, 2340),
    "HD 720p (1280×720)": (1280, 720),
}

RES_ORIGINAL = "Original (image ratio)"
RES_CUSTOM = "Custom…"


def even_size(size):
    """H.264 yuv420p needs even dimensions."""
    return (max(2, int(size[0]) // 2 * 2), max(2, int(size[1]) // 2 * 2))


def size_from_image(image_path, short_side=1080, max_long=2560):
    """Video size matching the dropped image's own aspect ratio."""
    from PIL import Image as _Image
    with _Image.open(image_path) as im:
        w0, h0 = im.size
    scale = short_side / min(w0, h0)
    w, h = w0 * scale, h0 * scale
    if max(w, h) > max_long:
        f = max_long / max(w, h)
        w, h = w * f, h * f
    return even_size((w, h))

TITLE_POSITIONS = [
    "Top Left", "Top Center", "Top Right",
    "Middle Center",
    "Bottom Left", "Bottom Center", "Bottom Right",
]

SUBTITLE_STYLES = ["CapCut Box", "Bold Outline", "Neon Glow"]

DEFAULT_CUSTOM = {
    "element": "Bars",          # Bars | Dots | Line
    "count": 64,                # 24..128
    "thickness": 60,            # % of slot width
    "height": 55,               # % of frame height
    "position": "Bottom",       # Bottom | Center | Top
    "mirror": True,
    "reflection": True,
    "rounded": True,
}

CUSTOM_ELEMENTS = ["Bars", "Dots", "Line"]
CUSTOM_POSITIONS = ["Bottom", "Center", "Top"]


# --------------------------------------------------------------------------
# ffmpeg / audio
# --------------------------------------------------------------------------

def _no_window():
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def load_audio_mono(path):
    cmd = [
        ffmpeg_exe(), "-v", "error", "-i", path,
        "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, creationflags=_no_window())
    if proc.returncode != 0 or len(proc.stdout) < 4:
        raise RuntimeError(
            "Could not decode audio file:\n" + proc.stderr.decode(errors="replace")[-400:]
        )
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


@dataclass
class Analysis:
    samples: np.ndarray
    spectra: np.ndarray      # [num_frames, NUM_BARS] 0..1
    bass: np.ndarray         # [num_frames] 0..1
    phase: np.ndarray        # [num_frames] cumulative beat phase (Pulse Rings)
    fps: int
    num_frames: int
    duration: float


def analyze(audio_path, fps):
    samples = load_audio_mono(audio_path)
    hop = SAMPLE_RATE / fps
    num_frames = max(1, int(math.ceil(len(samples) / hop)))
    window = np.hanning(FFT_SIZE).astype(np.float32)

    freqs = np.fft.rfftfreq(FFT_SIZE, 1.0 / SAMPLE_RATE)
    edges = np.logspace(math.log10(40), math.log10(16000), NUM_BARS + 1)
    bin_idx = np.searchsorted(freqs, edges)

    spectra = np.zeros((num_frames, NUM_BARS), dtype=np.float32)
    padded = np.concatenate([samples, np.zeros(FFT_SIZE, dtype=np.float32)])
    for i in range(num_frames):
        start = int(i * hop)
        chunk = padded[start:start + FFT_SIZE] * window
        mag = np.abs(np.fft.rfft(chunk))
        for b in range(NUM_BARS):
            lo, hi = bin_idx[b], max(bin_idx[b] + 1, bin_idx[b + 1])
            spectra[i, b] = mag[lo:hi].mean()

    spectra = np.log1p(spectra * 10.0)
    peak = np.percentile(spectra, 99.5)
    if peak > 0:
        spectra = np.clip(spectra / peak, 0.0, 1.0) ** 0.75
    for i in range(1, num_frames):
        spectra[i] = np.maximum(spectra[i], spectra[i - 1] * 0.80)

    bass = spectra[:, :6].mean(axis=1)
    phase = np.cumsum(0.006 + 0.05 * bass)
    return Analysis(samples, spectra, bass, phase, fps,
                    num_frames, len(samples) / SAMPLE_RATE)


# --------------------------------------------------------------------------
# Fonts (Khmer-aware, selectable families)
# --------------------------------------------------------------------------

_KHMER_RE = re.compile(r"[ក-៿᧠-᧿]")
_font_cache = {}

# Bundled Khmer font families (all from Google Fonts, SIL OFL license).
# Every family also covers basic Latin, so mixed ខ្មែរ + English text works.
KHMER_FONTS = {
    "Noto Sans Khmer": {"file": "NotoSansKhmer-VF.ttf", "vf": True},
    "Battambang": {"file": "Battambang-Regular.ttf", "bold": "Battambang-Bold.ttf"},
    "Moul (មូល)": {"file": "Moul-Regular.ttf"},
    "Koulen (គូលែន)": {"file": "Koulen-Regular.ttf"},
    "Bokor (បូកគោ)": {"file": "Bokor-Regular.ttf"},
    "Dangrek (ដងរែក)": {"file": "Dangrek-Regular.ttf"},
    "Suwannaphum": {"file": "Suwannaphum-Regular.ttf", "bold": "Suwannaphum-Bold.ttf"},
    "Preahvihear (ព្រះវិហារ)": {"file": "Preahvihear-Regular.ttf"},
    "Fasthand (អក្សរដៃ)": {"file": "Fasthand-Regular.ttf"},
}
KHMER_FONT_NAMES = list(KHMER_FONTS)
DEFAULT_FONT = "Noto Sans Khmer"


def text_has_khmer(text):
    return bool(_KHMER_RE.search(text or ""))


def raqm_available():
    """Raqm is Pillow's complex-script shaping engine. Without it Khmer
    subscripts/vowels come out scrambled — the UI warns about this."""
    try:
        from PIL import features
        return bool(features.check("raqm"))
    except Exception:
        return False


def khmer_support():
    """Diagnose why Khmer text might render wrong on this machine."""
    import PIL
    return {
        "fonts_ok": os.path.exists(os.path.join(FONT_DIR, "NotoSansKhmer-VF.ttf")),
        "raqm_ok": raqm_available(),
        "pillow_version": getattr(PIL, "__version__", "?"),
    }


def _try_font(name, px, bold, vf=False):
    key = (name, px, bold)
    if key in _font_cache:
        return _font_cache[key]
    try:
        try:
            font = ImageFont.truetype(name, px, layout_engine=ImageFont.Layout.RAQM)
        except Exception:
            font = ImageFont.truetype(name, px)
        if vf:
            try:
                font.set_variation_by_name("Bold" if bold else "Regular")
            except Exception:
                pass
        _font_cache[key] = font
        return font
    except Exception:
        return None


def load_font(px, text="", bold=True, family=None):
    """Pick a font that can draw `text` (Khmer + Latin), honoring the
    user-selected Khmer `family` when given."""
    if family in KHMER_FONTS:
        spec = KHMER_FONTS[family]
        fname = spec.get("bold") if (bold and spec.get("bold")) else spec["file"]
        font = _try_font(os.path.join(FONT_DIR, fname), px, bold,
                         vf=spec.get("vf", False))
        if font is not None:
            return font

    khmer = text_has_khmer(text)
    if khmer:
        names = [
            (os.path.join(FONT_DIR, "NotoSansKhmer-VF.ttf"), True),
            ("khmerui.ttf", False), ("khmeruib.ttf", False),   # Windows Khmer UI
            ("leelawui.ttf", False), ("leelauib.ttf", False),  # Leelawadee UI
        ]
    else:
        names = [
            ("arialbd.ttf" if bold else "arial.ttf", False), ("arial.ttf", False),
            ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", False),
            ("DejaVuSans.ttf", False),
            (os.path.join(FONT_DIR, "NotoSansKhmer-VF.ttf"), True),
        ]
    for name, vf in names:
        font = _try_font(name, px, bold, vf)
        if font is not None:
            return font
    return ImageFont.load_default()


def wrap_text(draw, text, font, max_width):
    words = text.split()
    if not words:
        return [text]
    lines, cur = [], words[0]
    for word in words[1:]:
        trial = cur + " " + word
        if draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


# --------------------------------------------------------------------------
# Subtitles: SRT + optional AI transcription
# --------------------------------------------------------------------------

_TIME_RE = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)")


def _parse_time(s):
    m = _TIME_RE.match(s.strip())
    if not m:
        raise ValueError(f"Bad SRT timestamp: {s!r}")
    h, mn, sec, ms = (int(g) for g in m.groups())
    return h * 3600 + mn * 60 + sec + ms / 1000.0


def _fmt_time(t):
    ms = int(round(t * 1000))
    h, rem = divmod(ms, 3600000)
    mn, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{mn:02d}:{s:02d},{ms:03d}"


def parse_srt(text):
    """Parse SRT text -> [(start, end, text), ...]."""
    subs = []
    for block in re.split(r"\n\s*\n", text.strip().replace("\r\n", "\n")):
        lines = [l for l in block.strip().split("\n") if l.strip()]
        if not lines:
            continue
        if "-->" not in lines[0] and len(lines) >= 2 and "-->" in lines[1]:
            lines = lines[1:]  # drop the index line
        if "-->" not in lines[0]:
            continue
        start_s, end_s = lines[0].split("-->")
        content = " ".join(lines[1:]).strip()
        if content:
            subs.append((_parse_time(start_s), _parse_time(end_s), content))
    subs.sort(key=lambda s: s[0])
    return subs


def format_srt(subs):
    out = []
    for i, (start, end, text) in enumerate(subs, 1):
        out.append(f"{i}\n{_fmt_time(start)} --> {_fmt_time(end)}\n{text}\n")
    return "\n".join(out)


def whisper_available():
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def install_whisper(progress_cb=None):
    """Install faster-whisper with pip (Auto Captions one-click setup)."""
    if getattr(sys, "frozen", False):
        raise RuntimeError(
            "This packaged build has no pip. Ask the app developer to "
            "bundle faster-whisper, or use 'Import SRT' instead."
        )
    cmd = [sys.executable, "-m", "pip", "install", "faster-whisper"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, creationflags=_no_window())
    for line in proc.stdout:
        if progress_cb and line.strip():
            progress_cb("Installing AI engine… " + line.strip()[:70])
    if proc.wait() != 0:
        raise RuntimeError(
            "Install failed. Run manually:\n    pip install faster-whisper"
        )


def transcribe(audio_path, language=None, model_size="small", progress_cb=None):
    """Speech-to-text via faster-whisper. Returns [(start, end, text), ...].

    Raises ImportError with install instructions when faster-whisper is
    missing so the UI can show a friendly message.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError(
            "AI subtitles need the faster-whisper package.\n\n"
            "Install it with:\n    pip install faster-whisper\n\n"
            "(The speech model downloads automatically on first use.)"
        )
    if progress_cb:
        progress_cb("Loading speech model…")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    if progress_cb:
        progress_cb("Transcribing audio…")
    segments, info = model.transcribe(
        audio_path, language=language, vad_filter=True, beam_size=5,
    )
    subs = []
    for seg in segments:
        text = seg.text.strip()
        if text:
            subs.append((float(seg.start), float(seg.end), text))
        if progress_cb:
            progress_cb(f"Transcribing… {_fmt_time(seg.end)}")
    return subs


def find_subtitle(subs, t):
    """Active subtitle text at time t, or None. subs sorted by start."""
    if not subs:
        return None
    idx = bisect.bisect_right([s[0] for s in subs], t) - 1
    if idx >= 0 and subs[idx][0] <= t <= subs[idx][1]:
        return subs[idx][2]
    return None


# --------------------------------------------------------------------------
# Backgrounds / assets
# --------------------------------------------------------------------------

def _lerp(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


MAX_ZOOM = 1.10


def build_background(image_path, size, blur, darken, beat_zoom=False):
    """Returns the base background. With beat_zoom, it is pre-enlarged so
    frames can crop a moving window out of it (see zoomed_background)."""
    img = Image.open(image_path).convert("RGB")
    if beat_zoom:
        big = (int(size[0] * MAX_ZOOM), int(size[1] * MAX_ZOOM))
        bg = ImageOps.fit(img, big, Image.LANCZOS)
    else:
        bg = ImageOps.fit(img, size, Image.LANCZOS)
    if blur > 0:
        bg = bg.filter(ImageFilter.GaussianBlur(blur))
    if darken > 0:
        bg = ImageEnhance.Brightness(bg).enhance(1.0 - darken)
    return bg


def zoomed_background(big_bg, size, bass):
    """Crop a bass-pulsing window from the pre-enlarged background."""
    w, h = size
    zoom = 1.0 + (MAX_ZOOM - 1.0) * min(1.0, 0.15 + 0.85 * bass)
    cw, ch = int(w * MAX_ZOOM / zoom), int(h * MAX_ZOOM / zoom)
    cx, cy = big_bg.width // 2, big_bg.height // 2
    box = (cx - cw // 2, cy - ch // 2, cx - cw // 2 + cw, cy - ch // 2 + ch)
    return big_bg.crop(box).resize(size, Image.BILINEAR)


def build_center_art(image_path, size):
    d = int(min(size) * 0.34)
    art = ImageOps.fit(Image.open(image_path).convert("RGB"), (d, d), Image.LANCZOS)
    mask = Image.new("L", (d * 4, d * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, d * 4, d * 4), fill=255)
    art.putalpha(mask.resize((d, d), Image.LANCZOS))
    return art


def build_watermark(logo_path, size, opacity):
    logo = Image.open(logo_path).convert("RGBA")
    target_w = max(24, int(size[0] * 0.12))
    ratio = target_w / logo.width
    logo = logo.resize((target_w, max(1, int(logo.height * ratio))), Image.LANCZOS)
    if opacity < 1.0:
        alpha = logo.getchannel("A").point(lambda a: int(a * opacity))
        logo.putalpha(alpha)
    return logo


# --------------------------------------------------------------------------
# Style drawing — each takes (frame, ctx)
# ctx: v, samples, pos, bass, phase, c1, c2, center_art, custom
# --------------------------------------------------------------------------

def _resample(values, count):
    if count == len(values):
        return values
    x_new = np.linspace(0, len(values) - 1, count)
    return np.interp(x_new, np.arange(len(values)), values)


def _bars_common(frame, values, c1, c2, *, base_frac, max_frac, mirror_up=False,
                 reflection=True, rounded=True, thickness=0.62, centered=False):
    w, h = frame.size
    draw = ImageDraw.Draw(frame, "RGBA")
    n = len(values)
    margin = int(w * 0.06)
    slot = (w - 2 * margin) / n
    bar_w = max(2, int(slot * thickness))
    radius = bar_w // 2 if rounded else 0
    base_y = int(h * base_frac)
    max_h = int(h * max_frac)
    for i, v in enumerate(values):
        x = int(margin + i * slot + (slot - bar_w) / 2)
        bh = max(2, int(v * max_h))
        color = _lerp(c1, c2, i / max(1, n - 1))
        if centered:
            draw.rounded_rectangle((x, base_y - bh // 2, x + bar_w, base_y + bh // 2),
                                   radius=radius, fill=color + (235,))
        else:
            draw.rounded_rectangle((x, base_y - bh, x + bar_w, base_y),
                                   radius=radius, fill=color + (235,))
            if reflection:
                rh = int(bh * 0.28)
                if rh > 2:
                    draw.rounded_rectangle((x, base_y + 6, x + bar_w, base_y + 6 + rh),
                                           radius=radius, fill=color + (60,))
        if mirror_up and not centered:
            draw.rounded_rectangle((x, base_y, x + bar_w, base_y + bh),
                                   radius=radius, fill=color + (120,))


def style_neon_bars(frame, ctx):
    _bars_common(frame, ctx["v"], ctx["c1"], ctx["c2"],
                 base_frac=0.86, max_frac=0.52)


def style_mirror_bars(frame, ctx):
    _bars_common(frame, ctx["v"], ctx["c1"], ctx["c2"],
                 base_frac=0.50, max_frac=0.72, centered=True)


def style_butterfly(frame, ctx):
    w, h = frame.size
    draw = ImageDraw.Draw(frame, "RGBA")
    values = _resample(ctx["v"], 48)
    c1, c2 = ctx["c1"], ctx["c2"]
    n = len(values)
    cx = w // 2
    span = int(w * 0.44)
    slot = span / n
    bar_w = max(2, int(slot * 0.62))
    base_y = int(h * 0.86)
    max_h = int(h * 0.52)
    for i, v in enumerate(values):
        bh = max(2, int(v * max_h))
        color = _lerp(c1, c2, i / max(1, n - 1))
        off = int((i + 0.5) * slot)
        for x in (cx + off - bar_w // 2, cx - off - bar_w // 2):
            draw.rounded_rectangle((x, base_y - bh, x + bar_w, base_y),
                                   radius=bar_w // 2, fill=color + (235,))
            rh = int(bh * 0.25)
            if rh > 2:
                draw.rounded_rectangle((x, base_y + 6, x + bar_w, base_y + 6 + rh),
                                       radius=bar_w // 2, fill=color + (55,))


def style_led_dots(frame, ctx):
    w, h = frame.size
    draw = ImageDraw.Draw(frame, "RGBA")
    values = _resample(ctx["v"], 44)
    c1, c2 = ctx["c1"], ctx["c2"]
    n = len(values)
    rows = 16
    margin = int(w * 0.06)
    slot = (w - 2 * margin) / n
    dot = max(3, int(min(slot * 0.55, h * 0.55 / rows * 0.62)))
    base_y = int(h * 0.86)
    cell_h = int(h * 0.52) / rows
    for i, v in enumerate(values):
        lit = int(round(v * rows))
        x = int(margin + i * slot + (slot - dot) / 2)
        for r in range(rows):
            y = int(base_y - (r + 1) * cell_h + (cell_h - dot) / 2)
            if r < lit:
                color = _lerp(c1, c2, r / max(1, rows - 1)) + (235,)
            else:
                color = (255, 255, 255, 14)
            draw.ellipse((x, y, x + dot, y + dot), fill=color)


def _spectrum_points(frame, values, base_frac=0.80, max_frac=0.45):
    w, h = frame.size
    n = len(values)
    margin = int(w * 0.06)
    span = w - 2 * margin
    base_y = int(h * base_frac)
    max_h = int(h * max_frac)
    return [(margin + int(i * span / (n - 1)), base_y - int(v * max_h))
            for i, v in enumerate(values)], base_y


def style_line_spectrum(frame, ctx):
    draw = ImageDraw.Draw(frame, "RGBA")
    pts, _ = _spectrum_points(frame, _resample(ctx["v"], 48))
    c1, c2 = ctx["c1"], ctx["c2"]
    draw.line(pts, fill=c2 + (90,), width=max(6, frame.height // 130), joint="curve")
    draw.line(pts, fill=c1 + (235,), width=max(3, frame.height // 240), joint="curve")
    r = max(3, frame.height // 200)
    for i, (x, y) in enumerate(pts):
        color = _lerp(c1, c2, i / max(1, len(pts) - 1))
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color + (235,))


def style_area_glow(frame, ctx):
    draw = ImageDraw.Draw(frame, "RGBA")
    pts, base_y = _spectrum_points(frame, _resample(ctx["v"], 56))
    c1, c2 = ctx["c1"], ctx["c2"]
    poly = pts + [(pts[-1][0], base_y), (pts[0][0], base_y)]
    draw.polygon(poly, fill=c2 + (70,))
    mid = [(x, (y + base_y) // 2) for x, y in pts]
    draw.polygon(mid + [(pts[-1][0], base_y), (pts[0][0], base_y)], fill=c1 + (60,))
    draw.line(pts, fill=c1 + (235,), width=max(3, frame.height // 220), joint="curve")


def style_waveform(frame, ctx):
    w, h = frame.size
    draw = ImageDraw.Draw(frame, "RGBA")
    c1, c2 = ctx["c1"], ctx["c2"]
    mid_y = int(h * 0.55)
    amp = int(h * 0.17)
    win = SAMPLE_RATE // 24
    samples, pos = ctx["samples"], ctx["pos"]
    start = max(0, pos - win // 2)
    chunk = samples[start:start + win]
    if len(chunk) < 2:
        chunk = np.zeros(2, dtype=np.float32)
    xs = np.linspace(0, len(chunk) - 1, w).astype(int)
    kernel = np.ones(9, dtype=np.float32) / 9.0
    ys = np.convolve(chunk, kernel, mode="same")[xs]
    ys = np.clip(ys * 2.4, -1.0, 1.0)
    pts = [(x, mid_y - float(y) * amp) for x, y in enumerate(ys)]
    draw.line(pts, fill=c1 + (235,), width=max(3, h // 260), joint="curve")
    draw.line([(x, y + 2) for x, y in pts], fill=c2 + (90,),
              width=max(5, h // 180), joint="curve")


def style_dual_wave(frame, ctx):
    w, h = frame.size
    draw = ImageDraw.Draw(frame, "RGBA")
    c1, c2 = ctx["c1"], ctx["c2"]
    mid_y = int(h * 0.55)
    amp = int(h * 0.20)
    win = SAMPLE_RATE // 8
    samples, pos = ctx["samples"], ctx["pos"]
    start = max(0, pos - win // 2)
    chunk = np.abs(samples[start:start + win])
    if len(chunk) < w:
        chunk = np.pad(chunk, (0, w - len(chunk)))
    cols = w
    k = len(chunk) // cols
    env = chunk[:k * cols].reshape(cols, k).max(axis=1)
    kernel = np.ones(7, dtype=np.float32) / 7.0
    env = np.clip(np.convolve(env, kernel, mode="same") * 2.2, 0.0, 1.0)
    top = [(x, mid_y - float(v) * amp) for x, v in enumerate(env)]
    bottom = [(x, mid_y + float(v) * amp) for x, v in enumerate(env)][::-1]
    draw.polygon(top + bottom, fill=c2 + (80,))
    draw.line(top, fill=c1 + (220,), width=max(2, h // 300), joint="curve")
    draw.line(bottom, fill=c1 + (220,), width=max(2, h // 300), joint="curve")


def _center_art_pulse(frame, draw, ctx, cx, cy):
    art, bass = ctx["center_art"], ctx["bass"]
    if art is None:
        return
    c1, c2 = ctx["c1"], ctx["c2"]
    d = int(art.width * (1.0 + 0.06 * bass))
    scaled = art.resize((d, d), Image.LANCZOS)
    ring = int(d * 1.04)
    draw.ellipse((cx - ring // 2, cy - ring // 2, cx + ring // 2, cy + ring // 2),
                 outline=_lerp(c1, c2, 0.5) + (200,), width=max(3, d // 90))
    frame.paste(scaled, (cx - d // 2, cy - d // 2), scaled)


def style_circular(frame, ctx):
    w, h = frame.size
    cx, cy = w // 2, int(h * 0.46)
    draw = ImageDraw.Draw(frame, "RGBA")
    values, c1, c2 = ctx["v"], ctx["c1"], ctx["c2"]
    n = len(values)
    base_r = int(min(w, h) * 0.20)
    max_len = int(min(w, h) * 0.17)
    for i, v in enumerate(values):
        ang = (i / n) * 2 * math.pi - math.pi / 2
        length = int(4 + v * max_len)
        x1 = cx + math.cos(ang) * (base_r + 6)
        y1 = cy + math.sin(ang) * (base_r + 6)
        x2 = cx + math.cos(ang) * (base_r + 6 + length)
        y2 = cy + math.sin(ang) * (base_r + 6 + length)
        color = _lerp(c1, c2, i / max(1, n - 1))
        draw.line((x1, y1, x2, y2), fill=color + (235,),
                  width=max(3, int(min(w, h) * 0.006)))
    _center_art_pulse(frame, draw, ctx, cx, cy)


def style_circular_wave(frame, ctx):
    w, h = frame.size
    cx, cy = w // 2, int(h * 0.46)
    draw = ImageDraw.Draw(frame, "RGBA")
    c1, c2 = ctx["c1"], ctx["c2"]
    base_r = min(w, h) * 0.24
    amp = min(w, h) * 0.10
    n = 180
    half = _resample(ctx["v"], n // 2)
    values = np.concatenate([half, half[::-1]])  # symmetric loop
    pts = []
    for i in range(n):
        ang = (i / n) * 2 * math.pi - math.pi / 2
        r = base_r + values[i] * amp
        pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
    pts.append(pts[0])
    draw.line(pts, fill=c2 + (90,), width=max(6, int(min(w, h) * 0.012)), joint="curve")
    draw.line(pts, fill=c1 + (235,), width=max(3, int(min(w, h) * 0.005)), joint="curve")
    _center_art_pulse(frame, draw, ctx, cx, cy)


def style_pulse_rings(frame, ctx):
    w, h = frame.size
    cx, cy = w // 2, int(h * 0.46)
    draw = ImageDraw.Draw(frame, "RGBA")
    c1, c2 = ctx["c1"], ctx["c2"]
    max_r = min(w, h) * 0.46
    min_r = min(w, h) * 0.19
    ph = ctx["phase"]
    for k in range(4):
        f = (ph + k / 4.0) % 1.0
        r = min_r + f * (max_r - min_r)
        alpha = int(210 * (1.0 - f) ** 1.5)
        if alpha < 8:
            continue
        color = _lerp(c1, c2, k / 3.0)
        width = max(2, int(min(w, h) * 0.008 * (1.0 - f)) + 2)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r),
                     outline=color + (alpha,), width=width)
    _center_art_pulse(frame, draw, ctx, cx, cy)


def style_custom(frame, ctx):
    cfg = {**DEFAULT_CUSTOM, **(ctx.get("custom") or {})}
    w, h = frame.size
    values = _resample(ctx["v"], int(cfg["count"]))
    c1, c2 = ctx["c1"], ctx["c2"]
    pos = cfg["position"]
    height_frac = max(0.05, min(0.9, cfg["height"] / 100.0))
    thickness = max(0.1, min(1.0, cfg["thickness"] / 100.0))
    centered = cfg["mirror"] and pos == "Center"

    if pos == "Bottom":
        base_frac = 0.86
    elif pos == "Top":
        base_frac = 0.14
    else:
        base_frac = 0.50

    if cfg["element"] == "Bars":
        if pos == "Top" and not centered:
            # bars hang downward: draw mirrored trick via centered=False upside down
            draw = ImageDraw.Draw(frame, "RGBA")
            n = len(values)
            margin = int(w * 0.06)
            slot = (w - 2 * margin) / n
            bar_w = max(2, int(slot * thickness))
            radius = bar_w // 2 if cfg["rounded"] else 0
            base_y = int(h * base_frac)
            max_h = int(h * height_frac)
            for i, v in enumerate(values):
                x = int(margin + i * slot + (slot - bar_w) / 2)
                bh = max(2, int(v * max_h))
                color = _lerp(c1, c2, i / max(1, n - 1))
                draw.rounded_rectangle((x, base_y, x + bar_w, base_y + bh),
                                       radius=radius, fill=color + (235,))
        else:
            _bars_common(frame, values, c1, c2, base_frac=base_frac,
                         max_frac=height_frac, centered=centered,
                         reflection=cfg["reflection"] and pos == "Bottom",
                         rounded=cfg["rounded"], thickness=thickness,
                         mirror_up=cfg["mirror"] and pos == "Bottom")
    elif cfg["element"] == "Dots":
        draw = ImageDraw.Draw(frame, "RGBA")
        n = len(values)
        margin = int(w * 0.06)
        slot = (w - 2 * margin) / n
        r = max(2, int(slot * thickness * 0.5))
        base_y = int(h * base_frac)
        max_h = int(h * height_frac)
        for i, v in enumerate(values):
            x = int(margin + (i + 0.5) * slot)
            off = int(v * max_h) * (1 if pos == "Top" else -1)
            y = base_y + off
            color = _lerp(c1, c2, i / max(1, n - 1))
            draw.ellipse((x - r, y - r, x + r, y + r), fill=color + (235,))
            if cfg["mirror"]:
                y2 = base_y - off
                draw.ellipse((x - r, y2 - r, x + r, y2 + r), fill=color + (110,))
    else:  # Line
        draw = ImageDraw.Draw(frame, "RGBA")
        pts, base_y = _spectrum_points(frame, values, base_frac=base_frac,
                                       max_frac=height_frac)
        if pos == "Top":
            pts = [(x, 2 * base_y - y) for x, y in pts]
        lw = max(2, int(h * 0.006 * thickness * 2))
        draw.line(pts, fill=c2 + (90,), width=lw + 4, joint="curve")
        draw.line(pts, fill=c1 + (235,), width=lw, joint="curve")
        if cfg["mirror"]:
            mirrored = [(x, 2 * base_y - y) for x, y in pts]
            draw.line(mirrored, fill=c1 + (110,), width=lw, joint="curve")


STYLE_FUNCS = {
    "Neon Bars": style_neon_bars,
    "Mirror Bars": style_mirror_bars,
    "Butterfly Bars": style_butterfly,
    "LED Dots": style_led_dots,
    "Line Spectrum": style_line_spectrum,
    "Area Glow": style_area_glow,
    "Waveform": style_waveform,
    "Dual Wave": style_dual_wave,
    "Circular Spectrum": style_circular,
    "Circular Wave": style_circular_wave,
    "Pulse Rings": style_pulse_rings,
    "Custom": style_custom,
}

STYLES = list(STYLE_FUNCS)
NEEDS_CENTER_ART = {"Circular Spectrum", "Circular Wave", "Pulse Rings"}


def draw_style(frame, style, an, i, c1, c2, center_art=None, custom=None):
    hop = SAMPLE_RATE / an.fps
    ctx = {
        "v": an.spectra[i], "samples": an.samples, "pos": int(i * hop),
        "bass": float(an.bass[i]), "phase": float(an.phase[i]),
        "c1": c1, "c2": c2, "center_art": center_art, "custom": custom,
    }
    STYLE_FUNCS.get(style, style_neon_bars)(frame, ctx)


# --------------------------------------------------------------------------
# Overlays
# --------------------------------------------------------------------------

_TITLE_ANCHOR = {
    "Top Left": (0.06, 0.06, "ls"), "Top Center": (0.5, 0.06, "ms"),
    "Top Right": (0.94, 0.06, "rs"), "Middle Center": (0.5, 0.5, "ms"),
    "Bottom Left": (0.06, 0.90, "ls"), "Bottom Center": (0.5, 0.90, "ms"),
    "Bottom Right": (0.94, 0.90, "rs"),
}


def draw_title(frame, text, c1, position="Bottom Center", scale=1.0, family=None):
    if not text:
        return
    w, h = frame.size
    px = max(14, int(h * 0.038 * scale))
    font = load_font(px, text, family=family)
    draw = ImageDraw.Draw(frame, "RGBA")
    fx, fy, align = _TITLE_ANCHOR.get(position, _TITLE_ANCHOR["Bottom Center"])
    tw = draw.textlength(text, font=font)
    asc, desc = font.getmetrics()
    x = int(w * fx - (tw if align == "rs" else tw / 2 if align == "ms" else 0))
    y = int(h * fy - (asc + desc) / 2 + asc) if fy == 0.5 else \
        int(h * fy + asc) if fy < 0.5 else int(h * fy)
    draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 160), anchor="ls")
    draw.text((x, y), text, font=font, fill=(245, 245, 245, 235), anchor="ls")
    pad = int(px * 0.45)
    draw.rounded_rectangle(
        (x - pad, y - asc - pad // 2, x + tw + pad, y + desc + pad // 2),
        radius=max(6, px // 4), outline=c1 + (120,), width=max(2, px // 18),
    )


def draw_subtitle(frame, text, style, c1, c2, family=None):
    if not text:
        return
    w, h = frame.size
    px = max(15, int(h * 0.045))
    font = load_font(px, text, family=family)
    draw = ImageDraw.Draw(frame, "RGBA")
    lines = wrap_text(draw, text, font, int(w * 0.82))
    asc, desc = font.getmetrics()
    line_h = int((asc + desc) * 1.18)
    total_h = line_h * len(lines)
    y0 = int(h * 0.80) - total_h
    stroke = max(2, px // 12)

    if style == "CapCut Box":
        widths = [draw.textlength(l, font=font) for l in lines]
        box_w = max(widths) + px * 1.2
        pad_y = px * 0.45
        bx0 = (w - box_w) / 2
        by0 = y0 - pad_y
        draw.rounded_rectangle(
            (bx0, by0, bx0 + box_w, y0 + total_h + pad_y * 0.6),
            radius=max(8, px // 3), fill=(12, 12, 20, 175),
        )
        draw.rounded_rectangle(
            (bx0, by0, bx0 + box_w, y0 + total_h + pad_y * 0.6),
            radius=max(8, px // 3), outline=c1 + (110,), width=max(2, px // 16),
        )
    for li, line in enumerate(lines):
        lw = draw.textlength(line, font=font)
        x = (w - lw) / 2
        y = y0 + li * line_h + asc
        if style == "Bold Outline":
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 245),
                      stroke_width=stroke, stroke_fill=(0, 0, 0, 230), anchor="ls")
        elif style == "Neon Glow":
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 245),
                      stroke_width=stroke + 1, stroke_fill=c1 + (200,), anchor="ls")
        else:  # CapCut Box
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 245),
                      stroke_width=max(1, stroke // 2), stroke_fill=(0, 0, 0, 140),
                      anchor="ls")


def draw_progress(frame, fraction, c1, c2):
    w, h = frame.size
    draw = ImageDraw.Draw(frame, "RGBA")
    margin = int(w * 0.05)
    y = int(h * 0.965)
    bar_h = max(3, int(h * 0.008))
    draw.rounded_rectangle((margin, y, w - margin, y + bar_h),
                           radius=bar_h // 2, fill=(255, 255, 255, 60))
    fill_w = int((w - 2 * margin) * max(0.0, min(1.0, fraction)))
    if fill_w > bar_h:
        draw.rounded_rectangle((margin, y, margin + fill_w, y + bar_h),
                               radius=bar_h // 2, fill=_lerp(c1, c2, fraction) + (230,))


_WM_POS = {"Top Left": (0.03, 0.03), "Top Right": (0.97, 0.03),
           "Bottom Left": (0.03, 0.93), "Bottom Right": (0.97, 0.93)}


def draw_watermark(frame, logo, corner):
    fx, fy = _WM_POS.get(corner, _WM_POS["Top Right"])
    x = int(frame.width * fx - (logo.width if fx > 0.5 else 0))
    y = int(frame.height * fy - (logo.height if fy > 0.5 else 0))
    frame.paste(logo, (x, y), logo)


# --------------------------------------------------------------------------
# Full frame composition (shared by preview + export)
# --------------------------------------------------------------------------

@dataclass
class FrameAssets:
    an: Analysis
    background: Image.Image          # normal or pre-enlarged (beat_zoom)
    size: tuple
    beat_zoom: bool = False
    center_art: Image.Image = None
    watermark: Image.Image = None


def prepare_assets(image_path, an, size, opts):
    beat_zoom = bool(opts.get("beat_zoom"))
    bg = build_background(image_path, size, opts.get("blur", 0),
                          opts.get("darken", 0), beat_zoom)
    art = None
    if opts.get("style") in NEEDS_CENTER_ART:
        art = build_center_art(image_path, size)
    wm = None
    if opts.get("watermark_path"):
        try:
            wm = build_watermark(opts["watermark_path"], size,
                                 opts.get("watermark_opacity", 0.85))
        except Exception:
            wm = None
    return FrameAssets(an, bg, size, beat_zoom, art, wm)


def compose_frame(assets, i, opts):
    an = assets.an
    c1, c2 = THEMES.get(opts.get("theme", "Neon Purple"), THEMES["Neon Purple"])
    if assets.beat_zoom:
        frame = zoomed_background(assets.background, assets.size, float(an.bass[i]))
    else:
        frame = assets.background.copy()

    draw_style(frame, opts.get("style", "Neon Bars"), an, i, c1, c2,
               assets.center_art, opts.get("custom"))

    if opts.get("show_title") and opts.get("title_text"):
        draw_title(frame, opts["title_text"], c1,
                   opts.get("title_pos", "Bottom Center"),
                   opts.get("title_scale", 1.0),
                   family=opts.get("title_font"))

    if opts.get("show_subs") and opts.get("subtitles"):
        t = i / an.fps
        text = find_subtitle(opts["subtitles"], t)
        if text:
            draw_subtitle(frame, text, opts.get("sub_style", "CapCut Box"), c1, c2,
                          family=opts.get("sub_font"))

    if opts.get("progress_bar"):
        draw_progress(frame, i / max(1, an.num_frames - 1), c1, c2)

    if assets.watermark is not None:
        draw_watermark(frame, assets.watermark,
                       opts.get("watermark_corner", "Top Right"))

    if opts.get("fade"):
        fade_frames = an.fps  # 1 second
        s = min(1.0, (i + 1) / fade_frames, (an.num_frames - i) / fade_frames)
        if s < 1.0:
            frame = ImageEnhance.Brightness(frame).enhance(max(0.0, s))
    return frame


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

def render_video(image_path, audio_path, out_path, opts,
                 progress_cb=None, cancel_event=None):
    fps = int(opts.get("fps", 30))
    size = even_size(opts.get("size", (1920, 1080)))
    an = opts.get("_analysis")
    if an is None or an.fps != fps:
        an = analyze(audio_path, fps)
    assets = prepare_assets(image_path, an, size, opts)

    w, h = size
    cmd = [
        ffmpeg_exe(), "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
        "-r", str(fps), "-i", "-",
        "-i", audio_path,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
    ]
    if opts.get("fade"):
        fade_out = max(0.0, an.duration - 1.0)
        cmd += ["-af", f"afade=t=in:st=0:d=1,afade=t=out:st={fade_out:.2f}:d=1"]
    cmd += ["-shortest", "-movflags", "+faststart", out_path]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=_no_window())
    try:
        for i in range(an.num_frames):
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("cancelled")
            frame = compose_frame(assets, i, opts)
            proc.stdin.write(frame.tobytes())
            if progress_cb and (i % 5 == 0 or i == an.num_frames - 1):
                progress_cb(i + 1, an.num_frames)
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="replace")
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg encoding failed:\n" + err[-400:])
    except BaseException:
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.kill()
        proc.wait()
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except OSError:
                pass
        raise
