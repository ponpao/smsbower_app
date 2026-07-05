"""
main_window_ui.py — Widget construction for Magic Studio.

Builds the frameless dark window, the custom title bar (app title + live
CPU/RAM + window controls) and the five tab panels. This file only *creates*
and exposes widgets; all behavior/signal wiring lives in controller.py.

Scope note: the panels here are honest, local-only tools. There is no cookie
input, no "auto-detect session", no cloud-upload drop target, and no
"bypass detector" toggle — those were removed on purpose.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QCheckBox, QListWidget, QTableWidget,
    QTableWidgetItem, QGroupBox, QPlainTextEdit, QProgressBar, QTabWidget,
    QSpinBox, QHeaderView, QSizePolicy,
)


APP_TITLE = "MAGIC STUDIO — Local Audio Toolkit"


class DropZone(QWidget):
    """Dashed drop target that emits a list of dropped file paths."""

    filesDropped = pyqtSignal(list)

    def __init__(self, title, subtitle, accent="Blue", parent=None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setProperty("accent", accent)
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("🎧")
        icon.setStyleSheet("font-size: 34pt;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        t = QLabel(title)
        t.setObjectName("DropZoneTitle")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)

        s = QLabel(subtitle)
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.browse_btn = QPushButton("Browse Local File…")
        self.browse_btn.setObjectName("Primary" if accent == "Blue" else "Emerald")
        self.browse_btn.setFixedWidth(200)

        lay.addStretch()
        lay.addWidget(icon)
        lay.addWidget(t)
        lay.addWidget(s)
        lay.addSpacing(10)
        lay.addWidget(self.browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addStretch()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.toLocalFile()]
        if paths:
            self.filesDropped.emit(paths)


def _panel_header(title, subtitle):
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("PanelTitle")
    s = QLabel(subtitle)
    s.setObjectName("PanelSubtitle")
    lay.addWidget(t)
    lay.addWidget(s)
    return box


def _queue_panel():
    """Reusable left-side 'Queue' column with add/remove/run buttons."""
    card = QGroupBox("Queue")
    lay = QVBoxLayout(card)
    listw = QListWidget()
    row = QHBoxLayout()
    add_btn = QPushButton("+ ADD")
    add_btn.setObjectName("Primary")
    rm_btn = QPushButton("– REMOVE")
    rm_btn.setObjectName("Danger")
    row.addWidget(add_btn)
    row.addWidget(rm_btn)
    run_btn = QPushButton("BULK MASTER")
    run_btn.setObjectName("Primary")
    lay.addWidget(listw)
    lay.addLayout(row)
    lay.addWidget(run_btn)
    return card, listw, add_btn, rm_btn, run_btn


class TitleBar(QWidget):
    """Custom frameless title bar: title | CPU/RAM | window buttons."""

    minimizeClicked = pyqtSignal()
    maximizeClicked = pyqtSignal()
    closeClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(34)
        self._drag_pos = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 4, 0)
        lay.setSpacing(6)

        self.title_lbl = QLabel(APP_TITLE)
        self.title_lbl.setObjectName("AppTitle")

        self.stats_lbl = QLabel("CPU: – % | RAM: – %")
        self.stats_lbl.setObjectName("SysStats")

        self.btn_min = QPushButton("—")
        self.btn_max = QPushButton("☐")
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("BtnClose")

        self.btn_min.clicked.connect(self.minimizeClicked)
        self.btn_max.clicked.connect(self.maximizeClicked)
        self.btn_close.clicked.connect(self.closeClicked)

        lay.addWidget(self.title_lbl)
        lay.addStretch()
        lay.addWidget(self.stats_lbl)
        lay.addWidget(self.btn_min)
        lay.addWidget(self.btn_max)
        lay.addWidget(self.btn_close)

    # Allow dragging the frameless window by its title bar.
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and self.window():
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.window().move(self.window().pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


class MainWindowUI(QWidget):
    """Root widget: title bar + tab widget with five panels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.title_bar = TitleBar()
        root.addWidget(self.title_bar)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        self.tabs.addTab(self._build_master_tab(), "Local Master")
        self.tabs.addTab(self._build_batch_tab(), "Batch Master")
        self.tabs.addTab(self._build_analysis_tab(), "Audio Analysis")
        self.tabs.addTab(self._build_metadata_tab(), "Metadata")
        self.tabs.addTab(self._build_settings_tab(), "Settings")

    # ---------- Tab 1: Local Master ----------
    def _build_master_tab(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.addWidget(_panel_header(
            "Local Master Workspace",
            "Remaster your own tracks on this machine — light EQ + loudness "
            "normalization. Files never leave your computer.",
        ))

        body = QHBoxLayout()
        (self.m_queue_card, self.m_list, self.m_add, self.m_remove,
         self.m_run) = _queue_panel()
        self.m_queue_card.setFixedWidth(230)
        body.addWidget(self.m_queue_card)

        right = QVBoxLayout()
        info = QGroupBox("Local Processing")
        info_lay = QVBoxLayout(info)
        info_lay.addWidget(QLabel(
            "This tool processes files locally with soundfile + pyloudnorm.\n"
            "No accounts, cookies, or uploads are involved."
        ))
        right.addWidget(info)

        self.m_drop = DropZone(
            "Drop a WAV/FLAC/MP3 here",
            "Adds it to the queue for local mastering",
            accent="Blue",
        )
        right.addWidget(self.m_drop, stretch=1)

        self.m_progress = QProgressBar()
        self.m_progress.setValue(0)
        self.m_status = QLabel("Ready.")
        self.m_status.setObjectName("PanelSubtitle")
        right.addWidget(self.m_progress)
        right.addWidget(self.m_status)

        body.addLayout(right, stretch=1)
        outer.addLayout(body, stretch=1)
        return page

    # ---------- Tab 2: Batch Master ----------
    def _build_batch_tab(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.addWidget(_panel_header(
            "Batch Master Workspace",
            "Configure a local mastering profile and output format, then "
            "process the whole queue on this machine.",
        ))

        body = QHBoxLayout()
        (self.b_queue_card, self.b_list, self.b_add, self.b_remove,
         self.b_run) = _queue_panel()
        self.b_queue_card.setFixedWidth(230)
        body.addWidget(self.b_queue_card)

        right = QVBoxLayout()
        self.b_drop = DropZone(
            "Drop tracks for batch mastering",
            "WAV / FLAC / MP3 — processed locally",
            accent="Emerald",
        )
        right.addWidget(self.b_drop, stretch=1)

        controls = QGridLayout()
        controls.addWidget(QLabel("Mastering Profile (EQ Curve):"), 0, 0)
        self.b_profile = QComboBox()
        self.b_profile.addItems(["neutral", "warm", "bright", "loud", "podcast"])
        controls.addWidget(self.b_profile, 1, 0)

        controls.addWidget(QLabel("Output Bitrate/Format:"), 0, 1)
        self.b_format = QComboBox()
        self.b_format.addItems([
            "Ultra HD (24-bit 48kHz WAV)",
            "HD (24-bit 44.1kHz WAV)",
            "CD (16-bit 44.1kHz WAV)",
            "Studio (32-bit float WAV)",
        ])
        controls.addWidget(self.b_format, 1, 1)
        right.addLayout(controls)

        self.b_start = QPushButton("Start Mastering")
        self.b_start.setObjectName("Primary")
        self.b_start.setMinimumHeight(38)
        right.addWidget(self.b_start)

        self.b_progress = QProgressBar()
        self.b_status = QLabel("Ready.")
        self.b_status.setObjectName("PanelSubtitle")
        right.addWidget(self.b_progress)
        right.addWidget(self.b_status)

        body.addLayout(right, stretch=1)
        outer.addLayout(body, stretch=1)
        return page

    # ---------- Tab 3: Audio Analysis ----------
    def _build_analysis_tab(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.addWidget(_panel_header(
            "Audio Analysis Workspace",
            "Measure real technical stats for your files — duration, loudness "
            "(LUFS), true peak, sample rate. No origin guessing, no spoofing.",
        ))

        self.a_table = QTableWidget(0, 6)
        self.a_table.setHorizontalHeaderLabels(
            ["Filename", "Duration", "LUFS", "True Peak", "RMS", "Sample Rate"]
        )
        self.a_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.a_table.verticalHeader().setVisible(False)
        outer.addWidget(self.a_table, stretch=1)

        row = QHBoxLayout()
        self.a_status = QLabel("Ready to scan.")
        self.a_status.setObjectName("PanelSubtitle")
        self.a_add = QPushButton("Add Audio Files")
        self.a_add.setObjectName("Primary")
        self.a_clear = QPushButton("Clear Analysis List")
        row.addWidget(self.a_status)
        row.addStretch()
        row.addWidget(self.a_add)
        row.addWidget(self.a_clear)
        outer.addLayout(row)
        return page

    # ---------- Tab 4: Metadata ----------
    def _build_metadata_tab(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.addWidget(_panel_header(
            "Metadata Workspace",
            "Batch-write the accurate tags configured in Settings to your own "
            "files. Whatever you enter is exactly what gets written.",
        ))

        self.md_table = QTableWidget(0, 3)
        self.md_table.setHorizontalHeaderLabels(["Filename", "Status", "Details"])
        self.md_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.md_table.verticalHeader().setVisible(False)
        outer.addWidget(self.md_table, stretch=1)

        row = QHBoxLayout()
        self.md_status = QLabel("Ready.")
        self.md_status.setObjectName("PanelSubtitle")
        self.md_add = QPushButton("Add Audio Files")
        self.md_add.setObjectName("Primary")
        self.md_write = QPushButton("Write Metadata")
        self.md_write.setObjectName("Pink")
        self.md_clear = QPushButton("Clear Queue")
        row.addWidget(self.md_status)
        row.addStretch()
        row.addWidget(self.md_add)
        row.addWidget(self.md_write)
        row.addWidget(self.md_clear)
        outer.addLayout(row)
        return page

    # ---------- Tab 5: Settings ----------
    def _build_settings_tab(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.addWidget(_panel_header(
            "Metadata & Cover Art Settings",
            "Defaults used by the Metadata tab. These write real, accurate tags.",
        ))

        grid = QGridLayout()

        # Basic info
        basic = QGroupBox("BASIC INFO")
        bform = QFormLayout(basic)
        self.s_artist = QLineEdit()
        self.s_year = QLineEdit()
        self.s_album = QLineEdit()
        self.s_rating = QLineEdit()
        self.s_genre = QLineEdit()
        bform.addRow("Artist", self.s_artist)
        bform.addRow("Year", self.s_year)
        bform.addRow("Album", self.s_album)
        bform.addRow("Rating", self.s_rating)
        bform.addRow("Genre", self.s_genre)
        grid.addWidget(basic, 0, 0)

        # Cover art
        cover = QGroupBox("COVER ART IMAGE")
        clay = QVBoxLayout(cover)
        self.s_cover_preview = QLabel("No cover")
        self.s_cover_preview.setFixedHeight(90)
        self.s_cover_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.s_cover_preview.setStyleSheet(
            "background:#16191f;border:1px solid #333d4f;border-radius:6px;")
        self.s_cover_path = QLineEdit()
        self.s_cover_path.setPlaceholderText("Cover file path…")
        crow = QHBoxLayout()
        self.s_cover_browse = QPushButton("Browse…")
        self.s_cover_clear = QPushButton("Clear Cover")
        self.s_cover_clear.setObjectName("Danger")
        crow.addWidget(self.s_cover_browse)
        crow.addWidget(self.s_cover_clear)
        clay.addWidget(self.s_cover_preview)
        clay.addWidget(self.s_cover_path)
        clay.addLayout(crow)
        grid.addWidget(cover, 0, 1)

        # Tracklist parsing
        parse = QGroupBox("TRACKLIST PARSING && COVER SIZING")
        play = QVBoxLayout(parse)
        self.s_uppercase = QCheckBox("Force UPPERCASE Title")
        self.s_striptrack = QCheckBox("Remove Track Numbers from Title")
        self.s_striptrack.setChecked(True)
        size_row = QHBoxLayout()
        self.s_cover_w = QSpinBox()
        self.s_cover_w.setRange(0, 10000)
        self.s_cover_w.setValue(3000)
        self.s_cover_h = QSpinBox()
        self.s_cover_h.setRange(0, 10000)
        self.s_cover_h.setValue(3000)
        size_row.addWidget(QLabel("Cover Size:"))
        size_row.addWidget(self.s_cover_w)
        size_row.addWidget(QLabel("x"))
        size_row.addWidget(self.s_cover_h)
        size_row.addStretch()
        play.addWidget(self.s_uppercase)
        play.addWidget(self.s_striptrack)
        play.addLayout(size_row)
        grid.addWidget(parse, 1, 0)

        # Studio metadata / copyright
        studio = QGroupBox("STUDIO METADATA && COPYRIGHT")
        sform = QFormLayout(studio)
        self.s_engineer = QLineEdit()
        self.s_copyright = QLineEdit()
        self.s_encoder = QLineEdit()
        self.s_source = QLineEdit()
        self.s_comment = QPlainTextEdit()
        self.s_comment.setFixedHeight(56)
        sform.addRow("Engineer", self.s_engineer)
        sform.addRow("Copyright", self.s_copyright)
        sform.addRow("Software Encoder", self.s_encoder)
        sform.addRow("Source", self.s_source)
        sform.addRow("Comment", self.s_comment)
        grid.addWidget(studio, 1, 1)

        outer.addLayout(grid)

        footer = QHBoxLayout()
        self.s_enable_injection = QCheckBox("Enable metadata writing")
        self.s_enable_injection.setChecked(True)
        footer.addWidget(self.s_enable_injection)
        footer.addStretch()
        self.s_apply = QPushButton("Apply Settings")
        self.s_apply.setObjectName("Primary")
        footer.addWidget(self.s_apply)
        outer.addLayout(footer)
        outer.addStretch()
        return page
