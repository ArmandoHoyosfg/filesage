"""Estado de sesion web: jobs globales + datos por seccion + seleccion compartida."""

from __future__ import annotations

from typing import Any, Callable

_page_state: dict[str, dict[str, Any]] = {}

_job: dict[str, Any] = {
    "running": False,
    "page": "",
    "label": "",
    "message": "",
    "fraction": None,
    "finished_notice": None,
}

# Seleccion compartida entre herramientas (rutas absolutas)
_selection: dict[str, Any] = {
    "paths": [],  # list[str]
    "source": "",  # p.ej. "search"
    "label": "",
}

_listeners: list[Callable[[], None]] = []


def get_page_state(route: str) -> dict[str, Any]:
    return _page_state.setdefault(route, {})


def update_page_state(route: str, **kwargs: Any) -> None:
    st = get_page_state(route)
    st.update(kwargs)


def clear_page_state(route: str) -> None:
    _page_state.pop(route, None)


def job_is_running() -> bool:
    return bool(_job["running"])


def job_info() -> dict[str, Any]:
    return dict(_job)


def job_start(page: str, label: str) -> None:
    _job["running"] = True
    _job["page"] = page
    _job["label"] = label
    _job["message"] = label
    _job["fraction"] = None
    _job["finished_notice"] = None
    _notify_listeners()


def job_progress(message: str, fraction: float | None) -> None:
    _job["message"] = message
    _job["fraction"] = fraction
    _notify_listeners()


def job_finish(notice: str | None = None) -> None:
    page = _job.get("page") or ""
    _job["running"] = False
    _job["message"] = ""
    _job["fraction"] = None
    if notice:
        _job["finished_notice"] = notice
        if page:
            update_page_state(page, last_notice=notice)
    _notify_listeners()


def consume_finished_notice() -> str | None:
    n = _job.get("finished_notice")
    _job["finished_notice"] = None
    return n


def set_selection(
    paths: list[str],
    *,
    source: str = "",
    label: str = "",
) -> None:
    """Publica rutas para que otras herramientas las consuman."""
    cleaned = []
    seen: set[str] = set()
    for p in paths:
        s = str(p).strip()
        if s and s not in seen:
            seen.add(s)
            cleaned.append(s)
    _selection["paths"] = cleaned
    _selection["source"] = source
    _selection["label"] = label or f"{len(cleaned)} archivos"
    _notify_listeners()


def get_selection() -> dict[str, Any]:
    return {
        "paths": list(_selection.get("paths") or []),
        "source": _selection.get("source") or "",
        "label": _selection.get("label") or "",
    }


def clear_selection() -> None:
    _selection["paths"] = []
    _selection["source"] = ""
    _selection["label"] = ""
    _notify_listeners()


def peek_selection_paths() -> list[str]:
    return list(_selection.get("paths") or [])


def add_listener(cb: Callable[[], None]) -> None:
    if cb not in _listeners:
        _listeners.append(cb)


def _notify_listeners() -> None:
    for cb in list(_listeners):
        try:
            cb()
        except Exception:
            pass


def bind_busy_button(button) -> None:
    """Deshabilita el boton mientras haya cualquier job global en curso."""

    def _sync() -> None:
        try:
            button.set_enabled(not job_is_running())
        except Exception:
            pass

    add_listener(_sync)
    _sync()
