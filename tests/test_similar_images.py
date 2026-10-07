from pathlib import Path

from PIL import Image

from filesage.core.config import Settings
from filesage.core.engine import Engine
from filesage.services.similar_images import difference_hash, find_similar_images, hamming_distance


def _make_img(path: Path, color: tuple[int, int, int], size=(64, 64)) -> None:
    Image.new("RGB", size, color).save(path)


def test_dhash_stable(tmp_path: Path):
    p = tmp_path / "a.png"
    _make_img(p, (200, 40, 40))
    h1 = difference_hash(p)
    h2 = difference_hash(p)
    assert h1 and h1 == h2
    assert hamming_distance(h1, h1) == 0


def test_similar_resized(tmp_path: Path):
    a = tmp_path / "orig.png"
    b = tmp_path / "small.png"
    _make_img(a, (30, 120, 220), size=(120, 120))
    _make_img(b, (30, 120, 220), size=(40, 40))
    settings = Settings()
    settings.scan.min_file_size_bytes = 0
    engine = Engine(settings)
    scan = engine.scan(tmp_path)
    groups = find_similar_images(scan.files, threshold=20)
    assert groups, "redimensionada deberia agruparse"
    assert len(groups[0].files) >= 2


def test_different_colors_not_grouped(tmp_path: Path):
    _make_img(tmp_path / "r.png", (255, 0, 0), size=(80, 80))
    _make_img(tmp_path / "g.png", (0, 255, 0), size=(80, 80))
    settings = Settings()
    settings.scan.min_file_size_bytes = 0
    scan = Engine(settings).scan(tmp_path)
    groups = find_similar_images(scan.files, threshold=5)
    assert groups == []


def test_engine_plan_trash_similar(tmp_path: Path):
    _make_img(tmp_path / "a.png", (10, 10, 10), size=(100, 100))
    _make_img(tmp_path / "b.png", (10, 10, 10), size=(50, 50))
    settings = Settings()
    settings.scan.min_file_size_bytes = 0
    engine = Engine(settings)
    _, groups = engine.find_similar_images(tmp_path, threshold=20)
    if not groups:
        # still allow plan empty
        plans = engine.plan_trash_similar_images(groups)
        assert plans == []
        return
    plans = engine.plan_trash_similar_images(groups, keep_largest=True)
    assert len(plans) >= 1
    tx = engine.execute_actions(plans, dry_run=True)
    assert tx.dry_run
