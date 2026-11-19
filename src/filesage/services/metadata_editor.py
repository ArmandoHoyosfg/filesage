"""Edicion segura de metadatos (PDF, JPEG, audio).

Principios:
- Escritura atomica (temp → verificar → reemplazar)
- Backup opcional antes de modificar
- Dry-run: solo muestra el plan
- JPEG: piexif sin re-encodear pixeles
- Audio: mutagen (tags, sin re-encodear el stream)
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from filesage.domain.exceptions import ActionError

logger = logging.getLogger(__name__)

SUPPORTED_PDF = {".pdf"}
SUPPORTED_JPEG = {".jpg", ".jpeg", ".jpe"}
SUPPORTED_AUDIO = {".mp3", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".mp4", ".aac", ".wma", ".wav"}
SUPPORTED = SUPPORTED_PDF | SUPPORTED_JPEG | SUPPORTED_AUDIO

# Campos comunes de la UI → mapeo por formato
COMMON_FIELDS = (
    "creator",      # creador / artist
    "author",       # autor (PDF Author)
    "copyright",    # derechos
    "license",      # licencia (comment / subject segun formato)
    "title",
    "subject",
    "comment",
)


@dataclass
class MetaSnapshot:
    path: Path
    kind: str  # pdf | jpeg | audio | unsupported
    fields: dict[str, str] = field(default_factory=dict)
    raw: dict[str, str] = field(default_factory=dict)
    error: str | None = None


@dataclass
class MetaWriteResult:
    path: Path
    success: bool
    dry_run: bool
    message: str
    backup: Path | None = None
    before: dict[str, str] = field(default_factory=dict)
    after: dict[str, str] = field(default_factory=dict)


def detect_kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in SUPPORTED_PDF:
        return "pdf"
    if ext in SUPPORTED_JPEG:
        return "jpeg"
    if ext in SUPPORTED_AUDIO:
        # .mp4 puede ser video; se intenta como audio y falla limpio si no hay tags
        return "audio"
    return "unsupported"


def read_metadata(path: Path) -> MetaSnapshot:
    path = Path(path)
    if not path.is_file():
        return MetaSnapshot(path, "unsupported", error="No es un archivo")
    kind = detect_kind(path)
    if kind == "pdf":
        return _read_pdf(path)
    if kind == "jpeg":
        return _read_jpeg(path)
    if kind == "audio":
        return _read_audio(path)
    return MetaSnapshot(
        path,
        "unsupported",
        error="Formato no soportado (PDF, JPEG, MP3/FLAC/OGG/M4A…)",
    )


def _read_pdf(path: Path) -> MetaSnapshot:
    try:
        from pypdf import PdfReader
    except ImportError:
        return MetaSnapshot(path, "pdf", error="pypdf no disponible")
    try:
        reader = PdfReader(str(path))
        meta = reader.metadata
        raw: dict[str, str] = {}
        if meta:
            for k, v in meta.items():
                key = str(k).lstrip("/")
                raw[key] = "" if v is None else str(v)
        fields = {
            "title": raw.get("Title", ""),
            "author": raw.get("Author", ""),
            "creator": raw.get("Creator", ""),
            "subject": raw.get("Subject", ""),
            "copyright": raw.get("Copyright", "") or raw.get("Rights", ""),
            "license": raw.get("License", "") or raw.get("Keywords", ""),
            "comment": raw.get("Keywords", ""),
        }
        return MetaSnapshot(path, "pdf", fields=fields, raw=raw)
    except Exception as exc:
        return MetaSnapshot(path, "pdf", error=f"No se pudo leer PDF: {exc}")


def _read_jpeg(path: Path) -> MetaSnapshot:
    try:
        import piexif
    except ImportError:
        # Fallback: solo lectura con Pillow
        return _read_jpeg_pillow(path)
    try:
        exif_dict = piexif.load(str(path))
        raw: dict[str, str] = {}
        fields = {
            "title": "",
            "author": "",
            "creator": "",
            "subject": "",
            "copyright": "",
            "license": "",
            "comment": "",
        }

        def _dec(val: Any) -> str:
            if val is None:
                return ""
            if isinstance(val, bytes):
                for enc in ("utf-8", "latin-1"):
                    try:
                        return val.decode(enc).rstrip("\x00")
                    except Exception:
                        continue
                return val.decode("latin-1", errors="replace").rstrip("\x00")
            return str(val)

        # 0th IFD
        zeroth = exif_dict.get("0th") or {}
        if piexif.ImageIFD.ImageDescription in zeroth:
            fields["title"] = _dec(zeroth[piexif.ImageIFD.ImageDescription])
            raw["ImageDescription"] = fields["title"]
        if piexif.ImageIFD.Artist in zeroth:
            fields["creator"] = _dec(zeroth[piexif.ImageIFD.Artist])
            fields["author"] = fields["creator"]
            raw["Artist"] = fields["creator"]
        if piexif.ImageIFD.Copyright in zeroth:
            fields["copyright"] = _dec(zeroth[piexif.ImageIFD.Copyright])
            raw["Copyright"] = fields["copyright"]
        if piexif.ImageIFD.Software in zeroth:
            raw["Software"] = _dec(zeroth[piexif.ImageIFD.Software])

        # EXIF IFD UserComment
        exif_ifd = exif_dict.get("Exif") or {}
        if piexif.ExifIFD.UserComment in exif_ifd:
            uc = exif_ifd[piexif.ExifIFD.UserComment]
            # Often starts with encoding prefix
            if isinstance(uc, bytes) and len(uc) >= 8:
                text = _dec(uc[8:]) if uc[:8] in (
                    b"ASCII\x00\x00\x00",
                    b"UNICODE\x00",
                    b"JIS\x00\x00\x00\x00",
                ) else _dec(uc)
            else:
                text = _dec(uc)
            fields["comment"] = text
            fields["license"] = fields["license"] or text
            raw["UserComment"] = text

        return MetaSnapshot(path, "jpeg", fields=fields, raw=raw)
    except Exception as exc:
        logger.debug("piexif read failed %s: %s", path, exc)
        return _read_jpeg_pillow(path)


def _read_jpeg_pillow(path: Path) -> MetaSnapshot:
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
    except ImportError:
        return MetaSnapshot(path, "jpeg", error="Pillow/piexif no disponibles")
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            raw: dict[str, str] = {}
            fields = {k: "" for k in COMMON_FIELDS}
            if exif:
                for tag_id, value in exif.items():
                    name = TAGS.get(tag_id, str(tag_id))
                    if isinstance(value, bytes):
                        try:
                            value = value.decode("utf-8", errors="replace")
                        except Exception:
                            value = repr(value)[:80]
                    raw[str(name)] = str(value)[:500]
                    low = str(name).lower()
                    if low in ("artist",):
                        fields["creator"] = str(value)
                        fields["author"] = str(value)
                    elif low in ("copyright",):
                        fields["copyright"] = str(value)
                    elif low in ("imagedescription",):
                        fields["title"] = str(value)
                    elif low in ("usercomment",):
                        fields["comment"] = str(value)
            return MetaSnapshot(path, "jpeg", fields=fields, raw=raw)
    except Exception as exc:
        return MetaSnapshot(path, "jpeg", error=f"No se pudo leer JPEG: {exc}")



def _read_audio(path: Path) -> MetaSnapshot:
    try:
        from mutagen import File as MutagenFile
    except ImportError:
        return MetaSnapshot(
            path,
            "audio",
            error="mutagen no disponible (pip install mutagen)",
        )
    try:
        audio = MutagenFile(str(path), easy=True)
        if audio is None:
            audio = MutagenFile(str(path))
        if audio is None:
            return MetaSnapshot(
                path, "audio", error="No se reconocio el contenedor de audio"
            )

        def _first(key: str) -> str:
            try:
                val = audio.get(key)
            except Exception:
                val = None
            if val is None:
                return ""
            if isinstance(val, list):
                return str(val[0]) if val else ""
            return str(val)

        raw: dict[str, str] = {}
        try:
            for k, v in dict(audio).items():
                if isinstance(v, list):
                    raw[str(k)] = ", ".join(str(x) for x in v[:5])
                else:
                    raw[str(k)] = str(v)[:500]
        except Exception:
            pass

        artist = _first("artist") or _first("albumartist")
        fields = {
            "title": _first("title"),
            "author": artist,
            "creator": artist,
            "subject": _first("album"),
            "copyright": _first("copyright") or _first("encodedby") or "",
            "license": _first("license") or _first("website") or "",
            "comment": _first("comment") or _first("description") or "",
        }
        if not any(fields.values()) and getattr(audio, "tags", None):
            tags = audio.tags
            mapping = {
                "TIT2": "title",
                "TPE1": "creator",
                "TALB": "subject",
                "TCOP": "copyright",
                "COMM": "comment",
            }
            try:
                for k, field in mapping.items():
                    if k in tags:
                        val = tags[k]
                        text_v = (
                            str(val.text[0])
                            if hasattr(val, "text") and val.text
                            else str(val)
                        )
                        fields[field] = text_v
                        if field == "creator":
                            fields["author"] = text_v
            except Exception:
                pass
        return MetaSnapshot(path, "audio", fields=fields, raw=raw)
    except Exception as exc:
        return MetaSnapshot(path, "audio", error=f"No se pudo leer audio: {exc}")


def _write_audio(path: Path, updates: dict[str, str]) -> None:
    try:
        from mutagen import File as MutagenFile
    except ImportError as exc:
        raise ActionError("Para audio instala mutagen: pip install mutagen") from exc

    fd, tmp_name = tempfile.mkstemp(suffix=path.suffix, prefix=".filesage_meta_")
    tmp = Path(tmp_name)
    try:
        import os

        os.close(fd)
        shutil.copy2(path, tmp)

        audio = MutagenFile(str(tmp), easy=True)
        if audio is None:
            audio = MutagenFile(str(tmp))
        if audio is None:
            raise ActionError(f"mutagen no puede abrir {path.name}")

        if audio.tags is None:
            try:
                audio.add_tags()
            except Exception:
                pass

        def _set_easy(key: str, value: str) -> None:
            try:
                audio[key] = value
            except Exception:
                try:
                    audio[key] = [value]
                except Exception as exc:
                    logger.debug("No se pudo set %s: %s", key, exc)

        if "title" in updates:
            _set_easy("title", updates["title"])
        artist = updates.get("creator") or updates.get("author")
        if artist is not None and ("creator" in updates or "author" in updates):
            _set_easy("artist", artist)
        if "subject" in updates:
            _set_easy("album", updates["subject"])
        if "copyright" in updates:
            try:
                _set_easy("copyright", updates["copyright"])
            except Exception:
                pass
        if "license" in updates:
            for key in ("license", "website", "comment"):
                try:
                    _set_easy(key, updates["license"])
                    break
                except Exception:
                    continue
        if "comment" in updates:
            _set_easy("comment", updates["comment"])

        audio.save()
        check = MutagenFile(str(tmp))
        if check is None:
            raise ActionError("Verificacion mutagen fallo tras guardar")
        _atomic_replace(tmp, path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise



def apply_metadata(
    path: Path,
    updates: dict[str, str],
    *,
    dry_run: bool = True,
    backup: bool = True,
) -> MetaWriteResult:
    """Aplica updates (solo claves no vacias se escriben; None/'' puede limpiar si se indica)."""
    path = Path(path)
    snap = read_metadata(path)
    if snap.error:
        return MetaWriteResult(
            path, False, dry_run, snap.error, before=snap.fields
        )
    if snap.kind == "unsupported":
        return MetaWriteResult(
            path, False, dry_run, snap.error or "Formato no soportado", before=snap.fields
        )

    # Normalizar updates
    clean = {k: (v or "").strip() for k, v in updates.items() if k in COMMON_FIELDS}
    after = dict(snap.fields)
    after.update(clean)

    if dry_run:
        return MetaWriteResult(
            path,
            True,
            True,
            f"[dry-run] Se escribirían metadatos en {path.name}",
            before=snap.fields,
            after=after,
        )

    backup_path: Path | None = None
    try:
        if backup:
            backup_path = path.with_suffix(path.suffix + ".filesage_meta.bak")
            if not backup_path.exists():
                shutil.copy2(path, backup_path)

        if snap.kind == "pdf":
            _write_pdf(path, clean)
        elif snap.kind == "jpeg":
            _write_jpeg(path, clean)
        elif snap.kind == "audio":
            _write_audio(path, clean)
        else:
            return MetaWriteResult(
                path, False, False, "Formato no soportado", before=snap.fields
            )

        # Verificar lectura posterior
        verify = read_metadata(path)
        if verify.error:
            # Intentar restaurar backup
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, path)
            return MetaWriteResult(
                path,
                False,
                False,
                f"Verificación falló tras escribir; restaurado backup si existía: {verify.error}",
                backup=backup_path,
                before=snap.fields,
            )

        return MetaWriteResult(
            path,
            True,
            False,
            f"Metadatos actualizados: {path.name}",
            backup=backup_path,
            before=snap.fields,
            after=verify.fields,
        )
    except Exception as exc:
        if backup_path and backup_path.exists():
            try:
                shutil.copy2(backup_path, path)
            except Exception:
                pass
        logger.exception("Error escribiendo metadatos %s", path)
        return MetaWriteResult(
            path,
            False,
            False,
            f"Error: {exc}",
            backup=backup_path,
            before=snap.fields,
        )


def _atomic_replace(src_tmp: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # En Windows, replace funciona si dest existe
    src_tmp.replace(dest)


def _write_pdf(path: Path, updates: dict[str, str]) -> None:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(path))
    writer = PdfWriter()
    writer.append(reader)

    meta_map = {}
    if "title" in updates:
        meta_map["/Title"] = updates["title"]
    if "author" in updates:
        meta_map["/Author"] = updates["author"]
    if "creator" in updates:
        meta_map["/Creator"] = updates["creator"]
    if "subject" in updates:
        meta_map["/Subject"] = updates["subject"]
    # Copyright / license: Keywords + custom-ish Subject append
    if "copyright" in updates:
        meta_map["/Copyright"] = updates["copyright"]
    if "license" in updates:
        meta_map["/Keywords"] = updates["license"]
    if "comment" in updates and "license" not in updates:
        meta_map["/Keywords"] = updates["comment"]

    if meta_map:
        writer.add_metadata(meta_map)

    fd, tmp_name = tempfile.mkstemp(suffix=".pdf", prefix=".filesage_meta_")
    tmp = Path(tmp_name)
    try:
        import os

        os.close(fd)
        with open(tmp, "wb") as f:
            writer.write(f)
        # Verificar
        PdfReader(str(tmp))
        _atomic_replace(tmp, path)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise


def _write_jpeg(path: Path, updates: dict[str, str]) -> None:
    try:
        import piexif
    except ImportError as exc:
        raise ActionError(
            "Para escribir metadatos JPEG instala piexif: pip install piexif"
        ) from exc

    try:
        exif_dict = piexif.load(str(path))
    except Exception:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    zeroth = exif_dict.setdefault("0th", {})
    exif_ifd = exif_dict.setdefault("Exif", {})

    def _enc(s: str) -> bytes:
        return s.encode("utf-8")

    if "title" in updates:
        zeroth[piexif.ImageIFD.ImageDescription] = _enc(updates["title"])
    artist = updates.get("creator") or updates.get("author")
    if artist is not None and ("creator" in updates or "author" in updates):
        zeroth[piexif.ImageIFD.Artist] = _enc(artist)
    if "copyright" in updates:
        zeroth[piexif.ImageIFD.Copyright] = _enc(updates["copyright"])
    # UserComment for license/comment
    comment = updates.get("comment") or updates.get("license") or updates.get("subject")
    if comment is not None and any(
        k in updates for k in ("comment", "license", "subject")
    ):
        # ASCII prefix per EXIF
        payload = b"ASCII\x00\x00\x00" + _enc(comment)
        exif_ifd[piexif.ExifIFD.UserComment] = payload

    zeroth[piexif.ImageIFD.Software] = _enc("FileSage")

    exif_bytes = piexif.dump(exif_dict)
    fd, tmp_name = tempfile.mkstemp(suffix=".jpg", prefix=".filesage_meta_")
    tmp = Path(tmp_name)
    try:
        import os

        os.close(fd)
        # Insert EXIF without re-encoding pixels
        piexif.insert(exif_bytes, str(path), str(tmp))
        # Verificar
        piexif.load(str(tmp))
        _atomic_replace(tmp, path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise


def batch_apply(
    paths: list[Path],
    updates: dict[str, str],
    *,
    dry_run: bool = True,
    backup: bool = True,
    progress=None,
) -> list[MetaWriteResult]:
    results: list[MetaWriteResult] = []
    total = max(1, len(paths))
    for i, p in enumerate(paths):
        if progress:
            progress.report(f"Metadatos {i+1}/{len(paths)}: {Path(p).name}", i / total)
            progress.check()
        results.append(
            apply_metadata(Path(p), updates, dry_run=dry_run, backup=backup)
        )
    if progress:
        ok = sum(1 for r in results if r.success)
        progress.report(f"Listo: {ok}/{len(results)}", 1.0)
    return results
