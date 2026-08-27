"""Tests de configuracion persistente (Etapa 6)."""

from __future__ import annotations

from pathlib import Path

from filesage.core.config import Settings, load_settings, save_settings


def test_save_and_load_roundtrip(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    settings = Settings()
    settings.app.dry_run_default = False
    settings.duplicates.min_size_bytes = 9999
    settings.scan.ignore_hidden = False
    settings.scan.exclude_patterns = ["**/tmp/**", "**/cache/**"]

    saved = save_settings(settings, cfg_path)
    assert saved.exists()

    loaded = load_settings(cfg_path)
    assert loaded.app.dry_run_default is False
    assert loaded.duplicates.min_size_bytes == 9999
    assert loaded.scan.ignore_hidden is False
    assert "**/tmp/**" in loaded.scan.exclude_patterns


def test_to_dict_keys():
    s = Settings()
    d = s.to_dict()
    assert "app" in d
    assert "duplicates" in d
    assert "scan" in d
