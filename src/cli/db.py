"""bb db -- database management commands (backup, reset, purge-scouting)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from src.api.helpers import is_production
from src.db.backup import backup_database
from src.db.purge_scouting import (
    check_purge_production_guard,
    preview_purge,
    purge_scouting_data,
)
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


def _confirm_purge(resolved_path: Path) -> None:
    """Ask the operator to confirm, harder on production.

    Off production a yes/no is proportionate. ON production the answer must be
    TYPED -- the database filename or the literal ``purge`` -- because a reflex
    ``y`` is exactly how the wrong database gets emptied, and typing the name
    forces the operator to have read the resolved path printed above.

    Raises:
        typer.Abort: The operator declined the yes/no prompt.
        typer.Exit: The typed confirmation did not match.
    """
    if not is_production():
        typer.confirm(
            "This will delete ALL scouting and report data (logins are kept). "
            "Confirm?",
            abort=True,
        )
        return

    expected = resolved_path.name
    typed = typer.prompt(
        f"PRODUCTION purge. Type {expected!r} (or 'purge') to confirm",
        default="",
        show_default=False,
    )
    if typed.strip() not in {expected, "purge"}:
        err_console.print("[red]Confirmation did not match. Nothing was deleted.[/red]")
        raise typer.Exit(code=1)


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
        help="Override the PRODUCTION refusal only. Does not skip the prompt.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Skip the interactive confirmation only. Does not override "
        "the production refusal.",
    ),
) -> None:
    """Delete all scouting/report data, keeping user identity and logins.

    The clean-slate command for a LIVE database: every game, report, team,
    player, and season row is destroyed, while users, passkeys, magic links,
    sessions, and the programs bootstrap row survive -- so coaches stay logged
    in. Use ``bb db reset`` instead when destroying logins is acceptable.

    Sequence (E-270-02, TN-5), and the order is the safety property:
    guard -> preview -> confirm -> backup -> purge. The backup is deliberately
    LAST before the purge: taken before the prompt it would snapshot the whole
    database on every aborted attempt, while here it is the final act before an
    irreversible one, and a backup failure still aborts having destroyed
    nothing.

    ``--force`` and ``--yes`` are SEPARATE (they used to be one flag, which made
    "I know this is production" and "do not ask me" the same statement).
    ``--force`` overrides the production refusal only; ``--yes`` skips the
    prompt only. A scripted production purge needs both.
    """
    # Guard BEFORE everything else, so the operator is never asked to confirm a
    # purge that would be refused anyway (the bb db reset ordering) -- and so a
    # typo'd APP_ENV aborts before a single row is counted.
    #
    # BOTH excepts are required and they are not interchangeable: the production
    # refusal exits via ``SystemExit``, while the unrecognized-APP_ENV typo guard
    # raises ``RuntimeError``. Catching only the former (the pre-E-270 shape)
    # would surface the typo abort as a raw traceback.
    #
    # Keep this try SCOPED to the guard call. ``typer.Exit`` and ``typer.Abort``
    # are both ``RuntimeError`` SUBCLASSES, so widening this block to cover the
    # prompt or the purge would swallow Typer's own control flow and convert a
    # deliberate abort into the wrong message.
    try:
        check_purge_production_guard(force=force)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        err_console.print(
            "[red]Refusing to purge a PRODUCTION database without --force.[/red]"
        )
        raise typer.Exit(code=code) from exc
    except RuntimeError as exc:
        err_console.print(f"[red]Refusing to purge: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    # What is actually in the firing line. The guard keys on APP_ENV but the
    # destruction keys on resolve_db_path(), so the resolved path is shown here
    # rather than merely logged after the point of no return.
    try:
        preview = preview_purge(db_path)
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[red]Cannot read the database to purge: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"Database: [bold]{preview.resolved_path}[/bold]")
    nonempty = preview.nonempty_counts
    if nonempty:
        table = Table(title="Rows to be deleted (as of prompt)")
        table.add_column("Table")
        table.add_column("Rows", justify="right")
        for name, count in nonempty.items():
            table.add_row(name, str(count))
        table.add_row("[bold]TOTAL[/bold]", f"[bold]{preview.total_rows}[/bold]")
        console.print(table)
    else:
        # "as of this read", like the table's header above: a concurrent writer
        # (three processes share this WAL file) can insert between this count and
        # the operator's answer, so a flat "will be a no-op" would promise that a
        # destructive command is harmless when it may no longer be.
        console.print(
            "No scouting/report rows present as of this read "
            "(the purge is expected to be a no-op)."
        )

    if not yes:
        _confirm_purge(preview.resolved_path)

    # Fail-closed backup: the last thing before the irreversible act, and ANY
    # failure aborts before the library opens its BEGIN IMMEDIATE. A purge with
    # no recovery point is the case this closes, so a broken backup is a reason
    # to stop, not a warning to print.
    try:
        backup_path = backup_database(db_path=preview.resolved_path)
    except Exception as exc:  # noqa: BLE001
        err_console.print(
            f"[red]Refusing to purge: the pre-purge backup failed ({exc}). "
            "Nothing was deleted.[/red]"
        )
        raise typer.Exit(code=1) from exc
    console.print(f"[green]Pre-purge backup saved to {backup_path}[/green]")

    # The library re-runs the production guard itself (defense in depth); this
    # call site's own guard above exists only so the refusal precedes the
    # prompt. ``force`` is forwarded because the library guard reads it.
    try:
        result = purge_scouting_data(db_path=db_path, force=force)
    except Exception as exc:  # noqa: BLE001
        err_console.print(
            f"[red]Purge FAILED: {exc}[/red]\n"
            "[yellow]The purge runs in a single transaction, so the database "
            f"was rolled back. A backup was taken at {backup_path}.[/yellow]"
        )
        raise typer.Exit(code=1) from exc

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
