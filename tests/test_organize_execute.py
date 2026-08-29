from pathlib import Path

from filesage.core.config import Settings
from filesage.core.engine import Engine


def test_organize_plan_and_dry_run(tmp_path: Path):
    for i in range(3):
        (tmp_path / f"pic{i}.jpg").write_bytes(b"\xff\xd8\xff" + bytes([i]) * 100)
    for i in range(3):
        (tmp_path / f"song{i}.mp3").write_bytes(b"ID3" + bytes([i + 5]) * 120)

    settings = Settings()
    settings.scan.min_file_size_bytes = 0
    engine = Engine(settings)
    plan = engine.build_organize_plan(tmp_path, min_files_per_group=3)
    assert len(plan.items) >= 3
    assert all(i.category == "organize" for i in plan.items)

    for i in plan.items:
        i.selected = True
    actions = engine.organize_plan_to_actions(plan)
    assert len(actions) == len(plan.items)
    assert all(a.action_type.value == "move" for a in actions)

    tx = engine.execute_actions(actions, dry_run=True)
    assert tx.dry_run
    assert all(a.success for a in tx.actions)
    assert (tmp_path / "pic0.jpg").exists()


def test_organize_real_move(tmp_path: Path):
    for i in range(3):
        (tmp_path / f"img{i}.jpg").write_bytes(b"\xff\xd8\xff" + bytes([i]) * 80)

    settings = Settings()
    settings.scan.min_file_size_bytes = 0
    engine = Engine(settings)
    plan = engine.build_organize_plan(tmp_path, min_files_per_group=3)
    assert plan.items
    for i in plan.items:
        i.selected = True
    actions = engine.organize_plan_to_actions(plan)
    tx = engine.execute_actions(actions, dry_run=False)
    assert any(a.success for a in tx.actions)
    dest_root = tmp_path / "FileSage_Organizado"
    assert dest_root.exists()
    assert any(dest_root.rglob("*.jpg"))
