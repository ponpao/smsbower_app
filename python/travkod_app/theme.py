"""Dark theme for the TRAVKOD PyQt6 UI.

Slate background (#0d1420), blue accent (#3b82f6), muted labels — matching the
reference app. Exposed as a single QSS string plus a few color constants for
widgets that paint themselves.
"""
from __future__ import annotations

# Palette
BG = "#0d1420"
PANEL = "#111a2b"
PANEL_2 = "#152036"
CARD = "#0f1826"
BORDER = "#26324f"
BORDER_SOFT = "#1b2740"
ACCENT = "#3b82f6"
ACCENT_SOFT = "#60a5fa"
ACCENT_DIM = "#1e3a8a"
TEXT = "#cbd5e1"
TEXT_MUTED = "#64748b"
TEXT_DIM = "#475569"
GOOD = "#4ade80"
WARN = "#fbbf24"
BAD = "#f87171"

QSS = f"""
* {{
    font-family: 'Inter', 'Segoe UI', 'Noto Sans', sans-serif;
    font-size: 12px;
    color: {TEXT};
    outline: none;
}}
QWidget#root {{ background: {BG}; }}
QMainWindow {{ background: {BG}; }}

QLabel {{ background: transparent; }}
QLabel[muted="true"] {{ color: {TEXT_MUTED}; }}
QLabel[dim="true"] {{ color: {TEXT_DIM}; font-size: 10px; }}
QLabel[accent="true"] {{ color: {ACCENT_SOFT}; }}
QLabel[heading="true"] {{
    color: {TEXT_MUTED};
    font-size: 10px;
    letter-spacing: 2px;
}}

/* Panels */
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
    background: {PANEL_2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 10px;
    color: {TEXT};
}}
QPushButton:hover {{ background: {BORDER}; }}
QPushButton:pressed {{ background: {ACCENT_DIM}; }}
QPushButton:disabled {{ color: {TEXT_DIM}; background: {PANEL}; }}
QPushButton[accent="true"] {{
    background: {ACCENT};
    border: none;
    color: white;
    font-weight: 600;
}}
QPushButton[accent="true"]:hover {{ background: {ACCENT_SOFT}; }}
QPushButton[danger="true"] {{ background: #b91c1c; border: none; color: white; }}
QPushButton[danger="true"]:hover {{ background: #dc2626; }}
QPushButton[ghost="true"] {{ background: transparent; border: 1px solid {BORDER}; }}

/* Combo / spin / line */
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{
    background: {PANEL_2};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 3px 8px;
    min-height: 18px;
}}
QComboBox:hover {{ border-color: {ACCENT_DIM}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {PANEL_2};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_DIM};
    outline: none;
}}

/* Tables */
QTableWidget {{
    background: {CARD};
    border: 1px solid {BORDER_SOFT};
    border-radius: 8px;
    gridline-color: transparent;
    selection-background-color: {ACCENT_DIM};
}}
QTableWidget::item {{ padding: 4px 6px; border: none; }}
QTableWidget::item:selected {{ background: {ACCENT_DIM}; }}
QHeaderView::section {{
    background: {PANEL_2};
    color: {TEXT_MUTED};
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid {BORDER_SOFT};
    font-size: 10px;
}}
QTableCornerButton::section {{ background: {PANEL_2}; border: none; }}

/* Scrollbars */
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: #3b4a6b; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 4px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* Vertical mastering-strip sliders */
QSlider::groove:vertical {{
    background: {BORDER};
    width: 4px;
    border-radius: 2px;
}}
QSlider::handle:vertical {{
    background: {ACCENT};
    height: 12px;
    margin: 0 -6px;
    border-radius: 3px;
}}
QSlider::handle:vertical:hover {{ background: {ACCENT_SOFT}; }}
QSlider::sub-page:vertical {{ background: {BORDER}; border-radius: 2px; }}
QSlider::add-page:vertical {{ background: {ACCENT_DIM}; border-radius: 2px; }}
QSlider:disabled::handle:vertical {{ background: {TEXT_DIM}; }}

/* Horizontal sliders (humanize / volume / scrubber) */
QSlider::groove:horizontal {{ background: {BORDER}; height: 4px; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {ACCENT}; width: 12px; margin: -5px 0; border-radius: 3px;
}}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}

/* Progress bar in queue */
QProgressBar {{
    background: {BORDER}; border: none; border-radius: 3px; height: 6px; text-align: center;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}

/* Tooltips + menus */
QToolTip {{
    background: {PANEL_2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px 6px;
}}
QMenu {{ background: {PANEL_2}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 5px 20px; border-radius: 4px; }}
QMenu::item:selected {{ background: {ACCENT_DIM}; }}
QMenu::separator {{ height: 1px; background: {BORDER_SOFT}; margin: 4px 6px; }}

QDialog {{ background: {PANEL}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {BORDER}; background: {PANEL_2}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
"""
