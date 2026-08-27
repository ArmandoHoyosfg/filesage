"""Persistencia simple de transacciones (SQLite).

Implementa IStorage de forma minima para historial y rollback.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from filesage.core.config import Settings
from filesage.domain.exceptions import StorageError
from filesage.domain.interfaces import IStorage
from filesage.domain.models import ActionRecord, ActionType, ScanResult, Transaction

logger = logging.getLogger(__name__)


class SqliteStorage(IStorage):
    """Almacenamiento de transacciones en SQLite."""

    def __init__(self, settings: Settings) -> None:
        self._db_path = Path(settings.storage.transaction_db).expanduser()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    dry_run INTEGER NOT NULL,
                    notes TEXT,
                    actions_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save_scan(self, result: ScanResult) -> None:
        # Placeholder: se puede ampliar mas adelante
        pass

    def load_scan(self, root: Path) -> ScanResult | None:
        return None

    def save_transaction(self, transaction: Transaction) -> None:
        try:
            actions_data = [
                {
                    "action_id": a.action_id,
                    "action_type": a.action_type.value,
                    "source": str(a.source),
                    "destination": str(a.destination) if a.destination else None,
                    "timestamp": a.timestamp.isoformat(),
                    "success": a.success,
                    "message": a.message,
                    "dry_run": a.dry_run,
                    "metadata": a.metadata,
                }
                for a in transaction.actions
            ]
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO transactions
                    (transaction_id, started_at, finished_at, dry_run, notes, actions_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        transaction.transaction_id,
                        transaction.started_at.isoformat(),
                        transaction.finished_at.isoformat() if transaction.finished_at else None,
                        1 if transaction.dry_run else 0,
                        transaction.notes,
                        json.dumps(actions_data, ensure_ascii=False),
                    ),
                )
                conn.commit()
            logger.info("Transaccion guardada: %s (%d acciones)", transaction.transaction_id, len(transaction.actions))
        except Exception as exc:
            raise StorageError(f"No se pudo guardar la transaccion: {exc}") from exc

    def list_transactions(self, limit: int = 50) -> list[Transaction]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM transactions
                    ORDER BY started_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

            results: list[Transaction] = []
            for row in rows:
                actions_raw = json.loads(row["actions_json"])
                actions = []
                for a in actions_raw:
                    actions.append(
                        ActionRecord(
                            action_id=a["action_id"],
                            action_type=ActionType(a["action_type"]),
                            source=Path(a["source"]),
                            destination=Path(a["destination"]) if a.get("destination") else None,
                            timestamp=datetime.fromisoformat(a["timestamp"]),
                            success=a["success"],
                            message=a.get("message", ""),
                            dry_run=a.get("dry_run", True),
                            metadata=a.get("metadata") or {},
                        )
                    )
                results.append(
                    Transaction(
                        transaction_id=row["transaction_id"],
                        started_at=datetime.fromisoformat(row["started_at"]),
                        finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
                        actions=tuple(actions),
                        dry_run=bool(row["dry_run"]),
                        notes=row["notes"] or "",
                    )
                )
            return results
        except Exception as exc:
            raise StorageError(f"No se pudo listar transacciones: {exc}") from exc


def new_action_id() -> str:
    return uuid.uuid4().hex[:12]


def new_transaction_id() -> str:
    return uuid.uuid4().hex[:16]
