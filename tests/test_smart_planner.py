"""Tests del SmartPlanner."""

from pathlib import Path

from filesage.core.config import Settings
from filesage.core.engine import Engine
from filesage.services.smart_planner import Confidence, SmartPlanner


def test_smart_plan_preselects_duplicates_only(tmp_path: Path):
    content = b"dup-data-" * 200
    (tmp_path / "a.bin").write_bytes(content)
    (tmp_path / "b.bin").write_bytes(content)
    (tmp_path / "empty.txt").write_bytes(b"")
    (tmp_path / "setup.exe").write_bytes(b"z" * (6 * 1024 * 1024))

    settings = Settings()
    settings.duplicates.min_size_bytes = 10
    engine = Engine(settings)
    plan = engine.build_smart_plan(tmp_path)

    high = [i for i in plan.items if i.confidence == Confidence.HIGH]
    assert len(high) >= 1
    assert all(i.selected for i in high)
    # medium not preselected
    medium = [i for i in plan.items if i.confidence == Confidence.MEDIUM]
    assert all(not i.selected for i in medium)
