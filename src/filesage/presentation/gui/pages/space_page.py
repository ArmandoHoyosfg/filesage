"""Pagina de Analisis de Espacio.

Usa el Engine existente. Todo el trabajo pesado se hace en background
mediante QThread para no congelar la UI.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from filesage.core.engine import Engine
from filesage.domain.models import SpaceReport


def _fmt_size(n: int) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


class ScanWorker(QThread):
    """Worker que ejecuta el analisis de espacio en segundo plano."""

    finished_ok = Signal(object, object)  # ScanResult, SpaceReport
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, engine: Engine, path: Path, top_n: int = 30):
        super().__init__()
        self.engine = engine
        self.path = path
        self.top_n = top_n

    def run(self) -> None:
        try:
            self.progress.emit(f"Escaneando {self.path}...")
            scan_result, report = self.engine.analyze_space(self.path, top_n=self.top_n)
            self.finished_ok.emit(scan_result, report)
        except Exception as exc:
            self.failed.emit(str(exc))


class StatCard(QFrame):
    """Tarjeta de estadistica."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setStyleSheet(
            "QFrame { background-color: #313244; border-radius: 12px; "
            "border: 1px solid #45475a; padding: 16px; }"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        self.value_lbl = QLabel("—")
        self.value_lbl.setObjectName("stat_value")
        self.value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_lbl)

        self.label_lbl = QLabel(label)
        self.label_lbl.setObjectName("stat_label")
        self.label_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label_lbl)

    def set_value(self, text: str) -> None:
        self.value_lbl.setText(text)


class SpacePage(QWidget):
    """Vista principal de analisis de espacio."""

    def __init__(self, engine: Engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._worker: ScanWorker | None = None
        self._current_path: Path | None = None
        self._last_report = None
        self._last_scan = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Cabecera
        header = QHBoxLayout()
        title = QLabel("Analisis de Espacio")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()

        self.path_lbl = QLabel("Ninguna carpeta seleccionada")
        self.path_lbl.setObjectName("subtitle")
        header.addWidget(self.path_lbl)

        self.btn_browse = QPushButton("Seleccionar carpeta")
        self.btn_browse.setToolTip("Elige la carpeta o unidad que quieres analizar")
        self.btn_browse.setObjectName("secondary")
        self.btn_browse.clicked.connect(self._on_browse)
        header.addWidget(self.btn_browse)

        self.btn_analyze = QPushButton("Analizar")
        self.btn_analyze.setToolTip("Escanea y muestra los archivos y tipos que mas ocupan")
        self.btn_analyze.clicked.connect(self._on_analyze)
        self.btn_analyze.setEnabled(False)
        header.addWidget(self.btn_analyze)

        self.btn_export = QPushButton("Exportar")
        self.btn_export.setToolTip("Guarda el informe en JSON o CSV")
        self.btn_export.setObjectName("secondary")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._on_export)
        header.addWidget(self.btn_export)

        layout.addLayout(header)

        # Stats cards
        cards = QHBoxLayout()
        cards.setSpacing(16)
        self.card_files = StatCard("Archivos")
        self.card_size = StatCard("Tamano total")
        self.card_time = StatCard("Tiempo")
        cards.addWidget(self.card_files)
        cards.addWidget(self.card_size)
        cards.addWidget(self.card_time)
        layout.addLayout(cards)

        # Progress
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminado
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_lbl = QLabel("")
        self.status_lbl.setObjectName("subtitle")
        layout.addWidget(self.status_lbl)

        # Tabla top archivos
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["#", "Tamano", "Ruta"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, stretch=1)

        # Tabla extensiones
        self.ext_table = QTableWidget(0, 3)
        self.ext_table.setHorizontalHeaderLabels(["Extension", "Tamano", "%"])
        self.ext_table.horizontalHeader().setStretchLastSection(True)
        self.ext_table.setAlternatingRowColors(True)
        self.ext_table.setMaximumHeight(220)
        self.ext_table.verticalHeader().setVisible(False)
        layout.addWidget(self.ext_table)

    def _on_browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta o unidad")
        if path:
            self._current_path = Path(path)
            self.path_lbl.setText(str(self._current_path))
            self.btn_analyze.setEnabled(True)

    def _on_analyze(self) -> None:
        if not self._current_path:
            return
        if self._worker and self._worker.isRunning():
            return

        self.btn_analyze.setEnabled(False)
        self.btn_browse.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress.setVisible(True)
        self.status_lbl.setText("Analizando...")
        self.table.setRowCount(0)
        self.ext_table.setRowCount(0)

        self._worker = ScanWorker(self.engine, self._current_path, top_n=40)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.progress.connect(self.status_lbl.setText)
        self._worker.start()

    def _on_finished(self, scan_result, report: SpaceReport) -> None:
        self.progress.setVisible(False)
        self.btn_analyze.setEnabled(True)
        self.btn_browse.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.status_lbl.setText("Analisis completado")
        self._last_scan = scan_result
        self._last_report = report
        self.btn_export.setEnabled(True)

        self.card_files.set_value(f"{report.total_files:,}")
        self.card_size.set_value(_fmt_size(report.total_size))
        self.card_time.set_value(f"{scan_result.duration_seconds:.2f} s")

        # Top archivos
        self.table.setRowCount(len(report.top_files))
        root = report.root
        for i, fi in enumerate(report.top_files):
            try:
                rel = str(fi.path.relative_to(root))
            except ValueError:
                rel = str(fi.path)
            self.table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.table.setItem(i, 1, QTableWidgetItem(_fmt_size(fi.size)))
            self.table.setItem(i, 2, QTableWidgetItem(rel))
        self.table.resizeColumnsToContents()

        # Extensiones
        items = list(report.by_extension.items())[:15]
        total = report.total_size or 1
        self.ext_table.setRowCount(len(items))
        for i, (ext, size) in enumerate(items):
            pct = (size / total) * 100
            self.ext_table.setItem(i, 0, QTableWidgetItem(ext))
            self.ext_table.setItem(i, 1, QTableWidgetItem(_fmt_size(size)))
            self.ext_table.setItem(i, 2, QTableWidgetItem(f"{pct:.1f}%"))
        self.ext_table.resizeColumnsToContents()

    def _on_failed(self, message: str) -> None:
        self.progress.setVisible(False)
        self.btn_analyze.setEnabled(True)
        self.btn_browse.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.status_lbl.setText("Error")
        QMessageBox.critical(self, "Error de analisis", message)

    def _on_export(self) -> None:
        if not self._last_report or not self._last_scan:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar reporte", "filesage_space.json",
            "JSON (*.json);;CSV (*.csv)"
        )
        if not path:
            return
        fmt = "csv" if path.lower().endswith(".csv") else "json"
        try:
            out = self.engine.export_space(self._last_report, self._last_scan, Path(path), fmt=fmt)
            QMessageBox.information(self, "Exportar", f"Reporte guardado en:\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            self.status_lbl.setText("Cancelando...")
            self.btn_cancel.setEnabled(False)
