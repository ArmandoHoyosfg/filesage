# FileSage

Herramienta inteligente, modular y segura para analizar espacio en disco, encontrar duplicados y limpiar archivos **sin riesgos**.

Pensada tanto para **principiantes** (flujos guiados, dry-run, papelera) como para **usuarios avanzados** (CLI, exportes, hashing paralelo, transacciones).

## Inicio rapido (principiante)

```bash
cd filesage
pip install -e .
filesage gui
```

1. Abre **Ayuda** en el menu lateral.
2. Ve a **Espacio** o **Duplicados**.
3. Elige una carpeta pequena (Descargas, Documentos).
4. Usa siempre **Simular (dry-run)** antes de limpiar.
5. Si estas de acuerdo, envia a la **papelera** (recuperable).

## CLI (avanzado)

```bash
filesage scan /ruta --top 20
filesage space /ruta
filesage duplicates /ruta --min-size 1048576
filesage export /ruta -k space -f json -o espacio.json
filesage export /ruta -k duplicates -f csv -o dups.csv
filesage gui
```

## Seguridad por defecto

- Dry-run activado
- Limpieza a la papelera del sistema
- Confirmaciones en acciones reales
- Historial de transacciones
- Rollback basico para movimientos

## Arquitectura

Domain → Services → Infrastructure → Presentation (CLI + GUI)

## Requisitos

Python 3.11+ (ver pyproject.toml)

## Licencia

MIT
