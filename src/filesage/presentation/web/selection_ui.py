"""UI de seleccion compartida entre herramientas."""

from __future__ import annotations

from pathlib import Path

from nicegui import ui

from filesage.presentation.web import session_store


def selection_banner(*, tool: str = "") -> None:
    """Muestra si hay archivos enviados desde Buscar u otra seccion."""
    sel = session_store.get_selection()
    paths = sel.get("paths") or []
    if not paths:
        return
    with ui.card().classes("fs-card w-full max-w-2xl p-3 border border-primary/30"):
        ui.label(
            f"Seleccion compartida ({sel.get('source') or 'otra herramienta'}): "
            f"{len(paths)} archivos"
        ).classes("font-medium text-sm")
        ui.label(sel.get("label") or "").classes("text-xs text-[#9898b0]")
        parents = {str(Path(p).parent) for p in paths[:50]}
        if len(parents) == 1:
            ui.label(f"Carpeta comun: {next(iter(parents))}").classes(
                "text-xs text-primary break-all"
            )
        with ui.row().classes("gap-2 mt-1"):
            ui.button(
                "Limpiar seleccion",
                on_click=lambda: (session_store.clear_selection(), ui.notify("Seleccion limpia")),
            ).props("flat dense")
