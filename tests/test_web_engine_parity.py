"""Integracion: flujos que usa la UI web (sin arrancar NiceGUI)."""

from pathlib import Path

from filesage.application.progress import ProgressReporter
from filesage.core.config import Settings
from filesage.core.engine import Engine
from filesage.presentation.web.context import get_engine, get_settings, persist_settings, reload_settings


def test_web_context_engine():
    e = get_engine()
    assert e is not None
    s = get_settings()
    assert s.app.name


def test_space_export_roundtrip(tmp_path: Path):
    (tmp_path / "big.bin").write_bytes(b"x" * 5000)
    (tmp_path / "small.txt").write_text("hi")
    settings = Settings()
    settings.scan.min_file_size_bytes = 0
    engine = Engine(settings)
    msgs = []
    rep = ProgressReporter(callback=lambda m, f: msgs.append(m))
    scan, report = engine.analyze_space(tmp_path, top_n=10, progress=rep)
    assert scan.total_files >= 2
    out = engine.export_space(report, scan, tmp_path / "space.json", fmt="json")
    assert out.exists() and out.stat().st_size > 10
    out2 = engine.export_space(report, scan, tmp_path / "space.csv", fmt="csv")
    assert out2.exists()


def test_duplicates_dry_run_and_export(tmp_path: Path):
    (tmp_path / "a.txt").write_text("duplicate-body-xyz")
    (tmp_path / "b.txt").write_text("duplicate-body-xyz")
    settings = Settings()
    settings.duplicates.min_size_bytes = 1
    settings.scan.min_file_size_bytes = 0
    engine = Engine(settings)
    scan, groups = engine.find_duplicates(tmp_path)
    assert len(groups) >= 1
    plans = engine.plan_trash_duplicates(groups, keep_newest=True)
    tx = engine.execute_actions(plans, dry_run=True)
    assert tx.dry_run
    assert all(a.success for a in tx.actions)
    out = engine.export_duplicates(groups, tmp_path, tmp_path / "d.json", fmt="json")
    assert out.exists()


def test_smart_plan_dry_run(tmp_path: Path):
    (tmp_path / "a.txt").write_text("same")
    (tmp_path / "b.txt").write_text("same")
    settings = Settings()
    settings.duplicates.min_size_bytes = 1
    engine = Engine(settings)
    plan = engine.build_smart_plan(tmp_path)
    # puede o no tener selected segun heuristica
    actions = engine.smart_plan_to_actions(plan)
    if actions:
        tx = engine.execute_actions(actions, dry_run=True)
        assert tx.dry_run
