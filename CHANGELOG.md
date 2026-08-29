# Changelog

Todos los cambios relevantes de FileSage se documentan aqui.
Formato basado en [Keep a Changelog](https://keepachangelog.com/) y [Semantic Versioning](https://semver.org/).

## [0.8.8] - 2026-08-29

### Added
- Diagnostico inteligente de red + causa probable y reparaciones seguras

## [0.8.7] - 2026-08-29

### Fixed
- Icono nativo: usar start_args + WM_SETICON (Windows); nunca icon= en create_window

## [0.8.6] - 2026-08-29

### Fixed
- Arranque nativo: no pasar icon= a pywebview si la version no lo soporta

## [0.8.5] - 2026-08-29

### Improved
- Carpetas vacías: barra de acciones visible (simular / papelera / definitivo)

## [0.8.4] - 2026-08-29

### Added
- Icono propio FileSage (SVG/PNG/ICO) en ventana nativa y favicon web

## [0.8.3] - 2026-08-28

### Added
- Selector inteligente de puerto libre (evita choques con otras apps)
- Preferidos 8765+; fallback automatico; FILESAGE_PORT; --port 0 = auto

## [0.8.2] - 2026-08-28

### Added (Bloque 3)
- Limpieza profunda: carpetas vacias + archivos antiguos
- Dry-run / papelera / borrado definitivo (confirmacion escrita)
- Vaciar papelera del sistema (Windows API / macOS / Linux XDG)
- Pulido visual: hover en cards

## [0.8.1] - 2026-08-28

### Added (Bloque 2)
- Organizar por tipo: plan, dry-run y mover a FileSage_Organizado/
- Engine.build_organize_plan / organize_plan_to_actions
- Herramientas → Organizar por tipo (web)

## [0.8.0] - 2026-08-28

### Added (Bloque 1)
- Aviso de workspace peligroso / perfil completo
- Exclusiones recomendadas (AppData, .git, node_modules…) conmutables en Ajustes
- Un solo job global: botones de accion se deshabilitan mientras hay trabajo

## [0.7.4] - 2026-08-27

### Fixed
- Etiquetas truncadas en convertidor (Formato de salida / Calidad)
- Convertidor: no reconvierte mismo formato (jpg≈jpeg) ni archivos en FileSage_converted

## [0.7.3] - 2026-08-27

### Added
- Aviso al cambiar de seccion con trabajo en curso
- Notificacion al terminar un job (tambien si estabas en otra pagina)
- Persistencia de resultados por seccion (Espacio, Duplicados, Smart, Buscar)

## [0.7.2] - 2026-08-27

### Fixed
- ActionType.COPY implementado (safe_copy)

### Added
- Herramienta Carpetas vacias
- Herramienta Comprimir ZIP
- docs/ANALYSIS.md (bugs, mejoras, roadmap herramientas)

## [0.7.1] - 2026-08-27

### Added
- Directorio de trabajo maestro (persistido en ~/.filesage/workspace.json)
- Boton Examinar… con dialogo nativo de carpeta (WebView)
- Por seccion: usar workspace o carpeta individual

## [0.7.0] - 2026-08-27

### Fixed
- Layout web roto (sidebar/contenido): ahora header + left_drawer nativos NiceGUI

### Added
- Seccion Herramientas + convertidor de imagenes (cualquier formato → PNG/JPG/WEBP/…)
- Carpeta de salida inteligente FileSage_converted

## [0.6.1] - 2026-08-27

### Added
- Web: barra de progreso + Cancelar (Espacio, Duplicados, Smart, Buscar)
- Smart: checkboxes, seleccionar todos / quitar seleccion
- docs/MANUAL_TEST_WEB.md checklist de prueba en PC

## [0.6.0] - 2026-08-27

### Changed
- UI web por defecto en **ventana nativa** (pywebview), estilo app de escritorio
- Shell visual rediseñado: sidebar, tipografia, cards, colores mas premium
- `--browser` en launcher para forzar navegador

## [0.5.2] - 2026-08-27

### Added
- Web: estados vacios y microcopy en todas las paginas
- Web: export JSON/CSV (Espacio y Duplicados) con descarga
- Log por defecto en ~/.filesage/filesage.log
- Tests de paridad web/engine

### Changed
- UI web mas clara y consistente

## [0.5.1] - 2026-08-27

### Changed
- UI Qt/web: tema mas elegante (radios, tipografia, status bar, tooltips)
- Launcher: --gui / --web / --check / --install / --port
- Empaquetado aplazado; docs/STABILITY.md con checklist hacia 1.0

## [0.5.0] - 2026-08-27

### Added
- Etapa E: paridad web — Smart, Buscar, Historial, Config
- Duplicados web: dry-run y limpieza a papelera con confirmacion
- Smart web: generar plan, simular y ejecutar seleccion alta
- Settings web: dry-run, papelera, min size, ocultos

## [0.4.0] - 2026-08-27

### Added
- Etapa D: adaptador web NiceGUI (`presentation/web/`)
- Paginas: Dashboard, Espacio, Duplicados, About
- Extra opcional: `pip install filesage[web]`
- Comandos: `filesage web`, `filesage-web`

## [0.3.2] - 2026-08-27

### Changed
- Etapa C: adaptador Qt estabilizado
- Asistente: progreso %, cancelar escaneo, navegacion corregida
- Barra de estado global en MainWindow
- Errores con detalle (dialogo + etiqueta)
- Plan Smart y paginas Espacio/Duplicados con progreso visible

## [0.3.1] - 2026-08-27

### Added
- ProgressReporter y CancellationToken (contrato de aplicacion)
- Progreso real en scan / duplicados / smart plan
- Cancelacion cooperativa desde UI (Espacio, Duplicados)
- Tests de progreso (25 total)

## [0.3.0] - 2026-08-27

### Changed
- Licencia MIT → GPL-3.0-or-later
- Formalizado contrato ApplicationAPI (application/api.py)
- presentation/ ya no importa services/ ni infrastructure/
- Version 0.3.0

### Added
- docs/ARCHITECTURE.md
- Engine.identify_file, new_action_id, smart_plan_to_actions

## [0.2.0] - 2026-08-27

### Added
- Modo Smart con plan de limpieza (confianza alta/media) y organizacion por tipo de archivo
- Columna "Que es" con tipo MIME y metadatos (Pillow, tinytag, pypdf, puremagic)
- Iconos vectoriales (QtAwesome) y animaciones de transicion
- Pagina Buscar (nombre, extension, metadatos opcionales)
- Seleccionar visibles / quitar seleccion / solo confianza alta en Plan inteligente
- Filtro de texto en el plan Smart
- Configuracion persistente en ~/.filesage/config.yaml
- Lanzador robusto scripts/run_filesage.py

### Changed
- Dashboard responsive (1/2/3 columnas) con scroll
- Tema sidebar con mayor especificidad (evita botones "pegados" en azul)
- Navegacion exclusiva con QButtonGroup
- Version de app 0.2.0

### Fixed
- Solapamiento de tarjetas en el Dashboard
- Estado de botones del menu lateral que permanecian iluminados
- Dependencias deprecadas (PyPDF2/mutagen) sustituidas por pypdf y tinytag

## [0.1.0] - 2026-08-26

### Added
- Fundacion modular, scanner, espacio, duplicados, acciones, GUI base, CLI
