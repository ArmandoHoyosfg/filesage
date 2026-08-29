"""Shell de app: header + drawer + aviso de job + navegacion segura."""

from __future__ import annotations

from contextlib import contextmanager

from nicegui import ui

from filesage.presentation.web import session_store


NAV = [
    ("/", "Inicio", "home"),
    ("/space", "Espacio", "folder"),
    ("/duplicates", "Duplicados", "content_copy"),
    ("/smart", "Smart", "auto_awesome"),
    ("/search", "Buscar", "search"),
    ("/tools", "Herramientas", "handyman"),
    ("/history", "Historial", "history"),
    ("/settings", "Ajustes", "settings"),
    ("/about", "Acerca de", "info"),
]

_CSS = """
<style>
  :root {
    --fs-bg: #0b0b10;
    --fs-surface: #14141c;
    --fs-elevated: #1a1a24;
    --fs-border: #2c2c3a;
    --fs-text: #ececf4;
    --fs-muted: #9a9ab0;
    --fs-accent: #8b9cff;
  }
  body, .nicegui-content {
    background: var(--fs-bg) !important;
    color: var(--fs-text) !important;
    font-family: 'Segoe UI', Inter, system-ui, sans-serif !important;
  }
  .fs-brand {
    font-weight: 700;
    letter-spacing: -0.03em;
    background: linear-gradient(120deg, #c4b5fd, #8b9cff 50%, #67e8f9);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .fs-title { font-size: 1.75rem; font-weight: 700; letter-spacing: -0.03em; }
  .fs-sub { color: var(--fs-muted); font-size: 0.92rem; line-height: 1.5; }
  .fs-card {
    background: var(--fs-elevated) !important;
    border: 1px solid var(--fs-border) !important;
    border-radius: 16px !important;
    transition: border-color .2s ease, box-shadow .2s ease, transform .15s ease;
  }
  .fs-card:hover {
    border-color: rgba(139,156,255,.45) !important;
    box-shadow: 0 8px 28px rgba(0,0,0,.28);
  }
  .fs-empty {
    border: 1px dashed var(--fs-border);
    border-radius: 16px;
    background: rgba(20,20,28,.6);
    padding: 2.5rem 1.25rem;
    text-align: center;
  }
  .q-drawer { background: var(--fs-surface) !important; border-right: 1px solid var(--fs-border); }
  .q-header { background: var(--fs-surface) !important; border-bottom: 1px solid var(--fs-border); }
  .q-btn { text-transform: none !important; }
  .q-field__label { white-space: normal !important; max-width: 100% !important; }
  .q-select, .q-field { min-width: 9rem; }

  .fs-job-banner {
    background: rgba(139, 156, 255, 0.12);
    border: 1px solid rgba(139, 156, 255, 0.35);
    border-radius: 12px;
    padding: 0.6rem 1rem;
  }
</style>
"""


def _safe_navigate(href: str, current: str | None) -> None:
    """Avisa si hay trabajo en curso al cambiar de seccion."""
    if session_store.job_is_running():
        info = session_store.job_info()
        origin = info.get("page") or "otra seccion"
        if href != origin:
            with ui.dialog() as dialog, ui.card().classes("fs-card p-4 max-w-md"):
                ui.label("Trabajo en progreso").classes("font-bold text-lg")
                ui.label(
                    f"Hay una operacion en curso en «{origin}».\n"
                    f"{info.get('message') or info.get('label') or ''}\n\n"
                    "Puedes salir: el trabajo sigue en segundo plano y el resultado "
                    "se conservara al volver. O permanece hasta que termine."
                ).classes("whitespace-pre-wrap text-sm text-[#9a9ab0]")
                with ui.row().classes("w-full justify-end gap-2 mt-2"):
                    ui.button("Quedarme", on_click=dialog.close).props("flat")

                    def go() -> None:
                        dialog.close()
                        ui.navigate.to(href)

                    ui.button("Salir de todos modos", on_click=go).props("color=primary")
            dialog.open()
            return
    ui.navigate.to(href)


@contextmanager
def page_frame(title: str, active_path: str | None = None):
    ui.colors(
        primary="#8b9cff",
        secondary="#2c2c3a",
        accent="#c4b5fd",
        dark="#0b0b10",
        positive="#6ee7b7",
        negative="#fb7185",
    )
    ui.add_head_html(_CSS)

    # Aviso si un job termino mientras estabas en otra pagina
    notice = session_store.consume_finished_notice()
    if notice:
        ui.notify(f"Trabajo terminado: {notice}", type="positive", position="top", close_button=True)

    with ui.header().classes("items-center justify-between px-4").style("height:52px"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("auto_fix").classes("text-primary text-2xl")
            try:
                from filesage.assets import icon_path as _icon
                _p = _icon("filesage_32.png")
                if _p.exists():
                    ui.image(str(_p)).classes("w-7 h-7 rounded-lg")
            except Exception:
                pass
            ui.label("FileSage").classes("fs-brand text-xl")
            ui.label("·").classes("text-[#4a4a5c]")
            ui.label(title).classes("text-sm text-[#9a9ab0]")
        with ui.row().classes("items-center gap-3"):
            from filesage.presentation.web.context import get_workspace

            ws = get_workspace()
            ui.label(f"🗀 {ws.name}").classes("text-xs text-[#9a9ab0]").tooltip(str(ws))
            ui.label("Modo seguro").classes("text-xs text-[#6b6b80]")

    with ui.left_drawer(value=True, fixed=True, bordered=False).classes("p-3 gap-1").style(
        "width: 220px"
    ):
        ui.label("GESTIÓN").classes(
            "text-[10px] tracking-[0.14em] text-[#5c5c72] px-2 pt-1 pb-2"
        )
        for href, label, icon in NAV:
            is_active = active_path == href
            btn = (
                ui.button(
                    label,
                    icon=icon,
                    on_click=lambda h=href: _safe_navigate(h, active_path),
                )
                .props("flat dense align=left color=primary")
                .classes("w-full justify-start rounded-xl")
            )
            if is_active:
                btn.classes("bg-[rgba(139,156,255,0.16)]")
        ui.space()
        from filesage.presentation.web.context import get_settings

        ui.label(f"v{get_settings().app.version} · GPL-3").classes(
            "text-[11px] text-[#5c5c72] px-2 pb-2"
        )

    with ui.column().classes("w-full max-w-5xl mx-auto p-6 gap-5"):
        # Banner global de job
        banner = ui.row().classes("w-full fs-job-banner items-center gap-3")
        banner.set_visibility(False)
        with banner:
            ui.spinner(size="sm")
            banner_lbl = ui.label("").classes("text-sm")

        def _refresh_banner() -> None:
            if session_store.job_is_running():
                info = session_store.job_info()
                banner.set_visibility(True)
                banner_lbl.set_text(
                    f"Trabajando en {info.get('page') or '…'}: "
                    f"{info.get('message') or info.get('label') or ''}"
                )
            else:
                banner.set_visibility(False)

        _refresh_banner()
        session_store.add_listener(_refresh_banner)
        ui.timer(0.4, _refresh_banner)

        yield
