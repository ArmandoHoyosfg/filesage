"""Estado compartido del adaptador web (Engine + Settings + workspace)."""

from __future__ import annotations

import json
from pathlib import Path

from filesage.core.config import Settings, USER_CONFIG_DIR, load_settings, save_settings
from filesage.core.engine import Engine

_settings: Settings | None = None
_engine: Engine | None = None
_workspace: Path | None = None

_WORKSPACE_FILE = USER_CONFIG_DIR / "workspace.json"


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = Engine(get_settings())
    return _engine


def reload_settings() -> Settings:
    global _settings, _engine
    _settings = load_settings()
    _engine = Engine(_settings)
    return _settings


def persist_settings(settings: Settings | None = None) -> None:
    global _settings, _engine
    s = settings or get_settings()
    save_settings(s)
    _settings = s
    _engine = Engine(s)


def get_workspace() -> Path:
    """Directorio de trabajo maestro (persistido)."""
    global _workspace
    if _workspace is not None:
        return _workspace
    try:
        if _WORKSPACE_FILE.exists():
            data = json.loads(_WORKSPACE_FILE.read_text(encoding="utf-8"))
            p = Path(data.get("path", "")).expanduser()
            if p.is_dir():
                _workspace = p
                return _workspace
    except Exception:
        pass
    # default: home
    _workspace = Path.home()
    return _workspace


def set_workspace(path: Path | str) -> Path:
    global _workspace
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        raise ValueError(f"No es una carpeta: {p}")
    _workspace = p
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _WORKSPACE_FILE.write_text(
        json.dumps({"path": str(p)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return p
