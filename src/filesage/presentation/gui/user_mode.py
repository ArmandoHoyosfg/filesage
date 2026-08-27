"""Modo de usuario: Simple / Smart / Experto."""

from __future__ import annotations

from enum import Enum
from pathlib import Path


class UserMode(str, Enum):
    SIMPLE = "simple"
    SMART = "smart"
    EXPERT = "expert"


_MODE_FILE = Path.home() / ".filesage" / "user_mode"


def load_user_mode() -> UserMode:
    try:
        if _MODE_FILE.exists():
            value = _MODE_FILE.read_text(encoding="utf-8").strip().lower()
            if value in ("expert", "avanzado"):
                return UserMode.EXPERT
            if value in ("smart", "inteligente"):
                return UserMode.SMART
    except OSError:
        pass
    return UserMode.SIMPLE


def save_user_mode(mode: UserMode) -> None:
    try:
        _MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _MODE_FILE.write_text(mode.value, encoding="utf-8")
    except OSError:
        pass
