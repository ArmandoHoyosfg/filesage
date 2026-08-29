from pathlib import Path

from filesage.core.config import Settings
from filesage.core.engine import Engine
from datetime import datetime, timezone
from filesage.domain.models import ActionRecord, ActionType
from filesage.infrastructure.storage import new_action_id
from filesage.services.empty_folders import find_empty_folders
from filesage.services.archiver import zip_folder


def test_copy_action(tmp_path: Path):
    src = tmp_path / "a.txt"
    src.write_text("hello")
    dest = tmp_path / "copy" / "a.txt"
    engine = Engine(Settings())
    actions = [
        ActionRecord(
            action_id=new_action_id(),
            action_type=ActionType.COPY,
            source=src,
            destination=dest,
            timestamp=datetime.now(timezone.utc),
            success=False,
            message="",
            dry_run=False,
        )
    ]
    tx = engine.execute_actions(actions, dry_run=False)
    assert dest.exists()
    assert dest.read_text() == "hello"
    assert all(a.success for a in tx.actions)


def test_empty_folders(tmp_path: Path):
    (tmp_path / "keep").mkdir()
    (tmp_path / "keep" / "f.txt").write_text("x")
    (tmp_path / "empty1").mkdir()
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "empty2").mkdir()
    found = find_empty_folders(tmp_path)
    names = {p.name for p in found}
    assert "empty1" in names
    assert "empty2" in names
    assert "keep" not in names


def test_zip_folder(tmp_path: Path):
    d = tmp_path / "pack"
    d.mkdir()
    (d / "a.txt").write_text("data")
    out = zip_folder(d)
    assert out.exists() and out.suffix == ".zip"
