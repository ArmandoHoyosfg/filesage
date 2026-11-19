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



# --- Windows system signals ---

def _run_powershell(script: str, timeout: float = 25.0) -> tuple[int, str, str]:
    import subprocess

    try:
        r = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "CREATE_NO_WINDOW")
            else 0,
        )
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", "powershell no encontrado"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as exc:
        return 1, "", str(exc)


def _drive_letter(path: Path) -> str | None:
    s = str(path)
    if len(s) >= 2 and s[1] == ":":
        return s[0].upper()
    try:
        anchor = path.resolve().anchor  # e.g. 'F:\\'
        if anchor and ":" in anchor:
            return anchor[0].upper()
    except Exception:
        pass
    return None


def windows_system_disk_signals(path: Path) -> list[DiskFinding]:
    """Consulta Windows por salud de disco, eventos de error y prediccion SMART."""
    findings: list[DiskFinding] = []
    if platform.system() != "Windows":
        return findings

    letter = _drive_letter(path)
    findings.append(
        DiskFinding(
            "info",
            "Capa Windows",
            "Se consultan PhysicalDisk, volumen y eventos recientes del sistema "
            "(disk/NTFS). Si tambien fallas al copiar a mano, el fallo suele ser "
            "del hardware, cable, puerto USB o sistema de archivos.",
        )
    )

    # Volumen
    if letter:
        code, out, err = _run_powershell(
            f"Get-Volume -DriveLetter {letter} | "
            "Select-Object DriveLetter, FileSystem, HealthStatus, OperationalStatus, "
            "Size, SizeRemaining | Format-List | Out-String"
        )
        if code == 0 and out:
            low = out.lower()
            level = "ok"
            if "unhealthy" in low or "error" in low:
                level = "error"
            elif "warning" in low or "degraded" in low:
                level = "warn"
            findings.append(
                DiskFinding(
                    level,
                    f"Volumen {letter}:",
                    out[:800] if len(out) > 20 else (out or err or "sin datos"),
                )
            )
        elif err and "access" not in err.lower():
            findings.append(
                DiskFinding(
                    "info",
                    "Volumen",
                    f"No se pudo consultar Get-Volume ({err[:200]}). "
                    "Prueba ejecutar FileSage como usuario normal; algunos datos "
                    "requieren permisos elevados.",
                )
            )

    # Discos fisicos (salud global)
    code, out, err = _run_powershell(
        "Get-PhysicalDisk | Select-Object FriendlyName, MediaType, BusType, "
        "HealthStatus, OperationalStatus, Size | Format-Table -AutoSize | Out-String"
    )
    if code == 0 and out and "HealthStatus" in out:
        low = out.lower()
        level = "ok"
        if "unhealthy" in low:
            level = "error"
        elif "warning" in low:
            level = "warn"
        findings.append(
            DiskFinding(
                level,
                "Discos fisicos (HealthStatus)",
                out[:1200],
            )
        )
    else:
        findings.append(
            DiskFinding(
                "info",
                "PhysicalDisk",
                "Get-PhysicalDisk no disponible o sin permisos. "
                f"{(err or out)[:200]}",
            )
        )

    # SMART / prediccion de fallo (si el controlador lo expone)
    code, out, err = _run_powershell(
        "Get-CimInstance -Namespace root/wmi -ClassName MSStorageDriver_FailurePredictStatus "
        "-ErrorAction SilentlyContinue | "
        "Select-Object InstanceName, PredictFailure, Reason | Format-List | Out-String"
    )
    if code == 0 and out and "PredictFailure" in out:
        if "True" in out or "true" in out:
            findings.append(
                DiskFinding(
                    "error",
                    "SMART: prediccion de fallo",
                    "Windows reporta PredictFailure=True en al menos un disco. "
                    "Haz copia de seguridad ya y sustituye el disco. Detalle:\n"
                    + out[:800],
                )
            )
        else:
            findings.append(
                DiskFinding(
                    "ok",
                    "SMART (prediccion)",
                    "No hay prediccion de fallo activa en los discos que responden a WMI.",
                )
            )

    # Contadores de fiabilidad (errores de lectura/escritura) si existen
    code, out, err = _run_powershell(
        "Get-PhysicalDisk | ForEach-Object { "
        "  $c = $_ | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue; "
        "  if ($c) { [PSCustomObject]@{ Name=$_.FriendlyName; "
        "    ReadErrors=$c.ReadErrorsTotal; WriteErrors=$c.WriteErrorsTotal; "
        "    Temp=$c.Temperature } } "
        "} | Format-Table -AutoSize | Out-String"
    )
    if code == 0 and out and ("ReadErrors" in out or "Name" in out):
        level = "ok"
        # naive parse for non-zero errors
        for line in out.splitlines():
            parts = line.split()
            nums = [p for p in parts if p.isdigit()]
            if any(int(n) > 0 for n in nums[:2] if n.isdigit()):
                # could be false positive from Name numbers; soft warn if "error" word
                pass
        if any(
            tok.isdigit() and int(tok) > 0
            for tok in out.replace("ReadErrors", " ").split()
            if tok.isdigit() and int(tok) > 5
        ):
            level = "warn"
        findings.append(
            DiskFinding(
                level,
                "Contadores de fiabilidad",
                out[:900]
                if out.strip()
                else "Sin contadores (comun en algunos USB).",
            )
        )

    # Eventos recientes del sistema: disk / NTFS (IDs criticos)
    # 7, 11, 51 disk; 55, 50, 98, 140 NTFS; 129, 153, 157 storage
    code, out, err = _run_powershell(
        "$ids = 7,11,51,50,55,98,129,140,153,157; "
        "try { "
        "  Get-WinEvent -FilterHashtable @{LogName='System'; Id=$ids} "
        "    -MaxEvents 15 -ErrorAction Stop | "
        "  ForEach-Object { "
        "    '{0:yyyy-MM-dd HH:mm} ID={1} {2}' -f $_.TimeCreated, $_.Id, "
        "    ($_.Message -replace '\\s+',' ').Substring(0, [Math]::Min(160, $_.Message.Length)) "
        "  } "
        "} catch { 'SIN_EVENTOS_O_SIN_PERMISO: ' + $_.Exception.Message }"
    )
    if code == 0 and out:
        if "SIN_EVENTOS" in out and "No events" in out.lower():
            findings.append(
                DiskFinding(
                    "ok",
                    "Registro de eventos (disco/NTFS)",
                    "No se encontraron eventos criticos recientes (o no hay acceso al log).",
                )
            )
        elif out.strip().startswith("SIN_EVENTOS"):
            findings.append(
                DiskFinding(
                    "info",
                    "Registro de eventos",
                    out[:400]
                    + " Si puedes, ejecuta el diagnostico de nuevo o revisa "
                    "Visor de eventos → Sistema.",
                )
            )
        else:
            lines = [ln for ln in out.splitlines() if ln.strip()]
            level = "warn"
            if any(
                f"ID={x}" in out
                for x in ("55", "98", "153", "157", "11", "7", "51")
            ):
                level = "error"
            findings.append(
                DiskFinding(
                    level,
                    f"Eventos de disco/NTFS recientes ({len(lines)})",
                    "Estos eventos confirman problemas a nivel Windows "
                    "(coinciden con fallos al copiar a mano):\n"
                    + "\n".join(lines[:12]),
                )
            )
    else:
        findings.append(
            DiskFinding(
                "info",
                "Registro de eventos",
                "No se pudo leer el log del sistema. "
                f"{(err or '')[:200]}",
            )
        )

    # Consejo practico USB
    findings.append(
        DiskFinding(
            "info",
            "Si fallas tambien al copiar a mano",
            "1) Prueba otro puerto USB (trasero en PC de torre).\n"
            "2) Otro cable / hub sin alimentacion.\n"
            "3) Como administrador: chkdsk X: /f  (sustituye X por la letra).\n"
            "4) En Administrador de dispositivos, desactiva "
            "«Permitir que el equipo apague este dispositivo» en el USB raíz.\n"
            "5) Si hay eventos 153/157 o SMART PredictFailure: deja de confiar "
            "en ese disco y recupera lo que puedas por carpetas pequeñas.",
        )
    )
    return findings


def diagnose_path(
    path: str | Path,
    *,
    sample_limit: int = 40,
    max_seconds: float = 12.0,
    include_windows: bool = True,
) -> DiskReport:
    """Comprueba acceso, espacio, lectura y (en Windows) señales del sistema."""
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
        if include_windows and platform.system() == "Windows":
            report.findings.extend(windows_system_disk_signals(raw))
        return report

    root = _root_of(raw)
    report.findings.append(
        DiskFinding("info", "Volumen", f"Raíz detectada: {root}")
    )

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
        if include_windows and platform.system() == "Windows":
            report.findings.extend(windows_system_disk_signals(raw))
        return report

    sample = entries[:sample_limit]
    report.sample_files = len(sample)
    bytes_read = 0
    t1 = time.time()
    for f in sample:
        if time.time() - t1 > max_seconds:
            break
        try:
            with open(f, "rb") as fh:
                chunk = fh.read(1024 * 256)
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

    if include_windows and platform.system() == "Windows":
        report.findings.extend(windows_system_disk_signals(raw))
    elif platform.system() != "Windows":
        report.findings.append(
            DiskFinding(
                "info",
                "Sistema",
                "Comprobaciones avanzadas de Event Log / SMART solo en Windows.",
            )
        )

    return report
