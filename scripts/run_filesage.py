#!/usr/bin/env python3
"""Lanzador robusto de FileSage (sin empaquetar).

Revisa el entorno y arranca GUI Qt o Web.

  python scripts/run_filesage.py           # GUI Qt (por defecto)
  python scripts/run_filesage.py --web     # Adaptador web NiceGUI
  python scripts/run_filesage.py --check   # Solo verificacion
  python scripts/run_filesage.py --install # Intenta instalar deps
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

MIN_PY = (3, 11)

REQUIRED_CORE = [
    ("pydantic", "pydantic"),
    ("pydantic_settings", "pydantic-settings"),
    ("typer", "typer"),
    ("rich", "rich"),
    ("xxhash", "xxhash"),
    ("send2trash", "send2trash"),
    ("yaml", "pyyaml"),
]

REQUIRED_GUI = [
    ("PySide6", "PySide6"),
    ("PIL", "Pillow"),
    ("pypdf", "pypdf"),
    ("tinytag", "tinytag"),
    ("puremagic", "puremagic"),
    ("qtawesome", "qtawesome"),
]

REQUIRED_WEB = [
    ("nicegui", "nicegui"),
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


def missing_packages(pairs: list[tuple[str, str]]) -> list[str]:
    return [pip_name for mod, pip_name in pairs if not module_available(mod)]


def install_packages(pkgs: list[str]) -> None:
    if not pkgs:
        return
    info(f"Instalando: {', '.join(pkgs)}")
    cmd = [sys.executable, "-m", "pip", "install", *pkgs]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        fail("Fallo al instalar dependencias. Revisa el log de pip.")


def ensure_path(root: Path) -> None:
    src = str(root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    os.environ["PYTHONPATH"] = src + os.pathsep + os.environ.get("PYTHONPATH", "")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Lanzador FileSage (sin empaquetar)")
    p.add_argument("--gui", action="store_true", help="Abrir GUI Qt (default)")
    p.add_argument("--web", action="store_true", help="Abrir UI web en ventana nativa")
    p.add_argument("--browser", action="store_true", help="Forzar navegador en vez de ventana nativa")
    p.add_argument("--check", action="store_true", help="Solo verificar entorno")
    p.add_argument(
        "--install",
        action="store_true",
        help="Instalar dependencias faltantes con pip",
    )
    p.add_argument(
        "--port",
        type=int,
        default=0,
        help="Puerto web (0 = automatico, elige uno libre)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    root = project_root()
    check_python()
    check_structure(root)
    ensure_path(root)

    mode = "web" if args.web else "gui"
    needed = list(REQUIRED_CORE)
    if mode == "gui":
        needed += REQUIRED_GUI
    else:
        needed += REQUIRED_WEB

    missing = missing_packages(needed)
    if missing:
        if args.install:
            install_packages(missing)
            missing = missing_packages(needed)
        if missing:
            fail(
                "Faltan dependencias: "
                + ", ".join(missing)
                + "\n  Prueba: python scripts/run_filesage.py --install"
                + (" --web" if mode == "web" else "")
            )
    info(f"Dependencias OK ({mode})")

    if args.check:
        info("Verificacion completa. Nada que lanzar (--check).")
        return

    if mode == "web":
        native = not args.browser
        info(
            "Iniciando UI "
            + ("nativa (ventana app)" if native else "en navegador")
            + (f" · puerto {args.port}" if args.port else " · puerto automatico")
        )
        from filesage.presentation.web import run_web

        run_web(
            host="127.0.0.1",
            port=args.port,  # 0 = auto libre
            native=native,
            reload=False,
        )
    else:
        info("Iniciando GUI Qt…")
        from filesage.presentation.gui.app import run_gui

        raise SystemExit(run_gui())


if __name__ == "__main__":
    main()
