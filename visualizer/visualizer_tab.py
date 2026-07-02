# -*- coding: utf-8 -*-
"""
TRAVKOD CODEs — Video Visualizer tab (Tab 4, next to AI Song)
=============================================================

Drop an image + an audio file, watch the LIVE PREVIEW, pick one of 12
visualizer styles (or build your own with Custom), add a movable/resizable
title, generate AI subtitles (CapCut-style captions), then export an MP4.

Runs standalone too:      python visualizer_tab.py

Integration (main app):   from visualizer.visualizer_tab import add_visualizer_tab, enable_dnd
                          enable_dnd(app)                 # once, on the main window
                          add_visualizer_tab(self.tabview)  # after the AI Song tab -> Tab 4

Dependencies:  pip install -r visualizer/requirements.txt
Optional:      pip install faster-whisper   (AI subtitles / speech-to-text)
"""

import os
import subprocess
import sys
import threading
import time
import traceback
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

try:
    from . import engine
except ImportError:
    import engine

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
try:
    import pygame
    HAS_SOUND = True
except ImportError:
    HAS_SOUND = False

TAB_TITLE = "🎬 Visualizer"
PREVIEW_FPS = 30
PREVIEW_W = 540

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".opus"}

LANGUAGES = {
    "Auto detect": None, "ខ្មែរ (Khmer)": "km", "English": "en",
    "ไทย (Thai)": "th", "Tiếng Việt": "vi", "中文": "zh",
    "日本語": "ja", "한국어": "ko",
}

ACCENT = "#8b5cf6"
ACCENT_HOVER = "#7c3aed"
CARD = ("#f1f1f4", "#17171f")
CARD_BORDER = ("#d4d4dc", "#2b2b3a")
MUTED = ("#6b7280", "#8b8b9e")


def _fmt_clock(t):
    t = max(0, int(t))
    return f"{t // 60}:{t % 60:02d}"


# --------------------------------------------------------------------------
# Drop zone
# --------------------------------------------------------------------------

class DropZone(ctk.CTkFrame):
    """Drop card: drag & drop a file, or click to browse."""

    def __init__(self, master, *, icon, title, subtitle, exts, on_file):
        super().__init__(master, corner_radius=14, fg_color=CARD,
                         border_width=2, border_color=CARD_BORDER)
        self.exts = exts
        self.on_file = on_file
        self.path = None

        self.icon_lbl = ctk.CTkLabel(self, text=icon, font=ctk.CTkFont(size=30))
        self.icon_lbl.pack(pady=(12, 0))
        self.title_lbl = ctk.CTkLabel(self, text=title,
                                      font=ctk.CTkFont(size=13, weight="bold"))
        self.title_lbl.pack()
        self.sub_lbl = ctk.CTkLabel(self, text=subtitle,
                                    font=ctk.CTkFont(size=11), text_color=MUTED)
        self.sub_lbl.pack()
        self.file_lbl = ctk.CTkLabel(self, text="No file selected",
                                     font=ctk.CTkFont(size=11),
                                     text_color=MUTED, wraplength=220)
        self.file_lbl.pack(pady=(0, 12))

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
                pass

    def _reset_border(self):
        self.configure(border_color=ACCENT if self.path else CARD_BORDER)

    def _on_drop(self, event):
        for p in self.tk.splitlist(event.data):
            if os.path.splitext(p)[1].lower() in self.exts:
                self.set_file(p)
                return
        self._reset_border()
        messagebox.showwarning("Unsupported file",
                               "Please drop: " + ", ".join(sorted(self.exts)))

    def _browse(self, _event=None):
        patterns = " ".join("*" + e for e in sorted(self.exts))
        p = filedialog.askopenfilename(filetypes=[("Supported files", patterns)])
        if p:
            self.set_file(p)

    def set_file(self, path):
        self.path = path
        self.file_lbl.configure(text=os.path.basename(path),
                                text_color=(ACCENT, "#c4b5fd"))
        self.configure(border_color=ACCENT)
        self.on_file(path)


# --------------------------------------------------------------------------
# Custom visualizer builder dialog
# --------------------------------------------------------------------------

class CustomStyleDialog(ctk.CTkToplevel):
    def __init__(self, master, cfg, on_change):
        super().__init__(master)
        self.title("Custom Visualizer Builder")
        self.geometry("380x520")
        self.attributes("-topmost", True)
        self.cfg = cfg
        self.on_change = on_change

        ctk.CTkLabel(self, text="⚙️ Custom Visualizer",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(16, 8))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20)

        def row(label):
            ctk.CTkLabel(body, text=label,
                         font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(10, 2))

        row("Element")
        self.element = ctk.CTkSegmentedButton(
            body, values=engine.CUSTOM_ELEMENTS, command=lambda _: self._apply())
        self.element.set(cfg["element"])
        self.element.pack(fill="x")

        row("Position")
        self.position = ctk.CTkSegmentedButton(
            body, values=engine.CUSTOM_POSITIONS, command=lambda _: self._apply())
        self.position.set(cfg["position"])
        self.position.pack(fill="x")

        row(f"Bar count: {cfg['count']}")
        self.count_lbl = body.winfo_children()[-1]
        self.count = ctk.CTkSlider(body, from_=16, to=128, number_of_steps=28,
                                   command=lambda _: self._apply())
        self.count.set(cfg["count"])
        self.count.pack(fill="x")

        row(f"Thickness: {cfg['thickness']}%")
        self.thick_lbl = body.winfo_children()[-1]
        self.thickness = ctk.CTkSlider(body, from_=10, to=100,
                                       command=lambda _: self._apply())
        self.thickness.set(cfg["thickness"])
        self.thickness.pack(fill="x")

        row(f"Height: {cfg['height']}%")
        self.height_lbl = body.winfo_children()[-1]
        self.height = ctk.CTkSlider(body, from_=10, to=90,
                                    command=lambda _: self._apply())
        self.height.set(cfg["height"])
        self.height.pack(fill="x")

        switches = ctk.CTkFrame(body, fg_color="transparent")
        switches.pack(fill="x", pady=(14, 0))
        self.mirror = ctk.CTkSwitch(switches, text="Mirror", command=self._apply,
                                    progress_color=ACCENT)
        self.reflection = ctk.CTkSwitch(switches, text="Reflection", command=self._apply,
                                        progress_color=ACCENT)
        self.rounded = ctk.CTkSwitch(switches, text="Rounded", command=self._apply,
                                     progress_color=ACCENT)
        for sw, key in ((self.mirror, "mirror"), (self.reflection, "reflection"),
                        (self.rounded, "rounded")):
            sw.pack(side="left", expand=True)
            if cfg[key]:
                sw.select()

        ctk.CTkButton(self, text="Done", fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self.destroy).pack(pady=14)

    def _apply(self):
        self.cfg.update(
            element=self.element.get(), position=self.position.get(),
            count=int(self.count.get()), thickness=int(self.thickness.get()),
            height=int(self.height.get()),
            mirror=bool(self.mirror.get()), reflection=bool(self.reflection.get()),
            rounded=bool(self.rounded.get()),
        )
        self.count_lbl.configure(text=f"Bar count: {self.cfg['count']}")
        self.thick_lbl.configure(text=f"Thickness: {self.cfg['thickness']}%")
        self.height_lbl.configure(text=f"Height: {self.cfg['height']}%")
        self.on_change()


# --------------------------------------------------------------------------
# Subtitle editor dialog
# --------------------------------------------------------------------------

class SubtitleEditor(ctk.CTkToplevel):
    def __init__(self, master, subtitles, on_save):
        super().__init__(master)
        self.title("Subtitle Editor (SRT)")
        self.geometry("560x600")
        self.attributes("-topmost", True)
        self.on_save = on_save

        ctk.CTkLabel(self, text="📝 Edit subtitles — SRT format",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(14, 4))
        ctk.CTkLabel(self, text="00:00:01,000 --> 00:00:04,000  then the text on the next line",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack()

        self.textbox = ctk.CTkTextbox(self, font=ctk.CTkFont(size=13))
        self.textbox.pack(fill="both", expand=True, padx=16, pady=10)
        self.textbox.insert("1.0", engine.format_srt(subtitles))

        ctk.CTkButton(self, text="💾 Save subtitles", fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, command=self._save).pack(pady=(0, 14))

    def _save(self):
        try:
            subs = engine.parse_srt(self.textbox.get("1.0", "end"))
        except Exception as exc:
            messagebox.showerror("SRT error", str(exc), parent=self)
            return
        self.on_save(subs)
        self.destroy()


# --------------------------------------------------------------------------
# Main tab
# --------------------------------------------------------------------------

class VisualizerFrame(ctk.CTkFrame):
    """The full Visualizer tab UI. Pack/grid it into any container."""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.image_path = None
        self.audio_path = None
        self.watermark_path = None
        self.subtitles = []
        self.custom_cfg = dict(engine.DEFAULT_CUSTOM)
        self.analysis = None            # engine.Analysis at PREVIEW_FPS
        self._analyzing = False
        self._cancel = threading.Event()
        self._worker = None
        self._last_output = None

        # preview state
        self._pv_assets = None
        self._pv_key = None
        self._pv_playing = False
        self._pv_t = 0.0
        self._pv_last_tick = None
        self._pv_photo = None
        self._sound_ready = False
        self._seek_dragging = False

        self._build_ui()
        self.after(66, self._preview_tick)

    # ---------------- UI ----------------

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=11, uniform="cols")
        self.grid_columnconfigure(1, weight=9, uniform="cols")
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=10)
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=10)

        self._build_left(left)
        self._build_right(right)

    def _build_left(self, left):
        ctk.CTkLabel(left, text="🎬 Video Visualizer",
                     font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(left, text="Drop an image + a song, style it live, export MP4.",
                     font=ctk.CTkFont(size=12), text_color=MUTED).pack(anchor="w", pady=(0, 8))

        drops = ctk.CTkFrame(left, fg_color="transparent")
        drops.pack(fill="x")
        drops.grid_columnconfigure((0, 1), weight=1, uniform="drop")
        self.image_zone = DropZone(drops, icon="🖼️", title="Drop Image",
                                   subtitle="PNG • JPG • WEBP",
                                   exts=IMAGE_EXTS, on_file=self._set_image)
        self.image_zone.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.audio_zone = DropZone(drops, icon="🎵", title="Drop Audio",
                                   subtitle="MP3 • WAV • M4A",
                                   exts=AUDIO_EXTS, on_file=self._set_audio)
        self.audio_zone.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # ---- style & look card ----
        card = self._card(left, "🎨 Style & Look")

        srow = ctk.CTkFrame(card, fg_color="transparent")
        srow.pack(fill="x", padx=14, pady=(2, 4))
        self.style_menu = ctk.CTkOptionMenu(
            srow, values=engine.STYLES, fg_color=ACCENT, button_color=ACCENT_HOVER,
            button_hover_color=ACCENT_HOVER, command=lambda _: None)
        self.style_menu.set(engine.STYLES[0])
        self.style_menu.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(srow, text="⚙️ Custom…", width=100,
                      fg_color=("#d1d5db", "#2b2b3a"),
                      hover_color=("#b8bcc4", "#3a3a4d"),
                      text_color=("#111827", "#e5e7eb"),
                      command=self._open_custom).pack(side="left", padx=(8, 0))

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=14, pady=(0, 4))
        grid.grid_columnconfigure((0, 1), weight=1)

        def opt(r, c, label, values, default):
            ctk.CTkLabel(grid, text=label, font=ctk.CTkFont(size=11, weight="bold")
                         ).grid(row=r, column=c, sticky="w", padx=(0, 8), pady=(6, 0))
            menu = ctk.CTkOptionMenu(grid, values=values, fg_color=ACCENT,
                                     button_color=ACCENT_HOVER,
                                     button_hover_color=ACCENT_HOVER)
            menu.set(default)
            menu.grid(row=r + 1, column=c, sticky="ew", padx=(0, 8))
            return menu

        self.res_menu = opt(0, 0, "Resolution", list(engine.RESOLUTIONS),
                            list(engine.RESOLUTIONS)[0])
        self.theme_menu = opt(0, 1, "Color Theme", list(engine.THEMES),
                              list(engine.THEMES)[0])
        self.fps_menu = opt(2, 0, "FPS", ["24", "30", "60"], "30")

        self.blur_slider = self._slider(card, "Background blur", 0, 30, 12)
        self.dark_slider = self._slider(card, "Background darken", 0, 80, 35)

        # ---- title card ----
        card = self._card(left, "🏷️ Title")
        self.title_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(card, text="Show title on the video", variable=self.title_var,
                        fg_color=ACCENT, hover_color=ACCENT_HOVER
                        ).pack(anchor="w", padx=14, pady=(2, 4))
        self.title_entry = ctk.CTkEntry(card, placeholder_text="Title text (ខ្មែរ OK)")
        self.title_entry.pack(fill="x", padx=14)
        trow = ctk.CTkFrame(card, fg_color="transparent")
        trow.pack(fill="x", padx=14, pady=(6, 2))
        trow.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(trow, text="Position", font=ctk.CTkFont(size=11, weight="bold")
                     ).grid(row=0, column=0, sticky="w")
        self.title_pos_menu = ctk.CTkOptionMenu(
            trow, values=engine.TITLE_POSITIONS, fg_color=ACCENT,
            button_color=ACCENT_HOVER, button_hover_color=ACCENT_HOVER)
        self.title_pos_menu.set("Bottom Center")
        self.title_pos_menu.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkLabel(trow, text="Size", font=ctk.CTkFont(size=11, weight="bold")
                     ).grid(row=0, column=1, sticky="w")
        self.title_size = ctk.CTkSlider(trow, from_=0.5, to=2.5,
                                        progress_color=ACCENT, button_color=ACCENT)
        self.title_size.set(1.0)
        self.title_size.grid(row=1, column=1, sticky="ew", pady=(8, 0))
        ctk.CTkFrame(card, fg_color="transparent", height=8).pack()

        # ---- subtitles card ----
        card = self._card(left, "💬 Subtitles (CapCut-style)")
        self.subs_var = ctk.BooleanVar(value=False)
        self.subs_check = ctk.CTkCheckBox(
            card, text="Show subtitles on the video", variable=self.subs_var,
            fg_color=ACCENT, hover_color=ACCENT_HOVER)
        self.subs_check.pack(anchor="w", padx=14, pady=(2, 4))

        srow = ctk.CTkFrame(card, fg_color="transparent")
        srow.pack(fill="x", padx=14)
        srow.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkLabel(srow, text="Language", font=ctk.CTkFont(size=11, weight="bold")
                     ).grid(row=0, column=0, sticky="w")
        self.lang_menu = ctk.CTkOptionMenu(srow, values=list(LANGUAGES),
                                           fg_color=ACCENT, button_color=ACCENT_HOVER,
                                           button_hover_color=ACCENT_HOVER)
        self.lang_menu.set("ខ្មែរ (Khmer)")
        self.lang_menu.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkLabel(srow, text="AI model", font=ctk.CTkFont(size=11, weight="bold")
                     ).grid(row=0, column=1, sticky="w")
        self.model_menu = ctk.CTkOptionMenu(srow, values=["tiny", "base", "small", "medium"],
                                            fg_color=ACCENT, button_color=ACCENT_HOVER,
                                            button_hover_color=ACCENT_HOVER)
        self.model_menu.set("small")
        self.model_menu.grid(row=1, column=1, sticky="ew", padx=(0, 6))
        ctk.CTkLabel(srow, text="Caption style", font=ctk.CTkFont(size=11, weight="bold")
                     ).grid(row=0, column=2, sticky="w")
        self.sub_style_menu = ctk.CTkOptionMenu(srow, values=engine.SUBTITLE_STYLES,
                                                fg_color=ACCENT, button_color=ACCENT_HOVER,
                                                button_hover_color=ACCENT_HOVER)
        self.sub_style_menu.set(engine.SUBTITLE_STYLES[0])
        self.sub_style_menu.grid(row=1, column=2, sticky="ew")

        brow = ctk.CTkFrame(card, fg_color="transparent")
        brow.pack(fill="x", padx=14, pady=(8, 4))
        self.gen_subs_btn = ctk.CTkButton(
            brow, text="🎙 Generate from audio (AI)", fg_color=ACCENT,
            hover_color=ACCENT_HOVER, command=self._generate_subs)
        self.gen_subs_btn.pack(side="left", fill="x", expand=True)
        for text, cmd in (("📝 Edit", self._edit_subs),
                          ("📂 Import SRT", self._import_srt),
                          ("💾 Export", self._export_srt)):
            ctk.CTkButton(brow, text=text, width=86,
                          fg_color=("#d1d5db", "#2b2b3a"),
                          hover_color=("#b8bcc4", "#3a3a4d"),
                          text_color=("#111827", "#e5e7eb"),
                          command=cmd).pack(side="left", padx=(6, 0))
        self.subs_info = ctk.CTkLabel(card, text="No subtitles yet.",
                                      font=ctk.CTkFont(size=11), text_color=MUTED)
        self.subs_info.pack(anchor="w", padx=14, pady=(0, 8))

        # ---- pro extras card ----
        card = self._card(left, "✨ Pro Extras")
        xrow = ctk.CTkFrame(card, fg_color="transparent")
        xrow.pack(fill="x", padx=14, pady=(2, 6))
        self.zoom_var = ctk.BooleanVar(value=False)
        self.pbar_var = ctk.BooleanVar(value=True)
        self.fade_var = ctk.BooleanVar(value=True)
        for text, var in (("Beat zoom", self.zoom_var),
                          ("Progress bar", self.pbar_var),
                          ("Fade in/out", self.fade_var)):
            ctk.CTkCheckBox(xrow, text=text, variable=var, fg_color=ACCENT,
                            hover_color=ACCENT_HOVER).pack(side="left", expand=True,
                                                           anchor="w")
        wrow = ctk.CTkFrame(card, fg_color="transparent")
        wrow.pack(fill="x", padx=14, pady=(0, 10))
        self.wm_btn = ctk.CTkButton(wrow, text="🖼 Add logo / watermark…", width=190,
                                    fg_color=("#d1d5db", "#2b2b3a"),
                                    hover_color=("#b8bcc4", "#3a3a4d"),
                                    text_color=("#111827", "#e5e7eb"),
                                    command=self._choose_watermark)
        self.wm_btn.pack(side="left")
        self.wm_corner_menu = ctk.CTkOptionMenu(
            wrow, values=["Top Left", "Top Right", "Bottom Left", "Bottom Right"],
            width=120, fg_color=ACCENT, button_color=ACCENT_HOVER,
            button_hover_color=ACCENT_HOVER)
        self.wm_corner_menu.set("Top Right")
        self.wm_corner_menu.pack(side="left", padx=(8, 0))

        if not HAS_DND:
            ctk.CTkLabel(left, text="ℹ️ Drag & drop needs 'pip install tkinterdnd2' — click a card to browse.",
                         font=ctk.CTkFont(size=11),
                         text_color=("#9a6700", "#d4a72c")).pack(anchor="w", pady=(6, 0))

    def _build_right(self, right):
        card = ctk.CTkFrame(right, corner_radius=16, fg_color=CARD,
                            border_width=1, border_color=CARD_BORDER)
        card.pack(fill="x")
        ctk.CTkLabel(card, text="▶ Live Preview",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w",
                                                                    padx=14, pady=(10, 4))
        self.preview_lbl = ctk.CTkLabel(card, text="Drop an image to start the preview",
                                        text_color=MUTED, height=300)
        self.preview_lbl.pack(padx=14, pady=(0, 6))

        transport = ctk.CTkFrame(card, fg_color="transparent")
        transport.pack(fill="x", padx=14, pady=(0, 12))
        self.play_btn = ctk.CTkButton(transport, text="▶", width=44, height=32,
                                      corner_radius=8, fg_color=ACCENT,
                                      hover_color=ACCENT_HOVER,
                                      font=ctk.CTkFont(size=15, weight="bold"),
                                      command=self._toggle_play)
        self.play_btn.pack(side="left")
        self.seek = ctk.CTkSlider(transport, from_=0, to=1,
                                  progress_color=ACCENT, button_color=ACCENT)
        self.seek.set(0)
        self.seek.pack(side="left", fill="x", expand=True, padx=10)
        self.seek.bind("<Button-1>", lambda e: self._set_seek_drag(True))
        self.seek.bind("<ButtonRelease-1>", self._seek_release)
        self.time_lbl = ctk.CTkLabel(transport, text="0:00 / 0:00",
                                     font=ctk.CTkFont(size=11), text_color=MUTED)
        self.time_lbl.pack(side="left")

        if not HAS_SOUND:
            ctk.CTkLabel(card, text="🔇 Preview sound needs 'pip install pygame' (video export always has audio).",
                         font=ctk.CTkFont(size=10),
                         text_color=("#9a6700", "#d4a72c")).pack(anchor="w",
                                                                 padx=14, pady=(0, 8))

        action = ctk.CTkFrame(right, fg_color="transparent")
        action.pack(fill="x", pady=(12, 4))
        self.render_btn = ctk.CTkButton(
            action, text="🚀  Create Video", height=46, corner_radius=12,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._start_render)
        self.render_btn.pack(side="left", fill="x", expand=True)
        self.cancel_btn = ctk.CTkButton(
            action, text="✖", height=46, width=54, corner_radius=12,
            fg_color=("#d1d5db", "#2b2b3a"), hover_color=("#b8bcc4", "#3a3a4d"),
            text_color=("#111827", "#e5e7eb"), command=self._cancel.set,
            state="disabled")
        self.cancel_btn.pack(side="left", padx=(8, 0))
        self.open_btn = ctk.CTkButton(
            action, text="📂 Open", height=46, width=90, corner_radius=12,
            fg_color=("#10b981", "#059669"), hover_color=("#0d9668", "#047852"),
            command=self._open_output, state="disabled")
        self.open_btn.pack(side="left", padx=(8, 0))

        self.progress = ctk.CTkProgressBar(right, height=10, corner_radius=6,
                                           progress_color=ACCENT)
        self.progress.set(0)
        self.progress.pack(fill="x", pady=(8, 0))
        self.status_lbl = ctk.CTkLabel(right, text="Ready — drop an image and audio.",
                                       font=ctk.CTkFont(size=12), text_color=MUTED,
                                       wraplength=380, justify="left")
        self.status_lbl.pack(anchor="w", pady=(6, 0))

    def _card(self, parent, title):
        card = ctk.CTkFrame(parent, corner_radius=14, fg_color=CARD,
                            border_width=1, border_color=CARD_BORDER)
        card.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(card, text=title,
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w",
                                                                    padx=14, pady=(10, 2))
        return card

    def _slider(self, card, label, lo, hi, default):
        ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=11, weight="bold")
                     ).pack(anchor="w", padx=14, pady=(6, 0))
        slider = ctk.CTkSlider(card, from_=lo, to=hi, progress_color=ACCENT,
                               button_color=ACCENT)
        slider.set(default)
        slider.pack(fill="x", padx=14, pady=(0, 8))
        return slider

    # ---------------- file handlers ----------------

    def _set_image(self, path):
        self.image_path = path
        self._pv_key = None
        self._status("Image loaded." if self.audio_path is None
                     else "Ready — press ▶ to preview or Create Video.")

    def _set_audio(self, path):
        self.audio_path = path
        self.analysis = None
        self._stop_sound()
        self._pv_playing = False
        self._pv_t = 0.0
        if not self.title_entry.get().strip():
            self.title_entry.insert(0, os.path.splitext(os.path.basename(path))[0])
        self._status("Analyzing audio…")
        self._analyzing = True
        threading.Thread(target=self._analyze_worker, args=(path,), daemon=True).start()

    def _analyze_worker(self, path):
        try:
            an = engine.analyze(path, PREVIEW_FPS)
            self.after(0, self._on_analysis, path, an)
        except Exception as exc:
            self.after(0, self._on_analysis_error, str(exc))

    def _on_analysis(self, path, an):
        if path != self.audio_path:
            return
        self.analysis = an
        self._analyzing = False
        self._pv_key = None
        self.seek.configure(to=max(0.1, an.duration))
        self._status("Ready — press ▶ to preview or Create Video. 🚀")

    def _on_analysis_error(self, msg):
        self._analyzing = False
        self._status("❌ Audio error.")
        messagebox.showerror("Audio error", msg)

    def _choose_watermark(self):
        p = filedialog.askopenfilename(
            filetypes=[("Image", "*.png *.jpg *.jpeg *.webp")])
        if p:
            self.watermark_path = p
            self.wm_btn.configure(text="🖼 " + os.path.basename(p)[:22])
            self._pv_key = None

    def _open_custom(self):
        self.style_menu.set("Custom")
        CustomStyleDialog(self, self.custom_cfg, lambda: None)

    # ---------------- subtitles ----------------

    def _generate_subs(self):
        if not self.audio_path:
            messagebox.showwarning("No audio", "Drop an audio file first.")
            return
        self.gen_subs_btn.configure(state="disabled", text="🎙 Working…")
        lang = LANGUAGES[self.lang_menu.get()]
        model = self.model_menu.get()

        def worker():
            try:
                subs = engine.transcribe(
                    self.audio_path, language=lang, model_size=model,
                    progress_cb=lambda m: self.after(0, self._status, "🎙 " + m))
                self.after(0, self._on_subs_ready, subs)
            except ImportError as exc:
                self.after(0, self._on_subs_error, str(exc), True)
            except Exception as exc:
                traceback.print_exc()
                self.after(0, self._on_subs_error, str(exc), False)

        threading.Thread(target=worker, daemon=True).start()

    def _on_subs_ready(self, subs):
        self.gen_subs_btn.configure(state="normal", text="🎙 Generate from audio (AI)")
        self.subtitles = subs
        if subs:
            self.subs_var.set(True)
            self.subs_info.configure(text=f"✅ {len(subs)} subtitle lines ready — tick 'Show subtitles'. Use 📝 Edit to fix words.")
            self._status(f"Subtitles ready: {len(subs)} lines.")
        else:
            self.subs_info.configure(text="No speech detected in this audio.")
            self._status("No speech detected.")

    def _on_subs_error(self, msg, is_install):
        self.gen_subs_btn.configure(state="normal", text="🎙 Generate from audio (AI)")
        self._status("Subtitle generation failed.")
        messagebox.showwarning("AI subtitles" if is_install else "Subtitle error", msg)

    def _edit_subs(self):
        SubtitleEditor(self, self.subtitles, self._on_subs_saved)

    def _on_subs_saved(self, subs):
        self.subtitles = subs
        self.subs_info.configure(text=f"✏️ {len(subs)} subtitle lines.")
        if subs:
            self.subs_var.set(True)

    def _import_srt(self):
        p = filedialog.askopenfilename(filetypes=[("SubRip subtitles", "*.srt"),
                                                  ("All files", "*.*")])
        if not p:
            return
        try:
            with open(p, encoding="utf-8-sig") as fh:
                self.subtitles = engine.parse_srt(fh.read())
        except Exception as exc:
            messagebox.showerror("SRT error", str(exc))
            return
        self.subs_var.set(bool(self.subtitles))
        self.subs_info.configure(text=f"📂 Imported {len(self.subtitles)} lines.")

    def _export_srt(self):
        if not self.subtitles:
            messagebox.showwarning("No subtitles", "Nothing to export yet.")
            return
        p = filedialog.asksaveasfilename(defaultextension=".srt",
                                         filetypes=[("SubRip subtitles", "*.srt")])
        if p:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(engine.format_srt(self.subtitles))
            self._status(f"Subtitles saved: {p}")

    # ---------------- options ----------------

    def _current_opts(self):
        return {
            "style": self.style_menu.get(),
            "size": engine.RESOLUTIONS[self.res_menu.get()],
            "fps": int(self.fps_menu.get()),
            "theme": self.theme_menu.get(),
            "blur": float(self.blur_slider.get()),
            "darken": float(self.dark_slider.get()) / 100.0,
            "beat_zoom": self.zoom_var.get(),
            "show_title": self.title_var.get(),
            "title_text": self.title_entry.get().strip(),
            "title_pos": self.title_pos_menu.get(),
            "title_scale": float(self.title_size.get()),
            "show_subs": self.subs_var.get(),
            "subtitles": self.subtitles,
            "sub_style": self.sub_style_menu.get(),
            "progress_bar": self.pbar_var.get(),
            "fade": self.fade_var.get(),
            "watermark_path": self.watermark_path,
            "watermark_corner": self.wm_corner_menu.get(),
            "watermark_opacity": 0.85,
            "custom": self.custom_cfg,
        }

    # ---------------- live preview ----------------

    def _preview_size(self):
        w, h = engine.RESOLUTIONS[self.res_menu.get()]
        pw = PREVIEW_W
        ph = int(pw * h / w)
        if ph > 340:
            ph = 340
            pw = int(ph * w / h)
        return (pw // 2 * 2, ph // 2 * 2)

    def _preview_assets(self, opts):
        if self.image_path is None or self.analysis is None:
            return None
        key = (self.image_path, self.audio_path, self._preview_size(),
               round(opts["blur"], 1), round(opts["darken"], 2),
               opts["beat_zoom"], opts["style"] in engine.NEEDS_CENTER_ART,
               self.watermark_path)
        if key != self._pv_key:
            try:
                self._pv_assets = engine.prepare_assets(
                    self.image_path, self.analysis, self._preview_size(), opts)
                self._pv_key = key
            except Exception:
                traceback.print_exc()
                return None
        return self._pv_assets

    def _preview_tick(self):
        try:
            self._preview_frame()
        except Exception:
            traceback.print_exc()
        self.after(40, self._preview_tick)

    def _preview_frame(self):
        if self.image_path is None:
            return
        an = self.analysis
        now = time.monotonic()
        if self._pv_playing and an is not None:
            if self._pv_last_tick is not None:
                self._pv_t += now - self._pv_last_tick
            if self._pv_t >= an.duration:
                self._pv_t = 0.0
                self._pause_preview()
        self._pv_last_tick = now

        opts = self._current_opts()
        if an is None:
            # image but no audio yet: show plain background
            try:
                frame = engine.build_background(
                    self.image_path, self._preview_size(),
                    opts["blur"], opts["darken"])
            except Exception:
                return
        else:
            assets = self._preview_assets(opts)
            if assets is None:
                return
            i = min(an.num_frames - 1, int(self._pv_t * PREVIEW_FPS))
            frame = engine.compose_frame(assets, i, opts)
            if not self._seek_dragging:
                self.seek.set(self._pv_t)
            self.time_lbl.configure(
                text=f"{_fmt_clock(self._pv_t)} / {_fmt_clock(an.duration)}")

        photo = ctk.CTkImage(light_image=frame, dark_image=frame, size=frame.size)
        self._pv_photo = photo
        self.preview_lbl.configure(image=photo, text="")

    def _toggle_play(self):
        if self.analysis is None:
            if self._analyzing:
                self._status("Still analyzing audio — a moment…")
            else:
                messagebox.showwarning("No audio", "Drop an audio file first.")
            return
        if self._pv_playing:
            self._pause_preview()
        else:
            self._pv_playing = True
            self._pv_last_tick = time.monotonic()
            self.play_btn.configure(text="⏸")
            self._start_sound(self._pv_t)

    def _pause_preview(self):
        self._pv_playing = False
        self.play_btn.configure(text="▶")
        self._stop_sound()

    def _set_seek_drag(self, flag):
        self._seek_dragging = flag

    def _seek_release(self, _event):
        self._seek_dragging = False
        if self.analysis is None:
            return
        self._pv_t = min(float(self.seek.get()), self.analysis.duration)
        if self._pv_playing:
            self._start_sound(self._pv_t)

    def _start_sound(self, t):
        if not HAS_SOUND or not self.audio_path:
            return
        try:
            if not self._sound_ready:
                pygame.mixer.init()
                self._sound_ready = True
            pygame.mixer.music.load(self.audio_path)
            pygame.mixer.music.play(start=t)
        except Exception:
            pass  # unsupported codec -> silent preview

    def _stop_sound(self):
        if HAS_SOUND and self._sound_ready:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass

    # ---------------- export ----------------

    def _status(self, text):
        self.status_lbl.configure(text=text)

    def _start_render(self):
        if self._worker and self._worker.is_alive():
            return
        if not self.image_path or not self.audio_path:
            messagebox.showwarning("Missing files",
                                   "Please add both an image and an audio file first.")
            return
        default_name = os.path.splitext(os.path.basename(self.audio_path))[0] + "_visualizer.mp4"
        out_path = filedialog.asksaveasfilename(
            defaultextension=".mp4", initialfile=default_name,
            filetypes=[("MP4 video", "*.mp4")])
        if not out_path:
            return

        self._pause_preview()
        opts = self._current_opts()
        if self.analysis is not None and self.analysis.fps == opts["fps"]:
            opts["_analysis"] = self.analysis

        self._cancel.clear()
        self._last_output = None
        self.render_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.open_btn.configure(state="disabled")
        self.progress.set(0)
        self._status("Rendering…")

        self._worker = threading.Thread(
            target=self._render_worker,
            args=(self.image_path, self.audio_path, out_path, opts), daemon=True)
        self._worker.start()

    def _render_worker(self, image_path, audio_path, out_path, opts):
        try:
            engine.render_video(
                image_path, audio_path, out_path, opts,
                progress_cb=lambda a, b: self.after(0, self._on_progress, a, b),
                cancel_event=self._cancel)
            self.after(0, self._on_done, out_path)
        except InterruptedError:
            self.after(0, self._on_cancelled)
        except Exception as exc:
            traceback.print_exc()
            self.after(0, self._on_error, str(exc))

    def _on_progress(self, done, total):
        self.progress.set(done / total)
        self._status(f"Rendering… frame {done}/{total} ({done * 100 // total}%)")

    def _on_done(self, out_path):
        self._last_output = out_path
        self.progress.set(1)
        self._status(f"✅ Done!  Saved: {out_path}")
        self.render_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.open_btn.configure(state="normal")

    def _on_cancelled(self):
        self.progress.set(0)
        self._status("Render cancelled.")
        self.render_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")

    def _on_error(self, msg):
        self.progress.set(0)
        self._status("❌ Render failed.")
        self.render_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        messagebox.showerror("Visualizer error", msg)

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
    """Add the Visualizer as a new tab on a CTkTabview (call after AI Song)."""
    tab = tabview.add(title)
    VisualizerFrame(tab).pack(fill="both", expand=True)
    return tab


def enable_dnd(root):
    """Enable tkinterdnd2 drag & drop on an existing CTk/Tk root window."""
    if not HAS_DND:
        return False
    try:
        root.TkdndVersion = TkinterDnD._require(root)
        return True
    except Exception:
        return False


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
    app.geometry("1240x820")
    app.minsize(1000, 680)
    VisualizerFrame(app).pack(fill="both", expand=True)
    app.mainloop()


if __name__ == "__main__":
    run_standalone()
