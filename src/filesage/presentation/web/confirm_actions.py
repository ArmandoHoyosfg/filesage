"""Dialogos de confirmacion con vista previa (Fase A2)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path

from nicegui import ui


async def confirm_trash_preview(
    paths: Sequence[Path | str],
    *,
    title: str = "Enviar a papelera",
    confirm_word: str = "OK",
    on_confirm: Callable[[], Awaitable[None]] | None = None,
) -> None:
    """Muestra lista de archivos y pide palabra de confirmacion."""
    items = [str(p) for p in paths]
    if not items:
        ui.notify("Nada que procesar", type="warning")
        return

    with ui.dialog() as dialog, ui.card().classes("fs-card p-4 max-w-lg w-full"):
        ui.label(title).classes("font-bold text-lg")
        ui.label(
            f"{len(items)} elemento(s). Revisa la lista. "
            f"Escribe {confirm_word} para confirmar."
        ).classes("text-sm text-[#9898b0]")
        with ui.column().classes("w-full max-h-60 overflow-auto gap-1 my-2 p-2 rounded bg-black/20"):
            for p in items[:80]:
                ui.label(p).classes("text-xs break-all font-mono")
            if len(items) > 80:
                ui.label(f"… y {len(items) - 80} mas").classes("text-xs text-[#9898b0]")
        conf = ui.input(f"Escribe {confirm_word}").classes("w-full")
        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Cancelar", on_click=dialog.close).props("flat")

            async def go() -> None:
                if (conf.value or "").strip().upper() != confirm_word.upper():
                    ui.notify(f"Escribe {confirm_word}", type="warning")
                    return
                dialog.close()
                if on_confirm:
                    await on_confirm()

            ui.button("Confirmar", on_click=go).props("color=negative unelevated")
    dialog.open()
