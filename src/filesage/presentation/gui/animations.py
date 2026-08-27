"""Animaciones suaves en Python (Qt), equivalentes a transiciones CSS.

Qt no usa CSS animations del navegador; usamos QPropertyAnimation + efectos.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QAbstractAnimation,
    QObject,
    QPoint,
    Qt,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


def fade_in(widget: QWidget, *, duration: int = 250, on_finished: Callable | None = None) -> QPropertyAnimation:
    """Fade in de opacidad 0 → 1."""
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    effect.setOpacity(0.0)

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    if on_finished:
        anim.finished.connect(on_finished)
    anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    # anclar al widget para no GC prematuro
    widget._fade_anim = anim  # type: ignore[attr-defined]
    return anim


def fade_out(widget: QWidget, *, duration: int = 180, on_finished: Callable | None = None) -> QPropertyAnimation:
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(effect.opacity())
    anim.setEndValue(0.0)
    anim.setEasingCurve(QEasingCurve.Type.InCubic)
    if on_finished:
        anim.finished.connect(on_finished)
    anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    widget._fade_anim = anim  # type: ignore[attr-defined]
    return anim


def slide_fade_in(
    widget: QWidget,
    *,
    duration: int = 280,
    offset_y: int = 16,
) -> QParallelAnimationGroup:
    """Entrada suave: opacidad + ligero desplazamiento vertical."""
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)

    start_pos = widget.pos() + QPoint(0, offset_y)
    end_pos = widget.pos()
    widget.move(start_pos)

    fade = QPropertyAnimation(effect, b"opacity", widget)
    fade.setDuration(duration)
    fade.setStartValue(0.0)
    fade.setEndValue(1.0)
    fade.setEasingCurve(QEasingCurve.Type.OutCubic)

    move = QPropertyAnimation(widget, b"pos", widget)
    move.setDuration(duration)
    move.setStartValue(start_pos)
    move.setEndValue(end_pos)
    move.setEasingCurve(QEasingCurve.Type.OutCubic)

    group = QParallelAnimationGroup(widget)
    group.addAnimation(fade)
    group.addAnimation(move)
    group.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    widget._enter_anim = group  # type: ignore[attr-defined]
    return group


def pulse_opacity(widget: QWidget, *, duration: int = 400) -> QPropertyAnimation:
    """Breve pulso de opacidad (feedback de accion)."""
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setKeyValueAt(0.0, 1.0)
    anim.setKeyValueAt(0.4, 0.55)
    anim.setKeyValueAt(1.0, 1.0)
    anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
    anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    widget._pulse_anim = anim  # type: ignore[attr-defined]
    return anim
