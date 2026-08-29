"""Adaptador web/app de FileSage.

Por defecto abre ventana nativa (pywebview), no el navegador.
El puerto se elige solo si esta libre (evita choques con otras apps).

  python scripts/run_filesage.py --web
  python scripts/run_filesage.py --web --port 0          # auto
  python scripts/run_filesage.py --web --browser --port 8765
  FILESAGE_PORT=8877 python scripts/run_filesage.py --web
"""

from __future__ import annotations

__all__ = ["run_web"]


def run_web(
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    native: bool = True,
    reload: bool = False,
) -> None:
    from filesage.presentation.web.app import run

    run(host=host, port=port, native=native, reload=reload)
