"""bb db -- database management commands (backup, reset, purge-scouting)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from src.db.backup import backup_database
from src.db.purge_scouting import check_purge_production_guard, purge_scouting_data
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
            f"[red]{exc}. Initialize the database first.[/red]"
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
    """Drop and recreate the database (destroys all existing data)."""
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

    tables, _ = reset_database(db_path=db_path, force=force, _skip_guard=True)

    console.print(
        f"[green]Database reset to empty schema. {tables} tables created.[/green]"
    )


@app.command("purge-scouting")
def purge_scouting(
    db_path: Optional[Path] = typer.Option(
        None,
        "--db-path",
        metavar="PATH",
        help="Override DATABASE_PATH env var.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Skip confirmation prompt and the production refusal.",
    ),
) -> None:
    """Delete all scouting/report data, keeping user identity and logins.

    The clean-slate command for a LIVE database: every game, report, team,
    player, and season row is destroyed, while users, passkeys, magic links,
    sessions, and the programs bootstrap row survive -- so coaches stay logged
    in. Use ``bb db reset`` instead when destroying logins is acceptable.
    """
    # Guard BEFORE the confirmation prompt, so the operator is never asked to
    # confirm a purge that would be refused anyway (the bb db reset ordering).
    try:
        check_purge_production_guard(force=force)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        err_console.print(
            "[red]Refusing to purge a PRODUCTION database without --force.[/red]"
        )
        raise typer.Exit(code=code) from exc

    if not force:
        typer.confirm(
            "This will delete ALL scouting and report data (logins are kept). "
            "Confirm?",
            abort=True,
        )

    # The library re-runs the production guard itself (defense in depth); this
    # call site's own guard above exists only so the refusal precedes the
    # prompt. ``force`` is forwarded because the library guard reads it.
    result = purge_scouting_data(db_path=db_path, force=force)

    console.print(
        f"[green]Purged {result.total_rows} row(s) across "
        f"{len(result.rows_deleted)} table(s); removed {result.files_removed} "
        f"report file(s). User identity and auth preserved.[/green]"
    )
    if result.file_errors:
        err_console.print(
            f"[yellow]{result.file_errors} report file(s) could not be removed "
            f"(see logs); database purge completed.[/yellow]"
        )
