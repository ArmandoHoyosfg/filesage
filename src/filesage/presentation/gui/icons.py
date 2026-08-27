"""Iconos vectoriales escalables via QtAwesome (Font Awesome / Material).

Fallback a texto si qtawesome no esta disponible.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QColor, QIcon

_COLOR = "#cdd6f4"
_COLOR_ACCENT = "#89b4fa"
_COLOR_DARK = "#1e1e2e"

# nombre logico -> (prefix.name, color opcional)
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
    """Devuelve un QIcon escalable. Si falla, QIcon vacio."""
    key = ICON_MAP.get(name, name)
    try:
        import qtawesome as qta

        c = color or _COLOR
        return qta.icon(key, color=c, scale_factor=scale)
    except Exception:
        return QIcon()


def icon_for_button(name: str, *, on_accent: bool = False) -> QIcon:
    """Icono pensado para botones (contraste)."""
    return icon(name, color=_COLOR_DARK if on_accent else _COLOR_ACCENT)


def try_set_button_icon(button: Any, name: str, *, on_accent: bool = False) -> None:
    """Asigna icono a un QPushButton si es posible."""
    try:
        button.setIcon(icon_for_button(name, on_accent=on_accent))
    except Exception:
        pass
