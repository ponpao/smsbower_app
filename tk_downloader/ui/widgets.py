"""Reusable pieces of the TK Downloader interface."""

from __future__ import annotations

from typing import Callable

import flet as ft

from ..i18n import Translator
from ..models import ItemStatus, QueueItem
from ..utils import human_bytes, human_eta, human_speed, truncate
from .theme import Palette, STATUS_ICONS

# Column widths shared by the header and every data row so they line up exactly.
# Title is the only flexible column; everything else is fixed.
COL_CHECK = 34
COL_INDEX = 44
COL_PROFILE = 128
COL_ID = 118
COL_STATUS = 112
COL_PROGRESS = 140
COL_SPEED = 84
COL_ETA = 66
COL_ACTIONS = 120
COL_SPACING = 6

# Narrowest width at which the title column still has room. Below this the table
# scrolls sideways instead of squeezing the title down to nothing.
TABLE_MIN_WIDTH = (
    COL_CHECK + COL_INDEX + COL_PROFILE + COL_ID + COL_STATUS + COL_PROGRESS
    + COL_SPEED + COL_ETA + COL_ACTIONS + (COL_SPACING * 9) + 24 + 150
)


def section_title(text_control: ft.Text, palette: Palette, icon: str | None = None) -> ft.Control:
    """Small uppercase heading used above each settings block."""
    text_control.size = 12
    text_control.weight = ft.FontWeight.W_700
    text_control.color = palette.text_dim
    row = [text_control]
    if icon:
        row.insert(0, ft.Icon(icon, size=15, color=palette.text_dim))
    return ft.Row(row, spacing=6)


def card(content: ft.Control, palette: Palette, padding: int = 14) -> ft.Container:
    return ft.Container(
        content=content,
        padding=padding,
        bgcolor=palette.surface,
        border=ft.Border.all(1, palette.border),
        border_radius=14,
        shadow=ft.BoxShadow(
            blur_radius=18, spread_radius=-4,
            color=ft.Colors.with_opacity(0.28 if palette.dark else 0.10, "#000000"),
            offset=ft.Offset(0, 6),
        ),
    )


def stat_chip(icon: str, value_text: ft.Text, label_text: ft.Text, palette: Palette,
              color: str | None = None) -> ft.Container:
    """One of the Total / Done / Active / Failed counters above the queue."""
    value_text.size = 18
    value_text.weight = ft.FontWeight.BOLD
    value_text.color = color or palette.text
    label_text.size = 11
    label_text.color = palette.text_dim
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(icon, size=18, color=color or palette.text_dim),
                ft.Column([value_text, label_text], spacing=0, tight=True),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        bgcolor=palette.surface_hi,
        border_radius=10,
        border=ft.Border.all(1, palette.border),
    )


def queue_header(
    translator: Translator,
    palette: Palette,
    sort_key: str,
    sort_desc: bool,
    on_sort: Callable[[str], None],
    select_state: bool | None,
    on_select_all: Callable[[bool], None],
) -> ft.Container:
    """Sticky header row: a select-all checkbox plus clickable, sortable columns.

    ``select_state`` is ``True``/``False`` when every visible row is (un)selected
    and ``None`` for a mixed selection, which renders as Flet's tristate dash.

    Unlike most of the UI, labels here are *not* registered with
    ``translator.bind`` — the whole header is rebuilt (by the caller) on every
    sort click, selection change and language switch anyway, so a persistent
    binding would just accumulate orphaned entries in the translator's list
    every time the user re-sorts.
    """

    def plain(key: str, width: int | None = None, expand: bool = False) -> ft.Text:
        return ft.Text(translator.t(key), size=11, weight=ft.FontWeight.W_700,
                       color=palette.text_dim, width=width, expand=expand, no_wrap=True)

    def sortable(key: str, label_key: str, width: int | None, expand: bool = False) -> ft.Control:
        label = ft.Text(translator.t(label_key), size=11, weight=ft.FontWeight.W_700, no_wrap=True)
        arrow = ft.Icon(
            ft.Icons.ARROW_DOWNWARD if sort_desc else ft.Icons.ARROW_UPWARD,
            size=12, color=palette.accent,
            visible=(sort_key == key),
        )
        active = sort_key == key
        label.color = palette.accent if active else palette.text_dim
        return ft.Container(
            content=ft.Row([label, arrow], spacing=2, tight=True,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
            width=width,
            expand=expand,
            on_click=lambda e: on_sort(key),
            ink=True,
            border_radius=6,
            padding=ft.Padding.symmetric(horizontal=2, vertical=2),
        )

    select_checkbox = ft.Checkbox(
        value=select_state, tristate=True, fill_color=palette.accent,
        tooltip=translator.t("table.select_all"),
        on_change=lambda e: on_select_all(bool(e.control.value)),
    )

    return ft.Container(
        content=ft.Row(
            [
                ft.Container(select_checkbox, width=COL_CHECK),
                sortable("no", "table.num", COL_INDEX),
                sortable("profile", "table.profile", COL_PROFILE),
                sortable("title", "table.title", None, expand=True),
                plain("table.video_id", COL_ID),
                sortable("status", "table.status", COL_STATUS),
                plain("table.progress", COL_PROGRESS),
                sortable("speed", "table.speed", COL_SPEED),
                sortable("eta", "table.eta", COL_ETA),
                plain("table.actions", COL_ACTIONS),
            ],
            spacing=COL_SPACING,
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        bgcolor=palette.surface_hi,
        border_radius=ft.BorderRadius.only(top_left=10, top_right=10),
    )


class QueueRow:
    """A single row of the queue table.

    The row owns its Flet controls and exposes :meth:`sync`, which copies the
    current :class:`QueueItem` values onto them. The UI ticker calls ``sync`` only
    for rows that actually changed, so a hundred-item queue stays smooth.
    """

    def __init__(
        self,
        item: QueueItem,
        translator: Translator,
        palette: Palette,
        on_action: Callable[[str, QueueItem], None],
        selected: bool = False,
    ) -> None:
        self.item = item
        self.t = translator
        self.palette = palette
        self.on_action = on_action

        dim = palette.text_dim
        self.select_checkbox = ft.Checkbox(
            value=selected, fill_color=palette.accent,
            on_change=lambda e: self.on_action("select" if e.control.value else "deselect", self.item),
        )
        self.index_text = ft.Text(size=12, color=dim, width=COL_INDEX, no_wrap=True)
        self.profile_text = ft.Text(size=12, color=palette.accent, width=COL_PROFILE,
                                    no_wrap=True, weight=ft.FontWeight.W_600)
        self.title_text = ft.Text(size=13, color=palette.text, expand=True, no_wrap=True)
        self.id_text = ft.Text(size=12, color=dim, width=COL_ID, no_wrap=True,
                               font_family="monospace")
        self.status_icon = ft.Icon(ft.Icons.SCHEDULE, size=15, color=dim)
        self.status_text = ft.Text(size=12, color=dim, no_wrap=True, expand=True)
        self.progress_bar = ft.ProgressBar(value=0, width=COL_PROGRESS - 44, bar_height=7,
                                           border_radius=6, bgcolor=palette.surface_hi,
                                           color=palette.accent)
        self.progress_text = ft.Text("0%", size=11, color=dim, width=36, no_wrap=True,
                                     text_align=ft.TextAlign.RIGHT)
        self.speed_text = ft.Text("-", size=12, color=dim, width=COL_SPEED, no_wrap=True)
        self.eta_text = ft.Text("-", size=12, color=dim, width=COL_ETA, no_wrap=True)

        self.play_button = ft.IconButton(
            ft.Icons.PLAY_CIRCLE, icon_size=17, icon_color=palette.accent,
            on_click=lambda e: self.on_action("play", self.item),
        )
        self.open_button = ft.IconButton(
            ft.Icons.FOLDER_OPEN, icon_size=16, icon_color=dim,
            on_click=lambda e: self.on_action("open", self.item),
        )
        self.retry_button = ft.IconButton(
            ft.Icons.REFRESH, icon_size=16, icon_color=dim,
            on_click=lambda e: self.on_action("retry", self.item),
        )
        self.remove_button = ft.IconButton(
            ft.Icons.CLOSE, icon_size=16, icon_color=dim,
            on_click=lambda e: self.on_action("remove", self.item),
        )
        self.t.bind(self.play_button, "tooltip", "action.play")
        self.t.bind(self.open_button, "tooltip", "action.open_file")
        self.t.bind(self.retry_button, "tooltip", "action.retry_one")
        self.t.bind(self.remove_button, "tooltip", "action.remove")

        self.control = ft.Container(
            content=ft.Row(
                [
                    ft.Container(self.select_checkbox, width=COL_CHECK),
                    self.index_text,
                    self.profile_text,
                    self.title_text,
                    self.id_text,
                    ft.Row([self.status_icon, self.status_text], spacing=5,
                           width=COL_STATUS, tight=True),
                    ft.Row([self.progress_bar, self.progress_text], spacing=6,
                           width=COL_PROGRESS, tight=True,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    self.speed_text,
                    self.eta_text,
                    ft.Row([self.play_button, self.open_button, self.retry_button,
                            self.remove_button],
                           spacing=0, width=COL_ACTIONS, tight=True),
                ],
                spacing=COL_SPACING,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=12, vertical=2),
            border=ft.Border(bottom=ft.BorderSide(1, self.palette.border)),
        )
        self.sync()

    # -----------------------------------------------------------------------------
    def sync(self, selected: bool | None = None) -> None:
        """Refresh every control from the underlying item.

        ``selected`` is only passed when the selection state actually changed
        (row checkbox, select-all); omitting it leaves the checkbox as-is so a
        routine progress-driven ``sync()`` doesn't fight the user's click.
        """
        item = self.item
        status = item.status_enum
        color = self.palette.status_color(item.status)

        if selected is not None:
            self.select_checkbox.value = selected
            self.control.bgcolor = (
                ft.Colors.with_opacity(0.10, self.palette.accent) if selected else None
            )

        # "No" = the item's rank within its own profile, so a freshly-added
        # profile always starts counting from 1 instead of continuing the
        # global queue position.
        self.index_text.value = str(item.profile_position or item.position)
        self.profile_text.value = truncate(item.profile or "-", 20)
        self.profile_text.tooltip = item.profile
        self.title_text.value = truncate(item.title, 90)
        self.title_text.tooltip = item.error or item.title
        self.id_text.value = item.video_id or "-"

        self.status_icon.name = STATUS_ICONS.get(item.status, ft.Icons.SCHEDULE)
        self.status_icon.color = color
        self.status_text.value = self.t(f"status.{item.status}")
        self.status_text.color = color

        self.progress_bar.value = max(0.0, min(1.0, item.progress))
        self.progress_bar.color = color
        self.progress_text.value = f"{item.progress * 100:.0f}%"

        if status is ItemStatus.DOWNLOADING:
            self.speed_text.value = human_speed(item.speed)
            self.eta_text.value = human_eta(item.eta if item.eta >= 0 else None)
        elif status.is_finished:
            self.speed_text.value = human_bytes(item.total_bytes) if item.total_bytes else "-"
            self.eta_text.value = "-"
        else:
            self.speed_text.value = "-"
            self.eta_text.value = "-"

        self.retry_button.visible = status in (ItemStatus.ERROR, ItemStatus.CANCELLED,
                                               ItemStatus.PAUSED)
        self.open_button.visible = bool(item.filepath)
        self.play_button.visible = bool(item.filepath) and status.is_finished


def group_header(profile: str, count: int, palette: Palette) -> ft.Container:
    """Separator row shown when "group by profile" is switched on."""
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.ACCOUNT_CIRCLE, size=16, color=palette.accent),
                ft.Text(profile, size=13, weight=ft.FontWeight.BOLD, color=palette.accent),
                ft.Container(
                    content=ft.Text(str(count), size=11, color=palette.text),
                    padding=ft.Padding.symmetric(horizontal=8, vertical=1),
                    bgcolor=palette.surface_hi,
                    border_radius=8,
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        bgcolor=palette.surface_hi,
    )
