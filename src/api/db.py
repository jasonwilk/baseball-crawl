"""Database connection helpers for the FastAPI application.

Provides a simple synchronous SQLite connection factory and a health-check
function.  All database calls are run via ``run_in_threadpool`` in async
route handlers to avoid blocking the event loop (see routes/health.py).

Configuration:
    DATABASE_PATH   Environment variable specifying the path to the SQLite
                    file.  Defaults to ``<repo_root>/data/app.db``.
"""

from __future__ import annotations

import datetime
import logging
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path
from typing import Any

from src.db.paths import resolve_db_path

logger = logging.getLogger(__name__)


def get_db_path() -> Path:
    """Return the resolved path to the SQLite database file.

    Thin wrapper around the canonical :func:`src.db.paths.resolve_db_path`
    (DATABASE_PATH -> default).

    Returns:
        Resolved Path to the database file.
    """
    return resolve_db_path()


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open and return a new SQLite connection with recommended pragmas.

    This is the SINGLE connection factory for every SQLite writer in the
    system -- the admin UI (uvicorn workers), the interactive CLI, and the
    morning-run cron. They share one WAL file across processes, so every
    connection must carry a ``busy_timeout`` (a lock overlap WAITS instead of
    immediately raising ``database is locked``) and the WAL-safe
    ``synchronous=NORMAL``.

    Pragma scope: ``journal_mode=WAL`` is a persistent DB-file property, but
    ``foreign_keys``, ``busy_timeout``, and ``synchronous`` are per-connection
    and so are set on every connection returned here.

    Note: default (deferred) isolation is preserved -- this factory does NOT
    switch to ``isolation_level=None`` (full autocommit). busy_timeout only
    protects writers that also commit their write transactions promptly (never
    holding an open write transaction across a network fetch); that transaction
    discipline is the caller's responsibility.

    Callers are responsible for closing the connection (use as a context
    manager or call ``conn.close()`` explicitly).

    Args:
        db_path: Optional explicit database path. Defaults to the factory's
            canonical resolution (``get_db_path()`` -> ``resolve_db_path()``),
            so existing no-arg callers are unaffected. The CLI/cron pass their
            already-resolved ``resolve_db_path(override)`` here.

    Returns:
        Open sqlite3.Connection with WAL mode, foreign keys enabled,
        ``busy_timeout=30000`` (30s), and ``synchronous=NORMAL``.

    Raises:
        sqlite3.Error: If the database file cannot be opened.
    """
    if db_path is None:
        db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def list_reports_with_runs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return all reports LEFT JOINed to their 1:1 ``report_generation_runs`` row.

    Shared by the two report-listing surfaces -- the CLI ``list_reports()`` in
    ``src/reports/generator.py`` (``bb report list``) and the admin
    ``_get_all_reports()`` (``/admin/reports``) -- per the shared-query-functions
    convention (CLAUDE.md): both need the identical 1:1 join, so the SQL lives
    here once rather than being copied into two files (E-235-06 / TN-6, SE-F7).

    The join is LEFT so a report with no run row (legacy / pre-migration-002)
    still appears, with all ``run.*`` columns NULL -- callers and templates must
    stay NULL-safe. The run record's ``error_message`` is aliased
    ``run_error_message`` to avoid colliding with ``reports.error_message`` (the
    report-level message the admin list already renders).

    Callers decorate the returned dicts with ``url`` / ``is_expired`` using their
    own base URL (the two surfaces source it differently), so this helper does
    NOT add them.

    Args:
        conn: An open connection. ``row_factory`` is set to ``sqlite3.Row`` here.

    Returns:
        One dict per report, ordered by ``generated_at`` descending, carrying the
        ``reports`` columns plus the joined ``report_generation_runs`` columns.
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT
            r.id, r.slug, r.title, r.status, r.generated_at, r.expires_at,
            r.report_path, r.error_message,
            run.overall_status, run.crawl_status, run.load_status,
            run.gc_uuid_status, run.spray_status, run.plays_status,
            run.reconciliation_status, run.enrichment_status,
            run.completed_games, run.completed_games_with_data, run.spray_games,
            run.plays_games_expected, run.plays_games_covered,
            run.boxscores_fetched, run.load_errors, run.plays_errors,
            run.spray_games_with_data,
            run.discrepancies_found, run.discrepancies_corrected,
            run.season_id_used, run.identity_match_method,
            run.error_stage, run.error_message AS run_error_message
        FROM reports r
        LEFT JOIN report_generation_runs run ON run.report_id = r.id
        ORDER BY r.generated_at DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_pitching_workload(
    team_id: int,
    season_id: str,
    reference_date: str | None = None,
    *,
    db: sqlite3.Connection | None = None,
) -> dict[str, dict[str, Any]]:
    """Return per-pitcher workload data for a team.

    Computes last outing date, days since last outing, 7-day pitch total, and
    7-day span from ``player_game_pitching`` joined to ``games``.

    Args:
        team_id: INTEGER PK of the team.
        season_id: Season slug to scope the query.
        reference_date: ISO date string (``YYYY-MM-DD``) used as "today" for
            days-ago and 7-day window calculations.  Defaults to the current
            date (``date('now')``).
        db: Optional pre-existing connection (used by the report generator
            which manages its own connection).  When ``None``, opens a new
            connection via ``get_connection()``.

    Returns:
        Dict keyed by ``player_id`` with values containing:
        ``last_outing_date``, ``last_outing_days_ago``, ``pitches_7d``,
        ``span_days_7d``, ``appearances_7d``.  Returns empty dict on
        database error.
    """
    if reference_date is None:
        reference_date = datetime.date.today().isoformat()

    query = """
        WITH pitcher_games AS (
            SELECT
                pgp.player_id,
                g.game_date,
                pgp.pitches
            FROM player_game_pitching pgp
            JOIN games g ON g.game_id = pgp.game_id
            WHERE pgp.team_id = :team_id
              AND pgp.perspective_team_id = :team_id
              AND g.season_id = :season_id
        ),
        last_outing AS (
            SELECT
                player_id,
                MAX(game_date) AS last_outing_date
            FROM pitcher_games
            GROUP BY player_id
        ),
        seven_day AS (
            SELECT
                player_id,
                -- appearances_7d: count of games in the 7-day window
                COUNT(*) AS appearances_7d,
                -- non_null_pitch_count: how many of those have non-NULL pitches
                COUNT(pitches) AS non_null_pitch_count,
                -- raw_sum: SUM of non-NULL pitches (NULL if all are NULL)
                SUM(pitches) AS raw_sum,
                -- span: days between first and last appearance + 1
                CAST(julianday(MAX(game_date)) - julianday(MIN(game_date)) + 1 AS INTEGER) AS span_days_7d
            FROM pitcher_games
            WHERE game_date >= date(:ref_date, '-6 days')
              AND game_date <= :ref_date
            GROUP BY player_id
        )
        SELECT
            lo.player_id,
            lo.last_outing_date,
            CAST(julianday(:ref_date) - julianday(lo.last_outing_date) AS INTEGER) AS last_outing_days_ago,
            CASE
                WHEN sd.appearances_7d IS NULL THEN 0
                WHEN sd.non_null_pitch_count = 0 THEN NULL
                ELSE sd.raw_sum
            END AS pitches_7d,
            sd.span_days_7d,
            sd.appearances_7d
        FROM last_outing lo
        LEFT JOIN seven_day sd ON sd.player_id = lo.player_id
    """
    params = {
        "team_id": team_id,
        "season_id": season_id,
        "ref_date": reference_date,
    }
    own_conn = db is None
    try:
        conn = db if db is not None else get_connection()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            result: dict[str, dict[str, Any]] = {}
            for row in rows:
                result[row["player_id"]] = {
                    "last_outing_date": row["last_outing_date"],
                    "last_outing_days_ago": row["last_outing_days_ago"],
                    "pitches_7d": row["pitches_7d"],
                    "span_days_7d": row["span_days_7d"],
                    "appearances_7d": row["appearances_7d"],
                }
            return result
        finally:
            if own_conn:
                conn.close()
    except sqlite3.Error:
        logger.exception("Failed to fetch pitching workload for team %d", team_id)
        return {}


def get_pitching_history(
    team_id: int,
    season_id: str,
    *,
    db: sqlite3.Connection | None = None,
) -> list[dict]:
    """Return all pitching appearances for a team/season, chronologically.

    Includes computed ``rest_days`` (days since each pitcher's previous
    appearance of any type) and ``team_game_number`` (sequential game index
    for rotation cycle detection).

    Args:
        team_id: INTEGER PK of the team.
        season_id: Season slug to scope the query.
        db: Optional pre-existing connection.  When ``None``, opens a new
            connection via ``get_connection()``.

    Returns:
        List of dicts, one per pitching appearance, ordered by game_date ASC,
        start_time ASC NULLS LAST, appearance_order ASC NULLS LAST.
    """
    query = """
        SELECT
            pgp.player_id,
            p.first_name,
            p.last_name,
            tr.jersey_number,
            pgp.game_id,
            g.game_date,
            g.start_time,
            pgp.ip_outs,
            pgp.pitches,
            pgp.so,
            pgp.bb,
            pgp.h,
            pgp.r,
            pgp.er,
            pgp.bf,
            pgp.decision,
            pgp.appearance_order,
            CAST(
                julianday(g.game_date) - julianday(
                    LAG(g.game_date) OVER (
                        PARTITION BY pgp.player_id
                        ORDER BY g.game_date ASC, g.start_time ASC NULLS LAST
                    )
                )
            AS INTEGER) AS rest_days,
            DENSE_RANK() OVER (
                ORDER BY g.game_date ASC, g.start_time ASC NULLS LAST
            ) AS team_game_number
        FROM player_game_pitching pgp
        JOIN games g ON g.game_id = pgp.game_id
        JOIN players p ON p.player_id = pgp.player_id
        LEFT JOIN team_rosters tr
            ON tr.team_id = pgp.team_id
           AND tr.player_id = pgp.player_id
           AND tr.season_id = :season_id
        WHERE pgp.team_id = :team_id
          AND pgp.perspective_team_id = :team_id
          AND g.season_id = :season_id
          AND g.status = 'completed'
        ORDER BY g.game_date ASC,
                 g.start_time ASC NULLS LAST,
                 pgp.appearance_order ASC NULLS LAST
    """
    params = {"team_id": team_id, "season_id": season_id}
    own_conn = db is None
    try:
        conn = db if db is not None else get_connection()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
        finally:
            if own_conn:
                conn.close()
    except sqlite3.Error:
        logger.exception(
            "Failed to fetch pitching history for team %d", team_id
        )
        return []


def build_pitcher_profiles(history: list[dict]) -> dict[str, dict]:
    """Group pitching history rows into per-pitcher profile dicts.

    Args:
        history: Output from ``get_pitching_history()``.

    Returns:
        Dict keyed by ``player_id``.  Each value contains identity fields,
        a chronological ``appearances`` list, a ``starts`` list (filtered
        by ``appearance_order = 1`` when available, falling back to
        most-IP-per-game heuristic), aggregate counts, and
        ``start_to_start_rest`` intervals.
    """
    pitchers: dict[str, dict] = {}
    # First pass: collect appearances per pitcher
    for row in history:
        pid = row["player_id"]
        if pid not in pitchers:
            pitchers[pid] = {
                "player_id": pid,
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "jersey_number": row["jersey_number"],
                "appearances": [],
            }
        pitchers[pid]["appearances"].append(row)

    for profile in pitchers.values():
        apps = profile["appearances"]
        profile["total_games"] = len(apps)
        profile["season_ip_outs"] = sum(a.get("ip_outs") or 0 for a in apps)

        # K/9 = (SO * 27) / ip_outs  (ip_outs is total outs, 27 = 9 innings)
        total_so = sum(a.get("so") or 0 for a in apps)
        if profile["season_ip_outs"] > 0:
            profile["season_k9"] = round(
                (total_so * 27) / profile["season_ip_outs"], 2
            )
        else:
            profile["season_k9"] = None

        # Determine starts: use appearance_order if available
        has_appearance_order = any(
            a.get("appearance_order") is not None for a in apps
        )
        if has_appearance_order:
            starts = [a for a in apps if a.get("appearance_order") == 1]
        else:
            # Fallback: most IP per game = starter for that game
            # Group all history rows by game, find max ip_outs pitcher per game
            games_max_ip: dict[str, tuple[str, int]] = defaultdict(
                lambda: ("", 0)
            )
            for row in history:
                gid = row["game_id"]
                ip = row.get("ip_outs") or 0
                if ip > games_max_ip[gid][1]:
                    games_max_ip[gid] = (row["player_id"], ip)
            starter_game_ids = {
                gid
                for gid, (pid, _) in games_max_ip.items()
                if pid == profile["player_id"]
            }
            starts = [a for a in apps if a["game_id"] in starter_game_ids]

        profile["starts"] = starts
        profile["total_starts"] = len(starts)

        # Start-to-start rest: days between consecutive starts
        start_dates = [s["game_date"] for s in starts]
        rest_intervals: list[int] = []
        for i in range(1, len(start_dates)):
            d1 = datetime.date.fromisoformat(start_dates[i - 1])
            d2 = datetime.date.fromisoformat(start_dates[i])
            rest_intervals.append((d2 - d1).days)
        profile["start_to_start_rest"] = rest_intervals

    return pitchers


def check_connection() -> bool:
    """Verify that the database is accessible and the schema is initialized.

    Executes a trivial query against the ``_migrations`` table (created by
    ``apply_migrations.py``).  Returns True if the query succeeds, False if
    the database is not reachable or the migrations table does not exist.

    This function is designed to be called via ``run_in_threadpool`` from an
    async route handler.

    Returns:
        True if the database is accessible and initialized; False otherwise.
    """
    try:
        with closing(get_connection()) as conn:
            conn.execute("SELECT 1 FROM _migrations LIMIT 1;")
        return True
    except sqlite3.Error:
        logger.exception("Database health check failed")
        return False


# ---------------------------------------------------------------------------
# Season stat fetches (E-256-04 / TN-14 -- DE's relocation contract)
# ---------------------------------------------------------------------------
# Relocated VERBATIM out of ``src/reports/generator.py``'s ``_query_batting`` /
# ``_query_pitching``. These are the PURE fetch halves; the presentation halves
# (``_apply_name_cascade``, ``_compute_pitching_rates``) deliberately stay in
# ``src/reports/`` -- dragging them here would make ``db.py`` import the report
# layer while ``generator.py`` already imports FROM here, closing an import
# cycle. The fetch-only split is what keeps the graph acyclic, not merely tidy.
#
# So ``get_season_pitching`` returns the RAW SUM columns and NOT the display
# strings ``era`` / ``k9`` / ``whip`` / ``strike_pct``, which ``_compute_pitching_rates``
# writes in the wrapper.
#
# E-259 rewrites ONLY the SQL bodies below (against ``player_game_*``, adding the
# ``perspective_team_id`` filter and reproducing the ORDER BY over the new
# projection). The move being *pure* is what makes that diff a legible
# old-SQL-vs-new-SQL comparison, so do not "clean up" this SQL.


def get_season_batting(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> list[dict]:
    """Fetch raw season batting rows for a team-season (no presentation)."""
    rows = conn.execute(
        """
        SELECT
            p.player_id,
            p.first_name || ' ' || p.last_name AS name,
            COALESCE(psb.gp, 0) AS games,
            COALESCE(psb.ab, 0) AS ab,
            COALESCE(psb.h, 0) AS h,
            COALESCE(psb.doubles, 0) AS doubles,
            COALESCE(psb.triples, 0) AS triples,
            COALESCE(psb.hr, 0) AS hr,
            COALESCE(psb.rbi, 0) AS rbi,
            COALESCE(psb.bb, 0) AS bb,
            COALESCE(psb.so, 0) AS so,
            COALESCE(psb.sb, 0) AS sb,
            COALESCE(psb.cs, 0) AS cs,
            COALESCE(psb.hbp, 0) AS hbp,
            COALESCE(psb.shf, 0) AS shf,
            tr.jersey_number
        FROM player_season_batting psb
        JOIN players p ON p.player_id = psb.player_id
        LEFT JOIN team_rosters tr
            ON tr.player_id = psb.player_id
            AND tr.team_id = psb.team_id
            AND tr.season_id = psb.season_id
        WHERE psb.team_id = ? AND psb.season_id = ?
        ORDER BY
            (COALESCE(psb.ab, 0) + COALESCE(psb.bb, 0)
             + COALESCE(psb.hbp, 0) + COALESCE(psb.shf, 0)) DESC,
            p.last_name ASC
        """,
        (team_id, season_id),
    ).fetchall()
    return [dict(r) for r in rows]


def get_season_pitching(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> list[dict]:
    """Fetch raw season pitching rows for a team-season (no computed rates)."""
    rows = conn.execute(
        """
        SELECT
            p.player_id,
            p.first_name || ' ' || p.last_name AS name,
            COALESCE(psp.gp_pitcher, 0) AS games,
            COALESCE(psp.ip_outs, 0) AS ip_outs,
            COALESCE(psp.h, 0) AS h,
            COALESCE(psp.er, 0) AS er,
            COALESCE(psp.bb, 0) AS bb,
            COALESCE(psp.so, 0) AS so,
            COALESCE(psp.pitches, 0) AS pitches,
            COALESCE(psp.total_strikes, 0) AS total_strikes,
            p.throws,
            tr.jersey_number,
            psp.gs
        FROM player_season_pitching psp
        JOIN players p ON p.player_id = psp.player_id
        LEFT JOIN team_rosters tr
            ON tr.player_id = psp.player_id
            AND tr.team_id = psp.team_id
            AND tr.season_id = psp.season_id
        WHERE psp.team_id = ? AND psp.season_id = ?
        ORDER BY
            COALESCE(psp.ip_outs, 0) DESC,
            p.last_name ASC
        """,
        (team_id, season_id),
    ).fetchall()
    return [dict(r) for r in rows]
