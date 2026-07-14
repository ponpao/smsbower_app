# -*- coding: utf-8 -*-
"""Dialogs: group create/rename/edit (name + color), profile editor,
and the delete-group cascade-choice dialog."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from .chrome import default_user_data_path, scan_system_profiles
from .i18n import tr
from .logger import read_log
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
        self.notes_edit = QLineEdit(p.get("notes", ""))
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
        form.addRow(tr("lbl_notes"), self.notes_edit)
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
            "notes": self.notes_edit.text().strip(),
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


class ScanImportDialog(QDialog):
    """Scan the system Chrome 'User Data' folder and import existing profiles.

    Imported profiles keep launching with the user's existing Chrome data
    (--user-data-dir=<User Data> --profile-directory=<dir>) — nothing is
    copied or moved.
    """

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.imported = 0
        self.setWindowTitle(tr("scan_title"))
        self.setMinimumSize(560, 420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("scan_path")))
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(default_user_data_path())
        self.path_edit.editingFinished.connect(self._rescan)
        browse_btn = QPushButton(tr("btn_browse"))
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        select_row = QHBoxLayout()
        all_btn = QPushButton(tr("btn_select_all"))
        none_btn = QPushButton(tr("btn_deselect_all"))
        all_btn.clicked.connect(lambda: self._set_all(Qt.Checked))
        none_btn.clicked.connect(lambda: self._set_all(Qt.Unchecked))
        select_row.addWidget(all_btn)
        select_row.addWidget(none_btn)
        select_row.addStretch()
        layout.addLayout(select_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["", tr("col_key"), tr("col_name"), tr("col_gmail")])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnWidth(0, 30)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 180)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        import_btn = QPushButton(tr("btn_import_selected"))
        import_btn.setDefault(True)
        import_btn.setMinimumWidth(160)
        import_btn.clicked.connect(self._import_selected)
        cancel_btn = QPushButton(tr("cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(import_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        self._rescan()

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, tr("scan_path"), self.path_edit.text())
        if path:
            self.path_edit.setText(path)
            self._rescan()

    def _already_imported(self, base: str, profile_dir: str) -> bool:
        return any(p.get("chrome_base") == base and p.get("chrome_profile_dir") == profile_dir
                   for p in self.store.profiles)

    def _rescan(self):
        base = self.path_edit.text().strip()
        found = scan_system_profiles(base)
        self.table.setRowCount(len(found))
        for row, item in enumerate(found):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            already = self._already_imported(base, item["dir"])
            check.setCheckState(Qt.Unchecked if already else Qt.Checked)
            check.setData(Qt.UserRole, item)
            self.table.setItem(row, 0, check)
            self.table.setItem(row, 1, QTableWidgetItem(item["dir"]))
            self.table.setItem(row, 2, QTableWidgetItem(item["name"]))
            self.table.setItem(row, 3, QTableWidgetItem(item["gmail"]))

    def _set_all(self, state):
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(state)

    def _import_selected(self):
        base = self.path_edit.text().strip()
        count = 0
        for row in range(self.table.rowCount()):
            check = self.table.item(row, 0)
            if check.checkState() != Qt.Checked:
                continue
            item = check.data(Qt.UserRole)
            if self._already_imported(base, item["dir"]):
                continue
            self.store.add_profile(name=item["name"], gmail=item["gmail"],
                                   chrome_base=base, chrome_profile_dir=item["dir"])
            count += 1
        self.imported = count
        if count == 0 and self.table.rowCount() == 0:
            QMessageBox.information(self, self.windowTitle(), tr("scan_none"))
            return
        self.accept()


class LogsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("logs_title"))
        self.setMinimumSize(620, 420)
        layout = QVBoxLayout(self)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setPlainText(read_log() or tr("logs_empty"))
        view.moveCursor(view.textCursor().MoveOperation.End)
        layout.addWidget(view)
        close_btn = QPushButton(tr("ok"))
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close_btn)
        layout.addLayout(row)


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
