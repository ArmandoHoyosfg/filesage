"""Envio seguro a la papelera del sistema (multiplataforma)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from send2trash import send2trash

from filesage.domain.exceptions import ActionError

logger = logging.getLogger(__name__)


def move_to_trash(path: Path) -> None:
    """Envia un archivo o carpeta a la papelera del sistema.

    Raises:
        ActionError: si no se puede completar la operacion.
    """
    path = Path(path)
    if not path.exists():
        raise ActionError(f"No existe: {path}")
    try:
        send2trash(str(path))
        logger.info("Enviado a papelera: %s", path)
    except Exception as exc:
        raise ActionError(f"No se pudo enviar a papelera {path}: {exc}") from exc


def permanent_delete(path: Path) -> None:
    """Elimina permanentemente (usar solo cuando el usuario lo pida explicitamente)."""
    path = Path(path)
    if not path.exists():
        raise ActionError(f"No existe: {path}")
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        logger.info("Eliminado permanentemente: %s", path)
    except Exception as exc:
        raise ActionError(f"No se pudo eliminar {path}: {exc}") from exc


def safe_move(source: Path, destination: Path) -> None:
    """Mueve un archivo/carpeta a otro destino."""
    source = Path(source)
    destination = Path(destination)
    if not source.exists():
        raise ActionError(f"No existe el origen: {source}")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        logger.info("Movido: %s -> %s", source, destination)
    except Exception as exc:
        raise ActionError(f"No se pudo mover {source} -> {destination}: {exc}") from exc
