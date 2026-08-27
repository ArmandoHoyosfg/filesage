"""Modelos de dominio puros de FileSage.

Estos modelos no dependen de ninguna infraestructura.
Son inmutables en la medida de lo posible y sirven como contratos de datos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class KeepStrategy(str, Enum):
    NEWEST = "newest"
    OLDEST = "oldest"
    LARGEST = "largest"
    PATH_PRIORITY = "path_priority"


class ActionType(str, Enum):
    MOVE = "move"
    DELETE = "delete"
    COPY = "copy"
    TRASH = "trash"


@dataclass(frozen=True, slots=True)
class FileInfo:
    """Representación inmutable de un archivo descubierto durante el escaneo."""

    path: Path
    size: int
    mtime: float  # timestamp Unix
    is_symlink: bool = False
    hash_partial: str | None = None
    hash_full: str | None = None
    extension: str = field(default="")

    def __post_init__(self) -> None:
        # Asegurar extensión normalizada
        if not self.extension and self.path.suffix:
            object.__setattr__(self, "extension", self.path.suffix.lower())

    @property
    def mtime_dt(self) -> datetime:
        return datetime.fromtimestamp(self.mtime)

    def with_hashes(
        self,
        partial: str | None = None,
        full: str | None = None,
    ) -> FileInfo:
        """Devuelve una nueva instancia con los hashes actualizados."""
        return FileInfo(
            path=self.path,
            size=self.size,
            mtime=self.mtime,
            is_symlink=self.is_symlink,
            hash_partial=partial if partial is not None else self.hash_partial,
            hash_full=full if full is not None else self.hash_full,
            extension=self.extension,
        )


@dataclass(frozen=True, slots=True)
class DuplicateGroup:
    """Grupo de archivos que se consideran duplicados."""

    hash_full: str
    files: tuple[FileInfo, ...]
    total_size: int
    wasted_size: int  # size * (len - 1)

    @property
    def count(self) -> int:
        return len(self.files)


@dataclass(frozen=True, slots=True)
class SpaceNode:
    """Nodo del árbol de uso de espacio."""

    path: Path
    size: int
    file_count: int
    children: tuple[SpaceNode, ...] = field(default_factory=tuple)
    is_file: bool = False


@dataclass(frozen=True, slots=True)
class SpaceReport:
    """Informe completo de uso de espacio."""

    root: Path
    total_size: int
    total_files: int
    tree: SpaceNode
    top_files: tuple[FileInfo, ...]
    by_extension: dict[str, int]  # extensión -> bytes


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Resultado de un escaneo completo."""

    root: Path
    files: tuple[FileInfo, ...]
    total_size: int
    total_files: int
    errors: tuple[str, ...] = field(default_factory=tuple)
    duration_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class ActionRecord:
    """Registro de una acción realizada (para log y rollback)."""

    action_id: str
    action_type: ActionType
    source: Path
    destination: Path | None
    timestamp: datetime
    success: bool
    message: str = ""
    dry_run: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Transaction:
    """Conjunto de acciones agrupadas (permite rollback atómico a nivel lógico)."""

    transaction_id: str
    started_at: datetime
    finished_at: datetime | None
    actions: tuple[ActionRecord, ...]
    dry_run: bool = True
    notes: str = ""
