"""Capas inteligentes sobre resultados de busqueda (Fase D).

- Filtros post-escaneo (tamano, fecha, solo imagenes, excluir FileSage_*)
- Sugerencias contextuales segun la seleccion o el conjunto de resultados
- Presets de busqueda persistidos en ~/.filesage/search_presets.json
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

IMAGE_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
    ".heic",
}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}
DOC_EXTS = {".pdf", ".doc", ".docx", ".txt", ".odt", ".rtf", ".xlsx", ".xls"}


def _is_app_folder_path(path: Path) -> bool:
    return any(
        part.lower().startswith("filesage_") or part.lower() in {".filesage"}
        for part in path.parts
    )


@dataclass
class SearchFilters:
    min_size: int = 0
    max_size: int = 0  # 0 = sin limite
    newer_days: int = 0  # 0 = sin filtro
    images_only: bool = False
    exclude_app_folders: bool = True

    def allows(self, path: Path, size: int, mtime: float | None = None) -> bool:
        if self.min_size and size < self.min_size:
            return False
        if self.max_size and size > self.max_size:
            return False
        if self.images_only and path.suffix.lower() not in IMAGE_EXTS:
            return False
        if self.exclude_app_folders and _is_app_folder_path(path):
            return False
        if self.newer_days and mtime is not None:
            cutoff = time.time() - self.newer_days * 86400
            if mtime < cutoff:
                return False
        return True


@dataclass
class SearchSuggestion:
    key: str
    title: str
    detail: str
    action: str  # convert | organize | duplicates | cleanup | similar


def suggest_from_rows(rows: Iterable[dict[str, Any]]) -> list[SearchSuggestion]:
    """Sugerencias a partir de resultados o seleccion (dicts con path/size)."""
    items = list(rows)
    if not items:
        return []

    paths = [Path(str(r.get("path") or "")) for r in items]
    paths = [p for p in paths if str(p)]
    n = len(paths)
    by_ext: dict[str, int] = {}
    total = 0
    for p, r in zip(paths, items):
        ext = p.suffix.lower() or "(sin)"
        by_ext[ext] = by_ext.get(ext, 0) + 1
        total += int(r.get("size") or 0)

    tips: list[SearchSuggestion] = []

    n_img = sum(by_ext.get(e, 0) for e in IMAGE_EXTS)
    if n_img >= 2:
        tips.append(
            SearchSuggestion(
                key="convert",
                title=f"Convertir {n_img} imagenes",
                detail="Unificar formato (p. ej. a PNG) en FileSage_converted",
                action="convert",
            )
        )
        tips.append(
            SearchSuggestion(
                key="similar",
                title="Buscar imagenes similares entre resultados",
                detail="Detecta redimensionadas o recomprimidas",
                action="similar",
            )
        )

    n_aud = sum(by_ext.get(e, 0) for e in AUDIO_EXTS)
    n_vid = sum(by_ext.get(e, 0) for e in VIDEO_EXTS)
    n_doc = sum(by_ext.get(e, 0) for e in DOC_EXTS)
    media_like = n_img + n_aud + n_vid
    if media_like >= 3 or n_doc >= 3:
        tips.append(
            SearchSuggestion(
                key="organize",
                title="Organizar por tipo",
                detail="Mover imagenes/audio/video/documentos a subcarpetas",
                action="organize",
            )
        )

    if n >= 2:
        tips.append(
            SearchSuggestion(
                key="duplicates",
                title="Buscar duplicados exactos en la seleccion",
                detail=f"{n} archivos seleccionados o listados",
                action="duplicates",
            )
        )

    if total > 50 * 1024 * 1024:
        tips.append(
            SearchSuggestion(
                key="cleanup",
                title="Revisar en Limpieza profunda",
                detail=f"Hay ~{total // (1024*1024)} MB en estos resultados",
                action="cleanup",
            )
        )

    # dedupe by key
    seen: set[str] = set()
    out: list[SearchSuggestion] = []
    for s in tips:
        if s.key not in seen:
            seen.add(s.key)
            out.append(s)
    return out[:5]


PRESETS_PATH = Path.home() / ".filesage" / "search_presets.json"


@dataclass
class SearchPreset:
    name: str
    query: str = ""
    ext_filter: str = ""
    use_meta: bool = False
    use_path: bool = False
    min_size: int = 0
    max_size: int = 0
    newer_days: int = 0
    images_only: bool = False
    exclude_app_folders: bool = True


def load_presets() -> list[SearchPreset]:
    if not PRESETS_PATH.exists():
        return []
    try:
        data = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
        out = []
        for item in data if isinstance(data, list) else []:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            out.append(
                SearchPreset(
                    name=str(item["name"]),
                    query=str(item.get("query") or ""),
                    ext_filter=str(item.get("ext_filter") or ""),
                    use_meta=bool(item.get("use_meta")),
                    use_path=bool(item.get("use_path")),
                    min_size=int(item.get("min_size") or 0),
                    max_size=int(item.get("max_size") or 0),
                    newer_days=int(item.get("newer_days") or 0),
                    images_only=bool(item.get("images_only")),
                    exclude_app_folders=bool(
                        item.get("exclude_app_folders", True)
                    ),
                )
            )
        return out
    except Exception:
        return []


def save_preset(preset: SearchPreset) -> None:
    PRESETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    current = load_presets()
    current = [p for p in current if p.name != preset.name]
    current.append(preset)
    PRESETS_PATH.write_text(
        json.dumps([asdict(p) for p in current], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def delete_preset(name: str) -> None:
    current = [p for p in load_presets() if p.name != name]
    PRESETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRESETS_PATH.write_text(
        json.dumps([asdict(p) for p in current], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
