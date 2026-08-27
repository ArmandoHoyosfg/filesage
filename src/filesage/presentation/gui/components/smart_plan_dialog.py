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
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from filesage.core.engine import Engine
from filesage.services.smart_planner import Confidence, SmartPlan, SmartPlanner


def _fmt(n: int) -> str:
    v = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(v) < 1024:
            return f"{v:.1f} {u}"
        v /= 1024
    return f"{v:.1f} PB"


class PlanWorker(QThread):
    finished_ok = Signal(object)  # SmartPlan
    failed = Signal(str)

    def __init__(self, engine: Engine, path: Path):
        super().__init__()
        self.engine = engine
        self.path = path

    def run(self) -> None:
        try:
            scan, groups = self.engine.find_duplicates(self.path)
            planner = SmartPlanner(self.engine.settings)
            plan = planner.build(scan, groups, include_medium=True, include_low=False)
            self.finished_ok.emit(plan)
        except Exception as e:
            self.failed.emit(str(e))


class SmartPlanDialog(QDialog):
    def __init__(self, engine: Engine, parent=None, initial_path: Path | None = None):
        super().__init__(parent)
        self.engine = engine
        self._plan: SmartPlan | None = None
        self._worker: PlanWorker | None = None

        self.setWindowTitle("Plan inteligente")
        self.setMinimumSize(640, 480)
        self.setModal(True)

        layout = QVBoxLayout(self)

        self.info = QLabel(
            "FileSage analizara la carpeta y proponda un plan conservador:\n"
            "• Confianza alta (duplicados exactos) → preseleccionados\n"
            "• Confianza media (instaladores, vacios, grandes) → opcionales\n"
            "Nada se borra hasta que confirmes. Siempre puedes simular primero."
        )
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        path_row = QHBoxLayout()
        self.path_lbl = QLabel(str(initial_path) if initial_path else "Ninguna carpeta")
        path_row.addWidget(self.path_lbl, stretch=1)
        btn_folder = QPushButton("Elegir carpeta...")
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

        self.summary = QLabel("")
        self.summary.setObjectName("subtitle")
        layout.addWidget(self.summary)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Incluir", "Confianza", "Tamano", "Que es", "Motivo / archivo"])
        self.tree.setColumnWidth(0, 60)
        self.tree.setColumnWidth(1, 90)
        self.tree.setColumnWidth(2, 80)
        self.tree.setColumnWidth(3, 180)
        self.tree.setAlternatingRowColors(True)
        layout.addWidget(self.tree, stretch=1)

        actions = QHBoxLayout()
        self.btn_sim = QPushButton("Simular plan")
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

        self._path = initial_path
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
        self.btn_analyze.setEnabled(False)
        self.tree.clear()
        self._worker = PlanWorker(self.engine, self._path)
        self._worker.finished_ok.connect(self._on_plan)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _on_fail(self, msg: str) -> None:
        self.progress.setVisible(False)
        self.btn_analyze.setEnabled(True)
        QMessageBox.critical(self, "Error", msg)

    def _on_plan(self, plan: SmartPlan) -> None:
        self.progress.setVisible(False)
        self.btn_analyze.setEnabled(True)
        self._plan = plan
        self.tree.clear()

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
                item.what or "—",
                f"{item.reason}\n{item.path}",
            ])
            row.setData(0, Qt.ItemDataRole.UserRole, item)
            self.tree.addTopLevelItem(row)
            chk = QCheckBox()
            chk.setChecked(item.selected)
            chk.stateChanged.connect(lambda state, it=item: self._toggle(it, state))
            self.tree.setItemWidget(row, 0, chk)

        self.summary.setText(
            f"Archivos escaneados: {plan.scan_files} · "
            f"Grupos duplicados: {plan.duplicate_groups} · "
            f"Candidatos: {len(plan.items)} · "
            f"Preseleccionados: {len(plan.selected_items)} ({_fmt(plan.selected_bytes)})"
        )
        self.btn_sim.setEnabled(len(plan.items) > 0)
        self.btn_apply.setEnabled(len(plan.selected_items) > 0)
        self._refresh_apply_state()

    def _toggle(self, item, state) -> None:
        item.selected = state == Qt.CheckState.Checked.value or state == 2
        self._refresh_apply_state()

    def _refresh_apply_state(self) -> None:
        if not self._plan:
            return
        n = len(self._plan.selected_items)
        b = self._plan.selected_bytes
        self.btn_apply.setEnabled(n > 0)
        self.summary.setText(
            f"Archivos escaneados: {self._plan.scan_files} · "
            f"Candidatos: {len(self._plan.items)} · "
            f"Seleccionados: {n} ({_fmt(b)})"
        )

    def _simulate(self) -> None:
        if not self._plan:
            return
        planner = SmartPlanner(self.engine.settings)
        actions = planner.to_trash_actions(self._plan)
        if not actions:
            QMessageBox.information(self, "Simular", "No hay elementos seleccionados.")
            return
        tx = self.engine.execute_actions(actions, dry_run=True)
        QMessageBox.information(
            self,
            "Simulacion",
            f"Dry-run OK.\nTransaccion: {tx.transaction_id}\n"
            f"Se enviarian {len(actions)} archivos a la papelera "
            f"({_fmt(self._plan.selected_bytes)}).\n\nNingun archivo se ha modificado.",
        )

    def _apply(self) -> None:
        if not self._plan or not self._plan.selected_items:
            return
        reply = QMessageBox.warning(
            self,
            "Confirmar plan inteligente",
            f"Se aplicaran {len(self._plan.selected_items)} acciones (papelera y/o mover a carpetas) "
            f"({_fmt(self._plan.selected_bytes)}).\n\n"
            "Confianza alta = duplicados exactos (se mantiene 1 copia).\n"
            "Puedes recuperarlos desde la papelera del sistema.\n\n¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        planner = SmartPlanner(self.engine.settings)
        actions = planner.to_trash_actions(self._plan)
        tx = self.engine.execute_actions(actions, dry_run=False)
        ok = sum(1 for a in tx.actions if a.success)
        QMessageBox.information(
            self,
            "Plan aplicado",
            f"Completado: {ok}/{len(tx.actions)}\nTransaccion: {tx.transaction_id}",
        )
        self.accept()
