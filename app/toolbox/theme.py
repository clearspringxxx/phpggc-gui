"""主题：纯黑暗色风 —— 黑灰中性色 / 白色强调 / 等宽字体。"""
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# 基础色板：纯黑 + 中性灰
BG = "#0d0d0d"          # 窗口背景
PANEL = "#141414"       # 面板/树/输出区
INPUT = "#1a1a1a"       # 输入框
BORDER = "#2a2a2a"      # 边框
TEXT = "#d4d4d4"        # 正文浅灰
MUTED = "#828282"       # 次要文字
ACCENT = "#f0f0f0"      # 强调：白
DANGER = "#ff5f56"      # 错误红

DARK_QSS = f"""
* {{ outline: none; }}
QMainWindow, QDialog {{ background: {BG}; }}
QWidget {{
    color: {TEXT};
    font-family: "Consolas", "Microsoft YaHei UI";
    font-size: 10pt;
}}

QLineEdit, QComboBox, QSpinBox {{
    background: {INPUT}; border: 1px solid {BORDER}; border-radius: 3px;
    padding: 4px 8px; selection-background-color: #3a3a3a;
    color: {TEXT};
}}
QLineEdit:focus, QComboBox:focus {{
    border-color: #6e6e6e;
    color: #ffffff;
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {PANEL}; border: 1px solid {BORDER};
    selection-background-color: #3a3a3a; selection-color: #ffffff;
    color: {TEXT};
}}

QPushButton {{
    background: #1e1e1e; border: 1px solid {BORDER}; border-radius: 3px;
    padding: 5px 14px; color: {TEXT};
    font-family: "Consolas", "Microsoft YaHei UI";
}}
QPushButton:hover {{
    background: #262626; border-color: #5a5a5a; color: #ffffff;
}}
QPushButton:pressed {{ background: #191919; }}
QPushButton:disabled {{ color: #555555; background: #161616; }}
QPushButton#primary {{
    background: #e8e8e8; border: 1px solid #ffffff;
    color: #111111; font-weight: bold; padding: 7px 24px;
}}
QPushButton#primary:hover {{ background: #ffffff; }}
QPushButton#primary:pressed {{ background: #cfcfcf; }}
QPushButton#primary:disabled {{ background: #2c2c2c; color: #666666; border-color: {BORDER}; }}

QPushButton#winbtn {{
    background: transparent; border: none; border-radius: 3px;
    color: {MUTED}; font-size: 11pt; padding: 0;
}}
QPushButton#winbtn:hover {{ background: #2c2c2c; color: #ffffff; }}
QPushButton#winbtn:pressed {{ background: #242424; }}
QPushButton#winbtn-danger:hover {{ background: #c42b1c; color: #ffffff; }}
QPushButton#winbtn-danger:pressed {{ background: #a82517; }}

QGroupBox {{
    border: 1px solid {BORDER}; border-radius: 4px; margin-top: 12px;
    background: {PANEL}; padding-top: 4px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 10px; padding: 0 4px;
    color: #a0a0a0;
}}

QTreeWidget, QListWidget, QPlainTextEdit, QTreeView {{
    background: {PANEL}; border: 1px solid {BORDER}; border-radius: 3px;
    selection-background-color: #333333; selection-color: #ffffff;
    alternate-background-color: #111111;
}}
QPlainTextEdit, QTreeWidget, QListWidget {{
    font-family: "Consolas", "Microsoft YaHei UI";
}}
QPlainTextEdit {{ font-size: 10pt; color: #c8c8c8; }}
QHeaderView::section {{
    background: {PANEL}; color: #9a9a9a; border: none;
    border-bottom: 1px solid {BORDER}; padding: 5px;
    font-family: "Consolas", "Microsoft YaHei UI";
}}

QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 3px; background: {PANEL}; }}
QTabBar::tab {{
    background: transparent; color: {MUTED}; padding: 7px 18px;
    border: 1px solid transparent; border-bottom: none;
    border-top-left-radius: 3px; border-top-right-radius: 3px;
}}
QTabBar::tab:selected {{
    background: {PANEL}; color: #ffffff; border-color: {BORDER};
}}
QTabBar::tab:hover:!selected {{ color: {TEXT}; }}

QSplitter::handle {{ background: {BG}; width: 5px; height: 5px; }}
QSplitter::handle:hover {{ background: #333333; }}

QCheckBox {{ spacing: 6px; }}
QCheckBox:hover {{ color: #ffffff; }}
QCheckBox::indicator, QGroupBox::indicator {{
    width: 14px; height: 14px; border: 1px solid {BORDER};
    border-radius: 2px; background: {INPUT};
}}
QCheckBox::indicator:hover {{ border-color: #6e6e6e; }}
QCheckBox::indicator:checked, QGroupBox::indicator:checked {{
    background: #d9d9d9; border-color: #ffffff;
}}

QScrollBar:vertical {{ background: {PANEL}; width: 10px; margin: 1px; }}
QScrollBar::handle:vertical {{ background: #303030; border-radius: 2px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: #454545; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: {PANEL}; height: 10px; margin: 1px; }}
QScrollBar::handle:horizontal {{ background: #303030; border-radius: 2px; min-width: 24px; }}
QScrollBar::handle:horizontal:hover {{ background: #454545; }}

QStatusBar {{
    background: {PANEL}; color: {MUTED};
    border-top: 1px solid {BORDER};
    font-family: "Consolas", "Microsoft YaHei UI";
}}
QToolTip {{
    background: #1c1c1c; color: {TEXT}; border: 1px solid #4a4a4a; padding: 4px;
}}
QLabel#muted {{ color: {MUTED}; }}
QLabel#title {{
    font-size: 12pt; font-weight: bold; color: {ACCENT}; letter-spacing: 1px;
}}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(BG))
    pal.setColor(QPalette.WindowText, QColor(TEXT))
    pal.setColor(QPalette.Base, QColor(PANEL))
    pal.setColor(QPalette.AlternateBase, QColor("#111111"))
    pal.setColor(QPalette.Text, QColor(TEXT))
    pal.setColor(QPalette.Button, QColor("#1e1e1e"))
    pal.setColor(QPalette.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.Highlight, QColor("#333333"))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ToolTipBase, QColor("#1c1c1c"))
    pal.setColor(QPalette.ToolTipText, QColor(TEXT))
    pal.setColor(QPalette.Link, QColor("#c8c8c8"))
    pal.setColor(QPalette.PlaceholderText, QColor("#5c5c5c"))
    app.setPalette(pal)
    app.setStyleSheet(DARK_QSS)
