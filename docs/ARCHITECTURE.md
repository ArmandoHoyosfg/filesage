# Arquitectura FileSage

## Principio

**Ports & Adapters (hexagonal):** el nucleo no conoce la UI.
Cualquier presentacion (Qt, CLI, web) es un adaptador intercambiable.

```
presentation/   →  application/ + core.Engine  →  services/  →  infrastructure/
     UI                    API estable              logica           I/O
```

## Reglas

1. `presentation/` no importa `services/` ni `infrastructure/`.
2. `presentation/` usa `Engine` (implementa `ApplicationAPI`) y tipos de `application.types` / `domain.models`.
3. El dominio no importa PySide6, NiceGUI, FastAPI ni frameworks de UI.
4. Progreso/cancelacion futuros deben entrar por el contrato de aplicacion, no por detalles Qt.

## Modulos clave

| Modulo | Rol |
|--------|-----|
| `domain/` | Modelos e interfaces puras |
| `services/` | Casos de uso (scan, duplicados, smart, acciones) |
| `infrastructure/` | FS, hash, papelera, SQLite |
| `core/engine.py` | Fachada unica hacia presentation |
| `application/api.py` | Protocolo `ApplicationAPI` (contrato) |
| `application/types.py` | DTOs expuestos a la UI |
| `presentation/gui/` | Adaptador Qt (actual) |
| `presentation/cli.py` | Adaptador CLI |
| `presentation/web/` | (futuro) Adaptador web |

## Licencia

GPL-3.0-or-later

## Roadmap hacia UI intercambiable

Ver etapas en el changelog / respuesta del proyecto (Etapa A–F).


## Progreso y cancelacion (Etapas A/B)

- `application/progress.py`: `ProgressReporter`, `CancellationToken`
- `domain.exceptions.CancelledError`
- `Engine.scan/analyze_space/find_duplicates/build_smart_plan(..., progress=...)`
- UI conecta callbacks; el motor no conoce Qt


## Etapa D — Adaptador web

- `presentation/web/` (NiceGUI) habla solo con `Engine`
- Instalacion: `pip install filesage[web]`
- Arranque: `filesage web` → http://127.0.0.1:8080


## Etapa E — Paridad web

Paginas: Dashboard, Espacio, Duplicados (dry-run/papelera), Smart, Buscar, Historial, Config, About.
Todas usan solo `Engine` + `ProgressReporter`.
