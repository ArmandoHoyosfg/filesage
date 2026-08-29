# Hacia una version estable (sin empaquetar)

Empaquetado **aplazado** a proposito. El flujo oficial de desarrollo/uso es el launcher:

```bash
python scripts/run_filesage.py           # Qt
python scripts/run_filesage.py --web     # NiceGUI
python scripts/run_filesage.py --check
python scripts/run_filesage.py --install
```

## Criterios de “estable” (checklist)

### Ya cubierto
- [x] Arquitectura hexagonal (Engine / ApplicationAPI)
- [x] Dry-run por defecto + papelera
- [x] Progreso y cancelacion cooperativa
- [x] Qt pulido (tema, sidebar, asistente, barras)
- [x] Web con paridad funcional basica (E)
- [x] Tests de nucleo (25+)
- [x] Licencia GPL-3.0-or-later
- [x] Launcher con verificacion de deps

### Pendiente recomendado (antes de empaquetar)
1. **Pruebas manuales en Windows** (ruta del usuario actual) con carpetas reales grandes.
2. **Estados vacios** uniformes (“elige una carpeta”, “sin resultados”) en todas las paginas.
3. **Export** accesible tambien en web.
4. **COPY** en ActionManager (o documentarlo como no soportado).
5. **Mas tests de integracion** (smart plan + execute dry-run, settings persist).
6. **Telemetria de errores local** (log file legible en `~/.filesage/`).
7. **A11y**: foco de teclado y contraste revisados en pantallas densas.
8. **Rendimiento**: carpetas 100k+ archivos — muestrear progreso y no congelar UI.
9. **Documentacion de usuario** corta (1 pagina) en Ayuda Qt + About web.
10. Version **1.0.0** solo cuando 1–9 esten cerrados en al menos Windows + un Linux.

## UI: lineas guia

- Acento unico: `#89b4fa`
- Fondos: `#11111b` / `#1e1e2e` / `#313244`
- Texto: `#cdd6f4` (no blanco puro)
- Radios 10–16px, padding generoso
- Un CTA primario por vista; peligro solo en acciones irreversibles

## No hacer ahora

- PyInstaller / Nuitka / instaladores
- Electron
- Reescribir el motor al cambiar de UI
