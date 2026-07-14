# -*- coding: utf-8 -*-
"""Main window: tabs (All / Favorites / custom groups), profile table,
search, menu-driven actions, status bar and group management.

Note: the v1.0.1 app had a sponsor button ("ឧបត្ថម្ភ") at the right end of
the bottom toolbar. It was removed per the v1.1 brief — intentionally not
recreated in this rebuild.
"""

import os
import subprocess
import sys
import time

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QBrush, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFileDialog, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QTabBar,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

try:
    import psutil
except ImportError:  # CPU/RAM readout simply hides if psutil is missing
    psutil = None

from . import i18n, optimize
from .chrome import GMAIL_SIGNUP_URL, ChromeLauncher, find_chrome
from .dialogs import (
    DELETE_CANCELLED, DELETE_GROUP_AND_PROFILES, GroupDialog, LogsDialog,
    ProfileDialog, ScanImportDialog, ask_delete_group, ask_yes_no,
)
from .i18n import tr
from .logger import log
from .storage import ProfileStore

APP_VERSION = "1.1.0"

TAB_ALL = "__all__"
TAB_FAVORITES = "__favorites__"
FIXED_TABS = 2  # All + Favorites stay pinned at indexes 0 and 1

COL_STATUS, COL_FAV, COL_NAME, COL_KEY, COL_GMAIL, COL_PASSWORD, COL_NOTES = range(7)
RUNNING_COLOR = QColor("#1a9c40")
FAVORITE_COLOR = QColor("#f0a500")
LAUNCH_CONFIRM_THRESHOLD = 5


class MainWindow(QMainWindow):
    def __init__(self, store: ProfileStore):
        super().__init__()
        self.store = store
        self.launcher = ChromeLauncher()
        self._started_at = time.monotonic()
        i18n.set_language(store.settings.get("language", "km"))

        self._build_ui()
        self._build_menus()
        self.retranslate()
        self.rebuild_tabs()
        self.refresh_table()

        # live running/idle indicator refresh
        self._run_timer = QTimer(self)
        self._run_timer.setInterval(2000)
        self._run_timer.timeout.connect(self._refresh_running_state)
        self._run_timer.start()
        # status bar clock + CPU/RAM
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1000)
        self._status_timer.timeout.connect(self._update_status_bar)
        self._status_timer.start()

    # ---------- UI construction ----------

    def _build_ui(self):
        self.resize(1020, 640)
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 10, 12, 6)
        root.setSpacing(8)

        self.search_edit = QLineEdit()
        self.search_edit.textChanged.connect(self.refresh_table)
        root.addWidget(self.search_edit)

        self.tab_bar = QTabBar()
        self.tab_bar.setMovable(True)  # drag-and-drop group reorder
        self.tab_bar.setUsesScrollButtons(True)
        self.tab_bar.setDrawBase(False)
        self.tab_bar.setExpanding(False)
        self.tab_bar.currentChanged.connect(lambda _i: self.refresh_table())
        self.tab_bar.tabMoved.connect(self._on_tab_moved)
        self.tab_bar.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tab_bar.customContextMenuRequested.connect(self._tab_context_menu)
        root.addWidget(self.tab_bar)

        self.table = QTableWidget(0, 7)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)  # ctrl+click multi-select
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_context_menu)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        self.table.cellClicked.connect(self._on_cell_clicked)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(COL_STATUS, 70)
        self.table.setColumnWidth(COL_FAV, 90)
        self.table.setColumnWidth(COL_NAME, 220)
        self.table.setColumnWidth(COL_KEY, 110)
        self.table.setColumnWidth(COL_GMAIL, 220)
        self.table.setColumnWidth(COL_PASSWORD, 110)
        root.addWidget(self.table, 1)

        # status bar: uptime + CPU/RAM on the left, Create Gmail on the right
        self.uptime_label = QLabel()
        self.uptime_label.setStyleSheet("color: #e08a00; font-weight: 700; padding: 0 8px;")
        self.sys_label = QLabel()
        self.sys_label.setStyleSheet("color: #2f8a3b; font-weight: 700; padding: 0 8px;")
        self.chk_create_gmail = QCheckBox()
        self.chk_create_gmail.setChecked(bool(self.store.settings.get("create_gmail")))
        self.chk_create_gmail.toggled.connect(self._on_create_gmail_toggled)
        status = self.statusBar()
        status.addWidget(self.uptime_label)
        status.addWidget(self.sys_label)
        status.addPermanentWidget(self.chk_create_gmail)
        self._update_status_bar()

        QShortcut(QKeySequence.Find, self, activated=lambda: self.search_edit.setFocus())
        QShortcut(QKeySequence.Delete, self.table, activated=self.delete_selected_profiles)

    def _build_menus(self):
        bar = self.menuBar()

        # View: refresh + create + scan + import/export + close all + logs
        self.menu_view = bar.addMenu("")
        self.act_refresh = QAction(self)
        self.act_refresh.setShortcut(QKeySequence.Refresh)
        self.act_refresh.triggered.connect(self._full_refresh)
        self.act_new_profile = QAction(self)
        self.act_new_profile.setShortcut(QKeySequence.New)
        self.act_new_profile.triggered.connect(self.create_profile)
        self.act_add_group = QAction(self)
        self.act_add_group.triggered.connect(self.create_group)
        self.act_scan_view = QAction(self)
        self.act_scan_view.triggered.connect(self.scan_chrome_profiles)
        self.act_import = QAction(self)
        self.act_import.triggered.connect(self._import)
        self.act_export_all = QAction(self)
        self.act_export_all.triggered.connect(self._export_all)
        self.act_close_all_view = QAction(self)
        self.act_close_all_view.triggered.connect(self.close_all_chrome)
        self.act_logs = QAction(self)
        self.act_logs.triggered.connect(lambda: LogsDialog(self).exec())
        self.menu_view.addAction(self.act_refresh)
        self.menu_view.addSeparator()
        self.menu_view.addActions([self.act_new_profile, self.act_add_group, self.act_scan_view])
        self.menu_view.addSeparator()
        self.menu_view.addActions([self.act_import, self.act_export_all])
        self.menu_view.addSeparator()
        self.menu_view.addActions([self.act_close_all_view, self.act_logs])

        # Session: backups, restore, data folder, scan, close all
        self.menu_session = bar.addMenu("")
        self.act_backup = QAction(self)
        self.act_backup.triggered.connect(self._backup_now)
        self.act_backup_data = QAction(self)
        self.act_backup_data.triggered.connect(self._backup_data)
        self.act_restore_data = QAction(self)
        self.act_restore_data.triggered.connect(self._restore_data)
        self.act_open_data = QAction(self)
        self.act_open_data.triggered.connect(self._open_data_folder)
        self.act_scan_session = QAction(self)
        self.act_scan_session.triggered.connect(self.scan_chrome_profiles)
        self.act_close_all = QAction(self)
        self.act_close_all.triggered.connect(self.close_all_chrome)
        self.menu_session.addActions([self.act_backup, self.act_backup_data, self.act_restore_data,
                                      self.act_open_data, self.act_scan_session])
        self.menu_session.addSeparator()
        self.menu_session.addAction(self.act_close_all)

        # Optimize: clear caches for selected / all, with a dry-run toggle
        self.menu_optimize = bar.addMenu("")
        self.act_opt_selected = QAction(self)
        self.act_opt_selected.triggered.connect(lambda: self.optimize_profiles(self._selected_profiles()))
        self.act_opt_all = QAction(self)
        self.act_opt_all.triggered.connect(lambda: self.optimize_profiles(list(self.store.profiles)))
        self.act_opt_dry = QAction(self)
        self.act_opt_dry.setCheckable(True)
        self.menu_optimize.addActions([self.act_opt_selected, self.act_opt_all])
        self.menu_optimize.addSeparator()
        self.menu_optimize.addAction(self.act_opt_dry)

        self.menu_help = bar.addMenu("")
        self.act_about = QAction(self)
        self.act_about.triggered.connect(self._show_about)
        self.menu_help.addAction(self.act_about)
        # The v1.0.1 Help menu also carried the sponsor entry point — not recreated.

        self.menu_language = bar.addMenu("")
        for code, label in i18n.LANGS.items():
            act = QAction(label, self)
            act.setCheckable(True)
            act.setData(code)
            act.triggered.connect(lambda _checked=False, c=code: self._set_language(c))
            self.menu_language.addAction(act)

    # ---------- i18n ----------

    def retranslate(self):
        self.setWindowTitle(f"{tr('app_title')} Version {APP_VERSION}")
        self.search_edit.setPlaceholderText(tr("search_placeholder"))
        self.menu_view.setTitle(tr("menu_view"))
        self.act_refresh.setText(tr("act_refresh"))
        self.act_new_profile.setText(tr("btn_add_profile"))
        self.act_add_group.setText(tr("btn_add_group"))
        self.act_scan_view.setText(tr("act_scan"))
        self.act_import.setText(tr("ie_import"))
        self.act_export_all.setText(tr("ie_export_all"))
        self.act_close_all_view.setText(tr("act_close_all"))
        self.act_logs.setText(tr("act_logs"))
        self.menu_session.setTitle(tr("menu_session"))
        self.act_backup.setText(tr("act_backup_now"))
        self.act_backup_data.setText(tr("act_backup_data"))
        self.act_restore_data.setText(tr("act_restore_data"))
        self.act_open_data.setText(tr("act_open_data_folder"))
        self.act_scan_session.setText(tr("act_scan"))
        self.act_close_all.setText(tr("act_close_all"))
        self.menu_optimize.setTitle(tr("menu_optimize"))
        self.act_opt_selected.setText(tr("act_opt_selected"))
        self.act_opt_all.setText(tr("act_opt_all"))
        self.act_opt_dry.setText(tr("act_opt_dry"))
        self.menu_help.setTitle(tr("menu_help"))
        self.act_about.setText(tr("act_about"))
        self.menu_language.setTitle(tr("menu_language"))
        for act in self.menu_language.actions():
            act.setChecked(act.data() == i18n.current_language())
        self.table.setHorizontalHeaderLabels([
            tr("col_status"), tr("col_fav"), tr("col_name"), tr("col_key"),
            tr("col_gmail"), tr("col_password"), tr("col_notes"),
        ])
        self.chk_create_gmail.setText(tr("chk_create_gmail"))

    def _set_language(self, code: str):
        i18n.set_language(code)
        self.store.settings["language"] = code
        self.store.save_settings()
        self.retranslate()
        self.rebuild_tabs()
        self.refresh_table()

    # ---------- status bar ----------

    def _update_status_bar(self):
        elapsed = int(time.monotonic() - self._started_at)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self.uptime_label.setText(f"🕐 {h:02d}:{m:02d}:{s:02d}")
        if psutil:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            self.sys_label.setText(f"💻 CPU: {cpu:.0f}% | RAM: {ram:.0f}%")
        else:
            self.sys_label.setText("")

    # ---------- tabs ----------

    def current_tab_id(self) -> str:
        idx = self.tab_bar.currentIndex()
        return self.tab_bar.tabData(idx) if idx >= 0 else TAB_ALL

    def rebuild_tabs(self):
        current = self.current_tab_id()
        self.tab_bar.blockSignals(True)
        while self.tab_bar.count():
            self.tab_bar.removeTab(0)
        self.tab_bar.addTab("")
        self.tab_bar.setTabData(0, TAB_ALL)
        self.tab_bar.addTab("")
        self.tab_bar.setTabData(1, TAB_FAVORITES)
        for g in self.store.groups:
            idx = self.tab_bar.addTab("")
            self.tab_bar.setTabData(idx, g["id"])
            self.tab_bar.setTabTextColor(idx, QColor(g.get("color") or "#4f8ef7"))
        self._update_tab_labels()
        for i in range(self.tab_bar.count()):
            if self.tab_bar.tabData(i) == current:
                self.tab_bar.setCurrentIndex(i)
                break
        self.tab_bar.blockSignals(False)

    def _update_tab_labels(self):
        """Live profile-count badge on every tab, custom groups included."""
        profiles = self.store.profiles
        for i in range(self.tab_bar.count()):
            tab_id = self.tab_bar.tabData(i)
            if tab_id == TAB_ALL:
                self.tab_bar.setTabText(i, f"{tr('tab_all')} ({len(profiles)})")
            elif tab_id == TAB_FAVORITES:
                n = sum(1 for p in profiles if p.get("favorite"))
                self.tab_bar.setTabText(i, f"{tr('tab_favorites')} ({n})")
            else:
                g = self.store.group_by_id(tab_id)
                if g:
                    self.tab_bar.setTabText(i, f"{g['name']} ({self.store.group_count(tab_id)})")

    def _on_tab_moved(self, _from: int, _to: int):
        # Pinned tabs (All/Favorites) must stay at 0 and 1; otherwise persist
        # the new custom-group order.
        ids = [self.tab_bar.tabData(i) for i in range(self.tab_bar.count())]
        if ids[:FIXED_TABS] != [TAB_ALL, TAB_FAVORITES]:
            self.rebuild_tabs()
            return
        self.store.reorder_groups([tid for tid in ids if tid not in (TAB_ALL, TAB_FAVORITES)])

    # ---------- table ----------

    def _visible_profiles(self) -> list:
        tab_id = self.current_tab_id()
        query = self.search_edit.text().strip().casefold()
        result = []
        for p in self.store.profiles:
            if tab_id == TAB_FAVORITES and not p.get("favorite"):
                continue
            if tab_id not in (TAB_ALL, TAB_FAVORITES) and p.get("group_id") != tab_id:
                continue
            if query and query not in " ".join(
                    [p.get("name", ""), p.get("key", ""), p.get("gmail", ""), p.get("notes", "")]).casefold():
                continue
            result.append(p)
        result.sort(key=lambda p: (not self.launcher.is_running(p["id"]), p.get("name", "").casefold()))
        return result

    def refresh_table(self):
        self._update_tab_labels()
        profiles = self._visible_profiles()
        self.table.setRowCount(len(profiles))
        for row, p in enumerate(profiles):
            running = self.launcher.is_running(p["id"])
            group = self.store.group_by_id(p.get("group_id", ""))

            status_item = QTableWidgetItem("1" if running else "0")
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setData(Qt.UserRole, p["id"])

            fav_item = QTableWidgetItem(tr("col_fav") if p.get("favorite") else "")
            fav_item.setTextAlignment(Qt.AlignCenter)
            fav_item.setForeground(QBrush(FAVORITE_COLOR))

            name_item = QTableWidgetItem(p.get("name", ""))
            if running:
                name_item.setForeground(QBrush(RUNNING_COLOR))
                status_item.setForeground(QBrush(RUNNING_COLOR))
            if group:
                name_item.setToolTip(group["name"])
                name_item.setForeground(QBrush(QColor(group.get("color") or "#4f8ef7"))
                                        if not running else QBrush(RUNNING_COLOR))

            gmail_item = QTableWidgetItem(p.get("gmail", ""))
            gmail_item.setForeground(QBrush(QColor("#2f8a3b")))

            self.table.setItem(row, COL_STATUS, status_item)
            self.table.setItem(row, COL_FAV, fav_item)
            self.table.setItem(row, COL_NAME, name_item)
            self.table.setItem(row, COL_KEY, QTableWidgetItem(p.get("key", "")))
            self.table.setItem(row, COL_GMAIL, gmail_item)
            self.table.setItem(row, COL_PASSWORD, QTableWidgetItem(p.get("password", "")))
            self.table.setItem(row, COL_NOTES, QTableWidgetItem(p.get("notes", "")))

    def _refresh_running_state(self):
        # cheap periodic poll; repaint only when something changed
        running_now = self.launcher.running_ids()
        if running_now != getattr(self, "_last_running", None):
            self._last_running = running_now
            self.refresh_table()

    def _full_refresh(self):
        self.rebuild_tabs()
        self.refresh_table()

    def _selected_profiles(self) -> list:
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        out = []
        for row in rows:
            item = self.table.item(row, COL_STATUS)
            if item:
                p = self.store.profile_by_id(item.data(Qt.UserRole))
                if p:
                    out.append(p)
        return out

    # ---------- profile actions ----------

    def _on_cell_clicked(self, row: int, col: int):
        if col == COL_FAV:
            item = self.table.item(row, COL_STATUS)
            p = self.store.profile_by_id(item.data(Qt.UserRole)) if item else None
            if p:
                self.store.update_profile(p["id"], favorite=not p.get("favorite"))
                self.refresh_table()

    def _on_double_click(self, row: int, _col: int):
        item = self.table.item(row, COL_STATUS)
        p = self.store.profile_by_id(item.data(Qt.UserRole)) if item else None
        if p:
            self.launch_profile(p)

    def launch_profile(self, profile: dict, url: str = "", quiet: bool = False) -> bool:
        chrome = find_chrome(self.store.settings.get("chrome_path", ""))
        if not chrome:
            QMessageBox.critical(self, tr("app_title"), tr("msg_chrome_not_found"))
            return False
        # duplicate-launch prevention
        if self.launcher.is_running(profile["id"]):
            if not quiet:
                QMessageBox.information(self, tr("app_title"),
                                        tr("msg_already_running", name=profile.get("name", "")))
            return False
        if not url:
            url = profile.get("launch_url", "")
            if self.chk_create_gmail.isChecked():
                url = GMAIL_SIGNUP_URL
        if self.store.is_system_profile(profile):
            # existing Chrome profile on this PC: reuse the real User Data dir
            started = self.launcher.launch(
                profile["id"], chrome, user_data_dir=profile["chrome_base"], url=url,
                profile_directory=profile["chrome_profile_dir"])
        else:
            started = self.launcher.launch(
                profile["id"], chrome, user_data_dir=self.store.user_data_dir(profile), url=url)
        if started:
            log().info("launched profile %s (%s)", profile.get("name"), profile.get("key"))
            self.store.update_profile(profile["id"], last_used=time.strftime("%Y-%m-%d %H:%M:%S"))
            self.refresh_table()
        return started

    def launch_profiles(self, profiles: list):
        pending = [p for p in profiles if not self.launcher.is_running(p["id"])]
        if len(pending) > LAUNCH_CONFIRM_THRESHOLD:
            if not ask_yes_no(self, tr("app_title"), tr("msg_launch_many", n=len(pending))):
                return
        for p in pending:
            self.launch_profile(p, quiet=True)

    def create_profile(self):
        dlg = ProfileDialog(self.store, self)
        tab_id = self.current_tab_id()
        if tab_id not in (TAB_ALL, TAB_FAVORITES):
            idx = dlg.group_combo.findData(tab_id)
            if idx >= 0:
                dlg.group_combo.setCurrentIndex(idx)
        if dlg.exec():
            self.store.add_profile(**dlg.result_values())
            log().info("created profile")
            self._full_refresh()

    def edit_profile(self, profile: dict):
        dlg = ProfileDialog(self.store, self, profile=profile)
        if dlg.exec():
            self.store.update_profile(profile["id"], **dlg.result_values())
            self._full_refresh()

    def set_launch_url(self, profile: dict):
        url, ok = QInputDialog.getText(self, tr("dlg_set_url_title"), tr("dlg_set_url_prompt"),
                                       text=profile.get("launch_url", ""))
        if ok:
            self.store.update_profile(profile["id"], launch_url=url.strip())

    def export_profile(self, profile: dict):
        default = f"{profile.get('key', 'profile')}.json"
        path, _ = QFileDialog.getSaveFileName(self, tr("ctx_export_profile"), default,
                                              "JSON (*.json);;CSV (*.csv)")
        if path:
            self.store.export_profiles([profile], path)
            QMessageBox.information(self, tr("app_title"), tr("export_done", path=path))

    def delete_selected_profiles(self):
        profiles = self._selected_profiles()
        if not profiles:
            return
        if len(profiles) == 1:
            text = tr("msg_confirm_delete_profile", name=profiles[0].get("name", ""))
        else:
            text = tr("msg_confirm_delete_profiles", n=len(profiles))
        if not ask_yes_no(self, tr("app_title"), text):
            return
        # disk data is only removed after its own explicit confirmation, and
        # only for app-owned isolated profiles (never the real Chrome data)
        isolated = [p for p in profiles if not self.store.is_system_profile(p)]
        wipe_disk = False
        if isolated:
            wipe_disk = ask_yes_no(self, tr("app_title"),
                                   tr("msg_delete_disk_folders", n=len(isolated)))
        for p in profiles:
            self.launcher.close(p["id"])
            if wipe_disk:
                self.store.delete_profile_disk_data(p)
        self.store.delete_profiles([p["id"] for p in profiles])
        log().info("deleted %d profile(s)", len(profiles))
        self._full_refresh()

    # ---------- scan & import / optimize ----------

    def scan_chrome_profiles(self):
        dlg = ScanImportDialog(self.store, self)
        if dlg.exec() and dlg.imported:
            log().info("imported %d system Chrome profile(s)", dlg.imported)
            self._full_refresh()
            QMessageBox.information(self, tr("scan_title"), tr("scan_imported", n=dlg.imported))

    def optimize_profiles(self, profiles: list):
        if not profiles:
            return
        dry_run = self.act_opt_dry.isChecked()
        running = [p for p in profiles if self.launcher.is_running(p["id"])]
        targets = [p for p in profiles if not self.launcher.is_running(p["id"])]
        if not dry_run and targets:
            if not ask_yes_no(self, tr("menu_optimize"), tr("opt_confirm", n=len(targets))):
                return
        freed = 0
        seen_roots = set()
        for p in targets:
            freed += optimize.optimize_profile(self.store.profile_content_dir(p), dry_run)
            if not self.store.is_system_profile(p):
                root = self.store.user_data_dir(p)
                if root not in seen_roots:
                    seen_roots.add(root)
                    freed += optimize.optimize_user_data_root(root, dry_run)
        mb = f"{freed / (1024 * 1024):.1f}"
        msg = tr("opt_dry_result" if dry_run else "opt_result", mb=mb, n=len(targets))
        if running:
            msg += "\n" + tr("opt_skipped_running", n=len(running))
        log().info("optimize (%s): %s MB across %d profile(s)",
                   "dry-run" if dry_run else "real", mb, len(targets))
        QMessageBox.information(self, tr("menu_optimize"), msg)

    # ---------- context menus ----------

    def _table_context_menu(self, pos: QPoint):
        profiles = self._selected_profiles()
        if not profiles:
            return
        menu = QMenu(self)
        if len(profiles) == 1:
            p = profiles[0]
            menu.addAction(tr("ctx_launch"), lambda: self.launch_profile(p))
            if self.launcher.is_running(p["id"]):
                menu.addAction(tr("ctx_close"), lambda: (self.launcher.close(p["id"]), self.refresh_table()))
            menu.addSeparator()
            fav_key = "ctx_remove_fav" if p.get("favorite") else "ctx_add_fav"
            menu.addAction(tr(fav_key), lambda: (
                self.store.update_profile(p["id"], favorite=not p.get("favorite")), self.refresh_table()))
            menu.addAction(tr("ctx_edit"), lambda: self.edit_profile(p))
            menu.addAction(tr("ctx_set_url"), lambda: self.set_launch_url(p))
            menu.addAction(tr("ctx_export_profile"), lambda: self.export_profile(p))
            menu.addAction(tr("ctx_create_gmail"), lambda: self.launch_profile(p, url=GMAIL_SIGNUP_URL))
            menu.addSeparator()
            menu.addAction(tr("act_opt_selected"), lambda: self.optimize_profiles([p]))
            move_menu = menu.addMenu(tr("ctx_move_to_group"))
            delete_text = tr("ctx_delete_profile")
        else:
            menu.addAction(tr("ctx_launch"), lambda: self.launch_profiles(profiles))
            menu.addSeparator()
            menu.addAction(tr("act_opt_selected"), lambda: self.optimize_profiles(profiles))
            move_menu = menu.addMenu(tr("ctx_move_selected_to_group", n=len(profiles)))
            delete_text = tr("ctx_delete_profiles", n=len(profiles))

        pids = [p["id"] for p in profiles]
        move_menu.addAction(tr("group_none"),
                            lambda: (self.store.move_profiles_to_group(pids, ""), self._full_refresh()))
        for g in self.store.groups:
            move_menu.addAction(g["name"], lambda _=False, gid=g["id"]: (
                self.store.move_profiles_to_group(pids, gid), self._full_refresh()))

        menu.addSeparator()
        menu.addAction(delete_text, self.delete_selected_profiles)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _tab_context_menu(self, pos: QPoint):
        idx = self.tab_bar.tabAt(pos)
        if idx < 0:
            return
        tab_id = self.tab_bar.tabData(idx)
        if tab_id in (TAB_ALL, TAB_FAVORITES):
            return  # built-in tabs are not editable
        group = self.store.group_by_id(tab_id)
        if not group:
            return
        members = [p for p in self.store.profiles if p.get("group_id") == tab_id]
        menu = QMenu(self)
        menu.addAction(tr("tabctx_rename_group"), lambda: self.rename_group(group))
        menu.addAction(tr("tabctx_edit_group"), lambda: self.edit_group(group))
        menu.addSeparator()
        menu.addAction(tr("tabctx_launch_group"), lambda: self.launch_profiles(members))
        menu.addAction(tr("tabctx_close_group"), lambda: (
            self.launcher.close_many([p["id"] for p in members]), self.refresh_table()))
        menu.addAction(tr("tabctx_export_group"), lambda: self.export_group(group, members))
        menu.addSeparator()
        menu.addAction(tr("tabctx_delete_group"), lambda: self.delete_group(group))
        menu.exec(self.tab_bar.mapToGlobal(pos))

    # ---------- group actions ----------

    def create_group(self):
        dlg = GroupDialog(self.store, self)
        if dlg.exec():
            name, color = dlg.result_values()
            self.store.add_group(name, color)
            self._full_refresh()

    def rename_group(self, group: dict):
        dlg = GroupDialog(self.store, self, group=group, title_key="dlg_rename_group_title")
        if dlg.exec():
            name, color = dlg.result_values()
            self.store.update_group(group["id"], name=name, color=color)
            self._full_refresh()

    def edit_group(self, group: dict):
        dlg = GroupDialog(self.store, self, group=group, title_key="dlg_edit_group_title")
        if dlg.exec():
            name, color = dlg.result_values()
            self.store.update_group(group["id"], name=name, color=color)
            self._full_refresh()

    def delete_group(self, group: dict):
        count = self.store.group_count(group["id"])
        choice = ask_delete_group(self, group["name"], count)
        if choice == DELETE_CANCELLED:
            return
        cascade = choice == DELETE_GROUP_AND_PROFILES
        wipe_disk = False
        if cascade and count:
            # disk folders are never deleted silently — separate confirmation
            wipe_disk = ask_yes_no(self, tr("dlg_delete_group_title"),
                                   tr("msg_delete_disk_folders", n=count))
        removed = self.store.delete_group(group["id"], delete_profiles=cascade)
        if cascade:
            for p in removed:
                self.launcher.close(p["id"])
                if wipe_disk:
                    self.store.delete_profile_disk_data(p)
        log().info("deleted group %s (cascade=%s)", group.get("name"), cascade)
        self._full_refresh()

    def export_group(self, group: dict, members: list):
        default = f"{group['name']}.csv"
        path, _ = QFileDialog.getSaveFileName(self, tr("tabctx_export_group"), default,
                                              "CSV (*.csv);;JSON (*.json)")
        if path:
            self.store.export_profiles(members, path)
            QMessageBox.information(self, tr("app_title"), tr("export_done", path=path))

    # ---------- import / export / backups ----------

    def _export_all(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("ie_export_all"), "profiles_export.json",
                                              "JSON (*.json);;CSV (*.csv)")
        if path:
            self.store.export_profiles(self.store.profiles, path)
            QMessageBox.information(self, tr("app_title"), tr("export_done", path=path))

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("ie_import"), "", "JSON (*.json)")
        if not path:
            return
        try:
            n = self.store.import_profiles(path)
        except (ValueError, KeyError, OSError) as e:
            QMessageBox.warning(self, tr("app_title"), tr("import_failed", err=str(e)))
            return
        log().info("imported %d profile(s) from %s", n, path)
        self._full_refresh()
        QMessageBox.information(self, tr("app_title"), tr("import_done", n=n))

    def _backup_now(self):
        self.store.save()
        QMessageBox.information(self, tr("app_title"),
                                tr("backup_data_done", path=self.store.backups_dir))

    def _backup_data(self):
        default = time.strftime("profile_data_%Y%m%d_%H%M%S.zip")
        path, _ = QFileDialog.getSaveFileName(self, tr("act_backup_data"), default, "ZIP (*.zip)")
        if not path:
            return
        self.store.backup_data_zip(path)
        log().info("data backup written to %s", path)
        QMessageBox.information(self, tr("app_title"), tr("backup_data_done", path=path))

    def _restore_data(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("act_restore_data"), "", "ZIP (*.zip)")
        if not path:
            return
        if not ask_yes_no(self, tr("act_restore_data"), tr("restore_confirm", path=path)):
            return
        self.close_all_chrome()
        try:
            self.store.restore_data_zip(path)
        except (ValueError, OSError) as e:
            QMessageBox.warning(self, tr("app_title"), tr("import_failed", err=str(e)))
            return
        log().info("data restored from %s", path)
        self._full_refresh()
        QMessageBox.information(self, tr("app_title"), tr("restore_done"))

    # ---------- misc ----------

    def close_all_chrome(self):
        self.launcher.close_all()
        self.refresh_table()

    def _open_data_folder(self):
        path = self.store.data_dir
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa: S606 - opens Explorer on the data folder
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _show_about(self):
        QMessageBox.about(self, tr("act_about"), tr("about_text", version=APP_VERSION))

    def _on_create_gmail_toggled(self, checked: bool):
        self.store.settings["create_gmail"] = checked
        self.store.save_settings()
