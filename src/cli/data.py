"""bb data -- data pipeline commands (crawl, load, sync, resolve-opponents)."""

from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from contextlib import closing
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import typer

if TYPE_CHECKING:
    from src.gamechanger.crawlers.scouting import ScoutingCrawler
    from src.gamechanger.loaders.scouting_loader import ScoutingLoader
    from src.reconciliation.engine import ReconciliationSummary

from src.db.merge import DuplicateTeam
from src.pipeline import bootstrap as bootstrap_module
from src.pipeline import crawl as crawl_module
from src.pipeline import load as load_module

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

_CRAWLER_CHOICES = ["roster", "schedule", "opponent", "player-stats", "game-stats", "spray-chart", "plays"]
_LOADER_CHOICES = ["roster", "schedule", "game", "plays", "season-stats", "spray-chart"]


class SourceOption(str, Enum):
    """Team config source for crawl and load commands."""

    yaml = "yaml"
    db = "db"


@app.command()
def sync(
    check_only: bool = typer.Option(
        False,
        "--check-only",
        help="Validate credentials and team config only -- skip crawl and load.",
    ),
    profile: str = typer.Option(
        "web",
        help="HTTP header profile for API requests (web or mobile).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Pass --dry-run through to crawl and load stages (no API calls or DB writes).",
    ),
) -> None:
    """Validate credentials, crawl data, and load into database.

    Uses YAML team config (config/teams.yaml) by default. For database-sourced
    team config, use `bb data crawl --source db` and `bb data load --source db`
    separately.
    """
    raise SystemExit(bootstrap_module.run(check_only=check_only, profile=profile, dry_run=dry_run))


@app.command()
def crawl(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print what would run without making API calls or writing files.",
    ),
    crawler: Optional[str] = typer.Option(
        None,
        "--crawler",
        help=f"Run only one crawler. Choices: {', '.join(_CRAWLER_CHOICES)}",
        metavar="NAME",
    ),
    profile: str = typer.Option(
        "web",
        help="HTTP header profile for API requests (web or mobile).",
    ),
    source: SourceOption = typer.Option(
        SourceOption.yaml,
        "--source",
        help="Config source: 'yaml' reads config/teams.yaml; 'db' reads from SQLite.",
    ),
) -> None:
    """Refresh all raw data from the GameChanger API."""
    if crawler is not None and crawler not in _CRAWLER_CHOICES:
        typer.echo(
            f"Error: Invalid crawler '{crawler}'. Choices: {', '.join(_CRAWLER_CHOICES)}",
            err=True,
        )
        raise SystemExit(1)

    raise SystemExit(
        crawl_module.run(
            dry_run=dry_run,
            crawler_filter=crawler,
            profile=profile,
            source=source.value,
        )
    )


@app.command()
def load(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print what would load without touching the database.",
    ),
    loader: Optional[str] = typer.Option(
        None,
        "--loader",
        help=f"Run only one loader. Choices: {', '.join(_LOADER_CHOICES)}",
        metavar="NAME",
    ),
    source: SourceOption = typer.Option(
        SourceOption.yaml,
        "--source",
        help="Config source: 'yaml' reads config/teams.yaml; 'db' reads from SQLite.",
    ),
) -> None:
    """Load raw GameChanger JSON files into the database."""
    if loader is not None and loader not in _LOADER_CHOICES:
        typer.echo(
            f"Error: Invalid loader '{loader}'. Choices: {', '.join(_LOADER_CHOICES)}",
            err=True,
        )
        raise SystemExit(1)

    raise SystemExit(
        load_module.run(
            dry_run=dry_run,
            loader_filter=loader,
            source=source.value,
        )
    )


@app.command()
def scout(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Log what would be scouted without making API calls or DB writes.",
    ),
    team: Optional[str] = typer.Option(
        None,
        "--team",
        help="Scout a specific opponent by public_id (slug). Scouts all if omitted.",
        metavar="PUBLIC_ID",
    ),
    season: Optional[str] = typer.Option(
        None,
        "--season",
        help="Override the auto-derived season_id (e.g. '2025-spring-hs').",
        metavar="SEASON_ID",
    ),
    profile: str = typer.Option(
        "web",
        help="HTTP header profile for API requests (web or mobile).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Bypass the 24-hour freshness check and re-scout all opponents.",
    ),
) -> None:
    """Scout opponent teams: fetch schedule, roster, and boxscores from public endpoints.

    Queries opponent_links for all opponents with a public_id (or scouts only
    the specified --team), crawls public/authenticated GameChanger API
    endpoints, and loads the results into the database.

    Season is derived automatically from the game schedule unless --season is
    provided.

    Examples:
        bb data scout                           # scout all opponents
        bb data scout --team QTiLIb2Lui3b      # scout one opponent by public_id
        bb data scout --dry-run                 # show what would be scouted
        bb data scout --force                   # re-scout all, bypassing freshness check
    """
    if dry_run:
        _scout_dry_run(profile=profile, team=team, season=season, force=force)
        raise SystemExit(0)

    _scout_live(profile=profile, team=team, season=season, force=force)


def _scout_dry_run(
    profile: str,
    team: Optional[str],
    season: Optional[str],
    force: bool = False,
) -> None:
    """Print dry-run summary for the scout command and return."""
    db_path = _resolve_db_path()
    typer.echo("Dry run -- no API calls or DB writes will be performed.")
    typer.echo(f"Profile: {profile}")
    typer.echo(f"DB path: {db_path}")
    if force:
        if team:
            typer.echo(
                "Force mode active (has no effect with --team; single-team mode already bypasses freshness)."
            )
        else:
            typer.echo("Force mode: freshness check bypassed -- all opponents will be re-scouted.")
    if team:
        typer.echo(f"Would scout: public_id={team}")
    else:
        typer.echo("Would scout all opponents with a public_id.")
    if season:
        typer.echo(f"Season override: {season}")


def _heal_season_year_scouting(
    conn: sqlite3.Connection, team_id: int, public_id: str
) -> None:
    """Backfill season_year for a tracked team if NULL.

    Calls resolve_team (public, no auth) and UPDATEs season_year WHERE IS NULL.
    Best-effort: any failure is logged and skipped.
    """
    from src.gamechanger.team_resolver import resolve_team

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
            logger.info("Healed season_year=%s for team_id=%d (scouting/cli)", profile.year, team_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("season_year heal failed for team_id=%d: %s", team_id, exc)


def _scout_live(
    profile: str,
    team: Optional[str],
    season: Optional[str],
    force: bool = False,
) -> None:
    """Execute the scouting pipeline (crawl + load) and exit with a status code."""
    from datetime import datetime, timezone

    from src.gamechanger.client import GameChangerClient
    from src.gamechanger.crawlers.scouting import ScoutingCrawler
    from src.gamechanger.loaders.scouting_loader import ScoutingLoader as _ScoutingLoader

    db_path = _resolve_db_path()
    data_root = _PROJECT_ROOT / "data" / "raw"
    client = GameChangerClient(profile=profile)
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    from src.gamechanger.crawlers.scouting_spray import ScoutingSprayChartCrawler

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")

        # Self-heal season_year before crawl starts.
        _heal_season_year_cli(conn, team)

        freshness_hours = 0 if force else 24
        crawler = ScoutingCrawler(client, conn, freshness_hours=freshness_hours)
        loader = _ScoutingLoader(conn)
        crawl_results: list = []
        try:
            exit_code, crawl_results = _run_scout_pipeline(
                conn, crawler, loader, data_root, team, season, started_at,
            )
        except Exception as exc:
            logger.error("Scouting failed: %s", exc)
            typer.echo(f"Error: {exc}", err=True)
            exit_code = 1

        if exit_code != 0:
            # Main scouting pipeline failed; skip spray stages because game and
            # roster rows that the spray loader depends on may be missing.
            logger.warning(
                "Main scouting pipeline failed (exit_code=%d); "
                "skipping spray crawl and load stages.",
                exit_code,
            )
        else:
            # Step 1.5: opportunistic gc_uuid resolution for tracked teams.
            # Runs after main crawl/load (which populates games table) and
            # before spray crawl (which benefits from resolved gc_uuids).
            _resolve_missing_gc_uuids(conn, data_root, client, team)

            # Step 2 + 3: scouting spray crawl + load PER TEAM (in-memory,
            # E-220 C2-B).  Each team uses its own ScoutingCrawlResult.games
            # so spray reads zero bytes from data/raw/.../scouting/.
            from src.gamechanger.loaders.scouting_spray_loader import ScoutingSprayChartLoader
            spray_crawler = ScoutingSprayChartCrawler(client, conn)
            spray_loader = ScoutingSprayChartLoader(conn)
            total_spray_crawled = 0
            total_spray_loaded = 0
            total_spray_errors = 0
            for cr in crawl_results:
                pub_id = getattr(cr, "public_id", "") or ""
                if not pub_id or not getattr(cr, "games", None):
                    continue
                try:
                    spray_result = spray_crawler.crawl_team(
                        pub_id,
                        season_id=cr.season_id or season,
                        games_data=cr.games,
                    )
                except CredentialExpiredError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Scouting spray crawl failed for %s: %s", pub_id, exc,
                    )
                    typer.echo(f"Spray crawl error for {pub_id}: {exc}", err=True)
                    total_spray_errors += 1
                    continue
                total_spray_crawled += spray_result.games_crawled
                total_spray_errors += spray_result.errors

                if spray_result.errors:
                    continue
                try:
                    spray_load_result = spray_loader.load_from_data(
                        spray_result.spray_data,
                        public_id=pub_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error("Scouting spray load failed for %s: %s", pub_id, exc)
                    typer.echo(f"Spray load error for {pub_id}: {exc}", err=True)
                    total_spray_errors += 1
                    continue
                total_spray_loaded += spray_load_result.loaded
                total_spray_errors += spray_load_result.errors

            typer.echo(
                f"Scouting spray crawl: crawled={total_spray_crawled} "
                f"errors={total_spray_errors}"
            )
            typer.echo(
                f"Scouting spray load: loaded={total_spray_loaded} "
                f"errors={total_spray_errors}"
            )
            if total_spray_errors:
                exit_code = 1

        # Step 4: post-spray dedup sweep (Hook 2).
        # Catches duplicate player stubs re-created by the spray loader.
        try:
            _post_spray_dedup(conn, team, season, started_at)
        except Exception:  # noqa: BLE001
            logger.error(
                "Post-spray dedup sweep failed (non-fatal)", exc_info=True
            )

    raise SystemExit(exit_code)


def _post_spray_dedup(
    conn: sqlite3.Connection,
    team_public_id: str | None,
    season_filter: str | None,
    started_at: str,
) -> None:
    """Run post-spray dedup sweep for teams scouted in this pipeline run.

    Queries ``scouting_runs`` for teams with runs checked after ``started_at``
    and runs ``dedup_team_players()`` for each with ``manage_transaction=True``.

    Args:
        conn: Open SQLite connection.
        team_public_id: If given, scope to this single team's public_id.
        season_filter: If given, scope to this season.
        started_at: ISO timestamp marking the start of this pipeline run.
    """
    from src.db.player_dedup import dedup_team_players

    if team_public_id:
        # Single-team mode: look up team_id and season_id from scouting_runs.
        lookup = _find_scouting_run(conn, team_public_id, started_at)
        if lookup is None:
            return
        team_id, season_id = lookup
        dedup_team_players(conn, team_id, season_id, manage_transaction=True)
    else:
        # All-teams mode: find all teams with recent scouting runs.
        query = (
            "SELECT DISTINCT sr.team_id, sr.season_id "
            "FROM scouting_runs sr "
            "WHERE sr.last_checked >= ?"
        )
        params: list[object] = [started_at]
        if season_filter:
            query += " AND sr.season_id = ?"
            params.append(season_filter)

        rows = conn.execute(query, params).fetchall()
        for tid, sid in rows:
            try:
                dedup_team_players(conn, tid, sid, manage_transaction=True)
            except Exception:  # noqa: BLE001
                logger.error(
                    "Post-spray dedup failed for team_id=%d season=%s (non-fatal)",
                    tid,
                    sid,
                    exc_info=True,
                )


def _resolve_missing_gc_uuids(
    conn: sqlite3.Connection,
    data_root: Path,
    client: GameChangerClient,
    team_public_id: Optional[str] = None,
) -> None:
    """Run the gc_uuid resolution cascade for tracked teams missing gc_uuid.

    When *team_public_id* is given, resolves only that single team (if it
    lacks gc_uuid).  Otherwise resolves all tracked teams with
    ``gc_uuid IS NULL``.

    Errors are logged but never propagated -- the spray crawl stage
    proceeds regardless.  ``CredentialExpiredError`` from tier 3 is also
    caught here (the spray crawl may still succeed using the boxscore
    fallback path even without gc_uuid).
    """
    from src.gamechanger.exceptions import CredentialExpiredError
    from src.gamechanger.resolvers.gc_uuid_resolver import resolve_gc_uuid

    try:
        if team_public_id:
            rows = conn.execute(
                "SELECT id, public_id, name, season_year FROM teams "
                "WHERE public_id = ? AND gc_uuid IS NULL AND membership_type = 'tracked' "
                "LIMIT 1",
                (team_public_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, public_id, name, season_year FROM teams "
                "WHERE gc_uuid IS NULL AND membership_type = 'tracked' AND is_active = 1"
            ).fetchall()

        resolved_count = 0
        for tid, pub_id, name, syear in rows:
            try:
                result = resolve_gc_uuid(
                    team_id=tid,
                    public_id=pub_id,
                    team_name=name,
                    season_year=syear,
                    conn=conn,
                    data_root=data_root,
                    client=client,
                )
                if result:
                    resolved_count += 1
            except CredentialExpiredError:
                logger.warning(
                    "gc_uuid resolution stopped: credentials expired (team_id=%d)", tid,
                )
                break
            except Exception:  # noqa: BLE001
                logger.warning(
                    "gc_uuid resolution failed for team_id=%d", tid, exc_info=True,
                )

        if resolved_count:
            typer.echo(f"gc_uuid resolved for {resolved_count} tracked team(s).")
    except Exception:  # noqa: BLE001
        logger.warning("gc_uuid resolution query failed", exc_info=True)


def _heal_season_year_cli(
    conn: sqlite3.Connection, team_public_id: Optional[str]
) -> None:
    """Heal season_year for tracked teams before CLI scouting.

    When *team_public_id* is provided, heals only that team.  Otherwise
    heals all tracked teams with ``season_year IS NULL``.

    Silently returns if the ``season_year`` column does not exist
    (pre-migration-004 database).
    """
    try:
        if team_public_id:
            row = conn.execute(
                "SELECT id FROM teams WHERE public_id = ? LIMIT 1",
                (team_public_id,),
            ).fetchone()
            if row is not None:
                _heal_season_year_scouting(conn, row[0], team_public_id)
        else:
            rows = conn.execute(
                "SELECT id, public_id FROM teams "
                "WHERE membership_type = 'tracked' AND season_year IS NULL AND public_id IS NOT NULL"
            ).fetchall()
            for team_id, pub_id in rows:
                _heal_season_year_scouting(conn, team_id, pub_id)
    except sqlite3.OperationalError:
        logger.debug("season_year column not available, skipping heal")


def _run_scout_pipeline(
    conn: sqlite3.Connection,
    crawler: ScoutingCrawler,
    loader: ScoutingLoader,
    data_root: Path,
    team: Optional[str],
    season: Optional[str],
    started_at: str,
) -> tuple[int, list]:
    """Run crawl + load for one team or all teams.

    E-220 C2-A: both branches now use in-memory ScoutingCrawlResults.  No
    disk reads from data/raw/.../scouting/ in this code path.

    Returns:
        Tuple of ``(exit_code, crawl_results)`` where ``crawl_results`` is
        the list of in-memory ``ScoutingCrawlResult`` objects (one per team).
        Callers (e.g. ``_scout_live``) use the per-team results to drive the
        spray pipeline without re-reading disk.
    """
    if team:
        crawl_result = crawler.scout_team(team, season_id=season)
        typer.echo(
            f"Crawl complete for {team}: "
            f"games_crawled={crawl_result.games_crawled} "
            f"errors={crawl_result.errors}"
        )
        load_errors = _load_scouted_team_in_memory(
            conn, crawler, loader, team, crawl_result, started_at,
        )
        total_errors = crawl_result.errors
        crawl_results = [crawl_result]
    else:
        crawl_results = crawler.scout_all_in_memory(season_id=season)
        total_games_crawled = sum(r.games_crawled for r in crawl_results)
        total_errors = sum(r.errors for r in crawl_results)
        typer.echo(
            f"Crawl complete: "
            f"teams_scouted={len(crawl_results)} "
            f"games_crawled={total_games_crawled} "
            f"errors={total_errors}"
        )
        load_errors = 0
        for cr in crawl_results:
            pub_id = getattr(cr, "public_id", "") or ""
            load_errors += _load_scouted_team_in_memory(
                conn, crawler, loader, pub_id, cr, started_at,
            )
    exit_code = 1 if (total_errors or load_errors) else 0
    return exit_code, crawl_results


def _find_scouting_run(
    conn: sqlite3.Connection,
    public_id: str,
    started_at: str,
) -> tuple[int, str] | None:
    """Look up the team INTEGER PK and season for the most recent eligible scouting run.

    Args:
        conn: Open SQLite connection.
        public_id: Team public_id slug.
        started_at: ISO timestamp — only runs checked after this time are considered.

    Returns:
        ``(team_id, season_id)`` or ``None`` if no matching team or run is found.
    """
    row = conn.execute(
        "SELECT id FROM teams WHERE public_id = ? LIMIT 1", (public_id,)
    ).fetchone()
    if row is None:
        logger.info("No team row found for public_id=%s; skipping load.", public_id)
        return None
    team_id: int = row[0]

    run = conn.execute(
        "SELECT season_id FROM scouting_runs "
        "WHERE team_id = ? AND status IN ('running', 'completed') AND last_checked >= ? "
        "ORDER BY last_checked DESC LIMIT 1",
        (team_id, started_at),
    ).fetchone()
    if run is None:
        logger.info("No eligible scouting run found for public_id=%s; skipping load.", public_id)
        return None

    return team_id, run[0]


def _load_scouted_team(
    conn: sqlite3.Connection,
    crawler: ScoutingCrawler,
    loader: ScoutingLoader,
    data_root: Path,
    public_id: str,
    started_at: str,
) -> int:
    """Load scouting data for a single team after crawling.

    Queries scouting_runs for the most recently crawled run for this team,
    calls the loader, and updates the run status based on the load outcome.

    Returns:
        Number of load errors (0 on success).
    """
    lookup = _find_scouting_run(conn, public_id, started_at)
    if lookup is None:
        return 0
    team_id, season_id = lookup

    scouting_dir = data_root / season_id / "scouting" / public_id
    if not scouting_dir.is_dir():
        logger.warning("Scouting dir not found at %s; skipping load.", scouting_dir)
        return 0

    try:
        result = loader.load_team(scouting_dir, team_id, season_id)
    except Exception as exc:
        logger.error("Load failed for public_id=%s: %s", public_id, exc)
        typer.echo(f"Load error for {public_id}: {exc}", err=True)
        crawler.update_run_load_status(team_id, season_id, "failed")
        return 1

    if result.errors:
        typer.echo(
            f"Load errors for {public_id} (season={season_id}): {result.errors} error(s).",
            err=True,
        )
        crawler.update_run_load_status(team_id, season_id, "failed")
        return result.errors

    crawler.update_run_load_status(team_id, season_id, "completed")
    typer.echo(f"Load complete for {public_id} (season={season_id}).")
    return 0


def _load_scouted_team_in_memory(
    conn: sqlite3.Connection,
    crawler: ScoutingCrawler,
    loader: ScoutingLoader,
    public_id: str,
    crawl_result: object,
    started_at: str,
) -> int:
    """Load scouting data from an in-memory crawl result (E-220-05).

    Returns:
        Number of load errors (0 on success).
    """
    season_id = getattr(crawl_result, "season_id", "")
    team_id = getattr(crawl_result, "team_id", None)

    if getattr(crawl_result, "errors", 0) > 0 and getattr(crawl_result, "games_crawled", 0) == 0:
        # Crawl errored and produced nothing -- mark the run failed so it
        # surfaces to operators (mirrors disk-based _load_scouted_team).
        typer.echo(
            f"Crawl failure for {public_id}: errors={crawl_result.errors}, no games crawled.",
            err=True,
        )
        if team_id and season_id:
            crawler.update_run_load_status(team_id, season_id, "failed")
        return int(getattr(crawl_result, "errors", 1)) or 1
    if getattr(crawl_result, "skipped", False):
        return 0  # No completed games.

    try:
        result = loader.load_team(crawl_result)
    except Exception as exc:
        logger.error("Load failed for public_id=%s: %s", public_id, exc)
        typer.echo(f"Load error for {public_id}: {exc}", err=True)
        if team_id and season_id:
            crawler.update_run_load_status(team_id, season_id, "failed")
        return 1

    if result.errors:
        typer.echo(
            f"Load errors for {public_id} (season={season_id}): {result.errors} error(s).",
            err=True,
        )
        if team_id and season_id:
            crawler.update_run_load_status(team_id, season_id, "failed")
        return result.errors

    if team_id and season_id:
        crawler.update_run_load_status(team_id, season_id, "completed")
    typer.echo(f"Load complete for {public_id} (season={season_id}).")
    return 0


def _echo_dry_run_config(config: object) -> None:
    """Print dry-run summary of loaded config and exit."""
    typer.echo("Dry run -- no API calls or DB writes will be performed.")
    typer.echo(f"Season: {config.season}")  # type: ignore[attr-defined]
    typer.echo(f"Member teams ({len(config.member_teams)}):")  # type: ignore[attr-defined]
    for team in config.member_teams:  # type: ignore[attr-defined]
        typer.echo(f"  {team.name} ({team.id})")
    raise SystemExit(0)


def _resolve_db_path() -> Path:
    """Return DB path from DATABASE_PATH env var or the project default."""
    env_db = os.environ.get("DATABASE_PATH")
    if env_db is not None:
        env_path = Path(env_db)
        return env_path if env_path.is_absolute() else _PROJECT_ROOT / env_path
    return _DEFAULT_DB_PATH


@app.command(name="resolve-opponents")
def resolve_opponents(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print what would run without making API calls or DB writes.",
    ),
    profile: str = typer.Option(
        "web",
        help="HTTP header profile for API requests (web or mobile).",
    ),
) -> None:
    """Resolve opponent public IDs via the GameChanger API.

    Fetches the opponent registry for each configured owned team, resolves
    each opponent's canonical GameChanger team ID and public_id slug via
    GET /teams/{progenitor_team_id}, and upserts results into the
    opponent_links table.  Manual links are never overwritten.

    Uses YAML team config (config/teams.yaml).  Database path is read from
    the DATABASE_PATH environment variable, defaulting to data/app.db.
    """
    from src.gamechanger.client import CredentialExpiredError, GameChangerClient
    from src.gamechanger.config import load_config
    from src.gamechanger.crawlers.opponent_resolver import OpponentResolver

    db_path = _resolve_db_path()
    config = load_config(db_path=db_path)
    if dry_run:
        _echo_dry_run_config(config)
    client = GameChangerClient(profile=profile)

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        resolver = OpponentResolver(client, config, conn)
        try:
            result = resolver.resolve()
        except CredentialExpiredError as exc:
            logger.error("Opponent resolution failed (credentials expired): %s", exc)
            typer.echo(f"Error: {exc}", err=True)
            raise SystemExit(1) from exc
        except Exception as exc:
            logger.error("Opponent resolution failed: %s", exc)
            typer.echo(f"Error: {exc}", err=True)
            raise SystemExit(1) from exc

        typer.echo(
            f"Progenitor resolution complete: "
            f"resolved={result.resolved} unlinked={result.unlinked} "
            f"skipped_hidden={result.skipped_hidden} errors={result.errors}"
        )

        unlinked_failed = False
        try:
            unlinked_result = resolver.resolve_unlinked()
        except Exception as exc:
            logger.error("resolve_unlinked failed: %s", exc)
            typer.echo(f"resolve-unlinked error: {exc}", err=True)
            unlinked_failed = True
        else:
            typer.echo(
                f"Follow-bridge resolution complete: "
                f"resolved={unlinked_result.resolved} "
                f"follow_bridge_failed={unlinked_result.follow_bridge_failed} "
                f"errors={unlinked_result.errors}"
            )
            if unlinked_result.errors:
                unlinked_failed = True

    raise SystemExit(1 if (result.errors or unlinked_failed) else 0)


# ---------------------------------------------------------------------------
# dedup command
# ---------------------------------------------------------------------------


def _select_canonical(
    group: list[DuplicateTeam],
) -> tuple[DuplicateTeam, list[DuplicateTeam]]:
    """Select the canonical team from a duplicate group using the heuristic.

    Priority order: has_stats > game_count > lowest id.

    Args:
        group: List of DuplicateTeam records.

    Returns:
        Tuple of (canonical, duplicates) where duplicates is sorted weakest-first.
    """
    sorted_group = sorted(
        group,
        key=lambda t: (t.has_stats, t.game_count, -t.id),
        reverse=True,
    )
    return sorted_group[0], sorted_group[1:]


def _format_team(t: DuplicateTeam) -> str:
    """Format a DuplicateTeam for CLI output."""
    gc = "gc_uuid" if t.gc_uuid else "no gc_uuid"
    pub = "public_id" if t.public_id else "no public_id"
    stats = "has_stats" if t.has_stats else "no stats"
    return (
        f"  id={t.id}  name={t.name!r}  season_year={t.season_year}  "
        f"games={t.game_count}  {stats}  {gc}  {pub}"
    )


@app.command()
def dedup(
    execute: bool = typer.Option(
        False,
        "--execute",
        help="Perform the merges. Without this flag, only a dry-run preview is shown.",
    ),
    db_path: Path = typer.Option(
        _DEFAULT_DB_PATH,
        "--db",
        help="Path to the SQLite database.",
    ),
) -> None:
    """Identify and auto-merge duplicate tracked teams."""
    from src.db.merge import (
        find_duplicate_teams,
        merge_teams,
        preview_merge,
    )

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        try:
            groups = find_duplicate_teams(conn)
        except Exception as exc:
            typer.echo(f"Error finding duplicates: {exc}", err=True)
            raise SystemExit(1) from exc

        if not groups:
            typer.echo("No duplicate teams found.")
            raise SystemExit(0)

        mode = "EXECUTE" if execute else "DRY RUN"
        typer.echo(f"[{mode}] Found {len(groups)} duplicate group(s).\n")

        merged = 0
        skipped = 0
        skip_reasons: list[str] = []

        for i, group in enumerate(groups, 1):
            canonical, duplicates = _select_canonical(group)

            typer.echo(f"--- Group {i} ({len(group)} teams) ---")
            for t in group:
                marker = " << canonical" if t.id == canonical.id else ""
                typer.echo(f"{_format_team(t)}{marker}")

            reason = f"has_stats={canonical.has_stats} games={canonical.game_count} id={canonical.id}"
            typer.echo(f"  Canonical: id={canonical.id} ({reason})")

            # Merge pairwise: weakest into canonical
            group_merged = 0
            group_skipped = 0
            for dup in duplicates:
                # Safety: never merge two teams that both have different non-NULL
                # season_year values -- that would be cross-season dedup.
                if (
                    canonical.season_year is not None
                    and dup.season_year is not None
                    and canonical.season_year != dup.season_year
                ):
                    typer.echo(
                        f"  SKIP merge {dup.id} -> {canonical.id}: "
                        f"different season_years ({dup.season_year} vs {canonical.season_year})"
                    )
                    group_skipped += 1
                    skip_reasons.append(
                        f"group {i}: cross-season merge blocked for "
                        f"id={dup.id} (year={dup.season_year}) vs "
                        f"id={canonical.id} (year={canonical.season_year})"
                    )
                    continue

                try:
                    preview = preview_merge(canonical.id, dup.id, conn)
                except Exception as exc:
                    typer.echo(f"  SKIP merge {dup.id} -> {canonical.id}: preview error: {exc}")
                    group_skipped += 1
                    skip_reasons.append(f"group {i}: preview error for id={dup.id}")
                    continue

                if preview.games_between_teams > 0:
                    typer.echo(
                        f"  SKIP merge {dup.id} -> {canonical.id}: "
                        f"{preview.games_between_teams} game(s) between teams"
                    )
                    group_skipped += 1
                    skip_reasons.append(
                        f"group {i}: {preview.games_between_teams} games between "
                        f"id={dup.id} and id={canonical.id}"
                    )
                    continue

                if execute:
                    try:
                        merge_teams(canonical.id, dup.id, conn)
                        typer.echo(f"  MERGED id={dup.id} -> id={canonical.id}")
                        group_merged += 1
                    except Exception as exc:
                        typer.echo(f"  ERROR merging {dup.id} -> {canonical.id}: {exc}")
                        group_skipped += 1
                        skip_reasons.append(f"group {i}: merge error for id={dup.id}: {exc}")
                else:
                    typer.echo(f"  Would merge id={dup.id} -> id={canonical.id}")
                    group_merged += 1

            merged += group_merged
            skipped += group_skipped
            typer.echo("")

        typer.echo(f"Summary: {len(groups)} group(s) found, {merged} merged, {skipped} skipped.")
        if skip_reasons:
            typer.echo("Skip reasons:")
            for reason in skip_reasons:
                typer.echo(f"  - {reason}")

    raise SystemExit(0)


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


# ---------------------------------------------------------------------------
# bb data repair-opponents
# ---------------------------------------------------------------------------


@app.command("repair-opponents")
def repair_opponents(
    execute: bool = typer.Option(
        False,
        "--execute",
        help="Apply changes. Without this flag, only a dry-run preview is shown.",
    ),
    db_path: Path = typer.Option(
        _DEFAULT_DB_PATH,
        "--db",
        help="Path to the SQLite database.",
    ),
) -> None:
    """Propagate existing opponent_links resolutions to team_opponents.

    Fixes the data disconnect for opponents resolved before write-through was
    implemented.  For each resolved opponent_links row, upserts a team_opponents
    row, activates the resolved team, and reassigns FK references from any old
    stub to the resolved team.

    Dry-run by default -- pass --execute to apply changes.
    """
    from src.api.db import _find_tracked_stub, finalize_opponent_resolution

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        rows = conn.execute(
            """
            SELECT ol.id, ol.our_team_id, ol.resolved_team_id, ol.opponent_name,
                   our_t.name AS our_team_name, our_t.season_year
            FROM opponent_links ol
            JOIN teams our_t ON our_t.id = ol.our_team_id
            WHERE ol.resolved_team_id IS NOT NULL
            """,
        ).fetchall()

        if not rows:
            typer.echo("No resolved opponent_links found. Nothing to repair.")
            raise SystemExit(0)

        mode = "EXECUTE" if execute else "DRY RUN"
        typer.echo(f"[{mode}] Found {len(rows)} resolved opponent link(s) to process.\n")

        created = 0
        updated = 0
        activated = 0
        no_op = 0
        fk_reassigned = 0

        for row in rows:
            link_id, our_team_id, resolved_team_id, opponent_name, our_team_name, season_year = row

            # Preview: describe what finalize will do
            existing = conn.execute(
                "SELECT opponent_team_id FROM team_opponents "
                "WHERE our_team_id = ? AND opponent_team_id = ?",
                (our_team_id, resolved_team_id),
            ).fetchone()
            is_active_row = conn.execute(
                "SELECT is_active FROM teams WHERE id = ?", (resolved_team_id,)
            ).fetchone()
            is_active = is_active_row[0] == 1 if is_active_row else False
            stub_id = _find_tracked_stub(conn, our_team_id, opponent_name)
            has_stub = stub_id is not None and stub_id != resolved_team_id

            if has_stub:
                action = f"REPLACE stub (team {stub_id})"
            elif not existing:
                action = "CREATE"
            elif not is_active:
                action = "ACTIVATE"
            else:
                action = "VERIFY"

            active_note = "" if is_active else " + activate"
            typer.echo(
                f"  {action}: {opponent_name} "
                f"(our_team={our_team_name}, resolved_id={resolved_team_id}){active_note}"
            )

            if execute:
                was_active_before = is_active
                had_row_before = existing is not None
                result = finalize_opponent_resolution(
                    conn,
                    our_team_id=our_team_id,
                    resolved_team_id=resolved_team_id,
                    opponent_name=opponent_name,
                    first_seen_year=season_year,
                )
                old_stub = result.get("old_stub_team_id")
                if old_stub:
                    updated += 1
                    fk_reassigned += result.get("fk_rows_moved", 0)
                elif not had_row_before:
                    created += 1
                else:
                    no_op += 1
                if not was_active_before:
                    activated += 1

        if execute:
            conn.commit()

        typer.echo(f"\nSummary ({mode}):")
        if execute:
            typer.echo(f"  team_opponents created: {created}")
            typer.echo(f"  team_opponents updated (stub replaced): {updated}")
            typer.echo(f"  teams activated: {activated}")
            typer.echo(f"  FK rows reassigned: {fk_reassigned}")
            typer.echo(f"  no-op (already correct): {no_op}")
        else:
            typer.echo(f"  total to process: {len(rows)}")
            typer.echo("\nRun with --execute to apply changes.")


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
    typer.echo("\nReminder: run 'bb data scout' to recompute scouting season aggregates.")

    raise SystemExit(0)
