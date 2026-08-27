"""Centro de ayuda in-app para todos los niveles de usuario."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QScrollArea,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


HELP_NOVICE = """
<h2>Guia rapida (principiante)</h2>
<p><b>FileSage</b> te ayuda a ver que ocupa espacio y a limpiar archivos duplicados
sin romper nada por accidente.</p>

<h3>1. Empieza por una carpeta pequena</h3>
<ul>
<li>Abre <b>Espacio</b> o <b>Duplicados</b>.</li>
<li>Pulsa <b>Seleccionar carpeta</b> y elige, por ejemplo, Descargas o Documentos.</li>
<li>No empieces por todo el disco C: la primera vez.</li>
</ul>

<h3>2. Analiza el espacio</h3>
<ul>
<li>En <b>Espacio</b> pulsa <b>Analizar</b>.</li>
<li>Veras los archivos mas grandes y que tipos de archivo ocupan mas.</li>
<li>Puedes <b>Exportar</b> el resultado a un archivo para guardarlo.</li>
</ul>

<h3>3. Busca duplicados con seguridad</h3>
<ul>
<li>En <b>Duplicados</b> selecciona la misma carpeta y pulsa <b>Buscar duplicados</b>.</li>
<li>Revisa los grupos (archivos iguales).</li>
<li>Primero usa <b>Simular limpieza (dry-run)</b>: no borra nada, solo te muestra que haria.</li>
<li>Si estas de acuerdo, usa <b>Limpiar (enviar a papelera)</b>. Los archivos van a la papelera del sistema, no se destruyen del todo.</li>
</ul>

<h3>Regla de oro</h3>
<p style="color:#a6e3a1"><b>Siempre simula antes de limpiar.</b> FileSage esta pensado para que no pierdas datos por error.</p>
"""

HELP_ADVANCED = """
<h2>Guia avanzada</h2>

<h3>Pipeline de duplicados</h3>
<ol>
<li>Agrupacion por tamano (descarta unicos al instante).</li>
<li>Hash parcial (primeros 64 KB, xxhash64 por defecto).</li>
<li>Hash completo en paralelo (hasta 8 hilos).</li>
</ol>

<h3>Acciones y transacciones</h3>
<ul>
<li>Cada limpieza o movimiento genera una <b>transaccion</b> (dry-run o real).</li>
<li>Consulta el <b>Historial</b> para ver el detalle.</li>
<li>Rollback automatico solo para <b>MOVE</b>. Lo enviado a papelera se restaura desde el sistema operativo.</li>
</ul>

<h3>CLI util</h3>
<pre>
filesage scan /ruta --top 20
filesage space /ruta
filesage duplicates /ruta --min-size 1048576
filesage export /ruta -k space -f json -o reporte.json
filesage export /ruta -k duplicates -f csv -o dups.csv
filesage gui
</pre>

<h3>Configuracion</h3>
<ul>
<li>Tamano minimo de duplicados, patrones de exclusion, algoritmo de hash.</li>
<li>Dry-run por defecto y uso de papelera se pueden cambiar en Configuracion.</li>
<li>Los cambios de la GUI aplican a la sesion actual.</li>
</ul>

<h3>Arquitectura</h3>
<p>Domain (modelos/interfaces) → Services → Infrastructure → Presentation (CLI + GUI).
Puedes extender sin romper el nucleo.</p>
"""

HELP_FAQ = """
<h2>Preguntas frecuentes</h2>

<p><b>¿Puedo perder archivos?</b><br>
Por defecto no. El modo dry-run esta activo y las limpiezas van a la papelera.
Siempre confirma dos veces en acciones reales.</p>

<p><b>¿Por que no encuentro duplicados?</b><br>
Revisa el tamano minimo en Configuracion (por defecto ignora archivos muy pequenos)
y que no esten en carpetas excluidas (.git, node_modules, etc.).</p>

<p><b>¿Que significa "espacio recuperable"?</b><br>
Es el espacio que liberarias si dejas solo una copia de cada grupo de duplicados.</p>

<p><b>¿Funciona en discos externos?</b><br>
Si. Selecciona la carpeta montada del disco externo igual que una carpeta local.</p>

<p><b>¿La GUI y la CLI hacen lo mismo?</b><br>
Si. Ambas usan el mismo motor (Engine). La GUI es mas visual; la CLI es ideal para scripts.</p>
"""


class HelpPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)

        title = QLabel("Ayuda")
        title.setObjectName("title")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._browser(HELP_NOVICE), "Principiante")
        tabs.addTab(self._browser(HELP_ADVANCED), "Avanzado")
        tabs.addTab(self._browser(HELP_FAQ), "FAQ")
        layout.addWidget(tabs)

    def _browser(self, html: str) -> QWidget:
        w = QTextBrowser()
        w.setOpenExternalLinks(True)
        w.setHtml(html)
        w.setStyleSheet(
            "QTextBrowser { background-color: #1e1e2e; color: #cdd6f4; "
            "border: 1px solid #313244; border-radius: 8px; padding: 12px; }"
        )
        return w
