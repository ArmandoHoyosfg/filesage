"""Interfaces (contratos) del dominio.

Toda la lógica de negocio y la presentación dependen únicamente de estas interfaces.
Las implementaciones concretas viven en infrastructure/ o services/.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Sequence

from filesage.domain.models import (
    ActionRecord,
    DuplicateGroup,
    FileInfo,
    ScanResult,
    SpaceReport,
    Transaction,
)


class IScanner(ABC):
    """Contrato para el descubrimiento de archivos."""

    @abstractmethod
    def scan(self, root: Path) -> ScanResult:
        """Recorre el árbol de directorios y devuelve un ScanResult."""
        ...


class IHasher(ABC):
    """Contrato para el cálculo de hashes."""

    @abstractmethod
    def partial_hash(self, path: Path) -> str:
        """Hash rápido de una porción del archivo (primeros N KB)."""
        ...

    @abstractmethod
    def full_hash(self, path: Path) -> str:
        """Hash completo del archivo."""
        ...


class IDuplicateFinder(ABC):
    """Contrato para la detección de duplicados."""

    @abstractmethod
    def find(self, files: Sequence[FileInfo]) -> list[DuplicateGroup]:
        """Recibe una lista de FileInfo y devuelve grupos de duplicados."""
        ...


class ISpaceAnalyzer(ABC):
    """Contrato para el análisis de uso de espacio."""

    @abstractmethod
    def analyze(self, scan_result: ScanResult) -> SpaceReport:
        """Genera un informe de espacio a partir de un ScanResult."""
        ...


class IActionExecutor(ABC):
    """Contrato para ejecutar acciones de forma segura (mover, borrar, etc.)."""

    @abstractmethod
    def execute(
        self,
        actions: Sequence[ActionRecord],
        *,
        dry_run: bool = True,
    ) -> Transaction:
        """Ejecuta (o simula) una lista de acciones y devuelve la transacción."""
        ...

    @abstractmethod
    def rollback(self, transaction: Transaction) -> Transaction:
        """Intenta revertir una transacción previa."""
        ...


class IStorage(ABC):
    """Contrato para persistencia (índice, transacciones, etc.)."""

    @abstractmethod
    def save_scan(self, result: ScanResult) -> None:
        ...

    @abstractmethod
    def load_scan(self, root: Path) -> ScanResult | None:
        ...

    @abstractmethod
    def save_transaction(self, transaction: Transaction) -> None:
        ...

    @abstractmethod
    def list_transactions(self, limit: int = 50) -> list[Transaction]:
        ...
