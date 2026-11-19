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
from filesage.presentation.web.path_picker import folder_field, workspace_bar, pick_files_dialog
from filesage.presentation.web.context import get_workspace
from filesage.core.workspace_safety import assess_workspace
from filesage.presentation.web.session_store import bind_busy_button
from filesage.presentation.web.selection_ui import selection_banner
from filesage.presentation.web.confirm_actions import confirm_trash_preview
from filesage.services.file_search import match_file, rank_hits
from filesage.services.search_smart import (
    SearchFilters,
    SearchPreset,
    delete_preset,
    load_presets,
    save_preset,
    suggest_from_rows,
)


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
        section_title("Duplicados", "Solo archivos con el MISMO contenido (hash completo). Para fotos parecidas pero no identicas usa Herramientas → Imagenes similares.")
        selection_banner(tool="duplicates")
        keep_strategy_sel = ui.select(
            {
                "newest": "Conservar el mas reciente",
                "oldest": "Conservar el mas antiguo",
                "shortest_name": "Conservar nombre mas corto",
                "prefer_path": "Preferir ruta que contenga…",
            },
            value="newest",
            label="Al limpiar, conservar",
        ).classes("max-w-md")
        prefer_path_in = ui.input(
            "Subcadena de ruta preferida (si aplica)",
            placeholder="ej. Originales o Backup",
        ).classes("max-w-md")
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
            plans = engine.plan_trash_duplicates(
                groups,
                strategy=str(keep_strategy_sel.value or "newest"),
                prefer_path_substr=(prefer_path_in.value or "").strip() or None,
            )
            if not plans:
                ui.notify("Nada que enviar (un solo archivo por grupo)", type="info")
                return

            def work(reporter):
                return engine.execute_actions_progressed(
                    plans, dry_run=True, progress=reporter
                )

            tx = await job.run(
                work, start_msg=f"Simulando limpieza de {len(plans)}…"
            )
            if tx is None:
                return
            job.status.set_text(
                f"Simulacion: {len(plans)} irian a papelera · {tx.transaction_id[:8]}…"
            )

        async def clean_real() -> None:
            groups = state["groups"]
            if not groups:
                ui.notify("Primero busca duplicados", type="warning")
                return
            plans = engine.plan_trash_duplicates(
                groups,
                strategy=str(keep_strategy_sel.value or "newest"),
                prefer_path_substr=(prefer_path_in.value or "").strip() or None,
            )
            if not plans:
                ui.notify("Nada que enviar", type="info")
                return
            paths = [a.source for a in plans]

            async def run_real() -> None:
                def work(reporter):
                    return engine.execute_actions_progressed(
                        plans, dry_run=False, progress=reporter
                    )
                tx = await job.run(
                    work, start_msg=f"Enviando {len(plans)} a papelera…"
                )
                if tx is None:
                    return
                ok = sum(1 for a in tx.actions if a.success)
                job.status.set_text(f"Papelera: {ok}/{len(tx.actions)} OK")
                ui.notify(f"{ok} archivos a la papelera", type="positive")

            await confirm_trash_preview(
                paths,
                title="Confirmar limpieza de duplicados",
                on_confirm=run_real,
            )


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
                    hh = (g.hash_full or "")[:12]
                    with ui.expansion(
                        f"Grupo {i}: {g.count} archivos · {_fmt(g.wasted_size)} recuperable · hash {hh}…",
                        icon="content_copy",
                    ).classes("w-full"):
                        ui.label("Contenido binario identico (no solo tamano).").classes(
                            "text-xs text-[#6b6b80] mb-1"
                        )
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
        selection_banner(tool="smart")
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
            if not actions:
                ui.notify("No hay acciones que simular", type="info")
                return

            def _work_dry(reporter):
                return engine.execute_actions_progressed(
                    actions, dry_run=True, progress=reporter
                )

            tx = await job.run(
                _work_dry, start_msg=f"Simulando {len(actions)} acciones…"
            )
            if tx is None:
                return
            ui.notify(
                f"Dry-run OK · {len(actions)} acciones · {tx.transaction_id[:8]}…",
                type="positive",
            )
            job.status.set_text(f"Simulacion OK · Tx {tx.transaction_id[:8]}…")

        async def run_plan() -> None:
            plan = state["plan"]
            if not plan:
                return
            _sync_selection_to_plan()
            if not plan.selected_items:
                ui.notify("Selecciona al menos un archivo", type="warning")
                return
            actions = engine.smart_plan_to_actions(plan)
            if not actions:
                ui.notify("No hay acciones", type="info")
                return
            paths = [a.source for a in actions]

            async def run_real() -> None:
                def _work_real(reporter):
                    return engine.execute_actions_progressed(
                        actions, dry_run=False, progress=reporter
                    )

                tx = await job.run(
                    _work_real, start_msg=f"Ejecutando {len(actions)} acciones…"
                )
                if tx is None:
                    return
                ok = sum(1 for a in tx.actions if a.success)
                job.status.set_text(f"Listo {ok}/{len(tx.actions)}")
                ui.notify(f"{ok}/{len(tx.actions)} completadas", type="positive")

            await confirm_trash_preview(
                paths,
                title="Confirmar plan Smart",
                on_confirm=run_real,
            )

        def _fill_actions() -> None:
            actions_row.clear()
            with actions_row:
                ui.button("Simular seleccion", on_click=sim_plan, icon="science").props(
                    "outline color=primary"
                )
                ui.button(
                    "Ejecutar seleccion", on_click=run_plan, icon="play_arrow"
                ).props("color=negative unelevated")

        if state.get("plan"):
            render_items()
            _fill_actions()
            if state.get("status"):
                job.status.set_text(state["status"])
                summary.set_text(state["status"])
        else:
            with table_host:
                empty_state(
                    "Genera un plan",
                    "Analiza la carpeta y te propondremos candidatos seguros.",
                    icon="auto_awesome",
                )
        btn_run.on_click(build)


@ui.page("/search")
def page_search() -> None:
    """Busqueda + acciones in-situ + puente a otras herramientas."""
    from datetime import datetime

    from filesage.domain.models import ActionRecord, ActionType
    from filesage.infrastructure.storage import new_action_id

    engine = get_engine()
    saved = session_store.get_page_state("/search")
    state: dict = {
        "results": list(saved.get("results") or []),
        "checks": dict(saved.get("checks") or {}),
        "status": saved.get("status", ""),
        "query": saved.get("query", ""),
    }
    norm_results: list[dict] = []
    for item in state["results"]:
        if isinstance(item, dict):
            norm_results.append(item)
        else:
            try:
                fi, what = item
                norm_results.append(
                    {
                        "path": str(fi.path),
                        "name": fi.path.name,
                        "parent": str(fi.path.parent),
                        "size": int(fi.size),
                        "what": what or "",
                    }
                )
            except Exception:
                continue
    state["results"] = norm_results

    with page_frame("Buscar", active_path="/search"):
        section_title(
            "Buscar archivos",
            "Coincide por nombre de archivo. La ruta de carpetas solo si lo activas.",
        )
        folder = folder_field(label="Carpeta raiz", value=saved.get("folder_path"))
        query_input = ui.input(
            "Texto (nombre, extension, ruta…)",
            value=state["query"],
            placeholder="ej. .pdf  ·  factura  ·  .mp3",
        ).classes("w-full max-w-xl")
        with ui.row().classes("gap-4 flex-wrap items-center"):
            use_meta = ui.checkbox(
                "Incluir metadatos (mas lento)", value=bool(saved.get("use_meta"))
            )
            use_path = ui.checkbox(
                "Buscar tambien en la ruta completa",
                value=bool(saved.get("use_path")),
            )
            only_ext = ui.input(
                "Filtrar extension (opcional)",
                value=saved.get("ext_filter") or "",
                placeholder=".jpg",
            ).classes("max-w-xs")
        with ui.expansion("Filtros inteligentes", icon="tune").classes(
            "w-full max-w-2xl"
        ):
            with ui.row().classes("gap-4 flex-wrap items-end w-full"):
                min_size_in = ui.number(
                    "Tamano min (KB)",
                    value=float(saved.get("min_size_kb") or 0),
                    min=0,
                    step=1,
                ).classes("max-w-[9rem]")
                max_size_in = ui.number(
                    "Tamano max (KB, 0=sin limite)",
                    value=float(saved.get("max_size_kb") or 0),
                    min=0,
                    step=1,
                ).classes("max-w-[11rem]")
                newer_days_in = ui.number(
                    "Mas nuevos que (dias, 0=todos)",
                    value=float(saved.get("newer_days") or 0),
                    min=0,
                    step=1,
                ).classes("max-w-[11rem]")
                images_only = ui.checkbox(
                    "Solo imagenes",
                    value=bool(saved.get("images_only")),
                )
                exclude_app = ui.checkbox(
                    "Excluir carpetas FileSage_*",
                    value=bool(saved.get("exclude_app_folders", True)),
                )
        with ui.expansion("Presets de busqueda", icon="bookmark").classes(
            "w-full max-w-2xl"
        ):
            preset_name = ui.input("Nombre del preset").classes("max-w-sm")
            preset_select = ui.select(
                options={p.name: p.name for p in load_presets()} or {"": "(ninguno)"},
                value=None,
                label="Cargar preset",
            ).classes("max-w-sm")

            def _refresh_preset_options() -> None:
                opts = {p.name: p.name for p in load_presets()}
                preset_select.options = opts or {"": "(ninguno)"}
                preset_select.update()

            def _apply_preset() -> None:
                name = preset_select.value
                for pr in load_presets():
                    if pr.name == name:
                        query_input.value = pr.query
                        only_ext.value = pr.ext_filter
                        use_meta.value = pr.use_meta
                        use_path.value = pr.use_path
                        min_size_in.value = pr.min_size / 1024 if pr.min_size else 0
                        max_size_in.value = pr.max_size / 1024 if pr.max_size else 0
                        newer_days_in.value = pr.newer_days
                        images_only.value = pr.images_only
                        exclude_app.value = pr.exclude_app_folders
                        ui.notify(f"Preset «{pr.name}» cargado", type="positive")
                        return
                ui.notify("Selecciona un preset", type="warning")

            def _save_preset() -> None:
                name = (preset_name.value or "").strip()
                if not name:
                    ui.notify("Pon un nombre al preset", type="warning")
                    return
                save_preset(
                    SearchPreset(
                        name=name,
                        query=(query_input.value or "").strip(),
                        ext_filter=(only_ext.value or "").strip(),
                        use_meta=bool(use_meta.value),
                        use_path=bool(use_path.value),
                        min_size=int(float(min_size_in.value or 0) * 1024),
                        max_size=int(float(max_size_in.value or 0) * 1024),
                        newer_days=int(newer_days_in.value or 0),
                        images_only=bool(images_only.value),
                        exclude_app_folders=bool(exclude_app.value),
                    )
                )
                _refresh_preset_options()
                ui.notify(f"Preset «{name}» guardado", type="positive")

            def _delete_preset() -> None:
                name = preset_select.value
                if not name:
                    return
                delete_preset(str(name))
                _refresh_preset_options()
                ui.notify("Preset eliminado", type="info")

            with ui.row().classes("gap-2 flex-wrap"):
                ui.button("Cargar", on_click=_apply_preset, icon="download").props(
                    "outline dense"
                )
                ui.button("Guardar actual", on_click=_save_preset, icon="save").props(
                    "outline dense color=primary"
                )
                ui.button("Eliminar", on_click=_delete_preset, icon="delete").props(
                    "flat dense"
                )
        ui.label(
            "Inteligente: prioriza el nombre. Filtros y presets evitan ruido. "
            "Tras buscar veras sugerencias segun lo encontrado."
        ).classes("text-xs text-[#6b6b80] max-w-2xl")
        suggestions_host = ui.column().classes("w-full gap-1")
        btn_run = ui.button("Buscar", icon="search").props("color=primary unelevated")
        job = JobControls(page_route="/search")
        bind_busy_button(btn_run)
        summary = ui.label(state.get("status") or "").classes("text-sm text-[#9898b0]")
        actions_row = ui.row().classes("gap-2 flex-wrap")
        bridge_row = ui.row().classes("gap-2 flex-wrap")
        result_area = ui.column().classes("w-full gap-2")

        def _selected_paths() -> list[Path]:
            out: list[Path] = []
            for row in state["results"]:
                p = str(row.get("path") or "")
                if p and state["checks"].get(p, False):
                    out.append(Path(p))
            return out

        def _update_summary() -> None:
            n = sum(1 for v in state["checks"].values() if v)
            total = len(state["results"])
            summary.set_text(f"{n} seleccionados · {total} resultados")
            session_store.update_page_state(
                "/search",
                results=list(state["results"]),
                checks=dict(state["checks"]),
                status=summary.text,
                query=state.get("query") or "",
            )

        def select_all(val: bool) -> None:
            for row in state["results"]:
                state["checks"][str(row["path"])] = val
            render()
            _update_summary()

        def render() -> None:
            result_area.clear()
            actions_row.clear()
            bridge_row.clear()
            with result_area:
                if not state["results"]:
                    empty_state(
                        "Escribe un criterio y busca",
                        "Luego podras actuar sobre la seleccion o enviar a otra herramienta.",
                        icon="search",
                    )
                    return
                with ui.row().classes("gap-2 mb-2 flex-wrap"):
                    ui.button(
                        "Seleccionar todos", on_click=lambda: select_all(True)
                    ).props("outline dense")
                    ui.button(
                        "Quitar seleccion", on_click=lambda: select_all(False)
                    ).props("outline dense")
                for row in state["results"][:400]:
                    p = str(row["path"])
                    if p not in state["checks"]:
                        state["checks"][p] = False
                    with ui.card().classes("fs-card w-full p-3"):
                        with ui.row().classes("items-start gap-3 w-full no-wrap"):
                            ui.checkbox(value=state["checks"][p]).on_value_change(
                                lambda e, k=p: (
                                    state["checks"].__setitem__(k, bool(e.value)),
                                    _update_summary(),
                                )
                            )
                            with ui.column().classes("gap-0 flex-grow"):
                                ui.label(row.get("name") or Path(p).name).classes(
                                    "font-medium"
                                )
                                ui.label(row.get("parent") or "").classes(
                                    "text-xs text-[#6b6b80] break-all"
                                )
                                if row.get("what"):
                                    ui.label(str(row["what"])).classes(
                                        "text-xs text-[#7c9cff]"
                                    )
                                if row.get("why"):
                                    ui.label(f"Coincide por: {row['why']}").classes(
                                        "text-xs text-[#6b6b80]"
                                    )
                            ui.label(_fmt(int(row.get("size") or 0))).classes(
                                "text-sm text-primary"
                            )
            _update_summary()
            with actions_row:
                ui.label("Acciones sobre la seleccion (aqui mismo)").classes(
                    "text-xs text-[#9898b0] w-full"
                )
                ui.button(
                    "Simular → papelera",
                    on_click=lambda: do_trash(True),
                    icon="science",
                ).props("outline color=primary")
                ui.button(
                    "Enviar a papelera",
                    on_click=lambda: do_trash(False),
                    icon="delete",
                ).props("color=negative unelevated")
                ui.button(
                    "Buscar duplicados entre seleccion",
                    on_click=dups_in_selection,
                    icon="content_copy",
                ).props("outline color=primary")
                ui.button(
                    "Convertir imagenes seleccionadas",
                    on_click=convert_selected,
                    icon="transform",
                ).props("outline color=primary")
                ui.button(
                    "Copiar rutas", on_click=copy_paths, icon="content_copy"
                ).props("outline")
                ui.button(
                    "Exportar lista", on_click=export_list, icon="download"
                ).props("outline")
            with bridge_row:
                with ui.expansion(
                    "Opciones avanzadas: abrir otra seccion", icon="open_in_new"
                ).classes("w-full max-w-2xl"):
                    ui.label(
                        "Solo si prefieres el flujo completo de esa herramienta."
                    ).classes("text-xs text-[#9898b0] mb-2")
                    with ui.row().classes("gap-2 flex-wrap"):
                        ui.button(
                            "Duplicados",
                            on_click=lambda: send_to("/duplicates", "duplicates"),
                        ).props("flat dense")
                        ui.button(
                            "Smart", on_click=lambda: send_to("/smart", "smart")
                        ).props("flat dense")
                        ui.button(
                            "Copiar / Mover",
                            on_click=lambda: send_to("/tools/transfer", "transfer"),
                        ).props("flat dense")
                        ui.button(
                            "Organizar",
                            on_click=lambda: send_to("/tools/organize", "organize"),
                        ).props("flat dense")
                        ui.button(
                            "Limpieza",
                            on_click=lambda: send_to("/tools/cleanup", "cleanup"),
                        ).props("flat dense")

        def publish_selection() -> list[str]:
            paths = [str(p) for p in _selected_paths()]
            if not paths:
                ui.notify("Selecciona al menos un archivo", type="warning")
                return []
            session_store.set_selection(
                paths, source="search", label=f"Busqueda: {len(paths)} archivos"
            )
            return paths

        def send_to(route: str, kind: str) -> None:
            paths = publish_selection()
            if not paths:
                return
            parents = {str(Path(p).parent) for p in paths}
            if len(parents) == 1:
                common = next(iter(parents))
                session_store.update_page_state(
                    route,
                    folder_path=common,
                    from_search=True,
                    selection_hint=f"{len(paths)} desde Buscar",
                )
            ui.notify(
                f"{len(paths)} archivos listos para {kind}. Abriendo…",
                type="positive",
            )
            ui.navigate.to(route)

        def _trash_actions(paths: list[Path]):
            return [
                ActionRecord(
                    action_id=new_action_id(),
                    action_type=ActionType.TRASH,
                    source=p,
                    destination=None,
                    timestamp=datetime.now(),
                    success=False,
                    message="",
                    dry_run=True,
                    metadata={"from": "search"},
                )
                for p in paths
            ]

        async def do_trash(dry: bool) -> None:
            paths = _selected_paths()
            if not paths:
                ui.notify("Selecciona al menos un archivo", type="warning")
                return
            actions = _trash_actions(paths)

            async def run_batch(dry_run: bool) -> None:
                def work(reporter):
                    return engine.execute_actions_progressed(
                        actions, dry_run=dry_run, progress=reporter
                    )

                tx = await job.run(
                    work,
                    start_msg=(
                        f"{'Simulando' if dry_run else 'Enviando a papelera'} "
                        f"{len(actions)} archivo(s)…"
                    ),
                    success_notice=None,
                )
                if tx is None:
                    return
                ok = sum(1 for a in tx.actions if a.success)
                msg = (
                    f"{'Simulacion' if dry_run else 'Papelera'}: "
                    f"{ok}/{len(tx.actions)} OK"
                )
                job.status.set_text(msg)
                ui.notify(msg, type="positive", position="top")
                if not dry_run:
                    done = {str(a.source) for a in tx.actions if a.success}
                    state["results"] = [
                        r for r in state["results"] if r["path"] not in done
                    ]
                    state["checks"] = {
                        r["path"]: state["checks"].get(r["path"], False)
                        for r in state["results"]
                    }
                    render()

            if dry:
                await run_batch(True)
                return

            await confirm_trash_preview(
                paths,
                title="Enviar a papelera",
                on_confirm=lambda: run_batch(False),
            )

        async def dups_in_selection() -> None:
            paths = _selected_paths()
            if len(paths) < 2:
                ui.notify("Selecciona al menos 2 archivos", type="warning")
                return

            def work(reporter):
                from filesage.domain.models import FileInfo

                files = []
                for pth in paths:
                    try:
                        st = pth.stat()
                        files.append(
                            FileInfo(
                                path=pth,
                                size=st.st_size,
                                mtime=st.st_mtime,
                                is_symlink=pth.is_symlink(),
                            )
                        )
                    except OSError:
                        continue
                reporter.report(f"Comparando {len(files)} archivos…", 0.1)
                return engine.duplicate_finder.find(files, progress=reporter)

            groups = await job.run(
                work, start_msg="Buscando duplicados en la seleccion…"
            )
            if groups is None:
                return
            if not groups:
                ui.notify("No hay duplicados exactos en la seleccion", type="info")
                job.status.set_text("Sin duplicados en la seleccion")
                return
            wasted = sum(g.wasted_size for g in groups)
            msg = f"{len(groups)} grupos · {_fmt(wasted)} recuperables"
            job.status.set_text(msg)
            ui.notify(msg, type="positive")
            with result_area:
                ui.label(f"Duplicados en seleccion: {msg}").classes(
                    "font-semibold text-primary mt-2"
                )
                for i, g in enumerate(groups[:20], 1):
                    names = ", ".join(f.path.name for f in g.files[:5])
                    ui.label(f"Grupo {i}: {names}").classes("text-sm")

        async def convert_selected() -> None:
            paths = _selected_paths()
            img_ext = {
                ".png",
                ".jpg",
                ".jpeg",
                ".webp",
                ".bmp",
                ".gif",
                ".tif",
                ".tiff",
            }
            imgs = [p for p in paths if p.suffix.lower() in img_ext]
            if not imgs:
                ui.notify("No hay imagenes en la seleccion", type="warning")
                return

            def work(reporter):
                from filesage.services.image_converter import (
                    convert_one,
                    default_output_dir,
                )

                results = []
                for i, img in enumerate(imgs):
                    reporter.report(
                        f"Convirtiendo {i+1}/{len(imgs)}: {img.name}",
                        i / max(1, len(imgs)),
                    )
                    reporter.check()
                    out = default_output_dir(img.parent)
                    results.append(convert_one(img, out, target_ext="png"))
                reporter.report("Conversion terminada", 1.0)
                return results

            res = await job.run(
                work, start_msg=f"Convirtiendo {len(imgs)} imagenes…"
            )
            if res is None:
                return
            ok = sum(1 for r in res if r.ok and not r.skipped)
            sk = sum(1 for r in res if r.skipped)
            msg = f"{ok} convertidas · {sk} omitidas"
            job.status.set_text(msg)
            ui.notify(msg, type="positive")

        def copy_paths() -> None:
            paths = _selected_paths()
            if not paths:
                ui.notify("Selecciona archivos", type="warning")
                return
            text = "\n".join(str(p) for p in paths)
            try:
                ui.clipboard.write(text)
            except Exception:
                with ui.dialog() as d, ui.card().classes("fs-card p-4 max-w-lg"):
                    ui.label("Copia las rutas:").classes("font-medium")
                    ui.textarea(value=text).classes("w-full").props(
                        "readonly outlined"
                    )
                    ui.button("Cerrar", on_click=d.close)
                d.open()
            ui.notify(f"{len(paths)} rutas", type="positive")

        def export_list() -> None:
            paths = _selected_paths() or [Path(r["path"]) for r in state["results"]]
            if not paths:
                return
            out = Path.home() / ".filesage" / "exports"
            out.mkdir(parents=True, exist_ok=True)
            dest = out / f"search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            dest.write_text("\n".join(str(p) for p in paths), encoding="utf-8")
            ui.notify(f"Exportado: {dest}", type="positive")


        def _show_suggestions(rows: list) -> None:
            suggestions_host.clear()
            selected = []
            for r in rows:
                if state["checks"].get(str(r.get("path")), False):
                    selected.append(r)
            base = selected or list(rows)
            tips = suggest_from_rows(base)
            with suggestions_host:
                if not tips:
                    return
                ui.label("Sugerencias inteligentes").classes(
                    "text-sm font-medium text-primary mt-2"
                )
                with ui.row().classes("gap-2 flex-wrap"):
                    for tip in tips:
                        def _go(action=tip.action, title=tip.title):
                            paths = _selected_paths()
                            if action == "convert":
                                for r in state["results"]:
                                    pth = str(r.get("path") or "")
                                    if Path(pth).suffix.lower() in {
                                        ".png", ".jpg", ".jpeg", ".webp",
                                        ".bmp", ".gif", ".tif", ".tiff",
                                    }:
                                        state["checks"][pth] = True
                                ui.notify(
                                    title + " — marca imagenes y usa Convertir",
                                    type="info",
                                )
                                render()
                                return
                            if action == "duplicates":
                                if not paths and state["results"]:
                                    for r in state["results"][:100]:
                                        state["checks"][str(r["path"])] = True
                                send_to("/duplicates", "duplicates")
                                return
                            if action == "organize":
                                send_to("/tools/organize", "organize")
                                return
                            if action == "cleanup":
                                send_to("/tools/cleanup", "cleanup")
                                return
                            if action == "similar":
                                paths = paths or [
                                    Path(r["path"]) for r in state["results"][:50]
                                ]
                                parents = {str(Path(p).parent) for p in paths}
                                if len(parents) == 1:
                                    session_store.update_page_state(
                                        "/tools/similar",
                                        folder_path=next(iter(parents)),
                                    )
                                ui.navigate.to("/tools/similar")
                                return

                        ui.button(
                            tip.title,
                            on_click=_go,
                            icon="auto_awesome",
                        ).props("outline dense color=primary").tooltip(tip.detail)

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
            actions_row.clear()
            bridge_row.clear()
            btn_run.set_enabled(False)
            ext_f = (only_ext.value or "").strip().lower()
            if ext_f and not ext_f.startswith("."):
                ext_f = "." + ext_f

            def work(reporter):
                reporter.report(f"Escaneando {root}…", 0.05)
                scan = engine.scan(root, progress=reporter)
                hits = []
                total = max(1, len(scan.files))
                for i, fi in enumerate(scan.files):
                    if reporter and i % 50 == 0:
                        reporter.report(
                            f"Filtrando {i}/{total}",
                            0.1 + 0.85 * (i / total),
                        )
                        reporter.check()
                    what = ""
                    mime = ""
                    if use_meta.value:
                        try:
                            ident = engine.identify_file(fi.path, deep=True)
                            what = ident.summary
                            mime = ident.mime
                        except Exception:
                            pass
                    filters = SearchFilters(
                        min_size=int(float(min_size_in.value or 0) * 1024),
                        max_size=int(float(max_size_in.value or 0) * 1024),
                        newer_days=int(newer_days_in.value or 0),
                        images_only=bool(images_only.value),
                        exclude_app_folders=bool(exclude_app.value),
                    )
                    if not filters.allows(fi.path, int(fi.size), fi.mtime):
                        continue
                    hit = match_file(
                        path=fi.path,
                        size=int(fi.size),
                        root=root,
                        query=q,
                        what=what,
                        mime=mime,
                        use_path=bool(use_path.value),
                        use_meta=bool(use_meta.value),
                        ext_filter=ext_f,
                    )
                    if hit:
                        hits.append(hit)
                ranked = rank_hits(hits, limit=500)
                results = [
                    {
                        "path": str(h.path),
                        "name": h.name,
                        "parent": h.parent,
                        "size": h.size,
                        "what": h.what,
                        "why": h.match_why,
                    }
                    for h in ranked
                ]
                reporter.report(f"{len(results)} coincidencias", 1.0)
                return results

            try:
                results = await job.run(work, start_msg="Buscando…")
            except Exception:
                btn_run.set_enabled(True)
                return
            btn_run.set_enabled(True)
            if results is None:
                return
            state["results"] = results
            state["checks"] = {r["path"]: False for r in results}
            state["query"] = q
            status_msg = f"{len(results)} coincidencias (max 500)"
            state["status"] = status_msg
            session_store.update_page_state(
                "/search",
                results=results,
                checks=dict(state["checks"]),
                status=status_msg,
                query=q,
                folder_path=str(root),
                use_meta=bool(use_meta.value),
                use_path=bool(use_path.value),
                ext_filter=ext_f,
                min_size_kb=float(min_size_in.value or 0),
                max_size_kb=float(max_size_in.value or 0),
                newer_days=int(newer_days_in.value or 0),
                images_only=bool(images_only.value),
                exclude_app_folders=bool(exclude_app.value),
            )
            job.status.set_text(status_msg)
            ui.notify(status_msg, type="positive", position="top")
            render()
            _show_suggestions(results)

        if state["results"]:
            render()
            if state.get("status"):
                job.status.set_text(state["status"])
        else:
            with result_area:
                empty_state(
                    "Escribe un criterio y busca",
                    "Ejemplos: .jpg · informe · setup.exe — luego actua.",
                    icon="search",
                )
        btn_run.on_click(do_search)



@ui.page("/tools")
def page_tools() -> None:
    with page_frame("Herramientas", active_path="/tools"):
        section_title("Herramientas", "Utilidades inteligentes sobre el mismo motor local.")
        with ui.row().classes("gap-4 flex-wrap"):
            feature_card(
                "/tools/metadata",
                "Metadatos",
                "description",
                "Ver y editar creador, derechos, licencia… (PDF, JPEG, audio; con backup)",
            )
            feature_card(
                "/tools/disk",
                "Diagnostico de disco",
                "hard_drive",
                "Lectura + eventos Windows, SMART y salud del volumen (USB/disco)",
            )
            feature_card(
                "/tools/transfer",
                "Copiar / Mover",
                "drive_file_move",
                "Copia o mueve archivos y carpetas a otro destino (con dry-run)",
            )
            feature_card(
                "/tools/convert",
                "Convertir imagenes",
                "image",
                "Cualquier formato → PNG, JPG, WEBP… en carpeta aparte",
            )
            feature_card(
                "/tools/similar",
                "Imagenes similares",
                "photo_library",
                "Parecidas visualmente (redimensionadas/comprimidas), no solo identicas",
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
        selection_banner(tool="organize")
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
            def _work_dry(reporter):
                return engine.execute_actions_progressed(
                    actions, dry_run=True, progress=reporter
                )
            tx = await job.run(
                _work_dry, start_msg=f"Simulando {len(actions)} acciones…"
            )
            if tx is None:
                return
            ui.notify(
                f"Dry-run OK · {len(actions)} acciones · {tx.transaction_id[:8]}…",
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
                        def _work_real(reporter):
                            return engine.execute_actions_progressed(
                                actions, dry_run=False, progress=reporter
                            )
                        tx = await job.run(
                            _work_real, start_msg=f"Ejecutando {len(actions)} acciones…"
                        )
                        if tx is None:
                            return
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
        selection_banner(tool="cleanup")
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
                def _work_dry(reporter):
                    return engine.execute_actions_progressed(
                        actions, dry_run=True, progress=reporter
                    )
                tx = await job.run(
                    _work_dry, start_msg=f"Simulando {len(actions)} acciones…"
                )
                if tx is None:
                    return
                ui.notify(
                    f"Dry-run OK · {len(actions)} acciones · {tx.transaction_id[:8]}…",
                    type="positive",
                )

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
                        def _work_real(reporter):
                            return engine.execute_actions_progressed(
                                actions, dry_run=False, progress=reporter
                            )
                        tx = await job.run(
                            _work_real, start_msg=f"Ejecutando {len(actions)} acciones…"
                        )
                        if tx is None:
                            return
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
        selection_banner(tool="convert")
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
            "Detecta el formato real (cabecera). Omite: mismo formato, "
            "FileSage_converted, salidas ya existentes y nombres *_converted."
        ).classes("text-xs text-[#6b6b80] max-w-2xl")
        force = ui.checkbox("Forzar sobrescritura si el destino ya existe", value=False)
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
                    force=bool(force.value),
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
                def _work_dry(reporter):
                    return engine.execute_actions_progressed(
                        actions, dry_run=True, progress=reporter
                    )
                tx = await job.run(
                    _work_dry, start_msg=f"Simulando {len(actions)} acciones…"
                )
                if tx is None:
                    return
                ui.notify(
                    f"Dry-run OK · {len(actions)} acciones · {tx.transaction_id[:8]}…",
                    type="positive",
                )

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
                        def _work_real(reporter):
                            return engine.execute_actions_progressed(
                                actions, dry_run=False, progress=reporter
                            )
                        tx = await job.run(
                            _work_real, start_msg=f"Ejecutando {len(actions)} acciones…"
                        )
                        if tx is None:
                            return
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




@ui.page("/tools/similar")
def page_similar_images() -> None:
    """Imagenes visualmente similares (B2) — modo distinto a duplicados exactos."""
    engine = get_engine()
    saved = session_store.get_page_state("/tools/similar")
    state: dict = {
        "groups": saved.get("groups") or [],
        "status": saved.get("status", ""),
    }

    with page_frame("Imagenes similares", active_path="/tools"):
        section_title(
            "Imagenes similares",
            "Detecta fotos parecidas (redimensionadas, recomprimidas). "
            "No sustituye a Duplicados exactos: aqui el contenido puede diferir en bytes.",
        )
        folder = folder_field(label="Carpeta", value=saved.get("folder_path"))
        threshold = ui.number(
            "Umbral Hamming (menor = mas estricto)",
            value=float(saved.get("threshold") or 12),
            min=0,
            max=64,
            step=1,
        ).classes("max-w-xs")
        ui.label(
            "Guia: 0–5 casi iguales · 8–15 muy similares · 20+ permisivo (mas falsos positivos)."
        ).classes("text-xs text-[#6b6b80]")
        btn_run = ui.button("Buscar similares", icon="photo_library").props(
            "color=primary unelevated"
        )
        job = JobControls(page_route="/tools/similar")
        bind_busy_button(btn_run)
        actions = ui.row().classes("gap-2 flex-wrap")
        host = ui.column().classes("w-full gap-2")

        def _render() -> None:
            host.clear()
            actions.clear()
            groups = state["groups"]
            with host:
                if not groups:
                    empty_state(
                        "Sin grupos",
                        "Elige una carpeta con fotos y pulsa Buscar.",
                        icon="photo_library",
                    )
                    return
                for i, g in enumerate(groups[:80], 1):
                    # groups may be dicts after session restore or objects
                    if isinstance(g, dict):
                        files = g.get("files") or []
                        max_d = g.get("max_distance", "?")
                        wasted = int(g.get("wasted_size") or 0)
                        names = [Path(str(f)).name for f in files[:6]]
                        nfiles = len(files)
                    else:
                        files = list(g.files)
                        max_d = g.max_distance
                        wasted = g.wasted_size
                        names = [f.path.name for f in files[:6]]
                        nfiles = len(files)
                    with ui.card().classes("fs-card w-full p-3"):
                        ui.label(
                            f"Grupo {i} · {nfiles} imagenes · dist≤{max_d} · "
                            f"~{_fmt(wasted)} recuperables"
                        ).classes("font-medium")
                        ui.label(" · ".join(names)).classes(
                            "text-xs text-[#9898b0] break-all"
                        )
            with actions:
                ui.button(
                    "Simular → papelera (conserva la mas grande)",
                    on_click=lambda: do_clean(True),
                    icon="science",
                ).props("outline color=primary")
                ui.button(
                    "Enviar a papelera",
                    on_click=lambda: do_clean(False),
                    icon="delete",
                ).props("color=negative unelevated")

        def _serialize(groups):
            out = []
            for g in groups:
                out.append(
                    {
                        "files": [str(f.path) for f in g.files],
                        "max_distance": g.max_distance,
                        "wasted_size": g.wasted_size,
                        "threshold": g.threshold,
                    }
                )
            return out

        async def do_search() -> None:
            root = Path(folder.path_value() or "").expanduser()
            if not root.is_dir():
                ui.notify("Carpeta invalida", type="negative")
                return
            th = int(threshold.value or 12)
            host.clear()
            actions.clear()

            def work(reporter):
                return engine.find_similar_images(
                    root, threshold=th, progress=reporter
                )

            result = await job.run(
                work, start_msg="Buscando imagenes similares…"
            )
            if result is None:
                return
            scan, groups = result
            state["groups"] = groups
            status = f"{len(groups)} grupos · {scan.total_files} archivos escaneados"
            session_store.update_page_state(
                "/tools/similar",
                groups=_serialize(groups),
                status=status,
                folder_path=str(root),
                threshold=th,
            )
            job.status.set_text(status)
            ui.notify(status, type="positive")
            _render()

        async def do_clean(dry: bool) -> None:
            groups = state["groups"]
            if not groups:
                ui.notify("Primero busca", type="warning")
                return
            # Reconstruir objetos minimos si vienen de sesion
            from filesage.domain.models import FileInfo
            from filesage.services.similar_images import SimilarImageGroup

            rebuilt = []
            for g in groups:
                if isinstance(g, SimilarImageGroup):
                    rebuilt.append(g)
                    continue
                files = []
                for p in g.get("files") or []:
                    path = Path(p)
                    try:
                        st = path.stat()
                        files.append(
                            FileInfo(
                                path=path,
                                size=st.st_size,
                                mtime=st.st_mtime,
                                is_symlink=path.is_symlink(),
                            )
                        )
                    except OSError:
                        continue
                if len(files) >= 2:
                    rebuilt.append(
                        SimilarImageGroup(
                            fingerprint="",
                            files=tuple(files),
                            max_distance=int(g.get("max_distance") or 0),
                            threshold=int(g.get("threshold") or 12),
                        )
                    )
            plans = engine.plan_trash_similar_images(rebuilt, keep_largest=True)
            if not plans:
                ui.notify("Nada que enviar", type="info")
                return

            async def run_batch(dry_run: bool) -> None:
                def work(reporter):
                    return engine.execute_actions_progressed(
                        plans, dry_run=dry_run, progress=reporter
                    )

                tx = await job.run(
                    work,
                    start_msg=f"{'Simulando' if dry_run else 'Papelera'} {len(plans)}…",
                )
                if tx is None:
                    return
                ok = sum(1 for a in tx.actions if a.success)
                ui.notify(f"{ok}/{len(tx.actions)} OK", type="positive")

            if dry:
                await run_batch(True)
            else:
                paths = [a.source for a in plans]
                await confirm_trash_preview(
                    paths,
                    title="Papelera — imagenes similares",
                    on_confirm=lambda: run_batch(False),
                )

        if state["groups"]:
            _render()
            if state.get("status"):
                job.status.set_text(state["status"])
        else:
            with host:
                empty_state(
                    "Busca imagenes parecidas",
                    "Ideal para capturas, exports y fotos redimensionadas.",
                    icon="photo_library",
                )
        btn_run.on_click(do_search)









@ui.page("/tools/metadata")
def page_metadata() -> None:
    """Paneles por tipo (PDF / JPEG / Audio) con metadatos actuales precargados."""
    from filesage.services.metadata_editor import detect_kind, read_metadata
    from filesage.presentation.web.path_picker import pick_files_dialog
    from filesage.presentation.web.context import get_workspace

    engine = get_engine()
    saved = session_store.get_page_state("/tools/metadata")
    state: dict = {
        "paths": list(saved.get("paths") or []),
        "snaps": {},  # path -> snapshot dict
    }

    # Campos por tipo (etiquetas de UI)
    TYPE_FIELDS = {
        "pdf": [
            ("title", "Titulo"),
            ("author", "Autor"),
            ("creator", "Creador / Producer"),
            ("subject", "Asunto"),
            ("copyright", "Derechos de autor"),
            ("license", "Licencia / Keywords"),
            ("comment", "Comentario"),
        ],
        "jpeg": [
            ("title", "Descripcion / Title"),
            ("creator", "Artist / Creador"),
            ("author", "Autor"),
            ("copyright", "Copyright"),
            ("license", "Licencia"),
            ("comment", "Comentario EXIF"),
        ],
        "audio": [
            ("title", "Titulo"),
            ("creator", "Artista"),
            ("author", "Artista (alt)"),
            ("subject", "Album"),
            ("copyright", "Copyright"),
            ("license", "Licencia"),
            ("comment", "Comentario"),
        ],
    }
    TYPE_META = {
        "pdf": ("PDF", "picture_as_pdf", "#e57373"),
        "jpeg": ("JPEG", "image", "#64b5f6"),
        "audio": ("Audio", "audio_file", "#81c784"),
    }

    with page_frame("Metadatos", active_path="/tools"):
        selection_banner(tool="metadata")
        section_title(
            "Metadatos de archivos",
            "Cada tipo tiene su panel. Al elegir archivos se leen los valores actuales; "
            "cambia solo lo que quieras y simula antes de aplicar.",
        )

        # ---- Seleccion ----
        with ui.row().classes("gap-2 flex-wrap items-center"):
            async def _browse_files() -> None:
                try:
                    start_dir = str(get_workspace())
                except Exception:
                    start_dir = None
                chosen = await pick_files_dialog(start_dir)
                if not chosen:
                    ui.notify(
                        "No se abrio el dialogo o no hubo seleccion.",
                        type="warning",
                    )
                    return
                merged = list(
                    dict.fromkeys(state["paths"] + [str(Path(c)) for c in chosen])
                )
                state["paths"] = merged
                session_store.update_page_state("/tools/metadata", paths=merged)
                await _reload_all()

            ui.button(
                "Elegir archivos…",
                icon="folder_open",
                on_click=_browse_files,
            ).props("unelevated color=primary")

            def _from_selection() -> None:
                paths = []
                try:
                    bag = session_store.get_selection()
                    raw = getattr(bag, "paths", None) or (
                        bag.get("paths") if isinstance(bag, dict) else []
                    )
                    paths = [str(p) for p in (raw or [])]
                except Exception:
                    paths = []
                if not paths:
                    ui.notify("No hay seleccion desde Buscar", type="warning")
                    return
                state["paths"] = list(dict.fromkeys(state["paths"] + paths))
                session_store.update_page_state(
                    "/tools/metadata", paths=state["paths"]
                )
                ui.timer(0.05, lambda: _reload_all_sync(), once=True)

            ui.button(
                "Usar seleccion de Buscar",
                icon="playlist_add",
                on_click=_from_selection,
            ).props("outline")

            def _clear() -> None:
                state["paths"] = []
                state["snaps"] = {}
                session_store.update_page_state("/tools/metadata", paths=[])

                def _after_clear() -> None:
                    try:
                        _rebuild_panels()
                    except Exception:
                        pass
                    try:
                        ui.notify("Paneles eliminados", type="info", position="top")
                    except Exception:
                        pass

                ui.timer(0.05, _after_clear, once=True)

            ui.button(
                "Quitar todos los paneles",
                icon="clear_all",
                on_click=_clear,
            ).props("outline dense color=negative")

        do_backup = ui.checkbox(
            "Backup (.filesage_meta.bak) al escribir",
            value=bool(saved.get("backup", True)),
        )
        job = JobControls(page_route="/tools/metadata")
        panels_host = ui.column().classes("w-full gap-3")

        # Referencias a inputs: kind -> path_str -> field -> input widget
        editors: dict = {}

        def _paths() -> list[Path]:
            return [Path(p).expanduser() for p in state["paths"] if str(p).strip()]

        def _load_snaps(paths: list[Path]) -> None:
            state["snaps"] = {}
            for p in paths:
                if not p.is_file():
                    continue
                snap = engine.read_file_metadata(p)
                state["snaps"][str(p)] = {
                    "path": str(p),
                    "kind": snap.kind,
                    "error": snap.error,
                    "fields": dict(snap.fields or {}),
                }

        def _remove_paths(to_remove: list[str]) -> None:
            """Quita archivos y reconstruye fuera del slot del boton (evita RuntimeError NiceGUI)."""
            drop = set(to_remove)
            n = len(drop)
            state["paths"] = [p for p in state["paths"] if p not in drop]
            for p in drop:
                state["snaps"].pop(p, None)
            session_store.update_page_state("/tools/metadata", paths=state["paths"])

            # El boton vive dentro del panel que se borra: diferir clear/notify
            def _after_remove() -> None:
                try:
                    _rebuild_panels()
                except Exception:
                    pass
                try:
                    ui.notify(
                        f"Eliminado de la lista: {n}",
                        type="info",
                        position="top",
                    )
                except Exception:
                    pass

            ui.timer(0.05, _after_remove, once=True)

        def _rebuild_panels() -> None:
            editors.clear()
            panels_host.clear()
            paths = [p for p in _paths() if p.is_file()]
            by_kind: dict[str, list[Path]] = {"pdf": [], "jpeg": [], "audio": []}
            unsupported: list[Path] = []
            for p in paths:
                k = detect_kind(p)
                if k in by_kind:
                    by_kind[k].append(p)
                else:
                    unsupported.append(p)

            with panels_host:
                if not paths:
                    empty_state(
                        "Sin archivos",
                        "Pulsa «Elegir archivos…» o trae la seleccion de Buscar. "
                        "Se leeran los metadatos al cargar.",
                        icon="description",
                    )
                    return

                if unsupported:
                    with ui.card().classes("fs-card w-full p-3"):
                        ui.label(
                            f"Omitidos ({len(unsupported)}) — formato no editable aqui"
                        ).classes("text-sm text-warning")
                        for p in unsupported[:8]:
                            ui.label(p.name).classes("text-xs text-[#6b6b80]")

                for kind, items in by_kind.items():
                    label, icon, color = TYPE_META[kind]
                    fields_spec = TYPE_FIELDS[kind]
                    with ui.card().classes("fs-card w-full p-4 gap-2"):
                        with ui.row().classes("items-center gap-2 w-full"):
                            ui.icon(icon).style(f"color:{color}")
                            ui.label(f"{label}").classes("text-lg font-semibold")
                            ui.badge(str(len(items))).props("color=primary")
                            ui.space()
                            ui.label(
                                "Valores actuales · edita solo lo necesario"
                            ).classes("text-xs text-[#6b6b80]")

                            def _drop_kind(kind_paths=None):
                                # kind_paths bound below
                                pass

                            ui.button(
                                "Quitar panel",
                                icon="delete_outline",
                                on_click=lambda it=list(items): _remove_paths(
                                    [str(x) for x in it]
                                ),
                            ).props("flat dense color=negative")

                        if not items:
                            ui.label("Ningun archivo de este tipo.").classes(
                                "text-sm text-[#6b6b80]"
                            )
                            continue

                        editors.setdefault(kind, {})
                        for p in items:
                            key = str(p)
                            snap = state["snaps"].get(key) or {}
                            cur = snap.get("fields") or {}
                            err = snap.get("error")
                            editors[kind].setdefault(key, {})

                            with ui.expansion(
                                p.name,
                                icon=icon,
                                value=len(items) == 1,
                            ).classes("w-full"):
                                with ui.row().classes(
                                    "w-full items-center gap-2 mb-1"
                                ):
                                    ui.label(key).classes(
                                        "text-xs text-[#6b6b80] break-all flex-grow"
                                    )
                                    ui.button(
                                        "Quitar archivo",
                                        icon="close",
                                        on_click=lambda k=key: _remove_paths([k]),
                                    ).props("flat dense round color=negative")
                                if err:
                                    ui.label(f"Error al leer: {err}").classes(
                                        "text-negative text-sm"
                                    )
                                elif not any(cur.values()):
                                    ui.label(
                                        "Sin metadatos previos (campos vacios)."
                                    ).classes("text-xs text-[#6b6b80]")

                                with ui.grid(columns=2).classes(
                                    "w-full gap-2 max-w-3xl"
                                ):
                                    for field_id, field_label in fields_spec:
                                        current_val = cur.get(field_id) or ""
                                        with ui.column().classes("gap-0"):
                                            ui.label(field_label).classes(
                                                "text-xs text-[#9898b0]"
                                            )
                                            if current_val:
                                                ui.label(
                                                    f"Actual: {current_val[:120]}"
                                                ).classes(
                                                    "text-xs text-[#6b6b80] truncate"
                                                )
                                            inp = ui.input(
                                                value=current_val
                                            ).classes("w-full").props(
                                                "outlined dense "
                                                "placeholder=\"(sin cambio si lo dejas igual)\""
                                            )
                                            editors[kind][key][field_id] = {
                                                "input": inp,
                                                "original": current_val,
                                            }

                                def _revert_file(k=key, kd=kind):
                                    fmap = editors.get(kd, {}).get(k, {})
                                    for _fid, meta in fmap.items():
                                        orig = meta.get("original") or ""
                                        try:
                                            meta["input"].set_value(orig)
                                        except Exception:
                                            meta["input"].value = orig
                                    ui.notify("Valores restaurados", type="info")

                                ui.button(
                                    "Restaurar valores de este archivo",
                                    icon="undo",
                                    on_click=_revert_file,
                                ).props("flat dense")

                        with ui.row().classes("gap-2 mt-2 flex-wrap"):
                            def _make_handlers(k=kind, file_items=items):
                                async def run_kind(dry: bool) -> None:
                                    updates_per_file: list[tuple[Path, dict]] = []
                                    for fp in file_items:
                                        fk = str(fp)
                                        fields_map = editors.get(k, {}).get(fk, {})
                                        upd = {}
                                        for fid, meta in fields_map.items():
                                            new_v = (meta["input"].value or "").strip()
                                            orig = (meta.get("original") or "").strip()
                                            # Solo enviar si el usuario cambio el valor
                                            if new_v != orig:
                                                upd[fid] = new_v
                                        if upd:
                                            updates_per_file.append((fp, upd))
                                    if not updates_per_file:
                                        ui.notify(
                                            f"No hay cambios en {k.upper()}",
                                            type="info",
                                        )
                                        return

                                    def work(reporter):
                                        results = []
                                        total = max(1, len(updates_per_file))
                                        for i, (fp, upd) in enumerate(updates_per_file):
                                            reporter.report(
                                                f"{k}: {fp.name}",
                                                i / total,
                                            )
                                            reporter.check()
                                            from filesage.services.metadata_editor import (
                                                apply_metadata,
                                            )

                                            results.append(
                                                apply_metadata(
                                                    fp,
                                                    upd,
                                                    dry_run=dry,
                                                    backup=bool(do_backup.value),
                                                )
                                            )
                                        reporter.report("Listo", 1.0)
                                        return results

                                    res = await job.run(
                                        work,
                                        start_msg=(
                                            f"Simulando {k.upper()}…"
                                            if dry
                                            else f"Escribiendo {k.upper()}…"
                                        ),
                                    )
                                    if res is None:
                                        return
                                    ok = sum(1 for r in res if r.success)
                                    ui.notify(
                                        f"{k.upper()}: {ok}/{len(res)} OK",
                                        type="positive"
                                        if ok == len(res)
                                        else "warning",
                                    )
                                    if not dry:
                                        _load_snaps([p for p, _ in updates_per_file])
                                        _rebuild_panels()

                                return run_kind

                            handlers = _make_handlers()
                            ui.button(
                                f"Simular solo {label}",
                                icon="science",
                                on_click=lambda h=handlers: h(True),
                            ).props("outline dense color=primary")
                            ui.button(
                                f"Aplicar solo {label}",
                                icon="save",
                                on_click=lambda h=handlers: h(False),
                            ).props("unelevated dense color=primary")

                # Accion global
                with ui.row().classes("gap-2 flex-wrap mt-1"):
                    async def run_all(dry: bool) -> None:
                        all_jobs: list[tuple[Path, dict]] = []
                        for kind, fmap in editors.items():
                            for fpath, fields_map in fmap.items():
                                upd = {}
                                for fid, meta in fields_map.items():
                                    new_v = (meta["input"].value or "").strip()
                                    orig = (meta.get("original") or "").strip()
                                    if new_v != orig:
                                        upd[fid] = new_v
                                if upd:
                                    all_jobs.append((Path(fpath), upd))
                        if not all_jobs:
                            ui.notify("No hay cambios en ningun panel", type="info")
                            return

                        def work(reporter):
                            from filesage.services.metadata_editor import apply_metadata

                            results = []
                            total = max(1, len(all_jobs))
                            for i, (fp, upd) in enumerate(all_jobs):
                                reporter.report(fp.name, i / total)
                                reporter.check()
                                results.append(
                                    apply_metadata(
                                        fp,
                                        upd,
                                        dry_run=dry,
                                        backup=bool(do_backup.value),
                                    )
                                )
                            reporter.report("Listo", 1.0)
                            return results

                        res = await job.run(
                            work,
                            start_msg="Simulando todo…" if dry else "Aplicando todo…",
                        )
                        if res is None:
                            return
                        ok = sum(1 for r in res if r.success)
                        ui.notify(
                            f"Global: {ok}/{len(res)} OK",
                            type="positive" if ok == len(res) else "warning",
                        )
                        if not dry:
                            _load_snaps(_paths())
                            _rebuild_panels()

                    ui.button(
                        "Simular todos los tipos",
                        icon="science",
                        on_click=lambda: run_all(True),
                    ).props("outline")
                    ui.button(
                        "Aplicar todos los tipos",
                        icon="save",
                        on_click=lambda: run_all(False),
                    ).props("color=primary unelevated")

        def _reload_all_sync() -> None:
            paths = [p for p in _paths() if p.is_file()]
            if not paths:
                _rebuild_panels()
                return
            _load_snaps(paths)
            _rebuild_panels()
            ui.notify(f"Metadatos leidos: {len(paths)} archivo(s)", type="positive")

        async def _reload_all() -> None:
            def work(reporter):
                paths = [p for p in _paths() if p.is_file()]
                total = max(1, len(paths))
                out = {}
                for i, p in enumerate(paths):
                    reporter.report(f"Leyendo {p.name}", i / total)
                    reporter.check()
                    snap = engine.read_file_metadata(p)
                    out[str(p)] = {
                        "path": str(p),
                        "kind": snap.kind,
                        "error": snap.error,
                        "fields": dict(snap.fields or {}),
                    }
                reporter.report("Listo", 1.0)
                return out

            result = await job.run(work, start_msg="Leyendo metadatos…")
            if result is None:
                return
            state["snaps"] = result
            _rebuild_panels()

        # Carga inicial si habia paths en sesion
        if state["paths"]:
            ui.timer(0.1, _reload_all_sync, once=True)
        else:
            _rebuild_panels()



@ui.page("/tools/disk")
def page_disk_diag() -> None:
    """Diagnostico rapido de discos y unidades extraibles."""
    from filesage.services.disk_diagnostics import diagnose_path

    saved = session_store.get_page_state("/tools/disk")
    with page_frame("Diagnostico de disco", active_path="/tools"):
        section_title(
            "Diagnostico de disco / USB",
            "Prueba de lectura + señales de Windows (salud del volumen, PhysicalDisk, "
            "SMART si existe y eventos disk/NTFS). Si tambien fallas copiando a mano, "
            "el problema es del sistema o del hardware, no solo de FileSage.",
        )
        folder = folder_field(
            label="Unidad o carpeta a comprobar",
            value=saved.get("path"),
        )
        btn = ui.button("Diagnosticar", icon="health_and_safety").props(
            "color=primary unelevated"
        )
        job = JobControls(page_route="/tools/disk")
        bind_busy_button(btn)
        host = ui.column().classes("w-full gap-2")

        async def run() -> None:
            path = (folder.path_value() or "").strip()
            if not path:
                ui.notify("Indica una unidad (ej. F:\\) o carpeta", type="warning")
                return

            def work(reporter):
                reporter.report("Comprobando acceso y lectura…", 0.2)
                report = diagnose_path(path)
                reporter.report(report.summary, 1.0)
                return report

            report = await job.run(work, start_msg="Diagnostico…")
            if report is None:
                return
            session_store.update_page_state("/tools/disk", path=path)
            host.clear()
            with host:
                ui.label(report.summary).classes("text-lg font-medium")
                if report.free_gb is not None:
                    ui.label(
                        f"Espacio: {report.free_gb:.1f} GB libres / {report.total_gb:.1f} GB"
                    ).classes("text-sm text-[#9898b0]")
                if report.read_mbs is not None:
                    ui.label(
                        f"Lectura muestra: ~{report.read_mbs:.1f} MB/s · "
                        f"{report.sample_files} archivos · {report.sample_errors} errores"
                    ).classes("text-sm text-[#9898b0]")
                for f in report.findings:
                    color = {
                        "ok": "positive",
                        "warn": "warning",
                        "error": "negative",
                        "info": "info",
                    }.get(f.level, "info")
                    with ui.card().classes("fs-card w-full p-3"):
                        ui.badge(f.level.upper()).props(f"color={color}")
                        ui.label(f.title).classes("font-medium")
                        ui.label(f.detail).classes("text-sm text-[#9898b0] break-all")
                with ui.row().classes("gap-2 mt-2"):
                    ui.button(
                        "Ir a Copiar / Mover",
                        on_click=lambda: ui.navigate.to("/tools/transfer"),
                        icon="drive_file_move",
                    ).props("outline")
            ui.notify(report.summary, type="positive" if "sin errores" in report.summary.lower() else "warning")

        with host:
            empty_state(
                "Comprueba un USB o disco antes de copias grandes",
                "Si hay errores de lectura, copia por carpetas pequeñas y revisa el disco.",
                icon="hard_drive",
            )
        btn.on_click(run)



@ui.page("/tools/transfer")
def page_transfer() -> None:
    """Copiar o mover archivos y carpetas completas a un destino."""
    from datetime import datetime

    from filesage.domain.models import ActionRecord, ActionType
    from filesage.infrastructure.storage import new_action_id

    engine = get_engine()
    saved = session_store.get_page_state("/tools/transfer")

    # Seleccion previa (Buscar) o sesion
    initial_sources: list[str] = []
    if hasattr(session_store, "get_selection"):
        try:
            bag = session_store.get_selection()
            if bag:
                paths = getattr(bag, "paths", None) or (
                    bag.get("paths") if isinstance(bag, dict) else None
                )
                if paths:
                    initial_sources = [str(x) for x in paths]
        except Exception:
            pass
    if not initial_sources:
        initial_sources = [str(x) for x in (saved.get("sources") or [])]

    state: dict = {
        "sources": list(initial_sources),
        "plans": saved.get("plans") or [],
        "status": saved.get("status") or "",
    }

    with page_frame("Copiar / Mover", active_path="/tools"):
        selection_banner(tool="transfer")
        section_title(
            "Copiar o mover archivos y carpetas",
            "Puedes copiar/mover **carpetas completas** (con todo su contenido) o archivos sueltos. "
            "Simula siempre antes de aplicar. Los movimientos se pueden deshacer desde Historial.",
        )

        mode = ui.toggle(
            {"copy": "Copiar", "move": "Mover"},
            value=saved.get("mode") or "copy",
        ).props("no-caps")
        conflict = ui.select(
            {
                "rename": "Si existe: renombrar (nombre_1)",
                "skip": "Si existe: omitir",
                "overwrite": "Si existe: sobrescribir",
            },
            value=saved.get("on_conflict") or "skip",
            label="Conflictos de nombre",
        ).classes("max-w-md")
        expand_contents = ui.checkbox(
            "Copiar/mover el CONTENIDO de carpetas y unidades (recomendado)",
            value=bool(saved.get("expand_dir_contents", True)),
        )
        ui.label(
            "Con una unidad (F:) o carpeta: se listan sus elementos y se envían al destino. "
            "«Omitir» salta lo que ya exista en el destino."
        ).classes("text-xs text-[#6b6b80] max-w-2xl")

        # --- Origenes ---
        ui.label("1. Origenes (archivos o carpetas completas)").classes(
            "text-sm font-medium mt-3"
        )
        sources_input = ui.textarea(
            label="Lista de origenes (una ruta por linea)",
            value="\n".join(state["sources"]),
            placeholder=r"Ejemplos:" + "\n"
            r"F:\Fotos\Vacaciones" + "\n"
            r"C:\Users\Public\documento.pdf",
        ).classes("w-full max-w-2xl").props("outlined autogrow")

        with ui.row().classes("gap-2 flex-wrap items-end w-full max-w-2xl"):
            origin_picker = folder_field(label="Elegir carpeta de origen")

            def _add_origin_folder() -> None:
                raw = (origin_picker.path_value() or "").strip().strip('"')
                if not raw:
                    ui.notify("Elige una carpeta con Examinar…", type="warning")
                    return
                path = Path(raw)
                # Normalizar raíces de unidad Windows: F: -> F:\
                if len(raw) == 2 and raw[1] == ":":
                    path = Path(raw + "\\")
                    raw = str(path)
                if not path.exists():
                    ui.notify(f"No existe: {raw}", type="negative")
                    return
                cur = [
                    ln.strip()
                    for ln in (sources_input.value or "").splitlines()
                    if ln.strip()
                ]
                if raw not in cur and str(path) not in cur:
                    cur.append(str(path))
                sources_input.value = "\n".join(cur)
                kind = "carpeta" if path.is_dir() else "archivo"
                ui.notify(f"Añadido ({kind}): {path}", type="positive")

            ui.button(
                "Añadir a la lista",
                on_click=_add_origin_folder,
                icon="add",
            ).props("outline color=primary")

            def _from_selection() -> None:
                paths: list[str] = []
                if hasattr(session_store, "get_selection"):
                    try:
                        bag = session_store.get_selection()
                        raw_paths = getattr(bag, "paths", None) or (
                            bag.get("paths") if isinstance(bag, dict) else []
                        )
                        paths = [str(p) for p in (raw_paths or [])]
                    except Exception:
                        paths = []
                if not paths:
                    ui.notify(
                        "No hay selección. En Buscar marca archivos y envía a Copiar/Mover.",
                        type="warning",
                    )
                    return
                cur = [
                    ln.strip()
                    for ln in (sources_input.value or "").splitlines()
                    if ln.strip()
                ]
                for pth in paths:
                    if pth not in cur:
                        cur.append(pth)
                sources_input.value = "\n".join(cur)
                ui.notify(f"{len(paths)} rutas desde Buscar", type="positive")

            ui.button(
                "Usar selección de Buscar",
                on_click=_from_selection,
                icon="playlist_add",
            ).props("outline")

        # --- Destino ---
        ui.label("2. Carpeta destino").classes("text-sm font-medium mt-4")
        dest = folder_field(
            label="Destino (carpeta donde copiar/mover)",
            value=saved.get("dest_path"),
        )

        with ui.row().classes("gap-2 flex-wrap items-center"):
            btn_plan = ui.button("Preparar plan", icon="playlist_add_check").props(
                "color=primary unelevated"
            )

            def _diag_origin() -> None:
                raw = (origin_picker.path_value() or "").strip()
                lines = [
                    ln.strip()
                    for ln in (sources_input.value or "").splitlines()
                    if ln.strip()
                ]
                target = raw or (lines[0] if lines else "")
                if target:
                    session_store.update_page_state("/tools/disk", path=target)
                ui.navigate.to("/tools/disk")

            ui.button(
                "Diagnosticar origen",
                on_click=_diag_origin,
                icon="health_and_safety",
            ).props("outline")
        ui.label(
            "Si la barra se queda mucho rato en una carpeta, es normal: se está copiando "
            "archivo a archivo (USB lentos o con errores tardan más). Cancela si el disco se desconecta."
        ).classes("text-xs text-[#6b6b80] max-w-2xl")
        job = JobControls(page_route="/tools/transfer")
        bind_busy_button(btn_plan)
        summary = ui.label(state.get("status") or "").classes("text-sm text-[#9898b0]")
        actions = ui.row().classes("gap-2 flex-wrap")
        host = ui.column().classes("w-full gap-2")

        def _normalize_path(raw: str) -> Path:
            raw = raw.strip().strip('"')
            if len(raw) == 2 and raw[1] == ":":
                raw = raw + "\\"
            return Path(raw).expanduser()

        def _collect_sources() -> list[Path]:
            """Origenes de la lista + campo de carpeta si tiene valor."""
            lines = [
                ln.strip()
                for ln in (sources_input.value or "").splitlines()
                if ln.strip()
            ]
            # Auto-incluir el picker de origen si el usuario olvido pulsar Añadir
            picked = (origin_picker.path_value() or "").strip().strip('"')
            if picked and picked not in lines:
                lines.append(picked)
            out: list[Path] = []
            for ln in lines:
                pth = _normalize_path(ln)
                if pth.exists():
                    out.append(pth)
            return out

        def _render_plan() -> None:
            host.clear()
            actions.clear()
            plans = state.get("plans") or []
            with host:
                if not plans:
                    empty_state(
                        "Sin plan",
                        "Añade carpetas o archivos de origen y un destino.",
                        icon="drive_file_move",
                    )
                    return
                for row in plans[:300]:
                    if isinstance(row, dict):
                        src, dst, kind = (
                            row.get("source"),
                            row.get("dest"),
                            row.get("type"),
                        )
                    else:
                        src = str(row.source)
                        dst = str(row.destination or "")
                        kind = row.action_type.value
                    src_p = Path(str(src))
                    badge = "📁 carpeta" if src_p.is_dir() else "📄 archivo"
                    with ui.card().classes("fs-card w-full p-3"):
                        ui.label(
                            f"{(kind or '').upper()} · {badge} · {src_p.name}"
                        ).classes("font-medium")
                        ui.label(str(src)).classes("text-xs text-[#6b6b80] break-all")
                        ui.label(f"→ {dst}").classes("text-xs text-primary break-all")
            with actions:
                ui.button(
                    "Simular", on_click=lambda: do_exec(True), icon="science"
                ).props("outline color=primary")
                ui.button(
                    "Ejecutar de verdad",
                    on_click=lambda: do_exec(False),
                    icon="play_arrow",
                ).props("color=primary unelevated")

        def _serialize(plans):
            return [
                {
                    "source": str(a.source),
                    "dest": str(a.destination or ""),
                    "type": a.action_type.value,
                }
                for a in plans
            ]

        def build_plan() -> None:
            srcs = _collect_sources()
            dest_raw = (dest.path_value() or "").strip()
            dest_p = _normalize_path(dest_raw) if dest_raw else None

            if not srcs:
                # Diagnostico util
                lines = [
                    ln.strip()
                    for ln in (sources_input.value or "").splitlines()
                    if ln.strip()
                ]
                picked = (origin_picker.path_value() or "").strip()
                if not lines and not picked:
                    ui.notify(
                        "Añade al menos un origen: escribe una ruta, usa Examinar y «Añadir a la lista», o trae la selección de Buscar.",
                        type="warning",
                    )
                else:
                    ui.notify(
                        "Las rutas indicadas no existen o no son accesibles. Revisa unidades y permisos.",
                        type="negative",
                    )
                return
            if not dest_p or not dest_p.is_dir():
                ui.notify(
                    "El destino debe ser una carpeta existente (usa Examinar…).",
                    type="negative",
                )
                return

            # Actualizar textarea con origenes resueltos (feedback)
            sources_input.value = "\n".join(str(s) for s in srcs)

            m = str(mode.value or "copy")
            plans = engine.plan_transfer(
                srcs,
                dest_p,
                mode=m,
                on_conflict=str(conflict.value or "skip"),
                expand_dir_contents=bool(expand_contents.value),
            )
            if not plans:
                ui.notify(
                    "No se generaron acciones: todo ya existe en el destino (omitir), "
                    "la carpeta está vacía, o no se pudo leer el origen. "
                    "Prueba «renombrar» si quieres forzar copias con otro nombre.",
                    type="warning",
                )
                return

            n_dirs = sum(1 for s in srcs if s.is_dir())
            n_files = sum(1 for s in srcs if s.is_file())
            state["plans"] = plans
            state["sources"] = [str(s) for s in srcs]
            status = (
                f"{len(plans)} acciones · {m} · "
                f"{n_dirs} carpeta(s), {n_files} archivo(s)"
            )
            state["status"] = status
            session_store.update_page_state(
                "/tools/transfer",
                sources=state["sources"],
                plans=_serialize(plans),
                status=status,
                dest_path=str(dest_p),
                mode=m,
                on_conflict=str(conflict.value or "skip"),
                expand_dir_contents=bool(expand_contents.value),
            )
            summary.set_text(status)
            job.status.set_text(status)
            ui.notify(status, type="positive")
            _render_plan()

        async def do_exec(dry: bool) -> None:
            plans = state.get("plans") or []
            if not plans:
                ui.notify("Prepara un plan primero", type="warning")
                return

            rebuilt: list[ActionRecord] = []
            for item in plans:
                if isinstance(item, ActionRecord):
                    rebuilt.append(item)
                    continue
                at = (
                    ActionType.MOVE
                    if (item.get("type") == "move")
                    else ActionType.COPY
                )
                rebuilt.append(
                    ActionRecord(
                        action_id=new_action_id(),
                        action_type=at,
                        source=Path(item["source"]),
                        destination=Path(item["dest"]) if item.get("dest") else None,
                        timestamp=datetime.now(),
                        success=False,
                        message="",
                        dry_run=True,
                        metadata={"from": "transfer"},
                    )
                )

            async def run_batch(dry_run: bool) -> None:
                def work(reporter):
                    return engine.execute_actions_progressed(
                        rebuilt, dry_run=dry_run, progress=reporter
                    )

                tx = await job.run(
                    work,
                    start_msg=f"{'Simulando' if dry_run else 'Ejecutando'} {len(rebuilt)}…",
                )
                if tx is None:
                    return
                ok = sum(1 for a in tx.actions if a.success)
                fail = [a for a in tx.actions if not a.success]
                incomplete = [
                    a for a in tx.actions
                    if a.success and a.message and (
                        "omitidos" in a.message or "Incompletos" in a.message
                    )
                ]
                msg = (
                    f"{'Simulación' if dry_run else 'Hecho'}: "
                    f"{ok}/{len(tx.actions)} OK · {tx.transaction_id[:8]}…"
                )
                if fail:
                    msg += f" · {len(fail)} fallaron"
                if incomplete:
                    msg += f" · {len(incomplete)} con archivos omitidos"
                job.status.set_text(msg)
                summary.set_text(msg)
                # Detalle de incompletos / fallos
                details = []
                for a in (fail + incomplete)[:8]:
                    details.append(f"• {Path(a.source).name}: {(a.message or '')[:120]}")
                if details:
                    with host:
                        with ui.card().classes("fs-card w-full p-3 mt-2"):
                            ui.label("Incompletos / omitidos / errores").classes(
                                "font-medium text-warning"
                            )
                            for line in details:
                                ui.label(line).classes("text-xs text-[#9898b0] break-all")
                            ui.label(
                                "Los archivos problemáticos se saltaron; el resto se copió. "
                                "Revisa el USB si hay muchos omitidos."
                            ).classes("text-xs mt-1")
                ui.notify(msg, type="positive" if not fail else "warning")

            if dry:
                await run_batch(True)
                return

            paths = [str(a.source) for a in rebuilt]
            label = "MOVER" if str(mode.value) == "move" else "COPIAR"

            async def confirm() -> None:
                await run_batch(False)

            await confirm_trash_preview(
                paths,
                title=f"Confirmar {label} (archivos y carpetas)",
                confirm_word="OK",
                on_confirm=confirm,
            )

        if state.get("plans"):
            _render_plan()
        else:
            with host:
                empty_state(
                    "Carpetas completas o archivos sueltos",
                    "1) Añade orígenes  →  2) Elige destino  →  3) Preparar plan  →  Simular / Ejecutar",
                    icon="drive_file_move",
                )
        btn_plan.on_click(build_plan)


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
        section_title(
            "Historial",
            "Registro de acciones. Rollback automatico solo para MOVE/COPY; "
            "TRASH/DELETE se recuperan desde la papelera del sistema.",
        )
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
    use_hash_cache = ui.switch(
        "Cache de hashes (rescaneos mas rapidos)",
        value=getattr(s.hashing, "use_cache", True),
    )
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
        s.hashing.use_cache = bool(use_hash_cache.value)
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
