"""bb db -- database management commands (backup, reset)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from src.db.backup import backup_database
from src.db.reset import check_production_guard, reset_database

app = typer.Typer(
    help="Database operations.",
    invoke_without_command=True,
    epilog="Run 'bb db COMMAND --help' for more information on a command.",
)


@app.callback()
def _db_group(ctx: typer.Context) -> None:
    """Database operations."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()

console = Console()
err_console = Console(stderr=True)


@app.command()
def backup(
    db_path: Optional[Path] = typer.Option(
        None,
        "--db-path",
        metavar="PATH",
        help="Override DATABASE_PATH env var.",
    ),
) -> None:
    """Create a timestamped backup of the SQLite database."""
    try:
        result = backup_database(db_path=db_path)
    except FileNotFoundError as exc:
        err_console.print(
            f"[red]{exc}. Run `bb data sync` first.[/red]"
        )
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Backup saved to {result}[/green]")


@app.command()
def reset(
    db_path: Optional[Path] = typer.Option(
        None,
        "--db-path",
        metavar="PATH",
        help="Override DATABASE_PATH env var.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Skip confirmation prompt (for scripted use).",
    ),
) -> None:
    """Drop and recreate the database. All data will be lost."""
    # Production guard fires BEFORE the confirmation prompt so the user is
    # never asked to confirm a reset that will be blocked anyway.
    # check_production_guard() calls sys.exit(1) on failure; catch and convert
    # to a clean Typer exit.  On success, pass _skip_guard=True to
    # reset_database() so the guard does not fire a second time.
    try:
        check_production_guard(force=force)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        raise typer.Exit(code=code) from exc

    # Interactive confirmation for all environments unless --force.
    if not force:
        typer.confirm(
            "This will destroy and recreate the database. Confirm?",
            abort=True,
        )

    try:
        tables, rows = reset_database(db_path=db_path, force=force, _skip_guard=True)
    except FileNotFoundError as exc:
        err_console.print(f"[red]Seed file error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(
        f"[green]Database reset. {tables} tables created. {rows} rows inserted.[/green]"
    )
