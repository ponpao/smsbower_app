"""Light green theme for the TRAVKOD PyQt6 UI.

White/mint surfaces with a green accent (matching the reference). The QSS is a
function of the font family so the language switch can swap in Kantumruy Pro for
Khmer. Constant names are kept stable so widgets importing colors keep working.
"""
from __future__ import annotations

# Palette (light green)
BG = "#f4f8f5"          # window background
PANEL = "#ffffff"        # main panels
PANEL_2 = "#eef4f0"      # inputs / secondary surfaces
CARD = "#ffffff"         # cards
HEADER_BG = "#e3f3ea"    # table header / mint
ROW_ALT = "#f3fbf6"      # alternating row tint
BORDER = "#cfe6d9"       # visible borders
BORDER_SOFT = "#e2efe8"  # soft dividers
ACCENT = "#16a34a"       # primary green
ACCENT_SOFT = "#22c55e"  # bright green
ACCENT_DIM = "#dcfce7"   # selection / hover fill (light)
TEXT = "#20302a"         # primary text (dark)
TEXT_MUTED = "#5c6b63"   # muted labels
TEXT_DIM = "#93a49a"     # dim / inactive
GOOD = "#16a34a"
WARN = "#d97706"
BAD = "#dc2626"

EN_FONT = "'Inter','Segoe UI','Noto Sans',sans-serif"


def build_qss(font_family: str = EN_FONT) -> str:
    return f"""
* {{
    font-family: {font_family};
    font-size: 12px;
    color: {TEXT};
    outline: none;
}}
QWidget#root {{ background: {BG}; }}
QMainWindow {{ background: {BG}; }}

QLabel {{ background: transparent; }}
QLabel[muted="true"] {{ color: {TEXT_MUTED}; }}
QLabel[dim="true"] {{ color: {TEXT_DIM}; font-size: 10px; }}
QLabel[accent="true"] {{ color: {ACCENT}; }}

QFrame[panel="true"] {{
    background: {PANEL};
    border: 1px solid {BORDER_SOFT};
    border-radius: 10px;
}}
QFrame[card="true"] {{
    background: {CARD};
    border: 1px solid {BORDER_SOFT};
    border-radius: 8px;
}}

/* Buttons */
QPushButton {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 10px;
    color: {TEXT};
}}
QPushButton:hover {{ background: {ACCENT_DIM}; border-color: {ACCENT_SOFT}; }}
QPushButton:pressed {{ background: {ACCENT_DIM}; }}
QPushButton:disabled {{ color: {TEXT_DIM}; background: {PANEL_2}; border-color: {BORDER_SOFT}; }}
QPushButton[accent="true"] {{
    background: {ACCENT};
    border: none;
    color: white;
    font-weight: 600;
}}
QPushButton[accent="true"]:hover {{ background: {ACCENT_SOFT}; }}
QPushButton[danger="true"] {{ background: {BAD}; border: none; color: white; font-weight: 600; }}
QPushButton[danger="true"]:hover {{ background: #ef4444; }}
QPushButton:checked {{ background: {ACCENT_DIM}; border-color: {ACCENT}; color: {ACCENT}; }}

/* Inputs */
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 3px 8px;
    min-height: 18px;
    color: {TEXT};
}}
QComboBox:hover {{ border-color: {ACCENT_SOFT}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {PANEL};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_DIM};
    selection-color: {TEXT};
    outline: none;
}}

/* Tables */
QTableWidget {{
    background: {CARD};
    border: 1px solid {BORDER_SOFT};
    border-radius: 8px;
    gridline-color: transparent;
    selection-background-color: {ACCENT_DIM};
    alternate-background-color: {ROW_ALT};
}}
QTableWidget::item {{ padding: 4px 6px; border: none; }}
QTableWidget::item:selected {{ background: {ACCENT_DIM}; color: {TEXT}; }}
QHeaderView::section {{
    background: {HEADER_BG};
    color: {TEXT_MUTED};
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid {BORDER};
    font-size: 10px;
    font-weight: 600;
}}
QTableCornerButton::section {{ background: {HEADER_BG}; border: none; }}

/* Scrollbars */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {ACCENT_SOFT}; border-radius: 5px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {ACCENT_SOFT}; border-radius: 5px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* Vertical mastering-strip sliders */
QSlider::groove:vertical {{ background: {BORDER}; width: 4px; border-radius: 2px; }}
QSlider::handle:vertical {{
    background: {ACCENT}; height: 12px; margin: 0 -6px; border-radius: 3px;
}}
QSlider::handle:vertical:hover {{ background: {ACCENT_SOFT}; }}
QSlider::sub-page:vertical {{ background: {BORDER}; border-radius: 2px; }}
QSlider::add-page:vertical {{ background: #bfe8cd; border-radius: 2px; }}
QSlider:disabled::handle:vertical {{ background: {TEXT_DIM}; }}

/* Horizontal sliders */
QSlider::groove:horizontal {{ background: {BORDER}; height: 4px; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {ACCENT}; width: 12px; margin: -5px 0; border-radius: 3px;
}}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}

QProgressBar {{
    background: {BORDER}; border: none; border-radius: 3px; height: 6px; text-align: center;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}

QToolTip {{
    background: {PANEL}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px 6px;
}}
QMenu {{ background: {PANEL}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 5px 20px; border-radius: 4px; color: {TEXT}; }}
QMenu::item:selected {{ background: {ACCENT_DIM}; }}
QMenu::item:disabled {{ color: {TEXT_DIM}; }}
QMenu::separator {{ height: 1px; background: {BORDER_SOFT}; margin: 4px 6px; }}

QDialog {{ background: {BG}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {BORDER}; background: {PANEL}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
"""


QSS = build_qss()
