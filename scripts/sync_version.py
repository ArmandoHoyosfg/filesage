#!/usr/bin/env python3
"""Sincroniza la version desde VERSION a pyproject, config y default.yaml."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_version() -> str:
    v = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(\.\d+)?([a-zA-Z0-9.-]+)?", v):
        raise SystemExit(f"VERSION invalida: {v!r}")
    return v


def patch_file(path: Path, patterns: list[tuple[str, str]]) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    orig = text
    for old, new in patterns:
        text = re.sub(old, new, text, count=1)
    if text != orig:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> int:
    ver = read_version()
    updates = []

    if patch_file(
        ROOT / "pyproject.toml",
        [(r'(?m)^version\s*=\s*"[^"]+"', f'version = "{ver}"')],
    ):
        updates.append("pyproject.toml")

    if patch_file(
        ROOT / "src" / "filesage" / "core" / "config.py",
        [(r'version:\s*str\s*=\s*"[^"]+"', f'version: str = "{ver}"')],
    ):
        updates.append("config.py")

    if patch_file(
        ROOT / "config" / "default.yaml",
        [(r'(?m)^(\s*version:\s*)"[^"]+"', rf'\1"{ver}"')],
    ):
        updates.append("default.yaml")

    # __init__.py if has __version__
    init = ROOT / "src" / "filesage" / "__init__.py"
    if init.exists():
        t = init.read_text(encoding="utf-8")
        if "__version__" in t:
            if patch_file(init, [(r'__version__\s*=\s*"[^"]+"', f'__version__ = "{ver}"')]):
                updates.append("__init__.py")
        else:
            init.write_text(t.rstrip() + f'\n\n__version__ = "{ver}"\n', encoding="utf-8")
            updates.append("__init__.py")

    print(f"Version {ver} sincronizada en: {', '.join(updates) or '(ya al dia)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
