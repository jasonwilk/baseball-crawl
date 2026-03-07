"""bb db -- database management commands (backup, reset)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from scripts.backup_db import backup_database
from scripts.reset_dev_db import reset_database

app = typer.Typer(help="Database operations.")

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
    # Production guard fires BEFORE the confirmation prompt (AC-4, AC-5).
    app_env = os.environ.get("APP_ENV", "development").lower()
    if app_env == "production" and not force:
        err_console.print(
            "[red]APP_ENV=production detected. "
            "Pass --force to confirm reset. "
            "This is a destructive operation.[/red]"
        )
        raise typer.Exit(code=1)

    # Interactive confirmation for all environments unless --force (AC-5).
    if not force:
        typer.confirm(
            "This will destroy and recreate the database. Confirm?",
            abort=True,
        )

    try:
        tables, rows = reset_database(db_path=db_path, force=force)
    except SystemExit as exc:
        # Production guard inside reset_database (belt-and-suspenders).
        code = exc.code if isinstance(exc.code, int) else 1
        raise typer.Exit(code=code) from exc
    except FileNotFoundError as exc:
        err_console.print(f"[red]Seed file error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(
        f"[green]Database reset. {tables} tables created. {rows} rows inserted.[/green]"
    )
