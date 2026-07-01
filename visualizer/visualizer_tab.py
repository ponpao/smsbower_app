# -*- coding: utf-8 -*-
"""
TRAVKOD CODEs — Video Visualizer tab (Tab 4)
============================================

Drop an image + an audio file, pick a style, and render a music-visualizer
video (MP4).  Designed as a modern CustomTkinter tab that plugs into the main
app's tabview right next to the "AI Song" tab, and it can also run standalone:

    python visualizer_tab.py

Integration (inside the main app, after the AI Song tab is added):

    from visualizer.visualizer_tab import add_visualizer_tab
    add_visualizer_tab(self.tabview)          # becomes Tab 4

Dependencies:
    pip install customtkinter pillow numpy imageio-ffmpeg tkinterdnd2

tkinterdnd2 is optional — without it the drop zones still work as
click-to-browse buttons.  imageio-ffmpeg bundles an ffmpeg binary, so no
system ffmpeg install is needed.
"""

import math
import os
import subprocess
import sys
import threading
import traceback
from tkinter import filedialog, messagebox

import numpy as np
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

TAB_TITLE = "🎬 Visualizer"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".opus"}

RESOLUTIONS = {
    "YouTube 1080p (1920×1080)": (1920, 1080),
    "HD 720p (1280×720)": (1280, 720),
    "Square (1080×1080)": (1080, 1080),
    "TikTok / Reels (1080×1920)": (1080, 1920),
}

THEMES = {
    "Neon Purple": ((168, 85, 247), (59, 130, 246)),
    "Cyber Cyan": ((34, 211, 238), (16, 185, 129)),
    "Sunset": ((251, 146, 60), (236, 72, 153)),
    "Emerald": ((52, 211, 153), (250, 204, 21)),
    "Pure White": ((245, 245, 245), (160, 160, 160)),
}

STYLES = ["Neon Bars", "Circular Spectrum", "Waveform"]

SAMPLE_RATE = 44100
FFT_SIZE = 2048
NUM_BARS = 64


# --------------------------------------------------------------------------
# ffmpeg helpers
# --------------------------------------------------------------------------

def _no_window():
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def ffmpeg_exe():
    """Locate ffmpeg: bundled via imageio-ffmpeg first, then PATH."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def load_audio_mono(path):
    """Decode any audio file to mono float32 PCM at SAMPLE_RATE."""
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


# --------------------------------------------------------------------------
# Audio analysis
# --------------------------------------------------------------------------

def compute_spectra(samples, fps):
    """Per-video-frame, log-spaced spectrum magnitudes normalized to 0..1.

    Returns (spectra[num_frames, NUM_BARS], num_frames).
    """
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

    # Perceptual scaling + global normalization
    spectra = np.log1p(spectra * 10.0)
    peak = np.percentile(spectra, 99.5)
    if peak > 0:
        spectra = np.clip(spectra / peak, 0.0, 1.0) ** 0.75

    # Temporal smoothing: fast attack, slow decay
    for i in range(1, num_frames):
        spectra[i] = np.maximum(spectra[i], spectra[i - 1] * 0.80)
    return spectra, num_frames


# --------------------------------------------------------------------------
# Frame drawing
# --------------------------------------------------------------------------

def _lerp_color(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def build_background(image_path, size, blur, darken):
    """Cover-crop the dropped image to the video size, blur + darken it."""
    img = Image.open(image_path).convert("RGB")
    bg = ImageOps.fit(img, size, Image.LANCZOS)
    if blur > 0:
        bg = bg.filter(ImageFilter.GaussianBlur(blur))
    if darken > 0:
        bg = ImageEnhance.Brightness(bg).enhance(1.0 - darken)
    return bg


def build_center_art(image_path, size):
    """Round 'album art' disc used by the Circular Spectrum style."""
    d = int(min(size) * 0.34)
    art = ImageOps.fit(Image.open(image_path).convert("RGB"), (d, d), Image.LANCZOS)
    mask = Image.new("L", (d * 4, d * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, d * 4, d * 4), fill=255)
    art.putalpha(mask.resize((d, d), Image.LANCZOS))
    return art


def _load_font(px):
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except Exception:
            continue
    return ImageFont.load_default()


def draw_bars(frame, values, c1, c2):
    w, h = frame.size
    draw = ImageDraw.Draw(frame, "RGBA")
    n = len(values)
    margin = int(w * 0.06)
    span = w - 2 * margin
    slot = span / n
    bar_w = max(3, int(slot * 0.62))
    base_y = int(h * 0.86)
    max_h = int(h * 0.52)
    for i, v in enumerate(values):
        x = int(margin + i * slot + (slot - bar_w) / 2)
        bh = max(3, int(v * max_h))
        color = _lerp_color(c1, c2, i / max(1, n - 1))
        draw.rounded_rectangle(
            (x, base_y - bh, x + bar_w, base_y), radius=bar_w // 2, fill=color + (235,)
        )
        # mirrored reflection below the baseline
        rh = int(bh * 0.28)
        if rh > 2:
            draw.rounded_rectangle(
                (x, base_y + 6, x + bar_w, base_y + 6 + rh),
                radius=bar_w // 2, fill=color + (60,),
            )


def draw_circular(frame, values, c1, c2, center_art, bass):
    w, h = frame.size
    cx, cy = w // 2, int(h * 0.46)
    draw = ImageDraw.Draw(frame, "RGBA")
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
        color = _lerp_color(c1, c2, i / max(1, n - 1))
        draw.line((x1, y1, x2, y2), fill=color + (235,), width=max(3, int(min(w, h) * 0.006)))
    # pulsing round art in the middle
    scale = 1.0 + 0.06 * bass
    d = int(center_art.width * scale)
    art = center_art.resize((d, d), Image.LANCZOS)
    ring = int(d * 1.04)
    draw.ellipse(
        (cx - ring // 2, cy - ring // 2, cx + ring // 2, cy + ring // 2),
        outline=_lerp_color(c1, c2, 0.5) + (200,), width=max(3, d // 90),
    )
    frame.paste(art, (cx - d // 2, cy - d // 2), art)


def draw_waveform(frame, samples, pos, c1, c2):
    w, h = frame.size
    draw = ImageDraw.Draw(frame, "RGBA")
    mid_y = int(h * 0.55)
    amp = int(h * 0.17)
    win = SAMPLE_RATE // 24
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
    glow = [(x, y + 2) for x, y in pts]
    draw.line(glow, fill=c2 + (90,), width=max(5, h // 180), joint="curve")


def draw_title(frame, title, c1):
    w, h = frame.size
    font = _load_font(max(20, int(h * 0.038)))
    draw = ImageDraw.Draw(frame, "RGBA")
    box = draw.textbbox((0, 0), title, font=font)
    tw = box[2] - box[0]
    x, y = (w - tw) // 2, int(h * 0.905)
    draw.text((x + 2, y + 2), title, font=font, fill=(0, 0, 0, 160))
    draw.text((x, y), title, font=font, fill=(245, 245, 245, 235))
    draw.rounded_rectangle(
        (x - 14, y - 8, x + tw + 14, y + (box[3] - box[1]) + 14),
        radius=10, outline=c1 + (120,), width=2,
    )


# --------------------------------------------------------------------------
# Renderer (runs on a worker thread)
# --------------------------------------------------------------------------

def render_video(image_path, audio_path, out_path, *, style, size, fps, theme,
                 blur, darken, show_title, progress_cb, cancel_event):
    c1, c2 = THEMES[theme]
    samples = load_audio_mono(audio_path)
    spectra, num_frames = compute_spectra(samples, fps)
    bass = spectra[:, :6].mean(axis=1)

    background = build_background(image_path, size, blur, darken)
    center_art = build_center_art(image_path, size) if style == "Circular Spectrum" else None
    title = os.path.splitext(os.path.basename(audio_path))[0] if show_title else None

    w, h = size
    cmd = [
        ffmpeg_exe(), "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
        "-i", audio_path,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
        out_path,
    ]
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=_no_window()
    )
    try:
        hop = SAMPLE_RATE / fps
        for i in range(num_frames):
            if cancel_event.is_set():
                raise InterruptedError("cancelled")
            frame = background.copy()
            if style == "Neon Bars":
                draw_bars(frame, spectra[i], c1, c2)
            elif style == "Circular Spectrum":
                draw_circular(frame, spectra[i], c1, c2, center_art, float(bass[i]))
            else:
                draw_waveform(frame, samples, int(i * hop), c1, c2)
            if title:
                draw_title(frame, title, c1)
            proc.stdin.write(frame.tobytes())
            if i % 5 == 0 or i == num_frames - 1:
                progress_cb(i + 1, num_frames)
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


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------

ACCENT = "#8b5cf6"
ACCENT_HOVER = "#7c3aed"
CARD = ("#f1f1f4", "#17171f")
CARD_BORDER = ("#d4d4dc", "#2b2b3a")


class DropZone(ctk.CTkFrame):
    """A modern dashed-look drop card: drag & drop a file, or click to browse."""

    def __init__(self, master, *, icon, title, subtitle, exts, on_file):
        super().__init__(
            master, corner_radius=16, fg_color=CARD,
            border_width=2, border_color=CARD_BORDER,
        )
        self.exts = exts
        self.on_file = on_file
        self.path = None

        self.icon_lbl = ctk.CTkLabel(self, text=icon, font=ctk.CTkFont(size=40))
        self.icon_lbl.pack(pady=(22, 4))
        self.title_lbl = ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=15, weight="bold"))
        self.title_lbl.pack()
        self.sub_lbl = ctk.CTkLabel(
            self, text=subtitle, font=ctk.CTkFont(size=12),
            text_color=("#6b7280", "#8b8b9e"),
        )
        self.sub_lbl.pack(pady=(2, 4))
        self.file_lbl = ctk.CTkLabel(
            self, text="No file selected", font=ctk.CTkFont(size=12),
            text_color=("#6b7280", "#8b8b9e"), wraplength=260,
        )
        self.file_lbl.pack(pady=(0, 6))
        self.preview_lbl = None

        for widget in (self, self.icon_lbl, self.title_lbl, self.sub_lbl, self.file_lbl):
            widget.bind("<Button-1>", self._browse)
            widget.configure(cursor="hand2")

        if HAS_DND:
            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind("<<Drop>>", self._on_drop)
                self.dnd_bind("<<DropEnter>>", lambda e: self.configure(border_color=ACCENT))
                self.dnd_bind("<<DropLeave>>", lambda e: self._reset_border())
            except Exception:
                pass  # root window not DnD-enabled; browse still works

    def _reset_border(self):
        self.configure(border_color=ACCENT if self.path else CARD_BORDER)

    def _on_drop(self, event):
        paths = self.tk.splitlist(event.data)
        for p in paths:
            if os.path.splitext(p)[1].lower() in self.exts:
                self.set_file(p)
                return
        self._reset_border()
        messagebox.showwarning(
            "Unsupported file",
            "Please drop a file of type: " + ", ".join(sorted(self.exts)),
        )

    def _browse(self, _event=None):
        patterns = " ".join("*" + e for e in sorted(self.exts))
        p = filedialog.askopenfilename(filetypes=[("Supported files", patterns)])
        if p:
            self.set_file(p)

    def set_file(self, path):
        self.path = path
        self.file_lbl.configure(text=os.path.basename(path), text_color=(ACCENT, "#c4b5fd"))
        self.configure(border_color=ACCENT)
        if os.path.splitext(path)[1].lower() in IMAGE_EXTS:
            self._show_preview(path)
        self.on_file(path)

    def _show_preview(self, path):
        try:
            img = Image.open(path)
            img.thumbnail((220, 120), Image.LANCZOS)
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            if self.preview_lbl is None:
                self.preview_lbl = ctk.CTkLabel(self, text="")
                self.preview_lbl.pack(pady=(0, 12))
            self.preview_lbl.configure(image=photo)
            self.preview_lbl.image = photo
        except Exception:
            pass


class VisualizerFrame(ctk.CTkFrame):
    """The full Visualizer tab UI. Pack/grid it into any container."""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.image_path = None
        self.audio_path = None
        self._cancel = threading.Event()
        self._worker = None
        self._last_output = None
        self._build_ui()

    # ---------------- UI construction ----------------

    def _build_ui(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        body = scroll

        header = ctk.CTkFrame(body, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(18, 6))
        ctk.CTkLabel(
            header, text="🎬 Video Visualizer",
            font=ctk.CTkFont(size=26, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Drop an image and a song — get a music-visualizer video for YouTube or TikTok.",
            font=ctk.CTkFont(size=13), text_color=("#6b7280", "#8b8b9e"),
        ).pack(anchor="w", pady=(2, 0))

        # Drop zones
        drops = ctk.CTkFrame(body, fg_color="transparent")
        drops.pack(fill="x", padx=24, pady=10)
        drops.grid_columnconfigure((0, 1), weight=1, uniform="drop")

        self.image_zone = DropZone(
            drops, icon="🖼️", title="Drop Image Here",
            subtitle="PNG • JPG • WEBP — used as the video background",
            exts=IMAGE_EXTS, on_file=self._set_image,
        )
        self.image_zone.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.audio_zone = DropZone(
            drops, icon="🎵", title="Drop Audio Here",
            subtitle="MP3 • WAV • M4A — e.g. your AI Song export",
            exts=AUDIO_EXTS, on_file=self._set_audio,
        )
        self.audio_zone.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        # Settings card
        card = ctk.CTkFrame(body, corner_radius=16, fg_color=CARD,
                            border_width=1, border_color=CARD_BORDER)
        card.pack(fill="x", padx=24, pady=8)
        card.grid_columnconfigure((0, 1, 2, 3), weight=1)

        def option(col, label, values, default):
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=12, weight="bold")).grid(
                row=0, column=col, sticky="w", padx=16, pady=(14, 2))
            menu = ctk.CTkOptionMenu(
                card, values=values, fg_color=ACCENT, button_color=ACCENT_HOVER,
                button_hover_color=ACCENT_HOVER,
            )
            menu.set(default)
            menu.grid(row=1, column=col, sticky="ew", padx=16, pady=(0, 10))
            return menu

        self.style_menu = option(0, "Style", STYLES, STYLES[0])
        self.res_menu = option(1, "Resolution", list(RESOLUTIONS), list(RESOLUTIONS)[0])
        self.theme_menu = option(2, "Color Theme", list(THEMES), list(THEMES)[0])
        self.fps_menu = option(3, "FPS", ["24", "30", "60"], "30")

        ctk.CTkLabel(card, text="Background blur", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=16, pady=(4, 0))
        self.blur_slider = ctk.CTkSlider(card, from_=0, to=30, number_of_steps=30,
                                         progress_color=ACCENT, button_color=ACCENT)
        self.blur_slider.set(12)
        self.blur_slider.grid(row=3, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 12))

        ctk.CTkLabel(card, text="Background darken", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=2, column=2, columnspan=2, sticky="w", padx=16, pady=(4, 0))
        self.dark_slider = ctk.CTkSlider(card, from_=0, to=80, number_of_steps=80,
                                         progress_color=ACCENT, button_color=ACCENT)
        self.dark_slider.set(35)
        self.dark_slider.grid(row=3, column=2, columnspan=2, sticky="ew", padx=16, pady=(0, 12))

        self.title_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            card, text="Show song title on the video", variable=self.title_var,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 14))

        # Action row
        action = ctk.CTkFrame(body, fg_color="transparent")
        action.pack(fill="x", padx=24, pady=(6, 4))

        self.render_btn = ctk.CTkButton(
            action, text="🚀  Create Video", height=46, corner_radius=12,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._start_render,
        )
        self.render_btn.pack(side="left", fill="x", expand=True)

        self.cancel_btn = ctk.CTkButton(
            action, text="✖  Cancel", height=46, width=120, corner_radius=12,
            fg_color=("#d1d5db", "#2b2b3a"), hover_color=("#b8bcc4", "#3a3a4d"),
            text_color=("#111827", "#e5e7eb"), command=self._cancel_render, state="disabled",
        )
        self.cancel_btn.pack(side="left", padx=(10, 0))

        self.open_btn = ctk.CTkButton(
            action, text="📂  Open Video", height=46, width=140, corner_radius=12,
            fg_color=("#10b981", "#059669"), hover_color=("#0d9668", "#047852"),
            command=self._open_output, state="disabled",
        )
        self.open_btn.pack(side="left", padx=(10, 0))

        # Progress
        prog = ctk.CTkFrame(body, fg_color="transparent")
        prog.pack(fill="x", padx=24, pady=(4, 20))
        self.progress = ctk.CTkProgressBar(prog, height=10, corner_radius=6, progress_color=ACCENT)
        self.progress.set(0)
        self.progress.pack(fill="x")
        self.status_lbl = ctk.CTkLabel(
            prog, text="Ready — drop an image and an audio file to begin.",
            font=ctk.CTkFont(size=12), text_color=("#6b7280", "#8b8b9e"),
        )
        self.status_lbl.pack(anchor="w", pady=(6, 0))

        if not HAS_DND:
            ctk.CTkLabel(
                prog, text="ℹ️ Drag & drop needs 'pip install tkinterdnd2' — click a card to browse instead.",
                font=ctk.CTkFont(size=11), text_color=("#9a6700", "#d4a72c"),
            ).pack(anchor="w", pady=(4, 0))

    # ---------------- callbacks ----------------

    def _set_image(self, path):
        self.image_path = path
        self._update_status()

    def _set_audio(self, path):
        self.audio_path = path
        self._update_status()

    def _update_status(self):
        if self.image_path and self.audio_path:
            self.status_lbl.configure(text="Ready to render — press Create Video. 🚀")
        elif self.image_path:
            self.status_lbl.configure(text="Image loaded — now drop an audio file.")
        elif self.audio_path:
            self.status_lbl.configure(text="Audio loaded — now drop an image.")

    def _start_render(self):
        if self._worker and self._worker.is_alive():
            return
        if not self.image_path or not self.audio_path:
            messagebox.showwarning("Missing files", "Please add both an image and an audio file first.")
            return
        default_name = os.path.splitext(os.path.basename(self.audio_path))[0] + "_visualizer.mp4"
        out_path = filedialog.asksaveasfilename(
            defaultextension=".mp4", initialfile=default_name,
            filetypes=[("MP4 video", "*.mp4")],
        )
        if not out_path:
            return

        self._cancel.clear()
        self._last_output = None
        self.render_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.open_btn.configure(state="disabled")
        self.progress.set(0)
        self.status_lbl.configure(text="Analyzing audio…")

        params = dict(
            style=self.style_menu.get(),
            size=RESOLUTIONS[self.res_menu.get()],
            fps=int(self.fps_menu.get()),
            theme=self.theme_menu.get(),
            blur=float(self.blur_slider.get()),
            darken=float(self.dark_slider.get()) / 100.0,
            show_title=self.title_var.get(),
        )
        self._worker = threading.Thread(
            target=self._render_worker,
            args=(self.image_path, self.audio_path, out_path, params),
            daemon=True,
        )
        self._worker.start()

    def _render_worker(self, image_path, audio_path, out_path, params):
        def progress_cb(done, total):
            self.after(0, self._on_progress, done, total)

        try:
            render_video(
                image_path, audio_path, out_path,
                progress_cb=progress_cb, cancel_event=self._cancel, **params,
            )
            self.after(0, self._on_done, out_path)
        except InterruptedError:
            self.after(0, self._on_cancelled)
        except Exception as exc:
            traceback.print_exc()
            self.after(0, self._on_error, str(exc))

    def _on_progress(self, done, total):
        self.progress.set(done / total)
        self.status_lbl.configure(text=f"Rendering… frame {done}/{total} ({done * 100 // total}%)")

    def _on_done(self, out_path):
        self._last_output = out_path
        self.progress.set(1)
        self.status_lbl.configure(text=f"✅ Done!  Saved: {out_path}")
        self.render_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.open_btn.configure(state="normal")

    def _on_cancelled(self):
        self.progress.set(0)
        self.status_lbl.configure(text="Render cancelled.")
        self.render_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")

    def _on_error(self, msg):
        self.progress.set(0)
        self.status_lbl.configure(text="❌ Render failed.")
        self.render_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        messagebox.showerror("Visualizer error", msg)

    def _cancel_render(self):
        self._cancel.set()

    def _open_output(self):
        if not self._last_output or not os.path.exists(self._last_output):
            return
        if os.name == "nt":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(self._last_output)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", self._last_output])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(self._last_output)])


# --------------------------------------------------------------------------
# Integration helpers
# --------------------------------------------------------------------------

def add_visualizer_tab(tabview, title=TAB_TITLE):
    """Add the Visualizer as a new tab on a CTkTabview.

    Call it right after the AI Song tab is added so it becomes Tab 4:

        self.tabview.add("AI Song")            # Tab 3
        add_visualizer_tab(self.tabview)       # Tab 4  ← new
    """
    tab = tabview.add(title)
    VisualizerFrame(tab).pack(fill="both", expand=True)
    return tab


def enable_dnd(root):
    """Enable tkinterdnd2 on an existing CTk/Tk root window.

    Call once on the main window BEFORE creating the Visualizer tab so the
    drop zones accept drag & drop:

        from visualizer.visualizer_tab import enable_dnd
        enable_dnd(app)   # app = your ctk.CTk() main window
    """
    if not HAS_DND:
        return False
    try:
        root.TkdndVersion = TkinterDnD._require(root)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# Standalone launcher (modern app window)
# --------------------------------------------------------------------------

def run_standalone():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

    if HAS_DND:
        class App(ctk.CTk, TkinterDnD.DnDWrapper):
            def __init__(self):
                super().__init__()
                self.TkdndVersion = TkinterDnD._require(self)
    else:
        App = ctk.CTk

    app = App()
    app.title("TRAVKOD CODEs — Video Visualizer")
    app.geometry("1100x780")
    app.minsize(880, 640)
    VisualizerFrame(app).pack(fill="both", expand=True)
    app.mainloop()


if __name__ == "__main__":
    run_standalone()
