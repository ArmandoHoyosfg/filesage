"""Tests del DuplicateFinder (Etapa 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from filesage.core.config import Settings
from filesage.core.engine import Engine
from filesage.domain.models import FileInfo
from filesage.services.duplicate_finder import DuplicateFinder


@pytest.fixture
def dup_tree(tmp_path: Path) -> Path:
    """Arbol con duplicados controlados."""
    content_a = b"contenido identico A" * 50
    content_b = b"contenido diferente B" * 50

    (tmp_path / "f1.txt").write_bytes(content_a)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "f1_copy.txt").write_bytes(content_a)  # duplicado
    (tmp_path / "f2.txt").write_bytes(content_b)
    (tmp_path / "unique.bin").write_bytes(b"unico" * 20)
    return tmp_path


def test_find_duplicates(dup_tree: Path):
    settings = Settings()
    settings.duplicates.min_size_bytes = 10
    engine = Engine(settings)
    scan_result, groups = engine.find_duplicates(dup_tree)

    assert scan_result.total_files >= 4
    assert len(groups) >= 1

    # Debe haber un grupo con los dos archivos de content_a
    found = False
    for g in groups:
        names = {f.path.name for f in g.files}
        if "f1.txt" in names and "f1_copy.txt" in names:
            found = True
            assert g.count == 2
            assert g.wasted_size > 0
            break
    assert found, "No se detecto el grupo de duplicados esperado"


def test_no_duplicates(tmp_path: Path):
    (tmp_path / "a.txt").write_text("uno")
    (tmp_path / "b.txt").write_text("dos")
    settings = Settings()
    engine = Engine(settings)
    _, groups = engine.find_duplicates(tmp_path)
    assert groups == []
