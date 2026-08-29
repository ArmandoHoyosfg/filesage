"""Capa de aplicacion: contrato estable entre el nucleo y cualquier UI.

Las UIs (Qt, CLI, web) solo deben depender de esta capa y de domain/models
(mas core.Engine como implementacion del contrato).
No importar infrastructure/ ni services/ desde presentation/.
"""

from filesage.application.api import ApplicationAPI
from filesage.application.progress import CancellationToken, ProgressReporter

__all__ = [
    "ApplicationAPI",
    "CancellationToken",
    "ProgressReporter",
]
