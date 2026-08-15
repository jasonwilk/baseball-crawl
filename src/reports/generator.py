"""Report generation pipeline for standalone scouting reports.

Orchestrates the full lifecycle: URL parsing, team creation, scouting crawl/load,
stats query, HTML rendering, and file storage. Each generation creates a new
``reports`` row with a unique slug.

Public API::

    from src.reports.generator import generate_report

    result = generate_report("https://web.gc.com/teams/abc123/some-team")
    if result.success:
        print(result.slug, result.url)
    else:
        print(result.error_message)
"""

from __future__ import annotations

import logging
import secrets
import sqlite3
from contextlib import closing, nullcontext
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Literal

from src.api.db import (
    build_pitcher_profiles,
    get_connection,
    get_pitching_history,
    get_pitching_workload,
    get_season_batting,
    get_season_pitching,
)
from src.api.helpers import era_basis_innings, get_app_url
from src.db.teams import (
    MATCH_ANCHOR,
    MATCH_NAME_ONLY,
    ensure_team_row,
    ensure_team_row_with_provenance,
)
from src.gamechanger.client import CredentialExpiredError, GameChangerClient
from src.gamechanger.crawlers.scouting import ScoutingCrawler
from src.gamechanger.crawlers.scouting_spray import ScoutingSprayChartCrawler
from src.gamechanger.loaders import (
    derive_season_id_for_team,
    ensure_season_row,
)
from src.gamechanger.loaders.plays_loader import PlaysLoader
from src.gamechanger.loaders.scouting_loader import ScoutingLoader
from src.gamechanger.loaders.scouting_spray_loader import ScoutingSprayChartLoader
from src.gamechanger.opponent_ladder import TEAM_DETAIL_ACCEPT
from src.gamechanger.search import resolve_gc_uuid_by_public_id
from src.gamechanger.types import TeamRef
from src.gamechanger.url_parser import parse_team_url
from src.reconciliation.engine import reconcile_game
# The lifecycle module is client-free and MUST NOT import this one (E-256-04,
# TN-13). _REPO_ROOT / _REPORTS_DIR are canonical there; importing them binds
# them as generator's own module attributes, so the existing
# patch("src.reports.generator._REPORTS_DIR") test seam keeps working for the
# generation path. Code inside lifecycle reads lifecycle's globals.
from src.reports.lifecycle import (
    _REPO_ROOT,
    _REPORTS_DIR,
    cleanup_expired_reports,
    cleanup_orphan_teams,
)
from src.reports.renderer import render_no_games_page, render_report
from src.reports.run_status import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    classify_stage_status,
)
from src.util.timezone import (
    UTC_ISO_FORMAT,
    derive_local_date,
    get_operating_timezone,
    operating_today,
    utcnow_iso,
)

logger = logging.getLogger(__name__)

_EXPIRY_DAYS = 14
_PLAYS_ACCEPT = "application/vnd.gc.com.event_plays+json; version=0.0.0"


@dataclass
class GenerationResult:
    """Result of a report generation attempt."""

    success: bool
    slug: str | None = None
    title: str | None = None
    url: str | None = None
    error_message: str | None = None
    # The venue-local date the report's rest-day math and 7-day workload window
    # were computed against (E-256-05). Surfaced so `bb report generate` can
    # print it and the Step 1d smoke can assert it equals today in the operating
    # timezone. Set on the "ready" path only; None otherwise.
    reference_date: str | None = None
    # Additive finer-grained outcome (E-236 TN-5). ``success`` is UNCHANGED
    # (no_games stays success=False); ``outcome`` is purely additive. Defined
    # here with default "failed" so the all-blocked failed return (story 03)
    # inherits the default without an inter-story ordering edge -- story 05 SETS
    # "ready"/"no_games". This story sets NO values and changes NO behavior.
    outcome: Literal["ready", "no_games", "failed"] = "failed"
    # M / N counts carried out for the CLI no_games branch (Phase 4b MEDIUM):
    # so ``bb report generate`` can print an honest operator message
    # distinguishing M=0 ("no games on record") from M>0/N=0 ("played M games,
    # no box score data"). Set only on the no_games return; None elsewhere.
    completed_games: int | None = None
    completed_games_with_data: int | None = None


@dataclass
class _SprayOutcome:
    """Outcome of the spray-chart crawl/load stage.

    ``status`` is the stage's OWN explicit failure signal (``completed`` on a
    healthy crawl/load, ``failed`` on a total crawl failure or an unexpected
    exception). ``_spray_stage`` maps ``status == "failed"`` to a failed run
    record BEFORE the classifier (E-236 TN-1 precedence).

    ``games_crawled`` is the distinct-game count the run record records as
    ``spray_games`` (API fetch successes -- a null spray_chart_data response
    still increments it). ``errors`` is the crawl + load error count that drives
    the ERROR-driven ``spray_status`` (E-236-04 / TN-7); spray is NOT
    coverage-driven, so a null-chart coverage shortfall (zero errors) stays
    "completed". ``spray_games_with_data`` is the INFORMATIONAL coverage count
    (distinct games with spray ROWS actually loaded for this perspective) and
    NEVER drives ``spray_status`` (DE F1 / TN-2).
    """

    status: str
    games_crawled: int = 0
    errors: int = 0
    spray_games_with_data: int = 0


@dataclass
class _ReconCounts:
    """Mutable accumulator for reconciliation-pass counts (TN-2).

    Threaded into :func:`_crawl_and_load_plays` as an out-parameter so the
    plays helper can keep its pinned ``list[str]`` return type (E-211 contract
    test) while still surfacing reconciliation telemetry to the run record.
    """

    discrepancies_found: int = 0
    discrepancies_corrected: int = 0
    games_reconciled: int = 0
    # True when the plays crawl/load/reconcile actually FAILED (vs. legitimately
    # finding no plays). _crawl_and_load_plays swallows its errors and returns []
    # to keep the stage non-fatal + preserve its pinned list[str] return (E-211),
    # so this flag is how _plays_stage distinguishes failure from empty and
    # records plays_status="failed" instead of "completed" (E-235 Phase 4b HIGH-2).
    failed: bool = False
    # ERROR-driven plays-stage classifier inputs (E-236-02 / TN-7). The plays
    # helper keeps its pinned list[str] return, so these out-parameter counts are
    # how _plays_stage derives an honest plays_status without a coverage-driven
    # signal. plays_fetched_ok = games whose plays fetch did NOT raise (includes
    # idempotency-skipped games); plays_fetch_failures = per-game fetch failures
    # (the swallowed except at the crawl loop); plays_load_errors = folded
    # PlaysLoader load_result.errors. Classifier inputs at _plays_stage:
    # loaded = plays_fetched_ok; errors = plays_fetch_failures + plays_load_errors;
    # expected = plays_fetched_ok + plays_fetch_failures (games ATTEMPTED, NOT the
    # informational plays_games_expected / plays_games_covered coverage numbers).
    plays_fetched_ok: int = 0
    plays_fetch_failures: int = 0
    plays_load_errors: int = 0


def _coerce_int(value: object) -> int | None:
    """Return ``value`` if it is a real int, else ``None``.

    None-safe coercion before binding a count to an INTEGER run-record column:
    a stage may surface an absent/typeless count (e.g. an outcome attribute
    that was never populated), and writing ``None`` records "stage produced no
    count" rather than failing the bind. ``bool`` is intentionally excluded so
    a stray flag never lands in a count column.
    """
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _coerce_status(value: object) -> str | None:
    """Return ``value`` if it is a real str, else ``None``.

    None-safe coercion before binding a status to a TEXT run-record column;
    a non-string status resolves to NULL ("stage did not report a status")
    rather than persisting an unexpected value (see :func:`_coerce_int`).
    """
    return value if isinstance(value, str) else None


def _count_completed_games(games: list | None) -> int:
    """Count distinct completed games on the fetched schedule (M, per TN-2).

    Sourced from ``crawl_result.games`` -- the crawler carries the full
    schedule and marks each event's ``game_status``. Returns 0 (not NULL) for
    an empty/early-season schedule; that is a real M=0, not "unknown".
    """
    if not games:
        return 0
    return sum(
        1 for g in games if isinstance(g, dict) and g.get("game_status") == "completed"
    )


def _accumulate_recon_counts(out: _ReconCounts, summary: object) -> None:
    """Fold one game's :class:`ReconciliationSummary` into ``out`` (TN-2).

    ``discrepancies_found`` = non-MATCH signals detected pre-correction;
    ``discrepancies_corrected`` = plays reassigned by the correction pass.
    Reads defensively so a non-summary value (e.g. a test mock) is a no-op.
    """
    reassigned = getattr(summary, "total_plays_reassigned", None)
    if isinstance(reassigned, int):
        out.discrepancies_corrected += reassigned
    pre_counts = getattr(summary, "pre_correction_signal_counts", None)
    if isinstance(pre_counts, dict):
        for status_counts in pre_counts.values():
            if not isinstance(status_counts, dict):
                continue
            for status, count in status_counts.items():
                if status != "MATCH" and isinstance(count, int):
                    out.discrepancies_found += count
    out.games_reconciled += 1


def _get_base_url() -> str:
    """Return the base URL for public report links (shared APP_URL helper)."""
    return get_app_url()


def _create_report_row(
    conn: sqlite3.Connection,
    slug: str,
    team_id: int,
    title: str,
    generated_at: str,
    expires_at: str,
    *,
    commit: bool = True,
) -> int:
    """Insert a new reports row with status='generating'. Returns the row id.

    ``commit`` defaults to ``True`` (the standalone/backward-compatible path).
    Pass ``commit=False`` when the caller owns a shared transaction that also
    holds the team write (E-273-03 / TN-6): the teams row and this reports row
    must land in ONE commit so a team is never visible without its protecting
    'generating' reports row.
    """
    cursor = conn.execute(
        """
        INSERT INTO reports (slug, team_id, title, status, generated_at, expires_at)
        VALUES (?, ?, ?, 'generating', ?, ?)
        """,
        (slug, team_id, title, generated_at, expires_at),
    )
    if commit:
        conn.commit()
    return cursor.lastrowid


def _update_report_ready(
    conn: sqlite3.Connection, report_id: int, report_path: str
) -> None:
    conn.execute(
        "UPDATE reports SET status = 'ready', report_path = ? WHERE id = ?",
        (report_path, report_id),
    )
    conn.commit()


def _update_report_failed(
    conn: sqlite3.Connection, report_id: int, error_message: str
) -> None:
    conn.execute(
        "UPDATE reports SET status = 'failed', error_message = ? WHERE id = ?",
        (error_message, report_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# report_generation_runs (per-generation run record) -- E-235-02 / TN-2
# ---------------------------------------------------------------------------
# Whitelist of writable run-record columns. _update_run_record() interpolates
# column names into the UPDATE SET clause, so the set of accepted keys MUST be
# closed (the values are always bound as parameters; only these literal column
# names are ever interpolated).
_RUN_RECORD_COLUMNS = frozenset({
    "started_at", "completed_at", "overall_status",
    "crawl_status", "load_status", "gc_uuid_status", "spray_status",
    "plays_status", "reconciliation_status", "enrichment_status",
    "completed_games", "completed_games_with_data", "spray_games",
    "spray_games_with_data", "boxscores_fetched", "load_errors",
    "plays_games_expected", "plays_games_covered", "plays_errors",
    "discrepancies_found", "discrepancies_corrected",
    "season_id_used", "identity_match_method",
    "error_stage", "error_message",
})


def _create_run_record(
    conn: sqlite3.Connection,
    report_id: int,
    started_at: str,
    *,
    identity_match_method: str | None = None,
    commit: bool = True,
) -> int:
    """Insert the ``report_generation_runs`` row for ``report_id`` (TN-2).

    Created immediately after the reports row exists (the FK requires it) with
    ``overall_status='running'``. Signals determined before this point (e.g.
    ``identity_match_method`` stashed at the ``ensure_team_row`` site) are
    written here. Returns the new run row id.

    ``commit`` defaults to ``True`` (backward-compatible). Pass ``commit=False``
    when part of the shared team+report transaction (E-273-03 / TN-6); the owning
    ``run()`` issues the single commit for teams → reports → run-record.
    """
    cursor = conn.execute(
        """
        INSERT INTO report_generation_runs
            (report_id, started_at, overall_status, identity_match_method)
        VALUES (?, ?, 'running', ?)
        """,
        (report_id, started_at, identity_match_method),
    )
    if commit:
        conn.commit()
    return cursor.lastrowid


def _update_run_record(report_id: int, **fields: object) -> None:
    """Update the run record for ``report_id`` with the given column values.

    Opens its own connection (the pipeline uses fresh connections per stage).
    Failure to write telemetry must NOT break generation, so SQLite errors are
    logged and swallowed. Unknown column names are rejected defensively.
    """
    fields = {k: v for k, v in fields.items() if k in _RUN_RECORD_COLUMNS}
    if not fields:
        return
    assignments = ", ".join(f"{col} = ?" for col in fields)
    values = [*fields.values(), report_id]
    try:
        with closing(get_connection()) as conn:
            conn.execute(
                f"UPDATE report_generation_runs SET {assignments} WHERE report_id = ?",
                values,
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to update report_generation_runs for report_id=%s", report_id
        )


def _finalize_run_record(
    report_id: int,
    overall_status: str,
    *,
    error_stage: str | None = None,
    error_message: str | None = None,
) -> None:
    """Finalize the run record: set ``overall_status`` + ``completed_at`` (TN-2).

    On failure, also records ``error_stage``/``error_message``.
    """
    _update_run_record(
        report_id,
        overall_status=overall_status,
        completed_at=utcnow_iso(),
        error_stage=error_stage,
        error_message=error_message,
    )


def _query_team_info(conn: sqlite3.Connection, team_id: int) -> dict:
    """Query team name, season_year from the teams table."""
    row = conn.execute(
        "SELECT name, season_year FROM teams WHERE id = ?", (team_id,)
    ).fetchone()
    if row:
        return {"name": row[0], "season_year": row[1]}
    return {"name": f"Team {team_id}", "season_year": None}


def _query_record(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> dict | None:
    """Query win-loss-tie record from the games table.

    Returns ``{"wins": int, "losses": int, "ties": int}``, or ``None`` when the
    team has no scored games in the season. **The ``ties`` key was added in
    E-278-01 and widened this contract** -- a game at equal scores previously
    fell through both strict ``>`` and ``<`` arms and counted as neither, so it
    vanished from the record entirely.

    ⚠️ **This counts games PLAYED, not games we hold DATA for. Do NOT add a
    stat-row ``EXISTS`` gate, a perspective filter, or any other coverage
    condition here.** That was proposed as defence-in-depth and REJECTED by
    domain review (epic TN-7): a win, loss or tie is derivable from a final
    score alone, and the record is a statement about what happened on the field.
    The rejection is backed by measurement, not preference -- **20 genuine
    completed-and-scored games across 12 of 28 teams** (2.4%-15.8% per team)
    carry no stat rows from their own perspective, 17 of them charted only from
    the opposing side. A coverage gate would have silently deleted those 20 real
    games from twelve coaches' records. ``test_record_ignores_stat_row_coverage``
    goes red if such a condition is reintroduced anywhere in this query.

    On the absent ``status = 'completed'`` filter -- deliberate, see E-278-01
    AC-6. **This query is not an exception to its neighbours; it conforms to
    them.** Every game query in this module -- this one, ``_query_recent_games``,
    ``_query_runs_avg`` and ``_query_freshness`` -- gates completeness on
    SCORED-NESS (``home_score IS NOT NULL AND away_score IS NOT NULL``) rather
    than on ``status``, and none of the four carries a status predicate.

    ⚠️ An earlier version of this paragraph claimed *"every other game query in
    `src/` carries one, and this is a knowing exception"*. **That was false, and
    false about three functions in this same file** -- it was a census over a
    tree nobody re-counts, asserted rather than checked, and it survived a relay
    chain in which every verdict was right and the premise underneath was wrong
    the whole way down. The four siblings above are named deliberately instead:
    a claim about one module is checkable in one file and rots VISIBLY if a
    fifth query appears, which a tree-wide count does not.

    **What is actually established.** The ingest path structurally cannot
    CREATE a scored row under a non-terminal status:
    ``_build_games_index_from_data`` skips any event whose ``game_status !=
    "completed"``, and ``GameLoader._upsert_game`` -- the only ``INSERT INTO
    games`` in ``src/`` -- hardcodes ``'completed'``. ⚠️ That bounds what can be
    WRITTEN GOING FORWARD and says nothing whatever about rows already stored.

    **So the guard's cost and its benefit rest on the SAME unaudited
    population, and neither is measured.** For any legacy row holding real
    scores under a non-terminal status, the guard would exclude it -- which is
    at once the harm (a genuinely-played game silently dropped from a coach's
    record) and the benefit (an unfinished game no longer counted as a win).
    Whether such rows exist is unknown. Calling the benefit provably zero while
    calling the cost real would be an asymmetry the evidence does not support:
    if that population is empty the guard is free AND useless; if it is
    non-empty the guard is both helpful and harmful, in proportions nobody has
    counted.

    **And the direction cuts against declining, which is worth saying plainly.**
    This epic's founding defect is record INFLATION, and an unfinished game
    counted as a win is inflation -- so the risk this guard would address is the
    very class the epic exists to fix.

    **The verdict is nonetheless to DECLINE**, on the fail-safe grounds AC-6
    explicitly permits: adding an unauditable filter to a coach-facing number,
    where the failure mode is silent deletion, is not a change to make against
    an unmeasured population.

    ⚠️ **Do not over-read the resemblance to TN-7.** The shape is similar --
    a filter that could silently delete real games -- but TN-7's force was that
    someone COUNTED: 20 genuine games across 12 teams, 2.4%-15.8% each. This
    population is hypothetical and unreachable going forward. Same shape,
    different evidential weight, and borrowing TN-7's authority for an unmeasured
    case would be exactly the borrowed-authority move this repo keeps flagging.

    **How this decays.** The cost half is legacy-data-dependent, and the
    operator's reset removes that population. The verdict survives the reset --
    but NOT because the benefit was independently established at zero. It
    survives because afterwards BOTH halves are zero: no legacy rows remain for
    the guard to help or harm, and the ingest path cannot create new ones. The
    guard goes from unauditable to free-and-pointless.

    **So a later reader weighing "it is free now, add it for defence in depth"
    is making a real choice, not correcting an oversight.** This is settled on
    current grounds, not closed permanently.
    """
    row = conn.execute(
        """
        SELECT
            SUM(CASE
                WHEN home_team_id = :tid AND home_score > away_score THEN 1
                WHEN away_team_id = :tid AND away_score > home_score THEN 1
                ELSE 0
            END) AS wins,
            SUM(CASE
                WHEN home_team_id = :tid AND home_score < away_score THEN 1
                WHEN away_team_id = :tid AND away_score < home_score THEN 1
                ELSE 0
            END) AS losses,
            -- A tie needs no team-side branch: the WHERE clause already
            -- restricts to games this team played, and equal scores are equal
            -- from both sides.
            SUM(CASE
                WHEN home_score = away_score THEN 1
                ELSE 0
            END) AS ties
        FROM games
        WHERE season_id = :season_id
          AND (home_team_id = :tid OR away_team_id = :tid)
          AND home_score IS NOT NULL AND away_score IS NOT NULL
        """,
        {"tid": team_id, "season_id": season_id},
    ).fetchone()
    if row and any(value is not None for value in row):
        return {
            "wins": row[0] or 0,
            "losses": row[1] or 0,
            "ties": row[2] or 0,
        }
    return None


def _query_batting(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> list[dict]:
    """Query season batting stats.

    Thin presentation wrapper (E-256-04 / TN-14): the SQL fetch lives in
    ``src.api.db.get_season_batting``; the name cascade stays here in the report
    layer.  E-259 substitutes the fetch's SQL body without touching this wrapper,
    which is why ``tests/test_report_golden.py`` stays zero-diff across both.
    """
    result = get_season_batting(conn, team_id, season_id)
    _apply_name_cascade(result)
    return result


def _extract_innings_per_game(team_detail: Any) -> int | None:
    """Extract ``settings.scorekeeping.bats.innings_per_game`` (int) or None.

    The ERA basis (E-264 TN-1). Tolerates absence or a mistyped value at ANY
    hop of the nested path (AC-2): a non-dict at any level, a missing key, or a
    non-int (or bool -- ``isinstance(True, int)`` is True) value all yield None,
    so the compute site falls back to 7 rather than crash.
    """
    node: Any = team_detail
    for key in ("settings", "scorekeeping", "bats"):
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    if not isinstance(node, dict):
        return None
    value = node.get("innings_per_game")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _query_pitching(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> list[dict]:
    """Query season pitching stats and compute rate fields.

    Thin presentation wrapper (E-256-04 / TN-14).  ``get_season_pitching``
    returns the RAW SUM columns; the display strings ``era`` / ``k9`` / ``whip`` /
    ``strike_pct`` are added here by ``_compute_pitching_rates``, which must stay
    in the report layer to keep ``src.api.db`` free of a back-import.
    """
    result = get_season_pitching(conn, team_id, season_id)
    _apply_name_cascade(result)
    _compute_pitching_rates(result)
    return result


def _compute_pitching_rates(pitchers: list[dict]) -> None:
    """Add computed rate stats to pitcher dicts (mutates in place)."""
    for row in pitchers:
        ip_outs = row.get("ip_outs") or 0
        er = row.get("er") or 0
        so = row.get("so") or 0
        bb = row.get("bb") or 0
        h = row.get("h") or 0
        pitches = row.get("pitches") or 0
        total_strikes = row.get("total_strikes") or 0
        if ip_outs == 0:
            row["era"] = "-"
            row["k9"] = "-"
            row["whip"] = "-"
        else:
            # ERA uses the team's GC game-length basis (E-264 TN-5); K/9 stays
            # on the 9-inning basis (27 = 9x3) and WHIP stays per-inning (TN-9).
            basis = era_basis_innings(row.get("innings_per_game"))
            row["era"] = f"{(er * basis * 3) / ip_outs:.2f}"
            row["k9"] = f"{(so * 27) / ip_outs:.1f}"
            row["whip"] = f"{(bb + h) * 3 / ip_outs:.2f}"
        row["strike_pct"] = (
            f"{(total_strikes / pitches) * 100:.1f}%" if pitches > 0 else "-"
        )


def _apply_name_cascade(rows: list[dict]) -> None:
    """Apply the fallback display name cascade for Unknown players."""
    for row in rows:
        if row.get("name") == "Unknown Unknown":
            jersey = row.get("jersey_number")
            row["name"] = f"Player #{jersey}" if jersey else "Unknown Player"


def _query_recent_games(
    conn: sqlite3.Connection, team_id: int, season_id: str, limit: int = 5
) -> list[dict]:
    """Query the most recent completed games for recent form display.

    Joins the teams table to resolve opponent names.
    """
    rows = conn.execute(
        """
        SELECT
            g.game_date,
            g.home_team_id,
            g.away_team_id,
            g.home_score,
            g.away_score,
            t_home.name AS home_name,
            t_away.name AS away_name
        FROM games g
        LEFT JOIN teams t_home ON t_home.id = g.home_team_id
        LEFT JOIN teams t_away ON t_away.id = g.away_team_id
        WHERE g.season_id = ?
          AND (g.home_team_id = ? OR g.away_team_id = ?)
          AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL
        ORDER BY g.game_date DESC, g.start_time DESC NULLS LAST
        LIMIT ?
        """,
        (season_id, team_id, team_id, limit),
    ).fetchall()
    results = []
    for row in rows:
        home_id = row[1]
        home_score = row[3]
        away_score = row[4]
        home_name = row[5]
        away_name = row[6]
        is_home = home_id == team_id
        our_score = home_score if is_home else away_score
        their_score = away_score if is_home else home_score
        opponent_name = (away_name if is_home else home_name) or "Unknown"
        if our_score > their_score:
            result = "W"
        elif our_score < their_score:
            result = "L"
        else:
            result = "T"
        results.append({
            "result": result,
            "our_score": our_score,
            "their_score": their_score,
            "opponent_name": opponent_name,
            "is_home": is_home,
        })
    return results


def _query_runs_avg(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> tuple[float | None, float | None]:
    """Return (avg_runs_scored, avg_runs_allowed) per game for the team/season."""
    row = conn.execute(
        """
        SELECT
            AVG(CASE WHEN home_team_id = :tid THEN home_score
                     ELSE away_score END) AS avg_scored,
            AVG(CASE WHEN home_team_id = :tid THEN away_score
                     ELSE home_score END) AS avg_allowed
        FROM games
        WHERE season_id = :season_id
          AND (home_team_id = :tid OR away_team_id = :tid)
          AND home_score IS NOT NULL AND away_score IS NOT NULL
        """,
        {"tid": team_id, "season_id": season_id},
    ).fetchone()
    if row and row[0] is not None:
        return row[0], row[1]
    return None, None


def _query_freshness(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> tuple[str | None, int]:
    """Return (most_recent_game_date, game_count) for completed games the team
    actually has per-game STAT data for (N -- ``completed_games_with_data``).

    N counts completed games for which at least one ``player_game_batting`` or
    ``player_game_pitching`` row was loaded from THIS team's perspective
    (``perspective_team_id = team_id`` -- the perspective the report's crawl
    produced, per the perspective-provenance invariant) -- NOT bare ``games``
    rows. A completed ``games`` row can exist with ZERO stat rows: the game's
    scores come from the schedule summary (``GameLoader._resolve_home_away``
    reads ``summary.owning_team_score``/``opponent_team_score``), while stat rows
    load only when the boxscore carries lineup/pitching groups
    (``_upsert_game_and_stats`` loads stats conditionally on ``own_data``/
    ``opp_data``) -- e.g. an opponent with a public final score but no GC
    scorebook. Counting bare games rows would overstate the footer's N-of-M
    coverage AND let the no-completed-games gate (N==0) miss a report whose games
    have scores but no stats -- the exact silent-empty-report this epic exists to
    prevent (E-235 Phase 4b HIGH-1). The freshness date (MAX) is likewise scoped
    to games-with-data so "Through {date}" reflects the last game we have PLAYER
    DATA for, not a later scored-but-empty one -- one consistent data-bearing
    value across the pre-existing freshness display and the story-07 footer.
    """
    row = conn.execute(
        """
        SELECT MAX(g.game_date) AS latest, COUNT(*) AS cnt
        FROM games g
        WHERE g.season_id = ?
          AND (g.home_team_id = ? OR g.away_team_id = ?)
          AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL
          AND (
            EXISTS (
                SELECT 1 FROM player_game_batting b
                WHERE b.game_id = g.game_id AND b.perspective_team_id = ?
            )
            OR EXISTS (
                SELECT 1 FROM player_game_pitching p
                WHERE p.game_id = g.game_id AND p.perspective_team_id = ?
            )
          )
        """,
        (season_id, team_id, team_id, team_id, team_id),
    ).fetchone()
    if row and row[1] > 0:
        return row[0], row[1]
    return None, 0


def _query_roster(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> list[dict]:
    """Query roster with jersey numbers and positions."""
    rows = conn.execute(
        """
        SELECT
            p.first_name || ' ' || p.last_name AS name,
            tr.jersey_number,
            tr.position
        FROM team_rosters tr
        JOIN players p ON p.player_id = tr.player_id
        WHERE tr.team_id = ? AND tr.season_id = ?
        ORDER BY
            CASE WHEN tr.jersey_number IS NOT NULL
                 THEN CAST(tr.jersey_number AS INTEGER) ELSE 9999 END ASC,
            p.last_name ASC
        """,
        (team_id, season_id),
    ).fetchall()
    return [dict(r) for r in rows]


def _query_spray_charts(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> dict[str, list[dict]]:
    """Query spray chart events grouped by player_id."""
    rows = conn.execute(
        """
        SELECT player_id, x, y, play_result, play_type
        FROM spray_charts
        WHERE team_id = ? AND chart_type = 'offensive' AND season_id = ?
          AND perspective_team_id = ?
        """,
        (team_id, season_id, team_id),
    ).fetchall()
    result: dict[str, list[dict]] = {}
    for row in rows:
        r = dict(row)
        pid = r.pop("player_id")
        result.setdefault(pid, []).append(r)
    return result


def _resolve_gc_uuid(
    client: GameChangerClient,
    team_name: str,
    public_id: str,
) -> str | None:
    """Resolve a team's gc_uuid via POST /search + public_id filtering.

    Delegates the paginated public_id-match loop to
    :func:`~src.gamechanger.search.resolve_gc_uuid_by_public_id` (the shared
    seam), returning the first *truthy* matched id without UUID re-validation
    (a falsy id is skipped and paging continues).  Pagination caps, the
    partial-page short-circuit, and the dirty-name page-0 short-circuit all
    live in that helper.

    ``CredentialExpiredError`` propagates.  All other exceptions are
    caught and logged as warnings (resolution failure is non-fatal).
    """
    try:
        for page, gc_uuid in resolve_gc_uuid_by_public_id(
            client, team_name, public_id
        ):
            if gc_uuid:
                logger.info(
                    "Resolved gc_uuid=%s for public_id=%s via search "
                    "(page %d).",
                    gc_uuid,
                    public_id,
                    page,
                )
                return gc_uuid
        logger.info(
            "POST /search returned no hit matching public_id=%s; "
            "spray charts unavailable.",
            public_id,
        )
        return None
    except CredentialExpiredError:
        raise
    except Exception:  # noqa: BLE001
        logger.warning(
            "gc_uuid resolution via search failed for public_id=%s; "
            "continuing without spray charts.",
            public_id,
            exc_info=True,
        )
        return None


def _crawl_and_load_spray(
    client: GameChangerClient,
    public_id: str,
    season_id: str,
    gc_uuid: str | None = None,
    games_data: list | None = None,
    team_id: int | None = None,
    redirect_map: dict[str, str] | None = None,
) -> _SprayOutcome:
    """Crawl and load spray chart data in-memory (E-220-06).

    ``CredentialExpiredError`` propagates to the caller. All other exceptions
    are caught and logged as warnings -- spray failure is non-fatal.

    Args:
        client: Authenticated ``GameChangerClient``.
        public_id: The scouted team's ``public_id`` slug.
        season_id: Year-only season_id (e.g., ``"2026"``).
        gc_uuid: When provided, passed to the crawler to bypass DB lookup.
        games_data: In-memory games list from the scouting crawl result.
        team_id: This report's team DB id (E-236-04 / AC-6). When provided, the
            INFORMATIONAL ``spray_games_with_data`` coverage count is computed
            via a perspective-filtered ``COUNT(DISTINCT game_id)`` so
            cross-perspective spray rows are not miscounted.
        redirect_map: ``{stale_event_id: surviving_game_id}`` from the dedup
            stage (E-244; widened 2026-08-15). A key is any event id that no
            longer resolves to a ``games`` row -- which, since the
            opponent-identity promotion, INCLUDES the id of a row that was
            merged away and DELETED, not only an incoming source id. The crawl
            FETCHES by source event id (the scouted team's perspective), but
            spray rows are FILED under the canonical id
            via a dict-key remap of ``spray_data`` before load, so deduped games
            land under the canonical row instead of being FK-skipped. Defaults to
            identity passthrough (no remap) for non-deduped runs.

    Returns:
        A :class:`_SprayOutcome` recording the stage status, the distinct games
        crawled (run-record ``spray_games``), the crawl+load error count
        (drives the ERROR-driven ``spray_status``), and the informational
        ``spray_games_with_data`` coverage count.
    """
    try:
        with closing(get_connection()) as conn:
            spray_crawler = ScoutingSprayChartCrawler(client, conn)
            spray_result = spray_crawler.crawl_team(
                public_id, season_id=season_id, gc_uuid=gc_uuid,
                games_data=games_data,
            )

        if spray_result.errors and spray_result.games_crawled == 0:
            logger.warning("Spray crawl failed for public_id=%s; no data.", public_id)
            return _SprayOutcome(
                status=STATUS_FAILED, games_crawled=0, errors=spray_result.errors,
            )

        # Remap spray dict keys from source event ids to canonical game ids so
        # deduped games are filed under (and idempotency-checked against) the
        # canonical row (E-244 TN-3). The spray loader derives game_id solely
        # from the dict key, so this key remap is the only change spray needs --
        # the spray query is game-id-agnostic. .get(k, k) is identity for the
        # common non-deduped case.
        redirect = redirect_map or {}
        remapped_spray = {
            redirect.get(k, k): v for k, v in spray_result.spray_data.items()
        }
        with closing(get_connection()) as conn:
            spray_loader = ScoutingSprayChartLoader(conn)
            load_result = spray_loader.load_from_data(
                remapped_spray, public_id=public_id,
            )

        # INFORMATIONAL coverage (TN-2 / AC-1): distinct games with spray ROWS
        # actually present for THIS report's perspective. The predicate MUST
        # mirror _query_spray_charts (the query that builds the rendered
        # offensive spray line) -- same team_id + season_id + perspective +
        # chart_type='offensive' -- so the (with_data / spray_games) coverage
        # figure is coherent with what the report actually renders. Without the
        # season_id + chart_type='offensive' filters the count inflated by
        # counting cross-season and defensive-chart rows the spray line never
        # shows (Phase 4b MEDIUM). NEVER drives spray_status (DE F1) -- a
        # null-chart shortfall is the normal scorekeeper-didn't-chart case.
        # NOTE: this numerator is DB-state-scoped while the denominator
        # (spray_games = games_crawled) is this-run; they align under the
        # fresh-team-per-generation flow.
        spray_games_with_data = 0
        if team_id is not None:
            with closing(get_connection()) as conn:
                row = conn.execute(
                    "SELECT COUNT(DISTINCT game_id) FROM spray_charts "
                    "WHERE team_id = ? AND season_id = ? "
                    "AND chart_type = 'offensive' AND perspective_team_id = ?",
                    (team_id, season_id, team_id),
                ).fetchone()
                spray_games_with_data = row[0] if row else 0

        return _SprayOutcome(
            status=STATUS_COMPLETED,
            games_crawled=spray_result.games_crawled,
            # ERROR-driven signal (AC-2): crawl errors + load errors. A healthy
            # stage with null charts has errors==0 -> stays "completed".
            errors=spray_result.errors + load_result.errors,
            spray_games_with_data=spray_games_with_data,
        )
    except CredentialExpiredError:
        raise
    except Exception:  # noqa: BLE001
        logger.warning(
            "Spray chart crawl/load failed for public_id=%s; "
            "continuing without spray charts.",
            public_id,
            exc_info=True,
        )
        return _SprayOutcome(status=STATUS_FAILED, games_crawled=0, errors=1)


def _crawl_and_load_plays(
    client: GameChangerClient,
    public_id: str,
    team_id: int,
    season_id: str,
    game_ids: list[str] | None = None,
    recon_out: _ReconCounts | None = None,
    redirect_map: dict[str, str] | None = None,
) -> list[str]:
    """Crawl, load, and reconcile plays data in-memory (E-220-06).

    Game IDs come from crawl result boxscores (in-memory), not disk globs.
    Plays are fetched in-memory and passed directly to PlaysLoader via its
    payload entry point (no disk round-trip).

    Args:
        client: Authenticated ``GameChangerClient``.
        public_id: The scouted team's ``public_id`` slug.
        team_id: The team's DB integer PK.
        season_id: Canonical DB season_id for query scoping.
        game_ids: List of game IDs (SOURCE event ids) from the crawl result
            boxscores.
        recon_out: Optional mutable accumulator (E-235-02 / TN-2). When
            provided, the reconciliation pass populates it with per-generation
            ``discrepancies_found`` / ``discrepancies_corrected`` /
            ``games_reconciled`` for the run record. The return value stays
            ``list[str]`` (the E-211 contract) regardless.
        redirect_map: ``{stale_event_id: surviving_game_id}`` from the dedup
            stage (E-244; widened 2026-08-15). A key is any event id that no
            longer resolves to a ``games`` row -- which, since the
            opponent-identity promotion, INCLUDES the id of a row that was
            merged away and DELETED, not only an incoming source id. The API
            FETCH continues to use the SOURCE event id
            (it returns the scouted team's perspective), but the idempotency
            precheck, the DB-write key, the reconcile loop, and the returned
            game-id list (the rate-query scope) all use the CANONICAL id so
            deduped games are filed under -- and counted from -- the canonical
            row. Defaults to identity passthrough for non-deduped runs.

    Returns:
        List of CANONICAL game_id strings that were processed, deduped (two
        source perspectives can collapse to one canonical id).
    """
    if not game_ids:
        logger.info("No game IDs for plays stage for public_id=%s; skipping.", public_id)
        return []

    redirect = redirect_map or {}
    # Canonical, deduped, order-preserving id list for the DB-write/reconcile/
    # query scope. Two source ids can collapse to one canonical id, so a naive
    # remap would put a duplicate id in the rate-query IN-clause (E-244 TN-3).
    canonical_ids: list[str] = []
    _seen_canonical: set[str] = set()
    for _src_id in game_ids:
        _cid = redirect.get(_src_id, _src_id)
        if _cid not in _seen_canonical:
            _seen_canonical.add(_cid)
            canonical_ids.append(_cid)

    try:
        # Crawl: fetch plays for each game in-memory (per-game error isolation)
        plays_data: dict[str, dict] = {}
        for game_id in game_ids:
            # Fetch by SOURCE id; file/idempotency-check by CANONICAL id (E-244).
            canonical_id = redirect.get(game_id, game_id)
            # Check DB idempotency (perspective-aware) against the canonical id,
            # else every re-run re-fetches the API for every deduped game.
            with closing(get_connection()) as conn:
                existing = conn.execute(
                    "SELECT 1 FROM plays WHERE game_id = ? AND perspective_team_id = ? LIMIT 1",
                    (canonical_id, team_id),
                ).fetchone()
            if existing is not None:
                logger.debug("Plays already loaded for game %s perspective %d; skipping.", canonical_id, team_id)
                plays_data[canonical_id] = {}  # mark as processed for reconcile
                # Idempotency skip is a non-error outcome -- the game's plays
                # fetch did NOT raise, so it counts as fetched_ok (TN-7).
                if recon_out is not None:
                    recon_out.plays_fetched_ok += 1
                continue

            try:
                raw = client.get(
                    f"/game-stream-processing/{game_id}/plays",
                    accept=_PLAYS_ACCEPT,
                )
                # Key the payload by the canonical id so PlaysLoader (which
                # derives game_id from the dict key) files rows under it.
                plays_data[canonical_id] = raw if isinstance(raw, dict) else {}
                logger.debug("Fetched plays for game %s (canonical %s).", game_id, canonical_id)
                if recon_out is not None:
                    recon_out.plays_fetched_ok += 1
            except CredentialExpiredError:
                raise
            except Exception:  # noqa: BLE001
                # Per-game fetch failure (E-236-02 / TN-7): swallowed to keep the
                # stage non-fatal, but threaded into recon_out so _plays_stage can
                # classify the stage as "partial"/"failed" instead of "completed".
                if recon_out is not None:
                    recon_out.plays_fetch_failures += 1
                logger.warning(
                    "Failed to fetch plays for game %s; skipping.",
                    game_id,
                    exc_info=True,
                )

        if not plays_data:
            logger.info("No plays data fetched for team_id=%d.", team_id)
            return []

        # Load: pass the in-memory plays payloads directly to PlaysLoader
        # (no temp files). load_payload skips empty/{} entries (already-loaded
        # games) exactly as the old tempdir bridge skipped non-empty writes.
        with closing(get_connection()) as conn:
            row = conn.execute(
                "SELECT gc_uuid, public_id FROM teams WHERE id = ?", (team_id,)
            ).fetchone()
            gc_uuid = row[0] if row else None
            team_public_id = row[1] if row else public_id

        team_ref = TeamRef(id=team_id, gc_uuid=gc_uuid, public_id=team_public_id)

        with closing(get_connection()) as conn:
            loader = PlaysLoader(conn, owned_team_ref=team_ref)
            load_result = loader.load_payload(plays_data)

        logger.info(
            "Plays load for team_id=%d: loaded=%d skipped=%d errors=%d",
            team_id, load_result.loaded, load_result.skipped, load_result.errors,
        )
        # Fold PlaysLoader errors into the plays-stage error count (E-236-02 /
        # TN-7). load_result.errors is non-fatal here (the loader logged + kept
        # going), but it makes the stage "partial", not "completed".
        if recon_out is not None:
            recon_out.plays_load_errors += load_result.errors

        # Reconcile: correct pitcher attribution for each game.  E-220 round
        # 6 cluster 4: pass perspective_team_id=team_id so reconcile targets
        # the report's team perspective.  Otherwise cross-perspective games
        # where team_id != home_team_id would reconcile the wrong rows.
        # Iterate CANONICAL ids so reconcile finds the deduped games' plays
        # rows (under the bug it keyed off source ids and silently no-opped on
        # deduped games -- E-244 TN-3 site 2).
        for game_id in canonical_ids:
            try:
                with closing(get_connection()) as conn:
                    has_plays = conn.execute(
                        "SELECT 1 FROM plays WHERE game_id = ? AND perspective_team_id = ? LIMIT 1",
                        (game_id, team_id),
                    ).fetchone()
                    if has_plays:
                        summary = reconcile_game(
                            conn, game_id, dry_run=False,
                            perspective_team_id=team_id,
                        )
                        if recon_out is not None:
                            _accumulate_recon_counts(recon_out, summary)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Reconciliation failed for game %s; plays data still usable.",
                    game_id,
                    exc_info=True,
                )

        # Return CANONICAL deduped ids -- the single propagation point for the
        # three plays-derived rate queries' game-id scope (E-244 TN-3 site 3).
        return canonical_ids

    except CredentialExpiredError:
        raise
    except Exception:  # noqa: BLE001
        # Real failure (not "no plays found"). Signal it via recon_out so the
        # caller records plays_status="failed" rather than treating the []
        # return as success (E-235 Phase 4b HIGH-2). Still non-fatal: generation
        # continues without plays data.
        if recon_out is not None:
            recon_out.failed = True
        logger.warning(
            "Plays crawl/load/reconcile failed for public_id=%s; "
            "continuing without plays data.",
            public_id,
            exc_info=True,
        )
        return []


# Empty-result payload for ``_query_plays_team_stats`` -- returned when there
# are no scoped games or no plays data.  Single source so the two early-return
# sites cannot drift (E-247-05 AC-3).  Callers return a copy: the caller may
# mutate the returned dict, so each call must get a fresh dict.
_EMPTY_PLAYS_TEAM: dict = {
    "team_fps_pct": None,
    "team_pitches_per_pa": None,
    "team_qab_pct": None,
    "has_plays_data": False,
    "plays_game_count": 0,
    "pitch_charted_game_count": 0,
}


def _plays_scope(
    team_id: int,
    season_id: str,
    game_ids: list[str] | None,
    *,
    restrict_team_games: bool,
) -> tuple[str, str, list]:
    """Build the one varying piece of the three ``_query_plays_*`` queries.

    The plays queries are identical except for how they restrict the ``plays``
    set to a report's games (E-247-05 AC-1).  Two scopes:

    - **game_ids-IN** (``game_ids`` is a non-empty list): ``p.game_id IN (...)``
      with no ``games`` JOIN -- the id list already restricts the games (E-211
      exact scoping).
    - **season-JOIN** (``game_ids`` is ``None``): ``JOIN games g`` and filter
      ``g.season_id = ?``, plus -- when ``restrict_team_games`` -- the team's
      own games via ``(g.home_team_id = ? OR g.away_team_id = ?)``.

    ``restrict_team_games`` is ``True`` for the perspective/pitcher queries that
    bound to the team's own games via home/away, and ``False`` for the
    batting-side queries that bound via ``batting_team_id`` in the caller's own
    predicates (so the season scope is ``g.season_id = ?`` alone; the IN scope
    never needs home/away either).

    Returns ``(games_join_sql, scope_where_sql, scope_params)``.  Callers
    compose ``SELECT ... FROM plays p {games_join_sql} {own JOINs} WHERE
    {scope_where_sql} {own predicates} {GROUP BY}`` and bind params in the order
    the ``?`` appear: any params from JOINs injected before the WHERE, then
    ``scope_params``, then the caller's trailing-predicate params.

    The empty-``game_ids`` case (which would yield an invalid ``IN ()``) is
    guarded by each caller BEFORE calling this builder, exactly as the prior
    code did -- so this builder is only reached with a non-empty list or ``None``.
    """
    if game_ids is not None:
        placeholders = ",".join("?" for _ in game_ids)
        return "", f"p.game_id IN ({placeholders})", list(game_ids)

    where = "g.season_id = ?"
    params: list = [season_id]
    if restrict_team_games:
        where += " AND (g.home_team_id = ? OR g.away_team_id = ?)"
        params += [team_id, team_id]
    return "JOIN games g ON g.game_id = p.game_id", where, params


def _query_plays_pitching_stats(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    game_ids: list[str] | None = None,
) -> dict[str, dict]:
    """Aggregate plays-derived pitching stats grouped by pitcher_id.

    When ``game_ids`` is provided, scopes to exactly those games (E-211:
    prevents cross-pipeline game leakage).  Falls back to team_id scope.

    Returns dict keyed by player_id with ``fps_pct`` and ``pitches_per_bf``.

    FPS% and P-BF denominators count only CHARTED PAs (``pitch_count > 0``)
    per E-245 TN-5: an un-charted PA (no pitch-by-pitch data) carries
    ``pitch_count = 0`` and would otherwise dilute the rate toward zero.  The
    numerators (``is_first_pitch_strike`` sum, ``pitch_count`` sum) are already
    zero for un-charted PAs, so gating only the denominator is the whole fix.
    """
    if game_ids is not None and not game_ids:
        return {}
    games_join, scope_where, scope_params = _plays_scope(
        team_id, season_id, game_ids, restrict_team_games=True,
    )
    rows = conn.execute(
        f"""
        SELECT
            p.pitcher_id,
            SUM(p.is_first_pitch_strike) AS fps_sum,
            SUM(CASE WHEN p.pitch_count > 0 THEN 1 ELSE 0 END) AS fps_denom,
            SUM(p.pitch_count) AS total_pitches,
            SUM(CASE WHEN p.pitch_count > 0 THEN 1 ELSE 0 END) AS total_bf
        FROM plays p
        {games_join}
        WHERE {scope_where}
          AND p.perspective_team_id = ?
          AND p.pitcher_id IS NOT NULL
        GROUP BY p.pitcher_id
        """,
        [*scope_params, team_id],
    ).fetchall()

    result: dict[str, dict] = {}
    for row in rows:
        pitcher_id = row[0]
        fps_sum, fps_denom = row[1], row[2]
        total_pitches, total_bf = row[3], row[4]
        fps_pct = (fps_sum / fps_denom) if fps_denom and fps_denom > 0 else None
        pitches_per_bf = (total_pitches / total_bf) if total_bf and total_bf > 0 else None
        result[pitcher_id] = {
            "fps_pct": fps_pct,
            "pitches_per_bf": pitches_per_bf,
        }
    return result


def _query_plays_batting_stats(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    game_ids: list[str] | None = None,
) -> dict[str, dict]:
    """Aggregate plays-derived batting stats grouped by batter_id.

    When ``game_ids`` is provided, scopes to exactly those games (E-211).
    Falls back to season_id + batting_team_id scope.

    Returns dict keyed by player_id with ``qab_pct`` and ``pitches_per_pa``.

    Denominator policy (E-245 TN-5):
    - QAB% KEEPS its all-PA denominator (every PA is a QAB opportunity,
      regardless of whether pitches were charted) -- NOT gated on
      ``pitch_count > 0``.
    - P-PA counts only CHARTED PAs (``pitch_count > 0``) so un-charted PAs do
      not dilute the rate.
    """
    if game_ids is not None and not game_ids:
        return {}
    games_join, scope_where, scope_params = _plays_scope(
        team_id, season_id, game_ids, restrict_team_games=False,
    )
    rows = conn.execute(
        f"""
        SELECT
            p.batter_id,
            SUM(p.is_qab) AS qab_sum,
            SUM(p.pitch_count) AS total_pitches,
            COUNT(*) AS total_pa,
            SUM(CASE WHEN p.pitch_count > 0 THEN 1 ELSE 0 END) AS charted_pa
        FROM plays p
        {games_join}
        WHERE {scope_where}
          AND p.batting_team_id = ?
          AND p.perspective_team_id = ?
        GROUP BY p.batter_id
        """,
        [*scope_params, team_id, team_id],
    ).fetchall()

    result: dict[str, dict] = {}
    for row in rows:
        batter_id = row[0]
        qab_sum, total_pitches, total_pa, charted_pa = row[1], row[2], row[3], row[4]
        # QAB%: all-PA denominator (TN-5). P-PA: charted-PA denominator (TN-5).
        qab_pct = (qab_sum / total_pa) if total_pa and total_pa > 0 else None
        pitches_per_pa = (
            (total_pitches / charted_pa) if charted_pa and charted_pa > 0 else None
        )
        result[batter_id] = {
            "qab_pct": qab_pct,
            "pitches_per_pa": pitches_per_pa,
        }
    return result


def _query_plays_team_stats(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    game_ids: list[str] | None = None,
) -> dict:
    """Compute team-level plays aggregates and metadata.

    When ``game_ids`` is provided, scopes to exactly those games (E-211).
    Falls back to team_id scope.

    Returns dict with ``team_fps_pct``, ``team_pitches_per_pa``,
    ``team_qab_pct``, ``has_plays_data``, ``plays_game_count`` (games-with-plays,
    K -- drives QAB% coverage), and ``pitch_charted_game_count`` (N -- games with
    >=1 charted PA, drives FPS%/P-PA and the coverage badge).

    Two distinct coverage counts (E-245 TN-5): FPS%/P-PA are charted-gated, so
    they ride ``pitch_charted_game_count``; QAB% keeps its all-PA denominator,
    so it rides ``plays_game_count``.  ``has_plays_data`` is true when ANY plays
    rows exist (games-with-plays > 0), distinct from whether any were charted.
    """
    # Two perspective-scoped coverage counts in one pass:
    #   K = games with any plays rows; N = games with >=1 charted PA.
    if game_ids is not None and not game_ids:
        return dict(_EMPTY_PLAYS_TEAM)
    cov_join, cov_where, cov_params = _plays_scope(
        team_id, season_id, game_ids, restrict_team_games=True,
    )
    row = conn.execute(
        f"""
        SELECT
            COUNT(DISTINCT p.game_id),
            COUNT(DISTINCT CASE WHEN p.pitch_count > 0 THEN p.game_id END)
        FROM plays p
        {cov_join}
        WHERE {cov_where}
          AND p.perspective_team_id = ?
        """,
        [*cov_params, team_id],
    ).fetchone()
    plays_game_count = row[0] if row else 0
    pitch_charted_game_count = row[1] if row else 0
    has_plays_data = plays_game_count > 0

    if not has_plays_data:
        return dict(_EMPTY_PLAYS_TEAM)

    # Team FPS%: pitchers for this team (matched via roster). Denominator is
    # CHARTED BF only (pitch_count > 0) per TN-5.
    fps_join, fps_where, fps_params = _plays_scope(
        team_id, season_id, game_ids, restrict_team_games=True,
    )
    fps_row = conn.execute(
        f"""
        SELECT
            SUM(p.is_first_pitch_strike),
            SUM(CASE WHEN p.pitch_count > 0 THEN 1 ELSE 0 END)
        FROM plays p
        {fps_join}
        JOIN team_rosters tr ON tr.player_id = p.pitcher_id
            AND tr.team_id = ?
            AND tr.season_id = ?
        WHERE {fps_where}
          AND p.perspective_team_id = ?
          AND p.pitcher_id IS NOT NULL
        """,
        [team_id, season_id, *fps_params, team_id],
    ).fetchone()
    fps_sum = fps_row[0] if fps_row and fps_row[0] else 0
    fps_denom = fps_row[1] if fps_row and fps_row[1] else 0
    team_fps_pct = (fps_sum / fps_denom) if fps_denom > 0 else None

    # Team batting side: P/PA uses the CHARTED-PA denominator (TN-5); QAB% uses
    # the ALL-PA denominator (TN-5 -- every PA is a QAB opportunity).
    ppa_join, ppa_where, ppa_params = _plays_scope(
        team_id, season_id, game_ids, restrict_team_games=False,
    )
    ppa_row = conn.execute(
        f"""
        SELECT
            SUM(p.pitch_count),
            SUM(CASE WHEN p.pitch_count > 0 THEN 1 ELSE 0 END),
            SUM(p.is_qab),
            COUNT(*)
        FROM plays p
        {ppa_join}
        WHERE {ppa_where}
          AND p.batting_team_id = ?
          AND p.perspective_team_id = ?
        """,
        [*ppa_params, team_id, team_id],
    ).fetchone()
    total_pitches = ppa_row[0] if ppa_row and ppa_row[0] else 0
    charted_pa = ppa_row[1] if ppa_row and ppa_row[1] else 0
    qab_sum = ppa_row[2] if ppa_row and ppa_row[2] else 0
    all_pa = ppa_row[3] if ppa_row and ppa_row[3] else 0
    team_pitches_per_pa = (total_pitches / charted_pa) if charted_pa > 0 else None
    team_qab_pct = (qab_sum / all_pa) if all_pa > 0 else None

    return {
        "team_fps_pct": team_fps_pct,
        "team_pitches_per_pa": team_pitches_per_pa,
        "team_qab_pct": team_qab_pct,
        "has_plays_data": has_plays_data,
        "plays_game_count": plays_game_count,
        "pitch_charted_game_count": pitch_charted_game_count,
    }


# ── Report-time plausibility guard (E-257-03 / TN-4) ─────────────────────
#
# Fast render-time range-check on the TEAM-level headline rates. Complements
# (does not replace) the offline reconciliation scoreboard: it reproduces the
# operator's human-eyeball catch -- an 18x-off FPS shipped once was caught only
# by the operator -- at generation time. Advisory only: emits a WARNING naming
# the out-of-range rate; never blocks the render, auto-clamps, or discards.
# TEAM aggregates ONLY -- per-pitcher/per-batter rows are intentionally NOT
# checked (a legitimate small-sample reliever can be a real 0%/100% FPS;
# per-player flagging would flood the log and conflict with
# .claude/rules/display-philosophy.md "never flag small samples").
# ``team_fps_pct`` is a FRACTION (0-1); the bound is expressed as a fraction and
# rendered as a percent in the message.  Bounds are coach-confirmed (TN-4).
_FPS_PCT_MIN = 0.30
_FPS_PCT_MAX = 0.75
_PITCHES_PER_PA_MIN = 3.0
_PITCHES_PER_PA_MAX = 4.5


def _check_rate_plausibility(team_rates: dict) -> list[str]:
    """Range-check the team headline rates; return out-of-range messages.

    Pure comparison over already-computed values -- no query, no side effect.
    ``team_fps_pct`` is a fraction (0-1); ``team_pitches_per_pa`` is a raw
    pitches/PA rate. A ``None`` rate (no charted data) is skipped, not flagged.
    Returns an empty list when every present rate is within its plausible band.
    """
    messages: list[str] = []

    fps = team_rates.get("team_fps_pct")
    if fps is not None and not (_FPS_PCT_MIN <= fps <= _FPS_PCT_MAX):
        messages.append(
            f"team_fps_pct {fps * 100:.1f}% outside expected range "
            f"{_FPS_PCT_MIN * 100:.0f}-{_FPS_PCT_MAX * 100:.0f}% "
            "-- review before sharing"
        )

    ppa = team_rates.get("team_pitches_per_pa")
    if ppa is not None and not (
        _PITCHES_PER_PA_MIN <= ppa <= _PITCHES_PER_PA_MAX
    ):
        messages.append(
            f"team_pitches_per_pa {ppa:.2f} outside expected range "
            f"{_PITCHES_PER_PA_MIN:.1f}-{_PITCHES_PER_PA_MAX:.1f} "
            "-- review before sharing"
        )

    return messages


def _log_rate_plausibility_warnings(data: dict, slug: str) -> None:
    """Emit an operator WARNING per out-of-range TEAM headline rate.

    Thin wrapper over the pure :func:`_check_rate_plausibility` so the render
    call site is a single call and the wiring itself is unit-testable without a
    full ``generate_report()`` drive. Advisory only -- logging a WARNING never
    blocks the render or mutates the value.
    """
    for msg in _check_rate_plausibility(data):
        logger.warning("Report %s: %s", slug, msg)


# ── Tier-2 enrichment status (operator observability, E-233-04) ──────────
#
# Structured statuses distinguishing the three Tier-2 outcomes so an operator
# can detect when AI analysis was dropped rather than it vanishing silently.
# Medium observability: log/operator-level only -- no coach-visible label.
TIER2_SUCCESS = "success"
TIER2_UNAVAILABLE_NO_KEY = "unavailable-no-key"
TIER2_FAILED = "failed"

if TYPE_CHECKING:
    from src.reports.llm_analysis import EnrichedPrediction
    from src.reports.starter_prediction import StarterPrediction


def _run_tier2_enrichment(
    starter_prediction: StarterPrediction | None,
    pitching_history_rows: list[dict],
    *,
    team_name: str | None,
    team_record: str | None,
    reference_date: date | None,
    public_id: str,
) -> tuple[EnrichedPrediction | None, str | None]:
    """Run optional Tier-2 LLM enrichment, returning ``(prediction, status)``.

    ``status`` is one of :data:`TIER2_SUCCESS`,
    :data:`TIER2_UNAVAILABLE_NO_KEY`, :data:`TIER2_FAILED`, or ``None`` (the
    Tier-2 stage did not run).  The ``failed`` status is **cause-agnostic**
    (TN-4): it is read from the ``except`` branch, NOT from the exception type,
    so a parse failure after the retry, an HTTP/transport error, or a
    ``response_format``-400 all map to the same status.  The preserved WARNING
    carries the specific cause via ``exc_info`` for log triage.

    Suppress gate (E-253-07 / TN-2): when the deterministic Tier-1 prediction is
    absent or ``confidence == 'suppress'`` (reason ``insufficient_data`` OR
    ``unsupported_level``), enrichment is SKIPPED before any availability check
    or API call -- no LLM cost is spent, and the honest softened suppress copy
    renders alone.  Suppress is honest absence, not a degraded run, so the
    status is ``None`` ("enrichment did not run", the same NULL the run record
    already records when Tier-2 is not attempted) -- deliberately NOT a new
    enrichment_status enum value (the run-record CHECK admits only
    success/unavailable-no-key/failed/NULL).

    Non-fatal contract (TN-2): on failure this returns ``(None, TIER2_FAILED)``
    so the caller still renders the Tier-1 deterministic prediction.
    """
    if starter_prediction is None or starter_prediction.confidence == "suppress":
        logger.info(
            "Tier-2 LLM enrichment skipped for public_id=%s: Tier-1 prediction "
            "%s. No LLM call made; status=None (did not run).",
            public_id,
            "absent" if starter_prediction is None
            else f"suppressed ({starter_prediction.suppress_reason})",
        )
        return None, None

    from src.llm.openrouter import is_llm_available

    if not is_llm_available():
        logger.info(
            "Tier-2 LLM enrichment unavailable (no API key) for "
            "public_id=%s; rendering Tier-1 only. status=%s",
            public_id,
            TIER2_UNAVAILABLE_NO_KEY,
        )
        return None, TIER2_UNAVAILABLE_NO_KEY

    try:
        from src.reports.llm_analysis import enrich_prediction

        enriched = enrich_prediction(
            starter_prediction,
            pitching_history_rows,
            team_name=team_name,
            team_record=team_record,
            reference_date=reference_date,
        )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Tier-2 LLM enrichment failed for public_id=%s; "
            "continuing with Tier 1 only. status=%s",
            public_id,
            TIER2_FAILED,
            exc_info=True,
        )
        return None, TIER2_FAILED

    logger.info(
        "Tier-2 LLM enrichment succeeded for public_id=%s. status=%s",
        public_id,
        TIER2_SUCCESS,
    )
    return enriched, TIER2_SUCCESS


# ---------------------------------------------------------------------------
# Stuck-'generating' report reaper (E-252-08)
# ---------------------------------------------------------------------------

# Staleness threshold for the stuck-'generating' reaper. A reports row is created
# 'generating' (in _create_report_row) BEFORE the crawl/load/render pipeline runs;
# _update_report_ready / _update_report_failed transition it at the end. If the
# process dies mid-generation (SIGKILL, container restart, an uncaught crash
# OUTSIDE the failure handler) the row stays 'generating' forever -- the admin
# /admin/reports page meta-refreshes on it indefinitely and its delete affordance
# is hidden (gated on status != 'generating'). The reaper transitions such a row to
# 'failed' once its generation START (generated_at) is older than this threshold.
#
# Derivation (AC-5): the value MUST be >= the max realistic single-report
# end-to-end generation wall-time (crawl + load + spray + plays + render -- "a few
# minutes" per the `bb report generate` CLI help) PLUS a large safety margin, and
# MUST be well below the 14-day (_EXPIRY_DAYS) report expiry. 1 hour is ~10-20x a
# real single-report generation, so it never kills a LIVE (even cross-process)
# generation, yet reaps a genuinely-dead one the same day. It bounds ONE report's
# generation (generated_at is that report's START). Operator-tunable.
def generate_report(gc_url: str) -> GenerationResult:
    """Generate a standalone scouting report for a GameChanger team.

    Executes the full pipeline: parse URL, ensure team row, create reports row
    + run record, run scouting crawl/load, resolve gc_uuid, spray, plays /
    reconcile, query stats, render HTML, save file. Each stage writes its status
    and counts to the ``report_generation_runs`` row (E-235-02 / TN-2).

    Thin wrapper over :class:`_ReportGeneration`, which carries the cross-stage
    state and the run-record handle. Behavior is unchanged from the prior
    monolithic implementation except for the new run record.

    Args:
        gc_url: A GameChanger team URL, bare public_id, or bare UUID.

    Returns:
        A :class:`GenerationResult` with success/failure details.
    """
    # Opportunistic expired-report file cleanup (E-238-07). A cleanup failure
    # must NEVER block or fail generation (AC-3), so swallow everything.
    #
    # The connection is opened HERE, through this module's `get_connection`, and
    # injected (E-256-04, CR round 1). `cleanup_expired_reports` lives in the
    # lifecycle module now, so calling it no-arg would make it resolve
    # `lifecycle.get_connection` -- the real `data/app.db` -- while every caller's
    # test sandbox patches `generator.get_connection`. The swallow below would
    # then hide the fact that the sweep ran against production data. Passing the
    # connection keeps the sandbox attached across the module boundary.
    #
    # Logged at ERROR, not WARNING: after the extraction this handler guards a
    # cross-module call, and a swallow that has never fired is indistinguishable
    # from one that fires every run.
    try:
        with closing(get_connection()) as cleanup_conn:
            cleanup_expired_reports(cleanup_conn)
    except Exception:  # noqa: BLE001
        logger.error(
            "Opportunistic expired-report cleanup failed; continuing generation",
            exc_info=True,
        )

    return _ReportGeneration(gc_url).run()


class _ReportGeneration:
    """One report-generation pipeline run.

    Carries cross-stage state (public-API team metadata, ``team_id``,
    ``crawl_result``, ``season_id``, resolved gc_uuid, plays game ids, the
    pre-run team-id snapshot) and the run-record handle (``report_id``) across
    the named stage methods. ``run()`` orchestrates the stages in the SAME
    order as the prior monolithic ``generate_report`` and preserves its exact
    control flow -- the two-tier crawl/load fail contract, the non-fatal
    spray/plays/reconciliation semantics, and the snapshot boundary -- adding
    only the per-stage run-record writes (TN-2).
    """

    def __init__(self, gc_url: str) -> None:
        self.gc_url = gc_url
        # Public-API team metadata (step 1b).
        self.public_id: str | None = None
        self.team_name_from_api: str | None = None
        self.season_year_from_api: int | None = None
        self.season_from_api: str | None = None
        self.ngb_from_api: str | None = None
        self.age_group_from_api: str | None = None
        # Identity (step 2). identity_match_method is stashed here and written
        # when the run row is created (TN-2 run-row-creation timing); story 03
        # populates the actual value from the extended ensure_team_row return.
        self.team_id: int | None = None
        self.identity_match_method: str | None = None
        # Report + run record (step 3).
        self.slug: str | None = None
        self.generated_at: str | None = None
        self.expires_at: str | None = None
        self.report_id: int | None = None
        # Pipeline state (step 4).
        self.client: GameChangerClient | None = None
        self.crawl_result = None
        self.season_id: str | None = None
        self.load_result = None
        self.resolved_gc_uuid: str | None = None
        self.plays_game_ids: list[str] = []
        self.completed_games: int = 0
        self.spray_games: int | None = None
        # Orphan determination (post-pipeline). The in-memory per-run
        # created-set (E-235-04 / TN-4) records the team ids THIS run INSERTed
        # during the scouting load (threaded through ScoutingLoader -> GameLoader
        # -> ensure_team_row_with_provenance). Replacing the old global pre/post
        # snapshot diff with this set closes the cross-process team-deletion race:
        # each generate_report() call deletes only the stubs it created, never a
        # concurrent run's freshly-created (and possibly shared) teams.
        self.created_team_ids: set[int] = set()
        self.orphan_ids: set[int] = set()
        # Render outputs.
        self.title: str | None = None
        self.team_info: dict | None = None

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------
    def run(self) -> GenerationResult:
        # Step 1: Parse URL
        parse_error = self._parse_url()
        if parse_error is not None:
            return parse_error

        # Step 1b: public team info (no auth)
        self._fetch_public_team_info()

        # Steps 2+3: ensure the team row and create the 'generating' reports row
        # (plus its run record) in ONE transaction on ONE connection, committed
        # once in FK order teams -> reports -> run-record (E-273-03 / TN-5/TN-6).
        # This closes the pre-reports-row concurrency window: a scouted teams row
        # is never visible without its protecting 'generating' reports row, so the
        # reclamation sweep's reap-then-gate guard can never see an in-flight
        # generation's team as an orphan. A failure between the two writes rolls
        # back BOTH (the connection closes without a commit), never leaving a
        # committed team without its report.
        with closing(get_connection()) as conn:
            self._ensure_team_row(conn)
            self._create_report_and_run_record(conn)
            conn.commit()

        # Step 4: scouting crawl/load/spray/plays pipeline. The scouting load
        # records every opponent stub it INSERTs into self.created_team_ids
        # (TN-4), so no pre-load team-id snapshot is taken.
        pipeline_error = self._run_pipeline()
        if pipeline_error is not None:
            return pipeline_error

        # Orphan determination from the per-run created-set (TN-4) -- only teams
        # THIS run inserted, never a concurrent run's teams.
        self._compute_orphans()

        # Step 5: query, render, save, finalize
        return self._query_render_save()

    # ------------------------------------------------------------------
    # Stage methods
    # ------------------------------------------------------------------
    def _parse_url(self) -> GenerationResult | None:
        """Step 1: parse the GC URL. Returns a failure result on bad input."""
        try:
            parsed = parse_team_url(self.gc_url)
        except ValueError as exc:
            return GenerationResult(success=False, error_message=str(exc))

        if parsed.is_uuid:
            return GenerationResult(
                success=False,
                error_message="UUID-based URLs are not supported for report generation. "
                "Please use a public team URL (with a public_id slug).",
            )

        self.public_id = parsed.value
        return None

    def _fetch_public_team_info(self) -> None:
        """Step 1b: fetch team name + season year from the public API (no auth).

        DO NOT split this into per-field or per-signal error handling.

        The coarseness is load-bearing safety, not sloppiness.  All five signals
        (`team_name`, `season_year`, `season`, `ngb`, `age_group`) are assigned
        together inside the single 200-block from one parsed payload, so any
        failure leaves them ALL None.  Four of the five feed league detection
        (`season_year` is used for the team row, not the gate), and with those
        four None::

            detect_league_level(ngb=None, age_group=None, team_name=None,
                                season=None)          # -> "unknown"
            get_rules_for_league("unknown", ref_date)  # -> None

        so the Most Likely Arms card SUPPRESSES.  Degrading to "no card" is the
        safe direction for a pitch-count gate.

        Granular handling would BREAK that.  If `season` could fail while
        `team_name` survived, a summer opponent named "...Varsity" would resolve
        `nsaa_varsity` (the season-absent default) instead of `legion` -- and
        NSAA Varsity UNDER-rests relative to Legion at 46-50p, 61-70p and 81-90p
        (and permits 110 pitches post-April vs 105).  That is a silent
        under-rest recommendation on a real arm, which is strictly worse than
        showing no card.  An isolated `season=None` alongside a usable
        `team_name` is not a shape this function can currently produce; keep it
        that way.  See IDEA-168 for the related season-vocabulary trigger.
        """
        try:
            from src.http.session import create_session

            session = create_session()
            resp = session.get(
                f"https://api.team-manager.gc.com/public/teams/{self.public_id}",
                timeout=15,
            )
            if resp.status_code == 200:
                pub_data = resp.json()
                self.team_name_from_api = pub_data.get("name")
                ts = pub_data.get("team_season") or {}
                self.season_year_from_api = ts.get("year")
                # Season string ("summer") disambiguates spring NSAA from the
                # summer Legion/NRBL family in detect_league_level (E-272).
                self.season_from_api = ts.get("season")
                self.ngb_from_api = pub_data.get("ngb")
                self.age_group_from_api = pub_data.get("age_group")
            else:
                # Observability only -- the control flow above is unchanged and
                # deliberately so.  Without this the non-200 path was entirely
                # silent (the except-handler below never fires for it), so a
                # suppressed card had no operator-visible cause.
                logger.warning(
                    "Public team info for %s returned HTTP %s -- league signals "
                    "unavailable, starter card will suppress",
                    self.public_id,
                    resp.status_code,
                )
            session.close()
        except Exception as exc:  # noqa: BLE001
            # No status code here on purpose: `resp` is unbound when the request
            # itself raised (timeout / DNS / TLS), so the exception is the only
            # cause available.
            logger.warning(
                "Could not fetch public team info for %s (%s: %s)",
                self.public_id,
                type(exc).__name__,
                exc,
            )

    def _ensure_team_row(self, conn: sqlite3.Connection | None = None) -> None:
        """Step 2: ensure the team row exists; backfill name/season/public_id.

        Captures the identity ``match_method`` (gate (c), TN-3) from the
        provenance-returning variant and stashes it on the context; it is
        written to the run record when that row is created (the run row does
        not exist yet here -- deferred write, SE-F3).

        Connection-injection (E-273-03 / TN-6): with ``conn=None`` (the default,
        preserving the standalone IDEA-127 test callers) this opens and COMMITS
        its own connection -- byte-identical to the pre-refactor behavior. When
        ``run()`` passes its shared ``conn``, this uses it and does NOT commit;
        the caller commits the teams row together with the reports row so the two
        are atomic.
        """
        owns_conn = conn is None
        cm = closing(get_connection()) if owns_conn else nullcontext(conn)
        with cm as conn:
            ensure_result = ensure_team_row_with_provenance(
                conn,
                public_id=self.public_id,
                name=self.team_name_from_api,
                season_year=self.season_year_from_api,
                source="report_generator",
            )
            self.team_id = ensure_result.team_id
            # Stash for deferred write at run-row creation (gate (c)).
            self.identity_match_method = ensure_result.match_method
            # ensure_team_row doesn't overwrite existing names (conservative
            # backfill). Force-update name/season_year from the public API when
            # available, since earlier failed attempts may have left the row
            # with placeholder values.
            if self.team_name_from_api:
                conn.execute(
                    "UPDATE teams SET name = ?, season_year = COALESCE(?, season_year) "
                    "WHERE id = ?",
                    (self.team_name_from_api, self.season_year_from_api, self.team_id),
                )
                # Backfill public_id when ensure_team_row matched by
                # name+season_year and left public_id NULL. Safe: AND public_id
                # IS NULL guard prevents overwriting a more-authoritative value.
                try:
                    result = conn.execute(
                        "UPDATE teams SET public_id = ? WHERE id = ? AND public_id IS NULL",
                        (self.public_id, self.team_id),
                    )
                    if result.rowcount > 0:
                        logger.info(
                            "Backfilled public_id=%s on team_id=%d",
                            self.public_id, self.team_id,
                        )
                        # IDEA-127: ensure_team_row matched this run's team as a
                        # name-only opponent stub (public_id NULL at cascade), so
                        # match_method came back name_only. When we establish a
                        # REAL public_id anchor within the same run, the team is
                        # not a low-trust name-only match -- downgrade the stamp
                        # to 'anchor' so the operator wrong-team badge does not
                        # fire on a correctly-resolved team.
                        #
                        # Guard is deliberately on a real anchor (self.public_id
                        # IS NOT NULL *and* rowcount > 0), not rowcount alone: the
                        # UPDATE's "WHERE public_id IS NULL" sets NULL->NULL with
                        # rowcount=1 when self.public_id is None, establishing no
                        # anchor -- so a genuinely unresolved name-only stub must
                        # keep recording name_only (AC-2). The == name_only check
                        # ensures we only downgrade, never disturb a genuine
                        # anchor stamp.
                        if (
                            self.public_id is not None
                            and self.identity_match_method == MATCH_NAME_ONLY
                        ):
                            self.identity_match_method = MATCH_ANCHOR
                except sqlite3.IntegrityError:
                    logger.warning(
                        "Could not backfill public_id=%s on team_id=%d — "
                        "another team already has this public_id",
                        self.public_id, self.team_id,
                    )
            if owns_conn:
                conn.commit()

    def _create_report_and_run_record(
        self, conn: sqlite3.Connection | None = None
    ) -> None:
        """Step 3: create the reports row, then its run record (FK order).

        Connection-injection (E-273-03 / TN-6): with ``conn=None`` (default) this
        opens its own connection and the row-insert helpers commit internally --
        backward-compatible. When ``run()`` passes its shared ``conn``, the
        helpers are told NOT to commit (``commit=owns_conn``); the caller issues
        the single teams -> reports -> run-record commit so the team is never
        committed without its 'generating' reports row.
        """
        self.slug = secrets.token_urlsafe(12)
        self.generated_at = utcnow_iso()
        expires_dt = datetime.now(timezone.utc) + timedelta(days=_EXPIRY_DAYS)
        self.expires_at = expires_dt.strftime(UTC_ISO_FORMAT)

        owns_conn = conn is None
        cm = closing(get_connection()) if owns_conn else nullcontext(conn)
        with cm as conn:
            initial_title = (
                f"Scouting Report — {self.team_name_from_api or self.public_id}"
            )
            self.report_id = _create_report_row(
                conn, self.slug, self.team_id, initial_title,
                self.generated_at, self.expires_at,
                commit=owns_conn,
            )
            # The run row FK-references the reports row. Stashed pre-run signals
            # (identity_match_method) are written here (TN-2).
            _create_run_record(
                conn, self.report_id, self.generated_at,
                identity_match_method=self.identity_match_method,
                commit=owns_conn,
            )

    def _run_pipeline(self) -> GenerationResult | None:
        """Step 4: crawl/load/gc_uuid/spray/plays. Returns a failure result on
        a fatal (two-tier) error, else ``None`` to continue."""
        try:
            self.client = GameChangerClient()
            with closing(get_connection()) as conn:
                crawler = ScoutingCrawler(self.client, conn)
                self.crawl_result = crawler.scout_team(self.public_id)

            # M = distinct completed games on the fetched schedule (TN-2 SE-F4).
            self.completed_games = _count_completed_games(self.crawl_result.games)
            # boxscores_fetched (TN-2) = boxscores successfully fetched. For the
            # boxscore crawl, games_crawled < M only happens via a fetch error
            # (empty-but-fetched bodies still increment games_crawled), so a
            # coverage shortfall here IS an honest error signal (TN-1/TN-7) --
            # unlike plays/spray, where shortfall is routine.
            boxscores_fetched = self.crawl_result.games_crawled

            # Two-tier fail contract (tier 1) -- repaired per SQ1 / TN-6 (FINAL,
            # Jason signed off 2026-06-14). An ALL-BLOCKED crawl (M>0 completed
            # games on the schedule but ZERO boxscores fetched) means every
            # fetch was blocked (403 / auth-expiry / transient mass-failure),
            # NOT that no data exists -- so fail HARD (no shareable page) instead
            # of slipping silently to a misleading no_games outcome. The
            # count-based ``completed_games > 0`` disjunct is the SQ1 repair; the
            # ``errors > 0`` disjunct preserves the pre-existing total-failure
            # cases (schedule / roster fetch failure -> M==0 but errors==1, which
            # must stay fatal rather than degrade to no_games).
            if boxscores_fetched == 0 and (
                self.crawl_result.errors > 0 or self.completed_games > 0
            ):
                _update_run_record(
                    self.report_id, crawl_status=STATUS_FAILED,
                    completed_games=self.completed_games,
                    boxscores_fetched=boxscores_fetched,
                )
                _finalize_run_record(
                    self.report_id, "failed", error_stage="crawl",
                    error_message="Scouting crawl failed — no data retrieved.",
                )
                _fail_report(self.report_id, "Scouting crawl failed — no data retrieved.")
                return GenerationResult(
                    success=False, slug=self.slug,
                    error_message="Scouting crawl failed.", outcome="failed",
                )

            # Honest crawl status (AC-1/2/4 / TN-7): derive completed vs partial
            # from boxscores_fetched vs M via the shared classifier. errors=0
            # because the coverage shortfall IS the boxscore-crawl error signal
            # (passing crawl_result.errors would double-count); the all-blocked
            # failed case is already intercepted by the fatal gate above.
            crawl_status = classify_stage_status(
                loaded=boxscores_fetched, errors=0, expected=self.completed_games,
            )
            _update_run_record(
                self.report_id, crawl_status=crawl_status,
                completed_games=self.completed_games,
                boxscores_fetched=boxscores_fetched,
            )

            # Derive the canonical DB season_id from team metadata.
            with closing(get_connection()) as conn:
                self.season_id, _ = derive_season_id_for_team(
                    conn, self.team_id,
                )
            # Guarantee the season row exists so season_id_used (FK) is safe to
            # write even when the loader early-returns without committing (the
            # no-games path). Idempotent.
            with closing(get_connection()) as conn:
                ensure_season_row(conn, self.season_id)
                conn.commit()
            # Record the season used for this run.
            _update_run_record(
                self.report_id,
                season_id_used=self.season_id,
            )

            # Run the loader with the in-memory crawl result. Pass the per-run
            # created-set so opponent stubs INSERTed during the load are recorded
            # for run-scoped orphan cleanup (TN-4) instead of a snapshot diff.
            with closing(get_connection()) as conn:
                loader = ScoutingLoader(conn, created_team_ids=self.created_team_ids)
                self.load_result = loader.load_team(self.crawl_result)

            # load_errors is the RECORD-level error tally (LoadResult.errors;
            # +1 per failed game upsert OR per failed player stat row) written
            # for operator drill-down (E-236-09 AC-1 / TN-2).
            load_errors = self.load_result.errors

            # Two-tier fail contract (tier 2): load guard fires only on
            # errors > 0 AND loaded == 0. This is the load stage's OWN explicit
            # total-failure signal -> map to "failed" BEFORE the classifier
            # (TN-1 precedence; mirrors stories 02/03). Covers the keyless /
            # unreadable-boxscore degenerate case (DE sub-case B, defensive).
            if self.load_result.loaded == 0 and self.load_result.errors > 0:
                _update_run_record(
                    self.report_id, load_status=STATUS_FAILED,
                    load_errors=load_errors,
                )
                _finalize_run_record(
                    self.report_id, "failed", error_stage="load",
                    error_message="Scouting load failed — no data loaded.",
                )
                _fail_report(self.report_id, "Scouting load failed — no data loaded.")
                return GenerationResult(
                    success=False, slug=self.slug, error_message="Scouting load failed."
                )

            # ERROR-driven status via the shared classifier (AC-2 / TN-1
            # guardrail + DE CAUTION 1). The total-failure case is already
            # handled above (precedence), so here some rows loaded (or nothing
            # was attempted): classify(1, load_errors, 1) -> errors == 0 ->
            # completed; errors > 0 (loaded == expected == 1) -> partial. The
            # realistic scored-but-empty boxscore (DE sub-case A: team keys
            # present, stat groups empty) takes the error-free branch ->
            # errors == 0 -> completed, so it is NOT falsely marked partial
            # (AC-4 false-alarm guard, same class as plays/spray).
            #
            # DE CAUTION 1: the loaded=1/expected=1 below is DEGENERATE
            # single-unit coverage (the load is treated as ONE unit of work) --
            # it is NOT LoadResult.loaded, which is a RECORD count (+1 per game
            # AND +1 per player row, dimensionally incoherent as a coverage
            # numerator: a scored-but-empty game has loaded=1, a normal game
            # 1+N). Do NOT "fix" these literals to LoadResult.loaded.
            load_status = classify_stage_status(
                loaded=1, errors=load_errors, expected=1,
            )
            _update_run_record(
                self.report_id, load_status=load_status, load_errors=load_errors,
            )

            # Re-read team_info AFTER crawl/load so name is populated from schedule.
            with closing(get_connection()) as conn:
                self.team_info = _query_team_info(conn, self.team_id)

            self.title = f"Scouting Report — {self.team_info['name']}"

            # Update the placeholder title with the real team name.
            with closing(get_connection()) as conn:
                conn.execute(
                    "UPDATE reports SET title = ? WHERE id = ?",
                    (self.title, self.report_id),
                )
                conn.commit()

            # Gate (a): no-completed-games -- ABORT to an explicit, shareable
            # no-games outcome instead of a silent empty "ready" report (TN-3).
            no_games_result = self._no_games_gate()
            if no_games_result is not None:
                return no_games_result

            # Step 4b: gc_uuid resolution.
            self._resolve_gc_uuid_stage()

            # Step 4c: spray chart crawl/load (in-memory -- E-220-06).
            self._spray_stage()

            # Step 4d: plays crawl/load/reconcile (in-memory -- E-220-06).
            self._plays_stage()

        except CredentialExpiredError:
            msg = "Authentication credentials expired — refresh with `bb creds setup web`"
            _finalize_run_record(
                self.report_id, "failed", error_stage="pipeline", error_message=msg,
            )
            _fail_report(self.report_id, msg)
            return GenerationResult(success=False, slug=self.slug, error_message=msg)
        except Exception as exc:  # noqa: BLE001
            msg = f"Pipeline error: {exc}"
            logger.exception("Report generation pipeline failed")
            _finalize_run_record(
                self.report_id, "failed", error_stage="pipeline", error_message=msg,
            )
            _fail_report(self.report_id, msg)
            return GenerationResult(success=False, slug=self.slug, error_message=msg)

        return None

    def _no_games_gate(self) -> GenerationResult | None:
        """Gate (a): the no-completed-games quality gate (TN-3).

        N (``completed_games_with_data``) is the ``_query_freshness`` count of
        distinct completed games we actually have stat data for. When N == 0 the
        report would be empty, so instead of rendering a silent empty "ready"
        report we produce an explicit, shareable no-games outcome:
        ``reports.status = 'no_games'`` + a minimal explanatory page on disk.

        The run record captures the M=0 vs N=0 distinction via
        ``completed_games`` (M, already written at the crawl stage) and
        ``completed_games_with_data`` (N, written here).

        Returns:
            A terminal :class:`GenerationResult` when the gate fires, else
            ``None`` to continue the pipeline.
        """
        with closing(get_connection()) as conn:
            _freshness_date, game_count = _query_freshness(
                conn, self.team_id, self.season_id,
            )

        if game_count > 0:
            # Has data -- record N and continue. (The render stage also records
            # N; writing it here keeps the run record correct even though the
            # gate did not fire.)
            _update_run_record(
                self.report_id, completed_games_with_data=game_count,
            )
            return None

        # Zero completed games with data -> explicit no-games terminal outcome.
        team_name = (
            (self.team_info or {}).get("name")
            or self.team_name_from_api
            or self.public_id
        )
        _update_run_record(self.report_id, completed_games_with_data=0)

        # Write the minimal shareable page and flip reports.status to 'no_games'
        # (free-text TEXT column -- no migration). The public serve route serves
        # 'no_games' like 'ready', so the shared link renders the message.
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = f"reports/{self.slug}.html"
        file_path = _REPO_ROOT / "data" / report_path
        # M = games played to date (already counted at the crawl stage); N = 0
        # here by construction (this branch only runs when game_count == 0). The
        # renderer branches the copy on M vs N (TN-5).
        file_path.write_text(
            render_no_games_page(team_name, self.completed_games, 0),
            encoding="utf-8",
        )
        with closing(get_connection()) as conn:
            conn.execute(
                "UPDATE reports SET status = 'no_games', report_path = ? WHERE id = ?",
                (report_path, self.report_id),
            )
            conn.commit()

        # Orphan cleanup on the abort path too, so it stays symmetric with the
        # normal render path (a true no-op here -- the N==0 firing condition
        # created no opponent stubs). Story 04 reworks orphan handling and
        # inherits this symmetric structure.
        self._compute_orphans()
        self._cleanup_orphans()

        _finalize_run_record(self.report_id, "completed")
        logger.info(
            "No completed games with data for public_id=%s (M=%d, N=0); "
            "wrote no-games page slug=%s",
            self.public_id, self.completed_games, self.slug,
        )

        msg = (
            f"No completed games found for {team_name} this season. "
            "If this looks wrong, verify the team URL and try again."
        )
        url = f"{_get_base_url()}/reports/{self.slug}"
        return GenerationResult(
            success=False, slug=self.slug, title=self.title, url=url,
            error_message=msg, outcome="no_games",
            # M / N for the CLI to print an honest M-vs-N message (Phase 4b
            # MEDIUM). N is 0 here by construction (this gate fires on N==0).
            completed_games=self.completed_games,
            completed_games_with_data=0,
        )

    def _resolve_gc_uuid_stage(self) -> None:
        """Step 4b: resolve gc_uuid for spray-chart access.

        Tracked teams always search-resolve (stored gc_uuid may be contaminated
        by opponent-perspective boxscore keys -- see E-211). Member teams use
        the stored gc_uuid (from the authenticated API).
        """
        self.resolved_gc_uuid = None
        with closing(get_connection()) as conn:
            row = conn.execute(
                "SELECT gc_uuid, membership_type FROM teams WHERE id = ?",
                (self.team_id,),
            ).fetchone()
            existing_gc_uuid = row[0] if row else None
            membership_type = row[1] if row else "tracked"

        if membership_type == "member" and existing_gc_uuid:
            self.resolved_gc_uuid = existing_gc_uuid
        elif self.team_info.get("name"):
            self.resolved_gc_uuid = _resolve_gc_uuid(
                self.client, self.team_info["name"], self.public_id,
            )
            if self.resolved_gc_uuid:
                with closing(get_connection()) as conn:
                    conn.execute(
                        "UPDATE teams SET gc_uuid = ? WHERE id = ? "
                        "AND membership_type = 'tracked'",
                        (self.resolved_gc_uuid, self.team_id),
                    )
                    conn.commit()

        # Fetch the ERA basis whenever a gc_uuid is available -- from EITHER
        # resolution branch (member or search) -- and independently of spray
        # (E-264 TN-6). Non-fatal: a failure leaves the stored basis unchanged.
        if self.resolved_gc_uuid:
            self._fetch_and_store_innings_per_game()

        _update_run_record(
            self.report_id,
            gc_uuid_status="resolved" if self.resolved_gc_uuid else "unavailable",
        )

    def _fetch_and_store_innings_per_game(self) -> None:
        """Fetch the team's ERA basis (innings/game) and store it (E-264 TN-6).

        The basis lives ONLY on the authenticated ``GET /teams/{gc_uuid}`` team
        detail (``settings.scorekeeping.bats.innings_per_game``), not on the
        public profile, so this runs after gc_uuid resolution. Non-fatal
        (AC-2), mirroring the spray-chart resilience posture: a raised 403
        (``ForbiddenError``, a subclass of ``CredentialExpiredError`` -- known
        for some non-owned teams) or any other failure is caught and logged,
        generation continues, and the stored basis is left UNCHANGED. The write
        routes through :func:`ensure_team_row`, whose NULL-safe backfill fills an
        existing NULL but never clobbers a stored integer (TN-4); it commits so
        the value is visible to the later ``get_season_pitching`` read within
        this same generation. The network fetch runs BEFORE any write connection
        is opened, so no write transaction is held across the fetch.
        """
        try:
            data = self.client.get(
                f"/teams/{self.resolved_gc_uuid}",
                accept=TEAM_DETAIL_ACCEPT,
            )
        except CredentialExpiredError as exc:
            logger.warning(
                "innings_per_game fetch: GET /teams/%s denied (%s); leaving "
                "basis unchanged (ERA falls back to 7)",
                self.resolved_gc_uuid, exc.__class__.__name__,
            )
            return
        except Exception:  # noqa: BLE001
            logger.warning(
                "innings_per_game fetch failed for gc_uuid=%s; leaving basis "
                "unchanged (ERA falls back to 7)",
                self.resolved_gc_uuid, exc_info=True,
            )
            return

        basis = _extract_innings_per_game(data)
        if basis is None:
            logger.info(
                "innings_per_game absent from team detail for gc_uuid=%s; "
                "leaving basis unchanged (ERA falls back to 7)",
                self.resolved_gc_uuid,
            )
            return

        with closing(get_connection()) as conn:
            ensure_team_row(
                conn,
                name=self.team_info.get("name") if self.team_info else None,
                gc_uuid=self.resolved_gc_uuid,
                public_id=self.public_id,
                innings_per_game=basis,
                source="report-era-basis",
            )
            conn.commit()
        logger.info(
            "innings_per_game=%d stored for gc_uuid=%s (ERA basis)",
            basis, self.resolved_gc_uuid,
        )

    def _spray_stage(self) -> None:
        """Step 4c: spray crawl/load (non-fatal). Records spray status + games.

        ``spray_status`` is ERROR-driven, NOT coverage-driven (E-236-04 / TN-7):
        spray is scorekeeper-dependent, so a coverage shortfall
        (``spray_games_with_data < spray_games``) is the NORMAL multi-game case
        and must NEVER register as "partial". Status flips off "completed" only
        on a real crawl/load error.
        """
        redirect_map = self.load_result.redirect_map if self.load_result else {}
        spray_outcome = _crawl_and_load_spray(
            self.client, self.public_id, self.season_id,
            gc_uuid=self.resolved_gc_uuid,
            games_data=self.crawl_result.games,
            team_id=self.team_id,
            redirect_map=redirect_map,
        )
        self.spray_games = _coerce_int(getattr(spray_outcome, "games_crawled", None))
        spray_games_with_data = _coerce_int(
            getattr(spray_outcome, "spray_games_with_data", None)
        )
        spray_errors = _coerce_int(getattr(spray_outcome, "errors", None)) or 0
        attempted = self.spray_games or 0

        # TN-1 precedence: map the stage's OWN explicit failure signal to
        # "failed" BEFORE the classifier, so the expected==0 -> completed branch
        # cannot mask a real total crawl failure (AC-4, mirrors story 02 AC-4).
        if getattr(spray_outcome, "status", None) == STATUS_FAILED:
            spray_status = STATUS_FAILED
        else:
            # ERROR-driven (AC-2/AC-3): loaded == expected == games attempted, so
            # only a non-zero error count flips status off "completed". The
            # informational coverage count is deliberately NOT an input here.
            spray_status = classify_stage_status(
                loaded=attempted, errors=spray_errors, expected=attempted,
            )

        _update_run_record(
            self.report_id,
            spray_status=spray_status,
            spray_games=self.spray_games,
            spray_games_with_data=spray_games_with_data,
        )

    def _plays_stage(self) -> None:
        """Step 4d: plays crawl/load/reconcile (non-fatal). Records plays +
        reconciliation status and counts.

        ``CredentialExpiredError`` here is non-fatal (caught locally, matching
        the prior behavior) -- it must NOT bubble to the pipeline-level handler.
        """
        self.plays_game_ids = []
        plays_games_expected = len(self.crawl_result.boxscores)
        recon = _ReconCounts()
        redirect_map = self.load_result.redirect_map if self.load_result else {}
        try:
            self.plays_game_ids = _crawl_and_load_plays(
                self.client, self.public_id, self.team_id, self.season_id,
                game_ids=sorted(self.crawl_result.boxscores.keys()),
                recon_out=recon,
                redirect_map=redirect_map,
            )
            # Sum the ERROR-driven count the run record records as plays_errors
            # (TN-2): per-game fetch failures + folded PlaysLoader load errors.
            plays_errors = recon.plays_fetch_failures + recon.plays_load_errors
            if recon.failed:
                # _crawl_and_load_plays swallowed a real (total) failure and
                # returned [] (HIGH-2). Per TN-1 precedence, a stage carrying its
                # OWN explicit failure signal maps to "failed" BEFORE the
                # classifier. Record the failure honestly -- NOT "completed" with
                # zero counts -- while keeping the stage non-fatal (no raise).
                _update_run_record(
                    self.report_id,
                    plays_status=STATUS_FAILED,
                    plays_games_expected=plays_games_expected,
                    plays_errors=plays_errors,
                    reconciliation_status="failed",
                )
                logger.warning(
                    "Plays stage failed for public_id=%s (swallowed error); "
                    "continuing without plays data.",
                    self.public_id,
                )
            else:
                # ERROR-driven classifier inputs (AC-2 / TN-7). loaded = games
                # whose fetch did NOT raise; errors = fetch failures + load
                # errors; expected = games ATTEMPTED (fetched_ok + fetch
                # failures). K (plays_games_covered, games with plays rows) is a
                # SEPARATE informational coverage number computed later in
                # _query_render_save -- it is NEVER the classifier's loaded.
                plays_status = classify_stage_status(
                    loaded=recon.plays_fetched_ok,
                    errors=plays_errors,
                    expected=recon.plays_fetched_ok + recon.plays_fetch_failures,
                )
                _update_run_record(
                    self.report_id,
                    plays_status=plays_status,
                    plays_games_expected=plays_games_expected,
                    plays_errors=plays_errors,
                    reconciliation_status="completed",
                    discrepancies_found=recon.discrepancies_found,
                    discrepancies_corrected=recon.discrepancies_corrected,
                )
        except CredentialExpiredError:
            _update_run_record(
                self.report_id, plays_status=STATUS_FAILED,
                plays_games_expected=plays_games_expected,
            )
            logger.warning(
                "Auth expired during plays stage for public_id=%s; "
                "continuing without plays data.",
                self.public_id,
            )
        except Exception:  # noqa: BLE001
            _update_run_record(
                self.report_id, plays_status=STATUS_FAILED,
                plays_games_expected=plays_games_expected,
            )
            logger.warning(
                "Plays stage failed for public_id=%s; continuing without plays data.",
                self.public_id,
                exc_info=True,
            )

    def _compute_orphans(self) -> None:
        """Compute orphan team IDs from the per-run created-set (TN-4).

        Orphans are exactly the teams THIS run INSERTed during the scouting load
        (``created_team_ids``), excluding the report team itself. Using the
        in-memory created-set instead of a global pre/post snapshot diff closes
        the cross-process race: a concurrent run's freshly-created teams are
        never in this run's set, so they can never be deleted here.
        """
        self.orphan_ids = self.created_team_ids - {self.team_id}

    def _cleanup_orphans(self) -> None:
        """Delete orphan teams created during this run (non-fatal).

        Shared by the normal render path and the no-games abort path so both
        run the same post-pipeline cleanup (path symmetry). A true no-op when
        ``orphan_ids`` is empty -- e.g. the N==0 no-games firing condition,
        where no opponent stubs were created.
        """
        if self.orphan_ids:
            try:
                with closing(get_connection()) as conn:
                    cleanup_orphan_teams(conn, self.orphan_ids)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Orphan cleanup failed for %d team(s); report continues.",
                    len(self.orphan_ids),
                    exc_info=True,
                )

    def _query_render_save(self) -> GenerationResult:
        """Step 5: query stats, render, save, mark ready, finalize the run.

        All in one failure-handling block so the report never gets stuck in
        'generating'. On success, writes N / plays-covered / enrichment-status
        counts and finalizes the run record as ``completed``.
        """
        team_id = self.team_id
        season_id = self.season_id
        report_id = self.report_id
        slug = self.slug
        generated_at = self.generated_at

        # The venue-local reference date, derived ONCE (E-256-05 / AC-1).
        #
        # `generated_at` is a UTC instant. Slicing its first ten characters gives
        # the UTC calendar date, which after ~19:00 venue time has already rolled
        # to tomorrow -- so an evening generation computed pitcher rest days and
        # the 7-day `pitches_7d` window against a date the coach has not reached.
        # This is the third site of the finding E-252 and E-253 fixed elsewhere.
        #
        # `derive_local_date` is the canonical converter and takes an IANA NAME,
        # so the operating-tz ZoneInfo is bridged via `.key`. The fallback below
        # is venue-local "today", never a UTC slice -- reintroducing one here is
        # the bug.
        #
        # It returns None for an absent instant, an unparseable one, and (since
        # E-278-04) a PRESENT-but-unresolvable timezone. That third case cannot
        # arise at THIS site: the zone comes from `get_operating_timezone()`,
        # which has already resolved it -- `.key` on a live ZoneInfo is by
        # construction a name this runtime resolves. The distinction matters
        # because it does not hold at the loader, whose zone is operator-typed
        # and arrives from a GameChanger payload.
        reference_date = (
            derive_local_date(generated_at, get_operating_timezone().key)
            or operating_today().isoformat()
        )
        # Adaptation, not a second derivation: two of the three consumers do date
        # arithmetic and need a `date`; `get_pitching_workload` takes the string
        # (its window is SQL `date(ref, '-6 days')`). One source, two shapes.
        reference_date_local = date.fromisoformat(reference_date)

        # Run-record counts captured during this stage (TN-2).
        completed_games_with_data: int | None = None
        plays_games_covered: int | None = None
        enrichment_status: str | None = None

        try:
            # Query BEFORE cleanup -- game-dependent queries need game rows
            with closing(get_connection()) as conn:
                conn.row_factory = sqlite3.Row
                batting = _query_batting(conn, team_id, season_id)
                pitching = _query_pitching(conn, team_id, season_id)
                roster = _query_roster(conn, team_id, season_id)
                record = _query_record(conn, team_id, season_id)
                recent_form = _query_recent_games(conn, team_id, season_id)
                freshness_date, game_count = _query_freshness(conn, team_id, season_id)
                # N = distinct completed games we actually have stat data for
                # (TN-2 SE-F2): the _query_freshness count, NOT load_result.loaded.
                completed_games_with_data = game_count
                spray_charts = _query_spray_charts(conn, team_id, season_id)
                runs_scored_avg, runs_allowed_avg = _query_runs_avg(
                    conn, team_id, season_id
                )

                # Pitching workload (7-day rolling window anchored on the
                # venue-local reference date, not the UTC generation date).
                pitching_workload = get_pitching_workload(
                    team_id, season_id, reference_date, db=conn,
                )

                # Predicted starter (Tier 1)
                starter_prediction = None
                enriched_prediction = None
                from src.reports.starter_prediction import (
                    is_predicted_starter_enabled,
                )
                show_predicted_starter = is_predicted_starter_enabled()
                if show_predicted_starter:
                    pitching_history_rows = get_pitching_history(
                        team_id, season_id, db=conn,
                    )
                    if pitching_history_rows:
                        from src.reports.starter_prediction import (
                            compute_starter_prediction,
                            detect_league_level,
                        )

                        league = detect_league_level(
                            ngb=self.ngb_from_api,
                            age_group=self.age_group_from_api,
                            team_name=self.team_name_from_api,
                            season=self.season_from_api,
                        )

                        pitcher_profiles = build_pitcher_profiles(
                            pitching_history_rows,
                        )
                        starter_prediction = compute_starter_prediction(
                            pitcher_profiles, pitching_history_rows,
                            reference_date=reference_date_local,
                            workload=pitching_workload,
                            league=league,
                        )

                        # Tier 2: LLM enrichment (optional, non-fatal). The
                        # helper emits an operator-detectable status for each of
                        # the three outcomes (success / unavailable-no-key /
                        # failed) and preserves the non-fatal contract (TN-2).
                        # enrichment_status IS the run record's enrichment_status.
                        team_record_str = None
                        if record:
                            team_record_str = (
                                f"{record['wins']}-{record['losses']}"
                            )
                        enriched_prediction, enrichment_status = _run_tier2_enrichment(
                            starter_prediction,
                            pitching_history_rows,
                            team_name=self.team_name_from_api,
                            team_record=team_record_str,
                            reference_date=reference_date_local,
                            public_id=self.public_id,
                        )

                # Outings Breakdown (E-265) -- mirrors the predicted-starter
                # wiring above: flag read + builder call INSIDE the DB scope so
                # the builder's own reads run on the open connection. The
                # builder returns [] on no pitching history (non-fatal empty
                # state), so no inner guard is needed here.
                pitcher_outings: list = []
                from src.reports.pitcher_outings import (
                    build_pitcher_outings,
                    is_pitcher_outings_enabled,
                )
                show_pitcher_outings = is_pitcher_outings_enabled()
                if show_pitcher_outings:
                    pitcher_outings = build_pitcher_outings(
                        conn, team_id, season_id,
                    )

                # Plays-derived stats
                plays_pitching = _query_plays_pitching_stats(
                    conn, team_id, season_id, game_ids=self.plays_game_ids,
                )
                plays_batting = _query_plays_batting_stats(
                    conn, team_id, season_id, game_ids=self.plays_game_ids,
                )
                plays_team = _query_plays_team_stats(
                    conn, team_id, season_id, game_ids=self.plays_game_ids,
                )
                # K = distinct games with plays/pitch-detail data (run record's
                # plays_games_covered; the footer's K).
                plays_games_covered = plays_team["plays_game_count"]

            # Build roster set for pitcher matching (pitching query returns all
            # pitchers in games involving this team; filter to team's own roster)
            with closing(get_connection()) as conn:
                roster_pids = {
                    row[0] for row in conn.execute(
                        "SELECT player_id FROM team_rosters WHERE team_id = ? AND season_id = ?",
                        (team_id, season_id),
                    ).fetchall()
                }
            for p in pitching:
                pid = p.get("player_id")
                if pid and pid in plays_pitching and pid in roster_pids:
                    p["fps_pct"] = plays_pitching[pid]["fps_pct"]
                    p["pitches_per_bf"] = plays_pitching[pid]["pitches_per_bf"]
                else:
                    p["fps_pct"] = None
                    p["pitches_per_bf"] = None

            # Merge plays stats into batter dicts
            for b in batting:
                pid = b.get("player_id")
                if pid and pid in plays_batting:
                    b["qab_pct"] = plays_batting[pid]["qab_pct"]
                    b["pitches_per_pa"] = plays_batting[pid]["pitches_per_pa"]
                else:
                    b["qab_pct"] = None
                    b["pitches_per_pa"] = None

            # Orphan cleanup -- after queries, before render (non-fatal)
            self._cleanup_orphans()

            # Footer trust-block inputs (AC-5 / TN-3 / TN-6) -- story 07
            # consumes these from the render data; this is the only generator
            # change the footer needs. degraded_confidence is the single derived
            # boolean: it fires ONLY on a name-only identity match (E-236-06 /
            # TN-4 / coach C2). The season-fallback signal was never part of
            # this term -- it fired on clean modal data (program_type NULL +
            # good season_year) and would have produced a false coach-facing
            # warning.
            degraded_confidence = bool(
                self.identity_match_method == "name_only"
            )

            # Render HTML
            self.team_info["record"] = record
            data = {
                "team": self.team_info,
                "generated_at": generated_at,
                "expires_at": self.expires_at,
                "freshness_date": freshness_date,
                "game_count": game_count,
                "recent_form": recent_form,
                "pitching": pitching,
                "batting": batting,
                "spray_charts": spray_charts,
                "roster": roster,
                "runs_scored_avg": runs_scored_avg,
                "runs_allowed_avg": runs_allowed_avg,
                "team_fps_pct": plays_team["team_fps_pct"],
                "team_pitches_per_pa": plays_team["team_pitches_per_pa"],
                "team_qab_pct": plays_team["team_qab_pct"],
                "has_plays_data": plays_team["has_plays_data"],
                "plays_game_count": plays_team["plays_game_count"],
                "pitch_charted_game_count": plays_team["pitch_charted_game_count"],
                "pitching_workload": pitching_workload,
                # The coach-facing "Generated <date>" footer. Fed the venue-local
                # reference date, so it agrees with the rest-day math above it
                # rather than showing tomorrow's UTC date on an evening run.
                # (A FOURTH consumer of this date; the story named three.)
                "generation_date": reference_date,
                "starter_prediction": starter_prediction,
                "enriched_prediction": enriched_prediction,
                "show_predicted_starter": show_predicted_starter,
                # Outings Breakdown (E-265): typed structure + boolean gate,
                # mirroring starter_prediction + show_predicted_starter.
                "pitcher_outings": pitcher_outings,
                "show_pitcher_outings": show_pitcher_outings,
                # Footer trust-block inputs (story 07):
                "completed_games": self.completed_games,  # M
                "completed_games_with_data": completed_games_with_data,  # N
                # K (plays_game_count) is already provided above.
                "spray_available": bool(spray_charts),
                "degraded_confidence": degraded_confidence,
            }

            # Report-time plausibility guard (E-257-03 / TN-4): advisory WARNING
            # when a TEAM headline rate is out of the coach-confirmed band. Never
            # blocks the render or mutates the value -- reproduces the operator's
            # human-eyeball catch at generation time.
            _log_rate_plausibility_warnings(data, slug)

            html = render_report(data)

            # Save HTML to disk
            _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            report_path = f"reports/{slug}.html"
            file_path = _REPO_ROOT / "data" / report_path
            file_path.write_text(html, encoding="utf-8")

            # Update reports row to 'ready'
            with closing(get_connection()) as conn:
                _update_report_ready(conn, report_id, report_path)

            # Run record: write the render-stage counts and finalize completed.
            _update_run_record(
                report_id,
                completed_games_with_data=_coerce_int(completed_games_with_data),
                plays_games_covered=_coerce_int(plays_games_covered),
                enrichment_status=_coerce_status(enrichment_status),
            )
            _finalize_run_record(report_id, "completed")

        except Exception as exc:  # noqa: BLE001
            msg = f"Post-pipeline error: {exc}"
            logger.exception("Failed to query/render/save report")
            _finalize_run_record(
                report_id, "failed", error_stage="render", error_message=msg,
            )
            _fail_report(report_id, msg)
            return GenerationResult(success=False, slug=slug, error_message=msg)

        url = f"{_get_base_url()}/reports/{slug}"
        logger.info(
            "Report generated: slug=%s team=%s url=%s",
            slug, self.team_info["name"], url,
        )

        return GenerationResult(
            success=True,
            slug=slug,
            title=self.title,
            url=url,
            reference_date=reference_date,
            outcome="ready",
        )


def _fail_report(report_id: int, error_message: str) -> None:
    """Mark a report as failed."""
    try:
        with closing(get_connection()) as conn:
            _update_report_failed(conn, report_id, error_message)
    except sqlite3.Error:
        logger.exception("Failed to update report status to 'failed'")
