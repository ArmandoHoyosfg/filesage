"""Jobs async con progreso visible, cancelacion y registro global de sesion."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from nicegui import ui

from filesage.application.progress import CancellationToken, ProgressReporter
from filesage.domain.exceptions import CancelledError
from filesage.presentation.web import session_store


class JobControls:
    """Panel de progreso siempre visible: mensaje, barra, % y cancelar."""

    def __init__(self, *, page_route: str = "") -> None:
        self.page_route = page_route
        self.token: CancellationToken | None = None
        self._running = False
        self._msg = "Listo"
        self._frac: float | None = None

        with ui.card().classes("fs-card w-full max-w-2xl p-3 gap-2") as self.root:
            with ui.row().classes("w-full items-center justify-between gap-2 no-wrap"):
                ui.label("Estado").classes("text-xs font-semibold text-[#9898b0]")
                self.cancel_btn = ui.button(
                    "Cancelar", icon="close", on_click=self.cancel
                ).props("outline dense color=negative size=sm")
                self.cancel_btn.set_visibility(False)
            self.status = ui.label("Listo — sin operacion en curso").classes(
                "text-sm text-[#ececf4]"
            )
            self.bar = ui.linear_progress(value=0, show_value=False).props(
                "color=primary rounded size=8px"
            )
            self.bar.set_visibility(False)
            with ui.row().classes("w-full items-center justify-between"):
                self.pct = ui.label("").classes("text-xs text-[#8b9cff]")
                self.hint = ui.label("").classes("text-xs text-[#6b6b80]")

        self._timer = ui.timer(0.1, self._flush, active=False)

    def _flush(self) -> None:
        if self._msg:
            self.status.set_text(self._msg)
        if self._frac is None:
            self.bar.props("indeterminate")
            self.pct.set_text("…")
        else:
            self.bar.props(remove="indeterminate")
            frac = max(0.0, min(1.0, self._frac))
            self.bar.set_value(frac)
            self.pct.set_text(f"{int(frac * 100)}%")

    def start(self, message: str = "Trabajando…") -> ProgressReporter:
        self.token = CancellationToken()
        self._running = True
        self._msg = message
        self._frac = None
        self.bar.set_visibility(True)
        self.cancel_btn.set_visibility(True)
        self.cancel_btn.set_enabled(True)
        self.bar.props("indeterminate")
        self.bar.set_value(0)
        self.status.set_text(message)
        self.pct.set_text("…")
        self.hint.set_text("Puedes cancelar o cambiar de seccion; el trabajo sigue en segundo plano.")
        self._timer.activate()
        session_store.job_start(self.page_route, message)

        def _cb(msg: str, frac: float | None) -> None:
            self._msg = msg
            self._frac = frac
            session_store.job_progress(msg, frac)

        return ProgressReporter(callback=_cb, cancel=self.token)

    def finish(self, message: str = "", *, notify: bool = True) -> None:
        self._running = False
        self._timer.deactivate()
        self.bar.set_visibility(False)
        self.cancel_btn.set_visibility(False)
        self.pct.set_text("")
        self.hint.set_text("")
        if message:
            self._msg = message
            self.status.set_text(message)
        else:
            self.status.set_text("Listo — sin operacion en curso")
        session_store.job_finish(message or "Operacion terminada")
        if notify and message:
            ui.notify(message, type="positive", position="top")

    def cancel(self) -> None:
        if self.token is not None:
            self.token.cancel()
            self._msg = "Cancelando… espera un momento"
            self.cancel_btn.set_enabled(False)
            session_store.job_progress("Cancelando…", self._frac)

    async def run(
        self,
        fn: Callable[[ProgressReporter], Any],
        *,
        start_msg: str = "Trabajando…",
        success_notice: str | None = None,
    ) -> Any:
        if session_store.job_is_running() and not self._running:
            ui.notify(
                "Ya hay una operacion en curso. Espera o cancela antes de iniciar otra.",
                type="warning",
            )
            return None
        reporter = self.start(start_msg)
        try:
            result = await asyncio.to_thread(fn, reporter)
            notice = (
                success_notice if success_notice is not None else "Operacion completada"
            )
            self.finish(notice, notify=bool(success_notice))
            if success_notice is None:
                ui.notify(notice, type="positive", position="top")
            return result
        except CancelledError:
            self.finish("Operacion cancelada", notify=False)
            ui.notify("Cancelado", type="warning", position="top")
            return None
        except Exception as e:
            self.finish(f"Error: {e}", notify=False)
            ui.notify(str(e), type="negative", position="top")
            raise
