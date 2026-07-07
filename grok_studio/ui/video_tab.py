"""Video tab — grok-imagine-video with reference images, polling + preview.

Uses VIDEO_ASPECT_RATIOS only — the video endpoint rejects most of the image
ratio list with HTTP 400, so the two dropdowns must never share a list.
"""

from __future__ import annotations

import base64
import time
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSlider,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..api_client import APIClient, VideoJob
from ..constants import (
    COLOR_BG_ELEVATED,
    COLOR_BORDER,
    COLOR_TEXT_SECONDARY,
    VIDEO_ASPECT_RATIOS,
    VIDEO_DURATION_MAX_S,
    VIDEO_DURATION_MIN_S,
    VIDEO_MAX_REFERENCE_IMAGES,
    VIDEO_MODEL,
    VIDEO_PRICE_PER_MINUTE,
    VIDEO_RESOLUTIONS,
)
from ..i18n import tr
from ..logging_setup import app_data_dir
from ..settings_manager import SettingsManager
from ..workers import DownloadWorker, VideoPollWorker


class ReferenceDropArea(QLabel):
    """Drag-and-drop target for up to 7 reference images."""

    images_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.images: list[bytes] = []
        self.setAcceptDrops(True)
        self.setFixedHeight(52)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setStyleSheet(
            f"background:{COLOR_BG_ELEVATED};border:1px dashed {COLOR_BORDER};"
            f"border-radius:8px;color:{COLOR_TEXT_SECONDARY};font-size:11px;"
        )

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            if len(self.images) >= VIDEO_MAX_REFERENCE_IMAGES:
                break
            path = Path(url.toLocalFile())
            if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
                try:
                    self.images.append(path.read_bytes())
                except OSError:
                    continue
        event.acceptProposedAction()
        self.images_changed.emit()

    def add_image(self, data: bytes) -> bool:
        if len(self.images) >= VIDEO_MAX_REFERENCE_IMAGES:
            return False
        self.images.append(data)
        self.images_changed.emit()
        return True

    def clear_images(self) -> None:
        self.images.clear()
        self.images_changed.emit()


class VideoTab(QWidget):
    toast = pyqtSignal(str, str)

    def __init__(self, client: APIClient, settings: SettingsManager, parent=None):
        super().__init__(parent)
        self._client = client
        self._settings = settings
        self._poll_worker: VideoPollWorker | None = None
        self._download_worker: DownloadWorker | None = None
        self._video_bytes: bytes | None = None
        self._preview_path: Path | None = None

        self.prompt = QTextEdit()
        self.prompt.setFixedHeight(60)

        self.drop_area = ReferenceDropArea()
        self.drop_area.images_changed.connect(self._refresh_drop_label)
        self.clear_refs_btn = QToolButton()
        self.clear_refs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_refs_btn.setStyleSheet(
            f"border:none;background:transparent;color:{COLOR_TEXT_SECONDARY};"
            "font-size:11px;"
        )
        self.clear_refs_btn.clicked.connect(self.drop_area.clear_images)

        # aspect ratio — VIDEO list only (subset; never reuse image list)
        self.ratio_combo = QComboBox()
        self.ratio_combo.addItems(VIDEO_ASPECT_RATIOS)
        self.ratio_combo.setCurrentText(settings.default_video_ratio)

        self.res_combo = QComboBox()
        self.res_combo.addItems(VIDEO_RESOLUTIONS)
        self.res_combo.setCurrentText("720p")

        self.duration_slider = QSlider(Qt.Orientation.Horizontal)
        self.duration_slider.setRange(VIDEO_DURATION_MIN_S, VIDEO_DURATION_MAX_S)
        self.duration_slider.setValue(5)
        self.duration_slider.valueChanged.connect(self._update_estimate)
        self.duration_label = QLabel()
        self.duration_label.setProperty("secondary", True)

        self.cost_label = QLabel()
        self.cost_label.setProperty("secondary", True)

        self.generate_btn = QPushButton()
        self.generate_btn.setProperty("accent", True)
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.clicked.connect(self._generate)

        self.cancel_btn = QPushButton()
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._cancel)
        self.cancel_btn.hide()

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()
        self.status_label = QLabel()
        self.status_label.setProperty("secondary", True)
        self.status_label.hide()

        # preview player
        self.video_widget = QVideoWidget()
        self.video_widget.setFixedHeight(170)
        self.video_widget.hide()
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self.video_widget)
        self._player.mediaStatusChanged.connect(self._loop_preview)

        self.download_btn = QPushButton()
        self.download_btn.clicked.connect(self._save_video)
        self.download_btn.hide()

        # ---- layout ---------------------------------------------------------
        refs_row = QHBoxLayout()
        refs_row.addWidget(self.drop_area, 1)
        refs_row.addWidget(self.clear_refs_btn, 0, Qt.AlignmentFlag.AlignTop)

        self.ratio_caption = QLabel()
        self.ratio_caption.setProperty("secondary", True)
        opts_row = QHBoxLayout()
        opts_row.addWidget(self.ratio_caption)
        opts_row.addWidget(self.ratio_combo, 1)
        opts_row.addWidget(self.res_combo)

        dur_row = QHBoxLayout()
        dur_row.addWidget(self.duration_label)
        dur_row.addWidget(self.duration_slider, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.prompt)
        layout.addLayout(refs_row)
        layout.addLayout(opts_row)
        layout.addLayout(dur_row)
        layout.addWidget(self.cost_label)
        layout.addWidget(self.generate_btn)
        layout.addWidget(self.cancel_btn)
        layout.addWidget(self.progress)
        layout.addWidget(self.status_label)
        layout.addWidget(self.video_widget)
        layout.addWidget(self.download_btn)
        layout.addStretch(1)

        self.retranslate_ui()
        self._update_estimate()
        self._refresh_drop_label()

    # ----------------------------------------------------- from image tab ---
    def add_reference_image(self, data: bytes) -> None:
        if not self.drop_area.add_image(data):
            self.toast.emit(
                f"Max {VIDEO_MAX_REFERENCE_IMAGES} reference images", "warning"
            )

    # ------------------------------------------------------------ estimate --
    def _update_estimate(self) -> None:
        seconds = self.duration_slider.value()
        cost = seconds / 60 * VIDEO_PRICE_PER_MINUTE
        self.duration_label.setText(
            f'{tr("video.duration")}: {seconds}{tr("video.seconds")}'
        )
        self.cost_label.setText(f'{tr("video.estimate")}: ≈ ${cost:.2f}')

    def _refresh_drop_label(self) -> None:
        count = len(self.drop_area.images)
        label = tr("video.reference")
        if count:
            label += f"  —  {count}/{VIDEO_MAX_REFERENCE_IMAGES}"
        self.drop_area.setText(label)

    # ------------------------------------------------------------ generate --
    def _generate(self) -> None:
        if self._poll_worker and self._poll_worker.isRunning():
            return
        prompt = self.prompt.toPlainText().strip()
        if not prompt and not self.drop_area.images:
            return

        self._video_bytes = None
        self.video_widget.hide()
        self.download_btn.hide()
        self._player.stop()

        create_kwargs = dict(
            prompt=prompt,
            model=VIDEO_MODEL,
            aspect_ratio=self.ratio_combo.currentText(),
            resolution=self.res_combo.currentText(),
            duration_seconds=self.duration_slider.value(),
            reference_images=list(self.drop_area.images) or None,
        )

        self.generate_btn.setEnabled(False)
        self.cancel_btn.show()
        self.progress.setValue(0)
        self.progress.show()
        self.status_label.setText(tr("generic.queued"))
        self.status_label.show()

        self._poll_worker = VideoPollWorker(self._client, create_kwargs,
                                            parent=self)
        self._poll_worker.status.connect(self._on_status)
        self._poll_worker.completed.connect(self._on_completed)
        self._poll_worker.error.connect(self._on_error)
        self._poll_worker.retry_wait.connect(
            lambda s: self.toast.emit(tr("generic.retry_in").format(s=s), "warning")
        )
        self._poll_worker.start()

    def _cancel(self) -> None:
        if self._poll_worker and self._poll_worker.isRunning():
            self._poll_worker.cancel()
        if self._download_worker and self._download_worker.isRunning():
            self._download_worker.cancel()
        self._reset_job_ui()

    def _estimated_total_s(self) -> int:
        # rough heuristic: ~30s fixed overhead + ~10s render per output second
        return 30 + self.duration_slider.value() * 10

    def _on_status(self, status: str, elapsed: int) -> None:
        est_total = self._estimated_total_s()
        pct = min(95, int(elapsed / est_total * 100)) if est_total else 0
        self.progress.setValue(pct)
        remaining = max(0, est_total - elapsed)
        status_text = {
            "queued": tr("generic.queued"),
            "rendering": tr("generic.rendering"),
            "done": tr("generic.done"),
            "failed": tr("generic.failed"),
            "expired": tr("generic.expired"),
        }.get(status, status)
        self.status_label.setText(
            f'{status_text} — {elapsed}s {tr("video.elapsed")}, '
            f'~{remaining}s {tr("video.remaining")}'
        )

    def _on_completed(self, job: VideoJob) -> None:
        self.progress.setValue(100)
        self.status_label.setText(tr("generic.done"))
        if job.video_b64:
            self._got_video_bytes(base64.b64decode(job.video_b64))
        elif job.video_url:
            self._download_worker = DownloadWorker(self._client, job.video_url,
                                                   parent=self)
            self._download_worker.success.connect(self._got_video_bytes)
            self._download_worker.error.connect(self._on_error)
            self._download_worker.start()
        else:
            self._on_error(tr("generic.failed"))

    def _got_video_bytes(self, data: bytes) -> None:
        self._video_bytes = bytes(data)
        cache_dir = app_data_dir() / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._preview_path = cache_dir / f"preview_{int(time.time())}.mp4"
        try:
            self._preview_path.write_bytes(self._video_bytes)
        except OSError as exc:
            self.toast.emit(str(exc), "error")
            self._reset_job_ui()
            return

        self._reset_job_ui()
        self.video_widget.show()
        self.download_btn.show()
        self._player.setSource(QUrl.fromLocalFile(str(self._preview_path)))
        self._player.play()

    def _loop_preview(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._player.setPosition(0)
            self._player.play()

    def _on_error(self, message: str) -> None:
        self._reset_job_ui()
        self.toast.emit(message, "error")

    def _reset_job_ui(self) -> None:
        self.generate_btn.setEnabled(True)
        self.cancel_btn.hide()
        self.progress.hide()
        self.status_label.hide()

    def _save_video(self) -> None:
        if not self._video_bytes:
            return
        out = self._settings.output_dir / f"grok_video_{int(time.time())}.mp4"
        try:
            out.write_bytes(self._video_bytes)
        except OSError as exc:
            self.toast.emit(str(exc), "error")
            return
        self.toast.emit(f'{tr("generic.saved_to")} {out}', "success")

    # ---------------------------------------------------------------- i18n --
    def retranslate_ui(self) -> None:
        self.prompt.setPlaceholderText(tr("video.prompt_placeholder"))
        self.ratio_caption.setText(tr("image.aspect"))
        self.generate_btn.setText(tr("generic.generate"))
        self.cancel_btn.setText(tr("generic.cancel"))
        self.cancel_btn.setToolTip(tr("video.cancel_tooltip"))
        self.download_btn.setText(tr("video.download"))
        self.clear_refs_btn.setText(tr("video.clear_refs"))
        self._update_estimate()
        self._refresh_drop_label()
