"""Tema oscuro elegante FileSage (Catppuccin Mocha refinado).

Principios:
- Un acento primario (#89b4fa) por vista
- Texto no puro blanco: #cdd6f4 / #a6adc8
- Radios y padding consistentes
- Jerarquia tipografica clara (title / subtitle / body)
"""

from __future__ import annotations

DARK_QSS = """
/* ===== FileSage Dark · UI polished ===== */
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", "Inter", "SF Pro Text", "Roboto", "Noto Sans", sans-serif;
    font-size: 13px;
}

QMainWindow, QDialog {
    background-color: #1e1e2e;
}

QStatusBar {
    background-color: #181825;
    color: #a6adc8;
    border-top: 1px solid #313244;
    font-size: 12px;
    padding: 2px 8px;
}

QToolTip {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 10px;
}

QMessageBox {
    background-color: #1e1e2e;
}
QMessageBox QLabel {
    color: #cdd6f4;
    min-width: 280px;
}

QFrame#sidebar {
    background-color: #11111b;
    border-right: 1px solid #313244;
}

QFrame#sidebar QPushButton {
    background-color: transparent;
    border: none;
    border-radius: 10px;
    padding: 11px 14px;
    text-align: left;
    color: #a6adc8;
    font-size: 13px;
    font-weight: 500;
    margin: 1px 6px;
}

QFrame#sidebar QPushButton:hover {
    background-color: #313244;
    color: #cdd6f4;
}

QFrame#sidebar QPushButton:checked {
    background-color: #89b4fa;
    color: #11111b;
    font-weight: 600;
}

QFrame#sidebar QPushButton:checked:hover {
    background-color: #b4befe;
    color: #11111b;
}

QFrame#navIndicator {
    background-color: #89b4fa;
    border-radius: 2px;
}

QFrame#sidebar QLabel {
    background: transparent;
    border: none;
    color: #6c7086;
}

QPushButton {
    background-color: #89b4fa;
    color: #11111b;
    border: none;
    border-radius: 10px;
    padding: 10px 18px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton:hover { background-color: #b4befe; }
QPushButton:pressed { background-color: #74c7ec; }
QPushButton:disabled {
    background-color: #45475a;
    color: #6c7086;
}

QPushButton#secondary {
    background-color: #45475a;
    color: #cdd6f4;
}
QPushButton#secondary:hover { background-color: #585b70; }

QPushButton#danger {
    background-color: #f38ba8;
    color: #11111b;
}
QPushButton#danger:hover { background-color: #eba0ac; }

QPushButton#ghost {
    background-color: transparent;
    color: #89b4fa;
    border: 1px solid #45475a;
}
QPushButton#ghost:hover {
    background-color: #313244;
    border-color: #89b4fa;
}

QTableWidget, QTreeWidget {
    background-color: #1e1e2e;
    alternate-background-color: #181825;
    gridline-color: #313244;
    border: 1px solid #313244;
    border-radius: 12px;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
    outline: none;
    padding: 2px;
}

QHeaderView::section {
    background-color: #313244;
    color: #a6adc8;
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid #45475a;
    font-weight: 600;
    font-size: 12px;
}

QTreeWidget::item, QTableWidget::item { padding: 4px; }

QProgressBar {
    background-color: #313244;
    border: none;
    border-radius: 8px;
    text-align: center;
    color: #cdd6f4;
    height: 18px;
    font-size: 11px;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 8px;
}

QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 10px;
    padding: 9px 12px;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
    selection-color: #11111b;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
    border: 1px solid #89b4fa;
}

QLabel#title {
    font-size: 24px;
    font-weight: 700;
    color: #cdd6f4;
    background: transparent;
    border: none;
    letter-spacing: -0.3px;
}
QLabel#subtitle {
    font-size: 13px;
    color: #a6adc8;
    background: transparent;
    border: none;
}
QLabel#stat_value {
    font-size: 28px;
    font-weight: 700;
    color: #89b4fa;
    background: transparent;
    border: none;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 4px 2px;
}
QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 5px;
    min-height: 32px;
}
QScrollBar::handle:vertical:hover { background: #585b70; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal {
    background: transparent;
    height: 10px;
}
QScrollBar::handle:horizontal {
    background: #45475a;
    border-radius: 5px;
    min-width: 32px;
}

QFrame#quickCard {
    background-color: #313244;
    border-radius: 16px;
    border: 1px solid #45475a;
}
QFrame#quickCard:hover {
    border: 1px solid #89b4fa;
    background-color: #383a4a;
}

QScrollArea {
    background-color: transparent;
    border: none;
}
QWidget#dashboardContent { background-color: #1e1e2e; }

QCheckBox {
    color: #cdd6f4;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid #45475a;
    background: #313244;
}
QCheckBox::indicator:checked {
    background: #89b4fa;
    border-color: #89b4fa;
}

QGroupBox {
    border: 1px solid #313244;
    border-radius: 12px;
    margin-top: 12px;
    padding: 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #a6adc8;
}
"""
