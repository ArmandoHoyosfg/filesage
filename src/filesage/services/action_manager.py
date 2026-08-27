"""ActionManager: ejecuta acciones de forma segura (IActionExecutor).

- Dry-run por defecto
- Papelera por defecto
- Log de transacciones
- Rollback basico (solo para movimientos; la papelera depende del SO)
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Sequence

from filesage.core.config import Settings
from filesage.domain.exceptions import ActionError
from filesage.domain.interfaces import IActionExecutor, IStorage
from filesage.domain.models import ActionRecord, ActionType, Transaction
from filesage.infrastructure.storage import SqliteStorage, new_action_id, new_transaction_id
from filesage.infrastructure.trash import move_to_trash, permanent_delete, safe_move

logger = logging.getLogger(__name__)


class ActionManager(IActionExecutor):
    """Ejecuta y registra acciones de archivos de forma controlada."""

    def __init__(self, settings: Settings, storage: IStorage | None = None) -> None:
        self._settings = settings
        self._storage = storage or SqliteStorage(settings)
        self._use_trash = settings.actions.use_trash

    def execute(
        self,
        actions: Sequence[ActionRecord],
        *,
        dry_run: bool | None = None,
    ) -> Transaction:
        """Ejecuta (o simula) una lista de acciones y devuelve la transaccion."""
        if dry_run is None:
            dry_run = self._settings.app.dry_run_default

        tx_id = new_transaction_id()
        started = datetime.now()
        executed: list[ActionRecord] = []

        logger.info("Iniciando transaccion %s (dry_run=%s, acciones=%d)", tx_id, dry_run, len(actions))

        for planned in actions:
            record = self._run_one(planned, dry_run=dry_run)
            executed.append(record)

        finished = datetime.now()
        transaction = Transaction(
            transaction_id=tx_id,
            started_at=started,
            finished_at=finished,
            actions=tuple(executed),
            dry_run=dry_run,
            notes=f"{len(executed)} acciones",
        )

        if self._settings.actions.transaction_log:
            try:
                self._storage.save_transaction(transaction)
            except Exception as exc:
                logger.warning("No se pudo guardar la transaccion: %s", exc)

        ok = sum(1 for a in executed if a.success)
        logger.info("Transaccion %s terminada: %d/%d OK", tx_id, ok, len(executed))
        return transaction

    def _run_one(self, planned: ActionRecord, *, dry_run: bool) -> ActionRecord:
        """Ejecuta una sola accion y devuelve el registro resultante."""
        action_id = planned.action_id or new_action_id()
        source = Path(planned.source)
        dest = Path(planned.destination) if planned.destination else None
        now = datetime.now()

        if dry_run:
            msg = f"[DRY-RUN] Se {planned.action_type.value}ia: {source}"
            if dest:
                msg += f" -> {dest}"
            logger.info(msg)
            return ActionRecord(
                action_id=action_id,
                action_type=planned.action_type,
                source=source,
                destination=dest,
                timestamp=now,
                success=True,
                message=msg,
                dry_run=True,
                metadata=planned.metadata,
            )

        try:
            if planned.action_type == ActionType.TRASH:
                move_to_trash(source)
                message = f"Enviado a papelera: {source}"
            elif planned.action_type == ActionType.DELETE:
                permanent_delete(source)
                message = f"Eliminado permanentemente: {source}"
            elif planned.action_type == ActionType.MOVE:
                if not dest:
                    raise ActionError("MOVE requiere destination")
                safe_move(source, dest)
                message = f"Movido: {source} -> {dest}"
            elif planned.action_type == ActionType.COPY:
                raise ActionError("COPY aun no implementado")
            else:
                raise ActionError(f"Tipo de accion no soportado: {planned.action_type}")

            return ActionRecord(
                action_id=action_id,
                action_type=planned.action_type,
                source=source,
                destination=dest,
                timestamp=now,
                success=True,
                message=message,
                dry_run=False,
                metadata=planned.metadata,
            )
        except Exception as exc:
            logger.error("Fallo accion %s sobre %s: %s", planned.action_type, source, exc)
            return ActionRecord(
                action_id=action_id,
                action_type=planned.action_type,
                source=source,
                destination=dest,
                timestamp=now,
                success=False,
                message=str(exc),
                dry_run=False,
                metadata=planned.metadata,
            )

    def rollback(self, transaction: Transaction) -> Transaction:
        """Intenta revertir una transaccion.

        Limitaciones:
        - Solo se pueden revertir MOVEs (devolver al origen).
        - TRASH/DELETE dependen de la papelera del sistema (el usuario debe restaurar manualmente).
        """
        if transaction.dry_run:
            logger.info("Rollback de dry-run: no hay nada que revertir")
            return transaction

        reverse_actions: list[ActionRecord] = []
        for action in reversed(transaction.actions):
            if not action.success:
                continue
            if action.action_type == ActionType.MOVE and action.destination:
                # Mover de vuelta
                reverse_actions.append(
                    ActionRecord(
                        action_id=new_action_id(),
                        action_type=ActionType.MOVE,
                        source=action.destination,
                        destination=action.source,
                        timestamp=datetime.now(),
                        success=False,
                        message="",
                        dry_run=False,
                        metadata={"rollback_of": action.action_id},
                    )
                )
            # TRASH/DELETE: no se revierten automaticamente

        if not reverse_actions:
            logger.warning("No hay acciones reversibles en la transaccion %s", transaction.transaction_id)
            return transaction

        return self.execute(reverse_actions, dry_run=False)

    def plan_trash_duplicates(
        self,
        groups: list,
        *,
        keep_newest: bool = True,
    ) -> list[ActionRecord]:
        """Genera un plan de acciones TRASH para duplicados (mantiene 1 por grupo)."""
        plans: list[ActionRecord] = []
        for group in groups:
            files = list(group.files)
            if len(files) < 2:
                continue
            # Ya vienen ordenados por mtime desc en DuplicateFinder
            keep = files[0] if keep_newest else files[-1]
            for fi in files:
                if fi.path == keep.path:
                    continue
                plans.append(
                    ActionRecord(
                        action_id=new_action_id(),
                        action_type=ActionType.TRASH,
                        source=fi.path,
                        destination=None,
                        timestamp=datetime.now(),
                        success=False,
                        message="",
                        dry_run=True,
                        metadata={"group_hash": group.hash_full, "kept": str(keep.path)},
                    )
                )
        return plans
