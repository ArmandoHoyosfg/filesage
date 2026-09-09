"""Hashing seguro y eficiente (IHasher).

Mejores practicas anti falso-positivo:
- Hash parcial multi-region (inicio + medio + final), no solo los primeros KB
  (dos MP3 distintos pueden compartir cabecera/silencio inicial).
- Hash completo por chunks de todo el archivo.
- xxhash64 por velocidad; SHA-256 disponible para modo estricto.
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
    """Hasher configurable (xxhash64 por defecto)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._partial_size = max(4 * 1024, settings.hashing.partial_size_kb * 1024)
        self._algo = settings.hashing.algorithm.lower()

    def _new_hasher(self):
        if self._algo in ("sha256", "sha-256"):
            return hashlib.sha256()
        return xxhash.xxh64()

    def partial_hash(self, path: Path) -> str:
        """Fingerprint rapido: inicio + medio + final (si el archivo es grande).

        Evita colisiones parciales tipicas en audio/video con cabeceras similares.
        """
        try:
            size = path.stat().st_size
            h = self._new_hasher()
            # Incluir tamano en el digest parcial reduce cruces entre archivos
            h.update(size.to_bytes(8, "little", signed=False))

            with path.open("rb") as f:
                # Inicio
                head = f.read(self._partial_size)
                h.update(head)

                if size > self._partial_size * 3:
                    # Medio
                    mid_pos = max(0, (size // 2) - (self._partial_size // 2))
                    f.seek(mid_pos)
                    h.update(f.read(self._partial_size))
                    # Final
                    tail_pos = max(0, size - self._partial_size)
                    f.seek(tail_pos)
                    h.update(f.read(self._partial_size))
                elif size > self._partial_size:
                    # Solo final si cabe
                    f.seek(max(0, size - self._partial_size))
                    h.update(f.read(self._partial_size))

            return h.hexdigest()
        except OSError as exc:
            raise HashError(f"No se pudo leer {path}: {exc}") from exc

    def full_hash(self, path: Path) -> str:
        """Hash de todo el contenido (por chunks)."""
        try:
            h = self._new_hasher()
            with path.open("rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        except OSError as exc:
            raise HashError(f"No se pudo hashear {path}: {exc}") from exc

    def verify_same_content(self, a: Path, b: Path, *, sample: int = 8192) -> bool:
        """Comprobacion extra tras hash: compara bloques inicio/final.

        No sustituye al hash completo; detecta fallos absurdos de I/O.
        """
        try:
            sa, sb = a.stat().st_size, b.stat().st_size
            if sa != sb:
                return False
            with a.open("rb") as fa, b.open("rb") as fb:
                if fa.read(sample) != fb.read(sample):
                    return False
                if sa > sample * 2:
                    fa.seek(sa - sample)
                    fb.seek(sb - sample)
                    if fa.read(sample) != fb.read(sample):
                        return False
            return True
        except OSError:
            return False
