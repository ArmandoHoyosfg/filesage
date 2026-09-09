"""Conversion inteligente de imagenes (Pillow).

Reglas anti-duplicado / anti-reconversion:
1. Formato real (cabecera puremagic + Pillow), no solo la extension.
2. Si origen ya es el formato pedido → omitir.
3. Si el archivo esta bajo FileSage_converted → omitir.
4. Si el destino (stem.ext) ya existe → omitir (no crear *_converted).
5. Si el nombre parece producto de conversion previa (*_converted.*) → omitir como origen.
6. Opcional force=True para sobrescribir destino existente.
"""

from __future__ import annotations

import logging
import re
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
    "ico": "ICO",
}

_EQUIV = {
    "jpeg": "jpg",
    "jpg": "jpg",
    "tif": "tiff",
    "tiff": "tiff",
    "jpe": "jpg",
}

# puremagic / Pillow format name → our norm ext
_FORMAT_TO_EXT = {
    "JPEG": "jpg",
    "JPG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
    "BMP": "bmp",
    "TIFF": "tiff",
    "GIF": "gif",
    "ICO": "ico",
    "MPO": "jpg",
}

INPUT_GLOBS = (
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.jpe",
    "*.webp",
    "*.bmp",
    "*.tif",
    "*.tiff",
    "*.gif",
    "*.ico",
)

OUTPUT_DIR_NAME = "FileSage_converted"
_CONVERTED_NAME_RE = re.compile(r"_converted(\d+)?$", re.IGNORECASE)


@dataclass
class ConvertResult:
    source: Path
    destination: Path | None
    ok: bool
    message: str
    skipped: bool = False
    detected_format: str | None = None


def default_output_dir(source_dir: Path) -> Path:
    return source_dir / OUTPUT_DIR_NAME


def _norm_ext(ext: str) -> str:
    e = ext.lower().lstrip(".")
    return _EQUIV.get(e, e)


def is_inside_converted_dir(path: Path) -> bool:
    try:
        return OUTPUT_DIR_NAME in path.resolve().parts
    except Exception:
        return OUTPUT_DIR_NAME in path.parts


def looks_like_converted_name(path: Path) -> bool:
    """True si el stem termina en _converted / _converted2 (producto previo)."""
    return bool(_CONVERTED_NAME_RE.search(path.stem))


def detect_image_format(path: Path) -> str | None:
    """Detecta formato real de imagen. Devuelve extension normalizada o None."""
    path = Path(path)

    # 1) puremagic (cabecera)
    try:
        import puremagic

        matches = puremagic.magic_file(str(path))
        for m in matches or []:
            mime = (getattr(m, "mime_type", None) or "").lower()
            if mime.startswith("image/"):
                sub = mime.split("/", 1)[-1]
                if sub in ("jpeg", "jpg", "pjpeg"):
                    return "jpg"
                if sub in ("tiff", "tif"):
                    return "tiff"
                if sub in FORMAT_MAP or sub in _EQUIV:
                    return _norm_ext(sub)
            # extension hint from puremagic
            ext = (getattr(m, "extension", None) or "").lstrip(".")
            if ext:
                n = _norm_ext(ext)
                if n in FORMAT_MAP or n in ("jpg", "tiff"):
                    return n
    except Exception as exc:
        logger.debug("puremagic detect %s: %s", path, exc)

    # 2) Pillow
    try:
        from PIL import Image

        with Image.open(path) as im:
            fmt = (im.format or "").upper()
            if fmt in _FORMAT_TO_EXT:
                return _FORMAT_TO_EXT[fmt]
    except Exception as exc:
        logger.debug("Pillow detect %s: %s", path, exc)

    # 3) extension del nombre
    if path.suffix:
        n = _norm_ext(path.suffix)
        if n in FORMAT_MAP or n in ("jpg", "tiff"):
            return n
    return None


def destination_path(source: Path, dest_dir: Path, target_ext: str) -> Path:
    out_suffix = "jpg" if target_ext == "jpg" else target_ext
    return Path(dest_dir) / f"{source.stem}.{out_suffix}"


def convert_one(
    source: Path,
    dest_dir: Path,
    *,
    target_ext: str = "png",
    quality: int = 90,
    force: bool = False,
) -> ConvertResult:
    try:
        from PIL import Image
    except ImportError as e:
        return ConvertResult(source, None, False, f"Pillow no disponible: {e}")

    source = Path(source)
    target_ext = _norm_ext(target_ext)
    if target_ext not in FORMAT_MAP:
        return ConvertResult(source, None, False, f"Formato no soportado: {target_ext}")

    if not source.is_file():
        return ConvertResult(source, None, False, "No es un archivo")

    if is_inside_converted_dir(source):
        return ConvertResult(
            source,
            None,
            True,
            "Omitido: dentro de FileSage_converted",
            skipped=True,
        )

    if looks_like_converted_name(source):
        return ConvertResult(
            source,
            None,
            True,
            "Omitido: nombre de conversion previa (*_converted)",
            skipped=True,
        )

    detected = detect_image_format(source)
    if detected is None:
        return ConvertResult(
            source, None, False, "No se reconoce como imagen", detected_format=None
        )

    if detected == target_ext:
        return ConvertResult(
            source,
            None,
            True,
            f"Omitido: ya es {target_ext} (detectado: {detected})",
            skipped=True,
            detected_format=detected,
        )

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = destination_path(source, dest_dir, target_ext)

    if dest.exists() and not force:
        # Si el destino es mas reciente que el origen, casi seguro conversion previa
        try:
            same_generation = dest.stat().st_mtime >= source.stat().st_mtime - 1
        except OSError:
            same_generation = True
        msg = (
            f"Omitido: ya existe {dest.name}"
            + (" (conversion previa)" if same_generation else "")
        )
        return ConvertResult(
            source,
            dest,
            True,
            msg,
            skipped=True,
            detected_format=detected,
        )

    try:
        with Image.open(source) as im:
            out = im
            fmt = FORMAT_MAP.get(target_ext, "PNG")
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
        return ConvertResult(
            source,
            dest,
            True,
            f"OK ({detected} → {target_ext})",
            detected_format=detected,
        )
    except Exception as e:
        logger.exception("convert failed %s", source)
        return ConvertResult(source, None, False, str(e), detected_format=detected)


def convert_path(
    path: Path,
    *,
    target_ext: str = "png",
    output_dir: Path | None = None,
    quality: int = 90,
    recursive: bool = False,
    force: bool = False,
) -> list[ConvertResult]:
    path = Path(path)
    results: list[ConvertResult] = []
    target_ext = _norm_ext(target_ext)

    if path.is_file():
        dest_dir = output_dir or default_output_dir(path.parent)
        results.append(
            convert_one(
                path, dest_dir, target_ext=target_ext, quality=quality, force=force
            )
        )
        return results

    if not path.is_dir():
        return [ConvertResult(path, None, False, "Ruta invalida")]

    dest_dir = output_dir or default_output_dir(path)
    try:
        dest_resolved = dest_dir.resolve()
    except Exception:
        dest_resolved = dest_dir

    pattern_iter = path.rglob if recursive else path.glob
    files: list[Path] = []
    for g in INPUT_GLOBS:
        files.extend(pattern_iter(g))
    files = sorted({f.resolve() for f in files if f.is_file()})

    for f in files:
        try:
            fr = f.resolve()
            if dest_resolved in fr.parents or fr.parent == dest_resolved:
                continue
        except Exception:
            pass
        if is_inside_converted_dir(f):
            continue
        if looks_like_converted_name(f):
            results.append(
                ConvertResult(
                    f,
                    None,
                    True,
                    "Omitido: nombre de conversion previa",
                    skipped=True,
                )
            )
            continue
        results.append(
            convert_one(
                f, dest_dir, target_ext=target_ext, quality=quality, force=force
            )
        )
    return results
