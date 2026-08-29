"""Crear ZIP de una carpeta (stdlib)."""

from __future__ import annotations

import shutil
from pathlib import Path


def zip_folder(source: Path, dest_zip: Path | None = None) -> Path:
    source = Path(source)
    if not source.is_dir():
        raise ValueError(f"No es carpeta: {source}")
    if dest_zip is None:
        dest_zip = source.parent / f"{source.name}.zip"
    dest_zip = Path(dest_zip)
    # shutil.make_archive needs path without .zip suffix
    base = dest_zip.with_suffix("")
    out = shutil.make_archive(str(base), "zip", root_dir=str(source))
    return Path(out)
