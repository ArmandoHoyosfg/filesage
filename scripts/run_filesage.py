#!/usr/bin/env python3
"""Lanzador robusto de FileSage (sin empaquetar).

Revisa el entorno antes de abrir la GUI:
- Version de Python
- Estructura del proyecto
- Dependencias criticas
- Configura PYTHONPATH
- Arranca la aplicacion

Uso (desde cualquier directorio):
  python scripts/run_filesage.py
  python3 scripts/run_filesage.py
  ./scripts/run_filesage.py
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

MIN_PY = (3, 11)

REQUIRED = [
    ("pydantic", "pydantic"),
    ("pydantic_settings", "pydantic-settings"),
    ("typer", "typer"),
    ("rich", "rich"),
    ("xxhash", "xxhash"),
    ("send2trash", "send2trash"),
    ("yaml", "pyyaml"),
    ("PySide6", "PySide6"),
    ("PIL", "Pillow"),
    ("pypdf", "pypdf"),
    ("tinytag", "tinytag"),
    ("puremagic", "puremagic"),
    ("qtawesome", "qtawesome"),
]


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def fail(msg: str, code: int = 1) -> None:
    print(f"[FileSage] ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def info(msg: str) -> None:
    print(f"[FileSage] {msg}")


def check_python() -> None:
    if sys.version_info < MIN_PY:
        fail(
            f"Se necesita Python {MIN_PY[0]}.{MIN_PY[1]}+. "
            f"Actual: {sys.version_info.major}.{sys.version_info.minor}"
        )
    info(f"Python OK: {sys.version.split()[0]}")


def check_structure(root: Path) -> None:
    needed = [
        root / "src" / "filesage" / "__main__.py",
        root / "src" / "filesage" / "presentation" / "gui" / "app.py",
        root / "pyproject.toml",
    ]
    for p in needed:
        if not p.exists():
            fail(f"Estructura incompleta. Falta: {p}")
    info(f"Proyecto OK: {root}")


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def check_dependencies(auto_install: bool) -> None:
    missing = []
    for mod, pkg in REQUIRED:
        if not module_available(mod):
            missing.append(pkg)

    if not missing:
        info("Dependencias criticas OK")
        return

    info(f"Faltan dependencias: {', '.join(missing)}")
    if not auto_install:
        fail(
            "Instala con:\n"
            f"  {sys.executable} -m pip install {' '.join(missing)}\n"
            "O vuelve a lanzar con: python scripts/run_filesage.py --install"
        )

    info("Instalando dependencias...")
    cmd = [sys.executable, "-m", "pip", "install", *missing]
    # En algunos entornos hace falta --break-system-packages
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            cmd2 = cmd + ["--break-system-packages"]
            r = subprocess.run(cmd2, capture_output=True, text=True)
        if r.returncode != 0:
            fail(f"No se pudieron instalar dependencias:\n{r.stderr or r.stdout}")
    except Exception as e:
        fail(str(e))

    for mod, pkg in REQUIRED:
        if not module_available(mod):
            fail(f"Tras instalar, sigue faltando el modulo: {mod} (paquete {pkg})")
    info("Dependencias instaladas OK")


def setup_path(root: Path) -> None:
    src = str(root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    os.environ["PYTHONPATH"] = src + os.pathsep + os.environ.get("PYTHONPATH", "")


def launch_gui() -> int:
    info("Iniciando GUI...")
    from filesage.presentation.gui.app import run_gui

    return int(run_gui() or 0)


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    auto_install = "--install" in argv or "-i" in argv
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        print("Opciones:")
        print("  --install, -i   Instala dependencias faltantes con pip")
        print("  --cli           Delega a la CLI en lugar de la GUI")
        print("  --check         Solo verifica entorno y sale")
        return 0

    root = project_root()
    info("Comprobando entorno...")
    check_python()
    check_structure(root)
    check_dependencies(auto_install=auto_install)
    setup_path(root)

    if "--check" in argv:
        info("Entorno listo. Nada que ejecutar (--check).")
        return 0

    if "--cli" in argv:
        # Quitar flags propios y pasar el resto a typer
        rest = [a for a in argv if a not in ("--install", "-i", "--cli", "--check")]
        from filesage.presentation.cli import app

        sys.argv = ["filesage", *rest]
        app()
        return 0

    try:
        return launch_gui()
    except Exception as e:
        fail(f"Fallo al iniciar la GUI: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
