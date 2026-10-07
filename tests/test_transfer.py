from pathlib import Path

from filesage.core.config import Settings
from filesage.core.engine import Engine
from filesage.domain.models import ActionType
from filesage.services.transfer import (
    expand_sources,
    plan_transfer,
    resolve_dest_path,
)


def test_resolve_rename(tmp_path: Path):
    dest = tmp_path / "out"
    dest.mkdir()
    src = tmp_path / "a.txt"
    src.write_text("x")
    (dest / "a.txt").write_text("old")
    target = resolve_dest_path(src, dest, on_conflict="rename")
    assert target is not None
    assert target.name == "a_1.txt"


def test_expand_dir_contents(tmp_path: Path):
    src = tmp_path / "drive"
    src.mkdir()
    (src / "song.mp3").write_bytes(b"m")
    (src / "album").mkdir()
    (src / "album" / "x.mp3").write_bytes(b"m")
    expanded = expand_sources([src], expand_dir_contents=True)
    names = {p.name for p in expanded}
    assert "song.mp3" in names
    assert "album" in names
    assert "x.mp3" not in names  # solo contenido inmediato


def test_copy_contents_skip_existing(tmp_path: Path):
    src = tmp_path / "F"
    dst = tmp_path / "MUSICA"
    src.mkdir()
    dst.mkdir()
    (src / "nueva.mp3").write_text("new")
    (src / "vieja.mp3").write_text("old-src")
    (dst / "vieja.mp3").write_text("already")
    plans = plan_transfer(
        [src],
        dst,
        mode="copy",
        on_conflict="skip",
        expand_dir_contents=True,
    )
    names = {Path(p.source).name for p in plans}
    assert "nueva.mp3" in names
    assert "vieja.mp3" not in names


def test_copy_dry_and_real(tmp_path: Path):
    src_dir = tmp_path / "src"
    dst = tmp_path / "dst"
    src_dir.mkdir()
    dst.mkdir()
    f = src_dir / "doc.txt"
    f.write_text("hola")
    settings = Settings()
    settings.storage.transaction_db = str(tmp_path / "tx.db")
    engine = Engine(settings)
    plans = engine.plan_transfer([f], dst, mode="copy", expand_dir_contents=False)
    assert len(plans) == 1
    assert plans[0].action_type == ActionType.COPY
    tx = engine.execute_actions(plans, dry_run=True)
    assert tx.dry_run
    assert f.exists()
    assert not (dst / "doc.txt").exists()
    tx2 = engine.execute_actions(plans, dry_run=False)
    assert all(a.success for a in tx2.actions)
    assert f.exists()
    assert (dst / "doc.txt").read_text() == "hola"


def test_move_real(tmp_path: Path):
    src_dir = tmp_path / "src"
    dst = tmp_path / "dst"
    src_dir.mkdir()
    dst.mkdir()
    f = src_dir / "m.txt"
    f.write_text("move-me")
    settings = Settings()
    settings.storage.transaction_db = str(tmp_path / "tx2.db")
    engine = Engine(settings)
    plans = engine.plan_transfer([f], dst, mode="move", expand_dir_contents=False)
    tx = engine.execute_actions(plans, dry_run=False)
    assert all(a.success for a in tx.actions)
    assert not f.exists()
    assert (dst / "m.txt").read_text() == "move-me"


def test_skip_conflict(tmp_path: Path):
    dest = tmp_path / "out"
    dest.mkdir()
    src = tmp_path / "b.txt"
    src.write_text("new")
    (dest / "b.txt").write_text("old")
    plans = plan_transfer([src], dest, mode="copy", on_conflict="skip")
    assert plans == []
