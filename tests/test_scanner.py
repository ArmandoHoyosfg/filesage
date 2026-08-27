"""Tests del Scanner y SpaceAnalyzer (Etapa 1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from filesage.core.config import Settings
from filesage.core.engine import Engine
from filesage.domain.exceptions import ScanError
from filesage.services.scanner import Scanner


@pytest.fixture
def tmp_tree(tmp_path: Path) -> Path:
    """Crea un arbol de prueba pequeno."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.txt").write_text("hola mundo")
    (tmp_path / "docs" / "b.txt").write_text("otro contenido mas largo aqui")
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "foto.jpg").write_bytes(b"\xff\xd8\xff" + b"\x00" * 500)
    (tmp_path / "empty").mkdir()
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "secret.txt").write_text("no deberia aparecer")
    return tmp_path


def test_scanner_basic(tmp_tree: Path):
    settings = Settings()
    scanner = Scanner(settings)
    result = scanner.scan(tmp_tree)

    assert result.total_files >= 3  # a.txt, b.txt, foto.jpg (hidden ignorado)
    assert result.total_size > 0
    assert result.root == tmp_tree.resolve()
    assert len(result.errors) == 0

    names = {f.path.name for f in result.files}
    assert "a.txt" in names
    assert "b.txt" in names
    assert "foto.jpg" in names
    assert "secret.txt" not in names  # ignore_hidden=True por defecto


def test_space_analyzer(tmp_tree: Path):
    settings = Settings()
    engine = Engine(settings)
    scan_result, report = engine.analyze_space(tmp_tree, top_n=5)

    assert report.total_files == scan_result.total_files
    assert report.total_size == scan_result.total_size
    assert len(report.top_files) <= 5
    assert len(report.by_extension) >= 1
    assert report.tree.path == tmp_tree.resolve()
    assert report.tree.size == report.total_size


def test_scanner_nonexistent():
    settings = Settings()
    scanner = Scanner(settings)
    with pytest.raises(ScanError):
        scanner.scan(Path("/ruta/que/no/existe/seguro"))
