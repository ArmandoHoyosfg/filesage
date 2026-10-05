"""Hashing seguro y eficiente (IHasher) con cache opcional.

- Hash parcial multi-region (inicio + medio + final)
- Hash completo por chunks
- Cache: path + size + mtime + algo + kind
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import xxhash

from filesage.core.config import Settings
from filesage.domain.exceptions import HashError
from filesage.domain.interfaces import IHasher
from filesage.infrastructure.hash_cache import HashCache

logger = logging.getLogger(__name__)


class Hasher(IHasher):
    """Hasher configurable (xxhash64 por defecto) + cache SQLite."""

    def __init__(self, settings: Settings, cache: HashCache | None = None) -> None:
        self._settings = settings
        self._partial_size = max(4 * 1024, settings.hashing.partial_size_kb * 1024)
        self._algo = settings.hashing.algorithm.lower()
        use_cache = getattr(settings.hashing, "use_cache", True)
        if cache is not None:
            self._cache = cache
        elif use_cache:
            db = Path(settings.storage.index_db).expanduser().parent / "hash_cache.db"
            self._cache = HashCache(db)
        else:
            self._cache = None

    def _new_hasher(self):
        if self._algo in ("sha256", "sha-256"):
            return hashlib.sha256()
        return xxhash.xxh64()

    def _stat(self, path: Path) -> tuple[int, float]:
        st = path.stat()
        return int(st.st_size), float(st.st_mtime)

    def partial_hash(self, path: Path) -> str:
        path = Path(path)
        try:
            size, mtime = self._stat(path)
        except OSError as exc:
            raise HashError(f"No se pudo leer {path}: {exc}") from exc

        if self._cache:
            hit = self._cache.get(
                path, size=size, mtime=mtime, kind="partial", algo=self._algo
            )
            if hit:
                return hit

        try:
            h = self._new_hasher()
            h.update(size.to_bytes(8, "little", signed=False))
            with path.open("rb") as f:
                head = f.read(self._partial_size)
                h.update(head)
                if size > self._partial_size * 3:
                    mid_pos = max(0, (size // 2) - (self._partial_size // 2))
                    f.seek(mid_pos)
                    h.update(f.read(self._partial_size))
                    tail_pos = max(0, size - self._partial_size)
                    f.seek(tail_pos)
                    h.update(f.read(self._partial_size))
                elif size > self._partial_size:
                    f.seek(max(0, size - self._partial_size))
                    h.update(f.read(self._partial_size))
            digest = h.hexdigest()
        except OSError as exc:
            raise HashError(f"No se pudo leer {path}: {exc}") from exc

        if self._cache:
            try:
                self._cache.put(
                    path,
                    size=size,
                    mtime=mtime,
                    kind="partial",
                    algo=self._algo,
                    digest=digest,
                )
            except Exception as exc:
                logger.debug("cache put partial: %s", exc)
        return digest

    def full_hash(self, path: Path) -> str:
        path = Path(path)
        try:
            size, mtime = self._stat(path)
        except OSError as exc:
            raise HashError(f"No se pudo hashear {path}: {exc}") from exc

        if self._cache:
            hit = self._cache.get(
                path, size=size, mtime=mtime, kind="full", algo=self._algo
            )
            if hit:
                return hit

        try:
            h = self._new_hasher()
            with path.open("rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    h.update(chunk)
            digest = h.hexdigest()
        except OSError as exc:
            raise HashError(f"No se pudo hashear {path}: {exc}") from exc

        if self._cache:
            try:
                self._cache.put(
                    path,
                    size=size,
                    mtime=mtime,
                    kind="full",
                    algo=self._algo,
                    digest=digest,
                )
            except Exception as exc:
                logger.debug("cache put full: %s", exc)
        return digest

    def verify_same_content(self, a: Path, b: Path, *, sample: int = 8192) -> bool:
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
