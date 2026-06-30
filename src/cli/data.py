"""bb data -- data maintenance commands (reconcile, dedup-players, backfill-appearance-order, reload-annotated-pitches, fix-self-games)."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import typer

from src.db.paths import resolve_db_path

if TYPE_CHECKING:
    from src.reconciliation.engine import ReconciliationSummary


logger = logging.getLogger(__name__)

# game_runs and game_pa_count are tautological data-availability checks (same
# source for both sides) -- excluded from cross-source reconciliation.
_AVAILABILITY_SIGNALS = frozenset({"game_runs", "game_pa_count"})


def _echo_match_rate(sig: str, match: int, total: int) -> None:
    """Echo one reconciliation signal's match-rate line."""
    rate = match / total * 100 if total else 0
    typer.echo(f"    {sig}: {match}/{total} match ({rate:.1f}%)")


def _echo_present(sig: str, present: int, total: int) -> None:
    """Echo one availability signal's presence line."""
    typer.echo(f"    {sig}: {present}/{total} present")


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
    db_path: Optional[Path] = typer.Option(
        None,
        "--db",
        help="Path to the SQLite database (defaults to DATABASE_PATH or the project DB).",
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

    db_path = resolve_db_path(db_path)
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
    db_path: Optional[Path] = typer.Option(
        None,
        "--db",
        help="Path to the SQLite database (defaults to DATABASE_PATH or the project DB).",
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

    db_path = resolve_db_path(db_path)
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

    # Separate pitcher vs batter vs game signals (availability signals excluded
    # from cross-source reconciliation -- see module-level _AVAILABILITY_SIGNALS).
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
            _echo_match_rate(sig, counts.get("MATCH", 0), total)

    typer.echo("\n  Batter Signals:")
    for sig in sorted(batter_signals):
        counts = batter_signals[sig]
        total = sum(counts.values())
        _echo_match_rate(sig, counts.get("MATCH", 0), total)

    if game_signals:
        typer.echo("\n  Game-Level Signals:")
        for sig in sorted(game_signals):
            counts = game_signals[sig]
            total = sum(counts.values())
            _echo_match_rate(sig, counts.get("MATCH", 0), total)

    if availability_signals:
        typer.echo("\n  Data Availability Checks (not cross-source reconciliation):")
        for sig in sorted(availability_signals):
            counts = availability_signals[sig]
            total = sum(counts.values())
            _echo_present(sig, counts.get("MATCH", 0), total)

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
                _echo_match_rate(sig, counts.get("MATCH", 0) + counts.get("CORRECTED", 0), total)

        if avail_sigs:
            typer.echo(f"\n  Data Availability Checks (not cross-source reconciliation):")
            for sig in sorted(avail_sigs):
                counts = avail_sigs[sig]
                total = sum(counts.values())
                _echo_present(sig, counts.get("MATCH", 0), total)


@app.command("backfill-appearance-order")
def backfill_appearance_order(
    db_path: Optional[Path] = typer.Option(
        None,
        "--db",
        help="Path to the SQLite database (defaults to DATABASE_PATH or the project DB).",
    ),
) -> None:
    """Backfill appearance_order for existing player_game_pitching rows.

    Walks cached boxscore JSON files on disk and updates rows where
    appearance_order IS NULL. Idempotent and re-runnable.

    Examples:
        bb data backfill-appearance-order
    """
    from src.gamechanger.loaders.backfill import backfill_appearance_order as _backfill

    db_path = resolve_db_path(db_path)
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


# ---------------------------------------------------------------------------
# bb data reload-annotated-pitches
# ---------------------------------------------------------------------------


@app.command("reload-annotated-pitches")
def reload_annotated_pitches(
    db_path: Optional[Path] = typer.Option(
        None,
        "--db",
        help="Path to the SQLite database (defaults to DATABASE_PATH or the project DB).",
    ),
) -> None:
    """Recover stranded annotated pitches in already-loaded games (E-245).

    Re-derives every loaded game's play_events + parent plays flags IN PLACE
    from the stored raw_template -- reclassifying pitch events that carry a
    trailing type/velocity annotation, populating pitch_type / pitch_speed_mph,
    and recomputing pitch_count / is_first_pitch_strike / is_qab. No API
    re-fetch and no DELETE. Idempotent and re-runnable. Boxscore-derived
    player_game_* and season-aggregate rows are left untouched.

    Examples:
        bb data reload-annotated-pitches
    """
    from src.gamechanger.loaders.plays_reload import reload_all_games

    db_path = resolve_db_path(db_path)
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            summary = reload_all_games(conn)
        except Exception as exc:
            typer.echo(f"Error reloading annotated pitches: {exc}", err=True)
            raise SystemExit(1) from exc

    typer.echo("\nReload Summary:")
    typer.echo(f"  Games processed: {summary['games_processed']}")
    typer.echo(f"  Games changed (pitches recovered): {summary['games_changed']}")
    typer.echo(f"  Plays re-derived: {summary['plays_updated']}")
    typer.echo(f"  Pitch events recovered: {summary['events_recovered']}")
    typer.echo(f"  Games with errors: {summary['games_with_errors']}")
    typer.echo(
        "\nReminder: regenerate reports for affected teams so the forward "
        "pipeline recomputes plays-derived stats from the recovered pitches."
    )

    raise SystemExit(0)


# ---------------------------------------------------------------------------
# bb data fix-self-games
# ---------------------------------------------------------------------------


@app.command("fix-self-games")
def fix_self_games(
    db_path: Optional[Path] = typer.Option(
        None,
        "--db",
        help="Path to the SQLite database (defaults to DATABASE_PATH or the project DB).",
    ),
    execute: bool = typer.Option(
        False,
        "--execute",
        help="Apply the corrective re-ingest (default: dry-run, change nothing).",
    ),
) -> None:
    """Correct self-game (home == away) corruption from the pre-fix loader (E-245-04).

    A scouting boxscore whose opponent never used GC scorekeeping was ingested
    with the opponent collapsed onto the scouted team, producing a self-game
    (home_team_id == away_team_id) and collapsing the plays' batting_team_id
    onto one team (TN-6).

    Dry-run (default) lists the corrupt games and the teams that need an API
    re-fetch. --execute re-fetches each affected team's boxscores via the
    scouting crawl->load pipeline (running the FIXED loader so the games row
    becomes home != away and the opponent is created by name), then re-derives
    the collapsed batting_team_id IN PLACE via reload_game_plays. Plays and
    play_events are NEVER cleared or re-fetched.

    Examples:
        bb data fix-self-games            # dry-run
        bb data fix-self-games --execute  # apply
    """
    from src.gamechanger.loaders.self_game_fix import (
        affected_team_ids,
        find_self_games,
        rederive_corrected_game_plays,
    )

    db_path = resolve_db_path(db_path)
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")

        self_games = find_self_games(conn)
        if not self_games:
            typer.echo(
                "No self-games found (home_team_id == away_team_id). Nothing to do."
            )
            raise SystemExit(0)

        affected = affected_team_ids(conn)
        team_public: dict[int, Optional[str]] = {}
        for tid in affected:
            row = conn.execute(
                "SELECT public_id FROM teams WHERE id = ?", (tid,)
            ).fetchone()
            team_public[tid] = row[0] if row else None

        typer.echo(
            f"\nSelf-games found: {len(self_games)} across {len(affected)} team(s)."
        )
        for tid in affected:
            pid = team_public[tid]
            n = sum(1 for _, t in self_games if t == tid)
            marker = pid if pid else "NO public_id -- cannot re-fetch (will skip)"
            typer.echo(f"  team_id={tid}: {n} self-game(s)  public_id={marker}")

        if not execute:
            typer.echo(
                "\nDry-run only. Re-run with --execute to apply the corrective "
                "re-ingest (requires GC credentials)."
            )
            raise SystemExit(0)

        # --- execute: re-fetch boxscores per affected team, then re-derive ---
        from src.gamechanger.client import GameChangerClient
        from src.gamechanger.crawlers.scouting import ScoutingCrawler
        from src.gamechanger.loaders.scouting_loader import ScoutingLoader

        client = GameChangerClient()
        crawler = ScoutingCrawler(client, conn)
        loader = ScoutingLoader(conn)
        refetched = 0
        for tid in affected:
            pid = team_public[tid]
            if not pid:
                typer.echo(
                    f"Skipping team_id={tid}: no public_id to re-fetch.", err=True
                )
                continue
            try:
                crawl_result = crawler.scout_team(pid)
                loader.load_team(crawl_result, team_id=tid)
                refetched += 1
            except Exception as exc:  # noqa: BLE001 -- per-team error isolation
                # Discard the failed team's PARTIAL writes on the shared
                # connection. load_team writes incrementally and commits only at
                # the end (scouting_loader.py), so a mid-load failure leaves
                # uncommitted partials pending -- without this rollback a later
                # team's commit, or the final rederive per-game commit, would
                # silently persist those orphaned rows. Prior successful teams
                # already committed, so their data is preserved.
                conn.rollback()
                typer.echo(
                    f"Re-fetch failed for team_id={tid} (public_id={pid}): {exc}",
                    err=True,
                )

        # Re-derive batting_team_id in place for the games that were self-games.
        original_ids = [gid for gid, _ in self_games]
        summary = rederive_corrected_game_plays(conn, original_ids)

        remaining = len(find_self_games(conn))
        typer.echo("\nFix Summary:")
        typer.echo(f"  Teams re-fetched: {refetched}/{len(affected)}")
        typer.echo(f"  Games re-derived: {summary['games_rederived']}")
        typer.echo(f"  Plays re-derived: {summary['plays_updated']}")
        typer.echo(f"  Games with re-derive errors: {summary['games_with_errors']}")
        typer.echo(f"  Self-games remaining (target 0): {remaining}")
        typer.echo(
            "\nReminder: regenerate reports for the affected teams so "
            "plays-derived rollups pick up the corrected batting_team_id."
        )

    raise SystemExit(0 if remaining == 0 else 1)
