"""Tests del contrato de progreso y cancelacion (Etapas A/B)."""

from pathlib import Path

import pytest

from filesage.application.progress import CancellationToken, ProgressReporter
from filesage.core.config import Settings
from filesage.core.engine import Engine
from filesage.domain.exceptions import CancelledError


def test_progress_reporter_callback():
    msgs = []

    def cb(msg, frac):
        msgs.append((msg, frac))

    r = ProgressReporter(callback=cb)
    r.report("hola", 0.5)
    assert msgs == [("hola", 0.5)]


def test_cancellation_token_raises():
    token = CancellationToken()
    r = ProgressReporter(callback=None, cancel=token)
    token.cancel()
    with pytest.raises(CancelledError):
        r.report("x", None)


def test_scan_with_progress(tmp_path: Path):
    for i in range(5):
        (tmp_path / f"f{i}.txt").write_text(f"data{i}")
    settings = Settings()
    settings.scan.min_file_size_bytes = 0
    engine = Engine(settings)
    seen = []

    def cb(msg, frac):
        seen.append(msg)

    reporter = ProgressReporter(callback=cb)
    result = engine.scan(tmp_path, progress=reporter)
    assert result.total_files >= 5
    assert any("Escaneo" in m or "Escaneados" in m or "listo" in m for m in seen)


def test_find_duplicates_progress(tmp_path: Path):
    (tmp_path / "a.txt").write_text("same-content-xyz")
    (tmp_path / "b.txt").write_text("same-content-xyz")
    settings = Settings()
    settings.duplicates.min_size_bytes = 1
    settings.scan.min_file_size_bytes = 0
    engine = Engine(settings)
    fracs = []

    def cb(msg, frac):
        if frac is not None:
            fracs.append(frac)

    reporter = ProgressReporter(callback=cb)
    scan, groups = engine.find_duplicates(tmp_path, progress=reporter)
    assert scan.total_files >= 2
    assert len(groups) >= 1
    assert fracs  # hubo fracciones reportadas
