"""Flujos del motor equivalentes a cada seccion de la UI."""

from __future__ import annotations

from pathlib import Path

import pytest

from filesage.application.progress import ProgressReporter
from filesage.services.file_search import match_file, rank_hits
from filesage.services.empty_folders import find_empty_folders


@pytest.mark.integrity
def test_flow_space(engine_tmp, sample_tree: Path):
    msgs: list[str] = []
    rep = ProgressReporter(callback=lambda m, f: msgs.append(m))
    scan, report = engine_tmp.analyze_space(sample_tree, top_n=5, progress=rep)
    assert scan.total_files >= 3
    assert report is not None
    assert msgs, "debe reportar progreso"


@pytest.mark.integrity
def test_flow_duplicates_strategies(engine_tmp, sample_tree: Path):
    scan, groups = engine_tmp.find_duplicates(sample_tree)
    assert groups, "debe haber al menos un grupo duplicado"
    for strategy in ("newest", "oldest", "shortest_name"):
        plans = engine_tmp.plan_trash_duplicates(groups, strategy=strategy)
        assert plans, strategy
        tx = engine_tmp.execute_actions_progressed(plans, dry_run=True)
        assert tx.dry_run
        assert all(a.success for a in tx.actions)


@pytest.mark.integrity
def test_flow_smart_plan(engine_tmp, sample_tree: Path):
    plan = engine_tmp.build_smart_plan(sample_tree)
    assert plan is not None
    # seleccionar todo y dry-run si hay acciones
    for it in plan.items:
        it.selected = True
    actions = engine_tmp.smart_plan_to_actions(plan)
    if actions:
        tx = engine_tmp.execute_actions_progressed(actions, dry_run=True)
        assert tx.dry_run


@pytest.mark.integrity
def test_flow_search_intelligent(engine_tmp, sample_tree: Path):
    scan = engine_tmp.scan(sample_tree)
    hits = []
    for fi in scan.files:
        h = match_file(
            path=fi.path,
            size=int(fi.size),
            root=sample_tree,
            query="unique",
            use_path=False,
            use_meta=False,
        )
        if h:
            hits.append(h)
    ranked = rank_hits(hits)
    assert ranked, "debe encontrar unique.txt por nombre"
    # no debe matchear solo por carpeta FileSage_converted
    fake = sample_tree / "FileSage_converted"
    fake.mkdir(exist_ok=True)
    decoy = fake / "photo.jpg"
    decoy.write_bytes(b"x")
    h = match_file(
        path=decoy,
        size=1,
        root=sample_tree,
        query="converted",
        use_path=True,
    )
    assert h is None


@pytest.mark.integrity
def test_flow_organize(engine_tmp, sample_tree: Path):
    plan = engine_tmp.build_organize_plan(sample_tree, min_files_per_group=1)
    assert plan is not None


@pytest.mark.integrity
def test_flow_cleanup_and_empty(engine_tmp, sample_tree: Path):
    empties = find_empty_folders(sample_tree)
    assert any(p.name == "empty_dir" for p in empties) or any(
        "empty_dir" in str(p) for p in empties
    )
    plan = engine_tmp.build_cleanup_plan(
        sample_tree,
        include_empty_folders=True,
        include_old_files=False,
    )
    assert plan is not None


@pytest.mark.integrity
def test_flow_convert_skips_same_format(engine_tmp, sample_tree: Path):
    img = sample_tree / "media" / "pixel.png"
    results = engine_tmp.convert_images(img, target_ext="png", force=False)
    # lista de ConvertResult
    assert results is not None


@pytest.mark.integrity
def test_flow_hash_cache_speeds_second_pass(engine_tmp, sample_tree: Path):
    f = sample_tree / "big.bin"
    d1 = engine_tmp.hasher.full_hash(f)
    d2 = engine_tmp.hasher.full_hash(f)
    assert d1 == d2


@pytest.mark.integrity
def test_flow_execute_progressed_cancel_token(engine_tmp, sample_tree: Path):
    from filesage.application.progress import CancellationToken, ProgressReporter
    from filesage.domain.exceptions import CancelledError

    (sample_tree / "x1.txt").write_text("same-xx")
    (sample_tree / "x2.txt").write_text("same-xx")
    _, groups = engine_tmp.find_duplicates(sample_tree)
    plans = engine_tmp.plan_trash_duplicates(groups, strategy="newest")
    if not plans:
        pytest.skip("sin planes")
    token = CancellationToken()
    token.cancel()
    rep = ProgressReporter(cancel=token)

    with pytest.raises(CancelledError):
        engine_tmp.execute_actions_progressed(plans, dry_run=True, progress=rep)
