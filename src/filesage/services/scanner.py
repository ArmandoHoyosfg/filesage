"""Implementacion del servicio de escaneo (IScanner)."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from filesage.core.config import Settings
from filesage.domain.exceptions import ScanError
from filesage.domain.interfaces import IScanner
from filesage.domain.models import FileInfo, ScanResult
from filesage.infrastructure.fs import iter_files

logger = logging.getLogger(__name__)


class Scanner(IScanner):
    """Escaner de archivos que respeta la configuracion de la aplicacion."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def scan(self, root: Path) -> ScanResult:
        """Recorre el directorio raiz y devuelve un ScanResult completo."""
        root = Path(root).expanduser().resolve()
        logger.info("Iniciando escaneo de: %s", root)

        start = time.perf_counter()
        files: list[FileInfo] = []
        total_size = 0
        errors: list[str] = []

        scan_cfg = self._settings.scan

        try:
            gen = iter_files(
                root,
                follow_symlinks=scan_cfg.follow_symlinks,
                ignore_hidden=scan_cfg.ignore_hidden,
                max_depth=scan_cfg.max_depth,
                min_size=scan_cfg.min_file_size_bytes,
                exclude_patterns=scan_cfg.exclude_patterns,
            )
            # Consumir el generador de forma limpia
            while True:
                try:
                    fi = next(gen)
                    files.append(fi)
                    total_size += fi.size
                except StopIteration as stop:
                    errors = list(stop.value or [])
                    break
        except ScanError:
            # Re-lanzar errores de dominio (ruta inexistente, etc.)
            raise
        except Exception as exc:
            logger.exception("Error inesperado durante el escaneo")
            errors.append(str(exc))

        duration = time.perf_counter() - start
        result = ScanResult(
            root=root,
            files=tuple(files),
            total_size=total_size,
            total_files=len(files),
            errors=tuple(errors),
            duration_seconds=duration,
        )

        logger.info(
            "Escaneo terminado: %d archivos, %.2f MB, %.2f s, %d errores",
            result.total_files,
            result.total_size / (1024 * 1024),
            result.duration_seconds,
            len(result.errors),
        )
        return result
