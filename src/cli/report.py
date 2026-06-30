"""bb report -- scouting report generation and management commands."""

from __future__ import annotations

import sqlite3
from contextlib import closing

import typer
from rich.console import Console
from rich.table import Table

from datetime import date, datetime

from src.gamechanger.exceptions import GameChangerAPIError, TeamNotFoundError
from src.gamechanger.opponent_ladder import METHOD_NO_PRESENCE, METHOD_OPERATOR
from src.gamechanger.team_resolver import resolve_team
from src.gamechanger.url_parser import parse_team_url
from src.reports.aggregate_parity import verify_aggregates
from src.db.paths import resolve_db_path
from src.reports.generator import (
    cleanup_expired_reports,
    generate_report,
    list_reports,
)

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


@app.command(name="cleanup")
def cleanup_cmd() -> None:
    """Remove on-disk HTML files for expired reports (keeps the report rows).

    Expired reports already 404 on serving; their HTML files, however, are
    never unlinked and accumulate on disk. This sweep deletes those files and
    NULLs ``report_path`` while KEEPING the ``reports`` row, so each report
    still shows as expired in ``bb report list`` / ``/admin/reports``.
    """
    result = cleanup_expired_reports()
    console.print(
        f"[green]Cleanup complete[/green] — removed {result.files_removed} "
        f"expired report file(s)."
    )
    if result.errors:
        err_console.print(
            f"[yellow]{result.errors} file(s) could not be removed[/yellow] "
            "(left in place for a later sweep; see logs)."
        )


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
    db_path = resolve_db_path()
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


def _apply_opponent_mapping(
    conn: sqlite3.Connection,
    root_team_id: str,
    *,
    public_id: str | None,
    method: str,
) -> int:
    """UPDATE the pending opponent_links row(s) for a root_team_id.

    Locates EVERY pending not-resolved row (``resolution_method IS NULL``) keyed
    on ``root_team_id`` -- there may be one per LSB team that faces the opponent
    (the ``opponent_links`` key is ``(our_team_id, root_team_id)``) -- and
    UPDATEs each to the operator-supplied state, deriving the NOT NULL
    ``our_team_id`` / ``opponent_name`` from the existing rows rather than
    inserting (the command's signature carries neither; B4). NEVER blind-INSERTs.

    Args:
        conn: Open SQLite connection.
        root_team_id: The GC ``root_team_id`` registry token (NOT a ``gc_uuid``
            -- it is never written to a ``gc_uuid`` column).
        public_id: The resolved opponent ``public_id`` for the positive form, or
            ``None`` for the ``--no-presence`` (resolved-negative) form.
        method: ``"operator"`` (positive) or ``"no_presence"`` (negative).

    Returns:
        The number of rows updated (one per LSB team facing this opponent).
        Zero means no pending row existed -- the caller errors and writes
        nothing.
    """
    # Locate the pending rows by root_team_id. Only NOT-yet-resolved rows are
    # eligible (resolution_method IS NULL) -- an already-resolved row is left
    # alone so a re-run does not clobber a prior mapping.
    pending = conn.execute(
        "SELECT id FROM opponent_links "
        "WHERE root_team_id = ? AND resolution_method IS NULL",
        (root_team_id,),
    ).fetchall()
    if not pending:
        return 0

    conn.execute(
        "UPDATE opponent_links "
        "SET public_id = ?, resolution_method = ?, resolved_at = datetime('now') "
        "WHERE root_team_id = ? AND resolution_method IS NULL",
        (public_id, method, root_team_id),
    )
    conn.commit()
    return len(pending)


@app.command(name="map-opponent")
def map_opponent_cmd(
    root_team_id: str = typer.Argument(
        ...,
        help=(
            "The opponent's GC root_team_id (copy it from a "
            "`bb report morning-run --dry-run` line)."
        ),
    ),
    target: str | None = typer.Argument(
        None,
        help=(
            "The opponent's public_id or full GameChanger team URL. "
            "Omit when using --no-presence."
        ),
    ),
    no_presence: bool = typer.Option(
        False,
        "--no-presence",
        help=(
            "Mark the opponent as having NO GameChanger presence (no report "
            "possible). Operator-declared only; omit <target>."
        ),
    ),
) -> None:
    """Resolve an unresolved-but-mappable opponent by its root_team_id.

    Locates the pending opponent_links row(s) the resolution ladder persisted in
    rung (d) -- there may be one per LSB team facing the opponent -- and UPDATEs
    ALL of them to resolved-positive (``--target`` -> ``public_id`` +
    ``resolution_method='operator'``) or, with ``--no-presence``, to the
    operator-declared resolved-negative state (``resolution_method='no_presence'``,
    ``public_id`` NULL). The rows are keyed on ``root_team_id`` (a stable
    registry id), never on the free-text opponent name.
    """
    # --- Validate the form (mutually exclusive: target XOR --no-presence) ----
    if no_presence:
        if target is not None:
            err_console.print(
                "[red]--no-presence takes no <target>.[/red] "
                "Use `bb report map-opponent <root_team_id> --no-presence`."
            )
            raise typer.Exit(code=2)
        public_id: str | None = None
        method = METHOD_NO_PRESENCE
        display_name: str | None = None
    else:
        if target is None:
            err_console.print(
                "[red]Missing <target>.[/red] Provide a public_id or GC team "
                "URL, or use --no-presence."
            )
            raise typer.Exit(code=2)
        # Parse the target -> public_id. A bare slug or a GC team URL both work;
        # a UUID is rejected (public endpoints / reports key on public_id).
        try:
            parsed = parse_team_url(target)
        except ValueError as exc:
            err_console.print(f"[red]Could not parse target:[/red] {exc}")
            raise typer.Exit(code=2)
        if not parsed.is_public_id:
            err_console.print(
                f"[red]Target must be a public_id or GC team URL, not a UUID[/red] "
                f"({parsed.value!r}). Paste the team's GameChanger URL or its "
                "public_id slug."
            )
            raise typer.Exit(code=2)
        public_id = parsed.value
        method = METHOD_OPERATOR

        # Resolve the display name for operator confirmation (AC-5). The mapping
        # is keyed on root_team_id regardless; a failed lookup warns but does not
        # abort -- the operator already chose the target.
        display_name = None
        try:
            display_name = resolve_team(public_id).name
        except (TeamNotFoundError, GameChangerAPIError) as exc:
            err_console.print(
                f"[yellow]Warning:[/yellow] could not fetch the team name for "
                f"public_id={public_id!r} ({exc}); applying the mapping anyway."
            )

    db_path = resolve_db_path()
    if not db_path.exists():
        err_console.print(f"[red]Database not found:[/red] {db_path}")
        raise typer.Exit(code=1)

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA foreign_keys=ON;")
        updated = _apply_opponent_mapping(
            conn, root_team_id, public_id=public_id, method=method
        )

    if updated == 0:
        err_console.print(
            f"[red]No pending opponent for root_team_id={root_team_id!r}.[/red] "
            "Run `bb report morning-run --dry-run` first to discover and queue "
            "the opponent, then re-run map-opponent."
        )
        raise typer.Exit(code=1)

    team_label = (
        f" — {display_name}" if display_name else ""
    )
    if no_presence:
        console.print(
            f"[green]Marked no GameChanger presence[/green] for "
            f"root_team_id={root_team_id} across {updated} team(s)."
        )
    else:
        console.print(
            f"[green]Mapped[/green] root_team_id={root_team_id}{team_label} "
            f"-> public_id={public_id} across {updated} team(s)."
        )


@app.command(name="morning-run")
def morning_run_cmd(
    team_urls: list[str] = typer.Argument(
        ...,
        help="One or more GameChanger team URLs / public_id slugs (the LSB teams).",
    ),
    date_str: str | None = typer.Option(
        None,
        "--date",
        help="Target date YYYY-MM-DD (default: today). Use for early-start tournaments.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Resolve + preview only; generate NO reports and write NO run records.",
    ),
) -> None:
    """Generate scheduled scouting reports for each team's games on the target date.

    Cron-invokable. For each team (SEQUENTIALLY), reads the schedule + opponents
    registry, filters to the target LOCAL date, resolves each upcoming opponent,
    and -- for auto-resolved opponents -- calls the existing ``generate_report``.
    Each scheduled slot's outcome is recorded to ``scheduled_report_runs`` and an
    end-of-run operator summary is sent.
    """
    # Imported lazily so the module import stays light and credential machinery
    # only loads when the command actually runs.
    from src.api.email import (
        send_end_of_run_summary_sync,
        send_preflight_failure_alert_sync,
        send_unresolved_opponent_alert_sync,
    )
    from src.gamechanger.client import ConfigurationError, GameChangerClient
    from src.reports.morning_run import (
        PreflightError,
        preflight_credential_check,
        run_morning,
    )

    # Parse --date.
    target_date: date | None = None
    if date_str is not None:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            err_console.print(
                f"[red]Invalid --date {date_str!r}[/red]; expected YYYY-MM-DD."
            )
            raise typer.Exit(code=2)

    db_path = resolve_db_path()
    if not db_path.exists():
        err_console.print(f"[red]Database not found:[/red] {db_path}")
        raise typer.Exit(code=1)

    try:
        client = GameChangerClient()
    except ConfigurationError as exc:
        err_console.print(f"[red]GameChanger credentials not configured:[/red] {exc}")
        raise typer.Exit(code=1)

    # Preflight credential liveness ONCE at the top; on failure send the operator
    # alert and abort early/visibly (the preflight-refreshed token feeds the SAME
    # client the crawlers/ladder use).
    try:
        preflight_credential_check(client)
    except PreflightError as exc:
        err_console.print(f"[red]Preflight credential check failed:[/red] {exc}")
        send_preflight_failure_alert_sync(str(exc))
        raise typer.Exit(code=1)

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA foreign_keys=ON;")
        result = run_morning(
            team_urls,
            conn=conn,
            client=client,
            target_date=target_date,
            dry_run=dry_run,
        )

    # Per-slot output: the dry-run eyeball line + the unresolved-mappable
    # prominent line + alert (the alert carries the templated map-opponent cmd).
    for slot in result.slots:
        if slot.resolved_public_id and slot.resolved_team_name:
            record = f" — record {slot.resolved_record}" if slot.resolved_record else ""
            console.print(
                f"[green]RESOLVED[/green] {slot.opponent_name} "
                f"(opponent_id={slot.opponent_root_team_id}) -> "
                f"{slot.resolved_team_name} [public_id: {slot.resolved_public_id}]{record}"
            )
        elif (
            slot.resolution_outcome == "unresolved_mappable"
            and slot.error_message is None
        ):
            # A GENUINE unresolved-mappable opponent (no error). A resolution-
            # CRASH slot shares this outcome value but carries an error_message,
            # so it is excluded -- the operator must NOT be prompted to
            # `map-opponent` an opponent whose processing simply errored.
            # soft_wrap so the copy-paste-ready map-opponent template is never
            # split across a line break on a narrow terminal.
            console.print(
                f"[yellow]UNRESOLVED[/yellow] {slot.opponent_name} "
                f"(opponent_id={slot.opponent_root_team_id}) — needs "
                f"`bb report map-opponent {slot.opponent_root_team_id} <PASTE-GC-TEAM-URL>`",
                soft_wrap=True,
            )
            if not dry_run:
                send_unresolved_opponent_alert_sync(
                    root_team_id=slot.opponent_root_team_id,
                    opponent_name=slot.opponent_name or "(unnamed)",
                )
        elif slot.error_message:
            # A per-game failure (resolution crash or generation failure) — show
            # the error, no map-opponent prompt.
            err_console.print(
                f"[red]FAILED[/red] {slot.opponent_name} "
                f"(opponent_id={slot.opponent_root_team_id}): {slot.error_message}"
            )
        else:
            console.print(
                f"[dim]{slot.resolution_outcome}[/dim] {slot.opponent_name} "
                f"(opponent_id={slot.opponent_root_team_id})"
            )

    console.print(
        f"\n[bold]Morning run complete[/bold] ({result.teams_processed} team(s)): "
        f"{result.generated} generated, {result.failed} failed, "
        f"{result.unresolved} unresolved, {result.deferred} deferred, "
        f"{result.skipped} skipped, {result.denied} denied (403)."
    )
    # Make an all-teams-denied (likely FALSE-403 / pin) situation loud on the CLI
    # too -- not just in the summary email.
    if result.denied:
        err_console.print(f"[yellow]{result.denied_detail}[/yellow]")

    # Always-sent end-of-run summary (the missed-run signal; warn+skip if
    # ADMIN_EMAIL unset). Not sent in --dry-run (no run occurred). The denied
    # line rides in `detail` (no email-helper signature change).
    if not dry_run:
        send_end_of_run_summary_sync(
            generated=result.generated,
            failed=result.failed,
            unresolved=result.unresolved,
            detail=result.detail_lines,
        )
