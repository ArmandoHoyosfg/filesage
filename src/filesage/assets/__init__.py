"""Recursos embebidos (iconos, etc.)."""

from __future__ import annotations

from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent
ICONS_DIR = ASSETS_DIR / "icons"


def icon_path(name: str = "filesage.png") -> Path:
    """Ruta al icono. Preferir PNG para web/favicon; ICO para Windows."""
    p = ICONS_DIR / name
    if p.exists():
        return p
    # fallbacks
    for cand in ("filesage.png", "filesage.ico", "filesage.svg"):
        q = ICONS_DIR / cand
        if q.exists():
            return q
    return p
