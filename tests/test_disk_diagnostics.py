
from pathlib import Path
from filesage.services.disk_diagnostics import diagnose_path


def test_diagnose_ok(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello" * 100)
    (tmp_path / "b.txt").write_text("world" * 100)
    r = diagnose_path(tmp_path)
    assert r.sample_files >= 1
    assert r.sample_errors == 0
    assert any(f.level in {"ok", "info", "warn"} for f in r.findings)


def test_diagnose_missing():
    r = diagnose_path("/ruta/que/no/existe/filesage")
    assert any(f.level == "error" for f in r.findings)
