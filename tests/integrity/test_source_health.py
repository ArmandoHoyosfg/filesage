"""Salud del codigo fuente: sintaxis y estructura basica."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "filesage"


def _py_files(base: Path) -> list[Path]:
    return sorted(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)


@pytest.mark.integrity
def test_all_source_parses():
    errors: list[str] = []
    for path in _py_files(SRC):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as e:
            errors.append(f"{path.relative_to(ROOT)}: {e}")
    assert not errors, "Errores de sintaxis:\n" + "\n".join(errors)


@pytest.mark.integrity
def test_pages_module_parses_and_has_routes():
    pages = SRC / "presentation" / "web" / "pages.py"
    tree = ast.parse(pages.read_text(encoding="utf-8"))
    funcs = {
        n.name
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("page_")
    }
    required = {
        "page_dashboard",
        "page_space",
        "page_duplicates",
        "page_smart",
        "page_search",
        "page_tools",
        "page_history",
        "page_settings",
        "page_about",
    }
    missing = required - funcs
    assert not missing, f"Faltan page_* en pages.py: {missing}"


@pytest.mark.integrity
def test_no_merged_search_into_smart():
    """Regresion: codigo de Buscar no debe vivir dentro de page_smart."""
    text = (SRC / "presentation" / "web" / "pages.py").read_text(encoding="utf-8")
    # Extraer cuerpo aproximado de page_smart hasta el siguiente @ui.page o def page_
    start = text.find("def page_smart()")
    assert start > 0
    rest = text[start + 10 :]
    next_page = rest.find("\n@ui.page(")
    next_def = rest.find("\ndef page_")
    end_rel = min(x for x in (next_page, next_def) if x > 0)
    body = rest[:end_rel]
    assert 'state["results"]' not in body, (
        "page_smart no debe usar state['results'] (pertenece a Buscar)"
    )
    assert "do_search" not in body
    assert "def page_search()" in text
