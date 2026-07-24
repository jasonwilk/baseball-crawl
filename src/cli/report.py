"""bb report -- scouting report generation and management commands."""

from __future__ import annotations

import json
import logging
import sqlite3
import subprocess
from contextlib import closing

import typer
from rich.console import Console
from rich.table import Table

from datetime import date, datetime

from src.gamechanger.exceptions import GameChangerAPIError, TeamNotFoundError
from src.gamechanger.opponent_ladder import METHOD_NO_PRESENCE, METHOD_OPERATOR
from src.gamechanger.team_resolver import resolve_team
from src.gamechanger.url_parser import parse_team_url
from src.reports.recon_scoreboard import (
    EXIT_BASELINE_ABSENT,
    EXIT_BASELINE_MALFORMED,
    EXIT_REGRESSION,
    BaselineError,
    ScoreboardResult,
    compute_scoreboard,
    default_baseline_path,
    evaluate_gate,
    load_baseline,
    to_json_dict,
    write_baseline,
)
from src.api.db import get_connection
from src.db.paths import resolve_db_path
from src.reports.generator import generate_report
from src.reports.lifecycle import cleanup_expired_reports, list_reports

app = typer.Typer(
    help="Scouting report generation and management.",
    invoke_without_command=True,
    epilog="Run 'bb report COMMAND --help' for more information on a command.",
)

console = Console()
err_console = Console(stderr=True)

logger = logging.getLogger(__name__)


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
        console.print("\n[green]Report generated successfully![/green]")
        console.print(f"  Title: {result.title}")
        console.print(f"  URL:   {result.url}")
        # E-256-05 / AC-4. Machine-assertable shape for the Step 1d smoke
        # (E-256-11): the literal prefix "Reference date:" followed by an
        # ISO-8601 YYYY-MM-DD, which must equal today in the operating timezone.
        if result.reference_date:
            console.print(f"  Reference date: {result.reference_date}")
    elif result.outcome == "no_games":
        # Distinguish M=0 ("no games on record") from M>0/N=0 ("games were
        # played, but no box score data") so the operator message is honest --
        # mirrors the coach page's two-case copy (Phase 4b MEDIUM). N is 0 in
        # both no_games cases; M (completed_games) is the discriminator.
        console.print("\n[yellow]No games to report yet.[/yellow]")
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
        err_console.print("\n[red]Report generation failed.[/red]")
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
    """Remove on-disk HTML files for expired reports (keeps the report rows),
    then reclaim orphaned reference data.

    Expired reports already 404 on serving; their HTML files, however, are
    never unlinked and accumulate on disk. This sweep deletes those files and
    NULLs ``report_path`` while KEEPING the ``reports`` row, so each report
    still shows as expired in ``bb report list`` / ``/admin/reports``.

    DESTRUCTIVE side effect (E-273-02, TN-14): ``cleanup_expired_reports`` also
    runs the terminal orphan-reclamation sweep, which HARD-DELETEs ``teams`` /
    ``players`` / ``team_rosters`` rows no longer reachable from any surviving
    report. So this command is not merely a file-cleanup: while the expired
    *report* rows are kept, unreachable reference data is reclaimed (best-effort;
    it DEFERS when a report generation is in flight). The reclamation counts are
    logged, not printed here; the ``scripts/reclaim_orphan_reference_data.py``
    one-shot is the authoritative reclaim-reporting surface.
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


def _render_scoreboard_table(result: ScoreboardResult) -> None:
    """Render the human-readable scoreboard (fidelity table + axis counters).

    Batting AB/H rows carry the abandoned-PA / quick-scored residual label
    (never suppressed, AC-3); the perspective-only split is shown as a
    display-only sub-line under the ``no_plays_units`` counter (TN-5).
    """
    table = Table(title="Plays-vs-Boxscore Reconciliation Scoreboard")
    table.add_column("Side", style="bold")
    table.add_column("Stat")
    table.add_column("Exact%", justify="right")
    table.add_column("abs-Δ", justify="right")
    table.add_column("Fidelity units", justify="right")
    table.add_column("Note")

    for side, stats in (("pitching", result.pitching), ("batting", result.batting)):
        for s in stats:
            note = (
                "known residual — quick-scored/abandoned-PA noise"
                if s.is_residual
                else ""
            )
            table.add_row(
                side,
                s.stat,
                f"{s.exact_pct:.1f}%",
                str(s.abs_delta),
                str(s.fidelity_units),
                note,
            )

    console.print(table)
    console.print("[bold]Axis counters[/bold] (north-star trend-toward-zero):")
    console.print(f"  dropped_pitch_events: {result.dropped_pitch_events}")
    console.print(f"  no_plays_units:       {result.no_plays_units}")
    console.print(
        f"      of which perspective-only misses: "
        f"{result.perspective_only_misses} (display-only)"
    )
    console.print(f"  self_games:           {result.self_games}")


def _current_git_sha() -> str:
    """Best-effort full (40-char) git SHA for the baseline metadata header.

    Records the commit a baseline snapshot was taken at (provenance only -- the
    gate diff ignores the metadata header).  Never raises: a baseline snapshot
    must not fail because git is unavailable; falls back to ``"unknown"``.
    """
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


@app.command(name="reconcile-scoreboard")
def reconcile_scoreboard_cmd(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit the scoreboard as a stable JSON block to stdout (JSON only; no table).",
    ),
    update_baseline: bool = typer.Option(
        False,
        "--update-baseline",
        help="Overwrite the committed baseline JSON with this run (then commit the diff).",
    ),
) -> None:
    """Measure plays-vs-boxscore fidelity and gate it against a committed baseline.

    Computes the plays-derived stat fidelity (perspective-scoped, excluding
    no-plays units) and the ``dropped_pitch_events`` / ``no_plays_units`` /
    ``self_games`` axis counters from the live DB -- the standing, repeatable
    form of the E-245 ``recon.sql`` baseline.  Read-only on the database.

    GATE (the north-star ratchet): a fresh run diffs against the committed
    baseline JSON and exits NON-ZERO when a gated number regressed -- any gated
    stat's abs-Δ rose (batting {AB,H,BB,SO}, pitching {H,SO,BB}), either
    ratcheted axis counter (dropped_pitch_events, no_plays_units) rose, OR
    self_games > 0 (a hard zero -- always an opponent-resolution bug). The
    ratchet is one-way: a fix that shrinks a number never trips it, and
    hold-steady passes. BF and HBP are shown as context but not gated.

    FIRST USE (establish the baseline): the gate has nothing to diff against
    until a baseline is committed. Run against the live DB:

        bb report reconcile-scoreboard --update-baseline

    then commit the written .project/baselines/reconciliation-scoreboard.json.
    Until that file exists the gate exits non-zero (code 3) with a bootstrap
    message rather than passing silently.

    ONGOING (after an ingestion change): run the gate before/after the change and
    read the diff. If a fix LEGITIMATELY improved a number, re-snapshot with
    --update-baseline, review the JSON commit diff (the human review point), and
    commit it so the improved number becomes the new floor. No agent
    auto-refreshes the baseline.

    With ``--json``, emits ONLY the stable JSON block to stdout (table
    suppressed; gate verdict + violations go to stderr) so ``json.loads(stdout)``
    is safe. Exit codes: 0 pass, 1 gated regression or run precondition failure
    (e.g. database not found), 3 baseline absent, 4 baseline malformed.
    """
    db_path = resolve_db_path()
    if not db_path.exists():
        err_console.print(f"[red]Database not found:[/red] {db_path}")
        raise typer.Exit(code=1)

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA foreign_keys=ON;")
        result = compute_scoreboard(conn)
        game_count = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]

    baseline_path = default_baseline_path()

    # --- Refresh mode: overwrite the baseline for an operator-reviewed commit --
    if update_baseline:
        metadata = {
            "git_sha": _current_git_sha(),
            "db_game_count": game_count,
            "snapshot_date": date.today().isoformat(),
        }
        write_baseline(baseline_path, result, metadata)
        console.print(f"[green]Baseline updated[/green] at {baseline_path}")
        console.print("Review the JSON commit diff, then commit it.")
        return

    # --- View surface ---------------------------------------------------------
    values = to_json_dict(result)
    if json_output:
        # AC-4b: ONLY the JSON object on stdout -- no Rich table -- so a
        # consumer's json.loads(stdout) never breaks on interleaved text.
        typer.echo(json.dumps(values, indent=2))
    else:
        _render_scoreboard_table(result)

    # --- Gate -----------------------------------------------------------------
    try:
        baseline = load_baseline(baseline_path)
    except BaselineError as exc:
        # A present-but-corrupt baseline (unparseable JSON, or missing a gated
        # value) -- actionable message + a DISTINCT non-zero code, symmetric with
        # the absent-baseline handling below. Never a raw traceback.
        err_console.print(
            f"[red]Committed baseline is malformed or incomplete[/red] ({exc}) — "
            "re-run `bb report reconcile-scoreboard --update-baseline` against the "
            "live DB to regenerate it, then commit."
        )
        raise typer.Exit(code=EXIT_BASELINE_MALFORMED)
    if baseline is None:
        # AC-8: no committed baseline yet -- actionable message + DISTINCT
        # non-zero code (never a crash, never a silent exit 0 that would let an
        # ungated run masquerade as passing).
        err_console.print(
            f"[red]No committed baseline yet[/red] at {baseline_path} — run "
            "`bb report reconcile-scoreboard --update-baseline` against the live "
            "DB to establish one, then commit it."
        )
        raise typer.Exit(code=EXIT_BASELINE_ABSENT)

    gate = evaluate_gate(values, baseline)
    if not gate.passed:
        err_console.print("[red]Reconciliation gate FAILED[/red] — regressed:")
        for violation in gate.violations:
            err_console.print(f"  • {violation.describe()}")
        raise typer.Exit(code=EXIT_REGRESSION)

    # Pass verdict only in table mode -- keep --json stdout pure JSON.
    if not json_output:
        console.print(
            "[green]Reconciliation gate passed[/green] (no gated regression)."
        )


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

    # Route through the single connection factory (E-252-03 AC-7 / GAP A): this
    # UPDATE-ing writer is a SQLite writer on the shared WAL file, so it must
    # carry the factory's busy_timeout + WAL-safe pragmas and WAIT on a concurrent
    # write lock instead of immediately raising "database is locked". The factory
    # already sets PRAGMA foreign_keys=ON, so this is behavior-preserving (the
    # UPDATE logic and `updated`-count semantics are unchanged).
    with closing(get_connection(db_path=db_path)) as conn:
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


def _emit_summary_if_needed(send_summary, *, result, run_error, dry_run: bool) -> bool:
    """Attempt the always-sent end-of-run summary (the missed-run heartbeat).

    Called from ``morning_run_cmd``'s ``finally`` so the summary fires even when
    the run body crashed (E-252-03 AC-1). Returns True when the summary was sent
    (or when dry-run, where no summary is due). On a run-body crash (``result``
    is None / ``run_error`` set) the summary still fires with the failure surfaced
    in its detail. The send is RETRIED once before being declared failed (AC-3);
    the caller turns a False return into a non-zero exit.
    """
    if dry_run:
        return True
    if result is not None:
        generated, failed, unresolved = result.generated, result.failed, result.unresolved
        detail = result.detail_lines
    else:
        generated = failed = unresolved = 0
        detail = ""
    if run_error is not None:
        crash_line = (
            f"RUN ABORTED — the morning-run body raised before completing: {run_error}"
        )
        detail = f"{crash_line}\n{detail}" if detail else crash_line
    for attempt in (1, 2):  # one retry before declaring the heartbeat failed (AC-3)
        if send_summary(
            generated=generated,
            failed=failed,
            unresolved=unresolved,
            detail=detail,
        ):
            return True
        logger.warning("End-of-run summary send failed (attempt %d/2)", attempt)
    return False


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
        validate_alerting_config,
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

    # AC-2: the end-of-run summary email is the ONLY missed-run signal, so for a
    # real run validate the alerting channel can actually DELIVER before doing any
    # work. A misconfigured channel (no ADMIN_EMAIL, or production without
    # Mailgun) aborts loudly HERE rather than running to completion with a
    # silently-dead heartbeat. Dry-run sends no summary, so it is exempt.
    if not dry_run:
        alerting_error = validate_alerting_config()
        if alerting_error:
            err_console.print(
                f"[red]Alerting channel misconfigured:[/red] {alerting_error}"
            )
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

    # AC-1: wrap the run body so an unexpected crash still triggers the summary
    # (the heartbeat) in the `finally`, then surfaces as a non-zero exit -- the run
    # must never die silently. E-252-02 isolates per-TEAM failures INSIDE
    # run_morning; this guards a crash OUTSIDE that isolation (or a path it does
    # not cover, e.g. the connection factory or the output loop).
    result = None
    run_error: Exception | None = None
    try:
        # Route through the single connection factory (GAP A / E-252-06): the
        # morning-run cron is a THIRD SQLite writer on the shared WAL file, so its
        # connection must carry the busy_timeout + WAL-safe pragmas the factory
        # sets rather than the old hand-rolled sqlite3.connect + inline
        # foreign_keys.
        with closing(get_connection(db_path=db_path)) as conn:
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
                # A per-game failure (resolution crash or generation failure) —
                # show the error, no map-opponent prompt.
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
        # Make an all-teams-denied (likely FALSE-403 / pin) situation loud on the
        # CLI too -- not just in the summary email.
        if result.denied:
            err_console.print(f"[yellow]{result.denied_detail}[/yellow]")
    except Exception as exc:  # noqa: BLE001 -- the heartbeat MUST fire on ANY crash
        run_error = exc
        logger.exception("Morning-run body failed")
        err_console.print(f"[red]Morning run failed:[/red] {exc}")
    finally:
        # Always-sent end-of-run summary (the missed-run signal). Attempted in the
        # finally so a body crash above still emails a summary (with the failure in
        # its detail). Not sent in --dry-run. The denied/transient/rate-limit lines
        # ride in `detail` via result.detail_lines (no email-helper signature change).
        summary_sent = _emit_summary_if_needed(
            send_end_of_run_summary_sync,
            result=result,
            run_error=run_error,
            dry_run=dry_run,
        )

    # AC-1 / AC-3 exit code: a body crash, OR a failed/skipped summary send, must
    # exit NON-ZERO (never a false success) so a cron/monitor catches it.
    if run_error is not None:
        raise typer.Exit(code=1)
    if not dry_run and not summary_sent:
        err_console.print(
            "[red]End-of-run summary email FAILED to send[/red] after retry — the "
            "missed-run heartbeat did not go out; investigate the alerting channel "
            "(ADMIN_EMAIL / Mailgun)."
        )
        raise typer.Exit(code=1)
