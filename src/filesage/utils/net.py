"""Utilidades de red: seleccion inteligente de puerto libre."""

from __future__ import annotations

import logging
import socket
from typing import Iterable

logger = logging.getLogger(__name__)

# Preferidos: evitar 8080/8000/3000 (muy usados por otros stacks)
DEFAULT_PREFERRED_PORTS = (8765, 8766, 8767, 8877, 8899, 9090, 9091)
DEFAULT_SCAN_START = 8765
DEFAULT_SCAN_END = 8999


def is_port_free(host: str, port: int) -> bool:
    """True si se puede hacer bind en host:port."""
    if port <= 0 or port > 65535:
        return False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # Sin SO_REUSEADDR: si otro proceso tiene el puerto, falla el bind
            s.bind((host, port))
            return True
    except OSError:
        return False


def find_free_port(
    host: str = "127.0.0.1",
    *,
    preferred: int | None = None,
    candidates: Iterable[int] | None = None,
    start: int = DEFAULT_SCAN_START,
    end: int = DEFAULT_SCAN_END,
) -> int:
    """Elige un puerto libre.

    Orden:
    1. ``preferred`` si esta libre
    2. lista ``candidates`` (o DEFAULT_PREFERRED_PORTS)
    3. barrido start..end
    4. puerto efimero del SO (bind 0)

    Raises:
        RuntimeError: si no hay puerto disponible (muy raro).
    """
    tried: list[int] = []

    def _try(p: int) -> int | None:
        if p in tried:
            return None
        tried.append(p)
        if is_port_free(host, p):
            return p
        return None

    if preferred and preferred > 0:
        hit = _try(preferred)
        if hit is not None:
            logger.info("Puerto preferido libre: %s:%s", host, hit)
            return hit
        logger.warning("Puerto %s ocupado; buscando alternativa…", preferred)

    for p in candidates or DEFAULT_PREFERRED_PORTS:
        hit = _try(int(p))
        if hit is not None:
            logger.info("Puerto candidato libre: %s:%s", host, hit)
            return hit

    for p in range(start, end + 1):
        hit = _try(p)
        if hit is not None:
            logger.info("Puerto libre por barrido: %s:%s", host, hit)
            return hit

    # Ultimo recurso: el SO asigna
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, 0))
            p = int(s.getsockname()[1])
            logger.info("Puerto efimero del SO: %s:%s", host, p)
            return p
    except OSError as exc:
        raise RuntimeError(f"No hay puertos libres en {host}") from exc
