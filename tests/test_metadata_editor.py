
from pathlib import Path

import pytest

from filesage.services.metadata_editor import apply_metadata, read_metadata


def test_pdf_metadata_roundtrip(tmp_path: Path):
    pypdf = pytest.importorskip("pypdf")
    from pypdf import PdfWriter

    pdf = tmp_path / "doc.pdf"
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    w.add_metadata({"/Title": "Old", "/Author": "A"})
    with open(pdf, "wb") as f:
        w.write(f)

    snap = read_metadata(pdf)
    assert snap.kind == "pdf"
    assert not snap.error

    dry = apply_metadata(
        pdf,
        {"title": "Nuevo titulo", "author": "FileSage", "creator": "FS", "copyright": "CC"},
        dry_run=True,
        backup=False,
    )
    assert dry.success and dry.dry_run

    real = apply_metadata(
        pdf,
        {"title": "Nuevo titulo", "author": "FileSage", "creator": "FS", "copyright": "CC-BY"},
        dry_run=False,
        backup=True,
    )
    assert real.success, real.message
    assert (pdf.with_suffix(pdf.suffix + ".filesage_meta.bak")).exists()
    after = read_metadata(pdf)
    assert "Nuevo" in (after.fields.get("title") or "")


def test_jpeg_metadata_if_piexif(tmp_path: Path):
    piexif = pytest.importorskip("piexif")
    from PIL import Image

    img = tmp_path / "pic.jpg"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(img, "JPEG")

    r = apply_metadata(
        img,
        {"creator": "Autor", "copyright": "All rights", "title": "Foto"},
        dry_run=False,
        backup=True,
    )
    assert r.success, r.message
    snap = read_metadata(img)
    assert snap.kind == "jpeg"
    assert "Autor" in (snap.fields.get("creator") or snap.fields.get("author") or "")


def test_unsupported(tmp_path: Path):
    p = tmp_path / "x.txt"
    p.write_text("hi")
    snap = read_metadata(p)
    assert snap.kind == "unsupported"


def test_audio_detect_kind():
    from filesage.services.metadata_editor import detect_kind
    assert detect_kind(Path("a.mp3")) == "audio"
    assert detect_kind(Path("a.flac")) == "audio"
    assert detect_kind(Path("a.m4a")) == "audio"
    assert detect_kind(Path("a.ogg")) == "audio"
    assert detect_kind(Path("a.pdf")) == "pdf"


def test_audio_read_missing_mutagen_or_invalid(tmp_path: Path):
    from filesage.services.metadata_editor import read_metadata
    p = tmp_path / "bad.mp3"
    p.write_bytes(b"not an mp3")
    snap = read_metadata(p)
    assert snap.kind == "audio"
    # error or empty fields is acceptable
    assert snap.error or snap.fields is not None
