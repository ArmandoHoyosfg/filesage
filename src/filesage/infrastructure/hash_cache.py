"""Cache de hashes (ruta + tamaño + mtime) para no recalcular en rescaneos.

Mejores practicas (Czkawka / File Hunter): invalidar si cambia size o mtime.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class HashCache:
    """SQLite thread-safe para partial/full hash."""

    def __init__(self, db_path: Path | str) -> None:
        self._path = Path(db_path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path), timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS hash_cache (
                        path TEXT NOT NULL,
                        size INTEGER NOT NULL,
                        mtime REAL NOT NULL,
                        kind TEXT NOT NULL,
                        digest TEXT NOT NULL,
                        algo TEXT NOT NULL,
                        PRIMARY KEY (path, kind, algo)
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_hash_path ON hash_cache(path)"
                )

    def get(
        self,
        path: Path,
        *,
        size: int,
        mtime: float,
        kind: str,
        algo: str,
    ) -> str | None:
        key = str(path.resolve()) if path.exists() else str(path)
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT digest, size, mtime FROM hash_cache
                    WHERE path = ? AND kind = ? AND algo = ?
                    """,
                    (key, kind, algo),
                ).fetchone()
        if not row:
            return None
        digest, csize, cmtime = row
        # tolerancia leve de mtime por redondeos de FS
        if int(csize) != int(size) or abs(float(cmtime) - float(mtime)) > 0.001:
            return None
        return str(digest)

    def put(
        self,
        path: Path,
        *,
        size: int,
        mtime: float,
        kind: str,
        algo: str,
        digest: str,
    ) -> None:
        key = str(path.resolve()) if path.exists() else str(path)
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO hash_cache
                    (path, size, mtime, kind, algo, digest)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (key, int(size), float(mtime), kind, algo, digest),
                )

    def clear(self) -> int:
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute("DELETE FROM hash_cache")
                return cur.rowcount
