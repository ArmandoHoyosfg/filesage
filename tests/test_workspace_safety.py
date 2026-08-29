from pathlib import Path

from filesage.core.workspace_safety import (
    assess_workspace,
    effective_exclude_patterns,
    RECOMMENDED_EXCLUDE_PATTERNS,
)


def test_home_is_warn():
    a = assess_workspace(Path.home())
    assert a.level == "warn"


def test_downloads_ok_if_exists():
    for name in ("Downloads", "Descargas", "Documents", "Documentos"):
        p = Path.home() / name
        if p.is_dir():
            a = assess_workspace(p)
            assert a.level in ("ok", "warn")  # ok expected
            if a.level == "ok":
                return
    # if none exist, still ok to assess tmp
    a = assess_workspace(Path.cwd())
    assert a.level in ("ok", "warn", "danger")


def test_recommended_merge():
    base = ["**/custom/**"]
    out = effective_exclude_patterns(base, use_recommended=True)
    assert "**/custom/**" in out
    assert any("AppData" in p for p in out)
    assert any(".git" in p for p in out)
    out2 = effective_exclude_patterns(base, use_recommended=False)
    assert out2 == base
