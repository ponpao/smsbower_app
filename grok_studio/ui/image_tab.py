"""Image tab — grok-imagine-image / -quality with live price estimate.

Uses IMAGE_ASPECT_RATIOS only (the video tab has its own, smaller list).
"""

from __future__ import annotations

import time
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QImage, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..api_client import APIClient
from ..constants import (
    COLOR_BG_ELEVATED,
    COLOR_BORDER,
    IMAGE_ASPECT_RATIOS,
    IMAGE_MODELS,
    MAX_IMAGE_BATCH,
)
from ..i18n import tr
from ..settings_manager import SettingsManager
from ..workers import ApiWorker

_QUALITY_MODEL = "grok-imagine-image-quality"


class ImageResultCard(QWidget):
    """One generated image: thumbnail with hover-zoom + action buttons."""

    save_requested = pyqtSignal(bytes)
    send_to_video = pyqtSignal(bytes)

    def __init__(self, data: bytes, parent=None):
        super().__init__(parent)
        self.data = data

        image = QImage.fromData(data)
        self._pixmap = QPixmap.fromImage(image)

        self.thumb = QLabel()
        self.thumb.setFixedSize(150, 150)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setStyleSheet(
            f"background:{COLOR_BG_ELEVATED};border:1px solid {COLOR_BORDER};"
            "border-radius:8px;"
        )
        self._base_size = 146
        self._set_thumb(self._base_size)
        self.thumb.installEventFilter(self)

        def small_btn(text: str) -> QToolButton:
            btn = QToolButton()
            btn.setText(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QToolButton{border:1px solid " + COLOR_BORDER +
                ";border-radius:6px;background:transparent;"
                "font-size:10px;padding:3px 6px;}"
                "QToolButton:hover{background:#232330;}"
            )
            return btn

        self.save_btn = small_btn(tr("generic.save"))
        self.copy_btn = small_btn(tr("generic.copy"))
        self.video_btn = small_btn(tr("image.send_to_video"))
        self.save_btn.clicked.connect(lambda: self.save_requested.emit(self.data))
        self.copy_btn.clicked.connect(self._copy)
        self.video_btn.clicked.connect(lambda: self.send_to_video.emit(self.data))

        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.copy_btn)
        buttons.addWidget(self.video_btn)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.thumb)
        layout.addLayout(buttons)

    def _set_thumb(self, size: int) -> None:
        if not self._pixmap.isNull():
            self.thumb.setPixmap(self._pixmap.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))

    def eventFilter(self, obj, event):  # noqa: N802 — hover-to-zoom
        if obj is self.thumb:
            if event.type() == event.Type.Enter:
                self._set_thumb(int(self._base_size * 1.15))
            elif event.type() == event.Type.Leave:
                self._set_thumb(self._base_size)
        return super().eventFilter(obj, event)

    def _copy(self) -> None:
        if not self._pixmap.isNull():
            QGuiApplication.clipboard().setPixmap(self._pixmap)


class ImageTab(QWidget):
    toast = pyqtSignal(str, str)
    send_image_to_video = pyqtSignal(bytes)

    def __init__(self, client: APIClient, settings: SettingsManager, parent=None):
        super().__init__(parent)
        self._client = client
        self._settings = settings
        self._worker: ApiWorker | None = None

        self.prompt = QTextEdit()
        self.prompt.setFixedHeight(70)

        # model + price
        self.model_combo = QComboBox()
        for model_id in IMAGE_MODELS:
            self.model_combo.addItem(model_id, model_id)
        self.model_combo.currentIndexChanged.connect(self._refresh_controls)

        self.price_label = QLabel()
        self.price_label.setProperty("secondary", True)

        # aspect ratio — IMAGE list only
        self.ratio_combo = QComboBox()
        self.ratio_combo.addItems(IMAGE_ASPECT_RATIOS)
        self.ratio_combo.setCurrentText(settings.default_image_ratio)

        # resolution toggle (quality model only)
        self.res_1k = QRadioButton("1K")
        self.res_2k = QRadioButton("2K")
        self.res_1k.setChecked(True)
        self.res_1k.toggled.connect(self._update_price)

        # batch stepper
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, MAX_IMAGE_BATCH)
        self.count_spin.valueChanged.connect(self._update_price)

        self.generate_btn = QPushButton()
        self.generate_btn.setProperty("accent", True)
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.clicked.connect(self._generate)

        self.status_label = QLabel()
        self.status_label.setProperty("secondary", True)
        self.status_label.hide()

        # results grid inside a scroll area
        self._grid = QGridLayout()
        self._grid.setSpacing(8)
        grid_host = QWidget()
        grid_host.setLayout(self._grid)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(grid_host)

        # ---- layout ---------------------------------------------------------
        self.model_caption = QLabel()
        self.model_caption.setProperty("secondary", True)
        model_row = QHBoxLayout()
        model_row.addWidget(self.model_caption)
        model_row.addWidget(self.model_combo, 1)
        model_row.addWidget(self.price_label)

        self.ratio_caption = QLabel()
        self.ratio_caption.setProperty("secondary", True)
        self.count_caption = QLabel()
        self.count_caption.setProperty("secondary", True)
        opts_row = QHBoxLayout()
        opts_row.addWidget(self.ratio_caption)
        opts_row.addWidget(self.ratio_combo, 1)
        opts_row.addWidget(self.res_1k)
        opts_row.addWidget(self.res_2k)
        opts_row.addWidget(self.count_caption)
        opts_row.addWidget(self.count_spin)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.prompt)
        layout.addLayout(model_row)
        layout.addLayout(opts_row)
        layout.addWidget(self.generate_btn)
        layout.addWidget(self.status_label)
        layout.addWidget(self._scroll, 1)

        self.retranslate_ui()
        self._refresh_controls()

    # ------------------------------------------------------------- pricing --
    def _current_resolution(self) -> str:
        return "2k" if self.res_2k.isChecked() else "1k"

    def _refresh_controls(self) -> None:
        is_quality = self.model_combo.currentData() == _QUALITY_MODEL
        self.res_1k.setVisible(is_quality)
        self.res_2k.setVisible(is_quality)
        if not is_quality:
            self.res_1k.setChecked(True)
        self._update_price()

    def _update_price(self) -> None:
        model = self.model_combo.currentData()
        prices = IMAGE_MODELS[model]["prices"]
        per_image = prices.get(self._current_resolution(), prices["1k"])
        total = per_image * self.count_spin.value()
        self.price_label.setText(f"≈ ${total:.2f}")

    # ------------------------------------------------------------ generate --
    def _generate(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        prompt = self.prompt.toPlainText().strip()
        if not prompt:
            return

        model = self.model_combo.currentData()
        kwargs = dict(
            model=model,
            aspect_ratio=self.ratio_combo.currentText(),
            n=self.count_spin.value(),
        )
        if model == _QUALITY_MODEL:
            kwargs["resolution"] = self._current_resolution()

        self.generate_btn.setEnabled(False)
        self.status_label.setText(tr("image.generating"))
        self.status_label.show()

        self._worker = ApiWorker(self._client.generate_images, prompt,
                                 parent=self, **kwargs)
        self._worker.success.connect(self._on_success)
        self._worker.error.connect(self._on_error)
        self._worker.retry_wait.connect(
            lambda s: self.toast.emit(tr("generic.retry_in").format(s=s), "warning")
        )
        self._worker.start()

    def _on_success(self, images: list) -> None:
        self.generate_btn.setEnabled(True)
        self.status_label.hide()
        self._clear_grid()
        for i, data in enumerate(images):
            card = ImageResultCard(bytes(data))
            card.save_requested.connect(self._save_image)
            card.send_to_video.connect(self.send_image_to_video.emit)
            self._grid.addWidget(card, i // 2, i % 2)

    def _on_error(self, message: str) -> None:
        self.generate_btn.setEnabled(True)
        self.status_label.hide()
        if "moderation" in message.lower():
            message = tr("generic.moderation")
        self.toast.emit(message, "error")

    def _clear_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _save_image(self, data: bytes) -> None:
        out_dir = self._settings.output_dir
        path = Path(out_dir) / f"grok_image_{int(time.time() * 1000)}.png"
        try:
            path.write_bytes(data)
        except OSError as exc:
            self.toast.emit(str(exc), "error")
            return
        self.toast.emit(f'{tr("generic.saved_to")} {path}', "success")

    # ---------------------------------------------------------------- i18n --
    def retranslate_ui(self) -> None:
        self.prompt.setPlaceholderText(tr("image.prompt_placeholder"))
        self.model_caption.setText(tr("image.model"))
        self.ratio_caption.setText(tr("image.aspect"))
        self.count_caption.setText(tr("image.count"))
        self.generate_btn.setText(tr("generic.generate"))
        self.status_label.setText(tr("image.generating"))
        self.price_label.setToolTip(tr("image.estimate"))
        for card_btn_update in self._iter_cards():
            card_btn_update.save_btn.setText(tr("generic.save"))
            card_btn_update.copy_btn.setText(tr("generic.copy"))
            card_btn_update.video_btn.setText(tr("image.send_to_video"))

    def _iter_cards(self):
        for i in range(self._grid.count()):
            widget = self._grid.itemAt(i).widget()
            if isinstance(widget, ImageResultCard):
                yield widget
