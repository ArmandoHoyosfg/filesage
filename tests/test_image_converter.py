from pathlib import Path

import pytest

from filesage.services.image_converter import (
    convert_path,
    convert_one,
    detect_image_format,
    looks_like_converted_name,
)


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


def test_skip_jpeg_jpg_equiv(tmp_path: Path):
    pytest.importorskip("PIL")
    from PIL import Image

    src = tmp_path / "a.jpeg"
    Image.new("RGB", (8, 8), color=(1, 2, 3)).save(src, "JPEG")
    r = convert_one(src, tmp_path / "out", target_ext="jpg")
    assert r.skipped


def test_skip_when_dest_exists_no_duplicate(tmp_path: Path):
    pytest.importorskip("PIL")
    from PIL import Image

    src = tmp_path / "photo.webp"
    Image.new("RGB", (8, 8), color=(9, 8, 7)).save(src, "WEBP")
    out = tmp_path / "out"
    r1 = convert_one(src, out, target_ext="png")
    assert r1.ok and not r1.skipped
    assert r1.destination and r1.destination.exists()
    # segunda pasada: no debe crear photo_converted.png
    r2 = convert_one(src, out, target_ext="png")
    assert r2.skipped
    assert list(out.glob("*")) == [r1.destination]


def test_skip_converted_name(tmp_path: Path):
    assert looks_like_converted_name(Path("foo_converted.png"))
    assert looks_like_converted_name(Path("foo_converted2.jpg"))
    assert not looks_like_converted_name(Path("foo.png"))


def test_detect_format(tmp_path: Path):
    pytest.importorskip("PIL")
    from PIL import Image

    src = tmp_path / "x.bin"
    Image.new("RGB", (4, 4), color=(1, 1, 1)).save(src, "PNG")
    assert detect_image_format(src) == "png"


def test_skip_inside_converted(tmp_path: Path):
    pytest.importorskip("PIL")
    from PIL import Image

    conv = tmp_path / "FileSage_converted"
    conv.mkdir()
    src = conv / "x.webp"
    Image.new("RGB", (8, 8), color=(1, 2, 3)).save(src)
    results = convert_path(tmp_path, target_ext="png", recursive=True)
    assert not any(r.destination and r.ok and not r.skipped for r in results)


def test_convert_folder(tmp_path: Path):
    pytest.importorskip("PIL")
    from PIL import Image

    Image.new("RGB", (8, 8), color=(1, 2, 3)).save(tmp_path / "x.webp")
    res = convert_path(tmp_path, target_ext="png")
    assert any(r.ok and not r.skipped for r in res)
