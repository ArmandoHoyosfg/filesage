"""Tests de ActionManager y transacciones (Etapa 3)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from filesage.core.config import Settings
from filesage.core.engine import Engine
from filesage.domain.models import ActionRecord, ActionType
from filesage.infrastructure.storage import new_action_id


@pytest.fixture
def action_tree(tmp_path: Path) -> Path:
    content = b"duplicado de prueba " * 30
    (tmp_path / "keep.txt").write_bytes(content)
    (tmp_path / "remove_me.txt").write_bytes(content)
    (tmp_path / "unique.txt").write_text("solo uno")
    return tmp_path


def test_plan_and_dry_run(action_tree: Path):
    settings = Settings()
    settings.duplicates.min_size_bytes = 10
    settings.app.dry_run_default = True
    engine = Engine(settings)

    _, groups = engine.find_duplicates(action_tree)
    assert len(groups) >= 1

    plans = engine.plan_trash_duplicates(groups, keep_newest=True)
    assert len(plans) >= 1
    assert all(p.action_type == ActionType.TRASH for p in plans)

    tx = engine.execute_actions(plans, dry_run=True)
    assert tx.dry_run is True
    assert all(a.success for a in tx.actions)
    # Archivos siguen existiendo
    assert (action_tree / "remove_me.txt").exists()
    assert (action_tree / "keep.txt").exists()


def test_list_transactions(action_tree: Path):
    settings = Settings()
    settings.duplicates.min_size_bytes = 10
    # Usar DB temporal
    settings.storage.transaction_db = str(action_tree / "tx.db")
    engine = Engine(settings)

    _, groups = engine.find_duplicates(action_tree)
    plans = engine.plan_trash_duplicates(groups)
    engine.execute_actions(plans, dry_run=True)

    txs = engine.list_transactions(limit=10)
    assert len(txs) >= 1
    assert txs[0].dry_run is True
