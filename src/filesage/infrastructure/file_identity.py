"""Identidad de archivo: tipo MIME, etiqueta humana y metadatos ligeros.

Dependencias activas (no deprecadas):
- puremagic: deteccion por magic numbers (alternativa pure-Python a libmagic)
- Pillow: imagenes + EXIF
- tinytag: audio (MIT, solo lectura; alternativa a mutagen GPL)
- pypdf: PDF (sucesor de PyPDF2, no usar PyPDF2)
"""

from __future__ import annotations

import logging
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

FAMILY_LABELS = {
    "image": "Imagen",
    "audio": "Audio",
    "video": "Video",
    "text": "Texto",
    "application/pdf": "Documento PDF",
    "application/zip": "Archivo comprimido",
    "application/x-tar": "Archivo comprimido",
    "application/gzip": "Archivo comprimido",
    "application/x-7z-compressed": "Archivo comprimido",
    "application/vnd.ms-excel": "Hoja de calculo",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Hoja de calculo",
    "application/msword": "Documento Word",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Documento Word",
    "application/vnd.ms-powerpoint": "Presentacion",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "Presentacion",
    "application/x-msdownload": "Ejecutable / instalador",
    "application/x-msi": "Instalador Windows",
    "application/x-iso9660-image": "Imagen de disco",
    "application/octet-stream": "Binario",
}

EXT_HINTS = {
    ".exe": "Instalador / ejecutable Windows",
    ".msi": "Instalador Windows",
    ".dmg": "Instalador macOS",
    ".pkg": "Instalador macOS",
    ".deb": "Paquete Debian/Ubuntu",
    ".rpm": "Paquete RPM",
    ".appimage": "AppImage Linux",
    ".iso": "Imagen de disco ISO",
    ".img": "Imagen de disco",
    ".apk": "Aplicacion Android",
    ".pdf": "Documento PDF",
    ".zip": "ZIP comprimido",
    ".rar": "RAR comprimido",
    ".7z": "7-Zip comprimido",
    ".tar": "TAR",
    ".gz": "Gzip",
    ".jpg": "Imagen JPEG",
    ".jpeg": "Imagen JPEG",
    ".png": "Imagen PNG",
    ".gif": "Imagen GIF",
    ".webp": "Imagen WebP",
    ".heic": "Imagen HEIC",
    ".mp3": "Audio MP3",
    ".flac": "Audio FLAC",
    ".wav": "Audio WAV",
    ".m4a": "Audio M4A",
    ".ogg": "Audio OGG",
    ".mp4": "Video MP4",
    ".mkv": "Video MKV",
    ".avi": "Video AVI",
    ".mov": "Video QuickTime",
    ".txt": "Texto plano",
    ".md": "Markdown",
    ".csv": "CSV",
    ".json": "JSON",
    ".xml": "XML",
    ".html": "HTML",
    ".py": "Codigo Python",
    ".js": "Codigo JavaScript",
    ".log": "Registro (log)",
    ".tmp": "Temporal",
    ".bak": "Copia de seguridad",
}


@dataclass
class FileIdentity:
    path: Path
    mime: str
    label: str
    family: str
    details: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if self.details:
            return f"{self.label} · " + " · ".join(self.details[:3])
        return self.label


def _guess_mime(path: Path) -> str:
    # 1) puremagic (cabecera real)
    try:
        import puremagic

        matches = puremagic.magic_file(str(path))
        if matches:
            best = matches[0]
            mime = getattr(best, "mime_type", None) or ""
            if mime and mime != "application/octet-stream":
                return mime
    except Exception as exc:
        logger.debug("puremagic fallo para %s: %s", path, exc)

    # 2) mimetypes por extension
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def _family(mime: str) -> str:
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("text/"):
        return "text"
    return mime


def _base_label(path: Path, mime: str) -> str:
    ext = path.suffix.lower()
    if ext in EXT_HINTS:
        return EXT_HINTS[ext]
    fam = _family(mime)
    if fam in FAMILY_LABELS:
        return FAMILY_LABELS[fam]
    if mime in FAMILY_LABELS:
        return FAMILY_LABELS[mime]
    return mime or "Archivo"


def _image_details(path: Path) -> list[str]:
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
    except ImportError:
        return []
    try:
        with Image.open(path) as img:
            details = [f"{img.width}x{img.height}"]
            if img.format:
                details.append(str(img.format))
            try:
                exif = img.getexif()
                if exif:
                    for tag_id, value in exif.items():
                        name = TAGS.get(tag_id, "")
                        if name in ("DateTime", "DateTimeOriginal") and value:
                            details.append(f"fecha {value}")
                            break
                    for tag_id, value in exif.items():
                        name = TAGS.get(tag_id, "")
                        if name == "Model" and value:
                            details.append(str(value)[:40])
                            break
            except Exception:
                pass
            return details[:4]
    except Exception as exc:
        logger.debug("No se pudo leer imagen %s: %s", path, exc)
        return []


def _audio_details(path: Path) -> list[str]:
    """Usa tinytag (MIT) en lugar de mutagen (GPL)."""
    try:
        from tinytag import TinyTag
    except ImportError:
        return []
    try:
        tag = TinyTag.get(str(path))
        details: list[str] = []
        if tag.duration:
            secs = int(tag.duration)
            details.append(f"{secs // 60}:{secs % 60:02d}")
        if tag.artist:
            details.append(str(tag.artist)[:40])
        if tag.title:
            details.append(str(tag.title)[:40])
        if tag.album:
            details.append(str(tag.album)[:40])
        return details[:4]
    except Exception as exc:
        logger.debug("No se pudo leer audio %s: %s", path, exc)
        return []


def _pdf_details(path: Path) -> list[str]:
    """Usa pypdf (activo). No usar PyPDF2 (deprecado)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return []
    try:
        reader = PdfReader(str(path))
        details: list[str] = []
        n = len(reader.pages)
        if n:
            details.append(f"{n} pag.")
        meta = reader.metadata
        if meta is not None:
            title = getattr(meta, "title", None)
            if title:
                details.append(str(title)[:50])
        return details[:3]
    except Exception as exc:
        logger.debug("No se pudo leer PDF %s: %s", path, exc)
        return []


def identify(path: Path | str, *, deep: bool = True) -> FileIdentity:
    path = Path(path)
    mime = _guess_mime(path)
    family = _family(mime)
    label = _base_label(path, mime)
    details: list[str] = []

    if deep and path.is_file():
        if family == "image" or path.suffix.lower() in {
            ".jpg", ".jpeg", ".png", ".gif", ".webp", ".tiff", ".tif", ".bmp"
        }:
            details = _image_details(path)
        elif family == "audio" or path.suffix.lower() in {
            ".mp3", ".flac", ".ogg", ".m4a", ".wav", ".wma", ".aiff"
        }:
            details = _audio_details(path)
        elif mime == "application/pdf" or path.suffix.lower() == ".pdf":
            details = _pdf_details(path)

    return FileIdentity(path=path, mime=mime, label=label, family=family, details=details)


def identify_many(paths: list[Path], *, deep: bool = True, limit: int = 200) -> dict[Path, FileIdentity]:
    result: dict[Path, FileIdentity] = {}
    for i, p in enumerate(paths):
        if i >= limit:
            break
        result[p] = identify(p, deep=deep)
    return result
