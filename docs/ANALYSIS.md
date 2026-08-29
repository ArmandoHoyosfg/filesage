# Analisis de bugs, mejoras y herramientas (v0.7.2)

## Bugs / huecos encontrados y estado

| Item | Severidad | Estado |
|------|-----------|--------|
| Layout web (sidebar abajo) | Alta | Corregido (drawer nativo) |
| COPY no implementado | Media | **Corregido** (safe_copy) |
| Sin selector de carpetas | Alta | Corregido (workspace + Examinar) |
| `except: pass` en UI/identidad | Baja | Aceptable (degradacion graceful) |
| Cancelacion prematura en UI | Media | Revisar uso; token nuevo por job |
| Escaneo home completo lento | Media | Esperado; usar workspace acotado |
| Qt vs Web paridad visual | Media | Web mejorada; Qt sigue valida |

## Mejoras recomendadas (prioridad)

1. **No escanear C:\Users\... entero por defecto** — workspace en Downloads/Documentos.
2. **Barra global de job** (una sola a la vez) para evitar dobles clics.
3. **Organizar por tipo ejecutable** (hoy solo sugerencias MEDIUM en Smart).
4. **Batch rename** con vista previa (dry-run).
5. **Excluir rutas del sistema** mas agresivo en Windows (`AppData`, etc. opcional).
6. **Tests de UI** smoke (Playwright opcional) — no bloqueante.

## Herramientas extra alineadas al proposito

### Ya en FileSage
- Espacio, Duplicados, Smart, Buscar, Convertir imagenes
- **Carpetas vacias** (nuevo)
- **ZIP de carpeta** (nuevo)
- Historial + dry-run + papelera

### Candidatas siguientes (encajan bien)
| Herramienta | Valor | Complejidad |
|-------------|-------|-------------|
| Organizar por tipo (mover real con dry-run) | Alto | Media |
| Renombrado por lotes + vista previa | Alto | Media |
| Limpiar nombres invalidos / caracteres raros | Medio | Baja |
| Hash / verificar integridad de archivo | Medio | Baja |
| Redimensionar imagenes (max width) | Medio | Baja (Pillow) |
| Extraer ZIP | Medio | Baja |
| Encontrar archivos antiguos (>N dias) | Alto | Baja |
| Duplicados “parecidos” (nombre) | Medio | Media |
| Reglas tipo FolderFresh | Alto | Alta |

## Buenas practicas que ya seguimos
- Dry-run por defecto
- Papelera antes que borrado duro
- Motor separado de la UI
- Progress + cancelacion cooperativa
