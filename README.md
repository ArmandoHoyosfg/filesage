# FileSage

Herramienta inteligente, modular y segura para analizar espacio en disco, encontrar duplicados y limpiar archivos **sin riesgos**.

Pensada tanto para **principiantes** (flujos guiados, dry-run, papelera) como para **usuarios avanzados** (CLI, exportes, hashing paralelo, transacciones).

## Inicio rapido (launcher, recomendado)

```bash
cd filesage
python scripts/run_filesage.py --install   # deps si faltan
python scripts/run_filesage.py             # GUI Qt
python scripts/run_filesage.py --web       # UI web
```

No hace falta empaquetar para usar la app en desarrollo.

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

GPL-3.0-or-later


## Arquitectura

El nucleo (`domain`, `services`, `infrastructure`, `core.Engine`) es independiente de la UI.
Las interfaces (Qt, CLI, futura web) son adaptadores que solo usan la Application API.

Ver `docs/ARCHITECTURE.md`.


## Interfaz web (Etapa D)

```bash
pip install 'filesage[web]'
filesage web
# o: python -m filesage.presentation.web
```

Abre http://127.0.0.1:8080 — usa el mismo motor que la GUI Qt.
