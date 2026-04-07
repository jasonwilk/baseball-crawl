"""Background-safe crawl trigger functions for the admin sync UI.

Called from FastAPI BackgroundTasks -- each function creates its own DB
connection and owns its full lifecycle.  Do NOT import from src/cli/.

Two pipelines:
- run_member_sync: full crawl.run + load.run for owned (member) teams.
- run_scouting_sync: ScoutingCrawler + ScoutingLoader for tracked teams.

Both functions:
1. Refresh the auth token eagerly at start (access token ~61-min lifetime).
2. Create/update a crawl_jobs row for UI status display.
3. Update teams.last_synced on success.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from src.api.db import get_db_path
from src.gamechanger.client import CredentialExpiredError, GameChangerClient
from src.gamechanger.config import CrawlConfig, load_config_from_db
from src.gamechanger.crawlers.opponent_resolver import OpponentResolver
from src.gamechanger.crawlers.scouting import ScoutingCrawler
from src.gamechanger.crawlers.scouting_spray import ScoutingSprayChartCrawler
from src.gamechanger.loaders.opponent_seeder import seed_schedule_opponents
from src.gamechanger.loaders.scouting_loader import ScoutingLoader
from src.gamechanger.loaders.scouting_spray_loader import ScoutingSprayChartLoader
from src.gamechanger.resolvers.gc_uuid_resolver import resolve_gc_uuid
from src.gamechanger.team_resolver import resolve_team
from src.pipeline import crawl as crawl_module
from src.pipeline import load as load_module

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATA_ROOT = _PROJECT_ROOT / "data" / "raw"


# ---------------------------------------------------------------------------
# Shared DB helpers
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _mark_job_terminal(
    conn: sqlite3.Connection,
    crawl_job_id: int,
    status: str,
    error_message: str | None,
) -> None:
    """Update a crawl_jobs row with a terminal status (completed or failed).

    Args:
        conn: Open SQLite connection.
        crawl_job_id: The crawl_jobs.id to update.
        status: Terminal status -- 'completed' or 'failed'.
        error_message: Optional error description for failed runs.
    """
    conn.execute(
        """
        UPDATE crawl_jobs
        SET status = ?, completed_at = ?, error_message = ?
        WHERE id = ?
        """,
        (status, _utcnow_iso(), error_message, crawl_job_id),
    )
    conn.commit()


def _update_last_synced(conn: sqlite3.Connection, team_id: int) -> None:
    """Set teams.last_synced to the current UTC time.

    Args:
        conn: Open SQLite connection.
        team_id: The teams.id (INTEGER PK) to update.
    """
    conn.execute(
        "UPDATE teams SET last_synced = ? WHERE id = ?",
        (_utcnow_iso(), team_id),
    )
    conn.commit()


def _refresh_auth_token() -> GameChangerClient:
    """Instantiate a GameChangerClient and force-refresh the access token.

    Called at the start of every background crawl to ensure the token does not
    expire mid-run (access token lifetime is ~61 minutes).

    Returns:
        A GameChangerClient with a freshly obtained access token.

    Raises:
        Exception: Any error from token refresh is re-raised to the caller.
    """
    client = GameChangerClient()
    client._token_manager.force_refresh(allow_login_fallback=True)  # noqa: SLF001
    return client


# ---------------------------------------------------------------------------
# Self-healing: season_year propagation
# ---------------------------------------------------------------------------


def _heal_season_year_member(
    conn: sqlite3.Connection, team_id: int, client: GameChangerClient
) -> None:
    """Backfill season_year for a member team if NULL.

    Looks up gc_uuid, calls the authenticated team endpoint, and UPDATEs
    season_year WHERE IS NULL.  Best-effort: any failure is logged and skipped.
    """
    row = conn.execute(
        "SELECT gc_uuid, season_year FROM teams WHERE id = ?", (team_id,)
    ).fetchone()
    if row is None:
        return
    gc_uuid, season_year = row
    if season_year is not None:
        return  # already populated
    if not gc_uuid:
        logger.debug("No gc_uuid for team_id=%d; skipping season_year heal.", team_id)
        return
    try:
        team_data = client.get(
            f"/teams/{gc_uuid}",
            accept="application/vnd.gc.com.team+json; version=0.10.0",
        )
        api_year = (
            team_data.get("season_year")
            if isinstance(team_data, dict)
            else None
        )
        if api_year is not None:
            conn.execute(
                "UPDATE teams SET season_year = ? WHERE id = ? AND season_year IS NULL",
                (int(api_year), team_id),
            )
            conn.commit()
            logger.info("Healed season_year=%s for team_id=%d", api_year, team_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("season_year heal failed for team_id=%d: %s", team_id, exc)


def _heal_season_year_scouting(
    conn: sqlite3.Connection, team_id: int, public_id: str
) -> None:
    """Backfill season_year for a tracked team if NULL.

    Calls resolve_team (public, no auth) and UPDATEs season_year WHERE IS NULL.
    Best-effort: any failure is logged and skipped.
    """
    row = conn.execute(
        "SELECT season_year FROM teams WHERE id = ?", (team_id,)
    ).fetchone()
    if row is None or row[0] is not None:
        return  # already populated or missing
    try:
        profile = resolve_team(public_id)
        if profile.year is not None:
            conn.execute(
                "UPDATE teams SET season_year = ? WHERE id = ? AND season_year IS NULL",
                (profile.year, team_id),
            )
            conn.commit()
            logger.info("Healed season_year=%s for team_id=%d (scouting)", profile.year, team_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("season_year heal (scouting) failed for team_id=%d: %s", team_id, exc)


# ---------------------------------------------------------------------------
# Opponent discovery helpers
# ---------------------------------------------------------------------------


def _auto_scout_resolved_opponents(
    our_team_id: int,
    resolve_start: str,
    db_path: Path,
) -> None:
    """Trigger scouting for opponents newly resolved during discovery.

    Queries ``opponent_links`` for rows resolved after ``resolve_start``
    whose resolved team has a ``public_id`` and that pass the freshness
    filter (no running job, no completed job within 24 hours).  For each,
    creates a ``crawl_jobs`` row and calls ``run_scouting_sync`` sequentially.

    Non-fatal: errors for individual opponents are logged and skipped.
    Auth failures (detected via crawl_job status) stop further attempts.

    Args:
        our_team_id: The member team whose discovery triggered resolution.
        resolve_start: UTC ISO timestamp recorded before the resolver ran.
        db_path: Path to the SQLite database.
    """
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA foreign_keys=ON;")
        rows = conn.execute(
            """
            SELECT DISTINCT t.id, t.public_id
            FROM opponent_links ol
            JOIN teams t ON ol.resolved_team_id = t.id
            WHERE ol.our_team_id = ?
              AND datetime(ol.resolved_at) >= datetime(?)
              AND t.public_id IS NOT NULL
              AND t.id NOT IN (
                  SELECT cj.team_id FROM crawl_jobs cj
                  WHERE cj.status = 'running'
              )
              AND t.id NOT IN (
                  SELECT cj.team_id FROM crawl_jobs cj
                  WHERE cj.status = 'completed'
                    AND datetime(cj.completed_at) >= datetime('now', '-24 hours')
              )
            """,
            (our_team_id, resolve_start),
        ).fetchall()

    if not rows:
        logger.info(
            "Auto-scout: no newly resolved opponents to scout for team_id=%d.",
            our_team_id,
        )
        return

    logger.info(
        "Auto-scout: %d newly resolved opponent(s) to scout for team_id=%d.",
        len(rows),
        our_team_id,
    )

    for opponent_team_id, public_id in rows:
        # Create a crawl_jobs row so the admin UI shows "Syncing..." status.
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.execute("PRAGMA foreign_keys=ON;")
            cur = conn.execute(
                "INSERT INTO crawl_jobs (team_id, sync_type, status, started_at) "
                "VALUES (?, 'scouting_crawl', 'running', datetime('now'))",
                (opponent_team_id,),
            )
            conn.commit()
            scout_job_id = cur.lastrowid

        logger.info(
            "Auto-scout: starting scouting for opponent team_id=%d "
            "public_id=%s crawl_job_id=%d",
            opponent_team_id,
            public_id,
            scout_job_id,
        )

        try:
            run_scouting_sync(opponent_team_id, public_id, scout_job_id)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Auto-scout failed for opponent team_id=%d (non-fatal)",
                opponent_team_id,
                exc_info=True,
            )

        # Check if auth failed -- stop further auto-scout attempts (AC-6).
        with closing(sqlite3.connect(str(db_path))) as conn:
            job_row = conn.execute(
                "SELECT status, error_message FROM crawl_jobs WHERE id = ?",
                (scout_job_id,),
            ).fetchone()
        if job_row and job_row[0] == "failed" and job_row[1]:
            err_msg = job_row[1]
            if "Auth refresh failed" in err_msg or "Credential expired" in err_msg:
                logger.warning(
                    "Auto-scout: stopping due to auth failure for opponent "
                    "team_id=%d: %s",
                    opponent_team_id,
                    err_msg,
                )
                break


def _discover_opponents(
    team_id: int,
    client: GameChangerClient,
    db_path: Path,
    crawl_job_id: int,
) -> None:
    """Run schedule seeder then ``OpponentResolver`` for one member team.

    Called from ``run_member_sync`` after crawl+load complete.  Provides
    automatic opponent discovery as a side effect of syncing the schedule.

    Error contract:
    - Seeder failures are non-fatal (WARNING-logged; pipeline continues).
    - ``CredentialExpiredError`` from the resolver marks the ``crawl_jobs``
      row as ``failed`` and propagates to the caller (signals dead auth,
      consistent with OpponentResolver's intentional re-raise design).
    - All other per-opponent resolver errors are handled internally by
      ``OpponentResolver.resolve()``.

    Args:
        team_id: INTEGER PK of the member team (``our_team_id`` in
            ``opponent_links``).
        client: Authenticated ``GameChangerClient`` (token already refreshed
            at sync start).
        db_path: Path to the SQLite database.
        crawl_job_id: ``crawl_jobs.id`` to update if a fatal auth error
            occurs during resolution.
    """
    # Load DB config to obtain the season slug and member team list.
    # Non-fatal if this fails (e.g. no seasons row configured yet).
    try:
        config = load_config_from_db(db_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Opponent discovery skipped for team_id=%d: config load failed: %s",
            team_id,
            exc,
        )
        return

    # Resolve gc_uuid for path construction.
    try:
        with closing(sqlite3.connect(str(db_path))) as conn:
            row = conn.execute(
                "SELECT gc_uuid FROM teams WHERE id = ?", (team_id,)
            ).fetchone()
    except sqlite3.OperationalError as exc:
        logger.warning(
            "Opponent discovery skipped for team_id=%d: gc_uuid lookup failed: %s",
            team_id,
            exc,
        )
        return
    gc_uuid: str | None = row[0] if row else None

    if not gc_uuid:
        logger.info(
            "Opponent discovery skipped for team_id=%d: no gc_uuid.", team_id
        )
        return

    # Filter config to just the syncing team (AC-6: prevents cross-team resolution).
    filtered_teams = [t for t in config.member_teams if t.internal_id == team_id]
    if not filtered_teams:
        logger.info(
            "Opponent discovery skipped for team_id=%d: "
            "team not found in active member config.",
            team_id,
        )
        return
    filtered_config = CrawlConfig(season=config.season, member_teams=filtered_teams)

    schedule_path = _DATA_ROOT / config.season / "teams" / gc_uuid / "schedule.json"
    opponents_path = _DATA_ROOT / config.season / "teams" / gc_uuid / "opponents.json"

    # 1. Schedule seeder -- non-fatal (AC-4a).
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            seeded = seed_schedule_opponents(team_id, schedule_path, opponents_path, conn)
            logger.info(
                "Schedule seeder: %d opponent(s) seeded for team_id=%d.",
                seeded,
                team_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Schedule seeder failed for team_id=%d (non-fatal): %s",
                team_id,
                exc,
            )

    # 2. OpponentResolver -- CredentialExpiredError marks job failed and propagates (AC-4b).
    # Record timestamp before resolver runs so we can identify newly resolved opponents.
    resolve_start = _utcnow_iso()
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA foreign_keys=ON;")
        resolver = OpponentResolver(client, filtered_config, conn)
        try:
            resolver.resolve()
            logger.info("OpponentResolver complete for team_id=%d.", team_id)
        except CredentialExpiredError as exc:
            logger.error(
                "Credential expired during opponent resolution for team_id=%d: %s",
                team_id,
                exc,
            )
            _mark_job_terminal(
                conn,
                crawl_job_id,
                "failed",
                f"Credential expired during opponent resolution: {exc}",
            )
            raise

    # 3. Auto-scout newly resolved opponents (E-189-02).
    _auto_scout_resolved_opponents(team_id, resolve_start, db_path)


# ---------------------------------------------------------------------------
# Member team sync
# ---------------------------------------------------------------------------


def run_member_sync(team_id: int, team_name: str, crawl_job_id: int) -> None:
    """Run the full crawl+load pipeline for an owned (member) team.

    Invokes ``crawl.run(source="db", team_ids=[team_id])`` then
    ``load.run(source="db", team_ids=[team_id])``, updates the
    ``crawl_jobs`` row, and sets ``teams.last_synced`` on success.

    Designed for use as a FastAPI BackgroundTask -- owns its own DB connection
    and handles all errors internally.

    Args:
        team_id: The team's INTEGER primary key in the ``teams`` table.
        team_name: Team display name (for log messages).
        crawl_job_id: The ``crawl_jobs.id`` row to update with final status.
    """
    logger.info(
        "Member sync starting: team_id=%d team=%r crawl_job_id=%d",
        team_id, team_name, crawl_job_id,
    )
    db_path = get_db_path()

    # 1. Refresh auth token before pipeline starts.
    # The returned client is kept for the season_year heal call below;
    # force_refresh() also persists credentials so the crawl pipeline
    # (which creates its own GameChangerClient internally) picks up
    # the fresh token automatically.
    try:
        client = _refresh_auth_token()
        logger.info("Auth token refreshed for member sync team_id=%d", team_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("Auth refresh failed for team_id=%d: %s", team_id, exc)
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.execute("PRAGMA foreign_keys=ON;")
            _mark_job_terminal(conn, crawl_job_id, "failed", f"Auth refresh failed: {exc}")
        return

    # 1b. Self-heal season_year if NULL.
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA foreign_keys=ON;")
        _heal_season_year_member(conn, team_id, client)

    # 2. Run crawl then load (each stage opens its own connection).
    try:
        crawl_exit = crawl_module.run(source="db", team_ids=[team_id])
        load_exit = load_module.run(source="db", team_ids=[team_id])
    except Exception as exc:  # noqa: BLE001
        logger.error("Pipeline exception for team_id=%d: %s", team_id, exc)
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.execute("PRAGMA foreign_keys=ON;")
            _mark_job_terminal(conn, crawl_job_id, "failed", str(exc))
        return

    # 2b. Opponent discovery: schedule seeder + OpponentResolver.
    # Runs after crawl+load (data is on disk).  Seeder failures are non-fatal.
    # CredentialExpiredError from the resolver marks job failed and propagates.
    _discover_opponents(team_id, client, db_path, crawl_job_id)

    # 3. Record outcome.
    success = crawl_exit == 0 and load_exit == 0
    status = "completed" if success else "failed"
    error_msg = None if success else f"crawl_exit={crawl_exit} load_exit={load_exit}"

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA foreign_keys=ON;")
        _mark_job_terminal(conn, crawl_job_id, status, error_msg)
        if success:
            _update_last_synced(conn, team_id)

    logger.info("Member sync complete: team_id=%d status=%s", team_id, status)


# ---------------------------------------------------------------------------
# Spray chart enrichment (scouting pipeline)
# ---------------------------------------------------------------------------


def _resolve_team_gc_uuid(
    conn: sqlite3.Connection,
    team_id: int,
    public_id: str,
    client: GameChangerClient,
) -> str | None:
    """Attempt gc_uuid resolution for a tracked team if gc_uuid is NULL.

    Returns the gc_uuid (existing or newly resolved), or None if unavailable.
    Errors are logged but never propagated -- spray stages degrade gracefully.
    """
    row = conn.execute(
        "SELECT gc_uuid, name, season_year FROM teams WHERE id = ?", (team_id,)
    ).fetchone()
    if row is None:
        return None

    gc_uuid, team_name, season_year = row
    if gc_uuid:
        return gc_uuid

    if not public_id:
        logger.info(
            "gc_uuid resolution skipped for team_id=%d: no public_id.", team_id
        )
        return None

    try:
        resolved = resolve_gc_uuid(
            team_id=team_id,
            public_id=public_id,
            team_name=team_name or "",
            season_year=season_year,
            conn=conn,
            data_root=_DATA_ROOT,
            client=client,
        )
        if resolved:
            logger.info(
                "gc_uuid resolved for team_id=%d: %s", team_id, resolved
            )
        else:
            logger.info(
                "gc_uuid resolution returned no result for team_id=%d.", team_id
            )
        return resolved
    except Exception:  # noqa: BLE001
        logger.warning(
            "gc_uuid resolution failed for team_id=%d", team_id, exc_info=True
        )
        return None


def _run_spray_stages(
    conn: sqlite3.Connection,
    client: GameChangerClient,
    team_id: int,
    public_id: str,
    gc_uuid: str | None,
    season_id: str | None,
) -> None:
    """Run spray chart crawl + load for a scouted team (non-fatal).

    If gc_uuid is None, both stages are skipped with an INFO log.
    Any exception is logged at WARNING and swallowed -- spray data is
    additive enrichment that must not fail the overall scouting sync.

    Args:
        conn: Open SQLite connection.
        client: Authenticated GameChangerClient.
        team_id: The team's INTEGER PK.
        public_id: The team's public_id slug.
        gc_uuid: The team's gc_uuid (may be None).
        season_id: Season to scope spray crawl/load (may be None).
    """
    if not gc_uuid:
        logger.info(
            "Spray stages skipped for team_id=%d: no gc_uuid available.", team_id
        )
        return

    # Spray crawl
    try:
        spray_crawler = ScoutingSprayChartCrawler(client, conn, data_root=_DATA_ROOT)
        spray_result = spray_crawler.crawl_team(
            public_id, season_id=season_id, gc_uuid=gc_uuid
        )
        logger.info(
            "Spray crawl done: team_id=%d written=%d skipped=%d errors=%d",
            team_id,
            spray_result.files_written,
            spray_result.files_skipped,
            spray_result.errors,
        )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Spray crawl failed for team_id=%d (non-fatal)", team_id, exc_info=True
        )
        return

    # Skip spray load if crawl had errors (parity with CLI behavior).
    if spray_result.errors:
        logger.warning(
            "Spray crawl had %d error(s) for team_id=%d; skipping spray load.",
            spray_result.errors,
            team_id,
        )
        return

    # Spray load
    try:
        spray_loader = ScoutingSprayChartLoader(conn)
        spray_load_result = spray_loader.load_all(
            _DATA_ROOT,
            public_id=public_id,
            season_id=season_id,
        )
        if spray_load_result.errors:
            logger.warning(
                "Spray load had %d error(s) for team_id=%d (non-fatal)",
                spray_load_result.errors,
                team_id,
            )
        else:
            logger.info(
                "Spray load done: team_id=%d loaded=%d skipped=%d",
                team_id,
                spray_load_result.loaded,
                spray_load_result.skipped,
            )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Spray load failed for team_id=%d (non-fatal)", team_id, exc_info=True
        )


# ---------------------------------------------------------------------------
# Tracked team (scouting) sync
# ---------------------------------------------------------------------------


def run_scouting_sync(team_id: int, public_id: str, crawl_job_id: int) -> None:
    """Run the scouting crawl+load pipeline for a tracked opponent team.

    Mirrors the CLI's ``_run_scout_pipeline`` behavior without importing from
    ``src/cli/``.  Preserves the ``scouting_runs`` status-update behavior that
    the CLI maintains -- ``crawl_jobs`` is an additional tracking row for the
    UI surface, not a replacement.

    Invokes ``ScoutingCrawler.scout_team(public_id)`` then
    ``ScoutingLoader.load_team(scouting_dir, team_id, season_id)``.

    Designed for use as a FastAPI BackgroundTask -- owns its own DB connection
    and handles all errors internally.

    Args:
        team_id: The team's INTEGER primary key in the ``teams`` table.
        public_id: The GameChanger public_id slug used by the scouting crawler.
        crawl_job_id: The ``crawl_jobs.id`` row to update with final status.
    """
    logger.info(
        "Scouting sync starting: team_id=%d public_id=%s crawl_job_id=%d",
        team_id, public_id, crawl_job_id,
    )
    db_path = get_db_path()
    started_at = _utcnow_iso()

    # 1. Refresh auth token before pipeline starts.
    try:
        client = _refresh_auth_token()
        logger.info("Auth token refreshed for scouting sync team_id=%d", team_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("Auth refresh failed for team_id=%d: %s", team_id, exc)
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.execute("PRAGMA foreign_keys=ON;")
            _mark_job_terminal(conn, crawl_job_id, "failed", f"Auth refresh failed: {exc}")
        return

    # 1b. Self-heal season_year if NULL (public endpoint, no auth needed).
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA foreign_keys=ON;")
        _heal_season_year_scouting(conn, team_id, public_id)

    # 2. Run crawl + load within a single shared connection.
    try:
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")

            crawler = ScoutingCrawler(client, conn)
            loader = ScoutingLoader(conn)

            # Crawl phase.
            crawl_result = crawler.scout_team(public_id)
            logger.info(
                "Scouting crawl done: public_id=%s files_written=%d files_skipped=%d errors=%d",
                public_id,
                crawl_result.files_written,
                crawl_result.files_skipped,
                crawl_result.errors,
            )

            # No completed games -- treat as a successful "nothing to do" sync.
            if crawl_result.files_skipped > 0 and crawl_result.errors == 0 and crawl_result.files_written == 0:
                _mark_job_terminal(conn, crawl_job_id, "completed", None)
                _update_last_synced(conn, team_id)
                logger.info("Scouting sync: no games to scout for public_id=%s; marked completed.", public_id)
                return

            # Crawl errors with no files written -- no scouting_run row created.
            if crawl_result.errors > 0 and crawl_result.files_written == 0:
                _mark_job_terminal(conn, crawl_job_id, "failed", "Crawl failed (schedule or roster unavailable)")
                return

            # Crawl succeeded -- find the scouting_run row the crawler created.
            run_row = conn.execute(
                "SELECT season_id FROM scouting_runs "
                "WHERE team_id = ? AND status IN ('running', 'completed') AND last_checked >= ? "
                "ORDER BY last_checked DESC LIMIT 1",
                (team_id, started_at),
            ).fetchone()

            if run_row is None:
                logger.warning(
                    "No scouting_run found after crawl for team_id=%d; marking failed.", team_id
                )
                _mark_job_terminal(conn, crawl_job_id, "failed", "Scouting run not found after crawl")
                return

            season_id: str = run_row[0]
            scouting_dir = _DATA_ROOT / season_id / "scouting" / public_id

            if not scouting_dir.is_dir():
                logger.warning("Scouting dir not found at %s; marking failed.", scouting_dir)
                crawler.update_run_load_status(team_id, season_id, "failed")
                _mark_job_terminal(conn, crawl_job_id, "failed", "Scouting directory not found")
                return

            # Load phase.
            try:
                load_result = loader.load_team(scouting_dir, team_id, season_id)
            except Exception as exc:  # noqa: BLE001
                logger.error("Load failed for public_id=%s: %s", public_id, exc)
                crawler.update_run_load_status(team_id, season_id, "failed")
                _mark_job_terminal(conn, crawl_job_id, "failed", str(exc))
                return

            if load_result.errors:
                crawler.update_run_load_status(team_id, season_id, "failed")
                _mark_job_terminal(
                    conn, crawl_job_id, "failed", f"Load errors: {load_result.errors}"
                )
            else:
                crawler.update_run_load_status(team_id, season_id, "completed")
                _mark_job_terminal(conn, crawl_job_id, "completed", None)
                _update_last_synced(conn, team_id)

                # 3. Spray chart enrichment (non-fatal; job stays "completed").
                gc_uuid = _resolve_team_gc_uuid(conn, team_id, public_id, client)
                _run_spray_stages(
                    conn, client, team_id, public_id, gc_uuid, season_id
                )

                # 4. Post-spray dedup sweep (Hook 2).
                # Catches duplicate player stubs re-created by the spray loader.
                try:
                    from src.db.player_dedup import dedup_team_players

                    dedup_team_players(
                        conn, team_id, season_id, manage_transaction=True
                    )
                except Exception:  # noqa: BLE001
                    logger.error(
                        "Post-spray dedup failed for team_id=%d (non-fatal)",
                        team_id,
                        exc_info=True,
                    )

            logger.info(
                "Scouting sync complete: team_id=%d public_id=%s loaded=%d errors=%d",
                team_id, public_id, load_result.loaded, load_result.errors,
            )

    except Exception as exc:  # noqa: BLE001
        logger.error("Scouting sync uncaught error: team_id=%d: %s", team_id, exc)
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.execute("PRAGMA foreign_keys=ON;")
            _mark_job_terminal(conn, crawl_job_id, "failed", str(exc))
