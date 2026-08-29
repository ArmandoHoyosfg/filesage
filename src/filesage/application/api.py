"""Contrato estable de la API de aplicacion (puerto de entrada).

Cualquier adaptador de presentacion (Qt, CLI, NiceGUI, REST) debe usar
solo este contrato. Implementacion de referencia: filesage.core.engine.Engine.

Regla de dependencias:
  presentation → application/core → services → infrastructure
  presentation ↛ infrastructure
  presentation ↛ services
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from filesage.application.progress import ProgressReporter
from filesage.domain.models import (
    ActionRecord,
    DuplicateGroup,
    ScanResult,
    SpaceReport,
    Transaction,
)


class ApplicationAPI(Protocol):
    """Puerto de entrada generico y reutilizable."""

    def scan(
        self, root: Path, *, progress: ProgressReporter | None = None
    ) -> ScanResult: ...

    def analyze_space(
        self,
        root: Path,
        *,
        top_n: int = 20,
        progress: ProgressReporter | None = None,
    ) -> tuple[ScanResult, SpaceReport]: ...

    def find_duplicates(
        self, root: Path, *, progress: ProgressReporter | None = None
    ) -> tuple[ScanResult, list[DuplicateGroup]]: ...

    def find_duplicates_from_scan(
        self,
        scan_result: ScanResult,
        *,
        progress: ProgressReporter | None = None,
    ) -> list[DuplicateGroup]: ...

    def plan_trash_duplicates(
        self, groups: list[DuplicateGroup], *, keep_newest: bool = True
    ) -> list[ActionRecord]: ...

    def execute_actions(
        self, actions: Sequence[ActionRecord], *, dry_run: bool | None = None
    ) -> Transaction: ...

    def list_transactions(self, limit: int = 50) -> list[Transaction]: ...

    def rollback(self, transaction: Transaction) -> Transaction: ...

    def export_space(self, report, scan, dest: Path, fmt: str = "json") -> Path: ...

    def export_duplicates(self, groups, root: Path, dest: Path, fmt: str = "json") -> Path: ...

    def smart_insights(self, scan_result: ScanResult) -> list: ...

    def build_smart_plan(
        self, root: Path, *, progress: ProgressReporter | None = None
    ): ...
