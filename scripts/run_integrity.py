#!/usr/bin/env python3
"""Ejecuta la suite de integridad FileSage (bloque S).

Uso:
  python scripts/run_integrity.py
  python scripts/run_integrity.py -q
  python scripts/run_integrity.py --full   # toda la carpeta tests/
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Suite de integridad FileSage")
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Ejecuta todos los tests del proyecto, no solo integrity/",
    )
    parser.add_argument(
        "--marker",
        default="integrity",
        help="Marcador pytest (default: integrity)",
    )
    args = parser.parse_args()

    target = str(ROOT / "tests") if args.full else str(ROOT / "tests" / "integrity")
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        target,
        "-v" if not args.quiet else "-q",
        "--tb=short",
    ]
    if not args.full:
        cmd.extend(["-m", args.marker])

    print("→", " ".join(cmd))
    print("   Raiz:", ROOT)
    env = {**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": str(ROOT / "src")}
    # Prefer pythonpath via pytest.ini; still set env
    result = subprocess.run(cmd, cwd=str(ROOT), env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")})
    if result.returncode == 0:
        print("\n✓ Integridad OK — no se detectaron fallos en la suite.")
    else:
        print("\n✗ Integridad FALLÓ — revisa el informe de pytest arriba.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
