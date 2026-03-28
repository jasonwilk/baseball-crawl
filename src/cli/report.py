"""bb report -- scouting report generation and management commands."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from src.reports.generator import generate_report, list_reports

app = typer.Typer(
    help="Scouting report generation and management.",
    invoke_without_command=True,
    epilog="Run 'bb report COMMAND --help' for more information on a command.",
)

console = Console()
err_console = Console(stderr=True)


@app.callback()
def _report_group(ctx: typer.Context) -> None:
    """Scouting report generation and management."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command()
def generate(
    gc_url: str = typer.Argument(
        ...,
        help="GameChanger team URL or public_id slug.",
    ),
) -> None:
    """Generate a standalone scouting report for a team."""
    console.print(f"Generating report for: {gc_url}")
    console.print("This may take a few minutes (crawling + loading)...")

    result = generate_report(gc_url)

    if result.success:
        console.print(f"\n[green]Report generated successfully![/green]")
        console.print(f"  Title: {result.title}")
        console.print(f"  URL:   {result.url}")
    else:
        err_console.print(f"\n[red]Report generation failed.[/red]")
        err_console.print(f"  Error: {result.error_message}")
        raise typer.Exit(code=1)


@app.command(name="list")
def list_cmd() -> None:
    """List all generated reports."""
    reports = list_reports()

    if not reports:
        console.print("No reports found.")
        return

    table = Table(title="Generated Reports")
    table.add_column("Title", style="bold")
    table.add_column("Status")
    table.add_column("Generated")
    table.add_column("Expires")
    table.add_column("URL")

    for r in reports:
        status = r["status"]
        if r["is_expired"]:
            status_display = "[dim]expired[/dim]"
        elif status == "ready":
            status_display = "[green]ready[/green]"
        elif status == "failed":
            status_display = "[red]failed[/red]"
        else:
            status_display = f"[yellow]{status}[/yellow]"

        table.add_row(
            r["title"],
            status_display,
            r["generated_at"][:10],
            r["expires_at"][:10],
            r["url"] if status == "ready" and not r["is_expired"] else "[dim]-[/dim]",
        )

    console.print(table)
