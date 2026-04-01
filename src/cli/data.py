"""bb data -- data pipeline commands (crawl, load, sync, resolve-opponents)."""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import closing
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import typer

if TYPE_CHECKING:
    from src.gamechanger.crawlers.scouting import ScoutingCrawler
    from src.gamechanger.loaders.scouting_loader import ScoutingLoader

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

_CRAWLER_CHOICES = ["roster", "schedule", "opponent", "player-stats", "game-stats", "spray-chart", "plays", "scouting-spray"]
_LOADER_CHOICES = ["roster", "schedule", "game", "plays", "season-stats", "spray-chart", "scouting-spray"]


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

    # scouting-spray is special-cased: it needs a DB connection to look up
    # gc_uuid values and is NOT routed through the pipeline factory.
    if crawler == "scouting-spray":
        if dry_run:
            typer.echo("Dry run: would crawl scouting spray charts (skipping).")
            raise SystemExit(0)
        _crawl_scouting_spray(profile=profile)
        return  # _crawl_scouting_spray raises SystemExit; this line is unreachable

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

    # scouting-spray is special-cased: it needs a DB connection and scans the
    # scouting data tree directly -- NOT routed through the pipeline factory.
    if loader == "scouting-spray":
        if dry_run:
            typer.echo("Dry run: would load scouting spray charts (skipping).")
            raise SystemExit(0)
        _load_scouting_spray()
        return  # _load_scouting_spray raises SystemExit; unreachable

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


def _crawl_scouting_spray(profile: str) -> None:
    """Run the scouting spray chart crawl independently.

    Creates a DB connection, instantiates ``ScoutingSprayChartCrawler``, and
    calls ``crawl_all()``.  Raises ``SystemExit`` with exit code 0 on success
    or 1 on error.
    """
    from src.gamechanger.client import GameChangerClient
    from src.gamechanger.crawlers.scouting_spray import ScoutingSprayChartCrawler

    db_path = _resolve_db_path()
    data_root = _PROJECT_ROOT / "data" / "raw"
    client = GameChangerClient(profile=profile)

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        spray_crawler = ScoutingSprayChartCrawler(client, conn, data_root=data_root)
        try:
            result = spray_crawler.crawl_all()
        except Exception as exc:
            logger.error("Scouting spray crawl failed: %s", exc)
            typer.echo(f"Error: {exc}", err=True)
            raise SystemExit(1) from exc

    typer.echo(
        f"Scouting spray crawl complete: "
        f"files_written={result.files_written} "
        f"files_skipped={result.files_skipped} "
        f"errors={result.errors}"
    )
    raise SystemExit(1 if result.errors else 0)


def _load_scouting_spray() -> None:
    """Run the scouting spray chart load independently.

    Creates a DB connection, instantiates ``ScoutingSprayChartLoader``, and
    calls ``load_all()``.  Raises ``SystemExit`` with exit code 0 on success
    or 1 on error.
    """
    from src.gamechanger.loaders.scouting_spray_loader import ScoutingSprayChartLoader

    db_path = _resolve_db_path()
    data_root = _PROJECT_ROOT / "data" / "raw"

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        spray_loader = ScoutingSprayChartLoader(conn)
        try:
            result = spray_loader.load_all(data_root)
        except Exception as exc:
            logger.error("Scouting spray load failed: %s", exc)
            typer.echo(f"Error: {exc}", err=True)
            raise SystemExit(1) from exc

    typer.echo(
        f"Scouting spray load complete: "
        f"loaded={result.loaded} "
        f"skipped={result.skipped} "
        f"errors={result.errors}"
    )
    raise SystemExit(1 if result.errors else 0)


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
        try:
            exit_code = _run_scout_pipeline(conn, crawler, loader, data_root, team, season, started_at)
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

            # Step 2: scouting spray crawl (runs after main crawl+load).
            spray_crawler = ScoutingSprayChartCrawler(client, conn, data_root=data_root)
            try:
                if team:
                    spray_result = spray_crawler.crawl_team(team, season_id=season)
                else:
                    spray_result = spray_crawler.crawl_all(season_id=season)
                typer.echo(
                    f"Scouting spray crawl: "
                    f"written={spray_result.files_written} "
                    f"skipped={spray_result.files_skipped} "
                    f"errors={spray_result.errors}"
                )
                if spray_result.errors:
                    exit_code = 1
            except Exception as exc:
                logger.error("Scouting spray crawl failed: %s", exc)
                typer.echo(f"Spray crawl error: {exc}", err=True)
                exit_code = 1

            if exit_code == 0:
                # Step 3: scouting spray load (runs after spray crawl).
                from src.gamechanger.loaders.scouting_spray_loader import ScoutingSprayChartLoader

                spray_loader = ScoutingSprayChartLoader(conn)
                try:
                    spray_load_result = spray_loader.load_all(
                        data_root,
                        public_id=team if team else None,
                        season_id=season,
                    )
                    typer.echo(
                        f"Scouting spray load: "
                        f"loaded={spray_load_result.loaded} "
                        f"skipped={spray_load_result.skipped} "
                        f"errors={spray_load_result.errors}"
                    )
                    if spray_load_result.errors:
                        exit_code = 1
                except Exception as exc:
                    logger.error("Scouting spray load failed: %s", exc)
                    typer.echo(f"Spray load error: {exc}", err=True)
                    exit_code = 1

    raise SystemExit(exit_code)


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
) -> int:
    """Run crawl + load for one team or all teams; return exit code."""
    if team:
        crawl_result = crawler.scout_team(team, season_id=season)
        typer.echo(
            f"Crawl complete for {team}: "
            f"files_written={crawl_result.files_written} "
            f"errors={crawl_result.errors}"
        )
        load_errors = _load_scouted_team(conn, crawler, loader, data_root, team, started_at)
    else:
        crawl_result = crawler.scout_all(season_id=season)
        typer.echo(
            f"Crawl complete: "
            f"files_written={crawl_result.files_written} "
            f"files_skipped={crawl_result.files_skipped} "
            f"errors={crawl_result.errors}"
        )
        load_errors = _load_all_scouted(conn, crawler, loader, data_root, started_at)
    return 1 if (crawl_result.errors or load_errors) else 0


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


def _load_all_scouted(
    conn: sqlite3.Connection,
    crawler: ScoutingCrawler,
    loader: ScoutingLoader,
    data_root: Path,
    started_at: str,
) -> int:
    """Load all opponents scouted during this session.

    Queries scouting_runs for crawled runs started since ``started_at`` and
    calls the loader for each.

    Returns:
        Total number of load errors across all teams.
    """
    runs = conn.execute(
        "SELECT sr.team_id, sr.season_id, t.public_id "
        "FROM scouting_runs sr JOIN teams t ON sr.team_id = t.id "
        "WHERE sr.status IN ('running', 'completed') AND sr.last_checked >= ?",
        (started_at,),
    ).fetchall()

    total_errors = 0
    for team_id, season_id, pub_id in runs:
        if pub_id is None:
            logger.warning(
                "Team id=%s has no public_id; cannot determine scouting directory. Skipping load.",
                team_id,
            )
            continue
        scouting_dir = data_root / season_id / "scouting" / pub_id
        if not scouting_dir.is_dir():
            logger.warning("Scouting dir not found at %s; skipping load.", scouting_dir)
            continue
        try:
            result = loader.load_team(scouting_dir, team_id, season_id)
        except Exception as exc:
            logger.error("Load failed for team_id=%s: %s", team_id, exc)
            typer.echo(f"Load error for {pub_id}: {exc}", err=True)
            crawler.update_run_load_status(team_id, season_id, "failed")
            total_errors += 1
            continue

        if result.errors:
            typer.echo(
                f"Load errors for {pub_id} (season={season_id}): {result.errors} error(s).",
                err=True,
            )
            crawler.update_run_load_status(team_id, season_id, "failed")
            total_errors += result.errors
        else:
            crawler.update_run_load_status(team_id, season_id, "completed")
            typer.echo(f"Load complete for {pub_id} (season={season_id}).")
    return total_errors


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

