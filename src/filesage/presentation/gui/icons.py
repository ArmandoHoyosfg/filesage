"""Iconos vectoriales via QtAwesome, con cache y fallback seguro."""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QIcon

_COLOR = "#cdd6f4"
_COLOR_ACCENT = "#89b4fa"
_COLOR_DARK = "#1e1e2e"
_CACHE: dict[str, QIcon] = {}

ICON_MAP: dict[str, str] = {
    "dashboard": "fa5s.home",
    "space": "fa5s.hdd",
    "duplicates": "fa5s.copy",
    "history": "fa5s.history",
    "settings": "fa5s.cog",
    "help": "fa5s.question-circle",
    "smart": "fa5s.magic",
    "wizard": "fa5s.hat-wizard",
    "folder": "fa5s.folder",
    "scan": "fa5s.search",
    "trash": "fa5s.trash",
    "export": "fa5s.file-export",
    "play": "fa5s.play",
    "music": "fa5s.music",
    "video": "fa5s.film",
    "image": "fa5s.image",
    "document": "fa5s.file-alt",
    "archive": "fa5s.file-archive",
    "check": "fa5s.check",
    "mode": "fa5s.sliders-h",
}


def icon(name: str, *, color: str | None = None, scale: float = 1.0) -> QIcon:
    key = ICON_MAP.get(name, name)
    c = color or _COLOR
    cache_key = f"{key}|{c}|{scale}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]
    try:
        import qtawesome as qta
        from PySide6.QtWidgets import QApplication
        if QApplication.instance() is None:
            return QIcon()
        ic = qta.icon(key, color=c, scale_factor=scale)
        _CACHE[cache_key] = ic
        return ic
    except Exception:
        return QIcon()


def icon_for_button(name: str, *, on_accent: bool = False) -> QIcon:
    return icon(name, color=_COLOR_DARK if on_accent else _COLOR_ACCENT)


def try_set_button_icon(button: Any, name: str, *, on_accent: bool = False) -> None:
    try:
        ic = icon_for_button(name, on_accent=on_accent)
        if not ic.isNull():
            button.setIcon(ic)
    except Exception:
        pass
