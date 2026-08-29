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
from filesage.application.progress import ProgressReporter

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

    def scan(self, root: Path, *, progress: ProgressReporter | None = None) -> ScanResult:
        return self.scanner.scan(root, progress=progress)

    def analyze_space(
        self,
        root: Path,
        *,
        top_n: int = 20,
        progress: ProgressReporter | None = None,
    ) -> tuple[ScanResult, SpaceReport]:
        scan_result = self.scanner.scan(root, progress=progress)
        if progress:
            progress.report("Calculando uso de espacio…", 0.9)
        report = self.space_analyzer.analyze(scan_result, top_n=top_n)
        if progress:
            progress.report("Analisis de espacio listo", 1.0)
        return scan_result, report

    def find_duplicates(
        self, root: Path, *, progress: ProgressReporter | None = None
    ) -> tuple[ScanResult, list[DuplicateGroup]]:
        scan_result = self.scanner.scan(root, progress=progress)
        groups = self.duplicate_finder.find(scan_result.files, progress=progress)
        return scan_result, groups

    def find_duplicates_from_scan(
        self,
        scan_result: ScanResult,
        *,
        progress: ProgressReporter | None = None,
    ) -> list[DuplicateGroup]:
        return self.duplicate_finder.find(scan_result.files, progress=progress)

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

    def build_smart_plan(
        self, root: Path, *, progress: ProgressReporter | None = None
    ) -> SmartPlan:
        scan, groups = self.find_duplicates(root, progress=progress)
        if progress:
            progress.report("Generando plan inteligente…", 0.95)
        planner = SmartPlanner(self.settings)
        plan = planner.build(scan, groups)
        if progress:
            progress.report(f"Plan listo: {len(plan.items)} candidatos", 1.0)
        return plan

    def smart_plan_to_actions(self, plan: SmartPlan):
        planner = SmartPlanner(self.settings)
        return planner.to_trash_actions(plan)

    def build_organize_plan(
        self,
        root: Path,
        *,
        min_files_per_group: int = 3,
        progress: ProgressReporter | None = None,
    ) -> SmartPlan:
        """Plan solo de organizacion por tipo (sin busqueda de duplicados)."""
        scan = self.scan(root, progress=progress)
        if progress:
            progress.report("Clasificando por tipo…", 0.85)
        planner = SmartPlanner(self.settings)
        items = planner.build_organize_suggestions(
            scan, min_files_per_group=min_files_per_group
        )
        # preseleccionar ninguno (MEDIUM); usuario elige
        plan = SmartPlan(
            root=root,
            items=items,
            scan_files=scan.total_files,
            duplicate_groups=0,
        )
        if progress:
            progress.report(f"Organizacion: {len(items)} candidatos", 1.0)
        return plan

    def organize_plan_to_actions(self, plan: SmartPlan):
        """Solo acciones MOVE de items organize seleccionados."""
        planner = SmartPlanner(self.settings)
        actions = planner.to_trash_actions(plan)
        from filesage.domain.models import ActionType
        return [a for a in actions if a.action_type == ActionType.MOVE]

    def identify_file(self, path: Path, *, deep: bool = True):
        """Identidad/tipo/metadatos de un archivo (capa de presentacion no importa infrastructure)."""
        from filesage.infrastructure.file_identity import identify
        return identify(path, deep=deep)

    def new_action_id(self) -> str:
        from filesage.infrastructure.storage import new_action_id
        return new_action_id()

    def convert_images(
        self,
        path: Path,
        *,
        target_ext: str = "png",
        output_dir: Path | None = None,
        quality: int = 90,
        recursive: bool = False,
    ):
        """Convierte imagenes a otro formato (Pillow)."""
        from filesage.services.image_converter import convert_path
        return convert_path(
            path,
            target_ext=target_ext,
            output_dir=output_dir,
            quality=quality,
            recursive=recursive,
        )

    def find_empty_folders(self, root: Path, *, max_depth: int | None = None) -> list:
        from filesage.services.empty_folders import find_empty_folders
        return find_empty_folders(root, max_depth=max_depth)

    def zip_folder(self, source: Path, dest_zip: Path | None = None) -> Path:
        from filesage.services.archiver import zip_folder
        return zip_folder(source, dest_zip)

    def build_cleanup_plan(
        self,
        root: Path,
        *,
        include_empty_folders: bool = True,
        include_old_files: bool = True,
        old_days: int = 365,
        min_old_size: int = 0,
        progress: ProgressReporter | None = None,
    ):
        """Plan de carpetas vacias + archivos antiguos."""
        from filesage.services.cleanup_plan import build_cleanup_plan

        scan = self.scan(root, progress=progress)
        if progress:
            progress.report("Construyendo plan de limpieza…", 0.9)
        plan = build_cleanup_plan(
            scan,
            include_empty_folders=include_empty_folders,
            include_old_files=include_old_files,
            old_days=old_days,
            min_old_size=min_old_size,
        )
        if progress:
            progress.report(f"{len(plan.items)} candidatos", 1.0)
        return plan

    def cleanup_plan_to_actions(self, plan, *, permanent: bool = False):
        from filesage.services.cleanup_plan import cleanup_to_actions
        return cleanup_to_actions(plan, permanent=permanent)

    def empty_recycle_bin(self) -> str:
        """Vacia la papelera del sistema (irreversible)."""
        from filesage.infrastructure.trash import empty_system_trash
        return empty_system_trash()

    def run_network_diagnostics(
        self,
        *,
        progress: ProgressReporter | None = None,
        light_speed: bool = True,
    ):
        from filesage.services.network_diagnostics import run_full_diagnostics
        return run_full_diagnostics(progress=progress, light_speed=light_speed)

    def run_network_repair(self, repair_id: str):
        from filesage.services.network_diagnostics import run_repair
        return run_repair(repair_id)
