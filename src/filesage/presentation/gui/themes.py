"""Temas modernos para FileSage (PySide6).

Usa un estilo oscuro limpio por defecto, inspirado en herramientas
modernas de analisis de disco. Facilmente extensible a modo claro.
"""

from __future__ import annotations

DARK_QSS = """
/* ===== FileSage Dark Theme ===== */
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", "Inter", "Roboto", sans-serif;
    font-size: 13px;
}

QMainWindow, QDialog {
    background-color: #1e1e2e;
}

/* Sidebar */
#sidebar {
    background-color: #181825;
    border-right: 1px solid #313244;
}

#sidebar QPushButton {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 12px 16px;
    text-align: left;
    color: #a6adc8;
    font-size: 14px;
    font-weight: 500;
}

#sidebar QPushButton:hover {
    background-color: #313244;
    color: #cdd6f4;
}

#sidebar QPushButton:checked {
    background-color: #89b4fa;
    color: #1e1e2e;
    font-weight: 600;
}

/* Cards / Panels */
.card {
    background-color: #313244;
    border-radius: 12px;
    border: 1px solid #45475a;
}

/* Buttons */
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #b4befe;
}

QPushButton:pressed {
    background-color: #74c7ec;
}

QPushButton:disabled {
    background-color: #45475a;
    color: #6c7086;
}

QPushButton#secondary {
    background-color: #45475a;
    color: #cdd6f4;
}

QPushButton#secondary:hover {
    background-color: #585b70;
}

QPushButton#danger {
    background-color: #f38ba8;
    color: #1e1e2e;
}

QPushButton#danger:hover {
    background-color: #eba0ac;
}

/* Tables */
QTableWidget, QTreeWidget {
    background-color: #1e1e2e;
    alternate-background-color: #181825;
    gridline-color: #313244;
    border: 1px solid #313244;
    border-radius: 8px;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}

QHeaderView::section {
    background-color: #313244;
    color: #cdd6f4;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #45475a;
    font-weight: 600;
}

/* Progress */
QProgressBar {
    background-color: #313244;
    border: none;
    border-radius: 6px;
    text-align: center;
    color: #cdd6f4;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 6px;
}

/* LineEdit / Combo */
QLineEdit, QComboBox, QSpinBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 8px;
    padding: 8px 12px;
    color: #cdd6f4;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #89b4fa;
}

/* Labels */
QLabel#title {
    font-size: 22px;
    font-weight: 700;
    color: #cdd6f4;
}

QLabel#subtitle {
    font-size: 14px;
    color: #a6adc8;
}

QLabel#stat_value {
    font-size: 28px;
    font-weight: 700;
    color: #89b4fa;
}

QLabel#stat_label {
    font-size: 12px;
    color: #a6adc8;
}

/* Scrollbars */
QScrollBar:vertical {
    background: #1e1e2e;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #585b70;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

/* Quick cards dashboard */
QFrame#quickCard {
    background-color: #313244;
    border-radius: 14px;
    border: 1px solid #45475a;
}
QFrame#quickCard:hover {
    border: 1px solid #89b4fa;
}

QScrollArea {
    background-color: transparent;
    border: none;
}

QWidget#dashboardContent {
    background-color: #1e1e2e;
}

"""
