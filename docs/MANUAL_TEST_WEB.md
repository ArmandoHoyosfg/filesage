# Prueba manual en tu PC (UI web nativa)

## Arranque

```bash
cd filesage
python scripts/run_filesage.py --install --web
python scripts/run_filesage.py --web
```

Debe abrirse una **ventana de app** (no el navegador). Si falla WebView2:

```bash
python scripts/run_filesage.py --web --browser
```

## Checklist

### Progreso y cancelacion
1. **Espacio** → carpeta grande (Descargas) → Analizar  
   - [ ] Se ve barra de progreso / %  
   - [ ] **Cancelar** detiene y muestra “cancelado”
2. **Duplicados** → misma carpeta → Buscar → Cancelar a mitad  
   - [ ] No modifica archivos
3. **Smart** → Generar plan → Cancelar si tarda  
4. **Buscar** → criterio + carpeta grande → Cancelar  

### Checkboxes Smart
1. Generar plan en carpeta con algo de basura/duplicados  
2. [ ] Items alta confianza vienen marcados  
3. **Quitar seleccion** → Simular → debe avisar “selecciona al menos uno”  
4. Marcar 1–2 → **Simular** → dry-run OK  
5. (Opcional) Ejecutar papelera solo si aceptas el riesgo  

### Visual / ventana
- [ ] Sidebar y titulo se ven bien  
- [ ] Redimensionar ventana no rompe layout  
- [ ] Cards del inicio navegan bien  

## Si algo falla

Copia:
1. Captura de pantalla  
2. Texto de `~/.filesage/filesage.log` (ultimas lineas)  
3. Pasos exactos  

Y reportalo para corregirlo.
