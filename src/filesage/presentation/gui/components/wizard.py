"""Asistente guiado de primera limpieza (wizard).

Pensado para novatos: 4 pasos claros, siempre con dry-run primero.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from filesage.core.engine import Engine


def _fmt_size(n: int) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


class WizardWorker(QThread):
    finished_ok = Signal(object, list)
    failed = Signal(str)

    def __init__(self, engine: Engine, path: Path):
        super().__init__()
        self.engine = engine
        self.path = path

    def run(self) -> None:
        try:
            scan, groups = self.engine.find_duplicates(self.path)
            self.finished_ok.emit(scan, groups)
        except Exception as e:
            self.failed.emit(str(e))


class CleanupWizard(QDialog):
    """Wizard de 4 pasos: carpeta → escaneo → revision → accion."""

    def __init__(self, engine: Engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._path: Path | None = None
        self._groups = []
        self._worker: WizardWorker | None = None

        self.setWindowTitle("Asistente de limpieza segura")
        self.setMinimumSize(560, 420)
        self.setModal(True)

        layout = QVBoxLayout(self)

        self.step_lbl = QLabel("Paso 1 de 4")
        self.step_lbl.setObjectName("subtitle")
        layout.addWidget(self.step_lbl)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, stretch=1)

        # Paso 0: bienvenida + elegir carpeta
        p0 = QWidget()
        l0 = QVBoxLayout(p0)
        l0.addWidget(QLabel(
            "<b>Vamos a buscar archivos duplicados de forma segura.</b><br><br>"
            "1. Elige una carpeta (recomendado: Descargas o Documentos).<br>"
            "2. FileSage buscara archivos iguales.<br>"
            "3. Primero simularemos (no se borra nada).<br>"
            "4. Solo si tu confirmas, se enviaran a la papelera."
        ))
        self.path_lbl = QLabel("Ninguna carpeta seleccionada")
        self.path_lbl.setObjectName("subtitle")
        l0.addWidget(self.path_lbl)
        btn_pick = QPushButton("Seleccionar carpeta...")
        btn_pick.clicked.connect(self._pick)
        l0.addWidget(btn_pick)
        l0.addStretch()
        self.stack.addWidget(p0)

        # Paso 1: escaneando
        p1 = QWidget()
        l1 = QVBoxLayout(p1)
        l1.addWidget(QLabel("<b>Buscando duplicados...</b><br>Esto puede tardar segun el tamano de la carpeta."))
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        l1.addWidget(self.progress)
        self.scan_status = QLabel("")
        l1.addWidget(self.scan_status)
        l1.addStretch()
        self.stack.addWidget(p1)

        # Paso 2: resultados
        p2 = QWidget()
        l2 = QVBoxLayout(p2)
        l2.addWidget(QLabel("<b>Resultados</b>"))
        self.results = QTextEdit()
        self.results.setReadOnly(True)
        l2.addWidget(self.results)
        self.stack.addWidget(p2)

        # Paso 3: accion
        p3 = QWidget()
        l3 = QVBoxLayout(p3)
        l3.addWidget(QLabel(
            "<b>¿Que quieres hacer?</b><br><br>"
            "• <b>Solo simular</b>: no cambia nada, solo registra que se haria.<br>"
            "• <b>Enviar a papelera</b>: quita las copias extra (recuperables desde la papelera)."
        ))
        self.action_status = QLabel("")
        l3.addWidget(self.action_status)
        l3.addStretch()
        self.stack.addWidget(p3)

        # Navegacion
        nav = QHBoxLayout()
        self.btn_back = QPushButton("Atras")
        self.btn_back.setObjectName("secondary")
        self.btn_back.clicked.connect(self._back)
        nav.addWidget(self.btn_back)

        self.btn_next = QPushButton("Siguiente")
        self.btn_next.clicked.connect(self._next)
        nav.addWidget(self.btn_next)

        self.btn_simulate = QPushButton("Solo simular")
        self.btn_simulate.setObjectName("secondary")
        self.btn_simulate.clicked.connect(self._simulate)
        self.btn_simulate.setVisible(False)
        nav.addWidget(self.btn_simulate)

        self.btn_clean = QPushButton("Enviar a papelera")
        self.btn_clean.setObjectName("danger")
        self.btn_clean.clicked.connect(self._clean)
        self.btn_clean.setVisible(False)
        nav.addWidget(self.btn_clean)

        self.btn_close = QPushButton("Cerrar")
        self.btn_close.setObjectName("secondary")
        self.btn_close.clicked.connect(self.accept)
        self.btn_close.setVisible(False)
        nav.addWidget(self.btn_close)

        layout.addLayout(nav)
        self._update_nav()

    def _pick(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta")
        if path:
            self._path = Path(path)
            self.path_lbl.setText(str(self._path))

    def _update_nav(self) -> None:
        idx = self.stack.currentIndex()
        self.step_lbl.setText(f"Paso {idx + 1} de 4")
        self.btn_back.setEnabled(idx > 0 and idx != 1)
        self.btn_next.setVisible(idx in (0, 2))
        self.btn_simulate.setVisible(idx == 3)
        self.btn_clean.setVisible(idx == 3)
        self.btn_close.setVisible(idx == 3)
        if idx == 0:
            self.btn_next.setEnabled(self._path is not None)
        elif idx == 2:
            self.btn_next.setEnabled(True)

    def _back(self) -> None:
        idx = self.stack.currentIndex()
        if idx == 2:
            self.stack.setCurrentIndex(0)
        elif idx == 3:
            self.stack.setCurrentIndex(2)
        self._update_nav()

    def _next(self) -> None:
        idx = self.stack.currentIndex()
        if idx == 0:
            if not self._path:
                return
            self.stack.setCurrentIndex(1)
            self._update_nav()
            self._start_scan()
        elif idx == 2:
            self.stack.setCurrentIndex(3)
            self._update_nav()

    def _start_scan(self) -> None:
        self.scan_status.setText(f"Escaneando {self._path}...")
        self._worker = WizardWorker(self.engine, self._path)
        self._worker.finished_ok.connect(self._on_scan_ok)
        self._worker.failed.connect(self._on_scan_fail)
        self._worker.start()

    def _on_scan_ok(self, scan, groups) -> None:
        self._groups = groups
        wasted = sum(g.wasted_size for g in groups)
        lines = [
            f"Carpeta: {self._path}",
            f"Archivos escaneados: {scan.total_files}",
            f"Grupos de duplicados: {len(groups)}",
            f"Espacio recuperable: {_fmt_size(wasted)}",
            "",
        ]
        if not groups:
            lines.append("No se encontraron duplicados. Puedes cerrar el asistente.")
        else:
            lines.append("Primeros grupos:")
            for i, g in enumerate(groups[:8], 1):
                lines.append(f"  {i}. {g.count} archivos · recuperable {_fmt_size(g.wasted_size)}")
                for fi in g.files[:3]:
                    lines.append(f"      - {fi.path.name}")
        self.results.setPlainText("\n".join(lines))
        self.stack.setCurrentIndex(2)
        self._update_nav()
        if not groups:
            self.btn_next.setEnabled(False)

    def _on_scan_fail(self, msg: str) -> None:
        QMessageBox.critical(self, "Error", msg)
        self.stack.setCurrentIndex(0)
        self._update_nav()

    def _simulate(self) -> None:
        if not self._groups:
            return
        plans = self.engine.plan_trash_duplicates(self._groups, keep_newest=True)
        tx = self.engine.execute_actions(plans, dry_run=True)
        self.action_status.setText(
            f"Simulacion OK. Transaccion {tx.transaction_id}\n"
            f"Se enviarian {len(plans)} archivos a la papelera.\n"
            "Ningun archivo se ha modificado."
        )

    def _clean(self) -> None:
        if not self._groups:
            return
        plans = self.engine.plan_trash_duplicates(self._groups, keep_newest=True)
        reply = QMessageBox.warning(
            self,
            "Confirmar",
            f"Se enviaran {len(plans)} archivos a la PAPELERA.\n"
            "Se mantiene el mas reciente de cada grupo.\n\n¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        tx = self.engine.execute_actions(plans, dry_run=False)
        ok = sum(1 for a in tx.actions if a.success)
        self.action_status.setText(
            f"Limpieza completada. {ok}/{len(tx.actions)} acciones OK.\n"
            f"Transaccion {tx.transaction_id}\n"
            "Revisa Historial si lo necesitas."
        )
