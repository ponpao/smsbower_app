"""Settings tab — API key (keyring only), language, defaults, output folder.

The key is validated with a minimal grok-4.3 call BEFORE being saved, and is
stored exclusively via keyring (Windows Credential Manager) — never in a
file, QSettings entry or log line.
"""

from __future__ import annotations

import shutil

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..api_client import APIClient
from ..constants import IMAGE_ASPECT_RATIOS, VIDEO_ASPECT_RATIOS
from ..i18n import tr
from ..logging_setup import app_data_dir
from ..settings_manager import SettingsManager
from ..workers import ApiWorker


class SettingsTab(QWidget):
    toast = pyqtSignal(str, str)
    key_validated = pyqtSignal()      # emitted when a key is tested + saved
    language_switched = pyqtSignal(str)

    def __init__(self, client: APIClient, settings: SettingsManager, parent=None):
        super().__init__(parent)
        self._client = client
        self._settings = settings
        self._test_worker: ApiWorker | None = None

        # ---- api key ----------------------------------------------------------
        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.setStyleSheet(
            "background:#3A2E14;color:#FFB84C;border-radius:8px;padding:8px;"
        )
        self.banner.hide()

        self.key_caption = QLabel()
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self.reveal_btn = QToolButton()
        self.reveal_btn.setText("👁")
        self.reveal_btn.setCheckable(True)
        self.reveal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reveal_btn.setStyleSheet(
            "border:none;background:transparent;font-size:14px;"
        )
        self.reveal_btn.toggled.connect(
            lambda checked: self.key_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked
                else QLineEdit.EchoMode.Password
            )
        )

        key_row = QHBoxLayout()
        key_row.setSpacing(4)
        key_row.addWidget(self.key_edit, 1)
        key_row.addWidget(self.reveal_btn)

        self.test_btn = QPushButton()
        self.test_btn.setProperty("accent", True)
        self.test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.test_btn.clicked.connect(self._test_and_save)

        self.key_status = QLabel()
        self.key_status.setProperty("secondary", True)
        self.key_status.setWordWrap(True)

        # ---- language ---------------------------------------------------------
        self.lang_caption = QLabel()
        self.lang_en = QRadioButton()
        self.lang_kh = QRadioButton()
        (self.lang_kh if settings.language == "kh" else self.lang_en).setChecked(True)
        self.lang_en.toggled.connect(self._on_language_toggle)

        lang_row = QHBoxLayout()
        lang_row.addWidget(self.lang_en)
        lang_row.addWidget(self.lang_kh)
        lang_row.addStretch(1)

        # ---- default ratios ----------------------------------------------------
        self.img_ratio_caption = QLabel()
        self.img_ratio_combo = QComboBox()
        self.img_ratio_combo.addItems(IMAGE_ASPECT_RATIOS)
        self.img_ratio_combo.setCurrentText(settings.default_image_ratio)
        self.img_ratio_combo.currentTextChanged.connect(
            lambda v: setattr(self._settings, "default_image_ratio", v)
        )

        self.vid_ratio_caption = QLabel()
        self.vid_ratio_combo = QComboBox()
        self.vid_ratio_combo.addItems(VIDEO_ASPECT_RATIOS)  # separate list!
        self.vid_ratio_combo.setCurrentText(settings.default_video_ratio)
        self.vid_ratio_combo.currentTextChanged.connect(
            lambda v: setattr(self._settings, "default_video_ratio", v)
        )

        # ---- output folder ------------------------------------------------------
        self.out_caption = QLabel()
        self.out_path_label = QLabel(str(settings.output_dir))
        self.out_path_label.setProperty("secondary", True)
        self.out_path_label.setWordWrap(True)
        self.browse_btn = QPushButton()
        self.browse_btn.clicked.connect(self._pick_output_dir)

        out_row = QHBoxLayout()
        out_row.addWidget(self.out_path_label, 1)
        out_row.addWidget(self.browse_btn)

        # ---- maintenance ---------------------------------------------------------
        self.clear_cache_btn = QPushButton()
        self.clear_cache_btn.clicked.connect(self._clear_cache)
        self.reset_btn = QPushButton()
        self.reset_btn.setProperty("danger", True)
        self.reset_btn.clicked.connect(self._reset_app)

        # ---- layout ------------------------------------------------------------
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(12, 6, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.banner)
        layout.addWidget(self.key_caption)
        layout.addLayout(key_row)
        layout.addWidget(self.test_btn)
        layout.addWidget(self.key_status)
        layout.addSpacing(8)
        layout.addWidget(self.lang_caption)
        layout.addLayout(lang_row)
        layout.addSpacing(8)
        layout.addWidget(self.img_ratio_caption)
        layout.addWidget(self.img_ratio_combo)
        layout.addWidget(self.vid_ratio_caption)
        layout.addWidget(self.vid_ratio_combo)
        layout.addSpacing(8)
        layout.addWidget(self.out_caption)
        layout.addLayout(out_row)
        layout.addSpacing(8)
        layout.addWidget(self.clear_cache_btn)
        layout.addWidget(self.reset_btn)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self.retranslate_ui()
        self._refresh_key_status()

    # -------------------------------------------------------------- api key --
    def show_key_required_banner(self, visible: bool) -> None:
        self.banner.setVisible(visible)

    def _refresh_key_status(self) -> None:
        has_key = self._settings.has_api_key()
        self.key_status.setText(
            tr("settings.key_stored") if has_key else tr("settings.key_missing")
        )

    def _test_and_save(self) -> None:
        key = self.key_edit.text().strip()
        if not key:
            self.toast.emit(tr("settings.key_missing"), "warning")
            return
        if self._test_worker and self._test_worker.isRunning():
            return

        self.test_btn.setEnabled(False)
        self.test_btn.setText(tr("settings.testing"))

        # validate with the candidate key, not the stored one
        probe_client = APIClient(lambda: key)
        self._test_worker = ApiWorker(probe_client.test_connection, parent=self)
        self._test_worker.success.connect(lambda _ok, k=key: self._on_key_ok(k))
        self._test_worker.error.connect(self._on_key_fail)
        self._test_worker.start()

    def _on_key_ok(self, key: str) -> None:
        if not self._settings.set_api_key(key):
            self.test_btn.setEnabled(True)
            self.test_btn.setText(tr("settings.test"))
            self.toast.emit("Could not write to Windows Credential Manager", "error")
            return
        self.key_edit.clear()
        self.test_btn.setEnabled(True)
        self.test_btn.setText(tr("settings.test"))
        self._refresh_key_status()
        self.banner.hide()
        self.toast.emit(tr("settings.test_ok"), "success")
        self.key_validated.emit()

    def _on_key_fail(self, message: str) -> None:
        self.test_btn.setEnabled(True)
        self.test_btn.setText(tr("settings.test"))
        self.toast.emit(f'{tr("settings.test_fail")}: {message}', "error")

    # ------------------------------------------------------------- language --
    def _on_language_toggle(self) -> None:
        lang = "en" if self.lang_en.isChecked() else "kh"
        if lang != self._settings.language:
            self._settings.language = lang
            self.language_switched.emit(lang)

    # ---------------------------------------------------------------- misc --
    def _pick_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, tr("settings.output_folder"), str(self._settings.output_dir)
        )
        if path:
            self._settings.output_dir = path
            self.out_path_label.setText(path)

    def _clear_cache(self) -> None:
        cache_dir = app_data_dir() / "cache"
        shutil.rmtree(cache_dir, ignore_errors=True)
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.toast.emit(tr("settings.cache_cleared"), "success")

    def _reset_app(self) -> None:
        answer = QMessageBox.question(
            self, tr("settings.reset_app"), tr("settings.reset_confirm")
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._settings.reset()
        self._clear_cache()
        self._refresh_key_status()
        self.toast.emit(tr("settings.reset_done"), "success")

    # ---------------------------------------------------------------- i18n --
    def retranslate_ui(self) -> None:
        self.banner.setText(tr("settings.key_required_banner"))
        self.key_caption.setText(tr("settings.api_key"))
        self.key_edit.setPlaceholderText(tr("settings.api_key_placeholder"))
        self.test_btn.setText(tr("settings.testing")
                              if self._test_worker and self._test_worker.isRunning()
                              else tr("settings.test"))
        self.lang_caption.setText(tr("settings.language"))
        self.lang_en.setText(tr("settings.lang_en"))
        self.lang_kh.setText(tr("settings.lang_kh"))
        self.img_ratio_caption.setText(tr("settings.default_image_ratio"))
        self.vid_ratio_caption.setText(tr("settings.default_video_ratio"))
        self.out_caption.setText(tr("settings.output_folder"))
        self.browse_btn.setText(tr("settings.browse"))
        self.clear_cache_btn.setText(tr("settings.clear_cache"))
        self.reset_btn.setText(tr("settings.reset_app"))
        self._refresh_key_status()
