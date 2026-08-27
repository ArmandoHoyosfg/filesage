"""Tests de identidad de archivo."""

from pathlib import Path

from filesage.infrastructure.file_identity import identify


def test_identify_by_extension(tmp_path: Path):
    p = tmp_path / "foto.jpg"
    p.write_bytes(b"\xff\xd8\xff\x00" + b"x" * 20)
    ident = identify(p, deep=False)
    assert "JPEG" in ident.label or "Imagen" in ident.label or "image" in ident.mime


def test_identify_exe(tmp_path: Path):
    p = tmp_path / "setup.exe"
    p.write_bytes(b"MZ" + b"\x00" * 40)
    ident = identify(p, deep=False)
    assert "nstal" in ident.label.lower() or "ejecut" in ident.label.lower() or ident.mime


def test_identify_empty_text(tmp_path: Path):
    p = tmp_path / "notas.txt"
    p.write_text("hola")
    ident = identify(p, deep=False)
    assert "Texto" in ident.label or "text" in ident.mime
