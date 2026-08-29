"""Sistema de configuracion centralizado de FileSage.

Carga desde YAML + variables de entorno.
Prioridad: archivo explicit → ~/.filesage/config.yaml → config/default.yaml → defaults.
Permite guardar la configuracion de usuario de forma persistente.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

USER_CONFIG_DIR = Path.home() / ".filesage"
USER_CONFIG_PATH = USER_CONFIG_DIR / "config.yaml"


class AppConfig(BaseModel):
    name: str = "FileSage"
    version: str = "0.8.9"
    dry_run_default: bool = True


class ScanConfig(BaseModel):
    follow_symlinks: bool = False
    ignore_hidden: bool = True
    max_depth: int | None = None
    min_file_size_bytes: int = 0
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "**/.git/**",
            "**/node_modules/**",
            "**/.venv/**",
            "**/__pycache__/**",
            "**/.DS_Store",
            "**/Thumbs.db",
        ]
    )
    use_recommended_excludes: bool = True


class HashingConfig(BaseModel):
    algorithm: str = "xxhash64"
    partial_size_kb: int = 64
    full_hash_threshold_mb: int = 0


class DuplicatesConfig(BaseModel):
    min_size_bytes: int = 1024
    keep_strategy: str = "newest"


class ActionsConfig(BaseModel):
    use_trash: bool = True
    transaction_log: bool = True
    confirm_destructive: bool = True


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str | None = "~/.filesage/filesage.log"
    format: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


class StorageConfig(BaseModel):
    index_db: str = "~/.filesage/index.db"
    transaction_db: str = "~/.filesage/transactions.db"


class Settings(BaseSettings):
    """Configuracion completa de la aplicacion."""

    model_config = SettingsConfigDict(
        env_prefix="FILESAGE_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    app: AppConfig = Field(default_factory=AppConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    hashing: HashingConfig = Field(default_factory=HashingConfig)
    duplicates: DuplicatesConfig = Field(default_factory=DuplicatesConfig)
    actions: ActionsConfig = Field(default_factory=ActionsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)

    @classmethod
    def from_yaml(cls, path: Path | str) -> "Settings":
        path = Path(path).expanduser()
        if not path.exists():
            return cls()
        with path.open("r", encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "app": self.app.model_dump(),
            "scan": self.scan.model_dump(),
            "hashing": self.hashing.model_dump(),
            "duplicates": self.duplicates.model_dump(),
            "actions": self.actions.model_dump(),
            "logging": self.logging.model_dump(),
            "storage": self.storage.model_dump(),
        }


def get_user_config_path() -> Path:
    return USER_CONFIG_PATH


def load_settings(config_path: Path | str | None = None) -> Settings:
    """Orden: ruta explicita → ~/.filesage/config.yaml → default del proyecto → codigo."""
    if config_path is not None:
        return Settings.from_yaml(config_path)

    if USER_CONFIG_PATH.exists():
        logger.debug("Cargando config de usuario: %s", USER_CONFIG_PATH)
        return Settings.from_yaml(USER_CONFIG_PATH)

    candidates = [
        Path("config/default.yaml"),
        Path(__file__).resolve().parents[3] / "config" / "default.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            logger.debug("Cargando config por defecto: %s", candidate)
            return Settings.from_yaml(candidate)

    return Settings()


def save_settings(settings: Settings, path: Path | str | None = None) -> Path:
    """Guarda la configuracion en YAML (por defecto ~/.filesage/config.yaml)."""
    dest = Path(path).expanduser() if path else USER_CONFIG_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = settings.to_dict()
    with dest.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    logger.info("Configuracion guardada en %s", dest)
    return dest
