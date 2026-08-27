"""Dialogo de bienvenida / onboarding para primera ejecucion."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)


class OnboardingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bienvenido a FileSage")
        self.setMinimumWidth(480)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("Bienvenido a FileSage")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        body = QLabel(
            "Esta herramienta te ayuda a:\n\n"
            "• Ver que archivos y carpetas ocupan mas espacio\n"
            "• Encontrar archivos duplicados\n"
            "• Limpiar de forma segura (primero simula, luego actua)\n\n"
            "Recomendacion para empezar:\n"
            "1. Ve a Espacio o Duplicados\n"
            "2. Elige una carpeta como Descargas\n"
            "3. Usa siempre Simular (dry-run) antes de limpiar\n\n"
            "Puedes consultar la seccion Ayuda en cualquier momento."
        )
        body.setWordWrap(True)
        body.setObjectName("subtitle")
        layout.addWidget(body)

        self.chk_dont = QCheckBox("No volver a mostrar este mensaje")
        layout.addWidget(self.chk_dont)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    @property
    def dont_show_again(self) -> bool:
        return self.chk_dont.isChecked()
