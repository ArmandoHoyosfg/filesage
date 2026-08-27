from pathlib import Path
from filesage.core.config import Settings
from filesage.core.engine import Engine
from filesage.services.smart_planner import Confidence


def test_organize_suggestions(tmp_path: Path):
    # Contenido unico por archivo (si son iguales, van a duplicados y no a organizar)
    for i in range(4):
        (tmp_path / f"track{i}.mp3").write_bytes(b"ID3" + bytes([i]) * 200)
    for i in range(3):
        (tmp_path / f"pic{i}.jpg").write_bytes(b"\xff\xd8\xff" + bytes([i + 10]) * 80)

    settings = Settings()
    settings.duplicates.min_size_bytes = 1
    engine = Engine(settings)
    plan = engine.build_smart_plan(tmp_path)
    org = [i for i in plan.items if i.category == "organize"]
    assert len(org) >= 3
    assert all(i.confidence == Confidence.MEDIUM for i in org)
    assert all(not i.selected for i in org)
    assert any("Musica" in i.reason for i in org)
    assert any("Imagenes" in i.reason for i in org)
