from pathlib import Path

from filesage.core.config import Settings
from filesage.core.engine import Engine
from filesage.domain.models import DuplicateGroup, FileInfo


def _fi(path: Path, size: int, mtime: float) -> FileInfo:
    return FileInfo(path=path, size=size, mtime=mtime, is_symlink=False)


def test_keep_shortest_name(tmp_path: Path):
    a = tmp_path / "short.txt"
    b = tmp_path / "much_longer_name.txt"
    a.write_text("same")
    b.write_text("same")
    group = DuplicateGroup(
        hash_full="h",
        files=(_fi(b, 4, 100.0), _fi(a, 4, 200.0)),
        total_size=8,
        wasted_size=4,
    )
    engine = Engine(Settings())
    plans = engine.plan_trash_duplicates([group], strategy="shortest_name")
    assert len(plans) == 1
    assert plans[0].source == b
    assert plans[0].metadata.get("kept") == str(a)


def test_keep_prefer_path(tmp_path: Path):
    good = tmp_path / "Originales" / "x.txt"
    bad = tmp_path / "copia" / "x.txt"
    good.parent.mkdir(parents=True)
    bad.parent.mkdir(parents=True)
    good.write_text("same")
    bad.write_text("same")
    group = DuplicateGroup(
        hash_full="h",
        files=(_fi(bad, 4, 300.0), _fi(good, 4, 100.0)),
        total_size=8,
        wasted_size=4,
    )
    engine = Engine(Settings())
    plans = engine.plan_trash_duplicates(
        [group], strategy="prefer_path", prefer_path_substr="Originales"
    )
    assert len(plans) == 1
    assert plans[0].source == bad
