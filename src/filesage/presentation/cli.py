"""Interfaz de linea de comandos de FileSage (Typer).

Etapa 0: comandos de informacion.
Etapa 1: scan + space.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from filesage.core.config import load_settings
from filesage.core.engine import Engine
from filesage.utils.logging import setup_logging

app = typer.Typer(
    name="filesage",
    help="FileSage - herramienta inteligente y segura para gestion de archivos.",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


def _format_size(num_bytes: int) -> str:
    """Formatea bytes en unidades legibles."""
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


@app.callback()
def main(
    ctx: typer.Context,
    config: str = typer.Option(
        None,
        "--config",
        "-c",
        help="Ruta a un archivo de configuracion YAML personalizado.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Activa logging DEBUG.",
    ),
) -> None:
    """Punto de entrada global. Carga configuracion y logging."""
    settings = load_settings(config)

    if verbose:
        settings.logging.level = "DEBUG"

    setup_logging(settings.logging)
    ctx.obj = {"settings": settings, "engine": Engine(settings)}


@app.command()
def version(ctx: typer.Context) -> None:
    """Muestra la version de FileSage."""
    settings = ctx.obj["settings"]
    console.print(
        Panel.fit(
            f"[bold cyan]{settings.app.name}[/bold cyan] v{settings.app.version}",
            title="Version",
            border_style="cyan",
        )
    )


@app.command()
def info(ctx: typer.Context) -> None:
    """Muestra informacion de la configuracion actual."""
    settings = ctx.obj["settings"]
    console.print("[bold]Configuracion actual:[/bold]\n")
    console.print(f"  App          : {settings.app.name} v{settings.app.version}")
    console.print(f"  Dry-run      : {settings.app.dry_run_default}")
    console.print(f"  Hash algo    : {settings.hashing.algorithm}")
    console.print(f"  Partial size : {settings.hashing.partial_size_kb} KB")
    console.print(f"  Use trash    : {settings.actions.use_trash}")
    console.print(f"  Log level    : {settings.logging.level}")


@app.command("hello")
def hello(name: str = "mundo") -> None:
    """Comando de prueba para verificar que la CLI funciona."""
    console.print(f"[green]Hola, {name}! FileSage esta listo.[/green]")


@app.command()
def scan(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Directorio o unidad a escanear."),
    top: int = typer.Option(15, "--top", "-t", help="Numero de archivos mas grandes a mostrar."),
) -> None:
    """Escanea un directorio y muestra un resumen + los archivos mas grandes."""
    engine: Engine = ctx.obj["engine"]
    path = path.expanduser().resolve()

    if not path.exists():
        console.print(f"[red]Error: la ruta no existe -> {path}[/red]")
        raise typer.Exit(code=1)

    with console.status(f"[bold cyan]Escaneando {path}...[/bold cyan]", spinner="dots"):
        result = engine.scan(path)

    console.print()
    console.print(
        Panel.fit(
            f"[bold]{result.total_files:,}[/bold] archivos  ·  "
            f"[bold]{_format_size(result.total_size)}[/bold]  ·  "
            f"{result.duration_seconds:.2f} s",
            title=f"Escaneo de {path}",
            border_style="green",
        )
    )

    if result.errors:
        console.print(f"[yellow]Advertencias / errores: {len(result.errors)}[/yellow]")
        for err in result.errors[:5]:
            console.print(f"  · {err}")
        if len(result.errors) > 5:
            console.print(f"  · ... y {len(result.errors) - 5} mas")

    if result.files:
        table = Table(title=f"Top {top} archivos mas grandes", show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Tamano", justify="right", width=10)
        table.add_column("Ruta")

        sorted_files = sorted(result.files, key=lambda f: f.size, reverse=True)[:top]
        for i, fi in enumerate(sorted_files, 1):
            try:
                rel = fi.path.relative_to(path)
            except ValueError:
                rel = fi.path
            table.add_row(str(i), _format_size(fi.size), str(rel))

        console.print()
        console.print(table)


@app.command()
def space(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Directorio o unidad a analizar."),
    top: int = typer.Option(15, "--top", "-t", help="Numero de archivos mas grandes a mostrar."),
    extensions: int = typer.Option(12, "--ext", "-e", help="Numero de extensiones a mostrar."),
) -> None:
    """Analiza el uso de espacio: resumen, top archivos y desglose por extension."""
    engine: Engine = ctx.obj["engine"]
    path = path.expanduser().resolve()

    if not path.exists():
        console.print(f"[red]Error: la ruta no existe -> {path}[/red]")
        raise typer.Exit(code=1)

    with console.status(f"[bold cyan]Analizando espacio de {path}...[/bold cyan]", spinner="dots"):
        scan_result, report = engine.analyze_space(path, top_n=top)

    console.print()
    console.print(
        Panel.fit(
            f"[bold]{report.total_files:,}[/bold] archivos  ·  "
            f"[bold]{_format_size(report.total_size)}[/bold]  ·  "
            f"{scan_result.duration_seconds:.2f} s",
            title=f"Espacio en {path}",
            border_style="green",
        )
    )

    if scan_result.errors:
        console.print(f"[yellow]Advertencias / errores: {len(scan_result.errors)}[/yellow]")

    if report.top_files:
        table = Table(title=f"Top {top} archivos mas grandes", show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Tamano", justify="right", width=10)
        table.add_column("Ruta")

        for i, fi in enumerate(report.top_files, 1):
            try:
                rel = fi.path.relative_to(path)
            except ValueError:
                rel = fi.path
            table.add_row(str(i), _format_size(fi.size), str(rel))

        console.print()
        console.print(table)

    if report.by_extension:
        table_ext = Table(
            title=f"Uso por extension (top {extensions})",
            show_header=True,
            header_style="bold cyan",
        )
        table_ext.add_column("Extension", width=16)
        table_ext.add_column("Tamano", justify="right", width=12)
        table_ext.add_column("%", justify="right", width=8)

        total = report.total_size or 1
        for i, (ext, size) in enumerate(report.by_extension.items()):
            if i >= extensions:
                break
            pct = (size / total) * 100
            table_ext.add_row(ext, _format_size(size), f"{pct:.1f}%")

        console.print()
        console.print(table_ext)




@app.command()
def gui(
    ctx: typer.Context,
    config: str = typer.Option(
        None,
        "--config",
        "-c",
        help="Ruta a un archivo de configuracion YAML personalizado.",
    ),
) -> None:
    """Lanza la interfaz grafica moderna de FileSage (PySide6)."""
    from filesage.presentation.gui.app import run_gui
    raise SystemExit(run_gui(config))




@app.command()
def duplicates(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Directorio a escanear en busca de duplicados."),
    min_size: int = typer.Option(1024, "--min-size", help="Tamano minimo en bytes."),
) -> None:
    """Busca archivos duplicados por contenido."""
    engine: Engine = ctx.obj["engine"]
    path = path.expanduser().resolve()
    if not path.exists():
        console.print(f"[red]Error: la ruta no existe -> {path}[/red]")
        raise typer.Exit(code=1)

    # Override temporal del min_size si se pasa
    original = engine.settings.duplicates.min_size_bytes
    engine.settings.duplicates.min_size_bytes = min_size

    with console.status(f"[bold cyan]Buscando duplicados en {path}...[/bold cyan]", spinner="dots"):
        scan_result, groups = engine.find_duplicates(path)

    engine.settings.duplicates.min_size_bytes = original

    total_wasted = sum(g.wasted_size for g in groups)
    console.print()
    console.print(
        Panel.fit(
            f"[bold]{len(groups)}[/bold] grupos  ·  "
            f"[bold]{sum(g.count for g in groups)}[/bold] archivos  ·  "
            f"recuperable [bold]{_format_size(total_wasted)}[/bold]  ·  "
            f"{scan_result.duration_seconds:.2f} s",
            title=f"Duplicados en {path}",
            border_style="green",
        )
    )

    if not groups:
        console.print("[green]No se encontraron duplicados.[/green]")
        return

    for i, g in enumerate(groups[:20], 1):
        console.print(f"\n[bold cyan]Grupo {i}[/bold cyan]  (hash {g.hash_full[:12]}...)  recuperable {_format_size(g.wasted_size)}")
        for fi in g.files:
            try:
                rel = fi.path.relative_to(path)
            except ValueError:
                rel = fi.path
            console.print(f"  · {_format_size(fi.size):>10}  {rel}")
    if len(groups) > 20:
        console.print(f"\n... y {len(groups)-20} grupos mas.")




@app.command()
def export(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Directorio a analizar/exportar."),
    output: Path = typer.Option(Path("filesage_report.json"), "--output", "-o", help="Archivo de salida."),
    kind: str = typer.Option("space", "--kind", "-k", help="space | duplicates"),
    fmt: str = typer.Option("json", "--format", "-f", help="json | csv"),
) -> None:
    """Exporta un reporte de espacio o duplicados a JSON/CSV."""
    engine: Engine = ctx.obj["engine"]
    path = path.expanduser().resolve()
    if not path.exists():
        console.print(f"[red]Error: la ruta no existe -> {path}[/red]")
        raise typer.Exit(code=1)

    output = output.expanduser()
    if kind == "duplicates":
        with console.status("Buscando duplicados y exportando..."):
            scan_result, groups = engine.find_duplicates(path)
            out = engine.export_duplicates(groups, path, output, fmt=fmt)
        console.print(f"[green]Exportado: {out}[/green]  ({len(groups)} grupos)")
    else:
        with console.status("Analizando espacio y exportando..."):
            scan_result, report = engine.analyze_space(path)
            out = engine.export_space(report, scan_result, output, fmt=fmt)
        console.print(f"[green]Exportado: {out}[/green]  ({report.total_files} archivos)")


if __name__ == "__main__":
    app()


@app.command("web")
def web(
    host: str = typer.Option("127.0.0.1", help="Host del servidor web"),
    port: int = typer.Option(0, help="Puerto (0=automatico)"),
    native: bool = typer.Option(True, help="Ventana nativa (default). Usa --no-native para navegador"),
) -> None:
    """Lanza el adaptador web (NiceGUI) sobre el mismo Engine."""
    from filesage.presentation.web import run_web
    run_web(host=host, port=port, native=native, reload=False)
