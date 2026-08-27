"""Punto de entrada unificado: python -m filesage

Por defecto abre la GUI. La CLI queda disponible con:
  python -m filesage cli ...
  o el comando instalado `filesage`
"""

from __future__ import annotations

import sys


def main() -> int:
    # Si el usuario pide explicitamente CLI, delegar
    if len(sys.argv) > 1 and sys.argv[1] in ("cli", "--cli"):
        sys.argv.pop(1)
        from filesage.presentation.cli import app
        app()
        return 0

    # Si hay subcomandos tipicos de CLI sin prefijo, tambien delegar
    cli_cmds = {
        "scan", "space", "duplicates", "export", "info", "version",
        "hello", "gui", "--help", "-h",
    }
    if len(sys.argv) > 1 and sys.argv[1] in cli_cmds:
        from filesage.presentation.cli import app
        app()
        return 0

    # Por defecto: GUI
    from filesage.presentation.gui.app import run_gui
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
