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
import concurrent.futures
import math
import multiprocessing
import os
import re
import subprocess
import sys
import traceback
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


def load_audio_mono(path_or_paths):
    if isinstance(path_or_paths, (list, tuple)):
        paths = path_or_paths
    else:
        paths = [path_or_paths]
    
    arrays = []
    for path in paths:
        cmd = [
            ffmpeg_exe(), "-v", "error", "-i", path,
            "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-",
        ]
        proc = subprocess.run(cmd, capture_output=True, creationflags=_no_window())
        if proc.returncode != 0 or len(proc.stdout) < 4:
            raise RuntimeError(
                f"Could not decode audio file '{path}':\n" + proc.stderr.decode(errors="replace")[-400:]
            )
        arr = np.frombuffer(proc.stdout, dtype=np.float32).copy()
        arrays.append(arr)
        
    if not arrays:
        raise RuntimeError("No audio paths provided.")
    return np.concatenate(arrays)


def get_audio_duration(path):
    cmd = [ffmpeg_exe(), "-i", path]
    proc = subprocess.run(cmd, capture_output=True, creationflags=_no_window())
    stderr = proc.stderr.decode(errors="replace") if proc.stderr else ""
    import re
    m = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.\d+)', stderr)
    if m:
        h = int(m.group(1))
        m_val = int(m.group(2))
        s = float(m.group(3))
        return h * 3600 + m_val * 60 + s
    # Fallback: decode and calculate
    try:
        arr = load_audio_mono(path)
        return len(arr) / SAMPLE_RATE
    except Exception:
        return 0.0


def build_track_timeline(audio_paths):
    timeline = []
    current_time = 0.0
    for path in audio_paths:
        dur = get_audio_duration(path)
        title = os.path.splitext(os.path.basename(path))[0]
        timeline.append((current_time, title))
        current_time += dur
    return timeline


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


def khmer_shaper_available():
    """Our own HarfBuzz+FreeType Khmer shaper — works on ANY Pillow build."""
    try:
        import uharfbuzz  # noqa: F401
        import freetype   # noqa: F401
        return True
    except ImportError:
        return False


def khmer_support():
    """Diagnose why Khmer text might render wrong on this machine."""
    import PIL
    return {
        "fonts_ok": os.path.exists(os.path.join(FONT_DIR, "NotoSansKhmer-VF.ttf")),
        "raqm_ok": raqm_available(),
        "hb_ok": khmer_shaper_available(),
        "pillow_version": getattr(PIL, "__version__", "?"),
    }


def khmer_shaping_mode():
    """Which engine will shape Khmer text right now.

    "harfbuzz" — our bundled uharfbuzz+freetype renderer (best, any Pillow)
    "raqm"     — Pillow built with Raqm (Layout.RAQM is requested on every
                 font load in _try_font)
    "none"     — neither available: ជើង/ស្រៈ would render scrambled
    """
    if khmer_shaper_available():
        path, vf = resolve_khmer_font_path()
        if path:
            try:
                _HBFont.get(path, 24, True, vf)   # real init, not just import
                return "harfbuzz"
            except Exception:
                print("[visualizer] HarfBuzz shaper init failed:",
                      file=sys.stderr)
                traceback.print_exc()
    if raqm_available():
        return "raqm"
    return "none"


def _try_font(name, px, bold, vf=False):
    key = (name, px, bold)
    if key in _font_cache:
        return _font_cache[key]
    try:
        try:
            if raqm_available():
                font = ImageFont.truetype(name, px, layout_engine=ImageFont.Layout.RAQM)
            else:
                font = ImageFont.truetype(name, px)
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


def resolve_khmer_font_path(family=None, bold=True):
    """Absolute path of a Khmer-capable font file (for the HB shaper)."""
    if family in KHMER_FONTS:
        spec = KHMER_FONTS[family]
        fname = spec.get("bold") if (bold and spec.get("bold")) else spec["file"]
        p = os.path.join(FONT_DIR, fname)
        if os.path.exists(p):
            return p, spec.get("vf", False)
    p = os.path.join(FONT_DIR, "NotoSansKhmer-VF.ttf")
    if os.path.exists(p):
        return p, True
    windir = os.environ.get("WINDIR", r"C:\Windows")
    for name in ("khmeruib.ttf", "khmerui.ttf", "leelauib.ttf", "leelawui.ttf"):
        p = os.path.join(windir, "Fonts", name)
        if os.path.exists(p):
            return p, False
    return None, False


def _force_buffer(buf, *, script, direction, language):
    """Set script/direction/language on a HarfBuzz buffer, tolerant of the
    binding's API: uharfbuzz uses properties, some builds expose setter
    methods. Any leftover fields are filled by guess_segment_properties()."""
    for attr, value, setter in (
        ("script", script, "set_script"),
        ("direction", direction, "set_direction"),
        ("language", language, "set_language"),
    ):
        try:
            method = getattr(buf, setter, None)
            if callable(method):
                method(value)
            else:
                setattr(buf, attr, value)
        except Exception:
            pass
    # backfill anything the binding left unset; HarfBuzz only fills fields
    # that are still unset, so the forced Khmr script is preserved
    try:
        buf.guess_segment_properties()
    except Exception:
        pass


class _HBFont:
    """HarfBuzz shaping + FreeType rasterizing for one (font, px, bold).

    Correct Khmer cluster shaping (ជើង, pre-base vowels) on any Pillow
    build — no Raqm needed.
    """
    _cache = {}

    @classmethod
    def get(cls, path, px, bold, vf):
        key = (path, px, bold)
        if key not in cls._cache:
            cls._cache[key] = cls(path, px, bold, vf)
        return cls._cache[key]

    def __init__(self, path, px, bold, vf):
        import freetype
        import uharfbuzz as hb
        self.px = px
        self.ft = freetype.Face(path)
        self.ft.set_pixel_sizes(0, px)
        self.hb_font = hb.Font(hb.Face(open(path, "rb").read()))
        self.hb_font.scale = (px * 64, px * 64)
        if vf and bold:
            try:
                self.hb_font.set_variations({"wght": 700.0})
                self.ft.set_var_design_coords((100.0, 700.0))  # wdth, wght
            except Exception:
                pass
        self.ascent, self.descent = self._scaled_metrics(px)
        self._mask_cache = {}

    def _scaled_metrics(self, px):
        """Pixel ascent/descent, robust across freetype-py versions.

        freetype-py's Face.size returns SizeMetrics directly (has
        .ascender); other bindings expose it as .size.metrics.ascender.
        Last resort: scale the face's font-unit metrics ourselves.
        """
        size = self.ft.size
        for obj in (size, getattr(size, "metrics", None)):
            if obj is None:
                continue
            try:
                return obj.ascender / 64.0, -obj.descender / 64.0
            except AttributeError:
                continue
        upem = self.ft.units_per_EM or 1000
        return (px * self.ft.ascender / upem, -px * self.ft.descender / upem)

    def shape(self, text):
        import uharfbuzz as hb
        buf = hb.Buffer()
        buf.add_str(text)
        if text_has_khmer(text):
            # Force Khmer shaping so ជើង (subscripts) and pre-base vowels are
            # reordered correctly. guess_segment_properties() alone leaves the
            # language at the machine locale, which can misfire on Windows.
            _force_buffer(buf, script="Khmr", direction="ltr", language="km")
        else:
            buf.guess_segment_properties()
        hb.shape(self.hb_font, buf)
        glyphs, pen = [], 0.0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            glyphs.append((info.codepoint,
                           pen + pos.x_offset / 64.0, pos.y_offset / 64.0))
            pen += pos.x_advance / 64.0
        return glyphs, pen

    def width(self, text):
        return self.shape(text)[1]

    def render_mask(self, text):
        """Tight-ish alpha mask + baseline position inside it + advance."""
        if text in self._mask_cache:
            return self._mask_cache[text]
        import freetype
        glyphs, adv = self.shape(text)
        pad = max(4, self.px // 3)
        W = int(math.ceil(adv)) + 2 * pad
        H = int((self.ascent + self.descent) * 1.6) + 2 * pad
        baseline = pad + int(self.ascent * 1.15)
        arr = np.zeros((H, W), np.uint8)
        for gid, gx, gy in glyphs:
            self.ft.load_glyph(gid, freetype.FT_LOAD_RENDER)
            bmp = self.ft.glyph.bitmap
            gw, gh = bmp.width, bmp.rows
            if gw == 0 or gh == 0:
                continue
            g = np.array(bmp.buffer, dtype=np.uint8).reshape(gh, bmp.pitch)[:, :gw]
            x0 = int(round(pad + gx + self.ft.glyph.bitmap_left))
            y0 = int(round(baseline - gy - self.ft.glyph.bitmap_top))
            xa, ya = max(0, x0), max(0, y0)
            xb, yb = min(W, x0 + gw), min(H, y0 + gh)
            if xa >= xb or ya >= yb:
                continue
            sub = g[ya - y0:yb - y0, xa - x0:xb - x0]
            arr[ya:yb, xa:xb] = np.maximum(arr[ya:yb, xa:xb], sub)
        result = (Image.fromarray(arr, "L"), pad, baseline, adv)
        if len(self._mask_cache) > 64:
            self._mask_cache.clear()
        self._mask_cache[text] = result
        return result


class TextEngine:
    """Unified measure/draw for titles & captions.

    Khmer text goes through HarfBuzz+FreeType when available (perfect ជើង
    even without Pillow-Raqm); everything else uses PIL.
    """

    def __init__(self, px, sample_text="", family=None, bold=True):
        self.px = px
        self.hb = None
        if text_has_khmer(sample_text) and khmer_shaper_available():
            path, vf = resolve_khmer_font_path(family, bold)
            if path:
                try:
                    self.hb = _HBFont.get(path, px, bold, vf)
                except Exception as exc:
                    import traceback
                    print('--- HarfBuzz Font Error ---')
                    traceback.print_exc()
                    self.hb = None
        if self.hb is not None:
            self.ascent, self.descent = self.hb.ascent, self.hb.descent
            self.pil_font = None
        else:
            self.pil_font = load_font(px, sample_text, bold, family)
            self.ascent, self.descent = self.pil_font.getmetrics()

    def width(self, text):
        if self.hb is not None:
            return self.hb.width(text)
        return ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(
            text, font=self.pil_font)

    def draw(self, img, xy, text, fill, stroke_width=0, stroke_fill=None):
        """Draw `text` with baseline-left at `xy` (like PIL anchor 'ls')."""
        x, by = xy
        if self.hb is None:
            ImageDraw.Draw(img, "RGBA").text(
                (x, by), text, font=self.pil_font, fill=fill, anchor="ls",
                stroke_width=stroke_width,
                stroke_fill=stroke_fill if stroke_width else None)
            return
        mask, pad, baseline, _ = self.hb.render_mask(text)
        pos = (int(round(x)) - pad, int(round(by)) - baseline)
        if stroke_width and stroke_fill:
            smask = mask.filter(ImageFilter.MaxFilter(2 * stroke_width + 1))
            img.paste(stroke_fill[:3], pos, _alpha_mask(smask, stroke_fill))
        img.paste(fill[:3], pos, _alpha_mask(mask, fill))


def _alpha_mask(mask, color):
    alpha = color[3] if len(color) > 3 else 255
    if alpha >= 255:
        return mask
    return mask.point(lambda v: v * alpha // 255)


def wrap_text(text, max_width, width_func):
    words = text.split()
    if not words:
        return [text]
    lines, cur = [], words[0]
    for word in words[1:]:
        trial = cur + " " + word
        if width_func(trial) <= max_width:
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


def _pip_install(packages, progress_cb=None, what="packages"):
    if getattr(sys, "frozen", False):
        raise RuntimeError(
            "This packaged build has no pip. Ask the app developer to "
            "bundle: " + " ".join(packages)
        )
    cmd = [sys.executable, "-m", "pip", "install", *packages]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            encoding="utf-8", errors="replace", creationflags=_no_window())
    for line in proc.stdout:
        if progress_cb and line.strip():
            progress_cb(f"Installing {what}… " + line.strip()[:70])
    if proc.wait() != 0:
        raise RuntimeError(
            "Install failed. Run manually:\n    pip install " + " ".join(packages)
        )


def install_whisper(progress_cb=None):
    """Install faster-whisper with pip (Auto Captions one-click setup)."""
    _pip_install(["faster-whisper"], progress_cb, "AI engine")


def install_khmer_shaper(progress_cb=None):
    """Install the HarfBuzz Khmer shaper (one-click fix for broken ជើង)."""
    _pip_install(["uharfbuzz", "freetype-py"], progress_cb, "Khmer shaper")


def _audio_is_stereo(path):
    r = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", path],
                       capture_output=True, text=True, creationflags=_no_window())
    for line in r.stderr.splitlines():
        if "Audio:" in line:
            return any(tag in line for tag in ("stereo", "5.1", "quad", "7.1"))
    return False


def isolate_vocals(path, out_path, progress_cb=None):
    """Real, lightweight vocal isolation via ffmpeg center-channel extraction.

    Vocals are usually mixed to the center, so the mid signal (L+R)/2 keeps
    them while hard-panned instruments cancel; a vocal-band band-pass then
    trims low rumble and high hiss. Not studio-grade AI separation, but a
    genuine, instant improvement — great for cleaning audio before Auto
    Captions. Returns out_path. Raises with a clear message on mono input.
    """
    if progress_cb:
        progress_cb("Analyzing channels…")
    if not _audio_is_stereo(path):
        raise RuntimeError(
            "This track is mono — center-channel isolation needs a stereo file.\n"
            "Tip: export the song in stereo, or use a full AI separator (demucs)."
        )
    if progress_cb:
        progress_cb("Isolating center-channel vocals…")
    af = "pan=mono|c0=0.5*c0+0.5*c1,highpass=f=150,lowpass=f=10000,dynaudnorm"
    cmd = [ffmpeg_exe(), "-y", "-v", "error", "-i", path, "-af", af,
           "-ac", "1", out_path]
    proc = subprocess.run(cmd, capture_output=True, creationflags=_no_window())
    if proc.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError("Vocal isolation failed:\n"
                           + proc.stderr.decode(errors="replace")[-300:])
    if progress_cb:
        progress_cb("Vocals isolated.")
    return out_path


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
# Only these styles read the raw per-sample waveform; for everything else the
# huge samples array can be dropped before shipping assets to worker processes.
NEEDS_SAMPLES = {"Waveform", "Dual Wave"}


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


def draw_title(frame, text, c1, position="Bottom Center", scale=1.0, family=None,
               custom=None, offset_x=0, alpha=255):
    """`custom` = (fx, fy) fractional center — lets the user drag the title
    anywhere on the preview; when set it overrides `position`."""
    if not text:
        return
    w, h = frame.size
    px = max(14, int(h * 0.038 * scale))
    te = TextEngine(px, text, family)
    tw = te.width(text)
    asc, desc = te.ascent, te.descent
    if custom:
        cx, cy = custom
        x = int(w * cx - tw / 2)
        y = int(h * cy + (asc - desc) / 2)
    else:
        fx, fy, align = _TITLE_ANCHOR.get(position, _TITLE_ANCHOR["Bottom Center"])
        x = int(w * fx - (tw if align == "rs" else tw / 2 if align == "ms" else 0))
        y = int(h * fy - (asc + desc) / 2 + asc) if fy == 0.5 else \
            int(h * fy + asc) if fy < 0.5 else int(h * fy)
    te.draw(frame, (x + offset_x + 2, y + 2), text, (0, 0, 0, int(160 * alpha / 255)))
    te.draw(frame, (x + offset_x, y), text, (245, 245, 245, int(235 * alpha / 255)))


def draw_subtitle(frame, text, style, c1, c2, family=None, scale=1.0, y_frac=0.80):
    if not text:
        return
    w, h = frame.size
    px = max(13, int(h * 0.045 * scale))
    te = TextEngine(px, text, family)
    draw = ImageDraw.Draw(frame, "RGBA")
    lines = wrap_text(text, int(w * 0.82), te.width)
    asc, desc = te.ascent, te.descent
    line_h = int((asc + desc) * 1.18)
    total_h = line_h * len(lines)
    y0 = int(h * y_frac) - total_h
    stroke = max(2, px // 12)

    if style == "CapCut Box":
        widths = [te.width(l) for l in lines]
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
        lw = te.width(line)
        x = (w - lw) / 2
        y = y0 + li * line_h + asc
        if style == "Bold Outline":
            te.draw(frame, (x, y), line, (255, 255, 255, 245),
                    stroke_width=stroke, stroke_fill=(0, 0, 0, 230))
        elif style == "Neon Glow":
            te.draw(frame, (x, y), line, (255, 255, 255, 245),
                    stroke_width=stroke + 1, stroke_fill=c1 + (200,))
        else:  # CapCut Box
            te.draw(frame, (x, y), line, (255, 255, 255, 245),
                    stroke_width=max(1, stroke // 2), stroke_fill=(0, 0, 0, 140))


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


# --------------------------------------------------------------------------
# Album Song Mode Helpers
# --------------------------------------------------------------------------

def parse_tracklist(raw_text):
    """
    Parse a YouTube-style tracklist.
    Example: 00:00 1. Song One\n03:15 2. Song Two
    Returns a sorted list of (seconds, title) tuples.
    """
    import re
    tracks = []
    # Match pattern: (H:)?M:S or (H:M:S)
    pattern = re.compile(r'(?:(\d+):)?(\d+):(\d+)')
    for line in (raw_text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        m = pattern.search(line)
        if m:
            h = int(m.group(1)) if m.group(1) else 0
            m_val = int(m.group(2))
            s = int(m.group(3))
            seconds = h * 3600 + m_val * 60 + s
            # Extract title: remove the matched timestamp from the line
            start_idx, end_idx = m.span()
            title = (line[:start_idx] + " " + line[end_idx:]).strip()
            # Clean up title (remove double spaces, leading dashes, dots, etc.)
            title = re.sub(r'^\s*[-–—:|.]\s*', '', title).strip()
            if not title:
                title = f"Track {len(tracks) + 1}"
            tracks.append((seconds, title))
    tracks.sort(key=lambda x: x[0])
    return tracks


def get_active_track(tracks, current_time):
    """
    Finds the active track index, title, start time, and elapsed time since it triggered.
    """
    if not tracks:
        return None, None, None, 0.0
    active_idx = -1
    for idx, (sec, title) in enumerate(tracks):
        if sec <= current_time:
            active_idx = idx
        else:
            break
    if active_idx == -1:
        active_idx = 0
    sec, title = tracks[active_idx]
    return active_idx, title, sec, current_time - sec


# --------------------------------------------------------------------------
# Playlist Cover (YouTube playlist-designer look)
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Video particle effects (deterministic per frame -> seekable + worker-safe)
# --------------------------------------------------------------------------

EFFECTS = ["None", "Snow Fall", "Fireflies", "Neon Dust", "Rising Sparks",
           "Bokeh Lights", "Rain", "Confetti", "Starfield", "Light Streaks",
           "Music Notes"]


def _prand(i, salt=0.0):
    """Stable pseudo-random 0..1 per particle index (no state between
    frames, so parallel workers and preview seeking stay consistent)."""
    return (math.sin(i * 12.9898 + salt * 78.233) * 43758.5453) % 1.0


def draw_effect(frame, effect, t, intensity, c1, c2, bass=0.0):
    """Overlay particles. `t` in seconds; intensity 0..100."""
    if not effect or effect == "None":
        return
    w, h = frame.size
    draw = ImageDraw.Draw(frame, "RGBA")
    n = int(18 + intensity * 1.1)
    unit = h / 540.0

    if effect == "Snow Fall":
        for i in range(n):
            spd = 0.05 + 0.11 * _prand(i, 3.3)
            y = ((_prand(i, 9.1) + t * spd) % 1.08) - 0.04
            x = (_prand(i, 1.7) + 0.025 * math.sin(t * (0.4 + _prand(i, 2.2)) + i)) % 1.0
            r = (1.0 + 2.6 * _prand(i, 5.5)) * unit
            alpha = int(110 + 110 * _prand(i, 7.7))
            px, py = x * w, y * h
            draw.ellipse((px - r, py - r, px + r, py + r),
                         fill=(255, 255, 255, alpha))

    elif effect == "Fireflies":
        for i in range(max(8, n // 2)):
            sp1, sp2 = 0.12 + 0.2 * _prand(i, 4.4), 0.1 + 0.16 * _prand(i, 6.6)
            x = (_prand(i, 1.1) + 0.06 * math.sin(t * sp1 + i * 2.1)) % 1.0
            y = (_prand(i, 2.9) + 0.05 * math.sin(t * sp2 + i * 4.7)
                 - t * 0.008) % 1.0
            pulse = 0.5 + 0.5 * math.sin(t * (0.8 + _prand(i, 8.8)) + i * 2.6)
            r = (1.4 + 2.0 * _prand(i, 5.2)) * unit
            px, py = x * w, y * h
            core = (255, 228, 140)
            draw.ellipse((px - r * 3, py - r * 3, px + r * 3, py + r * 3),
                         fill=core + (int(14 + 40 * pulse),))
            draw.ellipse((px - r, py - r, px + r, py + r),
                         fill=core + (int(90 + 150 * pulse),))

    elif effect == "Neon Dust":
        for i in range(n):
            spd = 0.015 + 0.03 * _prand(i, 3.9)
            y = ((_prand(i, 8.2) - t * spd) % 1.06) - 0.03
            x = (_prand(i, 1.3) + 0.012 * math.sin(t * 0.7 + i)) % 1.0
            twinkle = 0.4 + 0.6 * abs(math.sin(t * (1.2 + _prand(i, 6.1)) + i))
            r = (0.6 + 1.4 * _prand(i, 5.9)) * unit
            color = _lerp(c1, c2, _prand(i, 7.3))
            px, py = x * w, y * h
            draw.ellipse((px - r, py - r, px + r, py + r),
                         fill=color + (int(70 + 160 * twinkle * (0.6 + 0.4 * bass)),))

    elif effect == "Rising Sparks":
        for i in range(n):
            spd = 0.10 + 0.22 * _prand(i, 3.1)
            life = (_prand(i, 9.7) + t * spd) % 1.0
            y = 1.05 - life * 1.1
            x = (_prand(i, 1.9) + 0.02 * math.sin(t * 3.0 + i * 1.7)) % 1.0
            flicker = 0.55 + 0.45 * math.sin(t * 16 + i * 3.3)
            fade = max(0.0, 1.0 - life * 1.1)
            r = (0.7 + 1.6 * _prand(i, 4.8)) * unit
            color = _lerp(c1, c2, life)
            px, py = x * w, y * h
            draw.ellipse((px - r, py - r, px + r, py + r),
                         fill=color + (int(230 * fade * flicker),))

    elif effect == "Bokeh Lights":
        for i in range(max(5, n // 6)):
            x = (_prand(i, 1.5) + 0.03 * math.sin(t * 0.15 + i * 2.2)) % 1.0
            y = (_prand(i, 3.7) + 0.025 * math.sin(t * 0.11 + i * 1.4)) % 1.0
            pulse = 0.5 + 0.5 * math.sin(t * (0.3 + 0.3 * _prand(i, 6.3)) + i)
            r = (10 + 26 * _prand(i, 5.1)) * unit
            color = _lerp(c1, c2, _prand(i, 7.9))
            px, py = x * w, y * h
            a = int(10 + 26 * pulse)
            for k, f in ((1.0, a), (0.72, int(a * 1.5)), (0.4, int(a * 2.2))):
                rr = r * k
                draw.ellipse((px - rr, py - rr, px + rr, py + rr),
                             fill=color + (min(255, f),))

    elif effect == "Rain":
        length = 16 * unit
        for i in range(int(n * 1.4)):
            spd = 0.9 + 0.5 * _prand(i, 3.3)
            y = ((_prand(i, 9.1) + t * spd) % 1.12) - 0.08
            x = (_prand(i, 1.7) + 0.04) % 1.0
            slant = 3 * unit
            px, py = x * w, y * h
            alpha = int(60 + 90 * _prand(i, 7.7))
            draw.line((px, py, px + slant, py + length),
                      fill=(200, 220, 255, alpha), width=max(1, int(unit)))

    elif effect == "Confetti":
        for i in range(n):
            spd = 0.14 + 0.16 * _prand(i, 3.3)
            y = ((_prand(i, 9.1) + t * spd) % 1.1) - 0.05
            sway = 0.05 * math.sin(t * (1.5 + _prand(i, 2.2) * 2) + i)
            x = (_prand(i, 1.7) + sway) % 1.0
            s = (2.5 + 3.5 * _prand(i, 5.5)) * unit
            palette = [c1, c2, (255, 90, 90), (255, 214, 90),
                       (90, 220, 140), (110, 160, 255)]
            color = palette[i % len(palette)]
            px, py = x * w, y * h
            spin = math.sin(t * 6 + i)          # fake 3-D flip by squashing
            sw = max(1.0, abs(spin) * s)
            draw.rectangle((px - sw, py - s, px + sw, py + s),
                           fill=color + (225,))

    elif effect == "Starfield":
        for i in range(int(n * 1.6)):
            x, y = _prand(i, 1.3), _prand(i, 2.7)
            twinkle = 0.5 + 0.5 * math.sin(t * (1.5 + 2.5 * _prand(i, 6.1)) + i * 1.7)
            r = (0.5 + 1.6 * _prand(i, 5.9)) * unit
            px, py = x * w, y * h
            a = int(40 + 200 * twinkle * (0.6 + 0.4 * bass))
            draw.ellipse((px - r, py - r, px + r, py + r),
                         fill=(255, 255, 255, a))
            if _prand(i, 8.4) > 0.82:            # occasional colored star
                draw.ellipse((px - r, py - r, px + r, py + r),
                             fill=_lerp(c1, c2, _prand(i, 4.1)) + (a,))

    elif effect == "Light Streaks":
        for i in range(max(6, n // 4)):
            spd = 0.25 + 0.4 * _prand(i, 3.3)
            x = ((_prand(i, 9.1) + t * spd) % 1.3) - 0.15
            y = _prand(i, 2.7)
            ln = (40 + 120 * _prand(i, 5.5)) * unit
            px, py = x * w, y * h
            color = _lerp(c1, c2, _prand(i, 7.3))
            a = int(30 + 70 * (0.5 + 0.5 * bass))
            draw.line((px, py, px + ln, py), fill=color + (a,),
                      width=max(1, int(1.5 * unit)))
            draw.ellipse((px + ln - unit, py - unit, px + ln + unit, py + unit),
                         fill=color + (min(255, a * 3),))

    elif effect == "Music Notes":
        glyphs = ["♪", "♫", "♩", "♬"]
        # bucket sizes so we reuse a few cached TextEngines instead of
        # building a HarfBuzz font per note per frame (was ~80 ms/frame)
        base = max(12, int(16 * unit))
        buckets = {s: TextEngine(s, "♪") for s in (base, int(base * 1.6),
                                                   int(base * 2.2))}
        bsizes = sorted(buckets)
        for i in range(max(6, n // 3)):
            spd = 0.09 + 0.14 * _prand(i, 3.3)
            y = (_prand(i, 9.1) - t * spd) % 1.06
            sway = 0.04 * math.sin(t * (1.0 + _prand(i, 2.2)) + i)
            x = (_prand(i, 1.7) + sway) % 1.0
            g = glyphs[i % len(glyphs)]
            gte = buckets[bsizes[i % len(bsizes)]]
            color = _lerp(c1, c2, _prand(i, 7.3))
            fade = int(120 + 120 * (0.5 + 0.5 * math.sin(t + i)))
            gte.draw(frame, (int(x * w), int(y * h)), g,
                     color + (min(255, fade),))


PLAYLIST_MAX_ROWS = 9

# Playlist Cover layout variants (menu prefix -> config)
PLAYLIST_VARIANTS = {
    "11.": {"align": "left", "glass": False},
    "12.": {"align": "center", "glass": False},
    "13.": {"align": "right", "glass": False},
    "14.": {"align": "center", "glass": True},
    "15.": {"align": "right", "glass": True},
    "16.": {"align": "left", "glass": True},
}

# static layers are expensive (blur glow) but only change when the active
# track changes, so cache a handful per process
_PLAYLIST_CACHE = {}


def _fmt_mmss(t):
    t = max(0, int(t))
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _playlist_geometry(size, variant):
    w, h = size
    row_h = max(18, int(h * 0.058))
    y0 = int(h * 0.27)
    panel_w = int(w * (0.62 if variant.get("align") == "center" else 0.54))
    align = variant.get("align", "left")
    if align == "center":
        x0 = int((w - panel_w) / 2)
    elif align == "right":
        x0 = int(w - panel_w - w * 0.055)
    else:
        x0 = int(w * 0.055)
    return x0, y0, panel_w, row_h


def _build_playlist_layer(size, title, tracks, active_idx, win_start, theme,
                          family, scale, total_dur, variant):
    """Static part of the playlist cover: neon glow title, stats row, and
    the numbered tracklist with the active row highlighted."""
    w, h = size
    c1, c2 = THEMES.get(theme, THEMES["Neon Purple"])
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")

    # --- big neon title with a real blurred glow (auto-shrinks to fit) ---
    if title:
        px = max(16, int(h * 0.082 * scale))
        te = TextEngine(px, title, family)
        tw = te.width(title)
        while tw > w * 0.94 and px > 12:
            px = max(12, int(px * 0.92))
            te = TextEngine(px, title, family)
            tw = te.width(title)
        x = int((w - tw) / 2)
        y = int(h * 0.145)
        glow = Image.new("RGBA", size, (0, 0, 0, 0))
        te.draw(glow, (x, y), title, c1 + (255,))
        glow = glow.filter(ImageFilter.GaussianBlur(max(4, px // 6)))
        layer.alpha_composite(glow)
        layer.alpha_composite(glow)          # double pass = stronger neon
        te.draw(layer, (x, y), title, _lerp(c1, (255, 255, 255), 0.72) + (255,))

    # --- stats row: N SONGS · TOTAL · YEAR (separator dots are drawn, not
    # font glyphs — decorative fonts like Koulen have no bullet glyph) ---
    import time as _time
    segs = [f"{len(tracks)} SONGS", _fmt_mmss(total_dur),
            str(_time.localtime().tm_year)]
    spx = max(10, int(h * 0.024))
    stes = [TextEngine(spx, s, family) for s in segs]
    widths = [t.width(s) for t, s in zip(stes, segs)]
    gap = spx * 2.2
    total_w = sum(widths) + gap * (len(segs) - 1)
    sx = (w - total_w) / 2
    sy = int(h * 0.235)
    dot_r = max(2, spx // 6)
    for k, (t, s, sw_) in enumerate(zip(stes, segs, widths)):
        t.draw(layer, (int(sx), sy), s, c2 + (225,))
        sx += sw_
        if k < len(segs) - 1:
            cx = sx + gap / 2
            cy = sy - spx * 0.32
            draw.ellipse((cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r),
                         fill=c2 + (200,))
            sx += gap

    # --- tracklist rows ---
    x0, y0, panel_w, row_h = _playlist_geometry(size, variant)
    glass = variant.get("glass", False)
    rows = tracks[win_start:win_start + PLAYLIST_MAX_ROWS]
    rpx = max(11, int(row_h * 0.46))
    active_rect = None
    for r, (sec, ttl) in enumerate(rows):
        gi = win_start + r
        active = gi == active_idx
        top = y0 + r * row_h
        box = (x0, top, x0 + panel_w, top + row_h - max(4, row_h // 8))
        radius = (box[3] - box[1]) // 2
        rte = TextEngine(rpx, ttl, family)
        baseline = int((box[1] + box[3]) / 2 + (rte.ascent - rte.descent) / 2)
        time_lbl = _fmt_mmss(sec)
        tte = TextEngine(max(9, int(rpx * 0.8)), time_lbl, family)
        time_w = tte.width(time_lbl)
        # truncate the song name to fit the pill (reserve room for the
        # number, the play triangle on the active row, and the time label)
        avail = panel_w - int(rpx * 5.4) - time_w
        text = ttl
        while text and rte.width(text) > avail:
            text = text[:-1]
        if text != ttl:
            # don't end mid-cluster (dangling coeng/vowel renders a dotted
            # circle) and use ASCII dots — decorative fonts lack the … glyph
            while text and (0x17B4 <= ord(text[-1]) <= 0x17D3):
                text = text[:-1]
            text = text.rstrip() + ".."
        text_x = x0 + int(rpx * 2.6)
        if active:
            active_rect = box
            draw.rounded_rectangle(box, radius=radius, fill=c1 + (215,))
            draw.rounded_rectangle(box, radius=radius,
                                   outline=_lerp(c1, (255, 255, 255), 0.5) + (200,),
                                   width=max(1, h // 400))
            num_color, txt_color = (255, 255, 255, 255), (255, 255, 255, 255)
            # play triangle drawn geometrically (decorative Khmer fonts have
            # no ▶ glyph — a text prefix renders as a tofu box)
            th = rpx * 0.62
            ty = (box[1] + box[3]) / 2
            draw.polygon([(text_x, ty - th / 2), (text_x, ty + th / 2),
                          (text_x + th * 0.9, ty)], fill=(255, 255, 255, 240))
            text_x += int(th * 1.5)
        elif glass:
            # frosted-glass pills: translucent white with a light border
            draw.rounded_rectangle(box, radius=radius, fill=(255, 255, 255, 30))
            draw.rounded_rectangle(box, radius=radius,
                                   outline=(255, 255, 255, 70),
                                   width=max(1, h // 500))
            num_color, txt_color = (255, 255, 255, 235), (248, 248, 252, 225)
        else:
            draw.rounded_rectangle(box, radius=radius, fill=(10, 10, 18, 115))
            num_color, txt_color = c1 + (200,), (232, 232, 238, 200)
        nte = TextEngine(rpx, f"{gi + 1:02d}", family)
        nte.draw(layer, (x0 + int(rpx * 0.9), baseline), f"{gi + 1:02d}", num_color)
        rte2 = TextEngine(rpx, text, family)
        rte2.draw(layer, (text_x, baseline), text, txt_color)
        tte.draw(layer, (x0 + panel_w - time_w - int(rpx * 0.9),
                         baseline - int(rpx * 0.08)), time_lbl,
                 (200, 200, 210, 170) if not active else (255, 255, 255, 220))
    return layer, active_rect


def draw_playlist_cover(frame, idx, tracks, elapsed, opts, bass=0.0,
                        total_dur=0.0, variant=None):
    """YouTube-playlist-cover overlay: neon title + numbered tracklist with a
    beat-pulsing now-playing pill + stats row. Static parts are cached."""
    if variant is None:
        variant = PLAYLIST_VARIANTS["11."]
    size = frame.size
    theme = opts.get("theme", "Neon Purple")
    family = opts.get("title_font")
    title = (opts.get("title_text") or "").strip()
    scale = round(float(opts.get("title_scale", 1.0)), 2)
    n = len(tracks)
    win_start = 0
    if n > PLAYLIST_MAX_ROWS:
        win_start = max(0, min(idx - PLAYLIST_MAX_ROWS // 2,
                               n - PLAYLIST_MAX_ROWS))
    key = (size, title, tuple(t for _, t in tracks), idx, win_start, theme,
           family, scale, int(total_dur),
           variant.get("align"), variant.get("glass"))
    cached = _PLAYLIST_CACHE.get(key)
    if cached is None:
        cached = _build_playlist_layer(size, title, tracks, idx, win_start,
                                       theme, family, scale, total_dur, variant)
        if len(_PLAYLIST_CACHE) > 6:
            _PLAYLIST_CACHE.clear()
        _PLAYLIST_CACHE[key] = cached
    layer, active_rect = cached
    frame.paste(layer, (0, 0), layer)

    draw = ImageDraw.Draw(frame, "RGBA")
    c1, c2 = THEMES.get(theme, THEMES["Neon Purple"])
    if active_rect:
        # beat-pulsing glow ring around the now-playing pill
        pad = max(2, int(frame.height * 0.004))
        ring = (active_rect[0] - pad, active_rect[1] - pad,
                active_rect[2] + pad, active_rect[3] + pad)
        alpha = int(50 + 175 * max(0.0, min(1.0, bass)))
        draw.rounded_rectangle(ring, radius=(ring[3] - ring[1]) // 2,
                               outline=c2 + (alpha,),
                               width=max(2, frame.height // 260))
        # elapsed time of the current track, right of the pill
        lbl = _fmt_mmss(elapsed)
        px = max(10, int((active_rect[3] - active_rect[1]) * 0.55))
        te = TextEngine(px, lbl)
        te.draw(frame, (active_rect[2] + int(px * 0.7),
                        int((active_rect[1] + active_rect[3]) / 2
                            + (te.ascent - te.descent) / 2)),
                lbl, c2 + (235,))


def draw_album_styles(frame, title, idx, all_tracks, style_name, elapsed_time,
                      opts, bass=0.0, total_dur=0.0):
    """
    Dynamic track graphics router for all selection variants.
    """
    if "Playlist" in style_name:
        variant = next((cfg for pre, cfg in PLAYLIST_VARIANTS.items()
                        if style_name.startswith(pre)),
                       PLAYLIST_VARIANTS["11."])
        draw_playlist_cover(frame, idx, all_tracks, elapsed_time, opts,
                            bass=bass, total_dur=total_dur, variant=variant)
        return

    c1, c2 = THEMES.get(opts.get("theme", "Neon Purple"), THEMES["Neon Purple"])
    scale = float(opts.get("title_scale", 1.0))
    family = opts.get("title_font")
    px = max(14, int(frame.height * 0.038 * scale))
    te = TextEngine(px, title, family)
    tw = te.width(title)
    asc, desc = te.ascent, te.descent
    w, h = frame.size
    draw = ImageDraw.Draw(frame, "RGBA")

    # 1. Kinetic Slide-In
    if "1. Kinetic Slide-In" in style_name:
        offset_x = 0
        alpha = 255
        if 0 <= elapsed_time <= 2.5:
            p = elapsed_time / 2.5
            ease_out_exp = 1 - 2**(-10 * p)
            offset_x = int(-80 * (1.0 - ease_out_exp))
            alpha = int(255 * p)
        draw_title(frame, title, c1, position=opts.get("title_pos", "Bottom Center"),
                   scale=scale, family=family, custom=opts.get("title_custom"),
                   offset_x=offset_x, alpha=alpha)

    # 2. Side Playlist Panel
    elif "2. Side Playlist Panel" in style_name:
        panel_w = int(w * 0.28)
        draw.rectangle((w - panel_w, 0, w, h), fill=(12, 12, 20, 160))
        draw.line((w - panel_w, 0, w - panel_w, h), fill=c1 + (180,), width=2)
        
        head_px = max(12, int(h * 0.024))
        te_head = TextEngine(head_px, "TRACKLIST", family)
        te_head.draw(frame, (w - panel_w + 14, 28), "TRACKLIST", c1 + (255,))
        
        track_px = max(10, int(h * 0.018))
        y_offset = 64
        for t_idx, (sec, t_title) in enumerate(all_tracks):
            disp_title = t_title[:24] + "..." if len(t_title) > 26 else t_title
            te_track = TextEngine(track_px, disp_title, family)
            if t_idx == idx:
                pad = max(4, track_px // 3)
                tw_track = te_track.width(disp_title)
                draw.rounded_rectangle((w - panel_w + 8, y_offset - te_track.ascent - pad, w - 8, y_offset + te_track.descent + pad), radius=6, fill=c1 + (80,))
                te_track.draw(frame, (w - panel_w + 20, y_offset), disp_title, (255, 255, 255, 255))
            else:
                te_track.draw(frame, (w - panel_w + 20, y_offset), disp_title, (180, 180, 180, 120))
            y_offset += int(track_px * 2.2)
            if y_offset > h - 40:
                break

    # 3. Live Wave Indicator
    elif "3. Live Wave Indicator" in style_name:
        track_px = max(12, int(h * 0.022))
        y_offset = int(h * 0.15)
        for t_idx, (sec, t_title) in enumerate(all_tracks):
            te_track = TextEngine(track_px, t_title, family)
            tw_track = te_track.width(t_title)
            x = 30
            y = y_offset
            if t_idx == idx:
                te_track.draw(frame, (x, y), t_title, c1 + (255,))
                bx = x + tw_track + 14
                import math
                for b_idx in range(4):
                    bounce = math.sin(elapsed_time * 8.0 + b_idx * 1.5) * 0.5 + 0.5
                    bar_h = int(track_px * 0.8 * bounce) + 2
                    bar_w = max(2, track_px // 8)
                    gap = max(2, track_px // 10)
                    x0 = bx + b_idx * (bar_w + gap)
                    draw.rounded_rectangle((x0, y - bar_h, x0 + bar_w, y), radius=bar_w // 2, fill=c2 + (235,))
            else:
                te_track.draw(frame, (x, y), t_title, (180, 180, 180, 120))
            y_offset += int(track_px * 1.8)
            if y_offset > h - 40:
                break

    # 4. Modern Ticker Bar
    elif "4. Modern Ticker Bar" in style_name:
        bar_h = int(px * 1.6)
        draw.rectangle((0, h - bar_h, w, h), fill=(10, 10, 15, 180))
        draw.line((0, h - bar_h, w, h - bar_h), fill=c1 + (180,), width=2)
        m, s = divmod(int(elapsed_time), 60)
        time_str = f"{m:02d}:{s:02d}"
        text_info = f"NOW PLAYING: Track {idx+1}/{len(all_tracks)}  |  {title} ({time_str})"
        te_info = TextEngine(int(px * 0.9), text_info, family)
        te_info.draw(frame, (20, h - bar_h + int(px * 0.35)), text_info, (240, 240, 240, 235))

    # 5. Neon Glow Label
    elif "5. Neon Glow Label" in style_name:
        cx, cy = opts.get("title_custom") if opts.get("title_custom") else (0.5, 0.86)
        if not opts.get("title_custom"):
            fx, fy, align = _TITLE_ANCHOR.get(opts.get("title_pos", "Bottom Center"), _TITLE_ANCHOR["Bottom Center"])
            cx, cy = fx, fy
        x = int(w * cx - tw / 2)
        y = int(h * cy + (asc - desc) / 2)
        for r in (5, 3, 1):
            for dx, dy in [(-r, 0), (r, 0), (0, -r), (0, r), (-r, -r), (r, r), (-r, r), (r, -r)]:
                te.draw(frame, (x + dx, y + dy), title, c2 + (40 // r,))
        te.draw(frame, (x, y), title, (255, 255, 255, 255))

    # 6. Cinematic Corner Stamp
    elif "6. Cinematic Corner Stamp" in style_name:
        stamp_w = int(px * 8.0)
        stamp_h = int(px * 3.4)
        sx, sy = 24, 24
        draw.rectangle((sx, sy, sx + stamp_w, sy + stamp_h), fill=(0, 0, 0, 100), outline=(255, 255, 255, 100), width=1)
        te_stamp1 = TextEngine(int(px * 0.8), f"TRACK {idx+1:02d}: {title[:16]}", family)
        te_stamp1.draw(frame, (sx + 10, sy + int(px * 0.9)), f"TRACK {idx+1:02d}: {title[:16]}", (245, 245, 245, 220))
        m, s = divmod(int(elapsed_time), 60)
        te_stamp2 = TextEngine(int(px * 0.7), f"TIME: {m:02d}:{s:02d}", family)
        te_stamp2.draw(frame, (sx + 10, sy + int(px * 1.9)), f"TIME: {m:02d}:{s:02d}", (200, 200, 200, 200))
        if int(elapsed_time * 2) % 2 == 0:
            draw.ellipse((sx + stamp_w - 20, sy + 10, sx + stamp_w - 10, sy + 20), fill=(220, 40, 40, 255))

    # 7. Top Header Banner
    elif "7. Top Header Banner" in style_name:
        bar_h = int(px * 1.5)
        draw.rectangle((0, 0, w, bar_h), fill=(10, 10, 15, 190))
        draw.line((0, bar_h, w, bar_h), fill=c1 + (180,), width=2)
        header_text = f"● NOW PLAYING: {title}  |  TRACK {idx+1} OF {len(all_tracks)}"
        te_h = TextEngine(int(px * 0.85), header_text, family)
        htw = te_h.width(header_text)
        te_h.draw(frame, ((w - htw) // 2, int(px * 0.95)), header_text, (245, 245, 245, 235))

    # 8. Minimalist Drop Shadow
    elif "8. Minimalist Drop Shadow" in style_name:
        cx, cy = opts.get("title_custom") if opts.get("title_custom") else (0.5, 0.86)
        if not opts.get("title_custom"):
            fx, fy, align = _TITLE_ANCHOR.get(opts.get("title_pos", "Bottom Center"), _TITLE_ANCHOR["Bottom Center"])
            cx, cy = fx, fy
        x = int(w * cx - tw / 2)
        y = int(h * cy + (asc - desc) / 2)
        te.draw(frame, (x + 4, y + 4), title, (0, 0, 0, 40))
        te.draw(frame, (x + 3, y + 3), title, (0, 0, 0, 80))
        te.draw(frame, (x + 2, y + 2), title, (0, 0, 0, 130))
        te.draw(frame, (x + 1, y + 1), title, (0, 0, 0, 180))
        te.draw(frame, (x, y), title, (255, 255, 255, 255))

    # 9. Centered Focal Board
    elif "9. Centered Focal Board" in style_name:
        cx, cy = opts.get("title_custom") if opts.get("title_custom") else (0.5, 0.86)
        if not opts.get("title_custom"):
            fx, fy, align = _TITLE_ANCHOR.get(opts.get("title_pos", "Bottom Center"), _TITLE_ANCHOR["Bottom Center"])
            cx, cy = fx, fy
        pad_x = px * 1.5
        pad_y = px * 0.6
        bx0 = w * cx - tw / 2 - pad_x
        by0 = h * cy - asc - pad_y
        bx1 = w * cx + tw / 2 + pad_x
        by1 = h * cy + desc + pad_y
        draw.rounded_rectangle((bx0, by0, bx1, by1), radius=12, fill=(18, 18, 24, 185), outline=c1 + (150,), width=2)
        te.draw(frame, (int(w * cx - tw / 2), int(h * cy + (asc - desc) / 2)), title, (245, 245, 245, 235))
        sub_text = f"TRACK {idx+1:02d}"
        te_sub = TextEngine(int(px * 0.55), sub_text, family)
        stw = te_sub.width(sub_text)
        te_sub.draw(frame, (int(w * cx - stw / 2), int(by0 + px * 0.5)), sub_text, c1 + (220,))

    # 10. Compact Pill Capsule
    else:
        cx, cy = opts.get("title_custom") if opts.get("title_custom") else (0.5, 0.86)
        if not opts.get("title_custom"):
            fx, fy, align = _TITLE_ANCHOR.get(opts.get("title_pos", "Bottom Center"), _TITLE_ANCHOR["Bottom Center"])
            cx, cy = fx, fy
        pad = int(px * 0.6)
        bx0 = w * cx - tw / 2 - pad
        by0 = h * cy - asc - pad // 2
        bx1 = w * cx + tw / 2 + pad
        by1 = h * cy + desc + pad // 2
        draw.rounded_rectangle((bx0, by0, bx1, by1), radius=max(12, px // 2), fill=(247, 245, 240, 240), outline=c1 + (160,), width=2)
        te.draw(frame, (int(w * cx - tw / 2), int(h * cy + (asc - desc) / 2)), title, (17, 20, 24, 235))


def compose_frame(assets, i, opts):
    an = assets.an
    c1, c2 = THEMES.get(opts.get("theme", "Neon Purple"), THEMES["Neon Purple"])
    if assets.beat_zoom:
        frame = zoomed_background(assets.background, assets.size, float(an.bass[i]))
    else:
        frame = assets.background.copy()

    style = opts.get("style", "Neon Bars")
    vis_dx = float(opts.get("vis_dx", 0.0))
    vis_dy = float(opts.get("vis_dy", 0.0))
    vis_scale = float(opts.get("vis_scale", 1.0))
    w, h = assets.size
    if abs(vis_dx) > 0.002 or abs(vis_dy) > 0.002 or abs(vis_scale - 1.0) > 0.01:
        # draw the visualizer on its own layer so it can move/scale anywhere
        overlay = Image.new("RGBA", assets.size, (0, 0, 0, 0))
        draw_style(overlay, style, an, i, c1, c2,
                   assets.center_art, opts.get("custom"))
        if abs(vis_scale - 1.0) > 0.01:
            nw = max(2, int(w * vis_scale))
            nh = max(2, int(h * vis_scale))
            overlay = overlay.resize((nw, nh), Image.BILINEAR)
        else:
            nw, nh = w, h
        pos = (int((w - nw) / 2 + vis_dx * w), int((h - nh) / 2 + vis_dy * h))
        frame.paste(overlay, pos, overlay)
    else:
        draw_style(frame, style, an, i, c1, c2,
                   assets.center_art, opts.get("custom"))

    t = i / an.fps

    # particle effects float over the art + visualizer, under the text
    effect = opts.get("effect")
    if effect and effect != "None":
        draw_effect(frame, effect, t,
                    float(opts.get("effect_intensity", 50)),
                    c1, c2, bass=float(an.bass[i]))

    if opts.get("use_tracklist") and opts.get("audio_paths"):
        tracks = opts.get("track_timeline")
        if tracks is None:
            tracks = opts.get("_track_timeline")
        if tracks is None:
            tracks = build_track_timeline(opts["audio_paths"])

        if tracks:
            idx, active_title, track_start, elapsed = get_active_track(tracks, t)
            if active_title:
                draw_album_styles(frame, active_title, idx, tracks,
                                  opts.get("album_style", "1. Kinetic Slide-In"),
                                  elapsed, opts,
                                  bass=float(an.bass[i]), total_dur=an.duration)
    elif opts.get("show_title"):
        title_text = opts.get("title_text", "")
        offset_x = 0
        alpha = 255
        transition_start = 0.0

        if title_text:
            elapsed = t - transition_start
            if 0 <= elapsed <= 2.5:
                p = elapsed / 2.5
                ease_out_exp = 1 - 2**(-10 * p)
                offset_x = int(-80 * (1.0 - ease_out_exp))
                alpha = int(255 * p)

            draw_title(frame, title_text, c1,
                       opts.get("title_pos", "Bottom Center"),
                       opts.get("title_scale", 1.0),
                       family=opts.get("title_font"),
                       custom=opts.get("title_custom"),
                       offset_x=offset_x,
                       alpha=alpha)

    if opts.get("show_subs") and opts.get("subtitles"):
        t = i / an.fps
        text = find_subtitle(opts["subtitles"], t)
        if text:
            draw_subtitle(frame, text, opts.get("sub_style", "CapCut Box"), c1, c2,
                          family=opts.get("sub_font"),
                          scale=float(opts.get("sub_scale", 1.0)),
                          y_frac=float(opts.get("sub_y", 0.80)))

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
# Audio processing (Studio controls) + video codec selection
# --------------------------------------------------------------------------

# Enhancer preset -> extra ffmpeg audio filter. Keys match the UI menu.
ENHANCER_FILTERS = {
    "Disable": None,
    "Pro Vocal Boost": "equalizer=f=3000:t=q:w=1.5:g=4",
    "Clear Clear": "equalizer=f=8000:t=q:w=2:g=3",
    "Loudness Normalize": "loudnorm=I=-14:TP=-1.5:LRA=11",
    "Noise Cancel": "highpass=f=80,afftdn=nf=-25",
}

# Mix-Master presets: compressor -> tone shaping -> loudness -> limiter,
# like a streaming-ready mastering chain. Keys match the UI menu.
MASTER_PRESETS = {
    "Off": None,
    "YouTube Loud": ("acompressor=threshold=-18dB:ratio=3:attack=20:release=250:makeup=4,"
                     "loudnorm=I=-14:TP=-1.0:LRA=11,alimiter=limit=0.97"),
    "Warm Analog": ("bass=g=2.5:f=120,treble=g=-1.5:f=9000,"
                    "acompressor=threshold=-20dB:ratio=2:attack=25:release=300:makeup=3,"
                    "alimiter=limit=0.95"),
    "Club Bass": ("bass=g=6:f=90:w=0.5,"
                  "acompressor=threshold=-16dB:ratio=4:attack=10:release=180:makeup=5,"
                  "alimiter=limit=0.97"),
    "Crystal Clear": ("treble=g=3:f=8500,equalizer=f=250:t=q:w=1:g=-2,"
                      "loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.97"),
}


def build_audio_filters(opts, duration):
    """ffmpeg -af chain from the Studio controls + fade.

    Note: without stem separation "volume" scales the whole mix, so it is
    the overall output level, not vocals-only.
    """
    filters = []
    vol = float(opts.get("vocal_volume", 100)) / 100.0
    if abs(vol - 1.0) > 0.01:
        filters.append(f"volume={vol:.3f}")
    bass = float(opts.get("bass_boost", 0))
    if bass > 0:
        filters.append(f"bass=g={bass / 100.0 * 15.0:.1f}:f=110:w=0.6")
    reverb = float(opts.get("reverb", 0))
    if reverb > 0:
        d = reverb / 100.0
        filters.append(
            f"aecho=0.8:{0.6 + 0.3 * d:.2f}:{int(40 + 60 * d)}:{0.3 + 0.4 * d:.2f}")
    enh = ENHANCER_FILTERS.get(opts.get("enhancer", "Disable"))
    if enh:
        filters.append(enh)
    master = MASTER_PRESETS.get(opts.get("master", "Off"))
    if master:
        # loudnorm runs internally at 192 kHz — pin the output rate back
        filters.append(master + ",aresample=44100")
    if opts.get("fade"):
        fade_out = max(0.0, duration - 1.0)
        filters.append("afade=t=in:st=0:d=1")
        filters.append(f"afade=t=out:st={fade_out:.2f}:d=1")
    return filters


def _encoder_works(name):
    """Actually run the encoder on a tiny frame — listing it in -encoders
    does not mean the driver/hardware is present at runtime."""
    try:
        r = subprocess.run(
            [ffmpeg_exe(), "-hide_banner", "-f", "lavfi",
             "-i", "nullsrc=s=64x64:d=0.1", "-c:v", name, "-f", "null", "-"],
            capture_output=True, creationflags=_no_window())
        return r.returncode == 0
    except Exception:
        return False


def pick_video_codec(use_gpu):
    """(codec, extra_opts). Falls back to libx264 when no GPU encoder works."""
    if use_gpu:
        for name, gpu_opts in (
            ("h264_nvenc", ["-preset", "fast", "-b:v", "12M"]),
            ("h264_amf", ["-b:v", "12M"]),
            ("h264_qsv", ["-b:v", "12M"]),
        ):
            if _encoder_works(name):
                return name, gpu_opts
    return "libx264", ["-preset", "fast", "-crf", "18"]


# --------------------------------------------------------------------------
# Multi-Core CPU Rendering Workers
# --------------------------------------------------------------------------

_worker_assets = None
_worker_opts = None


# Frame count below which multiprocessing isn't worth the spawn overhead.
PARALLEL_MIN_FRAMES = 300


def _init_worker(assets, opts):
    global _worker_assets, _worker_opts
    _worker_assets = assets
    _worker_opts = opts


def _worker_payload(assets, opts, an):
    """Trim what gets pickled to each worker process.

    Drops the (potentially album-sized) raw samples array unless a
    waveform style needs it, and removes the pre-computed _analysis so the
    big object isn't shipped twice.
    """
    import dataclasses
    wopts = {k: v for k, v in opts.items() if k != "_analysis"}
    if opts.get("style") not in NEEDS_SAMPLES and getattr(an, "samples", None) is not None \
            and an.samples.size:
        light_an = dataclasses.replace(an, samples=np.empty(0, dtype=np.float32))
        assets = dataclasses.replace(assets, an=light_an)
    return assets, wopts


def _parallel_frames(assets, opts, an, cancel_event, start=0):
    """Yield ordered frames from a process pool with a BOUNDED window of
    in-flight futures. executor.map would submit every frame upfront and
    buffer finished RGB frames faster than ffmpeg consumes them — on long
    videos that exhausts RAM and Windows kills the workers ('process pool
    terminated abruptly'). A sliding window keeps memory flat."""
    from collections import deque
    wassets, wopts = _worker_payload(assets, opts, an)
    workers = max(1, min(12, (os.cpu_count() or 2) - 1))
    window = workers * 3
    executor = concurrent.futures.ProcessPoolExecutor(
        max_workers=workers, initializer=_init_worker,
        initargs=(wassets, wopts))
    futures = deque()
    next_i = start
    total = an.num_frames
    try:
        while next_i < total and len(futures) < window:
            futures.append(executor.submit(_draw_frame_worker, next_i))
            next_i += 1
        while futures:
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("cancelled")
            i, res = futures.popleft().result()
            if isinstance(res, Exception):
                raise res
            if next_i < total:
                futures.append(executor.submit(_draw_frame_worker, next_i))
                next_i += 1
            yield i, res
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _generate_frames(assets, opts, an, cancel_event, use_parallel):
    """Yield (frame_index, rgb_bytes) in order.

    Multi-core when it pays off; if the worker pool ever dies (OOM, broken
    child, frozen-build quirks) the render continues seamlessly on a single
    core from the next frame instead of failing.
    """
    start = 0
    if use_parallel:
        try:
            for i, res in _parallel_frames(assets, opts, an, cancel_event,
                                           start):
                start = i + 1
                yield i, res
            return
        except (InterruptedError, GeneratorExit):
            raise
        except BaseException:
            print("[visualizer] parallel rendering failed — continuing on a "
                  "single core from frame", start, file=sys.stderr)
            traceback.print_exc()
    for i in range(start, an.num_frames):
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("cancelled")
        yield i, compose_frame(assets, i, opts).tobytes()


def _draw_frame_worker(i):
    global _worker_assets, _worker_opts
    try:
        frame = compose_frame(_worker_assets, i, _worker_opts)
        return i, frame.tobytes()
    except Exception as e:
        return i, e


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

def render_video(image_path, audio_path, out_path, opts,
                 progress_cb=None, cancel_event=None):
    audio_paths = list(audio_path) if isinstance(audio_path, (list, tuple)) else [audio_path]
    if opts.get("use_tracklist") and audio_paths:
        opts["_track_timeline"] = build_track_timeline(audio_paths)

    fps = int(opts.get("fps", 30))
    size = even_size(opts.get("size", (1920, 1080)))
    an = opts.get("_analysis")
    if an is None or an.fps != fps:
        an = analyze(audio_paths, fps)
    assets = prepare_assets(image_path, an, size, opts)

    w, h = size
    v_codec, v_opts = pick_video_codec(opts.get("use_gpu"))
    audio_filters = build_audio_filters(opts, an.duration)
    use_parallel = an.num_frames >= PARALLEL_MIN_FRAMES and (os.cpu_count() or 1) > 1

    temp_concat_file = None
    try:
        if len(audio_paths) > 1:
            import tempfile
            fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix="ffmpeg_concat_")
            temp_concat_file = temp_path
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for p in audio_paths:
                    safe_p = os.path.abspath(p).replace("\\", "/")
                    f.write(f"file '{safe_p}'\n")

        cmd = [
            ffmpeg_exe(), "-y", "-v", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
            "-r", str(fps), "-i", "-",
        ]
        if temp_concat_file:
            cmd += ["-f", "concat", "-safe", "0", "-i", temp_concat_file]
        else:
            cmd += ["-i", audio_paths[0]]

        a_bitrate = "256k" if MASTER_PRESETS.get(opts.get("master", "Off")) else "192k"
        cmd += [
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", v_codec,
        ] + v_opts + [
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", a_bitrate,
        ]
        if audio_filters:
            cmd += ["-af", ",".join(audio_filters)]
        cmd += ["-shortest", "-movflags", "+faststart", out_path]

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
                                creationflags=_no_window())

        # Drain stderr on a thread so ffmpeg never blocks on a full pipe
        import threading
        ffmpeg_stderr_lines = []

        def log_ffmpeg_stderr():
            try:
                for line in proc.stderr:
                    ffmpeg_stderr_lines.append(line)
            except Exception:
                pass

        ffmpeg_stderr_thread = threading.Thread(target=log_ffmpeg_stderr, daemon=True)
        ffmpeg_stderr_thread.start()

        gen = None
        try:
            gen = _generate_frames(assets, opts, an, cancel_event, use_parallel)
            for i, res in gen:
                proc.stdin.write(res)
                if progress_cb and (i % 5 == 0 or i == an.num_frames - 1):
                    progress_cb(i + 1, an.num_frames)
            proc.stdin.close()
            ffmpeg_stderr_thread.join(timeout=2.0)
            err = b"".join(ffmpeg_stderr_lines).decode(errors="replace")
            if proc.wait() != 0:
                raise RuntimeError("ffmpeg encoding failed:\n" + err[-400:])
        except BaseException:
            if gen is not None:
                gen.close()          # shuts the worker pool down
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
    finally:
        if temp_concat_file and os.path.exists(temp_concat_file):
            try:
                os.remove(temp_concat_file)
            except Exception:
                pass
