"""Planes de limpieza: carpetas vacias + archivos antiguos.

Solo planifica. La ejecucion pasa por ActionManager (TRASH o DELETE).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from filesage.domain.models import ActionRecord, ActionType, FileInfo, ScanResult
from filesage.infrastructure.storage import new_action_id
from filesage.services.empty_folders import find_empty_folders


@dataclass
class CleanupItem:
    path: Path
    size: int
    kind: str  # "empty_folder" | "old_file"
    reason: str
    selected: bool = False
    mtime: float = 0.0


@dataclass
class CleanupPlan:
    root: Path
    items: list[CleanupItem] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)

    @property
    def selected_items(self) -> list[CleanupItem]:
        return [i for i in self.items if i.selected]

    @property
    def selected_bytes(self) -> int:
        return sum(i.size for i in self.selected_items)


def build_cleanup_plan(
    scan: ScanResult,
    *,
    include_empty_folders: bool = True,
    include_old_files: bool = True,
    old_days: int = 365,
    min_old_size: int = 0,
    now: float | None = None,
) -> CleanupPlan:
    now = now or time.time()
    items: list[CleanupItem] = []
    root = scan.root

    if include_old_files:
        threshold = now - old_days * 86400
        for fi in scan.files:
            if fi.mtime <= threshold and fi.size >= min_old_size:
                age = int((now - fi.mtime) / 86400)
                items.append(
                    CleanupItem(
                        path=fi.path,
                        size=fi.size,
                        kind="old_file",
                        reason=f"Sin modificar ~{age} dias",
                        selected=False,
                        mtime=fi.mtime,
                    )
                )

    if include_empty_folders:
        for folder in find_empty_folders(root):
            items.append(
                CleanupItem(
                    path=folder,
                    size=0,
                    kind="empty_folder",
                    reason="Carpeta vacia",
                    selected=False,
                )
            )

    # orden: carpetas vacias primero, luego archivos por antigüedad
    items.sort(key=lambda x: (0 if x.kind == "empty_folder" else 1, x.mtime))
    return CleanupPlan(root=root, items=items)


def cleanup_to_actions(
    plan: CleanupPlan,
    *,
    permanent: bool = False,
) -> list[ActionRecord]:
    """TRASH por defecto; DELETE solo si permanent=True."""
    action_type = ActionType.DELETE if permanent else ActionType.TRASH
    actions: list[ActionRecord] = []
    for item in plan.selected_items:
        actions.append(
            ActionRecord(
                action_id=new_action_id(),
                action_type=action_type,
                source=item.path,
                destination=None,
                timestamp=datetime.now(),
                success=False,
                message="",
                dry_run=True,
                metadata={"kind": item.kind, "reason": item.reason},
            )
        )
    return actions
