"""Asistente guiado de primera limpia (wizard) — adaptador Qt estable."""

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
    progress = Signal(str)
    progress_fraction = Signal(float)

    def __init__(self, engine: Engine, path: Path):
        super().__init__()
        self.engine = engine
        self.path = path
        self._token = None

    def run(self) -> None:
        from filesage.application.progress import ProgressReporter, CancellationToken
        from filesage.domain.exceptions import CancelledError

        self._token = CancellationToken()

        def _cb(msg: str, frac: float | None) -> None:
            if self.isInterruptionRequested() and self._token:
                self._token.cancel()
            self.progress.emit(msg)
            if frac is not None:
                self.progress_fraction.emit(frac)

        reporter = ProgressReporter(callback=_cb, cancel=self._token)
        try:
            scan, groups = self.engine.find_duplicates(self.path, progress=reporter)
            self.finished_ok.emit(scan, groups)
        except CancelledError:
            self.failed.emit("Cancelado")
        except Exception as e:
            self.failed.emit(str(e))

    def requestInterruption(self) -> None:
        super().requestInterruption()
        if self._token is not None:
            self._token.cancel()


class CleanupWizard(QDialog):
    """Wizard de 4 pasos: carpeta → escaneo → revision → accion."""

    def __init__(self, engine: Engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._path: Path | None = None
        self._groups = []
        self._worker: WizardWorker | None = None

        self.setWindowTitle("Asistente de limpieza segura")
        self.setMinimumSize(580, 440)
        self.resize(620, 480)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.step_lbl = QLabel("Paso 1 de 4")
        self.step_lbl.setObjectName("subtitle")
        layout.addWidget(self.step_lbl)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, stretch=1)

        # Paso 0
        p0 = QWidget()
        l0 = QVBoxLayout(p0)
        intro = QLabel(
            "<b>Vamos a buscar archivos duplicados de forma segura.</b><br><br>"
            "1. Elige una carpeta (recomendado: Descargas o Documentos).<br>"
            "2. FileSage buscara archivos con el mismo contenido.<br>"
            "3. Primero simularemos (no se borra nada).<br>"
            "4. Solo si tu confirmas, se enviaran a la papelera."
        )
        intro.setWordWrap(True)
        l0.addWidget(intro)
        self.path_lbl = QLabel("Ninguna carpeta seleccionada")
        self.path_lbl.setObjectName("subtitle")
        self.path_lbl.setWordWrap(True)
        l0.addWidget(self.path_lbl)
        btn_pick = QPushButton("Seleccionar carpeta...")
        btn_pick.clicked.connect(self._pick)
        l0.addWidget(btn_pick)
        l0.addStretch()
        self.stack.addWidget(p0)

        # Paso 1
        p1 = QWidget()
        l1 = QVBoxLayout(p1)
        wait = QLabel(
            "<b>Buscando duplicados...</b><br>"
            "Esto puede tardar segun el tamano de la carpeta.<br>"
            "<i>No cierres esta ventana. Puedes cancelar abajo.</i>"
        )
        wait.setWordWrap(True)
        l1.addWidget(wait)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("Trabajando...")
        l1.addWidget(self.progress)
        self.scan_status = QLabel("Iniciando…")
        self.scan_status.setWordWrap(True)
        self.scan_status.setObjectName("subtitle")
        l1.addWidget(self.scan_status)
        self.btn_cancel_scan = QPushButton("Cancelar escaneo")
        self.btn_cancel_scan.setObjectName("secondary")
        self.btn_cancel_scan.clicked.connect(self._cancel_scan)
        l1.addWidget(self.btn_cancel_scan)
        l1.addStretch()
        self.stack.addWidget(p1)

        # Paso 2
        p2 = QWidget()
        l2 = QVBoxLayout(p2)
        l2.addWidget(QLabel("<b>Resultados</b>"))
        self.results = QTextEdit()
        self.results.setReadOnly(True)
        l2.addWidget(self.results)
        self.stack.addWidget(p2)

        # Paso 3
        p3 = QWidget()
        l3 = QVBoxLayout(p3)
        act = QLabel(
            "<b>¿Que quieres hacer?</b><br><br>"
            "• <b>Solo simular</b>: no cambia nada.<br>"
            "• <b>Enviar a papelera</b>: quita las copias extra (recuperables)."
        )
        act.setWordWrap(True)
        l3.addWidget(act)
        self.action_status = QLabel("")
        self.action_status.setWordWrap(True)
        self.action_status.setObjectName("subtitle")
        l3.addWidget(self.action_status)
        l3.addStretch()
        self.stack.addWidget(p3)

        # Nav
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
            self._update_nav()

    def _update_nav(self) -> None:
        idx = self.stack.currentIndex()
        self.step_lbl.setText(f"Paso {idx + 1} de 4")
        self.btn_back.setEnabled(idx > 0 and idx != 1)
        self.btn_next.setVisible(idx in (0, 2))
        self.btn_simulate.setVisible(idx == 3)
        self.btn_clean.setVisible(idx == 3)
        self.btn_close.setVisible(idx in (2, 3) and (idx == 3 or not self._groups))
        if idx == 0:
            self.btn_next.setEnabled(self._path is not None)
            self.btn_next.setText("Siguiente")
        elif idx == 1:
            self.btn_next.setEnabled(False)
            self.btn_next.setVisible(False)
        elif idx == 2:
            self.btn_next.setEnabled(bool(self._groups))
            self.btn_next.setText("Continuar")
            self.btn_close.setVisible(not self._groups)
        elif idx == 3:
            self.btn_next.setVisible(False)

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
                QMessageBox.information(self, "Asistente", "Selecciona una carpeta primero.")
                return
            self.stack.setCurrentIndex(1)
            self._update_nav()
            self._start_scan()
        elif idx == 2:
            if not self._groups:
                return
            self.stack.setCurrentIndex(3)
            self._update_nav()

    def _start_scan(self) -> None:
        self.scan_status.setText(f"Escaneando:\n{self._path}")
        self.progress.setRange(0, 0)
        self.progress.setFormat("Trabajando...")
        self.progress.setVisible(True)
        self.btn_cancel_scan.setEnabled(True)
        self._worker = WizardWorker(self.engine, self._path)
        self._worker.finished_ok.connect(self._on_scan_ok)
        self._worker.failed.connect(self._on_scan_fail)
        self._worker.progress.connect(self.scan_status.setText)
        self._worker.progress_fraction.connect(self._on_frac)
        self._worker.start()

    def _on_frac(self, frac: float) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(int(frac * 100))
        self.progress.setFormat(f"{int(frac * 100)}%")

    def _cancel_scan(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            self.scan_status.setText("Cancelando…")
            self.btn_cancel_scan.setEnabled(False)

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
            lines.append("Primeros grupos (se mantendra el mas reciente de cada uno):")
            for i, g in enumerate(groups[:10], 1):
                lines.append(f"  {i}. {g.count} archivos · recuperable {_fmt_size(g.wasted_size)}")
                for fi in g.files[:3]:
                    lines.append(f"      - {fi.path.name}")
                if g.count > 3:
                    lines.append(f"      - … y {g.count - 3} mas")
        self.results.setPlainText("\n".join(lines))
        self.stack.setCurrentIndex(2)
        self._update_nav()

    def _on_scan_fail(self, msg: str) -> None:
        if msg == "Cancelado":
            QMessageBox.information(self, "Asistente", "Escaneo cancelado.")
        else:
            QMessageBox.critical(self, "Error", msg)
        self.stack.setCurrentIndex(0)
        self._update_nav()

    def _simulate(self) -> None:
        if not self._groups:
            return
        plans = self.engine.plan_trash_duplicates(self._groups, keep_newest=True)
        tx = self.engine.execute_actions(plans, dry_run=True)
        self.action_status.setText(
            f"Simulacion OK · Transaccion {tx.transaction_id}\n"
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
            f"Completado: {ok}/{len(tx.actions)} OK\n"
            f"Transaccion {tx.transaction_id}\n"
            "Revisa Historial si lo necesitas."
        )
        self._groups = []
