"""Detecta carpetas vacias (sin archivos; puede contener solo carpetas vacias)."""

from __future__ import annotations

import os
from pathlib import Path


def find_empty_folders(root: Path, *, max_depth: int | None = None) -> list[Path]:
    """Recorrido bottom-up: una carpeta es vacia si no tiene archivos
    y todas sus subcarpetas son vacias (o no tiene subcarpetas).
    """
    root = Path(root)
    if not root.is_dir():
        return []

    empty: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        current = Path(dirpath)
        if current.resolve() == root.resolve():
            continue
        if max_depth is not None:
            try:
                if len(current.relative_to(root).parts) > max_depth:
                    continue
            except ValueError:
                continue
        try:
            # archivos reales en este nivel
            if filenames:
                continue
            # subdirs: si alguna no esta en empty, no es vacia
            child_dirs = [current / d for d in dirnames]
            if any(c not in empty for c in child_dirs):
                # child might not be in empty list if it had files
                if any(True for c in child_dirs if c.exists() and c not in empty):
                    continue
            empty.append(current)
        except OSError:
            continue
    return empty
