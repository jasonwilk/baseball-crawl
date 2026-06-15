"""bb report -- scouting report generation and management commands."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.reports.aggregate_parity import verify_aggregates
from src.reports.generator import generate_report, list_reports

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "app.db"


def _resolve_db_path() -> Path:
    """Return DB path from DATABASE_PATH env var or the project default."""
    env_db = os.environ.get("DATABASE_PATH")
    if env_db is not None:
        env_path = Path(env_db)
        return env_path if env_path.is_absolute() else _PROJECT_ROOT / env_path
    return _DEFAULT_DB_PATH

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

    # Branch on the finer-grained outcome (E-236 TN-5), not just success:
    #   ready    -> success output, exit 0
    #   no_games -> shareable page exists; print the URL and exit 0 (NOT a
    #               hard failure -- the link renders the coach-facing message)
    #   failed   -> hard failure, exit 1
    if result.outcome == "ready":
        console.print(f"\n[green]Report generated successfully![/green]")
        console.print(f"  Title: {result.title}")
        console.print(f"  URL:   {result.url}")
    elif result.outcome == "no_games":
        # Distinguish M=0 ("no games on record") from M>0/N=0 ("games were
        # played, but no box score data") so the operator message is honest --
        # mirrors the coach page's two-case copy (Phase 4b MEDIUM). N is 0 in
        # both no_games cases; M (completed_games) is the discriminator.
        console.print(f"\n[yellow]No games to report yet.[/yellow]")
        m = result.completed_games
        if m:  # M > 0: games played, box-score data missing.
            console.print(
                f"  Played {m} games this season, but no box score data is "
                "available in GameChanger."
            )
        else:  # M == 0 (or unknown): no games on record yet.
            console.print("  No games on record for this team this season.")
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

        # E-235 Phase 4b MEDIUM-2: no_games is a shareable page (served like
        # ready), so expose its link too -- not just for 'ready'.
        linkable = status in ("ready", "no_games") and not r["is_expired"]
        table.add_row(
            r["title"],
            status_display,
            r["generated_at"][:10],
            r["expires_at"][:10],
            r["url"] if linkable else "[dim]-[/dim]",
        )

    console.print(table)


@app.command(name="verify-aggregates")
def verify_aggregates_cmd() -> None:
    """Check stored season aggregates against a per-game recompute.

    Recomputes batting and pitching season aggregates from the per-game stat
    rows (scoped to ``stat_completeness = 'boxscore_only'``) and reports any
    cell that diverges from the stored ``player_season_*`` rows.  A divergence
    is a real finding -- typically a post-load player-dedup merge that
    re-pointed game rows after the season aggregate was computed.  Read-only:
    never writes to the database.
    """
    db_path = _resolve_db_path()
    if not db_path.exists():
        err_console.print(f"[red]Database not found:[/red] {db_path}")
        raise typer.Exit(code=1)

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA foreign_keys=ON;")
        result = verify_aggregates(conn)

    if not result.mismatches:
        console.print(
            f"[green]Aggregates consistent[/green] "
            f"({result.cells_compared} cells compared, 0 mismatches)."
        )
        return

    table = Table(title="Aggregate Parity Mismatches")
    table.add_column("player_id", style="bold")
    table.add_column("team_id")
    table.add_column("season_id")
    table.add_column("column")
    table.add_column("stored")
    table.add_column("recomputed")
    for m in result.mismatches:
        table.add_row(
            str(m.player_id),
            str(m.team_id),
            str(m.season_id),
            m.column,
            str(m.stored),
            str(m.recomputed),
        )

    err_console.print(table)
    err_console.print(
        f"[red]{len(result.mismatches)} mismatch(es)[/red] across "
        f"{result.cells_compared} cells compared."
    )
    raise typer.Exit(code=1)
