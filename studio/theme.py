# -*- coding: utf-8 -*-
"""Dark theme tokens + stylesheet for the Pulse Rail master UI."""

BG          = "#0b0e14"
BG_ELEV     = "#121722"
BG_CARD     = "#161c28"
BORDER      = "#232b3b"
BORDER_SOFT = "#1b2230"

TEXT        = "#e8edf7"
TEXT_DIM    = "#8894ad"
TEXT_FAINT  = "#5b667e"

ACCENT      = "#22d3ee"
ACCENT_DIM  = "#0e7490"
ACCENT_2    = "#a855f7"
DANGER      = "#ef4444"
OK          = "#22c55e"
WARN        = "#f59e0b"

TITLEBAR_H  = 40
SIDEBAR_W   = 208
RADIUS      = 12


def stylesheet() -> str:
    return f"""
* {{
    font-family: "Inter", "Segoe UI", "Noto Sans Khmer", "Noto Sans Thai", sans-serif;
    font-size: 13px;
    color: {TEXT};
    outline: none;
}}

#Root {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: {RADIUS}px;
}}
#Root[maximized="true"] {{ border-radius: 0px; }}

/* ---------- custom title bar (there is no native one) ---------- */
#TitleBar {{
    background: {BG_ELEV};
    border-top-left-radius: {RADIUS}px;
    border-top-right-radius: {RADIUS}px;
    border-bottom: 1px solid {BORDER_SOFT};
}}
#TitleBar[maximized="true"] {{ border-top-left-radius: 0; border-top-right-radius: 0; }}
#AppMark {{ color: {ACCENT}; font-size: 15px; font-weight: 700; }}
#AppTitle {{ color: {TEXT}; font-size: 13px; font-weight: 600; }}
#AppSub   {{ color: {TEXT_FAINT}; font-size: 11px; }}

QPushButton#WinBtn {{
    background: transparent; border: none;
    min-width: 46px; max-width: 46px;
    min-height: {TITLEBAR_H}px; max-height: {TITLEBAR_H}px;
    color: {TEXT_DIM}; font-size: 14px;
}}
QPushButton#WinBtn:hover {{ background: {BG_CARD}; color: {TEXT}; }}
QPushButton#WinBtnClose:hover {{ background: {DANGER}; color: #fff; }}

/* ---------- sidebar ---------- */
#Sidebar {{
    background: {BG_ELEV};
    border-right: 1px solid {BORDER_SOFT};
    border-bottom-left-radius: {RADIUS}px;
}}
#Sidebar[maximized="true"] {{ border-bottom-left-radius: 0; }}

QPushButton#NavBtn {{
    background: transparent; border: none;
    border-left: 3px solid transparent;
    padding: 11px 14px; text-align: left;
    color: {TEXT_DIM}; font-size: 13px;
}}
QPushButton#NavBtn:hover  {{ background: {BG_CARD}; color: {TEXT}; }}
QPushButton#NavBtn:checked {{
    background: {BG_CARD}; color: {TEXT};
    border-left: 3px solid {ACCENT}; font-weight: 600;
}}
#NavHeader {{ color: {TEXT_FAINT}; font-size: 10px; font-weight: 700;
              padding: 14px 16px 6px 16px; letter-spacing: 1px; }}

/* ---------- cards / panels ---------- */
#Card {{
    background: {BG_CARD};
    border: 1px solid {BORDER_SOFT};
    border-radius: 10px;
}}
#CardTitle {{ color: {TEXT}; font-size: 13px; font-weight: 600; }}
#Hint {{ color: {TEXT_FAINT}; font-size: 11px; }}

#PreviewFrame {{
    background: #05070b;
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

#DropZone {{
    background: {BG_CARD};
    border: 1px dashed {BORDER};
    border-radius: 10px;
    color: {TEXT_DIM};
}}
#DropZone[hot="true"] {{ border: 1px dashed {ACCENT}; background: #10202a; }}

/* ---------- controls ---------- */
QPushButton {{
    background: {BG_CARD}; border: 1px solid {BORDER};
    border-radius: 8px; padding: 8px 14px; color: {TEXT};
}}
QPushButton:hover    {{ border-color: {ACCENT_DIM}; }}
QPushButton:disabled {{ color: {TEXT_FAINT}; border-color: {BORDER_SOFT}; }}

QPushButton#Primary {{
    background: {ACCENT}; border: none; color: #04222a;
    font-weight: 700; padding: 10px 18px; border-radius: 8px;
}}
QPushButton#Primary:hover    {{ background: #67e8f9; }}
QPushButton#Primary:disabled {{ background: {BORDER}; color: {TEXT_FAINT}; }}

QComboBox {{
    background: {BG_CARD}; border: 1px solid {BORDER};
    border-radius: 8px; padding: 7px 10px; min-height: 18px;
}}
QComboBox:hover {{ border-color: {ACCENT_DIM}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {BG_CARD}; border: 1px solid {BORDER};
    selection-background-color: {ACCENT_DIM}; padding: 4px;
}}

QLineEdit, QPlainTextEdit {{
    background: {BG}; border: 1px solid {BORDER};
    border-radius: 8px; padding: 7px 10px;
    selection-background-color: {ACCENT_DIM};
}}
QLineEdit:focus, QPlainTextEdit:focus {{ border-color: {ACCENT}; }}

QSlider::groove:horizontal {{ height: 4px; background: {BORDER}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {TEXT}; width: 13px; height: 13px;
    margin: -5px 0; border-radius: 6px;
}}

QProgressBar {{
    background: {BG}; border: 1px solid {BORDER};
    border-radius: 6px; height: 8px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 5px; }}

/* The viewport and the page widget inside it both default to the palette
   base colour (white). Without these two rules the settings pane shows a
   white block wherever the page is shorter than the scroll area. */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollArea > QWidget > QScrollBar {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 26px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT_DIM}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

#StatusBar {{
    background: {BG_ELEV};
    border-top: 1px solid {BORDER_SOFT};
    border-bottom-left-radius: {RADIUS}px;
    border-bottom-right-radius: {RADIUS}px;
}}
#StatusBar[maximized="true"] {{ border-bottom-left-radius: 0; border-bottom-right-radius: 0; }}
#StatusText {{ color: {TEXT_DIM}; font-size: 11px; }}
#Badge {{
    background: {BG_CARD}; border: 1px solid {BORDER};
    border-radius: 9px; padding: 2px 9px; color: {TEXT_DIM}; font-size: 10px;
}}
"""
