"""SmartPlanner: genera un plan de limpieza inteligente y conservador.

Combina:
- Duplicados exactos (confianza ALTA)
- Insights heuristicos filtrados (media / baja)

Nunca incluye la unica copia de un grupo.
No ejecuta acciones: solo planifica.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from filesage.core.config import Settings
from filesage.domain.models import ActionRecord, ActionType, DuplicateGroup, FileInfo, ScanResult
from filesage.infrastructure.storage import new_action_id
from filesage.services.smart_insights import Insight, analyze as analyze_insights
from filesage.infrastructure.file_identity import identify
from collections import defaultdict

logger = logging.getLogger(__name__)


class Confidence(str, Enum):
    HIGH = "high"      # seguro preseleccionar
    MEDIUM = "medium"  # opcional, visible
    LOW = "low"        # solo informativo / desmarcado


@dataclass
class PlanItem:
    path: Path
    size: int
    reason: str
    confidence: Confidence
    category: str
    selected: bool = False
    what: str = ""  # descripcion tipo + metadatos
    metadata: dict = field(default_factory=dict)


@dataclass
class SmartPlan:
    root: Path
    items: list[PlanItem]
    scan_files: int
    duplicate_groups: int
    generated_at: float = field(default_factory=time.time)

    @property
    def selected_items(self) -> list[PlanItem]:
        return [i for i in self.items if i.selected]

    @property
    def selected_bytes(self) -> int:
        return sum(i.size for i in self.selected_items)

    @property
    def total_candidate_bytes(self) -> int:
        return sum(i.size for i in self.items)


class SmartPlanner:
    """Construye planes a partir de ScanResult + grupos de duplicados + insights."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(
        self,
        scan: ScanResult,
        groups: list[DuplicateGroup],
        *,
        include_medium: bool = True,
        include_low: bool = False,
        preselect_high_only: bool = True,
    ) -> SmartPlan:
        items: list[PlanItem] = []
        seen: set[Path] = set()

        # 1) Duplicados exactos → HIGH (mantener el mas reciente)
        for group in groups:
            files = list(group.files)
            if len(files) < 2:
                continue
            keep = files[0]  # ya ordenados por mtime desc en DuplicateFinder
            for fi in files[1:]:
                if fi.path in seen:
                    continue
                seen.add(fi.path)
                items.append(
                    PlanItem(
                        path=fi.path,
                        size=fi.size,
                        reason=f"Duplicado exacto (se mantiene {keep.path.name})",
                        confidence=Confidence.HIGH,
                        category="duplicate",
                        selected=preselect_high_only,
                        metadata={"keep": str(keep.path), "hash": group.hash_full},
                    )
                )

        # 2) Insights → MEDIUM / LOW (no incluir si ya esta como duplicado)
        insights = analyze_insights(scan)
        for insight in insights:
            conf = self._insight_confidence(insight)
            if conf == Confidence.MEDIUM and not include_medium:
                continue
            if conf == Confidence.LOW and not include_low:
                continue
            for p_str in insight.paths:
                p = Path(p_str)
                if p in seen:
                    continue
                # Localizar FileInfo para el size
                fi = next((f for f in scan.files if f.path == p), None)
                size = fi.size if fi else 0
                if size == 0 and insight.category != "empty":
                    continue
                seen.add(p)
                items.append(
                    PlanItem(
                        path=p,
                        size=size,
                        reason=insight.title,
                        confidence=conf,
                        category=insight.category,
                        selected=False,  # nunca preseleccionar medium/low
                        metadata={"insight": insight.category},
                    )
                )

        # 3) Sugerencias de organizacion por tipo
        for org in self.build_organize_suggestions(scan):
            if org.path in seen:
                continue
            seen.add(org.path)
            items.append(org)

        # Enriquecer con tipo/metadatos (limitado)
        for item in items[:150]:
            try:
                ident = identify(item.path, deep=True)
                item.what = ident.summary
                item.metadata["mime"] = ident.mime
                item.metadata["family"] = ident.family
            except Exception:
                item.what = item.path.suffix or "archivo"

        items.sort(key=lambda i: (i.confidence != Confidence.HIGH, -i.size))
        plan = SmartPlan(

            root=scan.root,
            items=items,
            scan_files=scan.total_files,
            duplicate_groups=len(groups),
        )
        logger.info(
            "SmartPlan: %d items, selected=%d, bytes=%d",
            len(plan.items),
            len(plan.selected_items),
            plan.selected_bytes,
        )
        return plan

    def _insight_confidence(self, insight: Insight) -> Confidence:
        if insight.category in ("installers", "empty"):
            return Confidence.MEDIUM
        if insight.category in ("large", "old_large"):
            return Confidence.MEDIUM
        if insight.category == "temp_hint":
            return Confidence.LOW
        return Confidence.LOW


    def build_organize_suggestions(
        self,
        scan: ScanResult,
        *,
        min_files_per_group: int = 3,
        base_folder_name: str = "FileSage_Organizado",
    ) -> list[PlanItem]:
        """Sugiere mover archivos a subcarpetas por tipo (musica, video, imagenes...).

        Confianza MEDIA: el usuario debe revisar. No preseleccionado.
        """
        buckets: dict[str, list] = defaultdict(list)
        folder_names = {
            "audio": "Musica",
            "video": "Videos",
            "image": "Imagenes",
            "application/pdf": "Documentos_PDF",
            "text": "Documentos_Texto",
        }
        for fi in scan.files:
            try:
                ident = identify(fi.path, deep=False)
            except Exception:
                continue
            key = ident.family if ident.family in folder_names else None
            if key is None and ident.mime in folder_names:
                key = ident.mime
            if key is None:
                # extensiones de instalador no se organizan aqui
                continue
            buckets[key].append(fi)

        items: list[PlanItem] = []
        root = scan.root
        dest_root = root / base_folder_name
        for key, files in buckets.items():
            if len(files) < min_files_per_group:
                continue
            folder = folder_names.get(key, key)
            for fi in files:
                # no mover si ya esta en la carpeta destino
                try:
                    if dest_root in fi.path.parents or folder in fi.path.parts:
                        continue
                except Exception:
                    pass
                dest = dest_root / folder / fi.path.name
                items.append(
                    PlanItem(
                        path=fi.path,
                        size=fi.size,
                        reason=f"Organizar en {base_folder_name}/{folder}/",
                        confidence=Confidence.MEDIUM,
                        category="organize",
                        selected=False,
                        what=folder,
                        metadata={
                            "action": "move",
                            "destination": str(dest),
                            "group": folder,
                        },
                    )
                )
        return items

    def to_trash_actions(self, plan: SmartPlan) -> list[ActionRecord]:
        """Convierte items seleccionados en TRASH o MOVE (organizacion)."""
        from datetime import datetime

        actions: list[ActionRecord] = []
        for item in plan.selected_items:
            if item.category == "organize" and item.metadata.get("destination"):
                actions.append(
                    ActionRecord(
                        action_id=new_action_id(),
                        action_type=ActionType.MOVE,
                        source=item.path,
                        destination=Path(item.metadata["destination"]),
                        timestamp=datetime.now(),
                        success=False,
                        message="",
                        dry_run=True,
                        metadata={
                            "confidence": item.confidence.value,
                            "category": item.category,
                            "reason": item.reason,
                        },
                    )
                )
            else:
                actions.append(
                    ActionRecord(
                        action_id=new_action_id(),
                        action_type=ActionType.TRASH,
                        source=item.path,
                        destination=None,
                        timestamp=datetime.now(),
                        success=False,
                        message="",
                        dry_run=True,
                        metadata={
                            "confidence": item.confidence.value,
                            "category": item.category,
                            "reason": item.reason,
                        },
                    )
                )
        return actions
