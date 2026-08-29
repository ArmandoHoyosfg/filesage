"""Heuristicas de seguridad para el directorio de trabajo / escaneos."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspaceAssessment:
    level: str  # "ok" | "warn" | "danger"
    title: str
    message: str
    suggest: str | None = None


# Carpetas tipicas mas seguras dentro del home
_SAFE_HOME_CHILDREN = {
    "downloads",
    "descargas",
    "documents",
    "documentos",
    "pictures",
    "imagenes",
    "imágenes",
    "videos",
    "music",
    "musica",
    "música",
    "desktop",
    "escritorio",
}


def _is_windows_root(path: Path) -> bool:
    s = str(path).replace("/", "\\").rstrip("\\").upper()
    return len(s) == 2 and s[1] == ":"  # C:


def assess_workspace(path: Path | str) -> WorkspaceAssessment:
    """Evalua si una carpeta es peligrosa o demasiado amplia para escanear."""
    try:
        p = Path(path).expanduser().resolve()
    except Exception:
        return WorkspaceAssessment(
            "danger",
            "Ruta invalida",
            "No se pudo interpretar la ruta del directorio de trabajo.",
        )

    if not p.exists() or not p.is_dir():
        return WorkspaceAssessment(
            "danger",
            "No es una carpeta",
            f"La ruta no existe o no es un directorio: {p}",
        )

    # Raices de sistema
    if _is_windows_root(p) or str(p) in ("/", "\\"):
        return WorkspaceAssessment(
            "danger",
            "Raiz del sistema",
            "Escanear la raiz del disco puede ser muy lento y tocar archivos del sistema.",
            suggest="Elige Descargas, Documentos o una carpeta de proyecto.",
        )

    parts_lower = [x.lower() for x in p.parts]
    dangerous_names = {
        "windows",
        "program files",
        "program files (x86)",
        "programdata",
        "system32",
        "syswow64",
        "usr",
        "bin",
        "sbin",
        "etc",
        "boot",
    }
    if any(n in dangerous_names for n in parts_lower):
        return WorkspaceAssessment(
            "danger",
            "Carpeta de sistema",
            f"«{p}» parece una ruta de sistema. No es un buen objetivo para limpieza.",
            suggest="Usa una carpeta de usuario (Descargas, Documentos, etc.).",
        )

    home = Path.home().resolve()
    if p == home:
        return WorkspaceAssessment(
            "warn",
            "Perfil de usuario completo",
            "El directorio de trabajo es tu carpeta de usuario entera. "
            "Los analisis pueden tardar mucho e incluir AppData y otros datos sensibles.",
            suggest="Recomendado: Descargas o Documentos.",
        )

    # Padre es home y la carpeta no es una de las tipicas "seguras"
    try:
        if p.parent == home and p.name.lower() not in _SAFE_HOME_CHILDREN:
            # p.ej. C:\Users\Name\AppData o carpetas raras
            if p.name.lower() in {"appdata", "application data", "local settings"}:
                return WorkspaceAssessment(
                    "danger",
                    "AppData / datos de aplicaciones",
                    "Esta carpeta contiene configuracion de programas. No conviene escanearla para limpiar.",
                    suggest="Elige Descargas o Documentos.",
                )
    except Exception:
        pass

    return WorkspaceAssessment("ok", "Directorio adecuado", str(p))


RECOMMENDED_EXCLUDE_PATTERNS: list[str] = [
    "**/.git/**",
    "**/node_modules/**",
    "**/.venv/**",
    "**/venv/**",
    "**/__pycache__/**",
    "**/.DS_Store",
    "**/Thumbs.db",
    "**/AppData/**",
    "**/Application Data/**",
    "**/.cache/**",
    "**/.npm/**",
    "**/.local/share/**",
    "**/Target/**",  # builds rust a veces
    "**/dist/**",
    "**/build/**",
]


def effective_exclude_patterns(
    base: list[str],
    *,
    use_recommended: bool = True,
) -> list[str]:
    """Une patrones de usuario con los recomendados (sin duplicar)."""
    out: list[str] = []
    seen: set[str] = set()
    merged = list(base)
    if use_recommended:
        merged = list(base) + list(RECOMMENDED_EXCLUDE_PATTERNS)
    for p in merged:
        key = p.replace("\\", "/").lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out
