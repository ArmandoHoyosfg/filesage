
from pathlib import Path

from filesage.services.search_smart import (
    SearchFilters,
    SearchPreset,
    load_presets,
    save_preset,
    delete_preset,
    suggest_from_rows,
)


def test_filters_images_and_size(tmp_path: Path):
    f = SearchFilters(min_size=100, images_only=True, exclude_app_folders=True)
    assert f.allows(tmp_path / "a.jpg", 200)
    assert not f.allows(tmp_path / "a.txt", 200)
    assert not f.allows(tmp_path / "a.jpg", 50)
    app = tmp_path / "FileSage_converted" / "x.jpg"
    assert not f.allows(app, 500)


def test_suggestions_images():
    rows = [
        {"path": f"/t/img{i}.jpg", "size": 1000}
        for i in range(5)
    ]
    tips = suggest_from_rows(rows)
    keys = {t.key for t in tips}
    assert "convert" in keys
    assert "duplicates" in keys


def test_presets_roundtrip(tmp_path: Path, monkeypatch):
    import filesage.services.search_smart as sm
    monkeypatch.setattr(sm, "PRESETS_PATH", tmp_path / "presets.json")
    save_preset(SearchPreset(name="facturas", query=".pdf", ext_filter=".pdf"))
    loaded = load_presets()
    assert any(p.name == "facturas" and p.query == ".pdf" for p in loaded)
    delete_preset("facturas")
    assert load_presets() == []
