"""Imagenes visualmente similares (NO duplicados exactos).

Usa perceptual hash (dHash) + distancia de Hamming.
Modo independiente del pipeline de contenido binario identico.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from filesage.application.progress import ProgressReporter
from filesage.domain.models import FileInfo

logger = logging.getLogger(__name__)

IMAGE_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
}


@dataclass(frozen=True, slots=True)
class SimilarImageGroup:
    """Grupo de imagenes con hash perceptual cercano."""

    fingerprint: str  # hash representativo (el del primer archivo)
    files: tuple[FileInfo, ...]
    max_distance: int  # mayor distancia Hamming dentro del grupo
    threshold: int

    @property
    def wasted_size(self) -> int:
        """Estimacion: todo menos el archivo mas grande."""
        if len(self.files) < 2:
            return 0
        sizes = sorted((f.size for f in self.files), reverse=True)
        return sum(sizes[1:])


def is_image_path(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def difference_hash(path: Path, *, hash_size: int = 16) -> str | None:
    """dHash: robusto a redimensionado y compresion leve.

    Devuelve cadena de bits '0'/'1' de longitud hash_size * hash_size.
    """
    try:
        from PIL import Image
    except ImportError:
        logger.warning("Pillow no disponible para similar images")
        return None
    try:
        with Image.open(path) as im:
            im = im.convert("L")
            # ancho = hash_size+1 para comparar vecinos horizontales
            im = im.resize(
                (hash_size + 1, hash_size),
                getattr(Image, "Resampling", Image).LANCZOS
                if hasattr(Image, "Resampling")
                else Image.LANCZOS,
            )
            pixels = list(im.getdata())
        bits: list[str] = []
        for row in range(hash_size):
            row_start = row * (hash_size + 1)
            for col in range(hash_size):
                left = pixels[row_start + col]
                right = pixels[row_start + col + 1]
                bits.append("1" if left > right else "0")
        return "".join(bits)
    except Exception as exc:
        logger.debug("dHash fallo en %s: %s", path, exc)
        return None


def hamming_distance(a: str, b: str) -> int:
    if len(a) != len(b):
        return max(len(a), len(b))
    return sum(x != y for x, y in zip(a, b))


def find_similar_images(
    files: Sequence[FileInfo],
    *,
    threshold: int = 12,
    hash_size: int = 16,
    progress: ProgressReporter | None = None,
) -> list[SimilarImageGroup]:
    """Agrupa imagenes con distancia Hamming <= threshold.

    threshold tipico (hash_size=16 → 256 bits):
      - 0–5: casi identicas
      - 8–15: muy similares (redimension / compresion)
      - 20+: mas permisivo (puede haber falsos positivos)
    """
    images = [
        f
        for f in files
        if not f.is_symlink and is_image_path(f.path) and f.size > 0
    ]
    if progress:
        progress.report(f"Imagenes candidatas: {len(images)}", 0.05)
    if len(images) < 2:
        return []

    fingerprints: list[tuple[FileInfo, str]] = []
    total = len(images)
    for i, fi in enumerate(images):
        if progress and i % 10 == 0:
            progress.report(
                f"Hash perceptual {i}/{total}: {fi.path.name}",
                0.05 + 0.7 * (i / max(1, total)),
            )
            progress.check()
        fp = difference_hash(fi.path, hash_size=hash_size)
        if fp:
            fingerprints.append((fi, fp))

    if progress:
        progress.report(f"Agrupando {len(fingerprints)} huellas…", 0.8)

    # Union-find simple por distancia
    n = len(fingerprints)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    pair_dist: dict[tuple[int, int], int] = {}
    for i in range(n):
        if progress and i % 20 == 0:
            progress.report(f"Comparando {i}/{n}", 0.8 + 0.15 * (i / max(1, n)))
            progress.check()
        for j in range(i + 1, n):
            d = hamming_distance(fingerprints[i][1], fingerprints[j][1])
            if d <= threshold:
                union(i, j)
                pair_dist[(i, j)] = d

    buckets: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        buckets[find(i)].append(i)

    groups: list[SimilarImageGroup] = []
    for idxs in buckets.values():
        if len(idxs) < 2:
            continue
        members = tuple(fingerprints[i][0] for i in idxs)
        max_d = 0
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                i, j = idxs[a], idxs[b]
                key = (min(i, j), max(i, j))
                if key in pair_dist:
                    max_d = max(max_d, pair_dist[key])
                else:
                    max_d = max(
                        max_d,
                        hamming_distance(fingerprints[i][1], fingerprints[j][1]),
                    )
        groups.append(
            SimilarImageGroup(
                fingerprint=fingerprints[idxs[0]][1][:32],
                files=members,
                max_distance=max_d,
                threshold=threshold,
            )
        )

    groups.sort(key=lambda g: (-len(g.files), -g.wasted_size))
    if progress:
        progress.report(f"{len(groups)} grupos similares", 1.0)
    return groups
