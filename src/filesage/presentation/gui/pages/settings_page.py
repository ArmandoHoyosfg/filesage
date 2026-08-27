"""Pagina de Configuracion de FileSage (persistente)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from filesage.core.config import Settings, get_user_config_path, save_settings
from filesage.core.engine import Engine


class SettingsPage(QWidget):
    def __init__(self, settings: Settings, engine: Engine, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.engine = engine

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel("Configuracion")
        title.setObjectName("title")
        layout.addWidget(title)

        self.path_hint = QLabel(f"Se guarda en: {get_user_config_path()}")
        self.path_hint.setObjectName("subtitle")
        layout.addWidget(self.path_hint)

        # --- Seguridad ---
        g_sec = QGroupBox("Seguridad")
        f_sec = QFormLayout(g_sec)
        self.chk_dry = QCheckBox("Dry-run por defecto")
        self.chk_dry.setChecked(settings.app.dry_run_default)
        self.chk_dry.setToolTip("Si esta activo, las acciones se simulan salvo que confirmes lo contrario")
        f_sec.addRow(self.chk_dry)
        self.chk_trash = QCheckBox("Usar papelera del sistema")
        self.chk_trash.setChecked(settings.actions.use_trash)
        f_sec.addRow(self.chk_trash)
        self.chk_log = QCheckBox("Registrar transacciones")
        self.chk_log.setChecked(settings.actions.transaction_log)
        f_sec.addRow(self.chk_log)
        layout.addWidget(g_sec)

        # --- Escaneo ---
        g_scan = QGroupBox("Escaneo")
        f_scan = QFormLayout(g_scan)
        self.chk_hidden = QCheckBox("Ignorar archivos/carpetas ocultos")
        self.chk_hidden.setChecked(settings.scan.ignore_hidden)
        f_scan.addRow(self.chk_hidden)
        self.spin_min = QSpinBox()
        self.spin_min.setRange(0, 100_000_000)
        self.spin_min.setValue(settings.duplicates.min_size_bytes)
        self.spin_min.setSuffix(" bytes")
        self.spin_min.setToolTip("Archivos mas pequenos se ignoran al buscar duplicados")
        f_scan.addRow("Tamano minimo duplicados:", self.spin_min)
        self.edit_exclude = QTextEdit()
        self.edit_exclude.setPlainText("\n".join(settings.scan.exclude_patterns))
        self.edit_exclude.setMaximumHeight(100)
        f_scan.addRow("Patrones de exclusion (uno por linea):", self.edit_exclude)
        layout.addWidget(g_scan)

        # --- Hashing ---
        g_hash = QGroupBox("Hashing")
        f_hash = QFormLayout(g_hash)
        self.edit_algo = QLineEdit(settings.hashing.algorithm)
        f_hash.addRow("Algoritmo:", self.edit_algo)
        self.spin_partial = QSpinBox()
        self.spin_partial.setRange(4, 1024)
        self.spin_partial.setValue(settings.hashing.partial_size_kb)
        self.spin_partial.setSuffix(" KB")
        f_hash.addRow("Tamano hash parcial:", self.spin_partial)
        layout.addWidget(g_hash)

        # Botones
        btns = QHBoxLayout()
        self.btn_apply = QPushButton("Guardar y aplicar")
        self.btn_apply.setToolTip("Aplica los cambios y los guarda en disco para la proxima vez")
        self.btn_apply.clicked.connect(self._apply_and_save)
        btns.addWidget(self.btn_apply)

        self.btn_apply_session = QPushButton("Solo esta sesion")
        self.btn_apply_session.setObjectName("secondary")
        self.btn_apply_session.setToolTip("Aplica sin escribir el archivo de configuracion")
        self.btn_apply_session.clicked.connect(self._apply_session_only)
        btns.addWidget(self.btn_apply_session)

        self.btn_reset = QPushButton("Recargar desde disco")
        self.btn_reset.setObjectName("secondary")
        self.btn_reset.clicked.connect(self._reload_from_disk)
        btns.addWidget(self.btn_reset)
        btns.addStretch()
        layout.addLayout(btns)

        layout.addStretch()
        self.status = QLabel("")
        self.status.setObjectName("subtitle")
        layout.addWidget(self.status)

    def _read_form_into_settings(self) -> None:
        s = self.settings
        s.app.dry_run_default = self.chk_dry.isChecked()
        s.actions.use_trash = self.chk_trash.isChecked()
        s.actions.transaction_log = self.chk_log.isChecked()
        s.scan.ignore_hidden = self.chk_hidden.isChecked()
        s.duplicates.min_size_bytes = self.spin_min.value()
        patterns = [p.strip() for p in self.edit_exclude.toPlainText().splitlines() if p.strip()]
        s.scan.exclude_patterns = patterns
        s.hashing.algorithm = self.edit_algo.text().strip() or "xxhash64"
        s.hashing.partial_size_kb = self.spin_partial.value()
        self.engine.action_manager._use_trash = s.actions.use_trash

    def _apply_and_save(self) -> None:
        self._read_form_into_settings()
        try:
            path = save_settings(self.settings)
            self.status.setText(f"Guardado en {path}")
            QMessageBox.information(
                self,
                "Configuracion",
                f"Cambios aplicados y guardados.\n\nArchivo:\n{path}\n\n"
                "Se usaran automaticamente la proxima vez que abras FileSage.",
            )
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar", str(e))
            self.status.setText(f"Error: {e}")

    def _apply_session_only(self) -> None:
        self._read_form_into_settings()
        self.status.setText("Aplicado solo para esta sesion (no se escribio el archivo).")
        QMessageBox.information(self, "Configuracion", "Cambios aplicados solo para esta sesion.")

    def _reload_from_disk(self) -> None:
        from filesage.core.config import load_settings

        path = get_user_config_path()
        if not path.exists():
            QMessageBox.information(
                self,
                "Recargar",
                f"Aun no hay archivo de usuario en:\n{path}\n\nSe mantienen los valores actuales.",
            )
            return
        loaded = load_settings(path)
        # Copiar valores al objeto settings compartido
        self.settings.app.dry_run_default = loaded.app.dry_run_default
        self.settings.actions.use_trash = loaded.actions.use_trash
        self.settings.actions.transaction_log = loaded.actions.transaction_log
        self.settings.scan.ignore_hidden = loaded.scan.ignore_hidden
        self.settings.scan.exclude_patterns = list(loaded.scan.exclude_patterns)
        self.settings.duplicates.min_size_bytes = loaded.duplicates.min_size_bytes
        self.settings.hashing.algorithm = loaded.hashing.algorithm
        self.settings.hashing.partial_size_kb = loaded.hashing.partial_size_kb
        self.engine.action_manager._use_trash = self.settings.actions.use_trash

        self.chk_dry.setChecked(self.settings.app.dry_run_default)
        self.chk_trash.setChecked(self.settings.actions.use_trash)
        self.chk_log.setChecked(self.settings.actions.transaction_log)
        self.chk_hidden.setChecked(self.settings.scan.ignore_hidden)
        self.spin_min.setValue(self.settings.duplicates.min_size_bytes)
        self.edit_exclude.setPlainText("\n".join(self.settings.scan.exclude_patterns))
        self.edit_algo.setText(self.settings.hashing.algorithm)
        self.spin_partial.setValue(self.settings.hashing.partial_size_kb)
        self.status.setText(f"Recargado desde {path}")
