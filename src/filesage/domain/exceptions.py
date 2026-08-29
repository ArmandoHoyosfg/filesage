"""Excepciones de dominio de FileSage."""


class FileSageError(Exception):
    """Excepción base de la aplicación."""


class ScanError(FileSageError):
    """Error durante el escaneo de archivos."""


class HashError(FileSageError):
    """Error al calcular un hash."""


class ActionError(FileSageError):
    """Error al ejecutar o revertir una acción."""


class ConfigError(FileSageError):
    """Error de configuración."""


class StorageError(FileSageError):
    """Error de persistencia."""


class CancelledError(Exception):
    """La operacion fue cancelada por el usuario o un token de cancelacion."""
