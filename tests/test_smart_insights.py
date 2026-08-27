"""Tests de smart insights."""

from pathlib import Path

from filesage.core.config import Settings
from filesage.core.engine import Engine


def test_insights_empty_and_installer(tmp_path: Path):
    (tmp_path / "empty.txt").write_bytes(b"")
    (tmp_path / "setup.exe").write_bytes(b"y" * (6 * 1024 * 1024))
    (tmp_path / "normal.txt").write_text("hola")
    settings = Settings()
    engine = Engine(settings)
    scan = engine.scan(tmp_path)
    insights = engine.smart_insights(scan)
    cats = {i.category for i in insights}
    assert "empty" in cats
    assert "installers" in cats
