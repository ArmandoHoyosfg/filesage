"""Diagnostico rapido de discos / unidades extraibles."""

from __future__ import annotations

import os
import platform
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DiskFinding:
    level: str  # ok | warn | error | info
    title: str
    detail: str


@dataclass
class DiskReport:
    path: str
    findings: list[DiskFinding] = field(default_factory=list)
    read_mbs: float | None = None
    sample_files: int = 0
    sample_errors: int = 0
    free_gb: float | None = None
    total_gb: float | None = None

    @property
    def summary(self) -> str:
        errs = sum(1 for f in self.findings if f.level == "error")
        warns = sum(1 for f in self.findings if f.level == "warn")
        if errs:
            return f"Problemas graves: {errs} (revisa el disco antes de copiar mucho)"
        if warns:
            return f"Avisos: {warns} — puede ir lento o fallar en algunos archivos"
        return "Diagnostico basico sin errores evidentes"


def _root_of(path: Path) -> Path:
    path = Path(path)
    try:
        path = path.resolve()
    except Exception:
        pass
    if path.exists() and path.is_file():
        path = path.parent
    # Windows drive root
    parts = path.parts
    if len(parts) >= 1 and len(parts[0]) == 3 and parts[0][1] == ":":
        return Path(parts[0] + "\\") if not parts[0].endswith("\\") else Path(parts[0])
    if hasattr(path, "anchor") and path.anchor:
        return Path(path.anchor)
    return path


def diagnose_path(
    path: str | Path,
    *,
    sample_limit: int = 40,
    max_seconds: float = 12.0,
) -> DiskReport:
    """Comprueba acceso, espacio y lectura de una muestra de archivos."""
    raw = Path(str(path).strip().strip('"'))
    if len(str(raw)) == 2 and str(raw)[1] == ":":
        raw = Path(str(raw) + "\\")
    report = DiskReport(path=str(raw))

    if not raw.exists():
        report.findings.append(
            DiskFinding(
                "error",
                "Ruta inaccesible",
                f"No existe o no se puede ver: {raw}. ¿Unidad desconectada o letra cambiada?",
            )
        )
        return report

    root = _root_of(raw)
    report.findings.append(
        DiskFinding("info", "Volumen", f"Raíz detectada: {root}")
    )

    # Espacio
    try:
        usage = shutil.disk_usage(str(raw if raw.is_dir() else raw.parent))
        report.total_gb = usage.total / (1024**3)
        report.free_gb = usage.free / (1024**3)
        report.findings.append(
            DiskFinding(
                "ok" if usage.free > 500 * 1024**2 else "warn",
                "Espacio libre",
                f"{report.free_gb:.1f} GB libres de {report.total_gb:.1f} GB",
            )
        )
    except OSError as exc:
        report.findings.append(
            DiskFinding("error", "No se pudo leer espacio", str(exc))
        )

    # Listado
    t0 = time.time()
    entries: list[Path] = []
    try:
        base = raw if raw.is_dir() else raw.parent
        for dirpath, dirnames, filenames in os.walk(base):
            for name in filenames:
                entries.append(Path(dirpath) / name)
                if len(entries) >= sample_limit * 3:
                    dirnames.clear()
                    break
            if time.time() - t0 > max_seconds * 0.4:
                break
        list_ms = (time.time() - t0) * 1000
        report.findings.append(
            DiskFinding(
                "ok" if list_ms < 3000 else "warn",
                "Velocidad de listado",
                f"{len(entries)} entradas en muestra · listado ~{list_ms:.0f} ms",
            )
        )
    except OSError as exc:
        report.findings.append(
            DiskFinding(
                "error",
                "Error al listar",
                f"{exc}. Tipico en USB dañados o con sistema de archivos corrupto.",
            )
        )
        return report

    # Lectura de muestra
    sample = entries[:sample_limit]
    report.sample_files = len(sample)
    bytes_read = 0
    t1 = time.time()
    for f in sample:
        if time.time() - t1 > max_seconds:
            break
        try:
            with open(f, "rb") as fh:
                chunk = fh.read(1024 * 256)  # 256 KB
                bytes_read += len(chunk)
        except OSError as exc:
            report.sample_errors += 1
            if report.sample_errors <= 3:
                report.findings.append(
                    DiskFinding(
                        "error",
                        "Fallo de lectura",
                        f"{f.name}: {exc}",
                    )
                )

    elapsed = max(0.001, time.time() - t1)
    report.read_mbs = (bytes_read / (1024 * 1024)) / elapsed
    if report.sample_errors:
        report.findings.append(
            DiskFinding(
                "error",
                f"{report.sample_errors} archivos no legibles",
                "En un extraible suele indicar sectores danados. Evita copias masivas; "
                "copia por carpetas y revisa el disco (chkdsk / herramientas del fabricante).",
            )
        )
    else:
        level = "ok"
        if report.read_mbs is not None and report.read_mbs < 5:
            level = "warn"
        report.findings.append(
            DiskFinding(
                level,
                "Lectura de muestra",
                f"~{report.read_mbs:.1f} MB/s sobre {report.sample_files} archivos. "
                + (
                    "Muy lento para USB 3; posible USB 2, sobrecarga o disco fallando."
                    if level == "warn"
                    else "Lectura aceptable en la muestra."
                ),
            )
        )

    if platform.system() == "Windows":
        report.findings.append(
            DiskFinding(
                "info",
                "Consejo Windows",
                "Si hay errores de lectura: como administrador, "
                f"chkdsk {root} /f  (puede pedir desmontar la unidad). "
                "No interrumpas copias grandes en USB inestables.",
            )
        )

    return report
