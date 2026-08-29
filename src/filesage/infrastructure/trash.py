"""Envio seguro a la papelera del sistema (multiplataforma)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from send2trash import send2trash

from filesage.domain.exceptions import ActionError

logger = logging.getLogger(__name__)


def move_to_trash(path: Path) -> None:
    """Envia un archivo o carpeta a la papelera del sistema.

    Raises:
        ActionError: si no se puede completar la operacion.
    """
    path = Path(path)
    if not path.exists():
        raise ActionError(f"No existe: {path}")
    try:
        send2trash(str(path))
        logger.info("Enviado a papelera: %s", path)
    except Exception as exc:
        raise ActionError(f"No se pudo enviar a papelera {path}: {exc}") from exc


def permanent_delete(path: Path) -> None:
    """Elimina permanentemente (usar solo cuando el usuario lo pida explicitamente)."""
    path = Path(path)
    if not path.exists():
        raise ActionError(f"No existe: {path}")
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        logger.info("Eliminado permanentemente: %s", path)
    except Exception as exc:
        raise ActionError(f"No se pudo eliminar {path}: {exc}") from exc


def safe_move(source: Path, destination: Path) -> None:
    """Mueve un archivo/carpeta a otro destino."""
    source = Path(source)
    destination = Path(destination)
    if not source.exists():
        raise ActionError(f"No existe el origen: {source}")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        logger.info("Movido: %s -> %s", source, destination)
    except Exception as exc:
        raise ActionError(f"No se pudo mover {source} -> {destination}: {exc}") from exc


def safe_copy(source: Path, destination: Path) -> None:
    """Copia un archivo o arbol de directorios."""
    source = Path(source)
    destination = Path(destination)
    if not source.exists():
        raise ActionError(f"No existe el origen: {source}")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir() and not source.is_symlink():
            shutil.copytree(str(source), str(destination), dirs_exist_ok=False)
        else:
            shutil.copy2(str(source), str(destination))
        logger.info("Copiado: %s -> %s", source, destination)
    except Exception as exc:
        raise ActionError(f"No se pudo copiar {source} -> {destination}: {exc}") from exc


def empty_system_trash() -> str:
    """Vacia la papelera del sistema. Operacion irreversible a nivel de SO.

    Returns:
        Mensaje de resultado.

    Raises:
        ActionError: si no se puede completar.
    """
    import platform
    import subprocess

    system = platform.system()
    try:
        if system == "Windows":
            # API oficial del shell (sin dependencias extra)
            import ctypes
            from ctypes import wintypes

            SHERB_NOCONFIRMATION = 0x00000001
            SHERB_NOPROGRESSUI = 0x00000002
            SHERB_NOSOUND = 0x00000004
            flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
            hr = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
            if hr not in (0,):  # S_OK; algunos entornos devuelven otros codigos menores
                # 0x80270021 = ya vacia a veces
                if hr & 0xFFFFFFFF not in (0, 0x80270021):
                    raise ActionError(f"SHEmptyRecycleBin fallo (HRESULT={hr})")
            return "Papelera de Windows vaciada"
        if system == "Darwin":
            subprocess.run(
                ["osascript", "-e", 'tell application "Finder" to empty the trash'],
                check=True,
                capture_output=True,
            )
            return "Papelera de macOS vaciada"
        if system == "Linux":
            # freedesktop trash
            trash = Path.home() / ".local/share/Trash"
            files = trash / "files"
            info = trash / "info"
            removed = 0
            for base in (files, info):
                if not base.is_dir():
                    continue
                for child in list(base.iterdir()):
                    try:
                        if child.is_dir() and not child.is_symlink():
                            shutil.rmtree(child)
                        else:
                            child.unlink(missing_ok=True)
                        removed += 1
                    except OSError:
                        continue
            return f"Papelera Linux: {removed} elementos eliminados"
        raise ActionError(f"Vaciar papelera no soportado en {system}")
    except ActionError:
        raise
    except Exception as exc:
        raise ActionError(f"No se pudo vaciar la papelera: {exc}") from exc
