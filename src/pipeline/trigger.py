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
from src.gamechanger.loaders.opponent_seeder import seed_schedule_opponents
from src.gamechanger.loaders.scouting_loader import ScoutingLoader
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

            logger.info(
                "Scouting sync complete: team_id=%d public_id=%s loaded=%d errors=%d",
                team_id, public_id, load_result.loaded, load_result.errors,
            )

    except Exception as exc:  # noqa: BLE001
        logger.error("Scouting sync uncaught error: team_id=%d: %s", team_id, exc)
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.execute("PRAGMA foreign_keys=ON;")
            _mark_job_terminal(conn, crawl_job_id, "failed", str(exc))
