#!/usr/bin/env python3
"""Launcher grafico FileSage (Tkinter — sin dependencias extra).

Diseno oscuro, simple y claro. Arranca web/Qt, instala deps e integridad.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "scripts" / "run_filesage.py"
INTEGRITY = ROOT / "scripts" / "run_integrity.py"
SYNC = ROOT / "scripts" / "sync_version.py"

# Paleta alineada con la UI web FileSage
BG = "#0f0f14"
CARD = "#1a1a24"
FG = "#e8e8f0"
MUTED = "#9898b0"
ACCENT = "#7c9cff"
ACCENT_HOVER = "#9ab0ff"
DANGER = "#f07178"
OK = "#7fd99a"
BORDER = "#2a2a3a"
FONT_UI = ("Segoe UI", 11)
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_SMALL = ("Segoe UI", 9)


def read_version() -> str:
    vf = ROOT / "VERSION"
    if vf.exists():
        return vf.read_text(encoding="utf-8").strip()
    return "?"


class HoverButton(tk.Canvas):
    """Boton con hover suave (Canvas, sin ttk themes rotas)."""

    def __init__(
        self,
        master,
        text: str,
        command=None,
        *,
        primary: bool = False,
        width: int = 320,
        height: int = 42,
        **kwargs,
    ):
        super().__init__(
            master,
            width=width,
            height=height,
            bg=BG,
            highlightthickness=0,
            cursor="hand2",
            **kwargs,
        )
        self._command = command
        self._primary = primary
        self._text = text
        self._width = width
        self._height = height
        self._bg = ACCENT if primary else CARD
        self._bg_hover = ACCENT_HOVER if primary else "#242433"
        self._fg = "#0f0f14" if primary else FG
        self._draw(self._bg)
        self.bind("<Enter>", lambda e: self._draw(self._bg_hover))
        self.bind("<Leave>", lambda e: self._draw(self._bg))
        self.bind("<Button-1>", self._on_click)

    def _draw(self, fill: str) -> None:
        self.delete("all")
        r = 10
        w, h = self._width, self._height
        # rectangulo redondeado aproximado
        self.create_rectangle(2, 2, w - 2, h - 2, fill=fill, outline=BORDER, width=1)
        self.create_text(
            w // 2,
            h // 2,
            text=self._text,
            fill=self._fg,
            font=FONT_UI,
        )

    def _on_click(self, _event=None) -> None:
        if self._command:
            self._command()


class LauncherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"FileSage Launcher · {read_version()}")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.geometry("440x560")
        self._busy = False
        self._proc: subprocess.Popen | None = None

        # Icono si existe
        ico = ROOT / "src" / "filesage" / "assets" / "icons" / "filesage.ico"
        if ico.exists():
            try:
                self.iconbitmap(default=str(ico))
            except Exception:
                pass

        self._build()
        self._center()

    def _center(self) -> None:
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"+{x}+{y}")

    def _build(self) -> None:
        pad = {"padx": 28, "pady": 4}

        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", pady=(28, 8), padx=28)
        tk.Label(
            header,
            text="FileSage",
            bg=BG,
            fg=FG,
            font=FONT_TITLE,
        ).pack(anchor="w")
        tk.Label(
            header,
            text=f"v{read_version()}  ·  launcher",
            bg=BG,
            fg=MUTED,
            font=FONT_SMALL,
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Gestion inteligente de archivos — local y seguro",
            bg=BG,
            fg=MUTED,
            font=FONT_SMALL,
        ).pack(anchor="w", pady=(6, 0))

        # Separador
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=28, pady=12)

        btns = tk.Frame(self, bg=BG)
        btns.pack(fill="both", expand=True, padx=28)

        actions = [
            ("Abrir FileSage (ventana app)", lambda: self._launch(["--web"]), True),
            ("Abrir en el navegador", lambda: self._launch(["--web", "--browser"]), False),
            ("Interfaz Qt clasica", lambda: self._launch(["--gui"]), False),
            ("Verificar entorno", lambda: self._run_capture(["--check", "--web"]), False),
            ("Instalar / reparar dependencias", lambda: self._run_capture(["--install", "--web"]), False),
            ("Tests de integridad", self._integrity, False),
        ]
        for text, cmd, primary in actions:
            HoverButton(btns, text, command=cmd, primary=primary).pack(pady=5)

        # Log / estado
        status_frame = tk.Frame(self, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        status_frame.pack(fill="x", padx=28, pady=(16, 8))
        self.status = tk.Label(
            status_frame,
            text="Listo.",
            bg=CARD,
            fg=MUTED,
            font=FONT_SMALL,
            anchor="w",
            justify="left",
            wraplength=360,
            padx=12,
            pady=10,
        )
        self.status.pack(fill="x")

        foot = tk.Frame(self, bg=BG)
        foot.pack(fill="x", pady=(4, 20), padx=28)
        tk.Label(
            foot,
            text="Python 3.11+  ·  GPL-3.0",
            bg=BG,
            fg=MUTED,
            font=FONT_SMALL,
        ).pack(side="left")
        exit_lbl = tk.Label(
            foot,
            text="Salir",
            bg=BG,
            fg=MUTED,
            font=FONT_SMALL,
            cursor="hand2",
        )
        exit_lbl.pack(side="right")
        exit_lbl.bind("<Button-1>", lambda e: self.destroy())
        exit_lbl.bind("<Enter>", lambda e: exit_lbl.configure(fg=ACCENT))
        exit_lbl.bind("<Leave>", lambda e: exit_lbl.configure(fg=MUTED))

    def _set_status(self, text: str, *, ok: bool | None = None) -> None:
        color = MUTED
        if ok is True:
            color = OK
        elif ok is False:
            color = DANGER
        self.status.configure(text=text, fg=color)
        self.update_idletasks()

    def _python(self) -> list[str]:
        return [sys.executable]

    def _launch(self, args: list[str]) -> None:
        if self._busy:
            return
        self._set_status("Iniciando FileSage…")
        try:
            # Detach: la app sigue viva si se cierra el launcher
            creation = 0
            if os.name == "nt":
                creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                # Preferir ventana visible para la app nativa; CREATE_NEW_CONSOLE no
                creation = 0
            self._proc = subprocess.Popen(
                self._python() + [str(RUN), *args],
                cwd=str(ROOT),
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            )
            self._set_status(
                "FileSage en marcha. Puedes cerrar este launcher.",
                ok=True,
            )
        except Exception as exc:
            self._set_status(f"Error: {exc}", ok=False)
            messagebox.showerror("FileSage", str(exc))

    def _run_capture(self, args: list[str]) -> None:
        if self._busy:
            return
        self._busy = True
        self._set_status("Trabajando…")

        def worker() -> None:
            try:
                r = subprocess.run(
                    self._python() + [str(RUN), *args],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                )
                out = (r.stdout or "") + (r.stderr or "")
                lines = [ln for ln in out.splitlines() if ln.strip()]
                tail = "\n".join(lines[-6:]) if lines else "(sin salida)"
                ok = r.returncode == 0
                msg = ("Listo.\n" if ok else "Con avisos.\n") + tail
                self.after(0, lambda: self._set_status(msg[:400], ok=ok))
            except Exception as exc:
                self.after(0, lambda: self._set_status(str(exc), ok=False))
            finally:
                self._busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _integrity(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._set_status("Ejecutando tests de integridad…")

        def worker() -> None:
            try:
                r = subprocess.run(
                    self._python() + [str(INTEGRITY), "-q"],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                )
                out = (r.stdout or "") + (r.stderr or "")
                ok = r.returncode == 0 and "passed" in out.lower()
                if ok:
                    # extraer "42 passed"
                    summary = next(
                        (ln for ln in out.splitlines() if "passed" in ln),
                        "Integridad OK",
                    )
                    self.after(
                        0,
                        lambda: self._set_status(f"Integridad OK · {summary.strip()}", ok=True),
                    )
                else:
                    tail = "\n".join(out.splitlines()[-8:])
                    self.after(
                        0,
                        lambda: self._set_status(f"Integridad falló\n{tail[:350]}", ok=False),
                    )
            except Exception as exc:
                self.after(0, lambda: self._set_status(str(exc), ok=False))
            finally:
                self._busy = False

        threading.Thread(target=worker, daemon=True).start()


def main() -> int:
    # En algunos Linux headless falla; en Windows del usuario OK
    try:
        app = LauncherApp()
        app.mainloop()
    except tk.TclError as exc:
        print(f"[FileSage] No se pudo abrir GUI del launcher: {exc}")
        print("  Usa: python scripts/launcher_menu.py")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
