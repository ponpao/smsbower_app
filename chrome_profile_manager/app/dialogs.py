# -*- coding: utf-8 -*-
"""Dialogs: group create/rename/edit (name + color), profile editor,
and the delete-group cascade-choice dialog."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QVBoxLayout,
)

from .i18n import tr
from .storage import DEFAULT_GROUP_COLORS


class GroupDialog(QDialog):
    """Create / rename / edit a group: validated name + color swatch picker."""

    def __init__(self, store, parent=None, group=None, title_key="dlg_create_group_title"):
        super().__init__(parent)
        self.store = store
        self.group = group
        self.setWindowTitle(tr(title_key))
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("lbl_group_name")))
        self.name_edit = QLineEdit(group["name"] if group else "")
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel(tr("lbl_group_color")))
        swatch_row = QHBoxLayout()
        self.color_buttons = QButtonGroup(self)
        selected = (group or {}).get("color") or DEFAULT_GROUP_COLORS[0]
        for color in DEFAULT_GROUP_COLORS:
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(26, 26)
            btn.setProperty("swatch_color", color)
            btn.setStyleSheet(
                f"QPushButton {{ background: {color}; border: 2px solid transparent; border-radius: 5px; }}"
                f"QPushButton:checked {{ border: 2px solid #202020; }}"
            )
            if color == selected:
                btn.setChecked(True)
            self.color_buttons.addButton(btn)
            swatch_row.addWidget(btn)
        swatch_row.addStretch()
        layout.addLayout(swatch_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(tr("ok"))
        buttons.button(QDialogButtonBox.Cancel).setText(tr("cancel"))
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.name_edit.setFocus()

    def _validate(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, self.windowTitle(), tr("err_empty_name"))
            return
        exclude = self.group["id"] if self.group else ""
        if self.store.group_name_taken(name, exclude_id=exclude):
            QMessageBox.warning(self, self.windowTitle(), tr("err_duplicate_name"))
            return
        self.accept()

    def result_values(self):
        checked = self.color_buttons.checkedButton()
        color = checked.property("swatch_color") if checked else DEFAULT_GROUP_COLORS[0]
        return self.name_edit.text().strip(), color


class ProfileDialog(QDialog):
    """Create or edit a profile."""

    def __init__(self, store, parent=None, profile=None):
        super().__init__(parent)
        self.store = store
        self.profile = profile
        self.setWindowTitle(tr("dlg_profile_edit" if profile else "dlg_profile_new"))
        self.setMinimumWidth(380)
        p = profile or {}

        form = QFormLayout(self)
        self.name_edit = QLineEdit(p.get("name", ""))
        self.key_edit = QLineEdit(p.get("key") or store.next_profile_key())
        self.gmail_edit = QLineEdit(p.get("gmail", ""))
        self.password_edit = QLineEdit(p.get("password", ""))
        self.url_edit = QLineEdit(p.get("launch_url", ""))
        self.group_combo = QComboBox()
        self.group_combo.addItem(tr("group_none"), "")
        for g in store.groups:
            self.group_combo.addItem(g["name"], g["id"])
            if g["id"] == p.get("group_id"):
                self.group_combo.setCurrentIndex(self.group_combo.count() - 1)
        self.fav_check = QCheckBox()
        self.fav_check.setChecked(bool(p.get("favorite")))

        form.addRow(tr("lbl_name"), self.name_edit)
        form.addRow(tr("lbl_key"), self.key_edit)
        form.addRow(tr("lbl_gmail"), self.gmail_edit)
        form.addRow(tr("lbl_password"), self.password_edit)
        form.addRow(tr("lbl_launch_url"), self.url_edit)
        form.addRow(tr("lbl_group"), self.group_combo)
        form.addRow(tr("tab_favorites"), self.fav_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(tr("ok"))
        buttons.button(QDialogButtonBox.Cancel).setText(tr("cancel"))
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.name_edit.setFocus()

    def _validate(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, self.windowTitle(), tr("err_empty_name"))
            return
        self.accept()

    def result_values(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "key": self.key_edit.text().strip(),
            "gmail": self.gmail_edit.text().strip(),
            "password": self.password_edit.text(),
            "launch_url": self.url_edit.text().strip(),
            "group_id": self.group_combo.currentData(),
            "favorite": self.fav_check.isChecked(),
        }


# Outcomes of the delete-group dialog
DELETE_CANCELLED = 0
DELETE_GROUP_ONLY = 1
DELETE_GROUP_AND_PROFILES = 2


def ask_delete_group(parent, group_name: str, profile_count: int) -> int:
    """Two distinct destructive choices — never a silent cascade delete."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(tr("dlg_delete_group_title"))
    box.setText(tr("msg_delete_group", name=group_name, n=profile_count))
    only_btn = box.addButton(tr("btn_delete_group_only"), QMessageBox.AcceptRole)
    cascade_btn = box.addButton(tr("btn_delete_group_profiles"), QMessageBox.DestructiveRole)
    box.addButton(tr("cancel"), QMessageBox.RejectRole)
    box.exec()
    clicked = box.clickedButton()
    if clicked is only_btn:
        return DELETE_GROUP_ONLY
    if clicked is cascade_btn:
        return DELETE_GROUP_AND_PROFILES
    return DELETE_CANCELLED


def ask_yes_no(parent, title: str, text: str, default_no: bool = True) -> bool:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(title)
    box.setText(text)
    yes = box.addButton(tr("yes"), QMessageBox.YesRole)
    no = box.addButton(tr("no"), QMessageBox.NoRole)
    box.setDefaultButton(no if default_no else yes)
    box.exec()
    return box.clickedButton() is yes
