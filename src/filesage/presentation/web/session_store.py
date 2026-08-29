"""Estado de sesion web: jobs globales + datos por seccion + busy UI."""

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
