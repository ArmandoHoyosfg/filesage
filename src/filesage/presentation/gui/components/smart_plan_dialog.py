"""Dialogo del plan inteligente (modo Smart)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from filesage.core.engine import Engine
from filesage.application.types import Confidence, SmartPlan



def _fmt(n: int) -> str:
    v = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(v) < 1024:
            return f"{v:.1f} {u}"
        v /= 1024
    return f"{v:.1f} PB"


class PlanWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)
    progress = Signal(str)
    progress_fraction = Signal(float)

    def __init__(self, engine: Engine, path: Path):
        super().__init__()
        self.engine = engine
        self.path = path

    def run(self) -> None:
        from filesage.application.progress import ProgressReporter
        from filesage.domain.exceptions import CancelledError

        def _cb(msg: str, frac: float | None) -> None:
            self.progress.emit(msg)
            if frac is not None:
                self.progress_fraction.emit(frac)

        reporter = ProgressReporter(callback=_cb)
        try:
            plan = self.engine.build_smart_plan(self.path, progress=reporter)
            self.finished_ok.emit(plan)
        except CancelledError:
            self.failed.emit("Cancelado")
        except Exception as e:
            self.failed.emit(str(e))



class SmartPlanDialog(QDialog):
    def __init__(self, engine: Engine, parent=None, initial_path: Path | None = None):
        super().__init__(parent)
        self.engine = engine
        self._plan: SmartPlan | None = None
        self._worker: PlanWorker | None = None
        self._path: Path | None = initial_path
        self._row_checks: list = []

        self.setWindowTitle("Plan inteligente")
        self.setMinimumSize(720, 520)
        self.resize(820, 560)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.info = QLabel(
            "Plan conservador: alta = duplicados (preseleccionados) | "
            "media = instaladores / vacios / organizar por tipo | "
            "Simula siempre antes de aplicar."
        )
        self.info.setWordWrap(True)
        self.info.setObjectName("subtitle")
        layout.addWidget(self.info)

        path_row = QHBoxLayout()
        self.path_lbl = QLabel(str(initial_path) if initial_path else "Ninguna carpeta")
        self.path_lbl.setObjectName("subtitle")
        path_row.addWidget(self.path_lbl, stretch=1)
        btn_folder = QPushButton("Elegir carpeta...")
        btn_folder.setObjectName("secondary")
        btn_folder.clicked.connect(self._pick)
        path_row.addWidget(btn_folder)
        self.btn_analyze = QPushButton("Analizar")
        self.btn_analyze.clicked.connect(self._analyze)
        path_row.addWidget(self.btn_analyze)
        layout.addLayout(path_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_scan = QLabel("")
        self.status_scan.setObjectName("subtitle")
        self.status_scan.setWordWrap(True)
        layout.addWidget(self.status_scan)

        filter_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filtrar por nombre, extension, tipo o motivo...")
        self.search.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.search, stretch=1)
        self.btn_sel_all = QPushButton("Seleccionar visibles")
        self.btn_sel_all.setObjectName("secondary")
        self.btn_sel_all.setEnabled(False)
        self.btn_sel_all.clicked.connect(lambda: self._set_visible_selection(True))
        filter_row.addWidget(self.btn_sel_all)
        self.btn_sel_none = QPushButton("Quitar seleccion")
        self.btn_sel_none.setObjectName("secondary")
        self.btn_sel_none.setEnabled(False)
        self.btn_sel_none.clicked.connect(lambda: self._set_visible_selection(False))
        filter_row.addWidget(self.btn_sel_none)
        self.btn_sel_high = QPushButton("Solo confianza alta")
        self.btn_sel_high.setObjectName("secondary")
        self.btn_sel_high.setEnabled(False)
        self.btn_sel_high.clicked.connect(self._select_high_only)
        filter_row.addWidget(self.btn_sel_high)
        layout.addLayout(filter_row)

        self.summary = QLabel("")
        self.summary.setObjectName("subtitle")
        layout.addWidget(self.summary)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Incluir", "Confianza", "Tamano", "Que es", "Motivo / archivo"])
        self.tree.setColumnWidth(0, 55)
        self.tree.setColumnWidth(1, 85)
        self.tree.setColumnWidth(2, 80)
        self.tree.setColumnWidth(3, 160)
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(False)
        layout.addWidget(self.tree, stretch=1)

        actions = QHBoxLayout()
        self.btn_sim = QPushButton("Simular plan")
        self.btn_sim.setObjectName("secondary")
        self.btn_sim.setEnabled(False)
        self.btn_sim.clicked.connect(self._simulate)
        actions.addWidget(self.btn_sim)
        self.btn_apply = QPushButton("Aplicar seleccion")
        self.btn_apply.setObjectName("danger")
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply)
        actions.addWidget(self.btn_apply)
        btn_close = QPushButton("Cerrar")
        btn_close.setObjectName("secondary")
        btn_close.clicked.connect(self.reject)
        actions.addWidget(btn_close)
        layout.addLayout(actions)

        if initial_path:
            self._analyze()

    def _pick(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Carpeta para el plan inteligente")
        if path:
            self._path = Path(path)
            self.path_lbl.setText(str(self._path))

    def _analyze(self) -> None:
        if not self._path:
            QMessageBox.information(self, "Plan", "Elige una carpeta primero.")
            return
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.progress.setFormat("Analizando...")
        if hasattr(self, "status_scan"):
            self.status_scan.setText("Iniciando plan inteligente…")
        self.btn_analyze.setEnabled(False)
        self.tree.clear()
        self._row_checks.clear()
        self._worker = PlanWorker(self.engine, self._path)
        self._worker.finished_ok.connect(self._on_plan)
        self._worker.failed.connect(self._on_fail)
        if hasattr(self, "status_scan"):
            self._worker.progress.connect(self.status_scan.setText)
        self._worker.progress_fraction.connect(self._on_frac)
        self._worker.start()

    def _on_frac(self, frac: float) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(int(frac * 100))
        self.progress.setFormat(f"{int(frac * 100)}%")

    def _on_fail(self, msg: str) -> None:
        self.progress.setVisible(False)
        self.btn_analyze.setEnabled(True)
        QMessageBox.critical(self, "Error", msg)

    def _on_plan(self, plan: SmartPlan) -> None:
        self.progress.setVisible(False)
        self.btn_analyze.setEnabled(True)
        if hasattr(self, "status_scan"):
            self.status_scan.setText("")
        self._plan = plan
        self.tree.clear()
        self._row_checks.clear()
        conf_label = {
            Confidence.HIGH: "Alta",
            Confidence.MEDIUM: "Media",
            Confidence.LOW: "Baja",
        }
        for item in plan.items:
            row = QTreeWidgetItem([
                "",
                conf_label.get(item.confidence, item.confidence.value),
                _fmt(item.size),
                item.what or "-",
                f"{item.reason}\n{item.path}",
            ])
            row.setData(0, Qt.ItemDataRole.UserRole, item)
            self.tree.addTopLevelItem(row)
            chk = QCheckBox()
            chk.setChecked(item.selected)
            chk.stateChanged.connect(lambda state, it=item: self._toggle(it, state))
            self.tree.setItemWidget(row, 0, chk)
            self._row_checks.append((item, chk, row))
        for b in (self.btn_sel_all, self.btn_sel_none, self.btn_sel_high, self.btn_sim):
            b.setEnabled(len(plan.items) > 0)
        self.search.clear()
        self._refresh_apply_state()

    def _toggle(self, item, state) -> None:
        item.selected = state == Qt.CheckState.Checked.value or state == 2
        self._refresh_apply_state()

    def _apply_filter(self, text: str) -> None:
        q = text.strip().lower()
        for item, chk, row in self._row_checks:
            hay = " ".join([
                str(item.path),
                item.path.suffix,
                item.reason,
                item.what or "",
                item.category,
                item.confidence.value,
                str(item.metadata.get("mime", "")),
            ]).lower()
            row.setHidden(bool(q) and q not in hay)

    def _set_visible_selection(self, selected: bool) -> None:
        for item, chk, row in self._row_checks:
            if row.isHidden():
                continue
            chk.blockSignals(True)
            chk.setChecked(selected)
            chk.blockSignals(False)
            item.selected = selected
        self._refresh_apply_state()

    def _select_high_only(self) -> None:
        for item, chk, row in self._row_checks:
            want = item.confidence == Confidence.HIGH
            chk.blockSignals(True)
            chk.setChecked(want)
            chk.blockSignals(False)
            item.selected = want
        self._refresh_apply_state()

    def _refresh_apply_state(self) -> None:
        if not self._plan:
            return
        n = len(self._plan.selected_items)
        b = self._plan.selected_bytes
        self.btn_apply.setEnabled(n > 0)
        self.btn_sim.setEnabled(len(self._plan.items) > 0)
        self.summary.setText(
            f"Escaneados: {self._plan.scan_files} · "
            f"Candidatos: {len(self._plan.items)} · "
            f"Seleccionados: {n} ({_fmt(b)})"
        )

    def _simulate(self) -> None:
        if not self._plan:
            return
        actions = self.engine.smart_plan_to_actions(self._plan)
        if not actions:
            QMessageBox.information(self, "Simular", "No hay elementos seleccionados.")
            return
        tx = self.engine.execute_actions(actions, dry_run=True)
        QMessageBox.information(
            self,
            "Simulacion",
            f"Dry-run OK.\nTransaccion: {tx.transaction_id}\n"
            f"Acciones: {len(actions)} ({_fmt(self._plan.selected_bytes)}).\n\n"
            "Ningun archivo se ha modificado.",
        )

    def _apply(self) -> None:
        if not self._plan or not self._plan.selected_items:
            return
        reply = QMessageBox.warning(
            self,
            "Confirmar plan inteligente",
            f"Se aplicaran {len(self._plan.selected_items)} acciones "
            f"({_fmt(self._plan.selected_bytes)}).\n\n"
            "Pueden incluir papelera y/o mover a carpetas.\nContinuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        actions = self.engine.smart_plan_to_actions(self._plan)
        tx = self.engine.execute_actions(actions, dry_run=False)
        ok = sum(1 for a in tx.actions if a.success)
        QMessageBox.information(
            self,
            "Plan aplicado",
            f"Completado: {ok}/{len(tx.actions)}\nTransaccion: {tx.transaction_id}",
        )
        self.accept()
