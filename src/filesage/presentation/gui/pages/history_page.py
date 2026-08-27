"""Pagina de Historial de transacciones."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from filesage.core.engine import Engine
from filesage.domain.models import Transaction


def _fmt_size(n: int) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


class HistoryPage(QWidget):
    def __init__(self, engine: Engine, parent=None):
        super().__init__(parent)
        self.engine = engine

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Historial de transacciones")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()

        self.btn_refresh = QPushButton("Actualizar")
        self.btn_refresh.setObjectName("secondary")
        self.btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.btn_refresh)
        layout.addLayout(header)

        self.info = QLabel("Las transacciones dry-run y reales se registran aqui.")
        self.info.setObjectName("subtitle")
        layout.addWidget(self.info)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Transaccion / Accion", "Estado", "Fecha"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setColumnWidth(0, 520)
        layout.addWidget(self.tree, stretch=1)

        actions = QHBoxLayout()
        self.btn_rollback = QPushButton("Intentar rollback de la seleccionada")
        self.btn_rollback.setObjectName("secondary")
        self.btn_rollback.clicked.connect(self._on_rollback)
        actions.addWidget(self.btn_rollback)
        actions.addStretch()
        layout.addLayout(actions)

        self.refresh()

    def refresh(self) -> None:
        self.tree.clear()
        try:
            txs = self.engine.list_transactions(limit=40)
        except Exception as exc:
            self.info.setText(f"Error al cargar historial: {exc}")
            return

        self.info.setText(f"{len(txs)} transacciones recientes")

        for tx in txs:
            mode = "DRY-RUN" if tx.dry_run else "REAL"
            ok = sum(1 for a in tx.actions if a.success)
            parent = QTreeWidgetItem([
                f"{tx.transaction_id}  [{mode}]  {ok}/{len(tx.actions)} OK",
                "OK" if ok == len(tx.actions) else "Parcial",
                tx.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            ])
            parent.setData(0, Qt.ItemDataRole.UserRole, tx)
            for a in tx.actions:
                child = QTreeWidgetItem([
                    f"{a.action_type.value.upper()}  {a.source.name}",
                    "OK" if a.success else "ERROR",
                    a.timestamp.strftime("%H:%M:%S"),
                ])
                child.setToolTip(0, a.message)
                parent.addChild(child)
            self.tree.addTopLevelItem(parent)

    def _on_rollback(self) -> None:
        item = self.tree.currentItem()
        if not item:
            QMessageBox.information(self, "Rollback", "Selecciona una transaccion.")
            return
        # Subir al top-level si es hijo
        while item.parent():
            item = item.parent()
        tx: Transaction | None = item.data(0, Qt.ItemDataRole.UserRole)
        if not tx:
            return
        if tx.dry_run:
            QMessageBox.information(self, "Rollback", "Las transacciones dry-run no requieren rollback.")
            return

        reply = QMessageBox.question(
            self,
            "Confirmar rollback",
            f"Se intentara revertir la transaccion {tx.transaction_id}.\n"
            "Solo los MOVEs se pueden revertir automaticamente.\n"
            "Los envios a papelera deben restaurarse manualmente desde la papelera del sistema.\n\n"
            "Continuar?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self.engine.rollback(tx)
            QMessageBox.information(
                self,
                "Rollback",
                f"Rollback ejecutado. Acciones: {len(result.actions)}",
            )
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
