"""Conversion inteligente de imagenes (Pillow).

- No reconvierte si el formato de origen == formato de salida.
- No procesa archivos dentro de carpetas FileSage_converted.
- Escribe siempre en carpeta de salida dedicada.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

FORMAT_MAP = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "bmp": "BMP",
    "tiff": "TIFF",
    "tif": "TIFF",
    "gif": "GIF",
}

# Normaliza extensiones equivalentes
_EQUIV = {
    "jpeg": "jpg",
    "jpg": "jpg",
    "tif": "tiff",
    "tiff": "tiff",
}

INPUT_GLOBS = (
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.webp",
    "*.bmp",
    "*.tif",
    "*.tiff",
    "*.gif",
    "*.ico",
)

OUTPUT_DIR_NAME = "FileSage_converted"


@dataclass
class ConvertResult:
    source: Path
    destination: Path | None
    ok: bool
    message: str
    skipped: bool = False


def default_output_dir(source_dir: Path) -> Path:
    return source_dir / OUTPUT_DIR_NAME


def _norm_ext(ext: str) -> str:
    e = ext.lower().lstrip(".")
    return _EQUIV.get(e, e)


def is_inside_converted_dir(path: Path) -> bool:
    """True si el archivo vive bajo alguna carpeta FileSage_converted."""
    try:
        return OUTPUT_DIR_NAME in path.resolve().parts
    except Exception:
        return OUTPUT_DIR_NAME in path.parts


def convert_one(
    source: Path,
    dest_dir: Path,
    *,
    target_ext: str = "png",
    quality: int = 90,
) -> ConvertResult:
    try:
        from PIL import Image
    except ImportError as e:
        return ConvertResult(source, None, False, f"Pillow no disponible: {e}")

    source = Path(source)
    target_ext = _norm_ext(target_ext)
    if target_ext not in FORMAT_MAP and target_ext not in ("jpg", "tiff"):
        # jpg maps via FORMAT_MAP after norm
        if target_ext not in FORMAT_MAP:
            return ConvertResult(source, None, False, f"Formato no soportado: {target_ext}")

    src_ext = _norm_ext(source.suffix)
    if src_ext == target_ext:
        return ConvertResult(
            source,
            None,
            True,
            f"Omitido: ya es {target_ext}",
            skipped=True,
        )

    if is_inside_converted_dir(source):
        return ConvertResult(
            source,
            None,
            True,
            "Omitido: archivo dentro de FileSage_converted",
            skipped=True,
        )

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_suffix = "jpg" if target_ext == "jpg" else target_ext
    dest = dest_dir / f"{source.stem}.{out_suffix}"

    if dest.exists():
        dest = dest_dir / f"{source.stem}_converted.{out_suffix}"

    try:
        with Image.open(source) as im:
            out = im
            fmt = FORMAT_MAP.get(target_ext, FORMAT_MAP.get(out_suffix, "PNG"))
            if fmt == "JPEG" and im.mode in ("RGBA", "P", "LA"):
                out = im.convert("RGB")
            elif fmt == "PNG" and im.mode == "P":
                out = im.convert("RGBA")
            save_kwargs: dict = {}
            if fmt == "JPEG":
                save_kwargs["quality"] = max(1, min(100, quality))
                save_kwargs["optimize"] = True
            if fmt == "WEBP":
                save_kwargs["quality"] = max(1, min(100, quality))
            out.save(dest, fmt, **save_kwargs)
        return ConvertResult(source, dest, True, "OK")
    except Exception as e:
        logger.exception("convert failed %s", source)
        return ConvertResult(source, None, False, str(e))


def convert_path(
    path: Path,
    *,
    target_ext: str = "png",
    output_dir: Path | None = None,
    quality: int = 90,
    recursive: bool = False,
) -> list[ConvertResult]:
    path = Path(path)
    results: list[ConvertResult] = []
    target_ext = _norm_ext(target_ext)

    if path.is_file():
        dest_dir = output_dir or default_output_dir(path.parent)
        results.append(
            convert_one(path, dest_dir, target_ext=target_ext, quality=quality)
        )
        return results

    if not path.is_dir():
        return [ConvertResult(path, None, False, "Ruta invalida")]

    dest_dir = output_dir or default_output_dir(path)
    pattern_iter = path.rglob if recursive else path.glob
    files: list[Path] = []
    for g in INPUT_GLOBS:
        files.extend(pattern_iter(g))
    files = sorted({f.resolve() for f in files if f.is_file()})

    for f in files:
        try:
            if dest_dir.resolve() in f.resolve().parents or f.parent.resolve() == dest_dir.resolve():
                continue
        except Exception:
            pass
        if is_inside_converted_dir(f):
            continue
        results.append(
            convert_one(f, dest_dir, target_ext=target_ext, quality=quality)
        )
    return results
