"""Copia/movimiento con progreso, cancelacion, timeout y salto por cuelgue.

Evita bloqueos largos en USB: copia por bloques, timeout y deteccion de stall.
"""

from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from filesage.domain.exceptions import ActionError, CancelledError

logger = logging.getLogger(__name__)

ProgressCb = Callable[[str, float], None]
CHUNK = 1024 * 1024  # 1 MiB
DEFAULT_FILE_TIMEOUT_S = 45.0
DEFAULT_STALL_S = 12.0  # sin bytes nuevos → omitir archivo

def adaptive_timeout_s(size_bytes: int, base: float = DEFAULT_FILE_TIMEOUT_S) -> float:
    """Archivos pequeños no merecen esperar 90s en un USB muerto."""
    mb = max(0.1, size_bytes / (1024 * 1024))
    # ~8 s por MB, mínimo 12s, máximo base
    return float(min(base, max(12.0, mb * 8.0)))


@dataclass
class CopyStats:
    copied: int = 0
    skipped: int = 0
    incomplete: list[str] = field(default_factory=list)

    def summary(self, folder: str = "") -> str:
        base = f"{self.copied} ok"
        if self.skipped:
            base += f", {self.skipped} omitidos/incompletos"
        if folder:
            return f"{folder}: {base}"
        return base


def _os_walk(root: Path):
    import os

    for dirpath, dirnames, filenames in os.walk(root):
        yield Path(dirpath), dirnames, filenames


def collect_files(source: Path) -> list[Path]:
    source = Path(source)
    if source.is_file() or source.is_symlink():
        return [source]
    out: list[Path] = []
    try:
        for dirpath, _dirnames, filenames in _os_walk(source):
            for name in filenames:
                out.append(Path(dirpath) / name)
    except OSError as exc:
        raise ActionError(f"No se pudo listar {source}: {exc}") from exc
    return out


def _copy_file_chunked(
    src: Path,
    dst: Path,
    *,
    on_progress: ProgressCb | None = None,
    check_cancel: Callable[[], None] | None = None,
    timeout_s: float = DEFAULT_FILE_TIMEOUT_S,
    stall_s: float = DEFAULT_STALL_S,
) -> None:
    t0 = time.time()
    last_data = t0
    size = 0
    try:
        size = src.stat().st_size
    except OSError as exc:
        raise OSError(f"stat: {exc}") from exc

    # Timeout adaptativo: un MP3 de 4 MB no espera 90s
    if timeout_s >= DEFAULT_FILE_TIMEOUT_S - 0.1:
        timeout_s = adaptive_timeout_s(size, base=timeout_s)

    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".filesage_partial")
    copied = 0
    last_ui = 0.0

    try:
        with open(src, "rb") as fin, open(tmp, "wb") as fout:
            while True:
                if check_cancel:
                    check_cancel()
                now = time.time()
                if now - t0 > timeout_s:
                    raise TimeoutError(
                        f"Timeout {int(timeout_s)}s en {src.name}"
                    )
                if now - last_data > stall_s:
                    raise TimeoutError(
                        f"Sin progreso {int(stall_s)}s en {src.name} "
                        f"(posible sector danado o USB colgado)"
                    )
                try:
                    block = fin.read(CHUNK)
                except OSError as exc:
                    raise OSError(f"lectura: {exc}") from exc
                if not block:
                    break
                try:
                    fout.write(block)
                except OSError as exc:
                    raise OSError(f"escritura: {exc}") from exc
                copied += len(block)
                last_data = time.time()
                now = last_data
                if on_progress and (now - last_ui > 0.5 or (size and copied >= size)):
                    last_ui = now
                    frac = min(0.99, copied / size) if size else 0.5
                    mb = copied / (1024 * 1024)
                    total_mb = size / (1024 * 1024) if size else 0
                    on_progress(
                        f"{src.name[:40]} · {mb:.1f}/{total_mb:.1f} MB",
                        frac,
                    )
        try:
            shutil.copystat(str(src), str(tmp), follow_symlinks=True)
        except OSError:
            pass
        tmp.replace(dst)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink(missing_ok=True)  # type: ignore[call-arg]
        except TypeError:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
        except OSError:
            pass
        raise


def copy_with_progress(
    source: Path,
    destination: Path,
    *,
    on_progress: ProgressCb | None = None,
    check_cancel: Callable[[], None] | None = None,
    file_timeout_s: float = DEFAULT_FILE_TIMEOUT_S,
    stall_s: float = DEFAULT_STALL_S,
) -> str:
    source = Path(source)
    destination = Path(destination)
    if not source.exists():
        raise ActionError(f"No existe el origen: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stats = CopyStats()

    if source.is_file() or source.is_symlink():
        if on_progress:
            on_progress(source.name, 0.0)
        if check_cancel:
            check_cancel()
        try:
            _copy_file_chunked(
                source,
                destination,
                on_progress=on_progress,
                check_cancel=check_cancel,
                timeout_s=file_timeout_s,
                stall_s=stall_s,
            )
            stats.copied = 1
        except CancelledError:
            raise
        except Exception as exc:
            stats.skipped = 1
            stats.incomplete.append(f"{source.name}: {exc}")
            raise ActionError(
                f"No se pudo copiar {source.name}: {exc}"
            ) from exc
        if on_progress:
            on_progress(source.name, 1.0)
        return f"Copiado archivo: {source.name}"

    files = collect_files(source)
    total = max(1, len(files))
    if on_progress:
        on_progress(f"Carpeta {source.name}: {len(files)} archivos", 0.0)
    destination.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    for i, src_file in enumerate(files):
        if check_cancel:
            try:
                check_cancel()
            except CancelledError:
                msg = (
                    f"Cancelado en {source.name}: {stats.summary()} · "
                    f"{i}/{total} revisados"
                )
                if stats.incomplete:
                    msg += f" · incompletos: {len(stats.incomplete)}"
                if on_progress:
                    on_progress(msg, i / total)
                raise CancelledError(msg) from None

        try:
            rel = src_file.relative_to(source)
        except ValueError:
            rel = Path(src_file.name)
        dest_file = destination / rel

        try:
            def _cb(msg, frac, _i=i, _total=total):
                if on_progress:
                    on_progress(
                        f"{source.name}: {_i+1}/{_total} · {msg}",
                        (_i + frac) / _total,
                    )

            _copy_file_chunked(
                src_file,
                dest_file,
                on_progress=_cb if on_progress else None,
                check_cancel=check_cancel,
                timeout_s=file_timeout_s,
                stall_s=stall_s,
            )
            stats.copied += 1
        except CancelledError:
            raise
        except Exception as exc:
            stats.skipped += 1
            stats.incomplete.append(f"{rel}: {exc}")
            logger.warning("Omitido %s: %s", src_file, exc)
            if on_progress:
                on_progress(
                    f"{source.name}: omitido {src_file.name[:40]} — {exc}",
                    (i + 1) / total,
                )
            continue

        if on_progress and (i % 2 == 0 or i + 1 == total):
            elapsed = max(0.001, time.time() - t0)
            rate = stats.copied / elapsed
            on_progress(
                f"{source.name}: {i+1}/{total} · {rate:.1f} arch/s · {src_file.name[:36]}",
                (i + 1) / total,
            )

    if stats.copied == 0 and files:
        detail = stats.incomplete[0] if stats.incomplete else "sin detalle"
        raise ActionError(
            f"No se pudo copiar nada de «{source.name}». {detail}"
        )

    msg = f"Copiada carpeta {source.name}: {stats.summary()}"
    if stats.incomplete:
        # Primeros incompletos en el mensaje (el resto en log)
        sample = "; ".join(stats.incomplete[:5])
        msg += f" | Incompletos: {sample}"
        if len(stats.incomplete) > 5:
            msg += f" (+{len(stats.incomplete)-5} mas)"
    return msg


def move_with_progress(
    source: Path,
    destination: Path,
    *,
    on_progress: ProgressCb | None = None,
    check_cancel: Callable[[], None] | None = None,
    file_timeout_s: float = DEFAULT_FILE_TIMEOUT_S,
    stall_s: float = DEFAULT_STALL_S,
) -> str:
    source = Path(source)
    destination = Path(destination)
    if not source.exists():
        raise ActionError(f"No existe el origen: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        if on_progress:
            on_progress(f"Moviendo {source.name}…", 0.1)
        if check_cancel:
            check_cancel()
        shutil.move(str(source), str(destination))
        if on_progress:
            on_progress(f"Movido {source.name}", 1.0)
        return f"Movido: {source.name}"
    except CancelledError:
        raise
    except OSError:
        msg = copy_with_progress(
            source,
            destination,
            on_progress=on_progress,
            check_cancel=check_cancel,
            file_timeout_s=file_timeout_s,
            stall_s=stall_s,
        )
        try:
            if source.is_dir() and not source.is_symlink():
                shutil.rmtree(source, ignore_errors=True)
            elif source.exists():
                source.unlink()
        except OSError as exc:
            raise ActionError(
                f"Copiado pero no se pudo borrar origen {source}: {exc}"
            ) from exc
        return msg + " (move entre discos)"
