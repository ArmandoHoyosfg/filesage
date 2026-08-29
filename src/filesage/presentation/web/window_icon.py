"""Asignar icono de ventana de forma portable.

pywebview:
  - create_window() NO acepta ``icon`` (por eso fallaba).
  - start(icon=...) solo documentado bien en GTK/Qt (Linux).
  - pywebview reciente: se puede pasar por start_args.
  - Windows: fallback con Win32 WM_SETICON tras mostrar la ventana.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def apply_native_icon(icon_file: Path | str, *, app_title: str = "FileSage") -> None:
    """Configura icono nativo sin romper arranque si la API no existe."""
    path = Path(icon_file)
    if not path.exists():
        logger.warning("Icono no encontrado: %s", path)
        return

    path_str = str(path.resolve())

    # 1) NiceGUI / pywebview: start_args (versiones recientes)
    try:
        from nicegui import app

        app.native.start_args["icon"] = path_str
        logger.info("Icono via app.native.start_args: %s", path_str)
    except Exception as exc:
        logger.debug("start_args icon no disponible: %s", exc)

    # 2) Windows: aplicar cuando la ventana ya existe (Win32)
    if sys.platform == "win32":
        try:
            from nicegui import app

            def _on_connect(client) -> None:  # type: ignore[no-untyped-def]
                # Diferir un poco para que exista el HWND
                try:
                    from nicegui import ui

                    ui.timer(0.8, lambda: _set_windows_icon(path_str, app_title), once=True)
                except Exception:
                    _set_windows_icon(path_str, app_title)

            # Registrar una sola vez
            if not getattr(app, "_filesage_icon_hook", False):
                app.on_connect(_on_connect)
                app._filesage_icon_hook = True  # type: ignore[attr-defined]
        except Exception as exc:
            logger.debug("hook icon Windows: %s", exc)


def _set_windows_icon(icon_path: str, title_substr: str) -> None:
    """WM_SETICON sobre la ventana cuyo titulo contiene title_substr."""
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x0010
    LR_DEFAULTSIZE = 0x0040
    WM_SETICON = 0x0080
    ICON_SMALL = 0
    ICON_BIG = 1

    hicon = user32.LoadImageW(
        None,
        icon_path,
        IMAGE_ICON,
        0,
        0,
        LR_LOADFROMFILE | LR_DEFAULTSIZE,
    )
    if not hicon:
        logger.debug("LoadImageW fallo para %s", icon_path)
        return

    matches: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd, _lparam):  # type: ignore[no-untyped-def]
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if title_substr.lower() in buf.value.lower():
            matches.append(hwnd)
        return True

    user32.EnumWindows(enum_proc, 0)
    if not matches:
        logger.debug("No se encontro ventana con titulo ~ %s", title_substr)
        return

    for hwnd in matches:
        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
    logger.info("Icono Win32 aplicado a %d ventana(s)", len(matches))
