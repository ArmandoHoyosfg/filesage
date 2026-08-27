"""Capa de inteligencia local (heuristica, sin cloud).

Genera recomendaciones seguras y priorizadas a partir de un ScanResult:
- Archivos muy grandes
- Archivos antiguos y grandes
- Instaladores / descargas tipicas
- Archivos vacios
- Carpetas con muchos archivos pequenos (posible basura)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from filesage.domain.models import FileInfo, ScanResult

logger = logging.getLogger(__name__)

# Extensiones tipicas de instaladores / temporales de descarga
INSTALLER_EXTS = {".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".appimage", ".iso"}
TEMP_HINTS = ("temp", "tmp", "cache", "thumbnail", "crash", "log")
OLD_DAYS = 90
LARGE_BYTES = 50 * 1024 * 1024  # 50 MB
HUGE_BYTES = 500 * 1024 * 1024  # 500 MB


@dataclass(frozen=True)
class Insight:
    category: str
    title: str
    detail: str
    severity: str  # info | suggest | caution
    paths: tuple[str, ...]
    potential_bytes: int


def analyze(scan: ScanResult, *, now: float | None = None) -> list[Insight]:
    """Analiza un ScanResult y devuelve insights ordenados por impacto."""
    now = now or time.time()
    insights: list[Insight] = []
    files = scan.files

    if not files:
        return insights

    # 1) Archivos enormes
    huge = [f for f in files if f.size >= HUGE_BYTES]
    if huge:
        huge = sorted(huge, key=lambda f: f.size, reverse=True)[:10]
        insights.append(
            Insight(
                category="large",
                title=f"{len(huge)} archivo(s) muy grande(s) (≥ 500 MB)",
                detail="Revisa si siguen siendo necesarios. Son los que mas liberan espacio.",
                severity="suggest",
                paths=tuple(str(f.path) for f in huge),
                potential_bytes=sum(f.size for f in huge),
            )
        )

    # 2) Grandes y antiguos
    old_large = [
        f
        for f in files
        if f.size >= LARGE_BYTES and (now - f.mtime) >= OLD_DAYS * 86400
    ]
    if old_large:
        old_large = sorted(old_large, key=lambda f: f.size, reverse=True)[:15]
        insights.append(
            Insight(
                category="old_large",
                title=f"{len(old_large)} archivo(s) grande(s) y sin modificar ≥ {OLD_DAYS} dias",
                detail="Candidatos a archivar o eliminar si ya no los usas.",
                severity="suggest",
                paths=tuple(str(f.path) for f in old_large),
                potential_bytes=sum(f.size for f in old_large),
            )
        )

    # 3) Instaladores
    installers = [f for f in files if f.extension in INSTALLER_EXTS and f.size >= 5 * 1024 * 1024]
    if installers:
        installers = sorted(installers, key=lambda f: f.size, reverse=True)[:15]
        insights.append(
            Insight(
                category="installers",
                title=f"{len(installers)} instalador(es) o imagen(es) de disco",
                detail="Tras instalar, suelen sobrar. Comprueba antes de borrar.",
                severity="info",
                paths=tuple(str(f.path) for f in installers),
                potential_bytes=sum(f.size for f in installers),
            )
        )

    # 4) Vacios
    empty = [f for f in files if f.size == 0]
    if empty:
        insights.append(
            Insight(
                category="empty",
                title=f"{len(empty)} archivo(s) vacio(s)",
                detail="Casi nunca son utiles. Revisalos si quieres ordenar.",
                severity="info",
                paths=tuple(str(f.path) for f in empty[:20]),
                potential_bytes=0,
            )
        )

    # 5) Pistas de cache/temp en la ruta
    tempish = [
        f
        for f in files
        if f.size > 1024 * 1024
        and any(h in str(f.path).lower() for h in TEMP_HINTS)
    ]
    if tempish:
        tempish = sorted(tempish, key=lambda f: f.size, reverse=True)[:15]
        insights.append(
            Insight(
                category="temp_hint",
                title=f"{len(tempish)} archivo(s) en rutas tipo cache/temp/log",
                detail="Heuristica por nombre de ruta. No borres sin revisar (pueden ser datos de apps).",
                severity="caution",
                paths=tuple(str(f.path) for f in tempish),
                potential_bytes=sum(f.size for f in tempish),
            )
        )

    insights.sort(key=lambda i: i.potential_bytes, reverse=True)
    logger.info("Smart insights: %d recomendaciones", len(insights))
    return insights
