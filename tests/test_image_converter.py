from pathlib import Path

import pytest

from filesage.services.image_converter import convert_path, convert_one, default_output_dir


def test_convert_png_to_jpg(tmp_path: Path):
    pytest.importorskip("PIL")
    from PIL import Image

    src = tmp_path / "a.png"
    Image.new("RGB", (16, 16), color=(10, 20, 30)).save(src)
    results = convert_path(src, target_ext="jpg", output_dir=tmp_path / "out")
    assert len(results) == 1
    assert results[0].ok and not results[0].skipped
    assert results[0].destination is not None
    assert results[0].destination.exists()


def test_skip_same_format(tmp_path: Path):
    pytest.importorskip("PIL")
    from PIL import Image

    src = tmp_path / "a.png"
    Image.new("RGB", (8, 8), color=(1, 2, 3)).save(src)
    r = convert_one(src, tmp_path / "out", target_ext="png")
    assert r.skipped and r.ok
    assert r.destination is None


def test_skip_jpeg_jpg_equiv(tmp_path: Path):
    pytest.importorskip("PIL")
    from PIL import Image

    src = tmp_path / "a.jpeg"
    Image.new("RGB", (8, 8), color=(1, 2, 3)).save(src, "JPEG")
    r = convert_one(src, tmp_path / "out", target_ext="jpg")
    assert r.skipped


def test_skip_inside_converted(tmp_path: Path):
    pytest.importorskip("PIL")
    from PIL import Image

    conv = tmp_path / "FileSage_converted"
    conv.mkdir()
    src = conv / "x.webp"
    Image.new("RGB", (8, 8), color=(1, 2, 3)).save(src)
    results = convert_path(tmp_path, target_ext="png", recursive=True)
    # should not convert the one inside converted (filtered) or skip it
    assert all(
        (not r.ok) or r.skipped or "FileSage_converted" not in str(r.source)
        for r in results
        if r.destination
    )


def test_convert_folder(tmp_path: Path):
    pytest.importorskip("PIL")
    from PIL import Image

    Image.new("RGB", (8, 8), color=(1, 2, 3)).save(tmp_path / "x.webp")
    res = convert_path(tmp_path, target_ext="png")
    assert any(r.ok and not r.skipped for r in res)
