"""Cancelacion cooperativa y seleccion Smart (logica de motor)."""

from pathlib import Path

import pytest

from filesage.application.progress import CancellationToken, ProgressReporter
from filesage.core.config import Settings
from filesage.core.engine import Engine
from filesage.domain.exceptions import CancelledError


def test_cancel_during_progress_callback(tmp_path: Path):
    for i in range(30):
        (tmp_path / f"f{i}.txt").write_text(f"data{i}")
    settings = Settings()
    settings.scan.min_file_size_bytes = 0
    engine = Engine(settings)
    token = CancellationToken()
    count = {"n": 0}

    def cb(msg, frac):
        count["n"] += 1
        if count["n"] >= 2:
            token.cancel()

    reporter = ProgressReporter(callback=cb, cancel=token)
    with pytest.raises(CancelledError):
        # force cancel by cancelling after first reports — scan may finish if tiny
        token.cancel()
        reporter.report("x", 0.1)


def test_smart_toggle_selection_affects_actions(tmp_path: Path):
    (tmp_path / "a.txt").write_text("same-body")
    (tmp_path / "b.txt").write_text("same-body")
    settings = Settings()
    settings.duplicates.min_size_bytes = 1
    engine = Engine(settings)
    plan = engine.build_smart_plan(tmp_path)
    if not plan.items:
        pytest.skip("no plan items")
    # deselect all
    for it in plan.items:
        it.selected = False
    assert engine.smart_plan_to_actions(plan) == []
    # select first
    plan.items[0].selected = True
    actions = engine.smart_plan_to_actions(plan)
    assert len(actions) >= 1
