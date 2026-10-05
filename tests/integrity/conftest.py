"""Fixtures compartidas de la suite de integridad."""

from __future__ import annotations

from pathlib import Path

import pytest

from filesage.core.config import Settings
from filesage.core.engine import Engine


@pytest.fixture
def engine_tmp(tmp_path: Path) -> Engine:
    """Engine aislado con DBs/cache bajo tmp_path."""
    s = Settings()
    s.scan.min_file_size_bytes = 0
    s.duplicates.min_size_bytes = 1
    s.hashing.use_cache = True
    s.storage.index_db = str(tmp_path / "index.db")
    s.storage.transaction_db = str(tmp_path / "tx.db")
    s.logging.file = str(tmp_path / "test.log")
    return Engine(s)


@pytest.fixture
def sample_tree(tmp_path: Path) -> Path:
    """Arbol tipico: duplicados, imagen, vacia, grande."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.txt").write_text("dup-content-integrity")
    (tmp_path / "docs" / "b.txt").write_text("dup-content-integrity")
    (tmp_path / "docs" / "unique.txt").write_text("only-once")
    (tmp_path / "empty_dir").mkdir()
    (tmp_path / "media").mkdir()
    # PNG minimo 1x1
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    (tmp_path / "media" / "pixel.png").write_bytes(png)
    (tmp_path / "big.bin").write_bytes(b"Z" * 12_000)
    return tmp_path
