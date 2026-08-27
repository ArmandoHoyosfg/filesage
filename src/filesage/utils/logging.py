"""Configuración centralizada de logging."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from filesage.core.config import LoggingConfig


def setup_logging(config: LoggingConfig) -> None:
    """Configura el logging de toda la aplicación."""
    level = getattr(logging, config.level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if config.file:
        log_path = Path(config.file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format=config.format,
        handlers=handlers,
        force=True,  # permite reconfigurar en tests
    )

    # Reducir ruido de librerías de terceros
    logging.getLogger("urllib3").setLevel(logging.WARNING)
