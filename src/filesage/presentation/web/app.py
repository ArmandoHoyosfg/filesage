"""Punto de entrada NiceGUI — ventana nativa tipo app."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _require_nicegui():
    try:
        import nicegui  # noqa: F401
    except ImportError as e:
        raise SystemExit(
            "El adaptador web requiere NiceGUI.\n"
            "  pip install 'filesage[web]'\n"
            "  # o: pip install nicegui pywebview"
        ) from e


def run(
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    native: bool = True,
    reload: bool = False,
    window_size: tuple[int, int] = (1180, 760),
) -> None:
    """Arranca FileSage como app de escritorio (WebView nativo por defecto)."""
    _require_nicegui()
    from nicegui import app, ui

    from filesage.assets import icon_path
    from filesage.presentation.web import pages  # noqa: F401
    from filesage.presentation.web.context import get_settings
    from filesage.presentation.web.window_icon import apply_native_icon
    from filesage.utils.logging import setup_logging
    from filesage.utils.net import find_free_port

    settings = get_settings()
    setup_logging(settings.logging)

    preferred = port if port and port > 0 else None
    env_port = os.environ.get("FILESAGE_PORT", "").strip()
    if preferred is None and env_port.isdigit():
        preferred = int(env_port)

    chosen = find_free_port(host, preferred=preferred)
    if preferred and chosen != preferred:
        logger.warning(
            "Puerto %s ocupado; FileSage usara %s:%s", preferred, host, chosen
        )
    else:
        logger.info("FileSage UI en http://%s:%s (native=%s)", host, chosen, native)

    fav = icon_path("filesage.png")
    ico = icon_path("filesage.ico")
    if not fav.exists():
        fav = icon_path("filesage.svg")
    icon_file = ico if ico.exists() else fav

    if native:
        try:
            # Nunca pasar "icon" en window_args → create_window no lo acepta
            app.native.window_args["resizable"] = True
            app.native.window_args["title"] = f"{settings.app.name}"
            app.native.settings["ALLOW_DOWNLOADS"] = True
            if icon_file.exists():
                apply_native_icon(icon_file, app_title=settings.app.name)
        except Exception as exc:
            logger.debug("native window args: %s", exc)

    run_kwargs = dict(
        title=settings.app.name,
        host=host,
        port=chosen,
        reload=reload,
        native=native,
        dark=True,
        # favicon: pestaña del servidor; NiceGUI reciente puede reusarlo en nativo
        favicon=str(fav) if fav.exists() else "🗂️",
        show=not native,
        window_size=window_size if native else None,
        uvicorn_logging_level="warning",
    )

    ui.run(**run_kwargs)


if __name__ in {"__main__", "__mp_main__"}:
    run()
