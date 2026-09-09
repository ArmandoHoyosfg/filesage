"""Deteccion de archivos duplicados por CONTENIDO (no solo tamano).

Pipeline estricto (mejores practicas tipo fdupes/czkawka/dupeGuru):
1. Agrupar por tamano exacto (solo filtro; NUNCA resultado final)
2. Hash parcial multi-region (inicio/medio/fin)
3. Hash completo de candidatos que siguen coincidiendo
4. Clave final = tamano + hash completo
5. Verificacion por muestreo de bytes entre pares del grupo

Dos archivos del mismo tamano (p. ej. MP3 distintos de 2.7 MB) NO son
duplicados salvo que el hash completo coincida.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Sequence

from filesage.application.progress import ProgressReporter
from filesage.core.config import Settings
from filesage.domain.interfaces import IDuplicateFinder, IHasher
from filesage.domain.models import DuplicateGroup, FileInfo
from filesage.infrastructure.hasher import Hasher

logger = logging.getLogger(__name__)


class DuplicateFinder(IDuplicateFinder):
    """Solo reporta grupos con contenido binario identico."""

    def __init__(self, settings: Settings, hasher: IHasher | None = None) -> None:
        self._settings = settings
        self._hasher = hasher or Hasher(settings)

    def find(
        self,
        files: Sequence[FileInfo],
        *,
        progress: ProgressReporter | None = None,
    ) -> list[DuplicateGroup]:
        min_size = self._settings.duplicates.min_size_bytes
        candidates = [f for f in files if f.size >= min_size and not f.is_symlink]
        logger.info(
            "Buscando duplicados en %d archivos (min_size=%d)",
            len(candidates),
            min_size,
        )
        if progress:
            progress.report(f"Candidatos: {len(candidates)}", 0.05)

        if len(candidates) < 2:
            return []

        # --- 1) Solo filtro por tamano ---
        by_size: dict[int, list[FileInfo]] = defaultdict(list)
        for fi in candidates:
            by_size[fi.size].append(fi)
        size_groups = {s: lst for s, lst in by_size.items() if len(lst) > 1}
        logger.info(
            "Grupos por tamano (candidatos): %d",
            len(size_groups),
        )
        if progress:
            progress.report(
                f"Mismo tamano: {len(size_groups)} grupos candidatos (aún no son duplicados)",
                0.12,
            )
            progress.check()

        # --- 2) Hash parcial multi-region ---
        partial_map: dict[str, list[FileInfo]] = defaultdict(list)
        total_cand = sum(len(g) for g in size_groups.values())
        done_p = 0
        for size, group in size_groups.items():
            for fi in group:
                if progress:
                    progress.check()
                try:
                    ph = self._hasher.partial_hash(fi.path)
                    # size en la clave: seguridad extra
                    key = f"{size}:{ph}"
                    partial_map[key].append(fi.with_hashes(partial=ph))
                except Exception as exc:
                    logger.debug("Hash parcial fallido %s: %s", fi.path, exc)
                done_p += 1
                if progress and total_cand and done_p % 20 == 0:
                    progress.report(
                        f"Huella parcial {done_p}/{total_cand}",
                        0.12 + 0.28 * (done_p / total_cand),
                    )

        partial_groups = {k: lst for k, lst in partial_map.items() if len(lst) > 1}
        logger.info("Tras hash parcial: %d grupos", len(partial_groups))
        if progress:
            progress.report(
                f"Tras huella parcial: {len(partial_groups)} posibles",
                0.42,
            )
            progress.check()

        # --- 3) Hash completo (obligatorio para afirmar duplicado) ---
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
        if to_hash:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = [pool.submit(_hash_one, fi) for fi in to_hash]
                done = 0
                total = max(1, len(futures))
                for fut in as_completed(futures):
                    if progress:
                        progress.check()
                    fi, fh = fut.result()
                    done += 1
                    if progress and (done % 3 == 0 or done == total):
                        progress.report(
                            f"Hash completo {done}/{total}",
                            0.42 + 0.48 * (done / total),
                        )
                    if not fh:
                        continue
                    # Clave final: tamano + hash → imposible mezclar tamanos distintos
                    key = f"{fi.size}:{fh}"
                    full_map[key].append(
                        fi.with_hashes(partial=fi.hash_partial, full=fh)
                    )

        # --- 4) Construir grupos + verificacion por muestreo ---
        results: list[DuplicateGroup] = []
        for key, group in full_map.items():
            if len(group) < 2:
                continue
            # Todos deben compartir el mismo size y hash_full
            sizes = {f.size for f in group}
            hashes = {f.hash_full for f in group}
            if len(sizes) != 1 or len(hashes) != 1 or None in hashes:
                logger.warning("Grupo inconsistente descartado: %s", key)
                continue

            # Verificar por pares (muestreo) respecto al primero
            anchor = group[0]
            verified = [anchor]
            for other in group[1:]:
                if self._hasher.verify_same_content(anchor.path, other.path):
                    verified.append(other)
                else:
                    logger.warning(
                        "Falso positivo de hash descartado: %s vs %s",
                        anchor.path,
                        other.path,
                    )

            if len(verified) < 2:
                continue

            total = sum(f.size for f in verified)
            wasted = total - verified[0].size
            results.append(
                DuplicateGroup(
                    hash_full=verified[0].hash_full or key,
                    files=tuple(sorted(verified, key=lambda f: f.mtime, reverse=True)),
                    total_size=total,
                    wasted_size=wasted,
                )
            )

        results.sort(key=lambda g: g.wasted_size, reverse=True)
        if progress:
            progress.report(
                f"Duplicados confirmados: {len(results)} grupos (contenido identico)",
                1.0,
            )
        logger.info(
            "Duplicados: %d grupos, ~%.2f MB recuperables",
            len(results),
            sum(g.wasted_size for g in results) / (1024 * 1024),
        )
        return results
