"""bb report -- scouting report generation and management commands."""

from __future__ import annotations

from contextlib import closing

import typer
from rich.console import Console
from rich.table import Table

from src.api.db import get_connection
from src.reports.generator import generate_report, list_reports
from src.reports.matchup import is_matchup_enabled

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


def resolve_our_team(value: str) -> int | None:
    """Resolve ``--our-team`` flag value to an integer ``teams.id``.

    Strategy (E-228-01 AC-2a, AC-8):

    1. Try ``int(value)`` first -- ``--our-team 42`` is the integer id case.
    2. Fall back to ``teams.public_id`` lookup, restricted to
       ``membership_type='member'`` (the same set the admin dropdown shows).
    3. Return ``None`` when neither path matches; the caller is responsible
       for emitting a user-facing error and exiting non-zero.

    Args:
        value: The raw ``--our-team`` flag value.

    Returns:
        The resolved integer ``teams.id``, or ``None`` if no match.
    """
    # Strategy 1: integer id
    try:
        candidate_id = int(value)
    except ValueError:
        candidate_id = None

    with closing(get_connection()) as conn:
        if candidate_id is not None:
            row = conn.execute(
                "SELECT id FROM teams "
                "WHERE id = ? AND membership_type = 'member'",
                (candidate_id,),
            ).fetchone()
            if row is not None:
                return int(row[0])
            # Integer parsed but no match -- fall through to public_id lookup
            # so values like ``"123"`` (a numeric public_id slug) still work.

        # Strategy 2: public_id slug
        row = conn.execute(
            "SELECT id FROM teams "
            "WHERE public_id = ? AND membership_type = 'member'",
            (value,),
        ).fetchone()
        if row is not None:
            return int(row[0])

    return None


@app.command()
def generate(
    gc_url: str = typer.Argument(
        ...,
        help="GameChanger team URL or public_id slug.",
    ),
    our_team: str | None = typer.Option(
        None,
        "--our-team",
        help=(
            "Optional LSB team (INTEGER teams.id or public_id slug) to use "
            "for the matchup analysis section.  Resolution: integer id "
            "first, public_id fallback.  Restricted to "
            "membership_type='member' teams.  Requires "
            "FEATURE_MATCHUP_ANALYSIS=1; otherwise the flag is ignored with "
            "a warning."
        ),
    ),
) -> None:
    """Generate a standalone scouting report for a team."""
    console.print(f"Generating report for: {gc_url}")
    console.print("This may take a few minutes (crawling + loading)...")

    our_team_id: int | None = None
    if our_team is not None:
        if not is_matchup_enabled():
            err_console.print(
                "[yellow]Warning:[/yellow] FEATURE_MATCHUP_ANALYSIS is "
                "disabled -- --our-team is ignored.  Generating report "
                "without matchup section.",
            )
        else:
            our_team_id = resolve_our_team(our_team)
            if our_team_id is None:
                err_console.print(
                    f"\n[red]Unknown --our-team value:[/red] {our_team!r}"
                )
                err_console.print(
                    "  Expected an integer teams.id OR a public_id slug for "
                    "a team with membership_type='member'."
                )
                err_console.print(
                    "  Run [bold]bb status[/bold] to list member teams."
                )
                raise typer.Exit(code=2)

    result = generate_report(gc_url, our_team_id=our_team_id)

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
