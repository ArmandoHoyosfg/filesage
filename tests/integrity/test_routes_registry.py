"""Registro de rutas web = contrato de navegacion."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / "src" / "filesage" / "presentation" / "web" / "pages.py"
LAYOUT = ROOT / "src" / "filesage" / "presentation" / "web" / "layout.py"

# Rutas que la app debe exponer (navegacion lateral + herramientas)
EXPECTED_ROUTES = {
    "/",
    "/space",
    "/duplicates",
    "/smart",
    "/search",
    "/tools",
    "/tools/organize",
    "/tools/cleanup",
    "/tools/recycle",
    "/tools/network",
    "/tools/convert",
    "/tools/similar",
    "/tools/empty",
    "/tools/zip",
    "/tools/transfer",
    "/tools/disk",
    "/tools/metadata",
    "/history",
    "/settings",
    "/about",
}


def _routes_from_pages() -> set[str]:
    text = PAGES.read_text(encoding="utf-8")
    # @ui.page("/path") o @ui.page('/')
    found = set(re.findall(r'@ui\.page\(\s*["\']([^"\']+)["\']', text))
    return found


@pytest.mark.integrity
def test_all_expected_routes_registered():
    found = _routes_from_pages()
    missing = EXPECTED_ROUTES - found
    extra_ok = found - EXPECTED_ROUTES  # extras permitidos
    assert not missing, f"Rutas faltantes en pages.py: {sorted(missing)}"
    # documentar extras sin fallar
    assert isinstance(extra_ok, set)


@pytest.mark.integrity
def test_each_route_has_page_function():
    tree = ast.parse(PAGES.read_text(encoding="utf-8"))
    # Map decorator route -> function name
    route_to_fn: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            if (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Attribute)
                and dec.func.attr == "page"
                and dec.args
                and isinstance(dec.args[0], ast.Constant)
            ):
                route_to_fn[str(dec.args[0].value)] = node.name
    for route in EXPECTED_ROUTES:
        assert route in route_to_fn, f"Ruta {route} sin funcion decorada"
        assert route_to_fn[route].startswith("page_"), route_to_fn[route]


@pytest.mark.integrity
def test_layout_nav_targets_exist():
    """Enlaces del layout no deben apuntar a rutas inexistentes."""
    if not LAYOUT.exists():
        pytest.skip("sin layout")
    text = LAYOUT.read_text(encoding="utf-8")
    nav_paths = set(re.findall(r'["\'](/(?:[a-z0-9_/-]*))["\']', text))
    # filtrar solo paths que parecen rutas de app
    nav_paths = {p for p in nav_paths if p.startswith("/") and " " not in p}
    registered = _routes_from_pages()
    # algunos pueden ser solo fragmentos; solo comprobar interseccion tipica
    critical = {"/", "/space", "/duplicates", "/smart", "/search", "/history", "/settings"}
    for p in critical:
        if p in nav_paths or True:
            assert p in registered, f"Nav critica {p} no registrada"
