"""Exportacion de reportes (JSON / CSV)."""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from filesage.domain.models import DuplicateGroup, ScanResult, SpaceReport

logger = logging.getLogger(__name__)


def export_space_report(report: SpaceReport, scan: ScanResult, dest: Path, fmt: str = "json") -> Path:
    dest = Path(dest)
    data = {
        "generated_at": datetime.now().isoformat(),
        "root": str(report.root),
        "total_files": report.total_files,
        "total_size": report.total_size,
        "duration_seconds": scan.duration_seconds,
        "top_files": [
            {"path": str(f.path), "size": f.size, "mtime": f.mtime}
            for f in report.top_files
        ],
        "by_extension": report.by_extension,
    }
    if fmt == "csv":
        # CSV de top files
        with dest.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["rank", "size_bytes", "path"])
            for i, fi in enumerate(report.top_files, 1):
                w.writerow([i, fi.size, str(fi.path)])
    else:
        dest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Reporte de espacio exportado: %s", dest)
    return dest


def export_duplicates_report(groups: list[DuplicateGroup], root: Path, dest: Path, fmt: str = "json") -> Path:
    dest = Path(dest)
    if fmt == "csv":
        with dest.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["group", "hash", "path", "size", "mtime", "wasted_in_group"])
            for i, g in enumerate(groups, 1):
                for fi in g.files:
                    w.writerow([i, g.hash_full, str(fi.path), fi.size, fi.mtime, g.wasted_size])
    else:
        data: dict[str, Any] = {
            "generated_at": datetime.now().isoformat(),
            "root": str(root),
            "groups_count": len(groups),
            "total_wasted": sum(g.wasted_size for g in groups),
            "groups": [
                {
                    "hash": g.hash_full,
                    "count": g.count,
                    "total_size": g.total_size,
                    "wasted_size": g.wasted_size,
                    "files": [
                        {"path": str(f.path), "size": f.size, "mtime": f.mtime}
                        for f in g.files
                    ],
                }
                for g in groups
            ],
        }
        dest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Reporte de duplicados exportado: %s", dest)
    return dest
