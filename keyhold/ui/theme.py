"""A single, quiet dark theme."""

BG = "#111214"
SURFACE = "#18191c"
RAISED = "#1f2024"
BORDER = "#2a2b30"
TEXT = "#e8e8ea"
MUTED = "#8a8c93"
ACCENT = "#e8e8ea"
DANGER = "#e5484d"
WARN = "#e2a336"
OK = "#46a758"

MONO = "'JetBrains Mono', 'Cascadia Mono', 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace"

STYLESHEET = f"""
* {{
    color: {TEXT};
    font-size: 13px;
    outline: none;
}}
QMainWindow, QDialog, QWidget#root {{
    background: {BG};
}}
QScrollArea, QWidget#qt_scrollarea_viewport {{
    background: {BG};
    border: none;
}}
QLabel#title {{
    font-size: 22px;
    font-weight: 600;
}}
QLabel#heading {{
    font-size: 17px;
    font-weight: 600;
}}
QLabel#muted, QLabel#fieldLabel {{
    color: {MUTED};
}}
QLabel#fieldLabel {{
    font-size: 11px;
    letter-spacing: 0.5px;
}}
QLabel#error {{
    color: {DANGER};
}}
QLabel#mono, QLineEdit#mono, QPlainTextEdit#mono {{
    font-family: {MONO};
}}
QLineEdit#output {{
    font-family: {MONO};
    font-size: 15px;
    padding: 12px;
}}

QLineEdit, QPlainTextEdit, QSpinBox, QComboBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 9px;
    selection-background-color: #3a3c44;
}}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: #4a4c55;
}}
QLineEdit:read-only {{
    background: {BG};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {RAISED};
    border: 1px solid {BORDER};
    selection-background-color: #2c2e34;
}}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}

QPushButton {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 14px;
}}
QPushButton:hover {{ background: {RAISED}; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: {MUTED}; }}
QPushButton:focus {{ border-color: #5a5c66; }}
QPushButton#primary {{
    background: {ACCENT};
    color: {BG};
    border: 1px solid {ACCENT};
    font-weight: 600;
}}
QPushButton#primary:hover {{ background: #ffffff; }}
QPushButton#primary:disabled {{ background: #55575e; border-color: #55575e; }}
QPushButton#danger {{ color: {DANGER}; }}
QPushButton#link, QPushButton#ghost {{
    background: transparent;
    border: none;
    padding: 4px 6px;
}}
QPushButton#link {{ color: {MUTED}; }}
QPushButton#link:hover {{ color: {TEXT}; }}
QPushButton#ghost:hover {{ background: {RAISED}; }}
QPushButton:checked {{
    background: {RAISED};
    border-color: #4a4c55;
}}
QToolButton {{
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 3px 6px;
    color: {MUTED};
}}
QToolButton:hover {{ color: {TEXT}; background: {RAISED}; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid #4a4c55;
    border-radius: 3px;
    background: {SURFACE};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

QSlider::groove:horizontal {{
    height: 4px; background: {BORDER}; border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT}; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT}; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
}}

QListWidget {{
    background: {BG};
    border: none;
    border-right: 1px solid {BORDER};
}}
QListWidget::item {{
    border-radius: 6px;
    margin: 1px 6px;
}}
QListWidget::item:hover {{ background: {SURFACE}; }}
QListWidget::item:selected {{ background: {RAISED}; }}

QFrame#separator {{ background: {BORDER}; max-height: 1px; }}
QFrame#card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QMenu {{
    background: {RAISED};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QMenu::item {{ padding: 6px 18px; border-radius: 4px; }}
QMenu::item:selected {{ background: #2c2e34; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 6px; }}

QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QToolTip {{ background: {RAISED}; border: 1px solid {BORDER}; padding: 4px; }}
QStatusBar {{ color: {MUTED}; }}
"""
