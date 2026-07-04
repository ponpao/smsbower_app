"""Release Readiness Check dialog (honest — reminds to disclose AI, never bypass)."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout

from ..theme import TEXT, TEXT_MUTED, TEXT_DIM, GOOD, WARN
from travkod import release as release_mod


class ReleaseDialog(QDialog):
    def __init__(self, meta: dict, lufs_target, is_ai: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Release Readiness Check")
        self.setMinimumWidth(520)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(8)

        if not meta:
            root.addWidget(QLabel("Select and analyze a track first."))
            return

        check = release_mod.check(meta, lufs_target=lufs_target, is_ai=is_ai)
        summary = QLabel(("✓ " if check["passed"] else "⚠ ") + check["summary"])
        summary.setStyleSheet(f"color:{GOOD if check['passed'] else WARN}; font-size:13px; font-weight:600;")
        root.addWidget(summary)

        for it in check["items"]:
            row = QHBoxLayout()
            mark = QLabel("✓" if it["status"] == "pass" else "⚠")
            mark.setStyleSheet(f"color:{GOOD if it['status']=='pass' else WARN}; font-size:12px;")
            mark.setFixedWidth(16)
            text = QLabel(f"<b style='color:{TEXT}'>{it['name']}</b>"
                          f"<span style='color:{TEXT_MUTED}'> — {it['detail']}</span>")
            text.setTextFormat(Qt.TextFormat.RichText)
            text.setWordWrap(True)
            row.addWidget(mark)
            row.addWidget(text, stretch=1)
            root.addLayout(row)

        note = QLabel("This checklist reports objective facts about your master. It never tells "
                      "you how to “pass” a distributor check. Where a release requires AI "
                      "disclosure, disclose it.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px;")
        root.addSpacing(6)
        root.addWidget(note)

        close = QPushButton("Close"); close.clicked.connect(self.accept)
        b = QHBoxLayout(); b.addStretch(1); b.addWidget(close)
        root.addLayout(b)
