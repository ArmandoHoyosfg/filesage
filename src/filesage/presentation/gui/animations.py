"""Animaciones seguras para FileSage (sin QGraphicsOpacityEffect).

Por que no usamos opacity effects:
  QGraphicsOpacityEffect + iconos QtAwesome / widgets complejos provoca
  "QPainter::begin: A paint device can only be painted by one painter at a time".

Alternativas seguras (solo QPropertyAnimation sobre geometria/posicion):
  1. Transicion de pagina: captura (grab) + label deslizante
  2. Indicador del sidebar: mueve una barra de acento
  3. Feedback de boton: nada invasivo (QSS hover basta)

Todo es opt-in y falla en silencio si algo no se puede animar.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QAbstractAnimation,
    Qt,
)
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QStackedWidget, QWidget

# Activar/desactivar globalmente
ENABLED = True
PAGE_DURATION_MS = 220
INDICATOR_DURATION_MS = 180


def _keep(widget: QWidget, key: str, obj) -> None:
    """Evita que el GC destruya la animacion a mitad de camino."""
    if not hasattr(widget, "_fs_anims"):
        widget._fs_anims = {}  # type: ignore[attr-defined]
    widget._fs_anims[key] = obj  # type: ignore[attr-defined]


def clear_graphics_effects(widget: QWidget | None) -> None:
    """Limpia efectos residuales de versiones anteriores."""
    if widget is None:
        return
    try:
        if widget.graphicsEffect() is not None:
            widget.setGraphicsEffect(None)
    except Exception:
        pass


def fade_in(widget: QWidget, *, duration: int = 250, on_finished: Callable | None = None):
    """API compatible: ya no usa opacity; solo limpia efectos y opcional callback."""
    clear_graphics_effects(widget)
    if on_finished:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(max(duration // 5, 1), on_finished)
    return None


def fade_out(widget: QWidget, *, duration: int = 180, on_finished: Callable | None = None):
    clear_graphics_effects(widget)
    if on_finished:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(max(duration // 5, 1), on_finished)
    return None


def slide_fade_in(widget: QWidget, *, duration: int = 280, offset_y: int = 16):
    return fade_in(widget, duration=duration)


def pulse_opacity(widget: QWidget, *, duration: int = 400):
    return None


def animate_stacked_slide(
    stack: QStackedWidget,
    new_page: QWidget,
    *,
    duration: int = PAGE_DURATION_MS,
    direction: int = 1,
) -> None:
    """Cambia de pagina con deslizamiento horizontal seguro.

    Technique: grab() de la pagina actual -> QLabel overlay que se desliza fuera
    mientras la nueva pagina ya esta debajo. No toca painters de iconos en vivo.
    """
    if not ENABLED or stack is None or new_page is None:
        stack.setCurrentWidget(new_page)
        return

    if stack.currentWidget() is new_page:
        return

    old = stack.currentWidget()
    if old is None:
        stack.setCurrentWidget(new_page)
        return

    try:
        # Evitar animaciones concurrentes
        if getattr(stack, "_fs_sliding", False):
            stack.setCurrentWidget(new_page)
            return
        stack._fs_sliding = True  # type: ignore[attr-defined]

        w = stack.width()
        h = stack.height()
        if w < 20 or h < 20:
            stack.setCurrentWidget(new_page)
            stack._fs_sliding = False  # type: ignore[attr-defined]
            return

        pix: QPixmap = old.grab()
        overlay = QLabel(stack)
        overlay.setPixmap(pix)
        overlay.setGeometry(0, 0, w, h)
        overlay.show()
        overlay.raise_()

        stack.setCurrentWidget(new_page)

        # Nueva pagina entra desde un lado; overlay sale por el otro
        offset = w if direction >= 0 else -w
        new_page.setGeometry(offset, 0, w, h)

        anim_out = QPropertyAnimation(overlay, b"pos")
        anim_out.setDuration(duration)
        anim_out.setStartValue(QPoint(0, 0))
        anim_out.setEndValue(QPoint(-offset, 0))
        anim_out.setEasingCurve(QEasingCurve.Type.OutCubic)

        anim_in = QPropertyAnimation(new_page, b"pos")
        anim_in.setDuration(duration)
        anim_in.setStartValue(QPoint(offset, 0))
        anim_in.setEndValue(QPoint(0, 0))
        anim_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        group = QParallelAnimationGroup(stack)
        group.addAnimation(anim_out)
        group.addAnimation(anim_in)

        def _cleanup() -> None:
            try:
                overlay.hide()
                overlay.deleteLater()
            except Exception:
                pass
            try:
                # Restaurar geometry gestionada por el layout del stack
                new_page.setGeometry(stack.rect())
            except Exception:
                pass
            stack._fs_sliding = False  # type: ignore[attr-defined]

        group.finished.connect(_cleanup)
        group.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        _keep(stack, "slide", group)
    except Exception:
        stack.setCurrentWidget(new_page)
        try:
            stack._fs_sliding = False  # type: ignore[attr-defined]
        except Exception:
            pass


def animate_indicator_y(
    indicator: QWidget,
    target_y: int,
    *,
    duration: int = INDICATOR_DURATION_MS,
) -> None:
    """Mueve el indicador del sidebar a la altura del boton activo."""
    if not ENABLED or indicator is None:
        indicator.move(indicator.x(), target_y)
        return
    try:
        anim = QPropertyAnimation(indicator, b"pos")
        anim.setDuration(duration)
        anim.setStartValue(indicator.pos())
        anim.setEndValue(QPoint(indicator.x(), target_y))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        _keep(indicator, "move", anim)
    except Exception:
        indicator.move(indicator.x(), target_y)
