# -*- coding: utf-8 -*-
"""Pulse Rail Lyric Studio — master window (frameless, PyQt6)."""

import os

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (QButtonGroup, QComboBox, QFileDialog, QFrame,
                             QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                             QProgressBar, QPushButton, QScrollArea,
                             QSizePolicy, QSlider, QStackedWidget, QVBoxLayout,
                             QWidget)

from visualizer import templates as T

from . import theme
from .frameless import FramelessWindow
from .i18n import en, km, t
from .preview import PreviewPanel
from .title_bar import TitleBar

AUDIO_EXTS = (".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")

RESOLUTIONS = [
    ("2560 × 1440  QHD ★", (2560, 1440)),
    ("1920 × 1080  Full HD", (1920, 1080)),
    ("3840 × 2160  4K UHD", (3840, 2160)),
    ("1080 × 1920  Shorts 9:16", (1080, 1920)),
]


def card(title_key=None, title_text=None):
    box = QFrame()
    box.setObjectName("Card")
    lay = QVBoxLayout(box)
    lay.setContentsMargins(16, 14, 16, 16)
    lay.setSpacing(10)
    if title_key or title_text:
        lab = QLabel(title_text or t(title_key))
        lab.setObjectName("CardTitle")
        lay.addWidget(lab)
    return box, lay


class DropZone(QFrame):
    """Drag-and-drop target for audio / cover art."""

    def __init__(self, kind, title, hint, on_file, parent=None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(96)
        self._kind = kind
        self._on_file = on_file
        self.path = None

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(3)
        self._icon = QLabel("♪" if kind == "audio" else "▣")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet("font-size:22px;")
        self._title = QLabel(title)
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint = QLabel(hint)
        self._hint.setObjectName("Hint")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for w in (self._icon, self._title, self._hint):
            lay.addWidget(w)

    def _exts(self):
        return AUDIO_EXTS if self._kind == "audio" else IMAGE_EXTS

    def _hot(self, on):
        self.setProperty("hot", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._hot(True)

    def dragLeaveEvent(self, e):
        self._hot(False)

    def dropEvent(self, e):
        self._hot(False)
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if p.lower().endswith(self._exts()):
                self.set_path(p)
                break

    def mousePressEvent(self, e):
        filt = ("Audio (*.wav *.mp3 *.flac *.m4a *.aac *.ogg)"
                if self._kind == "audio"
                else "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        p, _ = QFileDialog.getOpenFileName(self, t("browse"), "", filt)
        if p:
            self.set_path(p)

    def set_path(self, p):
        self.path = p
        self._title.setText(os.path.basename(p))
        self._hint.setText(os.path.dirname(p) or "—")
        self._on_file(p)


class TemplateCard(QPushButton):
    """Selectable template tile."""

    def __init__(self, tpl, parent=None):
        super().__init__(parent)
        self.tpl = tpl
        self.setCheckable(True)
        self.setMinimumHeight(78)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)
        p = tpl.palette
        swatch = (f"qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                  f"stop:0 rgb{p.primary}, stop:1 rgb{p.secondary})")
        self.setStyleSheet(f"""
            QPushButton {{ text-align:left; padding:10px 12px 10px 56px; }}
            QPushButton:checked {{
                border:1px solid {theme.ACCENT};
                background:{theme.BG_ELEV};
            }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        dot = QLabel()
        dot.setFixedSize(QSize(30, 30))
        dot.setStyleSheet(f"background:{swatch}; border-radius:15px;")
        lay.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        txt = QVBoxLayout()
        txt.setSpacing(1)
        name = QLabel(f"{tpl.name}")
        name.setStyleSheet("font-weight:600;")
        sub = QLabel(f"{tpl.name_km} · {tpl.niche}")
        sub.setObjectName("Hint")
        txt.addWidget(name)
        txt.addWidget(sub)
        lay.addLayout(txt)
        lay.addStretch(1)


class MainWindow(FramelessWindow):
    def __init__(self):
        super().__init__(rounded=True)
        self.setWindowTitle(en("app_title"))
        self.resize(1320, 820)
        self.setMinimumSize(1040, 660)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("Root")
        root.addWidget(shell)

        outer = QVBoxLayout(shell)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = TitleBar(self)
        self.title_bar.close_requested.connect(self.close)
        outer.addWidget(self.title_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body, 1)

        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_main(), 1)

        outer.addWidget(self._build_status())
        self._select_page(0)
        self.preview.render()

    # ---------------- sidebar ----------------
    def _build_sidebar(self):
        bar = QFrame()
        bar.setObjectName("Sidebar")
        bar.setFixedWidth(theme.SIDEBAR_W)
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(0, 6, 0, 12)
        lay.setSpacing(0)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        def header(text):
            h = QLabel(text)
            h.setObjectName("NavHeader")
            lay.addWidget(h)

        def nav(idx, glyph, key):
            b = QPushButton(f"  {glyph}   {km(key)}  ·  {en(key)}")
            b.setObjectName("NavBtn")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, i=idx: self._select_page(i))
            self.nav_group.addButton(b, idx)
            lay.addWidget(b)
            return b

        header(km("nav_workspace") + "  ·  " + en("nav_workspace"))
        nav(0, "▤", "nav_files")
        nav(1, "◈", "nav_template")
        nav(2, "☰", "nav_lyrics")
        header(km("nav_output") + "  ·  " + en("nav_output"))
        nav(3, "▼", "nav_export")
        lay.addStretch(1)

        ver = QLabel("  v4.1.0 · TRAVKOD CODEs")
        ver.setObjectName("Hint")
        lay.addWidget(ver)
        return bar

    # ---------------- main area ----------------
    def _build_main(self):
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(16)

        # left: preview + transport
        left = QVBoxLayout()
        left.setSpacing(10)
        self.preview = PreviewPanel()
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding,
                                   QSizePolicy.Policy.Expanding)
        left.addWidget(self.preview, 1)
        left.addLayout(self._build_transport())
        lay.addLayout(left, 3)

        # right: paged settings
        self.pages = QStackedWidget()
        self.pages.setFixedWidth(392)
        for build in (self._page_files, self._page_template,
                      self._page_lyrics, self._page_export):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setWidget(build())
            self.pages.addWidget(scroll)
        lay.addWidget(self.pages)
        return wrap

    def _build_transport(self):
        row = QHBoxLayout()
        row.setSpacing(10)
        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedWidth(46)
        self.btn_play.setToolTip(t("play"))
        self.btn_play.clicked.connect(self._toggle_play)
        row.addWidget(self.btn_play)

        self.scrub = QSlider(Qt.Orientation.Horizontal)
        self.scrub.setRange(0, int(self.__class__._default_duration * 30))
        self.scrub.sliderMoved.connect(self.preview.seek)
        row.addWidget(self.scrub, 1)

        self.lbl_time = QLabel("00:00 / 03:30")
        self.lbl_time.setObjectName("Hint")
        row.addWidget(self.lbl_time)

        self.preview.frame_changed.connect(self._on_frame)
        return row

    _default_duration = 210.0

    # ---------------- pages ----------------
    def _page_files(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        box, inner = card("files_title")
        self.drop_audio = DropZone("audio", km("drop_audio"),
                                   en("drop_audio_h"), self._on_audio)
        self.drop_image = DropZone("image", km("drop_image"),
                                   en("drop_image_h"), self._on_image)
        inner.addWidget(self.drop_audio)
        inner.addWidget(self.drop_image)
        lay.addWidget(box)

        box2, in2 = card(title_text=t("track_title"))
        self.ed_title = QLineEdit()
        self.ed_title.setPlaceholderText(en("track_title"))
        self.ed_title.textChanged.connect(self._on_meta)
        self.ed_artist = QLineEdit()
        self.ed_artist.setPlaceholderText(en("artist"))
        self.ed_artist.textChanged.connect(self._on_meta)
        in2.addWidget(self.ed_title)
        in2.addWidget(self.ed_artist)
        lay.addWidget(box2)
        lay.addStretch(1)
        return page

    def _page_template(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        box, inner = card("tpl_title")
        hint = QLabel(t("tpl_hint"))
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        inner.addWidget(hint)

        self.tpl_group = QButtonGroup(self)
        self.tpl_group.setExclusive(True)
        for idx, key in enumerate(T.TEMPLATE_KEYS):
            tile = TemplateCard(T.TEMPLATES[key])
            tile.clicked.connect(lambda _, k=key: self._on_template(k))
            self.tpl_group.addButton(tile, idx)
            inner.addWidget(tile)
            if idx == 0:
                tile.setChecked(True)
        lay.addWidget(box)
        lay.addStretch(1)
        return page

    def _page_lyrics(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        box, inner = card("lyr_title")
        hint = QLabel(t("lyr_hint"))
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        inner.addWidget(hint)

        btn = QPushButton(t("lyr_import"))
        btn.clicked.connect(self._import_lyrics)
        inner.addWidget(btn)

        self.lbl_cues = QLabel(f"{t('lyr_cues')}: 0")
        self.lbl_cues.setObjectName("Hint")
        inner.addWidget(self.lbl_cues)
        lay.addWidget(box)
        lay.addStretch(1)
        return page

    def _page_export(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        box, inner = card("exp_title")
        grid = QGridLayout()
        grid.setVerticalSpacing(9)
        grid.setHorizontalSpacing(10)
        # Column 1 must absorb the slack. Without this a QComboBox sizes to
        # its longest item and pushes the whole card past its own border.
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)

        def combo(items):
            c = QComboBox()
            c.addItems(items)
            c.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            c.setMinimumContentsLength(8)
            c.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Fixed)
            return c

        grid.addWidget(QLabel(km("resolution")), 0, 0)
        self.cmb_res = combo([label for label, _ in RESOLUTIONS])
        self.cmb_res.currentIndexChanged.connect(self._on_res)
        grid.addWidget(self.cmb_res, 0, 1)

        grid.addWidget(QLabel(en("fps")), 1, 0)
        self.cmb_fps = combo(["30 fps", "60 fps", "24 fps"])
        grid.addWidget(self.cmb_fps, 1, 1)

        grid.addWidget(QLabel(km("quality")), 2, 0)
        self.cmb_q = combo(["BEST — x264 CRF 16", "FAST — GPU NVENC / QSV"])
        grid.addWidget(self.cmb_q, 2, 1)
        inner.addLayout(grid)

        self.btn_export = QPushButton(t("export_now"))
        self.btn_export.setObjectName("Primary")
        self.btn_export.clicked.connect(self._start_export)
        inner.addWidget(self.btn_export)

        self.btn_cancel = QPushButton(t("cancel"))
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._cancel_export)
        inner.addWidget(self.btn_cancel)

        self.bar = QProgressBar()
        self.bar.setValue(0)
        inner.addWidget(self.bar)

        self.lbl_export = QLabel("")
        self.lbl_export.setObjectName("Hint")
        self.lbl_export.setWordWrap(True)
        inner.addWidget(self.lbl_export)

        lay.addWidget(box)
        lay.addStretch(1)
        return page

    # ---------------- status ----------------
    def _build_status(self):
        bar = QFrame()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(30)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(8)
        self.status = QLabel(t("no_audio"))
        self.status.setObjectName("StatusText")
        lay.addWidget(self.status)
        lay.addStretch(1)
        for text in ("HarfBuzz ✓", "km th ko hi ta en", "bt709"):
            b = QLabel(text)
            b.setObjectName("Badge")
            lay.addWidget(b)
        return bar

    # ---------------- behaviour ----------------
    def _select_page(self, idx):
        self.pages.setCurrentIndex(idx)
        btn = self.nav_group.button(idx)
        if btn:
            btn.setChecked(True)

    def _toggle_play(self):
        if self.preview.playing:
            self.preview.pause()
            self.btn_play.setText("▶")
        else:
            self.preview.play()
            self.btn_play.setText("❚❚")

    def _on_frame(self, i):
        self.scrub.setValue(i)
        sec = i / max(1, self.preview.fps)
        dur = self.preview.duration
        self.lbl_time.setText(
            f"{int(sec)//60:02d}:{int(sec)%60:02d} / "
            f"{int(dur)//60:02d}:{int(dur)%60:02d}")

    def _on_template(self, key):
        self.preview.template_key = key
        self.preview.render()
        self.status.setText(T.TEMPLATES[key].name)

    def _on_res(self, idx):
        self.preview.master_size = RESOLUTIONS[idx][1]
        self.preview.render()

    def _on_meta(self):
        self.preview.title = self.ed_title.text()
        self.preview.artist = self.ed_artist.text()
        self.preview.render()

    def _on_audio(self, path):
        self.status.setText(f"{km('ready')} · {os.path.basename(path)}")
        try:
            from visualizer import engine
            an = engine.analyze([path], self.preview.fps)
            self.preview.spectra = an.spectra
            self.preview.duration = an.duration
            self.scrub.setRange(0, max(1, an.num_frames - 1))
        except Exception as exc:                      # keep the UI usable
            self.status.setText(f"Analyze failed: {exc}")
        self.preview.render()

    def _on_image(self, path):
        from PIL import Image
        try:
            self.preview.art = Image.open(path)
        except Exception as exc:
            self.status.setText(f"Image failed: {exc}")
            return
        self.preview.render()

    # ---------------- export ----------------
    def _start_export(self):
        if getattr(self, "_worker", None) and self._worker.isRunning():
            return
        audio = self.drop_audio.path
        if not audio:
            self._select_page(0)
            self.status.setText(t("no_audio"))
            self.lbl_export.setText(t("no_audio"))
            return

        default = os.path.splitext(os.path.basename(audio))[0] + ".mp4"
        out, _ = QFileDialog.getSaveFileName(
            self, en("export_now"), default, "MP4 video (*.mp4)")
        if not out:
            return

        from .exporter import ExportJob, ExportWorker
        job = ExportJob(
            audio_path=audio,
            out_path=out,
            template_key=self.preview.template_key,
            image_path=self.drop_image.path,
            size=RESOLUTIONS[self.cmb_res.currentIndex()][1],
            fps=int(self.cmb_fps.currentText().split()[0]),
            use_gpu=self.cmb_q.currentIndex() == 1,
            title=self.ed_title.text(),
            artist=self.ed_artist.text(),
            tracks=tuple(self.preview.tracks),
            cues=tuple(self.preview.cues),
            font_family=self.preview.font_family,
        )

        self._worker = ExportWorker(job, self)
        self._worker.stage.connect(self.lbl_export.setText)
        self._worker.progress.connect(self._on_export_progress)
        self._worker.finished_ok.connect(self._on_export_done)
        self._worker.failed.connect(self._on_export_failed)
        self._worker.cancelled.connect(self._on_export_cancelled)

        self.preview.pause()
        self.btn_play.setText("▶")
        self._set_exporting(True)
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self._worker.start()

    def _set_exporting(self, on):
        self.btn_export.setEnabled(not on)
        self.btn_cancel.setVisible(on)
        for w in (self.cmb_res, self.cmb_fps, self.cmb_q):
            w.setEnabled(not on)

    def _cancel_export(self):
        if getattr(self, "_worker", None):
            self.lbl_export.setText("Cancelling…")
            self._worker.cancel()

    def _on_export_progress(self, done, total):
        pct = int(done * 100 / max(1, total))
        self.bar.setValue(pct)
        self.lbl_export.setText(f"{done} / {total} frames  ·  {pct}%")
        self.status.setText(f"{km('export_now')} {pct}%")

    def _on_export_done(self, path):
        self._set_exporting(False)
        self.bar.setValue(100)
        self.lbl_export.setText(f"✅ {os.path.basename(path)}")
        self.status.setText(f"{km('ready')} · {path}")

    def _on_export_failed(self, msg):
        self._set_exporting(False)
        self.bar.setValue(0)
        self.lbl_export.setText(f"❌ {msg}")
        self.status.setText("Export failed")

    def _on_export_cancelled(self):
        self._set_exporting(False)
        self.bar.setValue(0)
        self.lbl_export.setText("Cancelled")
        self.status.setText(t("ready"))

    def closeEvent(self, event):
        w = getattr(self, "_worker", None)
        if w and w.isRunning():
            w.cancel()
            w.wait(3000)
        super().closeEvent(event)

    def _import_lyrics(self):
        p, _ = QFileDialog.getOpenFileName(
            self, en("lyr_import"), "", "Lyrics (*.lrc *.srt *.txt)")
        if not p:
            return
        from visualizer import engine
        raw = open(p, encoding="utf-8", errors="replace").read()
        cues = engine.parse_srt(raw) if p.lower().endswith(".srt") \
            else _parse_lrc(raw)
        self.preview.cues = cues
        self.lbl_cues.setText(f"{t('lyr_cues')}: {len(cues)}")
        self.preview.render()


def _parse_lrc(raw):
    """Minimal LRC reader -> [(start, end, text)] with inferred end times."""
    import re
    pat = re.compile(r"\[(\d+):(\d+)(?:[.:](\d+))?\]")
    rows = []
    for line in raw.splitlines():
        stamps = list(pat.finditer(line))
        if not stamps:
            continue
        text = line[stamps[-1].end():].strip()
        if not text:
            continue
        for m in stamps:
            mm, ss, frac = m.group(1), m.group(2), m.group(3) or "0"
            start = int(mm) * 60 + int(ss) + float(f"0.{frac}")
            rows.append((start, text))
    rows.sort(key=lambda r: r[0])
    out = []
    for idx, (start, text) in enumerate(rows):
        end = rows[idx + 1][0] - 0.05 if idx + 1 < len(rows) else start + 4.0
        out.append((start, max(start + 0.4, end), text))
    return out
