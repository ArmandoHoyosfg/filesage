"""Pagina de deteccion de duplicados.

Muestra progreso, grupos de duplicados, espacio recuperable y
acciones seguras (dry-run por defecto).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from filesage.core.engine import Engine
from filesage.domain.models import DuplicateGroup


def _fmt_size(n: int) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


class DuplicateWorker(QThread):
    finished_ok = Signal(object, list)  # ScanResult, list[DuplicateGroup]
    failed = Signal(str)
    progress = Signal(str)
    progress_fraction = Signal(float)

    def __init__(self, engine: Engine, path: Path):
        super().__init__()
        self.engine = engine
        self.path = path

    def run(self) -> None:
        from filesage.application.progress import ProgressReporter, CancellationToken
        from filesage.domain.exceptions import CancelledError

        self._token = CancellationToken()
        def _cb(msg: str, frac: float | None) -> None:
            if self.isInterruptionRequested():
                self._token.cancel()
            self.progress.emit(msg)
            if frac is not None and hasattr(self, "progress_fraction"):
                self.progress_fraction.emit(frac)

        reporter = ProgressReporter(callback=_cb, cancel=self._token)
        try:
            if self.isInterruptionRequested():
                self.failed.emit("Cancelado")
                return
            scan_result, groups = self.engine.find_duplicates(self.path, progress=reporter)
            if self.isInterruptionRequested():
                self.failed.emit("Cancelado")
                return
            self.finished_ok.emit(scan_result, groups)
        except CancelledError:
            self.failed.emit("Cancelado")
        except Exception as exc:
            self.failed.emit(str(exc))

    def requestInterruption(self) -> None:
        super().requestInterruption()
        if getattr(self, "_token", None) is not None:
            self._token.cancel()


class StatCard(QFrame):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
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


class DuplicatesPage(QWidget):
    def __init__(self, engine: Engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._worker: DuplicateWorker | None = None
        self._current_path: Path | None = None
        self._groups: list[DuplicateGroup] = []
        self._last_root: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title = QLabel("Duplicados")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()

        self.path_lbl = QLabel("Ninguna carpeta seleccionada")
        self.path_lbl.setObjectName("subtitle")
        header.addWidget(self.path_lbl)

        self.btn_browse = QPushButton("Seleccionar carpeta")
        self.btn_browse.setToolTip("Carpeta donde buscar archivos iguales")
        self.btn_browse.setObjectName("secondary")
        self.btn_browse.clicked.connect(self._on_browse)
        header.addWidget(self.btn_browse)

        self.btn_scan = QPushButton("Buscar duplicados")
        self.btn_scan.setToolTip("Compara el contenido de los archivos (no solo el nombre)")
        self.btn_scan.clicked.connect(self._on_scan)
        self.btn_scan.setEnabled(False)
        header.addWidget(self.btn_scan)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("secondary")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setToolTip("Cancelar la busqueda en curso")
        self.btn_cancel.clicked.connect(self._on_cancel)
        header.addWidget(self.btn_cancel)

        layout.addLayout(header)

        # Stats
        cards = QHBoxLayout()
        cards.setSpacing(16)
        self.card_groups = StatCard("Grupos")
        self.card_files = StatCard("Archivos duplicados")
        self.card_wasted = StatCard("Espacio recuperable")
        cards.addWidget(self.card_groups)
        cards.addWidget(self.card_files)
        cards.addWidget(self.card_wasted)
        layout.addLayout(cards)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("Buscando duplicados...")
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_lbl = QLabel("")
        self.status_lbl.setObjectName("subtitle")
        layout.addWidget(self.status_lbl)

        # Arbol de grupos
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Archivo / Grupo", "Tamano", "Fecha"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setColumnWidth(0, 520)
        self.tree.setColumnWidth(1, 100)
        layout.addWidget(self.tree, stretch=1)

        # Acciones (dry-run por ahora)
        actions = QHBoxLayout()
        self.btn_select_smart = QPushButton("Seleccionar inteligentemente (mantener mas reciente)")
        self.btn_select_smart.setObjectName("secondary")
        self.btn_select_smart.setEnabled(False)
        self.btn_select_smart.clicked.connect(self._select_smart)
        actions.addWidget(self.btn_select_smart)

        self.btn_dry_run = QPushButton("Simular limpieza (dry-run)")
        self.btn_dry_run.setToolTip("No borra nada: solo muestra que se enviaria a la papelera")
        self.btn_dry_run.setEnabled(False)
        self.btn_dry_run.clicked.connect(self._dry_run)
        actions.addWidget(self.btn_dry_run)

        self.btn_clean = QPushButton("Limpiar (enviar a papelera)")
        self.btn_clean.setToolTip("Accion real: envia duplicados a la papelera (puedes recuperarlos)")
        self.btn_clean.setObjectName("danger")
        self.btn_clean.setEnabled(False)
        self.btn_clean.clicked.connect(self._clean_real)
        actions.addWidget(self.btn_clean)

        self.btn_export = QPushButton("Exportar")
        self.btn_export.setObjectName("secondary")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._on_export)
        actions.addWidget(self.btn_export)

        self.btn_move = QPushButton("Mover seleccionados...")
        self.btn_move.setObjectName("secondary")
        self.btn_move.setEnabled(False)
        self.btn_move.clicked.connect(self._on_move)
        actions.addWidget(self.btn_move)

        actions.addStretch()
        layout.addLayout(actions)

    def _on_browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta")
        if path:
            self._current_path = Path(path)
            self.path_lbl.setText(str(self._current_path))
            self.btn_scan.setEnabled(True)

    def _on_scan(self) -> None:
        if not self._current_path:
            return
        if self._worker and self._worker.isRunning():
            return

        self.btn_scan.setEnabled(False)
        self.btn_browse.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.progress.setFormat("Buscando duplicados...")
        self.status_lbl.setText("Buscando duplicados...")
        w = self.window()
        if hasattr(w, "set_status"):
            w.set_status(f"Buscando duplicados: {self._current_path}")
        self.tree.clear()
        self._groups = []

        self._worker = DuplicateWorker(self.engine, self._current_path)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.progress.connect(self.status_lbl.setText)
        self._worker.progress_fraction.connect(self._on_progress_fraction)
        self._worker.start()

    def _on_finished(self, scan_result, groups: list) -> None:
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)
        self.progress.setFormat("Buscando duplicados...")
        self.btn_scan.setEnabled(True)
        self.btn_browse.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self._groups = groups
        self._last_root = scan_result.root

        total_dup_files = sum(g.count for g in groups)
        total_wasted = sum(g.wasted_size for g in groups)

        self.card_groups.set_value(str(len(groups)))
        self.card_files.set_value(str(total_dup_files))
        self.card_wasted.set_value(_fmt_size(total_wasted))
        self.status_lbl.setText(f"Encontrados {len(groups)} grupos · {scan_result.duration_seconds:.2f} s")

        self.tree.clear()
        for i, group in enumerate(groups):
            parent = QTreeWidgetItem([
                f"Grupo {i+1}  ({group.count} archivos, recuperable {_fmt_size(group.wasted_size)})",
                _fmt_size(group.total_size),
                "",
            ])
            parent.setData(0, Qt.ItemDataRole.UserRole, group)
            for fi in group.files:
                try:
                    rel = str(fi.path.relative_to(scan_result.root))
                except ValueError:
                    rel = str(fi.path)
                child = QTreeWidgetItem([
                    rel,
                    _fmt_size(fi.size),
                    fi.mtime_dt.strftime("%Y-%m-%d %H:%M"),
                ])
                child.setData(0, Qt.ItemDataRole.UserRole, fi)
                parent.addChild(child)
            self.tree.addTopLevelItem(parent)

        self.btn_select_smart.setEnabled(len(groups) > 0)
        self.btn_dry_run.setEnabled(len(groups) > 0)
        self.btn_clean.setEnabled(len(groups) > 0)
        self.btn_export.setEnabled(len(groups) > 0)
        self.btn_move.setEnabled(len(groups) > 0)

    def _on_failed(self, message: str) -> None:
        self.progress.setVisible(False)
        self.btn_scan.setEnabled(True)
        self.btn_browse.setEnabled(True)
        if hasattr(self, "btn_cancel"):
            self.btn_cancel.setEnabled(False)
        if message == "Cancelado":
            self.status_lbl.setText("Busqueda cancelada")
            self.progress.setVisible(False)
            return
        self.status_lbl.setText(f"Error: {message}")
        QMessageBox.critical(self, "Error al buscar duplicados", message)
        QMessageBox.critical(self, "Error", message)

    def _select_smart(self) -> None:
        """Marca visualmente (expandir) manteniendo el mas reciente de cada grupo."""
        # Por ahora solo expande y deja el primero (ya ordenado por mtime desc)
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item.setExpanded(True)
        self.status_lbl.setText("Seleccion inteligente: se mantiene el archivo mas reciente de cada grupo (revisa antes de limpiar).")

    def _dry_run(self) -> None:
        if not self._groups:
            return
        plans = self.engine.plan_trash_duplicates(self._groups, keep_newest=True)
        if not plans:
            QMessageBox.information(self, "Dry-run", "No hay acciones que simular.")
            return
        tx = self.engine.execute_actions(plans, dry_run=True)
        total_wasted = sum(g.wasted_size for g in self._groups)
        QMessageBox.information(
            self,
            "Simulacion (dry-run)",
            f"Se enviarian a la papelera {len(plans)} archivos.\n"
            f"Espacio recuperable aproximado: {_fmt_size(total_wasted)}.\n\n"
            f"Transaccion: {tx.transaction_id}\n"
            "Ningun archivo se ha modificado.",
        )

    def _clean_real(self) -> None:
        if not self._groups:
            return
        plans = self.engine.plan_trash_duplicates(self._groups, keep_newest=True)
        if not plans:
            QMessageBox.information(self, "Limpieza", "No hay archivos que limpiar.")
            return

        total_wasted = sum(g.wasted_size for g in self._groups)
        reply = QMessageBox.warning(
            self,
            "Confirmar limpieza REAL",
            f"Se enviaran a la PAPELERA {len(plans)} archivos duplicados.\n"
            f"Espacio recuperable: {_fmt_size(total_wasted)}.\n\n"
            "Se mantendra el archivo mas reciente de cada grupo.\n"
            "Esta accion NO es un dry-run.\n\n"
            "Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        tx = self.engine.execute_actions(plans, dry_run=False)
        ok = sum(1 for a in tx.actions if a.success)
        QMessageBox.information(
            self,
            "Limpieza completada",
            f"Transaccion {tx.transaction_id}\n"
            f"Exitosas: {ok}/{len(tx.actions)}\n"
            "Revisa el Historial para mas detalles.",
        )
        self._groups = []
        self.tree.clear()
        self.btn_dry_run.setEnabled(False)
        self.btn_clean.setEnabled(False)
        if hasattr(self, "btn_export"):
            self.btn_export.setEnabled(False)
        if hasattr(self, "btn_move"):
            self.btn_move.setEnabled(False)
        if hasattr(self, "btn_select_smart"):
            self.btn_select_smart.setEnabled(False)
        self.card_groups.set_value("0")
        self.card_files.set_value("0")
        self.card_wasted.set_value("—")

    def _on_export(self) -> None:
        if not self._groups or not self._last_root:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar duplicados", "filesage_duplicates.json",
            "JSON (*.json);;CSV (*.csv)"
        )
        if not path:
            return
        fmt = "csv" if path.lower().endswith(".csv") else "json"
        try:
            out = self.engine.export_duplicates(self._groups, self._last_root, Path(path), fmt=fmt)
            QMessageBox.information(self, "Exportar", f"Reporte guardado en:\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_move(self) -> None:
        if not self._groups:
            return
        dest = QFileDialog.getExistingDirectory(self, "Carpeta destino para mover duplicados")
        if not dest:
            return
        dest_path = Path(dest)
        from filesage.domain.models import ActionRecord, ActionType
        
        from datetime import datetime

        plans = self.engine.plan_trash_duplicates(self._groups, keep_newest=True)
        # Convert TRASH plans to MOVE
        move_plans = []
        for p in plans:
            target = dest_path / p.source.name
            # evitar colision simple
            if target.exists():
                target = dest_path / f"{p.source.stem}_dup{p.source.suffix}"
            move_plans.append(
                ActionRecord(
                    action_id=self.engine.new_action_id(),
                    action_type=ActionType.MOVE,
                    source=p.source,
                    destination=target,
                    timestamp=datetime.now(),
                    success=False,
                    message="",
                    dry_run=True,
                    metadata=p.metadata,
                )
            )

        reply = QMessageBox.question(
            self,
            "Mover duplicados",
            f"Se moveran {len(move_plans)} archivos a:\n{dest_path}\n\n"
            "Primero se simulares (dry-run). Continuar?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        tx = self.engine.execute_actions(move_plans, dry_run=True)
        QMessageBox.information(
            self, "Dry-run movimiento",
            f"Simulacion OK ({len(tx.actions)} acciones).\n"
            "Para ejecutar de verdad, usa Limpiar o implementa confirmacion adicional."
        )
        # Real move with second confirm
        reply2 = QMessageBox.warning(
            self,
            "Confirmar movimiento REAL",
            f"Mover {len(move_plans)} archivos a {dest_path}?\nEsta accion NO es dry-run.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply2 == QMessageBox.StandardButton.Yes:
            tx2 = self.engine.execute_actions(move_plans, dry_run=False)
            ok = sum(1 for a in tx2.actions if a.success)
            QMessageBox.information(self, "Movimiento", f"Completado: {ok}/{len(tx2.actions)}")



    def _on_progress_fraction(self, frac: float) -> None:
        if frac < 0:
            self.progress.setRange(0, 0)
            return
        self.progress.setRange(0, 100)
        self.progress.setValue(int(frac * 100))
        self.progress.setFormat(f"{int(frac * 100)}%")

    def _on_cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            self.status_lbl.setText("Cancelando...")
            if hasattr(self, "btn_cancel"):
                self.btn_cancel.setEnabled(False)
