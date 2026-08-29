"""Busqueda de archivos por nombre, extension y metadatos basicos."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
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
    QWidget,
)

from filesage.core.engine import Engine


def _fmt(n: int) -> str:
    v = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(v) < 1024:
            return f"{v:.1f} {u}"
        v /= 1024
    return f"{v:.1f} PB"


class SearchWorker(QThread):
    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(self, engine: Engine, root: Path, query: str, use_meta: bool):
        super().__init__()
        self.engine = engine
        self.root = root
        self.query = query.lower().strip()
        self.use_meta = use_meta

    def run(self) -> None:
        try:
            scan = self.engine.scan(self.root)
            results = []
            for fi in scan.files:
                name = fi.path.name.lower()
                ext = fi.path.suffix.lower()
                path_s = str(fi.path).lower()
                meta_s = ""
                what = ""
                if self.use_meta:
                    try:
                        ident = self.engine.identify_file(fi.path, deep=True)
                        what = ident.summary
                        meta_s = (ident.summary + " " + ident.mime).lower()
                    except Exception:
                        pass
                hay = f"{name} {ext} {path_s} {meta_s}"
                if self.query in hay:
                    results.append((fi, what))
            results.sort(key=lambda x: x[0].size, reverse=True)
            self.finished_ok.emit(results[:500])
        except Exception as e:
            self.failed.emit(str(e))


class SearchPage(QWidget):
    def __init__(self, engine: Engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._worker = None
        self._path = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        title = QLabel("Buscar archivos")
        title.setObjectName("title")
        layout.addWidget(title)

        sub = QLabel(
            "Busca por nombre, extension (.pdf, .mp3...) y opcionalmente metadatos "
            "(tipo, titulo de PDF, etiquetas de audio, etc.)."
        )
        sub.setObjectName("subtitle")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        row = QHBoxLayout()
        self.path_lbl = QLabel("Ninguna carpeta")
        self.path_lbl.setObjectName("subtitle")
        row.addWidget(self.path_lbl, stretch=1)
        btn = QPushButton("Carpeta...")
        btn.setObjectName("secondary")
        btn.clicked.connect(self._pick)
        row.addWidget(btn)
        layout.addLayout(row)

        qrow = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Ej: factura, .pdf, vacaciones, mp3...")
        self.query.returnPressed.connect(self._search)
        qrow.addWidget(self.query, stretch=1)
        self.chk_meta = QCheckBox("Incluir metadatos")
        self.chk_meta.setChecked(True)
        qrow.addWidget(self.chk_meta)
        self.btn_go = QPushButton("Buscar")
        self.btn_go.clicked.connect(self._search)
        qrow.addWidget(self.btn_go)
        layout.addLayout(qrow)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status = QLabel("")
        self.status.setObjectName("subtitle")
        layout.addWidget(self.status)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Archivo", "Tamano", "Que es", "Ruta"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 90)
        self.tree.setColumnWidth(2, 180)
        layout.addWidget(self.tree, stretch=1)

    def _pick(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Carpeta donde buscar")
        if path:
            self._path = Path(path)
            self.path_lbl.setText(str(self._path))

    def _search(self) -> None:
        if not self._path:
            QMessageBox.information(self, "Buscar", "Elige una carpeta.")
            return
        q = self.query.text().strip()
        if not q:
            QMessageBox.information(self, "Buscar", "Escribe algo para buscar.")
            return
        self.progress.setVisible(True)
        self.btn_go.setEnabled(False)
        self.tree.clear()
        self._worker = SearchWorker(self.engine, self._path, q, self.chk_meta.isChecked())
        self._worker.finished_ok.connect(self._on_ok)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _on_fail(self, msg: str) -> None:
        self.progress.setVisible(False)
        self.btn_go.setEnabled(True)
        QMessageBox.critical(self, "Error", msg)

    def _on_ok(self, results: list) -> None:
        self.progress.setVisible(False)
        self.btn_go.setEnabled(True)
        self.status.setText(f"{len(results)} resultado(s)" + (" (max 500)" if len(results) >= 500 else ""))
        for fi, what in results:
            self.tree.addTopLevelItem(QTreeWidgetItem([
                fi.path.name,
                _fmt(fi.size),
                what or "-",
                str(fi.path.parent),
            ]))
