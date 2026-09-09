"""Busqueda inteligente de archivos.

Principios:
- La coincidencia prioritaria es el **nombre** del archivo.
- La ruta se evalua en forma **relativa** al directorio de busqueda (no la ruta absoluta del disco).
- Carpetas generadas por FileSage (FileSage_converted, etc.) no cuentan como coincidencia
  de ruta: son el contexto de trabajo, no el contenido que el usuario busca.
- Metadatos: solo aportan si el termino no es generico (p. ej. "imagen", "jpeg" solo).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# Carpetas que la propia app crea / usa como contenedores
APP_CONTEXT_DIRS = frozenset(
    {
        "filesage_converted",
        "filesage_organizado",
        "filesage_organized",
        ".filesage",
    }
)

# Terminos demasiado genericos en metadatos (casi cualquier imagen/audio los tiene)
GENERIC_META_TOKENS = frozenset(
    {
        "imagen",
        "image",
        "jpeg",
        "jpg",
        "png",
        "webp",
        "gif",
        "bmp",
        "tiff",
        "audio",
        "video",
        "archivo",
        "file",
        "document",
        "documento",
        "text",
        "texto",
        "application",
        "octet-stream",
    }
)


@dataclass
class SearchHit:
    path: Path
    name: str
    parent: str
    size: int
    what: str
    score: int  # mayor = mejor
    match_why: str  # explicacion corta


def _norm(s: str) -> str:
    return s.lower().strip()


def _is_app_context_dir(name: str) -> bool:
    return _norm(name) in APP_CONTEXT_DIRS or _norm(name).startswith("filesage_")


def _path_parts_relative(file_path: Path, root: Path) -> list[str]:
    try:
        rel = file_path.resolve().relative_to(root.resolve())
    except Exception:
        try:
            rel = Path(*file_path.parts[-3:])
        except Exception:
            return []
    # partes de directorio (sin el nombre de archivo)
    return list(rel.parts[:-1]) if len(rel.parts) > 1 else []


def _meta_is_useful_match(query: str, meta: str) -> bool:
    """True si la query aporta algo especifico en metadatos, no solo 'JPEG'/'Imagen'."""
    q = _norm(query)
    m = _norm(meta)
    if not q or q not in m:
        return False
    # query generica corta que aparece en casi todo
    if q in GENERIC_META_TOKENS:
        return False
    # si la query es solo extension tipica
    if q in {".jpg", ".jpeg", ".png", ".webp", ".mp3", ".pdf"}:
        return False
    return True


def match_file(
    *,
    path: Path,
    size: int,
    root: Path,
    query: str,
    what: str = "",
    mime: str = "",
    use_path: bool = False,
    use_meta: bool = False,
    ext_filter: str = "",
) -> SearchHit | None:
    """Decide si un archivo entra en resultados y con que puntuacion."""
    q = _norm(query)
    if not q:
        return None

    name = path.name
    name_l = name.lower()
    ext = path.suffix.lower()

    if ext_filter:
        ef = ext_filter.lower()
        if not ef.startswith("."):
            ef = "." + ef
        if ext != ef:
            return None

    score = 0
    reasons: list[str] = []

    # 1) Nombre de archivo (principal)
    if q in name_l:
        score += 100
        reasons.append("nombre")
        # bonus: empieza por la query o es casi exacto
        stem = path.stem.lower()
        if stem == q or stem.startswith(q):
            score += 30
        if q in ext:
            score += 10

    # 2) Ruta relativa — solo si el usuario lo pide; nunca por carpetas de la app
    if use_path:
        parts = _path_parts_relative(path, root)
        meaningful = [p for p in parts if not _is_app_context_dir(p)]
        rel_hay = "/".join(meaningful).lower()
        if q in rel_hay:
            score += 40
            reasons.append("ruta")
        # Si SOLO coincidiria la carpeta FileSage_* no sumamos nada (ya filtrado)

    # 3) Metadatos — solo si el termino no es generico
    meta_blob = f"{what} {mime}".strip()
    if use_meta and meta_blob and _meta_is_useful_match(q, meta_blob):
        score += 25
        reasons.append("metadatos")

    if score <= 0:
        return None

    return SearchHit(
        path=path,
        name=name,
        parent=str(path.parent),
        size=size,
        what=what,
        score=score,
        match_why="+".join(reasons) if reasons else "nombre",
    )


def rank_hits(hits: Iterable[SearchHit], *, limit: int = 500) -> list[SearchHit]:
    return sorted(hits, key=lambda h: (-h.score, -h.size))[:limit]
