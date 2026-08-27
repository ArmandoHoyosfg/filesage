"""Dashboard principal de FileSage — layout responsive."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from filesage.core.config import Settings
from filesage.core.engine import Engine
from filesage.presentation.gui.icons import try_set_button_icon
from filesage.presentation.gui.animations import fade_in


class QuickCard(QFrame):
    """Tarjeta de acceso rapido con icono, titulo, descripcion y boton."""

    def __init__(
        self,
        icon: str,
        title: str,
        description: str,
        button_text: str,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("quickCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumWidth(180)
        self.setMinimumHeight(140)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 26px; background: transparent; border: none;")
        icon_lbl.setFixedWidth(36)
        header.addWidget(icon_lbl)

        t = QLabel(title)
        t.setWordWrap(True)
        t.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #cdd6f4; "
            "background: transparent; border: none;"
        )
        header.addWidget(t, stretch=1)
        layout.addLayout(header)

        d = QLabel(description)
        d.setWordWrap(True)
        d.setStyleSheet(
            "font-size: 12px; color: #a6adc8; background: transparent; border: none;"
        )
        d.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        layout.addWidget(d, stretch=1)

        self.button = QPushButton(button_text)
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setMinimumHeight(34)
        layout.addWidget(self.button)


class DashboardPage(QWidget):
    def __init__(
        self,
        settings: Settings,
        engine: Engine,
        navigate_callback,
        start_wizard=None,
        start_smart=None,
        parent=None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.engine = engine
        self._navigate = navigate_callback
        self._start_wizard = start_wizard
        self._start_smart = start_smart
        self._card_widgets: list[QuickCard] = []
        self._cols = -1

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        outer.addWidget(scroll)

        self._content = QWidget()
        self._content.setObjectName("dashboardContent")
        scroll.setWidget(self._content)

        self._main = QVBoxLayout(self._content)
        self._main.setContentsMargins(28, 24, 28, 24)
        self._main.setSpacing(16)

        title = QLabel(f"Bienvenido a {settings.app.name}")
        title.setObjectName("title")
        self._main.addWidget(title)

        sub = QLabel(
            "Herramienta modular y segura para analizar espacio, encontrar duplicados "
            "y gestionar archivos sin riesgos."
        )
        sub.setObjectName("subtitle")
        sub.setWordWrap(True)
        self._main.addWidget(sub)

        safety = QLabel(
            f"✓ Modo seguro activo  ·  Dry-run: "
            f"{'Sí' if settings.app.dry_run_default else 'No'}  ·  "
            f"Papelera: {'Sí' if settings.actions.use_trash else 'No'}"
        )
        safety.setObjectName("subtitle")
        safety.setStyleSheet("color: #a6e3a1;")
        safety.setWordWrap(True)
        self._main.addWidget(safety)

        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 8, 0, 8)
        self._grid.setSpacing(14)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._main.addWidget(self._grid_host)

        cards_def = [
            ("▤", "Analizar espacio",
             "Descubre que carpetas y archivos ocupan mas espacio en tu disco.",
             "Ir a Espacio", lambda: self._navigate("space")),
            ("⧉", "Buscar duplicados",
             "Encuentra archivos identicos y recupera espacio de forma segura.",
             "Ir a Duplicados", lambda: self._navigate("duplicates")),
            ("🕘", "Historial",
             "Revisa las acciones realizadas y restaura movimientos si hace falta.",
             "Ver historial", lambda: self._navigate("history")),
            ("🧙", "Asistente de limpieza",
             "Te guia paso a paso para buscar duplicados y limpiar con seguridad.",
             "Iniciar asistente", self._start_wizard),
            ("✦", "Plan inteligente",
             "Propone que limpiar (duplicados seguros preseleccionados). Tu confirmas.",
             "Abrir plan Smart", self._start_smart),
        ]

        for icon, title_t, desc, btn, cb in cards_def:
            card = QuickCard(icon, title_t, desc, btn)
            if cb:
                card.button.clicked.connect(cb)
            self._card_widgets.append(card)

        self._relayout_cards()

        # Iconos en botones de tarjetas
        icon_names = ["space", "duplicates", "history", "wizard", "smart"]
        for card, iname in zip(self._card_widgets, icon_names):
            try_set_button_icon(card.button, iname, on_accent=True)

        insight_box = QFrame()
        insight_box.setObjectName("quickCard")
        insight_layout = QVBoxLayout(insight_box)
        insight_layout.setContentsMargins(16, 16, 16, 16)
        insight_layout.setSpacing(10)

        insight_title = QLabel("✦  Sugerencias inteligentes (local, sin nube)")
        insight_title.setStyleSheet(
            "font-size: 15px; font-weight: 600; color: #cdd6f4; "
            "background: transparent; border: none;"
        )
        insight_layout.addWidget(insight_title)

        self.insights_box = QTextEdit()
        self.insights_box.setReadOnly(True)
        self.insights_box.setMinimumHeight(100)
        self.insights_box.setMaximumHeight(180)
        self.insights_box.setPlaceholderText(
            "Elige una carpeta y pulsa Analizar sugerencias. "
            "FileSage detectara archivos grandes, antiguos, instaladores, vacios y rutas tipo cache."
        )
        self.insights_box.setStyleSheet(
            "QTextEdit { background-color: #1e1e2e; border: 1px solid #45475a; "
            "border-radius: 8px; padding: 10px; color: #cdd6f4; }"
        )
        insight_layout.addWidget(self.insights_box)

        self.btn_insights = QPushButton("Analizar sugerencias...")
        self.btn_insights.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_insights.setFixedWidth(200)
        self.btn_insights.clicked.connect(self._run_insights)
        insight_layout.addWidget(self.btn_insights, alignment=Qt.AlignmentFlag.AlignLeft)

        self._main.addWidget(insight_box)

        tip = QLabel(
            "Principiante: empieza por Descargas o Documentos y usa siempre Simular antes de limpiar.\n"
            "Avanzado: ajusta exclusiones y tamano minimo en Configuracion; exporta reportes JSON/CSV.\n"
            "Ayuda completa: seccion Ayuda en el menu lateral (F1)."
        )
        tip.setObjectName("subtitle")
        tip.setWordWrap(True)
        tip.setStyleSheet(
            "color: #a6adc8; padding: 12px 14px; background-color: #313244; "
            "border-radius: 8px; border: 1px solid #45475a;"
        )
        self._main.addWidget(tip)
        self._main.addStretch(1)

        QTimer.singleShot(50, self._relayout_cards)
        QTimer.singleShot(80, lambda: fade_in(self._content, duration=280))

    def _relayout_cards(self) -> None:
        width = max(self._content.width(), self.width(), 400)
        if width < 720:
            cols = 1
        elif width < 1050:
            cols = 2
        else:
            cols = 3

        if cols == self._cols:
            return
        self._cols = cols

        while self._grid.count():
            self._grid.takeAt(0)

        for i, card in enumerate(self._card_widgets):
            row, col = divmod(i, cols)
            self._grid.addWidget(card, row, col)
            self._grid.setColumnStretch(col, 1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout_cards()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._relayout_cards)

    def _run_insights(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Carpeta para sugerencias inteligentes")
        if not path:
            return
        from pathlib import Path

        try:
            scan = self.engine.scan(Path(path))
            insights = self.engine.smart_insights(scan)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        if not insights:
            self.insights_box.setPlainText("No hay sugerencias destacadas en esta carpeta.")
            return
        lines = []
        for i in insights:
            size = i.potential_bytes
            if size >= 1024 * 1024 * 1024:
                sz = f"{size / (1024**3):.1f} GB"
            elif size >= 1024 * 1024:
                sz = f"{size / (1024**2):.1f} MB"
            else:
                sz = f"{size / 1024:.1f} KB" if size else "—"
            lines.append(f"[{i.severity.upper()}] {i.title}  (~{sz})")
            lines.append(f"  {i.detail}")
            for pth in i.paths[:3]:
                lines.append(f"  · {pth}")
            if len(i.paths) > 3:
                lines.append(f"  · ... y {len(i.paths) - 3} mas")
            lines.append("")
        self.insights_box.setPlainText("\n".join(lines))
