"""Planificacion de copia/movimiento de archivos y carpetas."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from filesage.domain.models import ActionRecord, ActionType
from filesage.infrastructure.storage import new_action_id

logger = logging.getLogger(__name__)


def _norm_src(path: Path) -> Path:
    """Normaliza rutas Windows tipo 'F:' -> 'F:\\'."""
    s = str(path).strip().strip('"')
    if len(s) == 2 and s[1] == ":":
        s = s + "\\"
    return Path(s)


def _is_drive_root(path: Path) -> bool:
    """True para 'F:\\', 'C:/', etc."""
    try:
        resolved = path.resolve()
        return resolved.parent == resolved
    except Exception:
        s = str(path)
        return len(s) <= 3 and ":" in s


def expand_sources(
    sources: list[Path],
    *,
    expand_dir_contents: bool = True,
) -> list[Path]:
    """Expande carpetas/unidades a su contenido inmediato.

    Si expand_dir_contents=True (por defecto):
      F:\\  →  F:\\carpeta1, F:\\archivo.mp3, ...
    Si False:
      se copia/mueve la carpeta como un solo bloque (salvo raíces de unidad,
      que siempre se expanden porque no tienen nombre util como destino).
    """
    out: list[Path] = []
    seen: set[str] = set()

    for raw in sources:
        src = _norm_src(Path(raw))
        if not src.exists():
            logger.info("Origen inexistente omitido: %s", src)
            continue

        must_expand = expand_dir_contents or _is_drive_root(src)
        if src.is_dir() and must_expand:
            try:
                children = sorted(src.iterdir(), key=lambda p: p.name.lower())
            except OSError as exc:
                logger.warning("No se pudo listar %s: %s", src, exc)
                continue
            if not children:
                logger.info("Carpeta vacia: %s", src)
                continue
            for child in children:
                key = str(child)
                if key not in seen:
                    seen.add(key)
                    out.append(child)
        else:
            key = str(src)
            if key not in seen:
                seen.add(key)
                out.append(src)
    return out


def resolve_dest_path(
    source: Path,
    dest_dir: Path,
    *,
    on_conflict: str = "rename",
) -> Path | None:
    """Calcula destino final. None = omitir (skip)."""
    dest_dir = Path(dest_dir)
    name = source.name
    if not name:
        # Raíz de unidad u objeto sin nombre: no se puede colocar como tal
        return None

    target = dest_dir / name
    if not target.exists():
        return target

    mode = (on_conflict or "rename").lower().strip()
    if mode == "skip":
        return None
    if mode == "overwrite":
        return target

    # rename: name_1.ext / carpeta_1
    if source.is_dir() and not source.is_symlink():
        stem, suffix = source.name, ""
    else:
        stem, suffix = source.stem, source.suffix

    for i in range(1, 10_000):
        candidate = dest_dir / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
    return None


def plan_transfer(
    sources: list[Path],
    dest_dir: Path,
    *,
    mode: str = "copy",
    on_conflict: str = "rename",
    expand_dir_contents: bool = True,
) -> list[ActionRecord]:
    """Genera acciones COPY o MOVE hacia dest_dir.

    Por defecto, las carpetas/unidades se expanden a su contenido
    (ideal para «copiar todo F:\\ a I:\\MUSICA omitiendo lo que ya existe»).

    mode: copy | move
    on_conflict: rename | skip | overwrite
    """
    dest_dir = Path(dest_dir)
    if not dest_dir.is_dir():
        return []

    action_type = ActionType.MOVE if mode == "move" else ActionType.COPY
    expanded = expand_sources(sources, expand_dir_contents=expand_dir_contents)
    plans: list[ActionRecord] = []
    seen_dest: set[str] = set()
    skipped_existing = 0

    try:
        dest_resolved = dest_dir.resolve()
    except Exception:
        dest_resolved = dest_dir

    for src in expanded:
        src = _norm_src(Path(src))
        if not src.exists():
            continue

        # No copiar/mover el destino sobre si mismo ni dentro del origen de forma insegura
        try:
            src_res = src.resolve()
            if src_res == dest_resolved:
                continue
            # Si el origen es carpeta y el destino está dentro, peligro
            if src.is_dir() and dest_resolved.is_relative_to(src_res):
                continue
        except Exception:
            pass

        target = resolve_dest_path(src, dest_dir, on_conflict=on_conflict)
        if target is None:
            skipped_existing += 1
            continue

        key = str(target)
        n = 1
        while key in seen_dest:
            if src.is_dir() and not src.is_symlink():
                target = dest_dir / f"{src.name}_{n}"
            else:
                target = dest_dir / f"{src.stem}_{n}{src.suffix}"
            key = str(target)
            n += 1
        seen_dest.add(key)

        plans.append(
            ActionRecord(
                action_id=new_action_id(),
                action_type=action_type,
                source=src,
                destination=target,
                timestamp=datetime.now(),
                success=False,
                message="",
                dry_run=True,
                metadata={
                    "transfer_mode": mode,
                    "on_conflict": on_conflict,
                    "expanded_from_dir": expand_dir_contents,
                },
            )
        )

    if not plans and skipped_existing:
        logger.info(
            "plan_transfer: 0 acciones, %d omitidos por conflicto/skip",
            skipped_existing,
        )
    return plans
