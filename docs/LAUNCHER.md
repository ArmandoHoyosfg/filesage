# Launcher FileSage

Punto de entrada único para usuarios y desarrollo **sin empaquetar**.

## Uso recomendado (Windows)

Doble clic en:

```text
FileSage.bat
```

Se abre un menú:

| Opción | Acción |
|--------|--------|
| 1 | App en ventana nativa (NiceGUI + WebView) |
| 2 | App en el navegador |
| 3 | GUI Qt clásica |
| 4 | Verificar entorno |
| 5 | Instalar / reparar dependencias |
| 6 | Tests de integridad |
| 7 | Sincronizar versión desde `VERSION` |
| 0 | Salir |

### Atajos desde consola

```bat
FileSage.bat web
FileSage.bat browser
FileSage.bat gui
FileSage.bat check
FileSage.bat install
FileSage.bat integrity
```

PowerShell:

```powershell
.\FileSage.ps1
.\FileSage.ps1 web
```

## Requisitos

- Python **3.11+**
- En Windows: preferir el launcher `py -3` (evita el stub de Microsoft Store)

## Versiones

Fuente de verdad: archivo `VERSION` en la raíz.

```bash
python scripts/sync_version.py
```

Actualiza:

- `pyproject.toml`
- `src/filesage/core/config.py`
- `config/default.yaml`
- `src/filesage/__init__.py` (`__version__`)

## Integridad

```bash
python scripts/run_integrity.py
# o desde el menú: opción 6
```

## Buenas prácticas aplicadas

1. **Un solo doble clic** — no hace falta recordar comandos.
2. **Detección de intérprete** — `py -3` → `python` → `python3`.
3. **Comprobación previa** — Python, estructura del proyecto, dependencias.
4. **Instalación guiada** — opción de reparar deps con pip.
5. **Mensajes claros** y pausa si hay error (la ventana no se cierra sola).
6. **Versión visible** y sincronizada.
7. **Sin empaquetado obligatorio** hasta que la app esté estable.
