"""Selector de carpetas (nativo en ventana app + fallback manual)."""

from __future__ import annotations

from pathlib import Path

from nicegui import ui

from filesage.presentation.web.context import get_workspace, set_workspace
from filesage.core.workspace_safety import assess_workspace


async def pick_folder_dialog(start: str | None = None) -> str | None:
    """Abre dialogo nativo de carpeta si hay WebView; si no, None."""
    try:
        from nicegui import app
        import webview

        if app.native.main_window is None:
            return None

        dialog_type = getattr(
            getattr(webview, "FileDialog", object),
            "FOLDER",
            getattr(webview, "FOLDER_DIALOG", None),
        )
        kwargs = {}
        if dialog_type is not None:
            kwargs["dialog_type"] = dialog_type
        if start:
            kwargs["directory"] = start
        result = await app.native.main_window.create_file_dialog(**kwargs)
        if not result:
            return None
        if isinstance(result, (list, tuple)):
            return str(result[0]) if result else None
        return str(result)
    except Exception:
        return None


def folder_field(
    *,
    label: str = "Carpeta",
    value: str | None = None,
    use_workspace_toggle: bool = True,
    on_change=None,
):
    """Campo de carpeta + Examinar + opcional 'Usar directorio de trabajo'.

    Devuelve un objeto simple con .path_value() y widgets.
    """
    use_ws_default = value is None
    initial = value if value is not None else str(get_workspace())
    state = {"use_ws": use_ws_default, "path": initial}

    box = ui.column().classes("w-full max-w-2xl gap-1")
    with box:
        use_ws = None
        if use_workspace_toggle:
            use_ws = ui.checkbox(
                "Usar directorio de trabajo maestro",
                value=use_ws_default,
            )

        with ui.row().classes("w-full items-end gap-2 no-wrap"):
            path_in = ui.input(label, value=initial).classes("flex-grow")
            path_in.props('outlined dense')

            async def browse() -> None:
                start = path_in.value or str(get_workspace())
                chosen = await pick_folder_dialog(start)
                if chosen:
                    path_in.set_value(chosen)
                    state["path"] = chosen
                    if use_ws is not None:
                        use_ws.set_value(False)
                        state["use_ws"] = False
                    if on_change:
                        on_change(chosen)
                    ui.notify(f"Carpeta: {chosen}", type="info")
                else:
                    ui.notify(
                        "No se pudo abrir el dialogo. Escribe la ruta o define el directorio de trabajo en Inicio.",
                        type="warning",
                    )

            ui.button("Examinar…", icon="folder_open", on_click=browse).props(
                "outline color=primary"
            )

        def _on_ws_change(e) -> None:
            state["use_ws"] = bool(e.value)
            if e.value:
                path_in.set_value(str(get_workspace()))
                path_in.set_enabled(False)
            else:
                path_in.set_enabled(True)

        if use_ws is not None:
            path_in.set_enabled(not use_ws_default)
            use_ws.on_value_change(_on_ws_change)

        def path_value() -> str:
            if use_ws is not None and use_ws.value:
                return str(get_workspace())
            return (path_in.value or "").strip()

    class Handle:
        def path_value(self) -> str:
            return path_value()

        @property
        def input(self):
            return path_in

    return Handle()


def _notify_assessment(path) -> None:
    a = assess_workspace(path)
    if a.level == "ok":
        ui.notify("Directorio de trabajo actualizado", type="positive")
        return
    msg = a.message
    if a.suggest:
        msg = f"{msg} {a.suggest}"
    ui.notify(f"{a.title}: {msg}", type="warning" if a.level == "warn" else "negative")


def workspace_bar() -> None:

    """Bloque compacto para definir el directorio de trabajo maestro."""
    ws = get_workspace()
    with ui.card().classes("fs-card w-full max-w-2xl p-4"):
        ui.label("Directorio de trabajo").classes("font-semibold")
        ui.label(
            "Se usa por defecto en Espacio, Duplicados, Smart, Buscar y Herramientas. "
            "En cada seccion puedes desmarcar y elegir otra carpeta."
        ).classes("fs-sub text-sm mb-2")
        path_lbl = ui.label(str(ws)).classes("text-sm text-primary break-all")
        a0 = assess_workspace(ws)
        warn_lbl = ui.label(
            "" if a0.level == "ok" else f"⚠ {a0.title}: {a0.message}"
            + (f" {a0.suggest}" if a0.suggest else "")
        ).classes(
            "text-sm text-negative" if a0.level == "danger" else "text-sm text-warning"
        )
        if a0.level == "ok":
            warn_lbl.set_visibility(False)

        def _refresh_warn(path) -> None:
            a = assess_workspace(path)
            if a.level == "ok":
                warn_lbl.set_visibility(False)
                warn_lbl.set_text("")
                ui.notify("Directorio de trabajo actualizado", type="positive")
                return
            warn_lbl.set_visibility(True)
            warn_lbl.set_text(
                f"⚠ {a.title}: {a.message}"
                + (f" {a.suggest}" if a.suggest else "")
            )
            # color via text content prefix only (Quasar classes set at create)
            ui.notify(
                f"{a.title}: {a.message}",
                type="warning" if a.level == "warn" else "negative",
            )

        async def change() -> None:
            chosen = await pick_folder_dialog(str(get_workspace()))
            if not chosen:
                ui.notify(
                    "Escribe una ruta valida abajo si el dialogo no esta disponible",
                    type="warning",
                )
                return
            try:
                set_workspace(chosen)
                path_lbl.set_text(chosen)
                _refresh_warn(chosen)
            except Exception as e:
                ui.notify(str(e), type="negative")

        manual = ui.input("O pega una ruta", value=str(ws)).classes("w-full")

        def apply_manual() -> None:
            try:
                p = set_workspace(manual.value or "")
                path_lbl.set_text(str(p))
                _refresh_warn(p)
            except Exception as e:
                ui.notify(str(e), type="negative")

        with ui.row().classes("gap-2 mt-1"):
            ui.button("Examinar…", icon="folder_open", on_click=change).props(
                "color=primary unelevated"
            )
            ui.button("Aplicar ruta", icon="check", on_click=apply_manual).props("outline")
