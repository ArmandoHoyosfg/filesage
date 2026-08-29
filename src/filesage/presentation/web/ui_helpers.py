"""Utilidades visuales de la UI web/app."""

from __future__ import annotations

from nicegui import ui


def empty_state(title: str, hint: str, *, icon: str = "inbox") -> None:
    with ui.column().classes("fs-empty w-full items-center gap-2"):
        ui.icon(icon).classes("text-5xl text-[#5c5c72]")
        ui.label(title).classes("text-lg font-semibold")
        ui.label(hint).classes("fs-sub max-w-md")


def section_title(text: str, subtitle: str | None = None) -> None:
    ui.label(text).classes("fs-title")
    if subtitle:
        ui.label(subtitle).classes("fs-sub")


def feature_card(href: str, title: str, icon: str, desc: str) -> None:
    with ui.card().classes("fs-card w-64 p-4 cursor-pointer").on(
        "click", lambda e=None, h=href: ui.navigate.to(h)
    ):
        with ui.row().classes("items-center gap-2 mb-1"):
            ui.icon(icon).classes("text-primary text-xl")
            ui.label(title).classes("font-semibold text-base")
        ui.label(desc).classes("fs-sub text-sm")
