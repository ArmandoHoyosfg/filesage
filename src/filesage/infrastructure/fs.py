"""Utilidades seguras de acceso al sistema de archivos.

Todas las operaciones de lectura de metadatos y recorrido de directorios
pasan por aquí para centralizar el manejo de errores, permisos y symlinks.
"""

from __future__ import annotations

import logging
import os
import stat as stat_module
from pathlib import Path
from typing import Generator, Iterable

from filesage.domain.exceptions import ScanError
from filesage.domain.models import FileInfo

logger = logging.getLogger(__name__)


def safe_stat(path: Path, *, follow_symlinks: bool = False) -> os.stat_result | None:
    """Obtiene el stat de un path de forma segura. Devuelve None si falla."""
    try:
        return path.stat(follow_symlinks=follow_symlinks)
    except (OSError, PermissionError, FileNotFoundError) as exc:
        logger.debug("No se pudo hacer stat de %s: %s", path, exc)
        return None


def is_hidden(path: Path) -> bool:
    """Detecta si un nombre de archivo/carpeta está oculto (empieza por punto)."""
    return path.name.startswith(".")


def should_exclude(path: Path, patterns: Iterable[str]) -> bool:
    """Comprueba si el path coincide con alguno de los patrones de exclusion.

    Implementacion simple y segura para los patrones mas comunes:
    - **/.git/**, **/node_modules/**, **/.venv/**, **/__pycache__/**
    - **/.DS_Store, **/Thumbs.db
    """
    common_names = {".git", "node_modules", ".venv", "__pycache__", ".DS_Store", "Thumbs.db"}

    # Excluir si el nombre actual o algun ancestro es un nombre comun presente en patterns
    parts_to_check = set(path.parts) | {path.name}
    for part in parts_to_check:
        if part in common_names:
            for pattern in patterns:
                if part in pattern.replace("\\", "/"):
                    return True
    return False

def iter_files(
    root: Path,
    *,
    follow_symlinks: bool = False,
    ignore_hidden: bool = True,
    max_depth: int | None = None,
    min_size: int = 0,
    exclude_patterns: Iterable[str] | None = None,
) -> Generator[FileInfo, None, list[str]]:
    """Generador que recorre el árbol de forma segura y produce FileInfo.

    Yields:
        FileInfo de cada archivo válido encontrado.

    Returns (via generator return):
        Lista de mensajes de error encontrados durante el recorrido.
    """
    root = root.resolve()
    if not root.exists():
        raise ScanError(f"La ruta no existe: {root}")
    if not root.is_dir():
        raise ScanError(f"La ruta no es un directorio: {root}")

    errors: list[str] = []
    exclude_patterns = list(exclude_patterns or [])

    # Usamos os.walk por rendimiento y control de profundidad
    for dirpath, dirnames, filenames in os.walk(
        root,
        topdown=True,
        followlinks=follow_symlinks,
        onerror=lambda e: errors.append(str(e)),
    ):
        current = Path(dirpath)
        relative = current.relative_to(root)
        depth = len(relative.parts)

        # Control de profundidad máxima
        if max_depth is not None and depth >= max_depth:
            dirnames.clear()
            continue

        # Filtrar directorios in-place para que os.walk no entre en ellos
        kept_dirs: list[str] = []
        for d in dirnames:
            d_path = current / d
            if ignore_hidden and is_hidden(d_path):
                continue
            if should_exclude(d_path, exclude_patterns):
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs

        for name in filenames:
            file_path = current / name

            if ignore_hidden and is_hidden(file_path):
                continue
            if should_exclude(file_path, exclude_patterns):
                continue

            st = safe_stat(file_path, follow_symlinks=follow_symlinks)
            if st is None:
                errors.append(f"No se pudo acceder: {file_path}")
                continue

            # Solo archivos regulares
            if not stat_module.S_ISREG(st.st_mode):
                continue

            size = st.st_size
            if size < min_size:
                continue

            is_link = file_path.is_symlink()
            yield FileInfo(
                path=file_path,
                size=size,
                mtime=st.st_mtime,
                is_symlink=is_link,
                extension=file_path.suffix.lower(),
            )

    return errors
