"""Tests de exportacion (Etapa 4)."""

from __future__ import annotations

import json
from pathlib import Path

from filesage.core.config import Settings
from filesage.core.engine import Engine


def test_export_space_json(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hola")
    (tmp_path / "b.bin").write_bytes(b"\x00" * 100)
    settings = Settings()
    engine = Engine(settings)
    scan, report = engine.analyze_space(tmp_path, top_n=5)
    out = tmp_path / "report.json"
    engine.export_space(report, scan, out, fmt="json")
    data = json.loads(out.read_text())
    assert data["total_files"] >= 2
    assert "top_files" in data


def test_export_duplicates_csv(tmp_path: Path):
    content = b"dup" * 100
    (tmp_path / "x.dat").write_bytes(content)
    (tmp_path / "y.dat").write_bytes(content)
    settings = Settings()
    settings.duplicates.min_size_bytes = 10
    engine = Engine(settings)
    _, groups = engine.find_duplicates(tmp_path)
    out = tmp_path / "dups.csv"
    engine.export_duplicates(groups, tmp_path, out, fmt="csv")
    assert out.exists()
    assert "hash" in out.read_text() or "group" in out.read_text()
