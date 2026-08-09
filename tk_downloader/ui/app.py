"""TK Downloader — the Flet application shell.

Threading model (important):

* **UI thread / asyncio loop** – owns every Flet control. All repainting happens
  in :meth:`TKApp._ui_tick`, an async task that runs a few times a second.
* **Monitor thread** – :class:`~tk_downloader.monitor.SystemMonitor` samples psutil
  (a blocking call) and only *stores* the snapshot; the async tick paints it.
* **Worker threads** – yt-dlp downloads. Their callbacks never touch a control;
  they just mark a row id dirty. The tick syncs the dirty rows.

Because of that split, no download, no extraction and no psutil sample can ever
block or flood the interface.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import flet as ft

from .. import __version__
from ..config import Settings, app_data_dir, archive_path, state_path
from ..cookies import SUPPORTED_BROWSERS, verify_browser_cookies
from ..downloader import DownloadManager, has_ffmpeg
from ..i18n import LANGUAGES, Translator
from ..models import ItemStatus, NamingMode, QueueItem, Quality
from ..monitor import SystemMonitor, SystemSnapshot
from ..naming import naming_example
from ..state import StateStore
from ..system_actions import SHUTDOWN_GRACE_SECONDS, open_folder, shutdown_pc
from ..utils import format_clock, human_speed
from .theme import Palette, build_theme
from .widgets import (
    TABLE_MIN_WIDTH, QueueRow, card, group_header, queue_header, section_title, stat_chip,
)

UI_TICK_SECONDS = 0.4
LEFT_PANEL_WIDTH = 400
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
MAX_LOG_LINES = 300
QUALITY_ORDER = (
    Quality.BEST, Quality.P1080, Quality.P720, Quality.P480, Quality.P360, Quality.AUDIO,
)


class TKApp:
    """Builds and drives the whole interface."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.settings = Settings.load()
        self.t = Translator(self.settings.language)

        self.store = StateStore(state_path(), archive_path())
        self.manager = DownloadManager(
            self.settings,
            self.store,
            on_items_changed=self._mark_rebuild,
            on_item_update=self._mark_dirty,
            on_batch_finished=self._on_batch_finished,
            on_log=self._append_log,
        )

        # Live machine stats: written by the monitor thread, read by the UI tick.
        self._snapshot = SystemSnapshot()
        self.monitor = SystemMonitor(self._on_snapshot, interval=1.5,
                                     disk_path=self._safe_disk_path())

        self.palette = Palette(self.settings.theme_mode == "dark")
        self.rows: dict[str, QueueRow] = {}
        self._dirty: set[str] = set()
        self._needs_rebuild = True
        self._log_lines: list[str] = []
        self._log_dirty = True
        self._filter_profile = "*"
        self._search = ""
        self._status_message = ""
        self._shutdown_dialog: ft.AlertDialog | None = None
        self._shutdown_cancelled = False

        self._configure_page()
        self.build()
        self._restore_previous_session()
        self.monitor.start()
        self.page.run_task(self._ui_tick)

    # =====================================================================================
    # Page setup
    # =====================================================================================
    def _configure_page(self) -> None:
        page = self.page
        page.title = f"TK Downloader v{__version__}"
        page.window.width = 1360
        page.window.height = 860
        page.window.min_width = 1080
        page.window.min_height = 700
        page.padding = 0
        page.spacing = 0
        self.font_family = self._register_fonts()
        self._apply_theme()

        self.file_picker = ft.FilePicker()
        page.services.append(self.file_picker)
        page.on_close = self._on_page_close
        page.on_disconnect = self._on_page_close

    def _register_fonts(self) -> str | None:
        """Register a bundled UI font if one was dropped into ``assets/fonts``.

        Khmer needs a font that actually contains Khmer glyphs. Most systems have
        one (Windows ships Khmer UI, macOS ships Khmer Sangam MN) and Flutter falls
        back to it automatically, so nothing is bundled by default. On a machine
        without one — some Linux installs — copy any Khmer-capable ``.ttf`` into
        ``tk_downloader/assets/fonts/`` and it is picked up here automatically.
        See the README for details.
        """
        fonts_dir = ASSETS_DIR / "fonts"
        if not fonts_dir.is_dir():
            return None
        candidates = sorted(list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf")))
        if not candidates:
            return None
        family = "TK UI"
        # Paths are relative to assets_dir, which ft.run() points at ASSETS_DIR.
        self.page.fonts = {family: f"fonts/{candidates[0].name}"}
        return family

    def _apply_theme(self) -> None:
        dark = self.settings.theme_mode == "dark"
        self.palette = Palette(dark)
        self.page.theme = build_theme(False, self.font_family)
        self.page.dark_theme = build_theme(True, self.font_family)
        self.page.theme_mode = ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT
        self.page.bgcolor = self.palette.bg

    def _safe_disk_path(self) -> str:
        """Deepest existing ancestor of the download folder (psutil needs a real path)."""
        path = Path(self.settings.download_dir).expanduser()
        while not path.exists() and path.parent != path:
            path = path.parent
        return str(path)

    # =====================================================================================
    # Build
    # =====================================================================================
    def build(self) -> None:
        """(Re)create every control. Called on start-up and after a theme switch."""
        self.t.clear_bindings()
        self.rows.clear()
        self.page.controls.clear()
        self.page.overlay.clear()

        self.page.appbar = self._build_appbar()
        self.page.bottom_appbar = self._build_status_bar()

        body = ft.Row(
            [
                ft.Container(
                    content=self._build_left_panel(),
                    width=LEFT_PANEL_WIDTH,
                    padding=ft.Padding.only(left=14, top=12, right=7, bottom=12),
                ),
                ft.Container(
                    content=self._build_right_panel(),
                    expand=True,
                    padding=ft.Padding.only(left=7, top=12, right=14, bottom=12),
                ),
            ],
            spacing=0,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        self.page.add(body)

        self.t.on_change(self._on_language_refresh)
        self._needs_rebuild = True
        self._log_dirty = True
        self.page.update()

    # -- app bar ----------------------------------------------------------------------
    def _build_appbar(self) -> ft.AppBar:
        title = ft.Text("TK Downloader", size=19, weight=ft.FontWeight.BOLD,
                        color=self.palette.text)
        subtitle = ft.Text(size=11, color=self.palette.text_dim)
        self.t.bind(subtitle, "value", "app.subtitle")

        self.language_dropdown = ft.Dropdown(
            value=self.t.language,
            width=158,
            dense=True,
            text_size=13,
            border_color=self.palette.border,
            options=[ft.DropdownOption(key=code, text=name) for code, name in LANGUAGES.items()],
            on_select=self._on_language_change,
            leading_icon=ft.Icons.LANGUAGE,
        )

        dark = self.settings.theme_mode == "dark"
        self.theme_button = ft.IconButton(
            ft.Icons.LIGHT_MODE if dark else ft.Icons.DARK_MODE,
            icon_color=self.palette.accent,
            on_click=self._on_theme_toggle,
        )
        self.t.bind(self.theme_button, "tooltip",
                    "theme.to_light" if dark else "theme.to_dark")

        return ft.AppBar(
            leading=ft.Container(
                content=ft.Icon(ft.Icons.DOWNLOAD_FOR_OFFLINE, color=self.palette.accent, size=28),
                padding=ft.Padding.only(left=14),
            ),
            leading_width=56,
            title=ft.Column([title, subtitle], spacing=0, tight=True),
            center_title=False,
            toolbar_height=62,
            bgcolor=self.palette.surface,
            actions=[
                self.language_dropdown,
                self.theme_button,
                ft.Container(width=8),
            ],
        )

    # -- left panel -------------------------------------------------------------------
    def _build_left_panel(self) -> ft.Control:
        return ft.Column(
            [
                self._build_links_card(),
                self._build_output_card(),
                self._build_naming_card(),
                self._build_quality_card(),
                self._build_performance_card(),
                self._build_cookies_card(),
                self._build_finish_card(),
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _build_links_card(self) -> ft.Control:
        heading = ft.Text()
        self.t.bind(heading, "value", "section.links")

        self.links_field = ft.TextField(
            multiline=True,
            min_lines=5,
            max_lines=8,
            text_size=12,
            border_color=self.palette.border,
            focused_border_color=self.palette.accent,
            color=self.palette.text,
        )
        self.t.bind(self.links_field, "hint_text", "links.hint")

        self.add_button = ft.FilledButton(icon=ft.Icons.PLAYLIST_ADD, on_click=self._on_add_links,
                                          expand=True)
        self.t.bind(self.add_button, "content", "action.add")
        clear_button = ft.OutlinedButton(icon=ft.Icons.CLEAR_ALL,
                                         on_click=lambda e: self._clear_links())
        self.t.bind(clear_button, "content", "action.clear_box")

        note = ft.Text(size=11, color=self.palette.text_dim)
        self.t.bind(note, "value", "links.note")

        return card(
            ft.Column(
                [
                    section_title(heading, self.palette, ft.Icons.LINK),
                    self.links_field,
                    ft.Row([self.add_button, clear_button], spacing=8),
                    note,
                ],
                spacing=10,
                tight=True,
            ),
            self.palette,
        )

    def _build_output_card(self) -> ft.Control:
        heading = ft.Text()
        self.t.bind(heading, "value", "section.output")

        self.folder_field = ft.TextField(
            value=self.settings.download_dir,
            read_only=True,
            dense=True,
            text_size=12,
            expand=True,
            border_color=self.palette.border,
            color=self.palette.text,
        )
        browse = ft.IconButton(ft.Icons.FOLDER_OPEN, icon_color=self.palette.accent,
                               on_click=self._on_pick_folder)
        self.t.bind(browse, "tooltip", "action.browse")
        reveal = ft.IconButton(ft.Icons.LAUNCH, icon_color=self.palette.text_dim,
                               on_click=lambda e: open_folder(self.settings.download_dir))
        self.t.bind(reveal, "tooltip", "action.open_folder")

        return card(
            ft.Column(
                [
                    section_title(heading, self.palette, ft.Icons.SAVE),
                    ft.Row([self.folder_field, browse, reveal], spacing=2,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ],
                spacing=10,
                tight=True,
            ),
            self.palette,
        )

    def _build_naming_card(self) -> ft.Control:
        """Naming section with the mandatory live ``ID.mp4`` + ``ID.txt`` example."""
        heading = ft.Text()
        self.t.bind(heading, "value", "section.naming")

        self.radio_id = ft.Radio(value=NamingMode.ID_ONLY.value, fill_color=self.palette.accent)
        self.radio_title = ft.Radio(value=NamingMode.TITLE_ONLY.value, fill_color=self.palette.accent)
        self.radio_num = ft.Radio(value=NamingMode.NUM_TITLE.value, fill_color=self.palette.accent)
        self.t.bind(self.radio_id, "label", "naming.id_only")
        self.t.bind(self.radio_title, "label", "naming.title_only")
        self.t.bind(self.radio_num, "label", "naming.num_title")

        self.naming_group = ft.RadioGroup(
            value=self.settings.naming_mode,
            on_change=self._on_naming_change,
            content=ft.Column([self.radio_id, self.radio_title, self.radio_num],
                              spacing=0, tight=True),
        )

        example_label = ft.Text(size=11, color=self.palette.text_dim)
        self.t.bind(example_label, "value", "naming.example")
        self.example_video = ft.Text(size=13, weight=ft.FontWeight.W_600,
                                     color=self.palette.accent, font_family="monospace")
        self.example_text = ft.Text(size=13, weight=ft.FontWeight.W_600,
                                    color=self.palette.text, font_family="monospace")
        self.example_note = ft.Text(size=11, color=self.palette.text_dim)

        self.example_box = ft.Container(
            content=ft.Column(
                [
                    example_label,
                    ft.Row([ft.Icon(ft.Icons.MOVIE, size=15, color=self.palette.accent),
                            self.example_video], spacing=7),
                    ft.Row([ft.Icon(ft.Icons.DESCRIPTION, size=15, color=self.palette.text_dim),
                            self.example_text], spacing=7),
                    self.example_note,
                ],
                spacing=5,
                tight=True,
            ),
            padding=10,
            bgcolor=self.palette.surface_hi,
            border_radius=10,
            border=ft.Border.all(1, self.palette.border),
        )

        self.sidecar_checkbox = ft.Checkbox(
            value=self.settings.write_sidecar_always,
            active_color=self.palette.accent,
            on_change=self._on_sidecar_toggle,
        )
        self.t.bind(self.sidecar_checkbox, "label", "naming.always_sidecar")

        self._refresh_naming_example()

        return card(
            ft.Column(
                [
                    section_title(heading, self.palette, ft.Icons.DRIVE_FILE_RENAME_OUTLINE),
                    self.naming_group,
                    self.example_box,
                    self.sidecar_checkbox,
                ],
                spacing=10,
                tight=True,
            ),
            self.palette,
        )

    def _build_quality_card(self) -> ft.Control:
        heading = ft.Text()
        self.t.bind(heading, "value", "section.quality")

        self.quality_dropdown = ft.Dropdown(
            value=self.settings.quality,
            dense=True,
            text_size=13,
            expand=True,
            border_color=self.palette.border,
            leading_icon=ft.Icons.HIGH_QUALITY,
            options=[ft.DropdownOption(key=q.value, text=self._quality_label(q))
                     for q in QUALITY_ORDER],
            on_select=self._on_quality_change,
        )
        self.t.bind(self.quality_dropdown, "label", "quality.label")

        self.concurrency_dropdown = ft.Dropdown(
            value=str(self.settings.concurrency),
            dense=True,
            text_size=13,
            expand=True,
            border_color=self.palette.border,
            leading_icon=ft.Icons.LAYERS,
            options=[ft.DropdownOption(key=str(n), text=str(n)) for n in range(1, 9)],
            on_select=self._on_concurrency_change,
        )
        self.t.bind(self.concurrency_dropdown, "label", "perf.concurrency")

        return card(
            ft.Column(
                [
                    section_title(heading, self.palette, ft.Icons.TUNE),
                    self.quality_dropdown,
                    self.concurrency_dropdown,
                ],
                spacing=12,
                tight=True,
            ),
            self.palette,
        )

    def _build_performance_card(self) -> ft.Control:
        heading = ft.Text()
        self.t.bind(heading, "value", "section.performance")

        self.cpu_checkbox = ft.Checkbox(value=self.settings.use_cpu,
                                        active_color=self.palette.accent,
                                        on_change=self._on_accel_change)
        self.gpu_checkbox = ft.Checkbox(value=self.settings.use_gpu,
                                        active_color=self.palette.accent,
                                        on_change=self._on_accel_change)
        self.t.bind(self.cpu_checkbox, "label", "perf.use_cpu")
        self.t.bind(self.gpu_checkbox, "label", "perf.use_gpu")

        self.accel_hint = ft.Text(size=11, color=self.palette.text_dim)
        self._refresh_accel_hint()

        children: list[ft.Control] = [
            section_title(heading, self.palette, ft.Icons.SPEED),
            ft.Row([self.cpu_checkbox, self.gpu_checkbox], spacing=14),
            self.accel_hint,
        ]

        if not has_ffmpeg():
            warning = ft.Text(size=11, color=self.palette.status_color(ItemStatus.ERROR.value))
            self.t.bind(warning, "value", "perf.ffmpeg_missing")
            children.append(warning)

        return card(ft.Column(children, spacing=10, tight=True), self.palette)

    def _build_cookies_card(self) -> ft.Control:
        heading = ft.Text()
        self.t.bind(heading, "value", "section.cookies")

        options = [ft.DropdownOption(key="", text=self.t("cookies.none"))]
        options += [ft.DropdownOption(key=b, text=b.capitalize()) for b in SUPPORTED_BROWSERS]
        self.cookies_dropdown = ft.Dropdown(
            value=self.settings.cookies_browser,
            dense=True,
            text_size=13,
            expand=True,
            border_color=self.palette.border,
            leading_icon=ft.Icons.COOKIE,
            options=options,
            on_select=self._on_cookies_browser_change,
        )
        self.t.bind(self.cookies_dropdown, "label", "cookies.browser")

        self.cookies_button = ft.OutlinedButton(icon=ft.Icons.DOWNLOAD_DONE,
                                                on_click=self._on_import_cookies)
        self.t.bind(self.cookies_button, "content", "action.import_cookies")

        self.cookies_status = ft.Text(size=11, color=self.palette.text_dim)
        hint = ft.Text(size=11, color=self.palette.text_dim)
        self.t.bind(hint, "value", "cookies.hint")

        return card(
            ft.Column(
                [
                    section_title(heading, self.palette, ft.Icons.LOCK_OPEN),
                    self.cookies_dropdown,
                    self.cookies_button,
                    self.cookies_status,
                    hint,
                ],
                spacing=10,
                tight=True,
            ),
            self.palette,
        )

    def _build_finish_card(self) -> ft.Control:
        heading = ft.Text()
        self.t.bind(heading, "value", "section.finish")

        self.shutdown_checkbox = ft.Checkbox(
            value=self.settings.shutdown_when_done,
            active_color=self.palette.status_color(ItemStatus.ERROR.value),
            on_change=self._on_shutdown_toggle,
        )
        self.t.bind(self.shutdown_checkbox, "label", "finish.shutdown")
        hint = ft.Text(size=11, color=self.palette.text_dim)
        self.t.bind(hint, "value", "finish.shutdown_hint")

        return card(
            ft.Column(
                [
                    section_title(heading, self.palette, ft.Icons.POWER_SETTINGS_NEW),
                    self.shutdown_checkbox,
                    hint,
                ],
                spacing=8,
                tight=True,
            ),
            self.palette,
        )

    # -- right panel ------------------------------------------------------------------
    def _build_right_panel(self) -> ft.Control:
        return ft.Column(
            [
                self._build_timer_card(),
                self._build_toolbar(),
                self._build_queue_card(),
                self._build_log_panel(),
            ],
            spacing=12,
            expand=True,
        )

    def _build_timer_card(self) -> ft.Control:
        """The large live ETA / countdown display."""
        timer_label = ft.Text(size=12, weight=ft.FontWeight.W_700, color=self.palette.text_dim)
        self.t.bind(timer_label, "value", "timer.title")

        self.timer_text = ft.Text("--:--:--", size=52, weight=ft.FontWeight.BOLD,
                                  color=self.palette.accent, font_family="monospace",
                                  no_wrap=True)

        self.elapsed_text = ft.Text("00:00:00", size=12, color=self.palette.text_dim,
                                    font_family="monospace")
        elapsed_label = ft.Text(size=12, color=self.palette.text_dim)
        self.t.bind(elapsed_label, "value", "timer.elapsed")

        self.total_speed_text = ft.Text("-", size=12, color=self.palette.text_dim)
        speed_label = ft.Text(size=12, color=self.palette.text_dim)
        self.t.bind(speed_label, "value", "timer.speed")

        self.overall_bar = ft.ProgressBar(value=0, bar_height=10, border_radius=8,
                                          expand=True,
                                          bgcolor=self.palette.surface_hi,
                                          color=self.palette.accent)
        self.overall_text = ft.Text("0%", size=12, weight=ft.FontWeight.W_600,
                                    color=self.palette.text, width=48,
                                    text_align=ft.TextAlign.RIGHT)

        # Counters
        self.stat_total = ft.Text("0")
        self.stat_done = ft.Text("0")
        self.stat_active = ft.Text("0")
        self.stat_failed = ft.Text("0")
        labels = {}
        for key in ("stats.total", "stats.done", "stats.active", "stats.failed"):
            text = ft.Text()
            self.t.bind(text, "value", key)
            labels[key] = text

        chips = ft.Row(
            [
                stat_chip(ft.Icons.LIST_ALT, self.stat_total, labels["stats.total"], self.palette),
                stat_chip(ft.Icons.CHECK_CIRCLE, self.stat_done, labels["stats.done"],
                          self.palette, self.palette.status_color(ItemStatus.COMPLETED.value)),
                stat_chip(ft.Icons.DOWNLOADING, self.stat_active, labels["stats.active"],
                          self.palette, self.palette.status_color(ItemStatus.DOWNLOADING.value)),
                stat_chip(ft.Icons.ERROR, self.stat_failed, labels["stats.failed"],
                          self.palette, self.palette.status_color(ItemStatus.ERROR.value)),
            ],
            spacing=8,
            wrap=True,
        )

        return card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Column([timer_label, self.timer_text], spacing=0, tight=True),
                            ft.Container(expand=True),
                            chips,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                    ),
                    ft.Row([self.overall_bar, self.overall_text], spacing=10,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Row(
                        [
                            speed_label, self.total_speed_text,
                            ft.Container(width=18),
                            elapsed_label, self.elapsed_text,
                        ],
                        spacing=6,
                    ),
                ],
                spacing=10,
                tight=True,
            ),
            self.palette,
        )

    def _build_toolbar(self) -> ft.Control:
        self.start_button = ft.FilledButton(icon=ft.Icons.PLAY_ARROW, on_click=self._on_start)
        self.pause_button = ft.OutlinedButton(icon=ft.Icons.PAUSE, on_click=self._on_pause,
                                              disabled=True)
        self.retry_button = ft.OutlinedButton(icon=ft.Icons.REFRESH, on_click=self._on_retry_failed)
        self.clear_done_button = ft.OutlinedButton(icon=ft.Icons.CLEANING_SERVICES,
                                                   on_click=self._on_clear_finished)
        self.clear_all_button = ft.OutlinedButton(icon=ft.Icons.DELETE_SWEEP,
                                                  on_click=self._on_clear_all)
        self.t.bind(self.start_button, "content", "action.start")
        self.t.bind(self.pause_button, "content", "action.pause")
        self.t.bind(self.retry_button, "content", "action.retry_failed")
        self.t.bind(self.clear_done_button, "content", "action.clear_finished")
        self.t.bind(self.clear_all_button, "content", "action.clear_all")

        self.profile_filter = ft.Dropdown(
            value="*",
            dense=True,
            text_size=12,
            width=210,
            border_color=self.palette.border,
            leading_icon=ft.Icons.FILTER_ALT,
            options=[ft.DropdownOption(key="*", text=self.t("filter.all"))],
            on_select=self._on_filter_change,
        )
        self.t.bind(self.profile_filter, "label", "filter.profile")

        self.search_field = ft.TextField(
            dense=True, text_size=12, width=200,
            border_color=self.palette.border,
            prefix_icon=ft.Icons.SEARCH,
            on_change=self._on_search_change,
        )
        self.t.bind(self.search_field, "hint_text", "filter.search")

        self.group_switch = ft.Switch(value=self.settings.group_by_profile,
                                      active_color=self.palette.accent,
                                      on_change=self._on_group_toggle)
        self.t.bind(self.group_switch, "label", "filter.group")

        # Note: the two halves are separate rows on purpose. A wrapping row cannot
        # contain an expanding child (Flutter forbids Expanded inside a Wrap), so the
        # buttons wrap on their own while the filters stay pinned to the right.
        return ft.Row(
            [
                ft.Row(
                    [
                        self.start_button, self.pause_button, self.retry_button,
                        self.clear_done_button, self.clear_all_button,
                    ],
                    spacing=8,
                    wrap=True,
                    run_spacing=8,
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [self.group_switch, self.profile_filter, self.search_field],
                    spacing=8,
                    wrap=True,
                    run_spacing=8,
                    alignment=ft.MainAxisAlignment.END,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _build_queue_card(self) -> ft.Control:
        self.queue_list = ft.ListView(expand=True, spacing=0, padding=0,
                                      build_controls_on_demand=True)
        self.empty_text = ft.Text(size=13, color=self.palette.text_dim,
                                  text_align=ft.TextAlign.CENTER)
        self.t.bind(self.empty_text, "value", "table.empty")
        self.empty_holder = ft.Container(content=self.empty_text, alignment=ft.Alignment.CENTER,
                                         padding=30)

        # The table keeps a minimum width so the Title column never collapses; on a
        # narrow window the whole table scrolls sideways instead.
        self.table_body = ft.Column(
            [queue_header(self.t, self.palette), self.empty_holder, self.queue_list],
            spacing=0,
            width=TABLE_MIN_WIDTH,
        )
        self.table_scroller = ft.Row(
            [self.table_body],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self.page.on_resize = self._on_resize
        self._resize_table()

        return ft.Container(
            content=self.table_scroller,
            expand=True,
            bgcolor=self.palette.surface,
            border=ft.Border.all(1, self.palette.border),
            border_radius=12,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

    def _on_resize(self, e: ft.Event) -> None:
        self._resize_table()

    def _resize_table(self) -> None:
        """Give the table all the horizontal room it can get, never less than the minimum."""
        page_width = getattr(self.page, "width", None) or 0
        available = page_width - LEFT_PANEL_WIDTH - 44  # paddings + card border
        self.table_body.width = max(TABLE_MIN_WIDTH, int(available))

    def _build_log_panel(self) -> ft.Control:
        self.log_text = ft.Text("", size=11, color=self.palette.text_dim,
                                font_family="monospace", selectable=True)
        title = ft.Text(size=12, weight=ft.FontWeight.W_700, color=self.palette.text_dim)
        self.t.bind(title, "value", "log.title")
        return ft.Container(
            content=ft.ExpansionTile(
                title=title,
                expanded=False,
                controls=[
                    ft.Container(
                        content=ft.Column([self.log_text], scroll=ft.ScrollMode.AUTO,
                                          height=130, auto_scroll=True),
                        padding=ft.Padding.only(left=14, right=14, bottom=10),
                    )
                ],
                collapsed_bgcolor=self.palette.surface,
                bgcolor=self.palette.surface,
            ),
            bgcolor=self.palette.surface,
            border=ft.Border.all(1, self.palette.border),
            border_radius=12,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

    # -- status bar -------------------------------------------------------------------
    def _build_status_bar(self) -> ft.BottomAppBar:
        """Bottom bar with the mandatory live CPU / RAM readout."""
        dim = self.palette.text_dim

        cpu_label = ft.Text("CPU", size=12, weight=ft.FontWeight.W_700, color=dim)
        self.cpu_value = ft.Text("0%", size=13, weight=ft.FontWeight.BOLD,
                                 color=self.palette.text, width=46,
                                 font_family="monospace")
        self.cpu_bar = ft.ProgressBar(value=0, width=90, bar_height=6, border_radius=4,
                                      bgcolor=self.palette.surface_hi, color=self.palette.accent)

        ram_label = ft.Text("RAM", size=12, weight=ft.FontWeight.W_700, color=dim)
        self.ram_value = ft.Text("0.0 / 0.0 GB (0%)", size=13, weight=ft.FontWeight.BOLD,
                                 color=self.palette.text, font_family="monospace")
        self.ram_bar = ft.ProgressBar(value=0, width=90, bar_height=6, border_radius=4,
                                      bgcolor=self.palette.surface_hi, color=self.palette.accent)

        self.disk_value = ft.Text("-", size=12, color=dim, font_family="monospace")
        disk_label = ft.Text(size=12, color=dim)
        self.t.bind(disk_label, "value", "statusbar.disk")

        self.archive_value = ft.Text("0", size=12, color=dim, font_family="monospace")
        archive_label = ft.Text(size=12, color=dim)
        self.t.bind(archive_label, "value", "statusbar.archive")

        self.status_message = ft.Text(size=12, color=dim, no_wrap=True)
        self.t.bind(self.status_message, "value", "statusbar.ready")

        def divider() -> ft.Control:
            return ft.Container(width=1, height=20, bgcolor=self.palette.border,
                                margin=ft.Margin.symmetric(horizontal=10))

        return ft.BottomAppBar(
            bgcolor=self.palette.surface,
            height=46,
            padding=ft.Padding.symmetric(horizontal=14, vertical=4),
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.MEMORY, size=17, color=self.palette.accent),
                    cpu_label, self.cpu_value, self.cpu_bar,
                    divider(),
                    ft.Icon(ft.Icons.DEVELOPER_BOARD, size=17, color=self.palette.accent),
                    ram_label, self.ram_value, self.ram_bar,
                    divider(),
                    ft.Icon(ft.Icons.STORAGE, size=16, color=dim),
                    disk_label, self.disk_value,
                    divider(),
                    ft.Icon(ft.Icons.INVENTORY_2, size=16, color=dim),
                    archive_label, self.archive_value,
                    ft.Container(expand=True),
                    self.status_message,
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    # =====================================================================================
    # Live refresh (async, on the UI loop)
    # =====================================================================================
    def _on_snapshot(self, snapshot: SystemSnapshot) -> None:
        """Monitor-thread callback: store only, never touch controls from here."""
        self._snapshot = snapshot

    async def _ui_tick(self) -> None:
        """Single repaint loop for the whole app."""
        while True:
            try:
                self._paint()
            except Exception as exc:  # noqa: BLE001 - never let the loop die
                print(f"[TK Downloader] UI tick error: {exc}")
            await asyncio.sleep(UI_TICK_SECONDS)

    def _paint(self) -> None:
        if self._needs_rebuild:
            self._needs_rebuild = False
            self._rebuild_queue_list()

        # Rows whose item changed since the last tick.
        if self._dirty:
            dirty, self._dirty = self._dirty, set()
            for uid in dirty:
                row = self.rows.get(uid)
                if row is not None:
                    row.sync()

        self._paint_stats()
        self._paint_status_bar()
        if self._log_dirty:
            self._log_dirty = False
            self.log_text.value = "\n".join(self._log_lines[-MAX_LOG_LINES:])
        self.page.update()

    def _paint_stats(self) -> None:
        stats = self.manager.stats()
        self.stat_total.value = str(stats["total"])
        self.stat_done.value = str(stats["done"])
        self.stat_active.value = str(stats["active"])
        self.stat_failed.value = str(stats["failed"])

        self.overall_bar.value = stats["overall_progress"]
        self.overall_text.value = f"{stats['overall_progress'] * 100:.0f}%"
        self.total_speed_text.value = human_speed(stats["speed"])
        self.elapsed_text.value = format_clock(stats["elapsed"])
        self.timer_text.value = format_clock(stats["eta"])

        running = stats["running"]
        self.start_button.disabled = running or self.manager.is_expanding
        self.pause_button.disabled = not running

    def _paint_status_bar(self) -> None:
        snapshot = self._snapshot
        self.cpu_value.value = snapshot.format_cpu()
        self.cpu_bar.value = min(1.0, snapshot.cpu_percent / 100.0)
        self.cpu_bar.color = self._load_color(snapshot.cpu_percent)
        self.ram_value.value = snapshot.format_ram()
        self.ram_bar.value = min(1.0, snapshot.ram_percent / 100.0)
        self.ram_bar.color = self._load_color(snapshot.ram_percent)
        self.disk_value.value = f"{snapshot.disk_free_gb:.1f} GB" if snapshot.disk_free_gb else "-"
        self.archive_value.value = str(self.store.archive_size())
        if self._status_message:
            self.status_message.value = self._status_message

    def _load_color(self, percent: float) -> str:
        if percent >= 90:
            return self.palette.status_color(ItemStatus.ERROR.value)
        if percent >= 70:
            return self.palette.status_color(ItemStatus.PROCESSING.value)
        return self.palette.accent

    # -- queue list -------------------------------------------------------------------
    def _mark_dirty(self, item: QueueItem) -> None:
        """Worker-thread callback — cheap by design."""
        self._dirty.add(item.uid)

    def _mark_rebuild(self) -> None:
        self._needs_rebuild = True

    def _visible_items(self) -> list[QueueItem]:
        items = list(self.manager.items)
        if self._filter_profile != "*":
            items = [i for i in items if i.profile == self._filter_profile]
        if self._search:
            needle = self._search.lower()
            items = [i for i in items
                     if needle in i.title.lower() or needle in i.url.lower()
                     or needle in (i.video_id or "").lower()]
        if self.settings.group_by_profile:
            items.sort(key=lambda i: (i.profile.lower(), i.position))
        return items

    def _rebuild_queue_list(self) -> None:
        """Recreate the visible rows (called when items are added/removed/filtered)."""
        items = self._visible_items()
        controls: list[ft.Control] = []
        live: dict[str, QueueRow] = {}
        current_profile: str | None = None

        if self.settings.group_by_profile:
            counts: dict[str, int] = {}
            for item in items:
                counts[item.profile] = counts.get(item.profile, 0) + 1

        for item in items:
            if self.settings.group_by_profile and item.profile != current_profile:
                current_profile = item.profile
                controls.append(group_header(item.profile, counts.get(item.profile, 0),
                                             self.palette))
            row = self.rows.get(item.uid)
            if row is None or row.item is not item:
                row = QueueRow(item, self.t, self.palette, self._on_row_action)
            else:
                row.sync()
            live[item.uid] = row
            controls.append(row.control)

        self.rows = live
        self.queue_list.controls = controls
        self.empty_holder.visible = not controls
        self._refresh_profile_filter()

    def _refresh_profile_filter(self) -> None:
        profiles = self.manager.profiles()
        options = [ft.DropdownOption(key="*", text=self.t("filter.all"))]
        options += [ft.DropdownOption(key=p, text=p) for p in profiles]
        self.profile_filter.options = options
        if self._filter_profile != "*" and self._filter_profile not in profiles:
            self._filter_profile = "*"
            self.profile_filter.value = "*"

    def _refresh_all_rows(self) -> None:
        for row in self.rows.values():
            row.sync()

    # =====================================================================================
    # Event handlers
    # =====================================================================================
    def _on_language_change(self, e: ft.Event) -> None:
        code = self.language_dropdown.value or "en"
        self.settings.language = code
        self.settings.save()
        self.t.set_language(code)
        self.page.update()

    def _on_language_refresh(self) -> None:
        """Re-apply anything that is not a simple bound label."""
        self._refresh_naming_example()
        self._refresh_accel_hint()
        self._refresh_all_rows()
        self._refresh_profile_filter()
        for option, quality in zip(self.quality_dropdown.options, QUALITY_ORDER):
            option.text = self._quality_label(quality)
        if self.cookies_dropdown.options:
            self.cookies_dropdown.options[0].text = self.t("cookies.none")

    def _on_theme_toggle(self, e: ft.Event) -> None:
        self.settings.theme_mode = "light" if self.settings.theme_mode == "dark" else "dark"
        self.settings.save()
        self._apply_theme()
        self.build()  # colors are explicit, so a rebuild is the honest way to swap them

    def _on_naming_change(self, e: ft.Event) -> None:
        self.settings.naming_mode = self.naming_group.value or NamingMode.ID_ONLY.value
        self.settings.save()
        self._refresh_naming_example()
        self.page.update()

    def _on_sidecar_toggle(self, e: ft.Event) -> None:
        self.settings.write_sidecar_always = bool(self.sidecar_checkbox.value)
        self.settings.save()
        self._refresh_naming_example()

    def _refresh_naming_example(self) -> None:
        """Keep the live ``ID.mp4`` / ``ID.txt`` preview in sync with the radio buttons."""
        mode = self.settings.naming
        extension = "mp3" if self.settings.quality_enum is Quality.AUDIO else "mp4"
        video_name, text_name = naming_example(mode, extension)
        self.example_video.value = video_name
        if not text_name and self.settings.write_sidecar_always:
            text_name = Path(video_name).with_suffix(".txt").name
        self.example_text.value = text_name or self.t("naming.no_txt")
        self.example_text.color = (self.palette.text if text_name else self.palette.text_dim)
        self.example_note.value = (
            self.t("naming.sidecar_note") if text_name else self.t("naming.no_txt_note")
        )

    def _quality_label(self, quality: Quality) -> str:
        return self.t(f"quality.{quality.value}")

    def _on_quality_change(self, e: ft.Event) -> None:
        self.settings.quality = self.quality_dropdown.value or Quality.BEST.value
        self.settings.save()
        self._refresh_naming_example()
        self.page.update()

    def _on_concurrency_change(self, e: ft.Event) -> None:
        try:
            self.settings.concurrency = int(self.concurrency_dropdown.value or 3)
        except ValueError:
            self.settings.concurrency = 3
        self.settings.save()

    def _on_accel_change(self, e: ft.Event) -> None:
        self.settings.use_cpu = bool(self.cpu_checkbox.value)
        self.settings.use_gpu = bool(self.gpu_checkbox.value)
        # "Both" is simply CPU + GPU ticked together; neither ticked means plain FFmpeg.
        self.settings.save()
        self._refresh_accel_hint()
        self.page.update()

    def _refresh_accel_hint(self) -> None:
        if self.settings.use_cpu and self.settings.use_gpu:
            key = "perf.mode_both"
        elif self.settings.use_gpu:
            key = "perf.mode_gpu"
        elif self.settings.use_cpu:
            key = "perf.mode_cpu"
        else:
            key = "perf.mode_none"
        self.accel_hint.value = self.t(key)

    def _on_cookies_browser_change(self, e: ft.Event) -> None:
        self.settings.cookies_browser = self.cookies_dropdown.value or ""
        self.settings.save()

    def _on_import_cookies(self, e: ft.Event) -> None:
        browser = self.settings.cookies_browser
        if not browser:
            self.cookies_status.value = self.t("cookies.pick_first")
            self.cookies_status.color = self.palette.status_color(ItemStatus.PROCESSING.value)
            self.page.update()
            return
        self.cookies_status.value = self.t("cookies.checking")
        self.page.update()

        def worker() -> None:
            ok, message = verify_browser_cookies(browser)

            def apply() -> None:
                self.cookies_status.value = message
                self.cookies_status.color = self.palette.status_color(
                    ItemStatus.COMPLETED.value if ok else ItemStatus.ERROR.value
                )

            self._call_on_ui(apply)
            self._append_log(message)

        self.page.run_thread(worker)

    def _on_shutdown_toggle(self, e: ft.Event) -> None:
        self.settings.shutdown_when_done = bool(self.shutdown_checkbox.value)
        self.settings.save()
        if self.settings.shutdown_when_done:
            self._set_status(self.t("finish.shutdown_armed"))

    async def _on_pick_folder(self, e: ft.Event) -> None:
        path = await self.file_picker.get_directory_path(
            dialog_title=self.t("action.browse"),
            initial_directory=self.settings.download_dir,
        )
        if path:
            self.settings.download_dir = path
            self.settings.save()
            self.folder_field.value = path
            self.monitor.set_disk_path(self._safe_disk_path())
            self.page.update()

    def _clear_links(self) -> None:
        self.links_field.value = ""
        self.page.update()

    def _on_add_links(self, e: ft.Event) -> None:
        text = self.links_field.value or ""
        if not text.strip():
            self._set_status(self.t("msg.no_links"))
            self.page.update()
            return
        self.add_button.disabled = True
        self._set_status(self.t("msg.extracting"))
        self.page.update()

        def done(added: int, errors: list[str]) -> None:
            self.add_button.disabled = False
            if added:
                self.links_field.value = ""
            message = self.t("msg.added", count=added)
            if errors:
                message += "  " + self.t("msg.some_failed", count=len(errors))
            self._set_status(message)
            self._mark_rebuild()

        self.manager.add_links_async(text, on_done=done)

    def _on_start(self, e: ft.Event) -> None:
        started = self.manager.start()
        self._shutdown_cancelled = False
        self._set_status(self.t("msg.started", count=started) if started
                         else self.t("msg.nothing_to_start"))
        self.page.update()

    def _on_pause(self, e: ft.Event) -> None:
        self.manager.pause()
        self._set_status(self.t("msg.paused"))
        self.page.update()

    def _on_retry_failed(self, e: ft.Event) -> None:
        count = self.manager.retry_failed()
        self._set_status(self.t("msg.retry_queued", count=count))
        self.page.update()

    def _on_clear_finished(self, e: ft.Event) -> None:
        self.manager.clear_finished()
        self._set_status(self.t("msg.cleared_finished"))

    def _on_clear_all(self, e: ft.Event) -> None:
        self._confirm(
            title_key="dialog.clear_all_title",
            body_key="dialog.clear_all_body",
            on_yes=lambda: (self.manager.clear_all(), self._set_status(self.t("msg.cleared_all"))),
        )

    def _on_filter_change(self, e: ft.Event) -> None:
        self._filter_profile = self.profile_filter.value or "*"
        self._mark_rebuild()

    def _on_search_change(self, e: ft.Event) -> None:
        self._search = (self.search_field.value or "").strip()
        self._mark_rebuild()

    def _on_group_toggle(self, e: ft.Event) -> None:
        self.settings.group_by_profile = bool(self.group_switch.value)
        self.settings.save()
        self._mark_rebuild()

    def _on_row_action(self, action: str, item: QueueItem) -> None:
        if action == "open":
            target = item.filepath or self.settings.download_dir
            open_folder(str(Path(target).parent if item.filepath else target))
        elif action == "remove":
            self.manager.remove([item.uid])
        elif action == "retry":
            item.set_status(ItemStatus.QUEUED)
            item.error = ""
            item.progress = 0.0
            self.store.upsert(item)
            self._mark_dirty(item)

    def _on_page_close(self, e: ft.Event | None = None) -> None:
        """Persist and release resources when the window goes away."""
        try:
            self.monitor.stop()
            self.manager.shutdown()
            self.settings.save()
            self.store.close()
        except Exception:  # noqa: BLE001 - shutdown must never raise
            pass

    # =====================================================================================
    # Logging & status
    # =====================================================================================
    def _append_log(self, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self._log_lines.append(f"[{stamp}] {message}")
        del self._log_lines[:-MAX_LOG_LINES]
        self._log_dirty = True

    def _set_status(self, message: str) -> None:
        """Queue a status-bar message.

        Safe to call from a worker thread: it only stores the string, and the UI
        tick paints it on the next pass.
        """
        self._status_message = message

    # =====================================================================================
    # Dialogs
    # =====================================================================================
    def _dialog(self, title: str, body: ft.Control, actions: list[ft.Control],
                modal: bool = True) -> ft.AlertDialog:
        return ft.AlertDialog(
            modal=modal,
            title=ft.Text(title, size=17, weight=ft.FontWeight.BOLD, color=self.palette.text),
            content=body,
            actions=actions,
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=self.palette.surface,
        )

    def _confirm(self, title_key: str, body_key: str, on_yes) -> None:
        def yes(e: ft.Event) -> None:
            self.page.pop_dialog()
            on_yes()
            self.page.update()

        dialog = self._dialog(
            self.t(title_key),
            ft.Text(self.t(body_key), color=self.palette.text),
            [
                ft.TextButton(self.t("action.cancel"), on_click=lambda e: self.page.pop_dialog()),
                ft.FilledButton(self.t("action.confirm"), on_click=yes),
            ],
        )
        self.page.show_dialog(dialog)

    # -- first-launch legal disclaimer ---------------------------------------------------
    def show_disclaimer(self) -> None:
        body = ft.Container(
            content=ft.Column(
                [
                    ft.Text(self.t("dialog.disclaimer_body"), color=self.palette.text, size=13,
                            weight=ft.FontWeight.W_600),
                    ft.Text(self.t("dialog.disclaimer_points"), color=self.palette.text_dim,
                            size=12),
                ],
                spacing=10,
                tight=True,
            ),
            width=520,
            height=190,
        )

        def accept(e: ft.Event) -> None:
            self.settings.disclaimer_accepted = True
            self.settings.save()
            self.page.pop_dialog()
            self._offer_resume()
            self.page.update()

        def decline(e: ft.Event) -> None:
            self.page.pop_dialog()
            self.page.window.close()

        dialog = self._dialog(
            self.t("dialog.disclaimer_title"),
            body,
            [
                ft.TextButton(self.t("action.decline"), on_click=decline),
                ft.FilledButton(self.t("action.accept"), on_click=accept),
            ],
        )
        self.page.show_dialog(dialog)

    # -- Smart Resume prompt -------------------------------------------------------------
    def _restore_previous_session(self) -> None:
        if not self.settings.disclaimer_accepted:
            self.show_disclaimer()
            return
        self._offer_resume()

    def _offer_resume(self) -> None:
        """Ask whether to continue a queue left over from an earlier run."""
        pending = self.store.pending_items()
        if not pending:
            # Nothing unfinished, but finished rows are still shown for reference.
            self.manager.load_from_store(self.store.load_all(), reset_active=False)
            return

        def resume(e: ft.Event) -> None:
            self.page.pop_dialog()
            self.manager.load_from_store(self.store.load_all())
            self._set_status(self.t("msg.resumed", count=len(pending)))
            self.page.update()

        def discard(e: ft.Event) -> None:
            self.page.pop_dialog()
            self.manager.clear_all()
            self._set_status(self.t("msg.session_discarded"))
            self.page.update()

        profiles = len({item.profile for item in pending})
        dialog = self._dialog(
            self.t("dialog.resume_title"),
            ft.Column(
                [
                    ft.Text(self.t("dialog.resume_body", count=len(pending), profiles=profiles),
                            color=self.palette.text, size=13),
                    ft.Text(self.t("dialog.resume_hint"), color=self.palette.text_dim, size=12),
                ],
                spacing=8,
                tight=True,
            ),
            [
                ft.TextButton(self.t("action.resume_no"), on_click=discard),
                ft.FilledButton(self.t("action.resume_yes"), on_click=resume),
            ],
        )
        self.page.show_dialog(dialog)

    # -- batch finished / shutdown --------------------------------------------------------
    def _on_batch_finished(self, stats: dict) -> None:
        """Worker-thread callback — hop onto the UI loop before touching controls."""
        self._append_log(
            f"Batch finished: {stats['done']} done, {stats['failed']} failed, "
            f"{stats['queued']} left."
        )
        self._set_status(self.t("msg.batch_done", done=stats["done"], failed=stats["failed"]))
        if self.settings.shutdown_when_done and stats["done"] > 0:
            self._call_on_ui(self._start_shutdown_countdown)

    def _call_on_ui(self, func) -> None:
        """Run ``func`` on the Flet event loop from any thread."""
        loop = getattr(self.page, "loop", None)
        if loop is not None:
            try:
                loop.call_soon_threadsafe(func)
                return
            except RuntimeError:
                pass
        func()

    def _start_shutdown_countdown(self) -> None:
        """Cancelable warning before powering the machine off."""
        self._shutdown_cancelled = False
        remaining = ft.Text(size=42, weight=ft.FontWeight.BOLD,
                            color=self.palette.status_color(ItemStatus.ERROR.value),
                            font_family="monospace")
        message = ft.Text(self.t("dialog.shutdown_body"), color=self.palette.text, size=13)

        def cancel(e: ft.Event) -> None:
            self._shutdown_cancelled = True
            self.page.pop_dialog()
            self._set_status(self.t("msg.shutdown_cancelled"))
            self.page.update()

        dialog = self._dialog(
            self.t("dialog.shutdown_title"),
            ft.Column([message, remaining], spacing=10, tight=True,
                      horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            [ft.FilledButton(self.t("action.cancel_shutdown"), on_click=cancel)],
        )
        self._shutdown_dialog = dialog
        self.page.show_dialog(dialog)

        async def countdown() -> None:
            for left in range(SHUTDOWN_GRACE_SECONDS, 0, -1):
                if self._shutdown_cancelled:
                    return
                remaining.value = f"{left}s"
                self.page.update()
                await asyncio.sleep(1)
            if self._shutdown_cancelled:
                return
            self.page.pop_dialog()
            ok, msg = shutdown_pc()
            self._append_log(msg)
            self._set_status(msg)
            self.page.update()

        self.page.run_task(countdown)


# =========================================================================================
# Entry point
# =========================================================================================
def main(page: ft.Page) -> None:
    TKApp(page)


def run() -> None:
    """Launch the desktop window (``python main.py``)."""
    ft.run(main, assets_dir=str(ASSETS_DIR))


__all__ = ["TKApp", "main", "run", "app_data_dir"]
