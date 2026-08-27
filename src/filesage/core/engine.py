"""Motor principal (orquestador) de FileSage."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from filesage.core.config import Settings
from filesage.domain.models import ActionRecord, DuplicateGroup, ScanResult, SpaceReport, Transaction
from filesage.infrastructure.hasher import Hasher
from filesage.infrastructure.storage import SqliteStorage
from filesage.services.action_manager import ActionManager
from filesage.services.duplicate_finder import DuplicateFinder
from filesage.services.scanner import Scanner
from filesage.services.space_analyzer import SpaceAnalyzer
from filesage.services.exporter import export_space_report, export_duplicates_report
from filesage.services.smart_insights import analyze as analyze_insights, Insight
from filesage.services.smart_planner import SmartPlanner, SmartPlan

logger = logging.getLogger(__name__)


class Engine:
    """Fachada de alto nivel para las operaciones principales."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.scanner = Scanner(settings)
        self.space_analyzer = SpaceAnalyzer()
        self.hasher = Hasher(settings)
        self.duplicate_finder = DuplicateFinder(settings, self.hasher)
        self.storage = SqliteStorage(settings)
        self.action_manager = ActionManager(settings, self.storage)

    def scan(self, root: Path) -> ScanResult:
        return self.scanner.scan(root)

    def analyze_space(self, root: Path, *, top_n: int = 20) -> tuple[ScanResult, SpaceReport]:
        scan_result = self.scanner.scan(root)
        report = self.space_analyzer.analyze(scan_result, top_n=top_n)
        return scan_result, report

    def find_duplicates(self, root: Path) -> tuple[ScanResult, list[DuplicateGroup]]:
        scan_result = self.scanner.scan(root)
        groups = self.duplicate_finder.find(scan_result.files)
        return scan_result, groups

    def find_duplicates_from_scan(self, scan_result: ScanResult) -> list[DuplicateGroup]:
        return self.duplicate_finder.find(scan_result.files)

    def plan_trash_duplicates(self, groups: list[DuplicateGroup], *, keep_newest: bool = True) -> list[ActionRecord]:
        return self.action_manager.plan_trash_duplicates(groups, keep_newest=keep_newest)

    def execute_actions(self, actions: Sequence[ActionRecord], *, dry_run: bool | None = None) -> Transaction:
        return self.action_manager.execute(actions, dry_run=dry_run)

    def list_transactions(self, limit: int = 50) -> list[Transaction]:
        return self.storage.list_transactions(limit=limit)

    def rollback(self, transaction: Transaction) -> Transaction:
        return self.action_manager.rollback(transaction)

    def export_space(self, report, scan, dest: Path, fmt: str = "json") -> Path:
        return export_space_report(report, scan, dest, fmt=fmt)

    def export_duplicates(self, groups, root: Path, dest: Path, fmt: str = "json") -> Path:
        return export_duplicates_report(groups, root, dest, fmt=fmt)

    def smart_insights(self, scan_result: ScanResult) -> list:
        """Recomendaciones inteligentes locales a partir de un escaneo."""
        return analyze_insights(scan_result)

    def build_smart_plan(self, root: Path) -> SmartPlan:
        scan, groups = self.find_duplicates(root)
        planner = SmartPlanner(self.settings)
        return planner.build(scan, groups)
