"""Ventana principal de FileSage (PySide6)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from filesage.core.config import Settings
from filesage.core.engine import Engine
from filesage.presentation.gui.pages.dashboard_page import DashboardPage
from filesage.presentation.gui.pages.duplicates_page import DuplicatesPage
from filesage.presentation.gui.pages.history_page import HistoryPage
from filesage.presentation.gui.pages.settings_page import SettingsPage
from filesage.presentation.gui.pages.help_page import HelpPage
from filesage.presentation.gui.components.onboarding import OnboardingDialog
from filesage.presentation.gui.components.wizard import CleanupWizard
from filesage.presentation.gui.components.smart_plan_dialog import SmartPlanDialog
from filesage.presentation.gui.user_mode import UserMode, load_user_mode, save_user_mode
from filesage.presentation.gui.pages.space_page import SpacePage
from filesage.presentation.gui.themes import DARK_QSS
from filesage.presentation.gui.icons import icon, try_set_button_icon
from filesage.presentation.gui.animations import fade_in


class SidebarButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(44)


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, engine: Engine, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.engine = engine
        self.user_mode = load_user_mode()

        self.setWindowTitle(f"{settings.app.name} v{settings.app.version}")
        self.setMinimumSize(720, 520)
        self.resize(1280, 800)
        self.setStyleSheet(DARK_QSS)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = self._build_sidebar()
        root_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        from PySide6.QtWidgets import QSizePolicy
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root_layout.addWidget(self.stack, stretch=1)

        self.pages: dict[str, QWidget] = {}
        self._nav_buttons: dict[str, SidebarButton] = {}

        self._build_pages()
        self._setup_shortcuts()

    def _build_sidebar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sidebar")
        frame.setMinimumWidth(180)
        frame.setMaximumWidth(240)
        frame.setFixedWidth(200)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 20, 12, 20)
        layout.setSpacing(6)

        title = QLabel("FileSage")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Gestion inteligente")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(24)

        self.btn_dashboard = SidebarButton("  ⌂  Dashboard")
        self.btn_space = SidebarButton("  ▤  Espacio")
        self.btn_duplicates = SidebarButton("  ⧉  Duplicados")
        self.btn_history = SidebarButton("  🕘  Historial")
        self.btn_settings = SidebarButton("  ⚙  Configuracion")
        self.btn_help = SidebarButton("  ?  Ayuda")

        for btn in (
            self.btn_dashboard,
            self.btn_space,
            self.btn_duplicates,
            self.btn_history,
            self.btn_settings,
            self.btn_help,
        ):
            layout.addWidget(btn)

        layout.addStretch()

        self.btn_mode = SidebarButton("  ◉  Modo: Simple")
        self.btn_mode.setCheckable(False)
        self.btn_mode.setToolTip("Alternar entre modo Simple (guiado) y Experto (todas las opciones)")
        self.btn_mode.clicked.connect(self._toggle_mode)
        layout.addWidget(self.btn_mode)

        ver = QLabel(f"v{self.settings.app.version}")
        ver.setObjectName("subtitle")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver)

        self.btn_dashboard.clicked.connect(lambda: self._navigate("dashboard"))
        self.btn_space.clicked.connect(lambda: self._navigate("space"))
        self.btn_duplicates.clicked.connect(lambda: self._navigate("duplicates"))
        self.btn_history.clicked.connect(lambda: self._navigate("history"))
        self.btn_settings.clicked.connect(lambda: self._navigate("settings"))
        self.btn_help.clicked.connect(lambda: self._navigate("help"))

        
        try_set_button_icon(self.btn_dashboard, "dashboard")
        try_set_button_icon(self.btn_space, "space")
        try_set_button_icon(self.btn_duplicates, "duplicates")
        try_set_button_icon(self.btn_history, "history")
        try_set_button_icon(self.btn_settings, "settings")
        try_set_button_icon(self.btn_help, "help")
        try_set_button_icon(self.btn_mode, "mode")
        self.btn_dashboard.setToolTip("Resumen y accesos rapidos")
        self.btn_space.setToolTip("Ver que ocupa mas espacio")
        self.btn_duplicates.setToolTip("Encontrar y limpiar archivos iguales")
        self.btn_history.setToolTip("Transacciones y posible rollback")
        self.btn_settings.setToolTip("Opciones de seguridad y escaneo")
        self.btn_help.setToolTip("Guia para principiantes y avanzados")

        self._nav_buttons = {
            "dashboard": self.btn_dashboard,
            "space": self.btn_space,
            "duplicates": self.btn_duplicates,
            "history": self.btn_history,
            "settings": self.btn_settings,
            "help": self.btn_help,
        }
        return frame

    def _build_pages(self) -> None:
        # Dashboard real
        dash = DashboardPage(self.settings, self.engine, self._navigate, start_wizard=self._start_wizard, start_smart=self._start_smart_plan)
        self.pages["dashboard"] = dash
        self.stack.addWidget(dash)

        # Space
        space = SpacePage(self.engine)
        self.pages["space"] = space
        self.stack.addWidget(space)

        # Duplicates
        dupes = DuplicatesPage(self.engine)
        self.pages["duplicates"] = dupes
        self.stack.addWidget(dupes)

        # History real
        hist = HistoryPage(self.engine)
        self.pages["history"] = hist
        self.stack.addWidget(hist)

        # Settings real
        settings_page = SettingsPage(self.settings, self.engine)
        self.pages["settings"] = settings_page
        self.stack.addWidget(settings_page)

        # Help
        help_page = HelpPage()
        self.pages["help"] = help_page
        self.stack.addWidget(help_page)

        self._navigate("dashboard")
        self._apply_user_mode()

    def register_page(self, key: str, widget: QWidget) -> None:
        if key in self.pages:
            old = self.pages[key]
            idx = self.stack.indexOf(old)
            self.stack.removeWidget(old)
            old.deleteLater()
            self.stack.insertWidget(idx, widget)
        else:
            self.stack.addWidget(widget)
        self.pages[key] = widget

    def _navigate(self, key: str) -> None:
        if key not in self.pages:
            return
        self.stack.setCurrentWidget(self.pages[key])
        try:
            fade_in(self.pages[key], duration=220)
        except Exception:
            pass
        for k, btn in self._nav_buttons.items():
            btn.setChecked(k == key)

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_onboarding_shown", False):
            self._onboarding_shown = True
            # Solo mostrar si no hay flag de usuario (simple: siempre en primeras pruebas)
            # En produccion se puede persistir en config
            from pathlib import Path
            flag = Path.home() / ".filesage" / "onboarding_done"
            if not flag.exists():
                dlg = OnboardingDialog(self)
                dlg.exec()
                if dlg.dont_show_again:
                    flag.parent.mkdir(parents=True, exist_ok=True)
                    flag.write_text("1", encoding="utf-8")

    def _start_wizard(self) -> None:
        dlg = CleanupWizard(self.engine, self)
        dlg.exec()

    def _toggle_mode(self) -> None:
        order = [UserMode.SIMPLE, UserMode.SMART, UserMode.EXPERT]
        idx = order.index(self.user_mode) if self.user_mode in order else 0
        self.user_mode = order[(idx + 1) % len(order)]
        save_user_mode(self.user_mode)
        self._apply_user_mode()

    def _apply_user_mode(self) -> None:
        labels = {
            UserMode.SIMPLE: "  Modo: Simple",
            UserMode.SMART: "  Modo: Smart",
            UserMode.EXPERT: "  Modo: Experto",
        }
        self.btn_mode.setText(labels.get(self.user_mode, "  Modo: Simple"))
        expert = self.user_mode == UserMode.EXPERT
        # En modo simple, historial y config siguen accesibles pero se puede atenuar
        # Ocultar botones avanzados en paginas si existen
        space = self.pages.get("space")
        dupes = self.pages.get("duplicates")
        if space is not None and hasattr(space, "btn_export"):
            space.btn_export.setVisible(expert)
        if dupes is not None:
            for name in ("btn_export", "btn_move", "btn_select_smart"):
                btn = getattr(dupes, name, None)
                if btn is not None:
                    btn.setVisible(expert)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+1"), self, lambda: self._navigate("dashboard"))
        QShortcut(QKeySequence("Ctrl+2"), self, lambda: self._navigate("space"))
        QShortcut(QKeySequence("Ctrl+3"), self, lambda: self._navigate("duplicates"))
        QShortcut(QKeySequence("Ctrl+4"), self, lambda: self._navigate("history"))
        QShortcut(QKeySequence("Ctrl+5"), self, lambda: self._navigate("settings"))
        QShortcut(QKeySequence("Ctrl+H"), self, lambda: self._navigate("help"))
        QShortcut(QKeySequence("Ctrl+W"), self, self._start_wizard)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self._start_smart_plan)
        QShortcut(QKeySequence("F1"), self, lambda: self._navigate("help"))

    def _start_smart_plan(self) -> None:
        dlg = SmartPlanDialog(self.engine, self)
        dlg.exec()
