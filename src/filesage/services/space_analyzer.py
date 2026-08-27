"""Implementación del analizador de espacio (ISpaceAnalyzer)."""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

from filesage.domain.interfaces import ISpaceAnalyzer
from filesage.domain.models import FileInfo, ScanResult, SpaceNode, SpaceReport

logger = logging.getLogger(__name__)


class SpaceAnalyzer(ISpaceAnalyzer):
    """Construye un informe de uso de espacio a partir de un ScanResult."""

    def analyze(self, scan_result: ScanResult, *, top_n: int = 20) -> SpaceReport:
        """Genera SpaceReport con árbol, top archivos y desglose por extensión."""
        logger.info("Analizando espacio de %s (%d archivos)", scan_result.root, scan_result.total_files)

        # Top N archivos más grandes
        sorted_files = sorted(scan_result.files, key=lambda f: f.size, reverse=True)
        top_files = tuple(sorted_files[:top_n])

        # Desglose por extensión
        by_ext: dict[str, int] = defaultdict(int)
        for fi in scan_result.files:
            ext = fi.extension or "(sin extensión)"
            by_ext[ext] += fi.size

        # Construir árbol de directorios (de forma eficiente)
        tree = self._build_tree(scan_result.root, scan_result.files)

        report = SpaceReport(
            root=scan_result.root,
            total_size=scan_result.total_size,
            total_files=scan_result.total_files,
            tree=tree,
            top_files=top_files,
            by_extension=dict(sorted(by_ext.items(), key=lambda x: x[1], reverse=True)),
        )

        logger.info(
            "Análisis de espacio listo: %.2f MB totales, %d extensiones distintas",
            report.total_size / (1024 * 1024),
            len(report.by_extension),
        )
        return report

    def _build_tree(self, root: Path, files: tuple[FileInfo, ...]) -> SpaceNode:
        """Construye un árbol de SpaceNode a partir de la lista plana de archivos.

        Estrategia:
        - Agrupar archivos por directorio padre.
        - Calcular tamaños de forma bottom-up.
        """
        # Mapa: directorio -> lista de FileInfo que contiene directamente
        dir_files: dict[Path, list[FileInfo]] = defaultdict(list)
        all_dirs: set[Path] = {root}

        for fi in files:
            parent = fi.path.parent
            dir_files[parent].append(fi)

            # Registrar todos los ancestros hasta root
            current = parent
            while current != root and root in current.parents or current == root:
                all_dirs.add(current)
                if current == root:
                    break
                current = current.parent
            all_dirs.add(parent)

        # También añadir root si no está
        all_dirs.add(root)

        # Calcular tamaño y conteo por directorio (solo archivos directos primero)
        dir_size: dict[Path, int] = defaultdict(int)
        dir_count: dict[Path, int] = defaultdict(int)

        for d, fis in dir_files.items():
            for fi in fis:
                dir_size[d] += fi.size
                dir_count[d] += 1

        # Propagar tamaños hacia arriba (de más profundo a más superficial)
        # Ordenamos por profundidad descendente
        sorted_dirs = sorted(all_dirs, key=lambda p: len(p.parts), reverse=True)

        children_map: dict[Path, list[Path]] = defaultdict(list)
        for d in sorted_dirs:
            if d == root:
                continue
            parent = d.parent
            children_map[parent].append(d)
            dir_size[parent] += dir_size[d]
            dir_count[parent] += dir_count[d]

        def build_node(path: Path) -> SpaceNode:
            child_nodes = tuple(
                sorted(
                    (build_node(c) for c in children_map.get(path, [])),
                    key=lambda n: n.size,
                    reverse=True,
                )
            )
            # Añadir también los archivos directos como nodos hoja
            file_nodes = tuple(
                SpaceNode(
                    path=fi.path,
                    size=fi.size,
                    file_count=1,
                    children=(),
                    is_file=True,
                )
                for fi in sorted(dir_files.get(path, []), key=lambda f: f.size, reverse=True)
            )
            return SpaceNode(
                path=path,
                size=dir_size.get(path, 0),
                file_count=dir_count.get(path, 0),
                children=child_nodes + file_nodes,
                is_file=False,
            )

        return build_node(root)
