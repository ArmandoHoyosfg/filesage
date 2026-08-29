import time
from pathlib import Path

from filesage.core.config import Settings
from filesage.core.engine import Engine
from filesage.domain.models import ActionType


def test_cleanup_old_and_empty(tmp_path: Path):
    old = tmp_path / "old.txt"
    old.write_text("x" * 100)
    # force old mtime
    old_time = time.time() - 400 * 86400
    import os
    os.utime(old, (old_time, old_time))
    empty = tmp_path / "empty_dir"
    empty.mkdir()

    settings = Settings()
    settings.scan.min_file_size_bytes = 0
    engine = Engine(settings)
    plan = engine.build_cleanup_plan(
        tmp_path, old_days=365, include_empty_folders=True, include_old_files=True
    )
    kinds = {i.kind for i in plan.items}
    assert "old_file" in kinds
    assert "empty_folder" in kinds

    for i in plan.items:
        i.selected = True
    actions = engine.cleanup_plan_to_actions(plan, permanent=False)
    assert all(a.action_type == ActionType.TRASH for a in actions)
    tx = engine.execute_actions(actions, dry_run=True)
    assert tx.dry_run
    assert old.exists()

    actions_del = engine.cleanup_plan_to_actions(plan, permanent=True)
    assert all(a.action_type == ActionType.DELETE for a in actions_del)
