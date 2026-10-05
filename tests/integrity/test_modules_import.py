"""Importacion de modulos criticos (sin NiceGUI obligatorio)."""

from __future__ import annotations

import importlib

import pytest

CORE_MODULES = [
    "filesage",
    "filesage.core.config",
    "filesage.core.engine",
    "filesage.core.workspace_safety",
    "filesage.domain.models",
    "filesage.infrastructure.hasher",
    "filesage.infrastructure.hash_cache",
    "filesage.infrastructure.storage",
    "filesage.services.scanner",
    "filesage.services.duplicate_finder",
    "filesage.services.action_manager",
    "filesage.services.smart_planner",
    "filesage.services.file_search",
    "filesage.services.image_converter",
    "filesage.services.cleanup_plan",
    "filesage.services.empty_folders",
    "filesage.services.network_diagnostics",
    "filesage.application.progress",
    "filesage.presentation.web.session_store",
    "filesage.presentation.web.context",
    "filesage.utils.net",
]

# Requieren nicegui (opcional en CI sin [web])
WEB_UI_MODULES = [
    "filesage.presentation.web.jobs",
    "filesage.presentation.web.confirm_actions",
]


@pytest.mark.integrity
@pytest.mark.parametrize("mod", CORE_MODULES)
def test_import_core(mod: str):
    importlib.import_module(mod)


@pytest.mark.integrity
@pytest.mark.parametrize("mod", WEB_UI_MODULES)
def test_import_web_ui_optional(mod: str):
    try:
        importlib.import_module(mod)
    except ModuleNotFoundError as e:
        assert "nicegui" in str(e).lower()


@pytest.mark.integrity
def test_pages_imports_optional_nicegui():
    """pages.py depende de nicegui; si no esta, debe fallar solo por eso."""
    try:
        importlib.import_module("filesage.presentation.web.pages")
    except ModuleNotFoundError as e:
        assert "nicegui" in str(e).lower() or "nicegui" in repr(e).lower()
