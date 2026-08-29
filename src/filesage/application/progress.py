"""Progreso y cancelacion — parte del contrato de aplicacion (Etapas A/B).

Generico: no depende de Qt ni de web. Cualquier UI puede conectar callbacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


ProgressCallback = Callable[[str, float | None], None]
# message, fraction 0.0–1.0 or None if unknown


@dataclass
class CancellationToken:
    """Señal de cancelacion compartida entre UI y motor."""

    _cancelled: bool = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def raise_if_cancelled(self) -> None:
        if self._cancelled:
            from filesage.domain.exceptions import CancelledError
            raise CancelledError("Operacion cancelada por el usuario")


@dataclass
class ProgressReporter:
    """Emite mensajes y fraccion de avance de forma segura."""

    callback: ProgressCallback | None = None
    cancel: CancellationToken | None = field(default_factory=CancellationToken)
    _last_message: str = ""

    def report(self, message: str, fraction: float | None = None) -> None:
        self._last_message = message
        if self.cancel is not None:
            self.cancel.raise_if_cancelled()
        if self.callback is not None:
            try:
                self.callback(message, fraction)
            except Exception:
                pass

    def check(self) -> None:
        if self.cancel is not None:
            self.cancel.raise_if_cancelled()
