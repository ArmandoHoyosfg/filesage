"""Deteccion de archivos duplicados (IDuplicateFinder).

Pipeline de 3 etapas para maximizar velocidad y minimizar I/O:
1. Agrupar por tamano (descartar unicos)
2. Hash parcial de candidatos
3. Hash completo solo de los que siguen coincidiendo
"""

from __future__ import annotations

import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Sequence

from filesage.core.config import Settings
from filesage.domain.interfaces import IDuplicateFinder, IHasher
from filesage.domain.models import DuplicateGroup, FileInfo
from filesage.infrastructure.hasher import Hasher
from filesage.application.progress import ProgressReporter

logger = logging.getLogger(__name__)


class DuplicateFinder(IDuplicateFinder):
    """Encuentra grupos de archivos con contenido identico."""

    def __init__(self, settings: Settings, hasher: IHasher | None = None) -> None:
        self._settings = settings
        self._hasher = hasher or Hasher(settings)

    def find(
        self,
        files: Sequence[FileInfo],
        *,
        progress: ProgressReporter | None = None,
    ) -> list[DuplicateGroup]:
        """Devuelve lista de DuplicateGroup (solo grupos con 2+ archivos)."""
        min_size = self._settings.duplicates.min_size_bytes
        candidates = [f for f in files if f.size >= min_size and not f.is_symlink]
        logger.info("Buscando duplicados en %d archivos (min_size=%d)", len(candidates), min_size)
        if progress:
            progress.report(f"Candidatos a duplicados: {len(candidates)}", 0.05)

        if len(candidates) < 2:
            return []

        # --- Etapa 1: agrupar por tamano ---
        by_size: dict[int, list[FileInfo]] = defaultdict(list)
        for fi in candidates:
            by_size[fi.size].append(fi)

        size_groups = {s: lst for s, lst in by_size.items() if len(lst) > 1}
        logger.info("Grupos por tamano: %d (candidatos tras filtro: %d)", len(size_groups), sum(len(v) for v in size_groups.values()))
        if progress:
            progress.report(f"Grupos por tamaño: {len(size_groups)}", 0.15)
            progress.report("Calculando hashes parciales…", 0.2)
            progress.check()

        # --- Etapa 2: hash parcial ---
        partial_map: dict[str, list[FileInfo]] = defaultdict(list)
        for size, group in size_groups.items():
            for fi in group:
                try:
                    ph = self._hasher.partial_hash(fi.path)
                    # clave = size + partial para evitar colisiones entre tamanos distintos
                    key = f"{size}:{ph}"
                    partial_map[key].append(fi.with_hashes(partial=ph))
                except Exception as exc:
                    logger.debug("Hash parcial fallido %s: %s", fi.path, exc)

        partial_groups = {k: lst for k, lst in partial_map.items() if len(lst) > 1}
        logger.info("Grupos tras hash parcial: %d", len(partial_groups))
        if progress:
            progress.report(f"Tras hash parcial: {len(partial_groups)} grupos", 0.45)
            progress.check()

        # --- Etapa 3: hash completo (paralelo) ---
        full_map: dict[str, list[FileInfo]] = defaultdict(list)
        to_hash: list[FileInfo] = []
        for group in partial_groups.values():
            to_hash.extend(group)

        def _hash_one(fi: FileInfo) -> tuple[FileInfo, str | None]:
            try:
                return fi, self._hasher.full_hash(fi.path)
            except Exception as exc:
                logger.debug("Hash completo fallido %s: %s", fi.path, exc)
                return fi, None

        max_workers = min(8, max(1, len(to_hash)))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_hash_one, fi) for fi in to_hash]
            done = 0
            total = max(1, len(futures))
            for fut in as_completed(futures):
                if progress:
                    progress.check()
                fi, fh = fut.result()
                done += 1
                if progress and (done % 5 == 0 or done == total):
                    progress.report(
                        f"Hash completo {done}/{total}",
                        0.45 + 0.50 * (done / total),
                    )
                if fh is not None:
                    full_map[fh].append(fi.with_hashes(partial=fi.hash_partial, full=fh))

        # Construir DuplicateGroup
        results: list[DuplicateGroup] = []
        for fh, group in full_map.items():
            if len(group) < 2:
                continue
            total = sum(f.size for f in group)
            wasted = total - group[0].size  # se mantiene una copia
            results.append(
                DuplicateGroup(
                    hash_full=fh,
                    files=tuple(sorted(group, key=lambda f: f.mtime, reverse=True)),
                    total_size=total,
                    wasted_size=wasted,
                )
            )

        # Ordenar por espacio desperdiciado (mayor primero)
        results.sort(key=lambda g: g.wasted_size, reverse=True)
        if progress:
            progress.report(f"Duplicados: {len(results)} grupos", 1.0)
        logger.info("Duplicados encontrados: %d grupos, espacio desperdiciado total ~%.2f MB",
                    len(results),
                    sum(g.wasted_size for g in results) / (1024 * 1024))
        return results
