"""High-contrast light and dark themes.

Both palettes are hand-picked rather than seed-generated so that text keeps a
strong contrast ratio against its background in either mode — the app is often
used on a bright desk or late at night, and the queue table is dense.
"""

from __future__ import annotations

import flet as ft

from ..models import ItemStatus

# Brand accent: a saturated cyan/teal that stays legible on white and on near-black.
ACCENT_DARK = "#22D3EE"
ACCENT_LIGHT = "#0369A1"

# Surfaces
DARK_BG = "#0B0F14"
DARK_SURFACE = "#141B23"
DARK_SURFACE_HI = "#1D2733"
DARK_BORDER = "#2B3947"
DARK_TEXT = "#F2F6FA"
DARK_TEXT_DIM = "#9FB0C0"

LIGHT_BG = "#F4F7FA"
LIGHT_SURFACE = "#FFFFFF"
LIGHT_SURFACE_HI = "#E8EEF5"
LIGHT_BORDER = "#C3D0DD"
LIGHT_TEXT = "#0C1116"
LIGHT_TEXT_DIM = "#4A5A6A"

# Status colors (identical hues in both modes, tuned for contrast).
STATUS_COLORS: dict[str, str] = {
    ItemStatus.QUEUED.value: "#8AA0B4",
    ItemStatus.EXTRACTING.value: "#A78BFA",
    ItemStatus.DOWNLOADING.value: "#38BDF8",
    ItemStatus.PROCESSING.value: "#FBBF24",
    ItemStatus.COMPLETED.value: "#22C55E",
    ItemStatus.SKIPPED.value: "#14B8A6",
    ItemStatus.ERROR.value: "#F43F5E",
    ItemStatus.PAUSED.value: "#F59E0B",
    ItemStatus.CANCELLED.value: "#94A3B8",
}

STATUS_ICONS: dict[str, str] = {
    ItemStatus.QUEUED.value: ft.Icons.SCHEDULE,
    ItemStatus.EXTRACTING.value: ft.Icons.TRAVEL_EXPLORE,
    ItemStatus.DOWNLOADING.value: ft.Icons.DOWNLOADING,
    ItemStatus.PROCESSING.value: ft.Icons.SETTINGS_SUGGEST,
    ItemStatus.COMPLETED.value: ft.Icons.CHECK_CIRCLE,
    ItemStatus.SKIPPED.value: ft.Icons.FAST_FORWARD,
    ItemStatus.ERROR.value: ft.Icons.ERROR,
    ItemStatus.PAUSED.value: ft.Icons.PAUSE_CIRCLE,
    ItemStatus.CANCELLED.value: ft.Icons.CANCEL,
}


class Palette:
    """Flat color bundle the widgets read instead of branching on theme mode."""

    def __init__(self, dark: bool) -> None:
        self.dark = dark
        self.accent = ACCENT_DARK if dark else ACCENT_LIGHT
        self.bg = DARK_BG if dark else LIGHT_BG
        self.surface = DARK_SURFACE if dark else LIGHT_SURFACE
        self.surface_hi = DARK_SURFACE_HI if dark else LIGHT_SURFACE_HI
        self.border = DARK_BORDER if dark else LIGHT_BORDER
        self.text = DARK_TEXT if dark else LIGHT_TEXT
        self.text_dim = DARK_TEXT_DIM if dark else LIGHT_TEXT_DIM

    def status_color(self, status: str) -> str:
        return STATUS_COLORS.get(status, self.text_dim)


def build_theme(dark: bool, font_family: str | None = None) -> ft.Theme:
    palette = Palette(dark)
    scheme = ft.ColorScheme(
        primary=palette.accent,
        on_primary="#04121A" if dark else "#FFFFFF",
        secondary=palette.accent,
        surface=palette.surface,
        on_surface=palette.text,
        on_surface_variant=palette.text_dim,
        error=STATUS_COLORS[ItemStatus.ERROR.value],
        outline=palette.border,
        outline_variant=palette.border,
        surface_tint=palette.accent,
    )
    # Rounded, flat-elevation buttons everywhere instead of Material's default
    # sharp corners + drop shadow — a big part of the "modern" look on its own.
    pill_shape = ft.RoundedRectangleBorder(radius=10)
    pill_style = ft.ButtonStyle(shape=pill_shape, elevation=0,
                                padding=ft.Padding.symmetric(horizontal=18, vertical=12))
    return ft.Theme(
        color_scheme=scheme,
        font_family=font_family,
        visual_density=ft.VisualDensity.COMPACT,
        scaffold_bgcolor=palette.bg,
        filled_button_theme=ft.FilledButtonTheme(style=pill_style),
        outlined_button_theme=ft.OutlinedButtonTheme(style=pill_style),
        text_button_theme=ft.TextButtonTheme(
            style=ft.ButtonStyle(shape=pill_shape, elevation=0)
        ),
    )
