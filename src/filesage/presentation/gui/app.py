"""Punto de entrada de la GUI de FileSage."""

from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from filesage.core.config import load_settings
from filesage.core.engine import Engine
from filesage.presentation.gui.main_window import MainWindow
from filesage.utils.logging import setup_logging


def run_gui(config_path: str | None = None) -> int:
    """Lanza la interfaz grafica."""
    settings = load_settings(config_path)
    setup_logging(settings.logging)

    app = QApplication(sys.argv)
    try:
        from filesage.assets import icon_path
        ico = icon_path("filesage.ico")
        if not ico.exists():
            ico = icon_path("filesage.png")
        if ico.exists():
            app.setWindowIcon(QIcon(str(ico)))
    except Exception:
        pass
    app.setApplicationName(settings.app.name)
    app.setApplicationVersion(settings.app.version)
    app.setStyle("Fusion")  # base limpia para el QSS

    engine = Engine(settings)
    window = MainWindow(settings, engine)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(run_gui())
