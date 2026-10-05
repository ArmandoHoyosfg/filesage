#!/usr/bin/env python3
"""Menu interactivo FileSage — pensado para doble clic / usuario final.

Mejores practicas:
- Un solo punto de entrada amigable
- Comprueba Python, proyecto y dependencias antes de abrir
- Menu claro con opciones numeradas
- Mensajes en español, pausa ante errores
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def read_version() -> str:
    vf = ROOT / "VERSION"
    if vf.exists():
        return vf.read_text(encoding="utf-8").strip()
    try:
        from filesage.core.config import Settings

        return Settings().app.version
    except Exception:
        return "?"


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def banner() -> None:
    ver = read_version()
    line = "═" * 52
    print()
    print(f"  {line}")
    print("     FileSage  ·  Launcher")
    print(f"     version {ver}")
    print(f"  {line}")
    print()
    print("  Gestion inteligente de archivos — local y seguro")
    print()


def pause(msg: str = "Pulsa Enter para volver al menu…") -> None:
    try:
        input(f"\n  {msg}")
    except EOFError:
        pass


def run_module(args: list[str]) -> int:
    cmd = [sys.executable, str(ROOT / "scripts" / "run_filesage.py"), *args]
    print(f"\n  → {' '.join(args) if args else 'inicio'}\n")
    return subprocess.call(cmd, cwd=str(ROOT))


def run_integrity() -> int:
    cmd = [sys.executable, str(ROOT / "scripts" / "run_integrity.py"), "-q"]
    print("\n  Ejecutando suite de integridad…\n")
    return subprocess.call(cmd, cwd=str(ROOT))


def sync_version() -> int:
    cmd = [sys.executable, str(ROOT / "scripts" / "sync_version.py")]
    return subprocess.call(cmd, cwd=str(ROOT))


def show_status() -> None:
    print("  Comprobando entorno…\n")
    code = run_module(["--check", "--web"])
    if code != 0:
        print("\n  (Web incompleto; se probará también núcleo)")
        run_module(["--check"])
    pause()


def install_all() -> None:
    print("  Instalando dependencias core + web…\n")
    run_module(["--install", "--web"])
    # también core/gui por si acaso
    run_module(["--install"])
    pause("Instalación terminada. Enter para continuar…")


def menu_loop() -> int:
    while True:
        clear()
        banner()
        print("  ¿Qué quieres hacer?\n")
        print("    [1]  Abrir FileSage (ventana app · recomendado)")
        print("    [G]  Abrir este launcher en modo grafico")
        print("    [2]  Abrir FileSage en el navegador")
        print("    [3]  Abrir interfaz Qt clásica")
        print("    [4]  Verificar entorno")
        print("    [5]  Instalar / reparar dependencias")
        print("    [6]  Ejecutar tests de integridad")
        print("    [7]  Sincronizar número de versión")
        print("    [0]  Salir")
        print()
        try:
            choice = input("  Elige una opción: ").strip()
        except EOFError:
            return 0

        if choice.lower() == "g":
            subprocess.call([sys.executable, str(ROOT / "scripts" / "launcher_gui.py")], cwd=str(ROOT))
        elif choice == "1":
            code = run_module(["--web"])
            if code != 0:
                pause("La app terminó con error. Enter para volver…")
        elif choice == "2":
            code = run_module(["--web", "--browser"])
            if code != 0:
                pause("Error al abrir en navegador. Enter…")
        elif choice == "3":
            code = run_module(["--gui"])
            if code != 0:
                pause("Error en GUI Qt. Enter…")
        elif choice == "4":
            show_status()
        elif choice == "5":
            install_all()
        elif choice == "6":
            code = run_integrity()
            pause("Enter para volver al menú…")
        elif choice == "7":
            sync_version()
            pause()
        elif choice in {"0", "q", "Q", "salir"}:
            print("\n  Hasta luego.\n")
            return 0
        else:
            pause("Opción no válida.")


def main() -> int:
    # Atajos por argumento (sin menu)
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in {"--web", "web"}:
            return run_module(["--web"])
        if arg in {"--browser", "browser"}:
            return run_module(["--web", "--browser"])
        if arg in {"--gui", "gui"}:
            return run_module(["--gui"])
        if arg in {"--check", "check"}:
            return run_module(["--check", "--web"])
        if arg in {"--install", "install"}:
            return run_module(["--install", "--web"])
        if arg in {"--integrity", "integrity"}:
            return run_integrity()
        if arg in {"--menu", "menu"}:
            return menu_loop()
    return menu_loop()


if __name__ == "__main__":
    raise SystemExit(main())
