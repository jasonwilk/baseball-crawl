"""bb data -- data maintenance commands (reconcile, dedup-players, backfill-appearance-order)."""

from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import typer

if TYPE_CHECKING:
    from src.reconciliation.engine import ReconciliationSummary


logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "app.db"

app = typer.Typer(
    help="Data pipeline commands.",
    invoke_without_command=True,
    epilog="Run 'bb data COMMAND --help' for more information on a command.",
)


@app.callback()
def _data_group(ctx: typer.Context) -> None:
    """Data pipeline commands."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()

def _resolve_db_path() -> Path:
    """Return DB path from DATABASE_PATH env var or the project default."""
    env_db = os.environ.get("DATABASE_PATH")
    if env_db is not None:
        env_path = Path(env_db)
        return env_path if env_path.is_absolute() else _PROJECT_ROOT / env_path
    return _DEFAULT_DB_PATH


# ---------------------------------------------------------------------------
# bb data dedup-players
# ---------------------------------------------------------------------------


@app.command("dedup-players")
def dedup_players(
    execute: bool = typer.Option(
        False,
        "--execute",
        help="Perform the merges. Without this flag, only a dry-run preview is shown.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Explicitly request dry-run mode (this is the default).",
    ),
    team_id: Optional[int] = typer.Option(
        None,
        "--team-id",
        help="Scope detection to a single team.",
    ),
    season_id: Optional[str] = typer.Option(
        None,
        "--season-id",
        help="Scope detection to a single season.",
    ),
    db_path: Path = typer.Option(
        _DEFAULT_DB_PATH,
        "--db",
        help="Path to the SQLite database.",
    ),
) -> None:
    """Detect and merge duplicate players on the same team.

    Default is dry-run: prints detected pairs and per-table row counts
    without modifying any data. Use --execute to perform the merges.
    """
    from src.db.player_dedup import (
        find_duplicate_players,
        merge_player_pair,
        preview_player_merge,
        recompute_affected_seasons,
    )

    # --dry-run is the default; --execute overrides it
    is_dry_run = not execute

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        try:
            pairs = find_duplicate_players(conn, team_id=team_id, season_id=season_id)
        except Exception as exc:
            typer.echo(f"Error finding duplicate players: {exc}", err=True)
            raise SystemExit(1) from exc

        if not pairs:
            typer.echo("No duplicate players found.")
            raise SystemExit(0)

        mode = "DRY RUN" if is_dry_run else "EXECUTE"
        team_ids_seen: set[int] = set()

        typer.echo(f"[{mode}] Found {len(pairs)} duplicate pair(s).\n")

        typer.echo(f"{'Canonical':<30s} {'Duplicate':<30s} {'Team':<30s} {'Confidence':<12s} Reason")
        typer.echo("-" * 120)

        for pair in pairs:
            team_ids_seen.add(pair.team_id)
            canonical_name = f"{pair.canonical_first_name} {pair.canonical_last_name}"
            duplicate_name = f"{pair.duplicate_first_name} {pair.duplicate_last_name}"
            confidence = "high" if pair.has_overlapping_games else "low"
            typer.echo(
                f"{canonical_name:<30s} {duplicate_name:<30s} {pair.team_name:<30s} "
                f"{confidence:<12s} {pair.reason}"
            )

        if is_dry_run:
            # Show per-table preview for each pair
            typer.echo("\nPer-pair row counts:")
            for pair in pairs:
                preview = preview_player_merge(
                    conn, pair.canonical_player_id, pair.duplicate_player_id
                )
                canonical_name = f"{pair.canonical_first_name} {pair.canonical_last_name}"
                duplicate_name = f"{pair.duplicate_first_name} {pair.duplicate_last_name}"
                if preview.table_counts:
                    tables_str = ", ".join(
                        f"{t}={n}" for t, n in sorted(preview.table_counts.items())
                    )
                    typer.echo(f"  {duplicate_name} -> {canonical_name}: {tables_str}")
                else:
                    typer.echo(f"  {duplicate_name} -> {canonical_name}: (no rows)")

            typer.echo("")
            typer.echo(f"Found {len(pairs)} duplicate pair(s) across {len(team_ids_seen)} team(s).")
        else:
            # Execute merges
            merged = 0
            failed = 0
            all_affected: set[tuple[str, int, str]] = set()

            typer.echo("")
            for pair in pairs:
                canonical_name = f"{pair.canonical_first_name} {pair.canonical_last_name}"
                duplicate_name = f"{pair.duplicate_first_name} {pair.duplicate_last_name}"
                try:
                    affected = merge_player_pair(
                        conn,
                        pair.canonical_player_id,
                        pair.duplicate_player_id,
                    )
                    all_affected.update(affected)
                    typer.echo(f"  MERGED {duplicate_name} -> {canonical_name}")
                    merged += 1
                except Exception as exc:
                    typer.echo(
                        f"  ERROR {duplicate_name} -> {canonical_name}: {exc}"
                    )
                    failed += 1

            # Recompute season aggregates
            if all_affected:
                typer.echo(f"\nRecomputing season aggregates for {len(all_affected)} tuple(s)...")
                recompute_affected_seasons(conn, all_affected)
                typer.echo("Season aggregates recomputed.")

            typer.echo(
                f"\nSummary: {len(pairs)} pair(s) detected, "
                f"{merged} merged, {failed} failed."
            )

    raise SystemExit(0)


# ---------------------------------------------------------------------------
# bb data reconcile
# ---------------------------------------------------------------------------


@app.command()
def reconcile(
    game_id: Optional[str] = typer.Option(
        None,
        "--game-id",
        help="Reconcile a single game by game_id.",
        metavar="GAME_ID",
    ),
    execute: bool = typer.Option(
        False,
        "--execute",
        help="Apply pitcher attribution corrections. Default is dry-run detection only.",
    ),
    summary_flag: bool = typer.Option(
        False,
        "--summary",
        help="Show aggregate statistics from reconciliation records (deduplicated by signal).",
    ),
    db_path: Path = typer.Option(
        _DEFAULT_DB_PATH,
        "--db",
        help="Path to the SQLite database.",
    ),
) -> None:
    """Compare plays-derived stats against boxscore ground truth.

    Default mode is dry-run: detects discrepancies and prints a summary
    without modifying any data.

    Examples:
        bb data reconcile                   # dry-run all games
        bb data reconcile --execute         # apply corrections
        bb data reconcile --game-id abc123  # single game, verbose
        bb data reconcile --summary         # aggregate stats from all runs
    """
    from src.reconciliation.engine import (
        get_summary_from_db,
        reconcile_all,
        reconcile_game,
    )

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")

        if summary_flag:
            db_summary = get_summary_from_db(conn)
            _print_db_summary(db_summary)
            raise SystemExit(0)

        if game_id:
            # E-221-07 (R8-P1-3): iterate every perspective the game was
            # loaded from, calling reconcile_game once per perspective.
            # Mirrors reconcile_all's per-pair iteration (engine.py:454-466).
            # Pre-fix, the CLI called reconcile_game without a
            # perspective_team_id kwarg, which fell through to the home-
            # first deterministic selection and silently dropped the other
            # perspective's discrepancies for any cross-perspective game.
            # Option A per DE consult (2026-04-13): unconditional iteration,
            # no --perspective-team-id flag.  The canonical operator mental
            # model for `bb data reconcile --game-id X` is "reconcile this
            # game (all perspectives of it)".
            ptids = [
                row[0]
                for row in conn.execute(
                    "SELECT DISTINCT perspective_team_id FROM plays "
                    "WHERE game_id = ? ORDER BY perspective_team_id",
                    (game_id,),
                ).fetchall()
            ]

            if not ptids:
                # No plays at all -- fall through to the existing skip
                # path so games_skipped_no_plays fires and the operator
                # sees the "no plays data found" message.
                summary = reconcile_game(conn, game_id, dry_run=not execute)
                if summary.games_skipped_no_plays:
                    typer.echo(
                        f"Game {game_id}: no plays data found, skipped."
                    )
                    raise SystemExit(0)
                # Unreachable today (no plays -> skipped above) but kept
                # defensively in case future reconcile_game changes emit
                # a summary without the skip flag.
                mode = "correction" if execute else "detection"
                typer.echo(f"Game {game_id}: {mode} complete.")
                _print_verbose_summary(summary, execute=execute)
                raise SystemExit(0)

            # Shared run_id across the per-perspective calls so all
            # reconciliation_discrepancies rows cluster under one run
            # (matches reconcile_all's pattern at engine.py:451).
            run_id = str(uuid.uuid4())
            mode = "correction" if execute else "detection"
            any_processed = False
            for ptid in ptids:
                summary = reconcile_game(
                    conn, game_id, dry_run=not execute,
                    run_id=run_id, perspective_team_id=ptid,
                )
                if summary.games_skipped_no_plays:
                    # Shouldn't happen -- ptid came from the plays table --
                    # but log and continue rather than failing the command.
                    typer.echo(
                        f"Game {game_id}, perspective {ptid}: no plays "
                        f"(unexpected -- skipped)."
                    )
                    continue
                any_processed = True
                typer.echo(
                    f"\nGame {game_id} (perspective={ptid}): {mode} complete."
                )
                _print_verbose_summary(summary, execute=execute)

            if not any_processed:
                typer.echo(
                    f"Game {game_id}: no reconcilable perspectives found."
                )
        else:
            summary = reconcile_all(conn, dry_run=not execute)
            _print_summary(summary, execute=execute)

    raise SystemExit(0)


def _print_summary(summary: ReconciliationSummary, *, execute: bool = False) -> None:
    """Print aggregate reconciliation summary."""
    typer.echo("\nReconciliation Summary")
    typer.echo(f"  Total games processed: {summary.games_processed}")
    typer.echo(f"  Games skipped (no plays): {summary.games_skipped_no_plays}")

    if execute:
        typer.echo(f"  Games corrected: {summary.games_corrected}")
        typer.echo(f"  Games unchanged: {summary.games_unchanged}")
        typer.echo(f"  Games with remaining ambiguity: {summary.games_with_remaining_ambiguity}")
        typer.echo(f"  Total plays reassigned: {summary.total_plays_reassigned}")
    else:
        typer.echo(f"  Games with all signals matching: {summary.games_all_match}")
        typer.echo(f"  Games with correctable pitcher errors: {summary.games_with_correctable}")
        typer.echo(f"  Games with ambiguous errors: {summary.games_with_ambiguous}")

    if not summary.signal_counts:
        typer.echo("  No signals to report.")
        return

    # Separate pitcher vs batter vs game signals.
    # game_runs and game_pa_count are tautological data-availability checks
    # (same source for both sides) -- exclude from cross-source reconciliation.
    _AVAILABILITY_SIGNALS = frozenset({"game_runs", "game_pa_count"})

    pitcher_signals: dict[str, dict[str, int]] = {}
    batter_signals: dict[str, dict[str, int]] = {}
    game_signals: dict[str, dict[str, int]] = {}
    availability_signals: dict[str, dict[str, int]] = {}

    for sig, counts in summary.signal_counts.items():
        if sig in _AVAILABILITY_SIGNALS:
            availability_signals[sig] = counts
        elif sig.startswith("pitcher_"):
            pitcher_signals[sig] = counts
        elif sig.startswith("batter_"):
            batter_signals[sig] = counts
        elif sig.startswith("game_"):
            game_signals[sig] = counts

    # In execute mode, show before/after comparison for pitcher signals
    if execute and summary.pre_correction_signal_counts:
        typer.echo("\n  Pitcher Signals (before -> after correction):")
        for sig in sorted(pitcher_signals):
            post = pitcher_signals[sig]
            pre = summary.pre_correction_signal_counts.get(sig, {})
            post_total = sum(post.values())
            pre_total = sum(pre.values())
            pre_match = pre.get("MATCH", 0)
            post_match = post.get("MATCH", 0) + post.get("CORRECTED", 0)
            pre_rate = pre_match / pre_total * 100 if pre_total else 0
            post_rate = post_match / post_total * 100 if post_total else 0
            typer.echo(
                f"    {sig}: {pre_match}/{pre_total} ({pre_rate:.1f}%) -> "
                f"{post_match}/{post_total} ({post_rate:.1f}%)"
            )
    else:
        typer.echo("\n  Pitcher Signals:")
        for sig in sorted(pitcher_signals):
            counts = pitcher_signals[sig]
            total = sum(counts.values())
            match = counts.get("MATCH", 0)
            rate = match / total * 100 if total else 0
            typer.echo(f"    {sig}: {match}/{total} match ({rate:.1f}%)")

    typer.echo("\n  Batter Signals:")
    for sig in sorted(batter_signals):
        counts = batter_signals[sig]
        total = sum(counts.values())
        match = counts.get("MATCH", 0)
        rate = match / total * 100 if total else 0
        typer.echo(f"    {sig}: {match}/{total} match ({rate:.1f}%)")

    if game_signals:
        typer.echo("\n  Game-Level Signals:")
        for sig in sorted(game_signals):
            counts = game_signals[sig]
            total = sum(counts.values())
            match = counts.get("MATCH", 0)
            rate = match / total * 100 if total else 0
            typer.echo(f"    {sig}: {match}/{total} match ({rate:.1f}%)")

    if availability_signals:
        typer.echo("\n  Data Availability Checks (not cross-source reconciliation):")
        for sig in sorted(availability_signals):
            counts = availability_signals[sig]
            total = sum(counts.values())
            match = counts.get("MATCH", 0)
            typer.echo(f"    {sig}: {match}/{total} present")

    typer.echo("\n  Status Distribution:")
    total_all = 0
    status_totals: dict[str, int] = {}
    for sig, counts in summary.signal_counts.items():
        if sig in _AVAILABILITY_SIGNALS:
            continue  # Exclude tautological signals from reconciliation totals
        for status, n in counts.items():
            status_totals[status] = status_totals.get(status, 0) + n
            total_all += n
    for status in ("MATCH", "CORRECTABLE", "CORRECTED", "AMBIGUOUS", "UNCORRECTABLE"):
        n = status_totals.get(status, 0)
        rate = n / total_all * 100 if total_all else 0
        typer.echo(f"    {status}: {n} ({rate:.1f}%)")


def _print_verbose_summary(
    summary: ReconciliationSummary, *, execute: bool = False
) -> None:
    """Print verbose per-signal output for a single game."""
    if not summary.signal_counts:
        typer.echo("  No signals to report.")
        return

    if execute:
        typer.echo(f"  Plays reassigned: {summary.total_plays_reassigned}")

    for sig in sorted(summary.signal_counts):
        counts = summary.signal_counts[sig]
        total = sum(counts.values())
        parts = [f"{status}={n}" for status, n in sorted(counts.items())]
        typer.echo(f"  {sig}: {', '.join(parts)} (total={total})")


def _print_db_summary(db_summary: dict) -> None:
    """Print deduplicated aggregate stats from reconciliation records."""
    _AVAILABILITY_SIGNALS = frozenset({"game_runs", "game_pa_count"})

    typer.echo("\nReconciliation Database Summary (deduplicated)")
    typer.echo(f"  Total records: {db_summary['total_records']}")
    typer.echo(f"  Total corrected: {db_summary['total_corrected']}")

    for label, key in [
        ("Pitcher Signals", "pitcher_signals"),
        ("Batter Signals", "batter_signals"),
        ("Game-Level Signals", "game_signals"),
    ]:
        signals = db_summary[key]
        if not signals:
            continue
        # Separate cross-source reconciliation from availability checks
        recon_sigs = {s: c for s, c in signals.items() if s not in _AVAILABILITY_SIGNALS}
        avail_sigs = {s: c for s, c in signals.items() if s in _AVAILABILITY_SIGNALS}

        if recon_sigs:
            typer.echo(f"\n  {label}:")
            for sig in sorted(recon_sigs):
                counts = recon_sigs[sig]
                total = sum(counts.values())
                match = counts.get("MATCH", 0) + counts.get("CORRECTED", 0)
                rate = match / total * 100 if total else 0
                typer.echo(f"    {sig}: {match}/{total} match ({rate:.1f}%)")

        if avail_sigs:
            typer.echo(f"\n  Data Availability Checks (not cross-source reconciliation):")
            for sig in sorted(avail_sigs):
                counts = avail_sigs[sig]
                total = sum(counts.values())
                match = counts.get("MATCH", 0)
                typer.echo(f"    {sig}: {match}/{total} present")


@app.command("backfill-appearance-order")
def backfill_appearance_order(
    db_path: Path = typer.Option(
        _DEFAULT_DB_PATH,
        "--db",
        help="Path to the SQLite database.",
    ),
) -> None:
    """Backfill appearance_order for existing player_game_pitching rows.

    Walks cached boxscore JSON files on disk and updates rows where
    appearance_order IS NULL. Idempotent and re-runnable.

    Examples:
        bb data backfill-appearance-order
    """
    from src.gamechanger.loaders.backfill import backfill_appearance_order as _backfill

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        summary = _backfill(conn)

    typer.echo("\nBackfill Summary:")
    typer.echo(f"  Games processed: {summary['games_processed']}")
    typer.echo(f"  Rows updated: {summary['rows_updated']}")
    typer.echo(f"  Games skipped (no cached file): {summary['games_skipped']}")
    typer.echo(f"  Games with errors: {summary['games_with_errors']}")
    typer.echo(
        "\nReminder: regenerate reports for affected teams so canonical_recompute "
        "rebuilds season aggregates from the backfilled appearance_order "
        "(verify with 'bb report verify-aggregates')."
    )

    raise SystemExit(0)
