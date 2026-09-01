"""Paginas web FileSage — progreso, cancelacion y Smart con checkboxes."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from nicegui import ui

from filesage.application.types import SmartPlan
from filesage.presentation.web.context import (
    get_engine,
    get_settings,
    persist_settings,
    reload_settings,
)
from filesage.presentation.web.jobs import JobControls
from filesage.presentation.web import session_store
from filesage.presentation.web.layout import page_frame
from filesage.presentation.web.ui_helpers import empty_state, feature_card, section_title
from filesage.presentation.web.path_picker import folder_field, workspace_bar
from filesage.presentation.web.context import get_workspace
from filesage.core.workspace_safety import assess_workspace
from filesage.presentation.web.session_store import bind_busy_button


def _fmt(n: int) -> str:
    v = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(v) < 1024:
            return f"{v:.1f} {u}"
        v /= 1024
    return f"{v:.1f} PB"


def _downloads_dir() -> Path:
    home = Path.home()
    for name in ("Downloads", "Descargas"):
        p = home / name
        if p.is_dir():
            return p
    return home


@ui.page("/")
def page_dashboard() -> None:
    settings = get_settings()
    with page_frame("Inicio", active_path="/"):
        section_title(
            f"Bienvenido a {settings.app.name}",
            "Analiza espacio, encuentra duplicados y limpia con seguridad (dry-run por defecto).",
        )
        workspace_bar()
        _a = assess_workspace(get_workspace())
        if _a.level != "ok":
            with ui.card().classes("fs-card w-full max-w-2xl p-4 border border-amber-600/40"):
                ui.label(f"⚠ {_a.title}").classes("font-semibold text-amber-400")
                ui.label(_a.message).classes("fs-sub text-sm")
                if _a.suggest:
                    ui.label(_a.suggest).classes("text-sm text-primary mt-1")
        cards = [
            ("/space", "Espacio", "folder", "Que ocupa mas en una carpeta"),
            ("/duplicates", "Duplicados", "content_copy", "Mismo contenido · simular o papelera"),
            ("/smart", "Smart", "auto_awesome", "Plan inteligente de limpieza"),
            ("/tools", "Herramientas", "handyman", "Convertir imagenes y mas"),
            ("/search", "Buscar", "search", "Nombre, extension y metadatos"),
            ("/history", "Historial", "history", "Transacciones y rollback"),
            ("/settings", "Ajustes", "settings", "Preferencias del motor"),
        ]
        with ui.row().classes("gap-4 flex-wrap"):
            for href, title, icon, desc in cards:
                feature_card(href, title, icon, desc)
        ui.separator().classes("my-2")
        with ui.row().classes("gap-6 text-sm text-[#9898b0]"):
            ui.label(f"Dry-run: {'sí' if settings.app.dry_run_default else 'no'}")
            ui.label(f"Papelera: {'sí' if settings.actions.use_trash else 'no'}")
            ui.label(f"v{settings.app.version}")



@ui.page("/space")
def page_space() -> None:
    engine = get_engine()
    saved = session_store.get_page_state("/space")
    state: dict = {
        "scan": saved.get("scan"),
        "report": saved.get("report"),
        "status": saved.get("status", ""),
    }

    with page_frame("Espacio", active_path="/space"):
        section_title("Uso de espacio", "No modifica archivos. Puedes cancelar el analisis.")
        folder = folder_field(label="Carpeta a analizar", value=saved.get("folder_path"))
        btn_run = ui.button("Analizar", icon="analytics").props("color=primary unelevated")
        job = JobControls(page_route="/space")
        bind_busy_button(btn_run)
        export_row = ui.row().classes("gap-2")
        result_area = ui.column().classes("w-full gap-2")

        def _render_space_results() -> None:
            result_area.clear()
            export_row.clear()
            report, scan = state.get("report"), state.get("scan")
            with result_area:
                if not report or not scan:
                    empty_state(
                        "Elige una carpeta y pulsa Analizar",
                        "Al salir de la seccion se conserva el ultimo resultado.",
                        icon="folder_open",
                    )
                    return
                ui.label("Archivos mas grandes").classes("font-semibold mt-2")
                rows = [
                    {"archivo": f.path.name, "ruta": str(f.path.parent), "tamano": _fmt(f.size)}
                    for f in report.top_files[:30]
                ]
                ui.table(
                    columns=[
                        {"name": "archivo", "label": "Archivo", "field": "archivo"},
                        {"name": "ruta", "label": "Carpeta", "field": "ruta"},
                        {"name": "tamano", "label": "Tamano", "field": "tamano"},
                    ],
                    rows=rows,
                    row_key="ruta",
                    pagination=15,
                ).classes("w-full")
            with export_row:
                ui.button("Exportar JSON", on_click=lambda: do_export("json"), icon="download").props("outline color=primary")
                ui.button("Exportar CSV", on_click=lambda: do_export("csv"), icon="download").props("outline color=primary")

        _render_space_results()
        if state.get("status"):
            job.status.set_text(state["status"])

        async def analyze() -> None:
            root = Path(folder.path_value() or "").expanduser()
            if not root.is_dir():
                ui.notify(f"No es una carpeta valida: {root}", type="negative")
                return
            result_area.clear()
            export_row.clear()
            state["scan"] = state["report"] = None
            btn_run.set_enabled(False)

            def work(reporter):
                return engine.analyze_space(root, top_n=30, progress=reporter)

            try:
                result = await job.run(
                    work,
                    start_msg=f"Analizando {root}…",
                    success_notice=None,  # se notifica abajo con detalle
                )
            except Exception:
                btn_run.set_enabled(True)
                with result_area:
                    empty_state("No se pudo analizar", "Revisa la ruta y los permisos.", icon="error")
                return
            btn_run.set_enabled(True)
            if result is None:
                with result_area:
                    empty_state("Analisis cancelado", "Puedes volver a intentarlo.", icon="cancel")
                return
            scan, report = result
            state["scan"], state["report"] = scan, report
            status_msg = (
                f"Listo · {scan.total_files} archivos · {_fmt(scan.total_size)} · "
                f"{scan.duration_seconds:.1f}s"
            )
            state["status"] = status_msg
            session_store.update_page_state(
                "/space",
                scan=scan,
                report=report,
                status=status_msg,
                folder_path=str(root),
            )
            # job.run ya marco job_finish generico; refinamos mensaje
            job.status.set_text(status_msg)
            ui.notify(status_msg, type="positive", position="top")
            _render_space_results()

        def do_export(fmt: str) -> None:
            if not state["report"] or not state["scan"]:
                ui.notify("Analiza una carpeta primero", type="warning")
                return
            dest = Path(tempfile.gettempdir()) / f"filesage_space.{fmt}"
            try:
                out = engine.export_space(state["report"], state["scan"], dest, fmt=fmt)
                ui.notify(f"Exportado: {out}", type="positive")
                ui.download(str(out), f"filesage_space.{fmt}")
            except Exception as e:
                ui.notify(str(e), type="negative")

        btn_run.on_click(analyze)


@ui.page("/duplicates")
def page_duplicates() -> None:
    engine = get_engine()
    saved = session_store.get_page_state("/duplicates")
    state: dict = {
        "groups": list(saved.get("groups") or []),
        "root": saved.get("root"),
        "status": saved.get("status", ""),
    }

    with page_frame("Duplicados", active_path="/duplicates"):
        section_title("Duplicados", "Compara contenido real. Veras el avance abajo; puedes cancelar si tarda demasiado.")
        folder = folder_field(
            label="Carpeta",
            value=str(saved["root"]) if saved.get("root") else None,
        )
        btn_run = ui.button("Buscar", icon="search").props("color=primary unelevated")
        job = JobControls(page_route="/duplicates")
        bind_busy_button(btn_run)
        actions_row = ui.row().classes("gap-2 flex-wrap")
        result_area = ui.column().classes("w-full gap-2")

        async def simulate() -> None:
            groups = state["groups"]
            if not groups:
                ui.notify("Primero busca duplicados", type="warning")
                return
            plans = engine.plan_trash_duplicates(groups, keep_newest=True)
            tx = await asyncio.to_thread(lambda: engine.execute_actions(plans, dry_run=True))
            ui.notify(f"Dry-run OK · {len(plans)} archivos", type="positive", position="top")
            job.status.set_text(
                f"Simulacion: {len(plans)} irian a la papelera. Tx {tx.transaction_id}"
            )

        async def clean_real() -> None:
            groups = state["groups"]
            if not groups:
                ui.notify("Primero busca duplicados", type="warning")
                return
            plans = engine.plan_trash_duplicates(groups, keep_newest=True)
            with ui.dialog() as dialog, ui.card().classes("fs-card p-4"):
                ui.label("Confirmar limpieza real").classes("font-bold text-lg")
                ui.label(
                    f"Se enviaran {len(plans)} archivos a la PAPELERA.\n"
                    "Se mantiene el mas reciente de cada grupo."
                ).classes("whitespace-pre-wrap text-sm text-[#9898b0]")
                with ui.row().classes("w-full justify-end gap-2 mt-2"):
                    ui.button("Cancelar", on_click=dialog.close).props("flat")

                    async def do_clean() -> None:
                        dialog.close()
                        tx = await asyncio.to_thread(
                            lambda: engine.execute_actions(plans, dry_run=False)
                        )
                        ok = sum(1 for a in tx.actions if a.success)
                        ui.notify(f"Limpieza: {ok}/{len(tx.actions)} OK", type="positive", position="top")
                        state["groups"] = []
                        session_store.update_page_state("/duplicates", groups=[], status="Limpieza terminada")
                        _render_dup_results()

                    ui.button("Confirmar", on_click=do_clean).props("color=negative")
            dialog.open()

        def export_dups(fmt: str) -> None:
            groups, root = state["groups"], state["root"]
            if not groups or not root:
                ui.notify("Busca duplicados primero", type="warning")
                return
            dest = Path(tempfile.gettempdir()) / f"filesage_duplicates.{fmt}"
            try:
                out = engine.export_duplicates(groups, root, dest, fmt=fmt)
                ui.notify(f"Exportado: {out}", type="positive")
                ui.download(str(out), f"filesage_duplicates.{fmt}")
            except Exception as e:
                ui.notify(str(e), type="negative")

        def _render_dup_results() -> None:
            result_area.clear()
            actions_row.clear()
            groups = state.get("groups") or []
            with result_area:
                if not groups:
                    empty_state(
                        "Selecciona una carpeta y busca",
                        "Los resultados se conservan si cambias de seccion.",
                        icon="content_copy",
                    )
                    return
                for i, g in enumerate(groups[:40], 1):
                    with ui.expansion(
                        f"Grupo {i}: {g.count} archivos · {_fmt(g.wasted_size)} recuperable",
                        icon="content_copy",
                    ).classes("w-full"):
                        for fi in g.files:
                            ui.label(f"{fi.path} ({_fmt(fi.size)})").classes("text-sm")
            if groups:
                with actions_row:
                    ui.button("Simular limpieza", on_click=simulate, icon="science").props(
                        "outline color=primary"
                    )
                    ui.button("Enviar a papelera", on_click=clean_real, icon="delete").props(
                        "color=negative unelevated"
                    )
                    ui.button(
                        "Exportar JSON", on_click=lambda: export_dups("json"), icon="download"
                    ).props("flat")
                    ui.button(
                        "Exportar CSV", on_click=lambda: export_dups("csv"), icon="download"
                    ).props("flat")

        _render_dup_results()
        if state.get("status"):
            job.status.set_text(state["status"])

        async def find() -> None:
            root = Path(folder.path_value() or "").expanduser()
            if not root.is_dir():
                ui.notify(f"No es una carpeta: {root}", type="negative")
                return
            result_area.clear()
            actions_row.clear()
            state["groups"] = []
            btn_run.set_enabled(False)

            def work(reporter):
                return engine.find_duplicates(root, progress=reporter)

            try:
                result = await job.run(
                    work,
                    start_msg=f"Buscando duplicados en {root}…",
                    success_notice=None,
                )
            except Exception:
                btn_run.set_enabled(True)
                with result_area:
                    empty_state("Error en la busqueda", "Revisa permisos y ruta.", icon="error")
                return
            btn_run.set_enabled(True)
            if result is None:
                with result_area:
                    empty_state("Busqueda cancelada", "Nada se ha modificado.", icon="cancel")
                return
            scan, groups = result
            state["groups"] = groups
            state["root"] = root
            wasted = sum(g.wasted_size for g in groups)
            status_msg = (
                f"{len(groups)} grupos · recuperable {_fmt(wasted)} · "
                f"{scan.total_files} archivos"
            )
            state["status"] = status_msg
            session_store.update_page_state(
                "/duplicates",
                groups=groups,
                root=root,
                status=status_msg,
            )
            job.status.set_text(status_msg)
            ui.notify(status_msg, type="positive", position="top")
            _render_dup_results()

        btn_run.on_click(find)


@ui.page("/smart")
def page_smart() -> None:
    engine = get_engine()
    saved = session_store.get_page_state("/smart")
    state: dict = {
        "plan": saved.get("plan"),
        "checks": dict(saved.get("checks") or {}),
        "status": saved.get("status", ""),
    }

    with page_frame("Smart", active_path="/smart"):
        section_title(
            "Plan inteligente",
            "Marca o desmarca archivos. Los resultados se conservan al cambiar de seccion.",
        )
        folder = folder_field(label="Carpeta", value=saved.get("folder_path"))
        btn_run = ui.button("Generar plan", icon="auto_awesome").props("color=primary unelevated")
        job = JobControls(page_route="/smart")
        bind_busy_button(btn_run)
        summary = ui.label("").classes("text-sm text-[#9898b0]")
        actions_row = ui.row().classes("gap-2 flex-wrap")
        table_host = ui.column().classes("w-full gap-2")

        def _sync_selection_to_plan() -> None:
            plan = state["plan"]
            if not plan:
                return
            for item in plan.items:
                key = str(item.path)
                if key in state["checks"]:
                    item.selected = bool(state["checks"][key])

        def _update_summary() -> None:
            plan = state["plan"]
            if not plan:
                summary.set_text("")
                return
            _sync_selection_to_plan()
            summary.set_text(
                f"{len(plan.selected_items)} seleccionados · "
                f"{_fmt(plan.selected_bytes)} / {_fmt(plan.total_candidate_bytes)} candidatos"
            )
            session_store.update_page_state(
                "/smart",
                plan=plan,
                checks=dict(state["checks"]),
                status=state.get("status") or "",
            )

        def select_all(val: bool) -> None:
            plan = state["plan"]
            if not plan:
                return
            for item in plan.items:
                state["checks"][str(item.path)] = val
                item.selected = val
            render_items()
            _update_summary()

        def render_items() -> None:
            plan = state["plan"]
            table_host.clear()
            with table_host:
                if not plan or not plan.items:
                    empty_state("Sin candidatos", "No hay duplicados evidentes ni basura tipica detectada.", icon="auto_awesome")
                    return
                with ui.row().classes("gap-2 mb-2"):
                    ui.button("Seleccionar todos", on_click=lambda: select_all(True)).props("outline dense")
                    ui.button("Quitar seleccion", on_click=lambda: select_all(False)).props("outline dense")
                for item in plan.items:
                    key = str(item.path)
                    if key not in state["checks"]:
                        state["checks"][key] = bool(item.selected)
                    with ui.card().classes("fs-card w-full p-3"):
                        with ui.row().classes("items-start gap-3 w-full no-wrap"):
                            ui.checkbox(value=state["checks"][key]).on_value_change(
                                lambda e, k=key: (state["checks"].__setitem__(k, bool(e.value)), _update_summary())
                            )
                            with ui.column().classes("gap-0 flex-grow"):
                                ui.label(item.path.name).classes("font-medium")
                                ui.label(str(item.path.parent)).classes("text-xs text-[#6b6b80]")
                                ui.label(f"{item.confidence.value} · {item.category} · {item.reason}").classes("text-xs text-[#9898b0]")
                                if item.what:
                                    ui.label(item.what).classes("text-xs text-[#7c9cff]")
                            ui.label(_fmt(item.size)).classes("text-sm font-medium text-primary")
            _update_summary()

        async def build() -> None:
            root = Path(folder.path_value() or "").expanduser()
            if not root.is_dir():
                ui.notify("Carpeta invalida", type="negative")
                return
            table_host.clear()
            actions_row.clear()
            state["plan"] = None
            state["checks"] = {}
            btn_run.set_enabled(False)

            def work(reporter):
                return engine.build_smart_plan(root, progress=reporter)

            try:
                plan = await job.run(work, start_msg="Generando plan inteligente…", success_notice=None)
            except Exception:
                btn_run.set_enabled(True)
                with table_host:
                    empty_state("No se pudo generar el plan", "Revisa la ruta.", icon="error")
                return
            btn_run.set_enabled(True)
            if plan is None:
                with table_host:
                    empty_state("Plan cancelado", "Puedes volver a generarlo.", icon="cancel")
                return
            state["plan"] = plan
            state["checks"] = {str(i.path): i.selected for i in plan.items}
            status_msg = f"Plan listo · {len(plan.items)} candidatos"
            session_store.update_page_state(
                "/smart",
                plan=plan,
                checks=dict(state["checks"]),
                status=status_msg,
                folder_path=str(root),
            )
            job.status.set_text(status_msg)
            ui.notify(status_msg, type="positive", position="top")
            render_items()
            _fill_actions()

        async def sim_plan() -> None:
            plan = state["plan"]
            if not plan:
                return
            _sync_selection_to_plan()
            if not plan.selected_items:
                ui.notify("Selecciona al menos un archivo", type="warning")
                return
            actions = engine.smart_plan_to_actions(plan)
            tx = await asyncio.to_thread(lambda: engine.execute_actions(actions, dry_run=True))
            ui.notify(f"Dry-run · {len(actions)} acciones", type="positive")
            job.status.set_text(f"Simulacion OK · Tx {tx.transaction_id}")

        async def run_plan() -> None:
            plan = state["plan"]
            if not plan:
                return
            _sync_selection_to_plan()
            if not plan.selected_items:
                ui.notify("Selecciona al menos un archivo", type="warning")
                return
            actions = engine.smart_plan_to_actions(plan)
            with ui.dialog() as dialog, ui.card().classes("fs-card p-4"):
                ui.label(f"¿Enviar {len(actions)} archivos a la papelera?\nAprox. {_fmt(plan.selected_bytes)}").classes("whitespace-pre-wrap")
                with ui.row().classes("justify-end gap-2"):
                    ui.button("Cancelar", on_click=dialog.close).props("flat")

                    async def confirm() -> None:
                        dialog.close()
                        tx = await asyncio.to_thread(lambda: engine.execute_actions(actions, dry_run=False))
                        ok = sum(1 for a in tx.actions if a.success)
                        ui.notify(f"{ok}/{len(tx.actions)} OK", type="positive")
                        job.status.set_text(f"Ejecutado · Tx {tx.transaction_id}")

                    ui.button("Confirmar", on_click=confirm).props("color=negative")
            dialog.open()

        def _fill_actions() -> None:
            actions_row.clear()
            with actions_row:
                ui.button("Simular plan", on_click=sim_plan, icon="science").props(
                    "outline color=primary"
                )
                ui.button(
                    "Ejecutar (papelera)", on_click=run_plan, icon="delete"
                ).props("color=negative unelevated")

        if state.get("plan"):
            render_items()
            _fill_actions()
            st = state.get("status") or session_store.get_page_state("/smart").get("status")
            if st:
                job.status.set_text(st)
            _update_summary()
        else:
            with table_host:
                empty_state(
                    "Genera un plan para ver candidatos",
                    "Los resultados se conservan al cambiar de seccion.",
                    icon="auto_awesome",
                )
        btn_run.on_click(build)


@ui.page("/search")
def page_search() -> None:
    engine = get_engine()
    saved = session_store.get_page_state("/search")
    state: dict = {
        "results": list(saved.get("results") or []),
        "status": saved.get("status", ""),
        "query": saved.get("query", ""),
    }

    with page_frame("Buscar", active_path="/search"):
        section_title(
            "Buscar archivos",
            "Puedes cancelar si la carpeta es grande. Resultados se conservan al salir.",
        )
        folder = folder_field(label="Carpeta raiz", value=saved.get("folder_path"))
        query_input = ui.input(
            "Texto (nombre, extension…)",
            value=state["query"],
            placeholder="ej. .pdf  o  factura",
        ).classes("w-full max-w-xl")
        use_meta = ui.checkbox(
            "Incluir metadatos (mas lento)", value=bool(saved.get("use_meta"))
        )
        btn_run = ui.button("Buscar", icon="search").props("color=primary unelevated")
        job = JobControls(page_route="/search")
        bind_busy_button(btn_run)
        result_area = ui.column().classes("w-full")

        def _render_search_results() -> None:
            result_area.clear()
            results = state.get("results") or []
            with result_area:
                if not results:
                    empty_state(
                        "Escribe un criterio y busca",
                        "Los resultados se conservan al cambiar de seccion.",
                        icon="search",
                    )
                    return
                rows = [
                    {
                        "archivo": fi.path.name,
                        "ruta": str(fi.path.parent),
                        "tamano": _fmt(fi.size),
                        "que": what or "",
                    }
                    for fi, what in results
                ]
                ui.table(
                    columns=[
                        {"name": "archivo", "label": "Archivo", "field": "archivo"},
                        {"name": "ruta", "label": "Ruta", "field": "ruta"},
                        {"name": "tamano", "label": "Tamano", "field": "tamano"},
                        {"name": "que", "label": "Que es", "field": "que"},
                    ],
                    rows=rows,
                    row_key="ruta",
                    pagination=25,
                ).classes("w-full")

        _render_search_results()
        if state.get("status"):
            job.status.set_text(state["status"])


        async def do_search() -> None:
            root = Path(folder.path_value() or "").expanduser()
            q = (query_input.value or "").strip().lower()
            if not root.is_dir():
                ui.notify("Carpeta invalida", type="negative")
                return
            if not q:
                ui.notify("Escribe un texto de busqueda", type="warning")
                return
            result_area.clear()
            btn_run.set_enabled(False)

            def work(reporter):
                reporter.report(f"Escaneando {root}…", 0.05)
                scan = engine.scan(root, progress=reporter)
                results = []
                total = max(1, len(scan.files))
                for i, fi in enumerate(scan.files):
                    if i % 40 == 0:
                        reporter.report(f"Filtrando {i}/{total}…", 0.1 + 0.9 * (i / total))
                    name = fi.path.name.lower()
                    ext = fi.path.suffix.lower()
                    path_s = str(fi.path).lower()
                    meta_s = ""
                    what = ""
                    if use_meta.value:
                        try:
                            ident = engine.identify_file(fi.path, deep=True)
                            what = ident.summary
                            meta_s = (ident.summary + " " + ident.mime).lower()
                        except Exception:
                            pass
                    if q in f"{name} {ext} {path_s} {meta_s}":
                        results.append((fi, what))
                results.sort(key=lambda x: x[0].size, reverse=True)
                reporter.report("Busqueda lista", 1.0)
                return results[:500]

            try:
                results = await job.run(work, start_msg="Buscando…")
            except Exception:
                btn_run.set_enabled(True)
                with result_area:
                    empty_state("Error en la busqueda", "Revisa la ruta.", icon="error")
                return
            btn_run.set_enabled(True)
            if results is None:
                with result_area:
                    empty_state("Busqueda cancelada", "Puedes intentar de nuevo.", icon="cancel")
                return
            status_msg = f"{len(results)} coincidencias (max 500)"
            job.finish(status_msg, notify=True)
            state["results"] = results
            state["status"] = status_msg
            state["query"] = q
            session_store.update_page_state(
                "/search",
                results=results,
                status=status_msg,
                query=q,
                folder_path=str(root),
                use_meta=bool(use_meta.value),
            )
            with result_area:
                if not results:
                    empty_state("Sin resultados", f"Nada coincide con «{q}»", icon="search_off")
                    return
                rows = [{"archivo": fi.path.name, "ruta": str(fi.path.parent), "tamano": _fmt(fi.size), "que": what or ""} for fi, what in results]
                ui.table(columns=[{"name": "archivo", "label": "Archivo", "field": "archivo"}, {"name": "ruta", "label": "Ruta", "field": "ruta"}, {"name": "tamano", "label": "Tamano", "field": "tamano"}, {"name": "que", "label": "Que es", "field": "que"}], rows=rows, row_key="ruta", pagination=25).classes("w-full")

        btn_run.on_click(do_search)




@ui.page("/tools")
def page_tools() -> None:
    with page_frame("Herramientas", active_path="/tools"):
        section_title("Herramientas", "Utilidades inteligentes sobre el mismo motor local.")
        with ui.row().classes("gap-4 flex-wrap"):
            feature_card(
                "/tools/convert",
                "Convertir imagenes",
                "image",
                "Cualquier formato → PNG, JPG, WEBP… en carpeta aparte",
            )
            feature_card(
                "/tools/empty",
                "Carpetas vacias",
                "folder_off",
                "Lista, selecciona y elimina carpetas vacías (papelera o definitivo)",
            )
            feature_card(
                "/tools/organize",
                "Organizar por tipo",
                "drive_file_move",
                "Mueve musica, imagenes, videos… a subcarpetas (dry-run primero)",
            )
            feature_card(
                "/tools/cleanup",
                "Limpieza profunda",
                "cleaning_services",
                "Vacias y archivos antiguos → papelera o borrado definitivo",
            )
            feature_card(
                "/tools/recycle",
                "Vaciar papelera",
                "delete_forever",
                "Vacia la papelera del sistema (irreversible)",
            )
            feature_card(
                "/tools/zip",
                "Comprimir ZIP",
                "folder_zip",
                "Empaqueta una carpeta en .zip",
            )
            feature_card(
                "/tools/network",
                "Diagnostico de red",
                "wifi_tethering",
                "Analiza DNS, ping, HTTP y sugiere la causa mas probable",
            )




@ui.page("/tools/organize")
def page_organize() -> None:
    """Organizar por tipo: dry-run y mover a FileSage_Organizado/."""
    engine = get_engine()
    saved = session_store.get_page_state("/tools/organize")
    state: dict = {
        "plan": saved.get("plan"),
        "checks": dict(saved.get("checks") or {}),
        "status": saved.get("status", ""),
    }

    with page_frame("Organizar por tipo", active_path="/tools"):
        section_title(
            "Organizar por tipo",
            "Clasifica archivos en FileSage_Organizado/Musica, Imagenes, Videos… "
            "Siempre puedes simular (dry-run) antes de mover.",
        )
        folder = folder_field(label="Carpeta a organizar", value=saved.get("folder_path"))
        min_group = ui.number(
            "Minimo de archivos por tipo", value=3, min=1, max=50, step=1
        ).classes("max-w-xs")
        btn_run = ui.button("Generar plan", icon="drive_file_move").props(
            "color=primary unelevated"
        )
        bind_busy_button(btn_run)
        job = JobControls(page_route="/tools/organize")
        summary = ui.label(state.get("status") or "").classes("text-sm text-[#9898b0]")
        actions_row = ui.row().classes("gap-2 flex-wrap")
        host = ui.column().classes("w-full gap-2")

        def _sync() -> None:
            plan = state["plan"]
            if not plan:
                return
            for item in plan.items:
                k = str(item.path)
                if k in state["checks"]:
                    item.selected = bool(state["checks"][k])

        def _update_summary() -> None:
            plan = state["plan"]
            if not plan:
                summary.set_text("")
                return
            _sync()
            summary.set_text(
                f"{len(plan.selected_items)} seleccionados · "
                f"{_fmt(plan.selected_bytes)} / {_fmt(plan.total_candidate_bytes)}"
            )
            session_store.update_page_state(
                "/tools/organize",
                plan=plan,
                checks=dict(state["checks"]),
                status=state.get("status") or "",
            )

        def select_all(val: bool) -> None:
            plan = state["plan"]
            if not plan:
                return
            for item in plan.items:
                state["checks"][str(item.path)] = val
                item.selected = val
            render()
            _update_summary()

        def render() -> None:
            plan = state["plan"]
            host.clear()
            with host:
                if not plan or not plan.items:
                    empty_state(
                        "Sin candidatos",
                        "Hace falta al menos N archivos del mismo tipo (musica, imagen, video…).",
                        icon="drive_file_move",
                    )
                    return
                with ui.row().classes("gap-2 mb-2"):
                    ui.button("Seleccionar todos", on_click=lambda: select_all(True)).props(
                        "outline dense"
                    )
                    ui.button("Quitar seleccion", on_click=lambda: select_all(False)).props(
                        "outline dense"
                    )
                for item in plan.items:
                    key = str(item.path)
                    if key not in state["checks"]:
                        state["checks"][key] = bool(item.selected)
                    with ui.card().classes("fs-card w-full p-3"):
                        with ui.row().classes("items-start gap-3 w-full no-wrap"):
                            ui.checkbox(value=state["checks"][key]).on_value_change(
                                lambda e, k=key: (
                                    state["checks"].__setitem__(k, bool(e.value)),
                                    _update_summary(),
                                )
                            )
                            with ui.column().classes("gap-0 flex-grow"):
                                ui.label(item.path.name).classes("font-medium")
                                ui.label(str(item.path.parent)).classes(
                                    "text-xs text-[#6b6b80]"
                                )
                                ui.label(item.reason).classes("text-xs text-[#9898b0]")
                            ui.label(_fmt(item.size)).classes(
                                "text-sm font-medium text-primary"
                            )
            _update_summary()

        def _fill_actions() -> None:
            actions_row.clear()
            with actions_row:
                ui.button("Simular (dry-run)", on_click=sim, icon="science").props(
                    "outline color=primary"
                )
                ui.button("Mover seleccionados", on_click=run_move, icon="drive_file_move").props(
                    "color=primary unelevated"
                )

        async def build() -> None:
            root = Path(folder.path_value() or "").expanduser()
            if not root.is_dir():
                ui.notify("Carpeta invalida", type="negative")
                return
            host.clear()
            actions_row.clear()
            state["plan"] = None
            state["checks"] = {}
            btn_run.set_enabled(False)
            nmin = int(min_group.value or 3)

            def work(reporter):
                return engine.build_organize_plan(
                    root, min_files_per_group=nmin, progress=reporter
                )

            try:
                plan = await job.run(
                    work, start_msg="Analizando tipos de archivo…"
                )
            except Exception:
                btn_run.set_enabled(True)
                with host:
                    empty_state("Error", "No se pudo generar el plan.", icon="error")
                return
            btn_run.set_enabled(True)
            if plan is None:
                with host:
                    empty_state("Cancelado", "Puedes volver a intentarlo.", icon="cancel")
                return
            state["plan"] = plan
            state["checks"] = {str(i.path): False for i in plan.items}
            status_msg = f"{len(plan.items)} candidatos a organizar"
            state["status"] = status_msg
            session_store.update_page_state(
                "/tools/organize",
                plan=plan,
                checks=dict(state["checks"]),
                status=status_msg,
                folder_path=str(root),
            )
            job.status.set_text(status_msg)
            ui.notify(status_msg, type="positive", position="top")
            render()
            _fill_actions()

        async def sim() -> None:
            plan = state["plan"]
            if not plan:
                return
            _sync()
            if not plan.selected_items:
                ui.notify("Selecciona al menos un archivo", type="warning")
                return
            actions = engine.organize_plan_to_actions(plan)
            tx = await asyncio.to_thread(
                lambda: engine.execute_actions(actions, dry_run=True)
            )
            ui.notify(
                f"Dry-run OK · {len(actions)} movimientos simulados · {tx.transaction_id[:8]}…",
                type="positive",
            )
            job.status.set_text(f"Simulacion: {len(actions)} se moverian")

        async def run_move() -> None:
            plan = state["plan"]
            if not plan:
                return
            _sync()
            if not plan.selected_items:
                ui.notify("Selecciona al menos un archivo", type="warning")
                return
            actions = engine.organize_plan_to_actions(plan)
            with ui.dialog() as dialog, ui.card().classes("fs-card p-4"):
                ui.label("Confirmar organizacion").classes("font-bold text-lg")
                ui.label(
                    f"Se moveran {len(actions)} archivos a subcarpetas "
                    f"FileSage_Organizado/\n"
                    f"Aprox. {_fmt(plan.selected_bytes)}.\n"
                    "Puedes deshacer movimientos desde el Historial (si aplica)."
                ).classes("whitespace-pre-wrap text-sm text-[#9898b0]")
                with ui.row().classes("w-full justify-end gap-2 mt-2"):
                    ui.button("Cancelar", on_click=dialog.close).props("flat")

                    async def confirm() -> None:
                        dialog.close()
                        tx = await asyncio.to_thread(
                            lambda: engine.execute_actions(actions, dry_run=False)
                        )
                        ok = sum(1 for a in tx.actions if a.success)
                        ui.notify(f"Movidos {ok}/{len(tx.actions)}", type="positive")
                        job.status.set_text(
                            f"Completado {ok}/{len(tx.actions)} · Tx {tx.transaction_id}"
                        )
                        state["plan"] = None
                        state["checks"] = {}
                        session_store.update_page_state(
                            "/tools/organize", plan=None, checks={}, status=job.status.text
                        )
                        host.clear()
                        actions_row.clear()
                        with host:
                            empty_state(
                                "Organizacion terminada",
                                "Revisa FileSage_Organizado/ en la carpeta origen.",
                                icon="done_all",
                            )

                    ui.button("Mover", on_click=confirm).props("color=primary")
            dialog.open()

        if state.get("plan"):
            render()
            _fill_actions()
            if state.get("status"):
                job.status.set_text(state["status"])
        else:
            with host:
                empty_state(
                    "Genera un plan de organizacion",
                    "No se mueve nada hasta que simules o confirmes.",
                    icon="drive_file_move",
                )
        btn_run.on_click(build)




@ui.page("/tools/cleanup")
def page_cleanup() -> None:
    engine = get_engine()
    saved = session_store.get_page_state("/tools/cleanup")
    state: dict = {
        "plan": saved.get("plan"),
        "checks": dict(saved.get("checks") or {}),
        "status": saved.get("status", ""),
    }

    with page_frame("Limpieza profunda", active_path="/tools"):
        section_title(
            "Limpieza profunda",
            "Carpetas vacias y archivos antiguos. Por defecto: papelera. "
            "El borrado definitivo exige confirmacion doble.",
        )
        folder = folder_field(label="Carpeta", value=saved.get("folder_path"))
        with ui.row().classes("gap-4 flex-wrap items-end"):
            old_days = ui.number("Antigüedad (días)", value=365, min=7, max=3650).classes(
                "max-w-xs"
            )
            include_empty = ui.checkbox("Carpetas vacías", value=True)
            include_old = ui.checkbox("Archivos antiguos", value=True)
        btn_run = ui.button("Generar plan", icon="cleaning_services").props(
            "color=primary unelevated"
        )
        bind_busy_button(btn_run)
        job = JobControls(page_route="/tools/cleanup")
        summary = ui.label(state.get("status") or "").classes("text-sm text-[#9898b0]")
        actions_row = ui.row().classes("gap-2 flex-wrap")
        host = ui.column().classes("w-full gap-2")

        def _sync() -> None:
            plan = state["plan"]
            if not plan:
                return
            for item in plan.items:
                k = str(item.path)
                if k in state["checks"]:
                    item.selected = bool(state["checks"][k])

        def _update_summary() -> None:
            plan = state["plan"]
            if not plan:
                return
            _sync()
            summary.set_text(
                f"{len(plan.selected_items)} seleccionados · {_fmt(plan.selected_bytes)}"
            )
            session_store.update_page_state(
                "/tools/cleanup",
                plan=plan,
                checks=dict(state["checks"]),
                status=state.get("status") or "",
            )

        def select_all(val: bool) -> None:
            plan = state["plan"]
            if not plan:
                return
            for item in plan.items:
                state["checks"][str(item.path)] = val
                item.selected = val
            render()
            _update_summary()

        def render() -> None:
            plan = state["plan"]
            host.clear()
            with host:
                if not plan or not plan.items:
                    empty_state(
                        "Sin candidatos",
                        "Prueba bajar los días de antigüedad o incluir carpetas vacías.",
                        icon="cleaning_services",
                    )
                    return
                with ui.row().classes("gap-2 mb-2"):
                    ui.button("Seleccionar todos", on_click=lambda: select_all(True)).props(
                        "outline dense"
                    )
                    ui.button("Quitar selección", on_click=lambda: select_all(False)).props(
                        "outline dense"
                    )
                for item in plan.items:
                    key = str(item.path)
                    if key not in state["checks"]:
                        state["checks"][key] = bool(item.selected)
                    icon = "folder_off" if item.kind == "empty_folder" else "schedule"
                    with ui.card().classes("fs-card w-full p-3"):
                        with ui.row().classes("items-start gap-3 w-full no-wrap"):
                            ui.checkbox(value=state["checks"][key]).on_value_change(
                                lambda e, k=key: (
                                    state["checks"].__setitem__(k, bool(e.value)),
                                    _update_summary(),
                                )
                            )
                            ui.icon(icon).classes("text-primary mt-1")
                            with ui.column().classes("gap-0 flex-grow"):
                                ui.label(item.path.name).classes("font-medium")
                                ui.label(str(item.path)).classes("text-xs text-[#6b6b80]")
                                ui.label(f"{item.kind} · {item.reason}").classes(
                                    "text-xs text-[#9898b0]"
                                )
                            ui.label(_fmt(item.size)).classes(
                                "text-sm font-medium text-primary"
                            )
            _update_summary()

        def _fill_actions() -> None:
            actions_row.clear()
            with actions_row:
                ui.button(
                    "Simular → papelera", on_click=lambda: do_exec(True, False), icon="science"
                ).props("outline color=primary")
                ui.button(
                    "Enviar a papelera", on_click=lambda: do_exec(False, False), icon="delete"
                ).props("color=negative unelevated")
                ui.button(
                    "Borrar DEFINITIVO",
                    on_click=lambda: do_exec(False, True),
                    icon="delete_forever",
                ).props("outline color=negative")

        async def build() -> None:
            root = Path(folder.path_value() or "").expanduser()
            if not root.is_dir():
                ui.notify("Carpeta inválida", type="negative")
                return
            host.clear()
            actions_row.clear()
            state["plan"] = None
            state["checks"] = {}
            btn_run.set_enabled(False)

            def work(reporter):
                return engine.build_cleanup_plan(
                    root,
                    include_empty_folders=bool(include_empty.value),
                    include_old_files=bool(include_old.value),
                    old_days=int(old_days.value or 365),
                    progress=reporter,
                )

            try:
                plan = await job.run(work, start_msg="Buscando candidatos…")
            except Exception:
                btn_run.set_enabled(True)
                return
            btn_run.set_enabled(True)
            if plan is None:
                return
            state["plan"] = plan
            state["checks"] = {str(i.path): False for i in plan.items}
            status_msg = f"{len(plan.items)} candidatos"
            state["status"] = status_msg
            session_store.update_page_state(
                "/tools/cleanup",
                plan=plan,
                checks=dict(state["checks"]),
                status=status_msg,
                folder_path=str(root),
            )
            job.status.set_text(status_msg)
            ui.notify(status_msg, type="positive", position="top")
            render()
            _fill_actions()

        async def do_exec(dry: bool, permanent: bool) -> None:
            plan = state["plan"]
            if not plan:
                return
            _sync()
            if not plan.selected_items:
                ui.notify("Selecciona al menos un elemento", type="warning")
                return
            actions = engine.cleanup_plan_to_actions(plan, permanent=permanent)
            if dry:
                tx = await asyncio.to_thread(
                    lambda: engine.execute_actions(actions, dry_run=True)
                )
                ui.notify(
                    f"Dry-run OK · {len(actions)} acciones · {tx.transaction_id[:8]}…",
                    type="positive",
                )
                return

            title = "Borrado DEFINITIVO" if permanent else "Enviar a papelera"
            warn = (
                "Esta acción NO se puede deshacer desde FileSage ni desde la papelera."
                if permanent
                else "Se enviará a la papelera del sistema (recuperable desde el SO)."
            )
            with ui.dialog() as dialog, ui.card().classes("fs-card p-4 max-w-md"):
                ui.label(title).classes("font-bold text-lg text-negative" if permanent else "font-bold text-lg")
                ui.label(
                    f"{len(actions)} elementos · {_fmt(plan.selected_bytes)}\n{warn}"
                ).classes("whitespace-pre-wrap text-sm text-[#9898b0]")
                confirm_txt = ui.input(
                    'Escribe BORRAR para confirmar' if permanent else "Escribe OK para confirmar",
                ).classes("w-full")
                with ui.row().classes("w-full justify-end gap-2 mt-2"):
                    ui.button("Cancelar", on_click=dialog.close).props("flat")

                    async def go() -> None:
                        need = "BORRAR" if permanent else "OK"
                        if (confirm_txt.value or "").strip().upper() != need:
                            ui.notify(f"Debes escribir {need}", type="warning")
                            return
                        dialog.close()
                        tx = await asyncio.to_thread(
                            lambda: engine.execute_actions(actions, dry_run=False)
                        )
                        ok = sum(1 for a in tx.actions if a.success)
                        ui.notify(f"{ok}/{len(tx.actions)} completados", type="positive")
                        job.status.set_text(f"Listo {ok}/{len(tx.actions)}")

                    ui.button("Confirmar", on_click=go).props("color=negative")
            dialog.open()

        if state.get("plan"):
            render()
            _fill_actions()
            if state.get("status"):
                job.status.set_text(state["status"])
        else:
            with host:
                empty_state(
                    "Genera un plan de limpieza",
                    "Nada se borra hasta simular o confirmar.",
                    icon="cleaning_services",
                )
        btn_run.on_click(build)


@ui.page("/tools/recycle")
def page_recycle() -> None:
    engine = get_engine()
    with page_frame("Vaciar papelera", active_path="/tools"):
        section_title(
            "Vaciar papelera del sistema",
            "Elimina de forma permanente todo lo que hay en la papelera del SO. "
            "No se puede deshacer.",
        )
        with ui.card().classes("fs-card w-full max-w-xl p-5 gap-3"):
            ui.icon("warning").classes("text-4xl text-negative")
            ui.label(
                "Usa esto solo cuando hayas revisado la papelera del sistema. "
                "FileSage no lista el contenido de la papelera: confía en el Explorador/Finder."
            ).classes("fs-sub text-sm")
            confirm = ui.input('Escribe VACIAR para habilitar el botón').classes("w-full")
            btn = ui.button(
                "Vaciar papelera ahora", icon="delete_forever"
            ).props("color=negative unelevated")
            btn.set_enabled(False)

            def _toggle() -> None:
                btn.set_enabled((confirm.value or "").strip().upper() == "VACIAR")

            confirm.on_value_change(lambda e: _toggle())

            async def do_empty() -> None:
                if (confirm.value or "").strip().upper() != "VACIAR":
                    return
                with ui.dialog() as dialog, ui.card().classes("fs-card p-4"):
                    ui.label("¿Vaciar la papelera del sistema?").classes("font-bold")
                    ui.label("Última confirmación. Acción irreversible.").classes(
                        "text-sm text-[#9898b0]"
                    )
                    with ui.row().classes("justify-end gap-2"):
                        ui.button("No", on_click=dialog.close).props("flat")

                        async def yes() -> None:
                            dialog.close()
                            try:
                                msg = await asyncio.to_thread(engine.empty_recycle_bin)
                                ui.notify(msg, type="positive")
                            except Exception as e:
                                ui.notify(str(e), type="negative")

                        ui.button("Sí, vaciar", on_click=yes).props("color=negative")
                dialog.open()

            btn.on_click(do_empty)




@ui.page("/tools/network")
def page_network() -> None:
    engine = get_engine()
    state: dict = {"diagnosis": None}

    with page_frame("Diagnostico de red", active_path="/tools"):
        section_title(
            "Diagnostico inteligente de red",
            "IP, gateway, DNS, ping, HTTP, latencia TCP y velocidad estimada (muestra pequena). "
            "No sustituye un speedtest completo.",
        )
        deeper = ui.checkbox(
            "Prueba de velocidad un poco mayor (~500KB, mas precisa)",
            value=False,
        )
        btn = ui.button("Analizar red", icon="wifi_tethering").props("color=primary unelevated")
        bind_busy_button(btn)
        job = JobControls(page_route="/tools/network")
        cause_box = ui.column().classes("w-full max-w-2xl gap-2")
        checks_box = ui.column().classes("w-full max-w-2xl gap-2")
        repair_box = ui.row().classes("gap-2 flex-wrap")

        def render(diag) -> None:
            state["diagnosis"] = diag
            cause_box.clear()
            checks_box.clear()
            repair_box.clear()
            with cause_box:
                with ui.card().classes("fs-card w-full p-4"):
                    ui.label("Causa mas probable").classes("font-semibold text-lg")
                    ui.label(diag.likely_cause).classes("text-sm mt-1")
                    ui.label(f"Confianza: {diag.confidence}").classes(
                        "text-xs text-[#9898b0] mt-1"
                    )
                    if diag.recommendations:
                        ui.label("Recomendaciones").classes("font-medium mt-3")
                        for r in diag.recommendations:
                            ui.label(f"• {r}").classes("text-sm text-[#b0b0c0]")
            with checks_box:
                ui.label("Checks").classes("font-semibold")
                for c in diag.checks:
                    color = (
                        "text-positive" if c.ok
                        else ("text-warning" if c.severity == "warn" else "text-negative")
                    )
                    icon = "check_circle" if c.ok else "error"
                    with ui.card().classes("fs-card w-full p-3"):
                        with ui.row().classes("items-start gap-2"):
                            ui.icon(icon).classes(color)
                            with ui.column().classes("gap-0"):
                                ui.label(c.title).classes("font-medium")
                                ui.label(c.detail).classes("text-xs text-[#9898b0] break-all")
            with repair_box:
                ui.button(
                    "Vaciar cache DNS",
                    on_click=lambda: do_repair("flush_dns"),
                    icon="cached",
                ).props("outline color=primary")
                ui.button(
                    "Renovar DHCP",
                    on_click=lambda: do_repair("renew_dhcp"),
                    icon="autorenew",
                ).props("outline color=primary")
                ui.button(
                    "Winsock reset (admin)",
                    on_click=confirm_winsock,
                    icon="warning",
                ).props("outline color=negative")

        async def analyze() -> None:
            cause_box.clear()
            checks_box.clear()
            repair_box.clear()
            btn.set_enabled(False)

            def work(reporter):
                return engine.run_network_diagnostics(progress=reporter, light_speed=not bool(deeper.value))

            try:
                diag = await job.run(work, start_msg="Diagnosticando red…")
            except Exception as e:
                btn.set_enabled(True)
                ui.notify(str(e), type="negative")
                return
            btn.set_enabled(True)
            if diag is None:
                return
            render(diag)
            ui.notify("Diagnostico listo", type="positive")

        async def do_repair(rid: str) -> None:
            result = await asyncio.to_thread(lambda: engine.run_network_repair(rid))
            ui.notify(
                result.message[:200],
                type="positive" if result.ok else "warning",
            )
            job.status.set_text(result.message[:120])

        async def confirm_winsock() -> None:
            with ui.dialog() as dialog, ui.card().classes("fs-card p-4 max-w-md"):
                ui.label("Reset Winsock (Windows)").classes("font-bold text-negative")
                ui.label(
                    "Requiere administrador y reinicio del PC. "
                    "Escribe WINSOCK para continuar."
                ).classes("text-sm text-[#9898b0]")
                conf = ui.input("Confirmacion").classes("w-full")
                with ui.row().classes("justify-end gap-2"):
                    ui.button("Cancelar", on_click=dialog.close).props("flat")

                    async def go() -> None:
                        if (conf.value or "").strip().upper() != "WINSOCK":
                            ui.notify("Escribe WINSOCK", type="warning")
                            return
                        dialog.close()
                        await do_repair("winsock_reset")

                    ui.button("Ejecutar", on_click=go).props("color=negative")
            dialog.open()

        with cause_box:
            empty_state(
                "Pulsa Analizar red",
                "Se evaluara conectividad local, DNS e Internet.",
                icon="wifi_tethering",
            )
        btn.on_click(analyze)


@ui.page("/tools/convert")
def page_convert() -> None:
    engine = get_engine()
    state: dict = {"results": []}

    with page_frame("Convertir imagenes", active_path="/tools"):
        section_title(
            "Convertidor de imagenes",
            "Detecta el formato de entrada y exporta al que elijas en una carpeta FileSage_converted.",
        )
        folder = folder_field(label="Archivo o carpeta de origen", use_workspace_toggle=True)
        with ui.row().classes("w-full max-w-2xl gap-4 items-end flex-wrap"):
            with ui.column().classes("gap-1"):
                ui.label("Formato de salida").classes("text-sm text-[#9a9ab0]")
                target = ui.select(
                    ["png", "jpg", "webp", "bmp", "tiff", "gif"],
                    value="png",
                ).classes("w-40")
            with ui.column().classes("gap-1 flex-grow"):
                ui.label("Calidad JPG / WEBP").classes("text-sm text-[#9a9ab0]")
                quality = ui.slider(min=50, max=100, value=90, step=1).props(
                    "label label-always"
                ).classes("min-w-[200px]")
        recursive = ui.checkbox("Incluir subcarpetas", value=False)
        out_input = ui.input(
            "Carpeta destino (vacío = FileSage_converted junto al origen)",
            value="",
        ).classes("w-full max-w-2xl")
        ui.label(
            "No se convierten archivos que ya tengan el formato elegido "
            "ni los que estén dentro de FileSage_converted."
        ).classes("text-xs text-[#6b6b80] max-w-2xl")
        job = JobControls(page_route="")
        result_area = ui.column().classes("w-full gap-2")
        btn = ui.button("Convertir", icon="transform").props("color=primary unelevated")
        bind_busy_button(btn)

        async def run_convert() -> None:
            import asyncio
            src = Path(folder.path_value() or "").expanduser()
            if not src.exists():
                ui.notify("Ruta no existe", type="negative")
                return
            dest = Path(out_input.value).expanduser() if (out_input.value or "").strip() else None
            result_area.clear()
            btn.set_enabled(False)

            def work(reporter):
                reporter.report("Convirtiendo…", 0.1)
                res = engine.convert_images(
                    src,
                    target_ext=str(target.value),
                    output_dir=dest,
                    quality=int(quality.value or 90),
                    recursive=bool(recursive.value),
                )
                reporter.report(f"Listo: {len(res)} archivo(s)", 1.0)
                return res

            try:
                res = await job.run(work, start_msg="Convirtiendo imagenes…")
            except Exception:
                btn.set_enabled(True)
                with result_area:
                    empty_state("Error", "No se pudo convertir.", icon="error")
                return
            btn.set_enabled(True)
            if res is None:
                with result_area:
                    empty_state("Cancelado", "No se escribio nada.", icon="cancel")
                return
            state["results"] = res
            ok = sum(1 for r in res if r.ok and not getattr(r, "skipped", False))
            skipped = sum(1 for r in res if getattr(r, "skipped", False))
            job.finish(f"{ok} convertidos · {skipped} omitidos · {len(res)} total")
            with result_area:
                if not res:
                    empty_state(
                        "Sin imagenes",
                        "No se encontraron archivos de imagen en esa ruta.",
                        icon="image_not_supported",
                    )
                    return
                rows = [
                    {
                        "origen": r.source.name,
                        "destino": str(r.destination) if r.destination else "—",
                        "estado": (
                            "Omitido" if getattr(r, "skipped", False)
                            else ("OK" if r.ok else r.message)
                        ),
                        "detalle": r.message,
                    }
                    for r in res[:200]
                ]
                ui.table(
                    columns=[
                        {"name": "origen", "label": "Origen", "field": "origen"},
                        {"name": "destino", "label": "Destino", "field": "destino"},
                        {"name": "estado", "label": "Estado", "field": "estado"},
                        {"name": "detalle", "label": "Detalle", "field": "detalle"},
                    ],
                    rows=rows,
                    row_key="origen",
                    pagination=20,
                ).classes("w-full")
                if ok and res[0].destination:
                    ui.label(f"Carpeta de salida: {res[0].destination.parent}").classes(
                        "text-sm text-[#9a9ab0]"
                    )

        btn.on_click(run_convert)
        with result_area:
            empty_state(
                "Elige una foto o una carpeta",
                "La salida va a FileSage_converted (o la carpeta que indiques).",
                icon="image",
            )




@ui.page("/tools/empty")
def page_empty_folders() -> None:
    """Lista carpetas vacias y permite papelera / borrado definitivo con dry-run."""
    from datetime import datetime

    from filesage.domain.models import ActionRecord, ActionType
    from filesage.infrastructure.storage import new_action_id

    engine = get_engine()
    saved = session_store.get_page_state("/tools/empty")
    state: dict = {
        "paths": list(saved.get("paths") or []),
        "checks": dict(saved.get("checks") or {}),
        "status": saved.get("status", ""),
    }

    with page_frame("Carpetas vacias", active_path="/tools"):
        section_title(
            "Carpetas vacías",
            "Encuéntralas y elimínalas: simulación, papelera o borrado definitivo.",
        )
        folder = folder_field(label="Carpeta raiz", value=saved.get("folder_path"))
        btn = ui.button("Buscar vacias", icon="folder_off").props("color=primary unelevated")
        bind_busy_button(btn)
        job = JobControls(page_route="/tools/empty")
        summary = ui.label(state.get("status") or "").classes("text-sm text-[#9898b0]")
        actions_row = ui.row().classes("gap-2 flex-wrap")
        result_area = ui.column().classes("w-full gap-2")

        def _selected_paths() -> list[Path]:
            out = []
            for s in state["paths"]:
                if state["checks"].get(s, False):
                    out.append(Path(s))
            return out

        def _update_summary() -> None:
            n = sum(1 for v in state["checks"].values() if v)
            summary.set_text(f"{n} seleccionadas · {len(state['paths'])} encontradas")
            session_store.update_page_state(
                "/tools/empty",
                paths=list(state["paths"]),
                checks=dict(state["checks"]),
                status=summary.text,
            )

        def select_all(val: bool) -> None:
            for s in state["paths"]:
                state["checks"][s] = val
            render()
            _update_summary()

        def render() -> None:
            result_area.clear()
            with result_area:
                if not state["paths"]:
                    empty_state(
                        "No hay carpetas vacias",
                        "Todo tiene contenido o aun no has buscado.",
                        icon="check",
                    )
                    return
                with ui.row().classes("gap-2 mb-2"):
                    ui.button("Seleccionar todas", on_click=lambda: select_all(True)).props(
                        "outline dense"
                    )
                    ui.button("Quitar seleccion", on_click=lambda: select_all(False)).props(
                        "outline dense"
                    )
                for s in state["paths"][:300]:
                    if s not in state["checks"]:
                        state["checks"][s] = False
                    with ui.card().classes("fs-card w-full p-3"):
                        with ui.row().classes("items-center gap-3 w-full no-wrap"):
                            ui.checkbox(value=state["checks"][s]).on_value_change(
                                lambda e, k=s: (
                                    state["checks"].__setitem__(k, bool(e.value)),
                                    _update_summary(),
                                )
                            )
                            ui.icon("folder_off").classes("text-primary")
                            ui.label(s).classes("text-sm break-all")
            _update_summary()

        def _fill_actions() -> None:
            actions_row.clear()
            with actions_row:
                with ui.card().classes("fs-card w-full p-3"):
                    ui.label("Acciones sobre la selección").classes("font-semibold mb-1")
                    ui.label(
                        "Elige carpetas abajo (o «Seleccionar todas») y luego una acción."
                    ).classes("text-xs text-[#9898b0] mb-2")
                    with ui.row().classes("gap-2 flex-wrap"):
                        ui.button(
                            "Simular → papelera",
                            on_click=lambda: do_exec(True, False),
                            icon="science",
                        ).props("outline color=primary")
                        ui.button(
                            "Enviar a papelera",
                            on_click=lambda: do_exec(False, False),
                            icon="delete",
                        ).props("color=negative unelevated")
                        ui.button(
                            "Borrar DEFINITIVO",
                            on_click=lambda: do_exec(False, True),
                            icon="delete_forever",
                        ).props("outline color=negative")
                        ui.button(
                            "Seleccionar todas",
                            on_click=lambda: select_all(True),
                            icon="done_all",
                        ).props("outline dense")

        def _to_actions(permanent: bool) -> list:
            at = ActionType.DELETE if permanent else ActionType.TRASH
            return [
                ActionRecord(
                    action_id=new_action_id(),
                    action_type=at,
                    source=path,
                    destination=None,
                    timestamp=datetime.now(),
                    success=False,
                    message="",
                    dry_run=True,
                    metadata={"kind": "empty_folder"},
                )
                for path in _selected_paths()
            ]

        async def run() -> None:
            root = Path(folder.path_value() or "").expanduser()
            if not root.is_dir():
                ui.notify("Carpeta invalida", type="negative")
                return
            result_area.clear()
            actions_row.clear()
            btn.set_enabled(False)

            def work(reporter):
                reporter.report("Explorando…", 0.2)
                found = engine.find_empty_folders(root)
                reporter.report(f"{len(found)} encontradas", 1.0)
                return found

            try:
                found = await job.run(work, start_msg="Buscando carpetas vacias…")
            except Exception:
                btn.set_enabled(True)
                return
            btn.set_enabled(True)
            if found is None:
                return
            state["paths"] = [str(p) for p in found]
            state["checks"] = {str(p): False for p in found}
            status_msg = f"{len(found)} carpetas vacias"
            state["status"] = status_msg
            session_store.update_page_state(
                "/tools/empty",
                paths=state["paths"],
                checks=dict(state["checks"]),
                status=status_msg,
                folder_path=str(root),
            )
            job.status.set_text(status_msg)
            ui.notify(status_msg, type="positive", position="top")
            render()
            if found:
                _fill_actions()

        async def do_exec(dry: bool, permanent: bool) -> None:
            paths = _selected_paths()
            if not paths:
                ui.notify("Selecciona al menos una carpeta", type="warning")
                return
            actions = _to_actions(permanent)
            if dry:
                tx = await asyncio.to_thread(
                    lambda: engine.execute_actions(actions, dry_run=True)
                )
                ui.notify(
                    f"Dry-run OK · {len(actions)} carpetas · {tx.transaction_id[:8]}…",
                    type="positive",
                )
                return

            title = "Borrado DEFINITIVO" if permanent else "Enviar a papelera"
            warn = (
                "No se puede deshacer desde la papelera."
                if permanent
                else "Las carpetas iran a la papelera del sistema."
            )
            with ui.dialog() as dialog, ui.card().classes("fs-card p-4 max-w-md"):
                ui.label(title).classes(
                    "font-bold text-lg text-negative" if permanent else "font-bold text-lg"
                )
                ui.label(f"{len(paths)} carpetas.\n{warn}").classes(
                    "whitespace-pre-wrap text-sm text-[#9898b0]"
                )
                need = "BORRAR" if permanent else "OK"
                confirm_txt = ui.input(f"Escribe {need} para confirmar").classes("w-full")
                with ui.row().classes("w-full justify-end gap-2 mt-2"):
                    ui.button("Cancelar", on_click=dialog.close).props("flat")

                    async def go() -> None:
                        if (confirm_txt.value or "").strip().upper() != need:
                            ui.notify(f"Debes escribir {need}", type="warning")
                            return
                        dialog.close()
                        tx = await asyncio.to_thread(
                            lambda: engine.execute_actions(actions, dry_run=False)
                        )
                        ok = sum(1 for a in tx.actions if a.success)
                        ui.notify(f"{ok}/{len(tx.actions)} completadas", type="positive")
                        job.status.set_text(f"Listo {ok}/{len(tx.actions)}")
                        # quitar del listado las que se eliminaron con exito
                        done = {
                            str(a.source)
                            for a in tx.actions
                            if a.success
                        }
                        state["paths"] = [s for s in state["paths"] if s not in done]
                        state["checks"] = {
                            s: state["checks"].get(s, False) for s in state["paths"]
                        }
                        render()
                        if state["paths"]:
                            _fill_actions()
                        else:
                            actions_row.clear()

                    ui.button("Confirmar", on_click=go).props("color=negative")
            dialog.open()

        if state["paths"]:
            render()
            _fill_actions()
            if state.get("status"):
                job.status.set_text(state["status"])
        else:
            with result_area:
                empty_state(
                    "Elige una carpeta y busca",
                    "Después podrás seleccionar y enviar a la papelera o borrar.",
                    icon="folder_off",
                )
        btn.on_click(run)



@ui.page("/tools/zip")
def page_zip() -> None:
    engine = get_engine()
    with page_frame("Comprimir ZIP", active_path="/tools"):
        section_title("Comprimir carpeta", "Crea un .zip junto a la carpeta (o en la ruta que indiques).")
        folder = folder_field(label="Carpeta a comprimir")
        dest_in = ui.input("ZIP destino (opcional)", value="").classes("w-full max-w-2xl")
        job = JobControls(page_route="")
        result_area = ui.column().classes("w-full gap-2")
        btn = ui.button("Crear ZIP", icon="folder_zip").props("color=primary unelevated")
        bind_busy_button(btn)

        async def run() -> None:
            src = Path(folder.path_value() or "").expanduser()
            if not src.is_dir():
                ui.notify("Carpeta invalida", type="negative")
                return
            dest = Path(dest_in.value).expanduser() if (dest_in.value or "").strip() else None
            result_area.clear()
            btn.set_enabled(False)

            def work(reporter):
                reporter.report("Comprimiendo…", 0.3)
                out = engine.zip_folder(src, dest)
                reporter.report("Listo", 1.0)
                return out

            try:
                out = await job.run(work, start_msg="Creando ZIP…")
            except Exception:
                btn.set_enabled(True)
                with result_area:
                    empty_state("Error", "No se pudo crear el ZIP.", icon="error")
                return
            btn.set_enabled(True)
            if out is None:
                return
            job.finish(f"ZIP: {out}")
            with result_area:
                ui.label(f"Creado: {out}").classes("text-primary font-medium")
                ui.label(f"Tamano: {out.stat().st_size} bytes").classes("text-sm text-[#9a9ab0]")

        btn.on_click(run)
        with result_area:
            empty_state("Elige una carpeta", "Se generara un archivo .zip.", icon="folder_zip")


@ui.page("/history")
def page_history() -> None:
    engine = get_engine()
    host = ui.column().classes("w-full gap-2")
    status = ui.label("").classes("text-sm text-[#9898b0]")

    def refresh() -> None:
        host.clear()
        try:
            txs = engine.list_transactions(limit=50)
        except Exception as e:
            status.set_text(f"Error: {e}")
            with host:
                empty_state("No se pudo leer el historial", str(e), icon="error")
            return
        status.set_text(f"{len(txs)} transacciones recientes")
        with host:
            if not txs:
                empty_state(
                    "Aun no hay transacciones",
                    "Apareceran al simular o ejecutar limpiezas.",
                    icon="history",
                )
                return
            for tx in txs:
                ok = sum(1 for a in tx.actions if a.success)
                title = (
                    f"{tx.transaction_id[:8]}… · "
                    f"{'dry-run' if tx.dry_run else 'REAL'} · "
                    f"{ok}/{len(tx.actions)} OK · {tx.started_at}"
                )
                with ui.expansion(title, icon="history").classes("w-full"):
                    for a in tx.actions[:30]:
                        ui.label(
                            f"{'✓' if a.success else '✗'} {a.action_type.value}: {a.source}"
                            + (f" → {a.destination}" if a.destination else "")
                        ).classes("text-sm")
                    if not tx.dry_run:

                        async def do_rollback(t=tx) -> None:
                            try:
                                await asyncio.to_thread(lambda: engine.rollback(t))
                                ui.notify("Rollback solicitado", type="info")
                                refresh()
                            except Exception as e:
                                ui.notify(str(e), type="negative")

                        ui.button(
                            "Intentar rollback", on_click=do_rollback, icon="undo"
                        ).props("outline dense")

    with page_frame("Historial", active_path="/history"):
        section_title("Historial", "Registro de simulaciones y acciones reales.")
        ui.button("Actualizar", on_click=refresh, icon="refresh").props("color=primary unelevated")
        status
        host
        refresh()


@ui.page("/settings")
def page_settings() -> None:
    s = get_settings()
    dry = ui.switch("Dry-run por defecto (recomendado)", value=s.app.dry_run_default)
    trash = ui.switch("Usar papelera del sistema", value=s.actions.use_trash)
    min_size = ui.number(
        "Tamano minimo duplicados (bytes)",
        value=s.duplicates.min_size_bytes,
        min=0,
        step=256,
    ).classes("max-w-xs")
    ignore_hidden = ui.switch("Ignorar ocultos al escanear", value=s.scan.ignore_hidden)
    reco = ui.switch(
        "Exclusiones recomendadas (AppData, .git, node_modules…)",
        value=getattr(s.scan, "use_recommended_excludes", True),
    )
    status = ui.label("").classes("text-sm text-[#9898b0]")
    log_path = ui.label(f"Log: {s.logging.file or '(solo consola)'}").classes(
        "text-xs text-[#6b6b80]"
    )

    def save() -> None:
        s.app.dry_run_default = bool(dry.value)
        s.actions.use_trash = bool(trash.value)
        s.duplicates.min_size_bytes = int(min_size.value or 0)
        s.scan.ignore_hidden = bool(ignore_hidden.value)
        s.scan.use_recommended_excludes = bool(reco.value)
        try:
            persist_settings(s)
            status.set_text("Guardado. Engine reiniciado.")
            ui.notify("Configuracion guardada", type="positive")
        except Exception as e:
            ui.notify(str(e), type="negative")

    def reload() -> None:
        reload_settings()
        ui.notify("Recargado desde disco", type="info")
        ui.navigate.to("/settings")

    with page_frame("Ajustes", active_path="/settings"):
        section_title("Preferencias", "Se aplican al motor de esta sesion web.")
        dry
        trash
        min_size
        ignore_hidden
        log_path
        with ui.row().classes("gap-2"):
            ui.button("Guardar", on_click=save, icon="save").props("color=primary unelevated")
            ui.button("Recargar", on_click=reload, icon="refresh").props("outline")
        status


@ui.page("/about")
def page_about() -> None:
    settings = get_settings()
    with page_frame("Acerca de", active_path="/about"):
        section_title("FileSage", f"Version {settings.app.version} · GPL-3.0-or-later")
        ui.markdown(
            f"""
Ventana nativa (WebView) · mismo motor que Qt/CLI.

- Dry-run: `{settings.app.dry_run_default}`
- Papelera: `{settings.actions.use_trash}`
- Log: `{settings.logging.file or "consola"}`

```
python scripts/run_filesage.py --web
```
"""
        )
