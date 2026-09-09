"""Tests del DuplicateFinder — contenido real, no solo tamano."""

from __future__ import annotations

from pathlib import Path

import pytest

from filesage.core.config import Settings
from filesage.core.engine import Engine
from filesage.services.duplicate_finder import DuplicateFinder
from filesage.infrastructure.hasher import Hasher


@pytest.fixture
def dup_tree(tmp_path: Path) -> Path:
    content_a = b"contenido identico A" * 50
    content_b = b"contenido diferente B" * 50
    (tmp_path / "f1.txt").write_bytes(content_a)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "f1_copy.txt").write_bytes(content_a)
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
    found = False
    for g in groups:
        names = {f.path.name for f in g.files}
        if "f1.txt" in names and "f1_copy.txt" in names:
            found = True
            assert g.count == 2
            break
    assert found


def test_same_size_different_content_not_duplicate(tmp_path: Path):
    """Caso del bug: dos MP3 distintos con el mismo tamano NO son duplicados."""
    # Mismo tamano exacto, contenido distinto
    a = b"SONG-A-PAYLOAD-" + bytes(range(256)) * 40
    b = b"SONG-B-PAYLOAD-" + bytes(range(255, -1, -1)) * 40
    assert len(a) == len(b)
    (tmp_path / "Fuego En La Tormenta.mp3").write_bytes(a)
    (tmp_path / "Caballeros de Acero.mp3").write_bytes(b)

    settings = Settings()
    settings.duplicates.min_size_bytes = 10
    engine = Engine(settings)
    _, groups = engine.find_duplicates(tmp_path)
    assert groups == [], f"Falsos positivos: {groups}"


def test_same_size_same_content_is_duplicate(tmp_path: Path):
    payload = b"SAME-AUDIO-BYTES" * 100
    (tmp_path / "track_a.mp3").write_bytes(payload)
    (tmp_path / "track_b.mp3").write_bytes(payload)
    settings = Settings()
    settings.duplicates.min_size_bytes = 10
    _, groups = Engine(settings).find_duplicates(tmp_path)
    assert len(groups) == 1
    assert groups[0].count == 2


def test_partial_differs_when_only_tail_differs(tmp_path: Path):
    """Cabecera igual, cola distinta → no duplicado."""
    head = b"HEADER" * 2000
    a = head + b"TAIL-AAAA" * 500
    b = head + b"TAIL-BBBB" * 500
    assert len(a) == len(b)
    (tmp_path / "a.bin").write_bytes(a)
    (tmp_path / "b.bin").write_bytes(b)
    settings = Settings()
    settings.duplicates.min_size_bytes = 10
    _, groups = Engine(settings).find_duplicates(tmp_path)
    assert groups == []


def test_no_duplicates(tmp_path: Path):
    (tmp_path / "a.txt").write_text("uno")
    (tmp_path / "b.txt").write_text("dos")
    _, groups = Engine(Settings()).find_duplicates(tmp_path)
    assert groups == []


def test_hasher_partial_includes_regions(tmp_path: Path):
    h = Hasher(Settings())
    p = tmp_path / "big.bin"
    data = bytearray(200_000)
    data[0:10] = b"STARTSTART"
    data[-10:] = b"ENDENDEND1"
    p.write_bytes(data)
    ph1 = h.partial_hash(p)
    data[-10:] = b"ENDENDEND2"
    p.write_bytes(data)
    ph2 = h.partial_hash(p)
    assert ph1 != ph2
