# FileSage

**Versión:** ver archivo [`VERSION`](VERSION)

Herramienta inteligente, modular y segura para analizar espacio en disco, encontrar duplicados, organizar y limpiar archivos **sin riesgos**.

Pensada para principiantes (flujos guiados, dry-run, papelera) y avanzados (CLI, exportaciones, hashing, transacciones).

Licencia: **GPL-3.0-or-later**

---

## Inicio en 10 segundos (Windows)

1. Entra en la carpeta del proyecto.
2. Doble clic en **`FileSage.bat`**.
3. Elige **[1] Abrir FileSage (ventana app)**.

La primera vez puedes usar **[5] Instalar / reparar dependencias**.

> ¿Sin menú?  
> `FileSage.bat web` — abre directo la app.

Documentación del launcher: [`docs/LAUNCHER.md`](docs/LAUNCHER.md)

---

## Otras formas de arrancar

```bash
# Menú interactivo
python scripts/launcher_menu.py

# Directo web (ventana nativa)
python scripts/run_filesage.py --web

# Navegador
python scripts/run_filesage.py --web --browser

# GUI Qt
python scripts/run_filesage.py --gui

# Solo comprobar entorno
python scripts/run_filesage.py --check --web

# Instalar dependencias faltantes
python scripts/run_filesage.py --install --web
```

---

## Tests de integridad

Comprueban rutas, motor, regresión Smart/Buscar y flujos de la UI:

```bash
python scripts/run_integrity.py
# o: FileSage.bat integrity
```

---

## Versión del proyecto

Fuente única: **`VERSION`**.

```bash
python scripts/sync_version.py
```

Sincroniza `pyproject.toml`, `config.py`, `default.yaml` y `__version__`.

---

## Seguridad por defecto

- Dry-run activado
- Limpieza a la papelera del sistema
- Confirmaciones en acciones reales
- Historial de transacciones
- Búsqueda inteligente (no confunde carpetas de la app con el contenido)

---

## Arquitectura

```text
domain → services → infrastructure → core.Engine
                                  ↘ presentation (CLI / Qt / Web)
```

Ver [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Requisitos

- Python **3.11+**
- Opcional web: `pip install "filesage[web]"` (nicegui, pywebview)

---

## CLI (avanzado)

```bash
pip install -e .
filesage scan /ruta --top 20
filesage duplicates /ruta
filesage web
```

---

## Documentación

| Doc | Contenido |
|-----|-----------|
| [docs/LAUNCHER.md](docs/LAUNCHER.md) | Launcher y menú |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Arquitectura |
| [docs/STABILITY.md](docs/STABILITY.md) | Estabilidad |
| [CHANGELOG.md](CHANGELOG.md) | Historial de cambios |
