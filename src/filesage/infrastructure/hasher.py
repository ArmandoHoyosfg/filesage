"""Implementacion de hashing segura y eficiente (IHasher).

Pipeline recomendado:
1. Agrupar por tamano (hecho en DuplicateFinder)
2. Hash parcial (primeros N KB) con xxhash
3. Hash completo solo de candidatos
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import xxhash

from filesage.core.config import Settings
from filesage.domain.exceptions import HashError
from filesage.domain.interfaces import IHasher

logger = logging.getLogger(__name__)


class Hasher(IHasher):
    """Hasher configurable (xxhash64 por defecto + SHA-256 opcional)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._partial_size = settings.hashing.partial_size_kb * 1024
        self._algo = settings.hashing.algorithm.lower()

    def partial_hash(self, path: Path) -> str:
        """Hash rapido de los primeros N KB del archivo."""
        try:
            with path.open("rb") as f:
                data = f.read(self._partial_size)
            if self._algo.startswith("xxhash"):
                return xxhash.xxh64(data).hexdigest()
            # fallback
            return hashlib.sha256(data).hexdigest()
        except OSError as exc:
            raise HashError(f"No se pudo leer {path}: {exc}") from exc

    def full_hash(self, path: Path) -> str:
        """Hash completo del archivo (lectura por chunks)."""
        try:
            if self._algo.startswith("xxhash"):
                h = xxhash.xxh64()
            else:
                h = hashlib.sha256()

            with path.open("rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)  # 1 MB
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        except OSError as exc:
            raise HashError(f"No se pudo hashear {path}: {exc}") from exc
