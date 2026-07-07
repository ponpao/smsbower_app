"""Dark theme QSS for the whole app."""

from __future__ import annotations

from .constants import (
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRESSED,
    COLOR_BG,
    COLOR_BG_ELEVATED,
    COLOR_BG_INPUT,
    COLOR_BORDER,
    COLOR_ERROR,
    COLOR_TEXT,
    COLOR_TEXT_SECONDARY,
)


def build_stylesheet(font_family: str) -> str:
    return f"""
    * {{
        font-family: "{font_family}", "Segoe UI", sans-serif;
        color: {COLOR_TEXT};
        font-size: 13px;
    }}
    QWidget#Card {{
        background: {COLOR_BG};
        border-radius: 12px;
    }}
    QWidget#Sidebar {{
        background: {COLOR_BG_ELEVATED};
        border-top-left-radius: 0px;
        border-bottom-left-radius: 12px;
    }}
    QLabel {{ background: transparent; }}
    QLabel[secondary="true"] {{ color: {COLOR_TEXT_SECONDARY}; font-size: 12px; }}
    QLabel[error="true"] {{ color: {COLOR_ERROR}; }}

    QPushButton {{
        background: {COLOR_BG_INPUT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 8px;
        padding: 7px 14px;
    }}
    QPushButton:hover {{ background: #232330; }}
    QPushButton:pressed {{ background: #1A1A24; }}
    QPushButton:disabled {{ color: {COLOR_TEXT_SECONDARY}; background: #16161E; }}
    QPushButton[accent="true"] {{
        background: {COLOR_ACCENT};
        border: none;
        color: white;
        font-weight: 600;
    }}
    QPushButton[accent="true"]:hover {{ background: {COLOR_ACCENT_HOVER}; }}
    QPushButton[accent="true"]:pressed {{ background: {COLOR_ACCENT_PRESSED}; }}
    QPushButton[accent="true"]:disabled {{ background: #3A3552; color: #B9B3D6; }}
    QPushButton[danger="true"] {{
        background: transparent; border: 1px solid {COLOR_ERROR}; color: {COLOR_ERROR};
    }}
    QPushButton[flat="true"] {{
        background: transparent; border: none; color: {COLOR_TEXT_SECONDARY};
    }}
    QPushButton[flat="true"]:hover {{ color: {COLOR_TEXT}; }}

    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox {{
        background: {COLOR_BG_INPUT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 8px;
        padding: 7px 10px;
        selection-background-color: {COLOR_ACCENT};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {{
        border: 1px solid {COLOR_ACCENT};
    }}

    QComboBox {{
        background: {COLOR_BG_INPUT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 8px;
        padding: 6px 10px;
    }}
    QComboBox:focus {{ border: 1px solid {COLOR_ACCENT}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {COLOR_TEXT_SECONDARY};
        margin-right: 8px;
    }}
    QComboBox QAbstractItemView {{
        background: {COLOR_BG_ELEVATED};
        border: 1px solid {COLOR_BORDER};
        border-radius: 8px;
        selection-background-color: {COLOR_ACCENT};
        outline: none;
    }}

    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{
        background: transparent; width: 8px; margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {COLOR_BORDER}; border-radius: 4px; min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {COLOR_TEXT_SECONDARY}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 2px; }}
    QScrollBar::handle:horizontal {{
        background: {COLOR_BORDER}; border-radius: 4px; min-width: 24px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    QProgressBar {{
        background: {COLOR_BG_INPUT};
        border: none; border-radius: 6px;
        height: 12px; text-align: center;
        color: {COLOR_TEXT}; font-size: 10px;
    }}
    QProgressBar::chunk {{ background: {COLOR_ACCENT}; border-radius: 6px; }}

    QSlider::groove:horizontal {{
        height: 4px; background: {COLOR_BG_INPUT}; border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{ background: {COLOR_ACCENT}; border-radius: 2px; }}
    QSlider::handle:horizontal {{
        width: 14px; height: 14px; margin: -5px 0;
        border-radius: 7px; background: {COLOR_TEXT};
    }}

    QToolTip {{
        background: {COLOR_BG_ELEVATED};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        padding: 6px;
    }}

    QCheckBox::indicator, QRadioButton::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {COLOR_BORDER}; border-radius: 4px;
        background: {COLOR_BG_INPUT};
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background: {COLOR_ACCENT}; border-color: {COLOR_ACCENT};
    }}
    QRadioButton::indicator {{ border-radius: 8px; }}

    QMenu {{
        background: {COLOR_BG_ELEVATED};
        border: 1px solid {COLOR_BORDER}; border-radius: 8px; padding: 4px;
    }}
    QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {COLOR_ACCENT}; }}
    """
