# -*- coding: utf-8 -*-
"""Modern light-green theme (QSS) matching the v1.1 design."""

GREEN = "#3fae4c"
GREEN_DARK = "#2f8a3b"
GREEN_TEXT = "#2f6b33"
BG = "#f4f6f4"

THEME_QSS = f"""
QMainWindow, QDialog {{
    background: {BG};
}}
QMenuBar {{
    background: #fbfcfb;
    border-bottom: 1px solid #e3e8e3;
    padding: 2px 6px;
}}
QMenuBar::item {{
    padding: 5px 10px;
    border-radius: 6px;
    color: #333;
}}
QMenuBar::item:selected {{
    background: #e4f2e5;
}}
QMenu {{
    background: white;
    border: 1px solid #dfe5df;
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    padding: 6px 26px 6px 14px;
    border-radius: 6px;
    color: #333;
}}
QMenu::item:selected {{
    background: #e4f2e5;
    color: {GREEN_TEXT};
}}
QMenu::separator {{
    height: 1px;
    background: #e8ece8;
    margin: 5px 8px;
}}
QLineEdit {{
    background: white;
    border: 1px solid #dfe5df;
    border-radius: 14px;
    padding: 8px 14px;
    selection-background-color: {GREEN};
}}
QLineEdit:focus {{
    border: 1px solid {GREEN};
}}
QTabBar {{
    background: transparent;
}}
QTabBar::tab {{
    background: transparent;
    color: #666;
    padding: 8px 18px;
    margin: 4px 4px 6px 0;
    border-radius: 15px;
    font-weight: 600;
}}
QTabBar::tab:selected {{
    background: {GREEN};
    color: white;
}}
QTabBar::tab:hover:!selected {{
    background: #e4f2e5;
    color: {GREEN_TEXT};
}}
QTableWidget {{
    background: white;
    alternate-background-color: #fafcfa;
    border: 1px solid #e3e8e3;
    border-radius: 8px;
    gridline-color: #eef1ee;
    selection-background-color: #cfe9d2;
    selection-color: #1c331e;
}}
QHeaderView::section {{
    background: #eaf3e6;
    color: {GREEN_TEXT};
    font-weight: 700;
    padding: 9px 6px;
    border: none;
    border-right: 1px solid #dde7da;
    border-bottom: 2px solid {GREEN};
}}
QTableWidget::item {{
    padding: 4px 6px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle {{
    background: {GREEN};
    border-radius: 4px;
    min-height: 24px;
    min-width: 24px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0; height: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
QPushButton {{
    background: white;
    border: 1px solid #d8ded8;
    border-radius: 8px;
    padding: 7px 16px;
    color: #333;
}}
QPushButton:hover {{
    border-color: {GREEN};
    color: {GREEN_TEXT};
}}
QPushButton:default {{
    background: {GREEN};
    border-color: {GREEN};
    color: white;
    font-weight: 600;
}}
QPushButton:default:hover {{
    background: {GREEN_DARK};
}}
QCheckBox {{
    color: #444;
    spacing: 7px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid #c9d2c9;
    border-radius: 4px;
    background: white;
}}
QCheckBox::indicator:checked {{
    background: {GREEN};
    border-color: {GREEN};
}}
QStatusBar {{
    background: #fbfcfb;
    border-top: 1px solid #e3e8e3;
}}
QStatusBar::item {{
    border: none;
}}
QComboBox {{
    background: white;
    border: 1px solid #dfe5df;
    border-radius: 8px;
    padding: 6px 10px;
}}
QPlainTextEdit {{
    background: white;
    border: 1px solid #e3e8e3;
    border-radius: 8px;
    font-family: Consolas, monospace;
}}
"""
