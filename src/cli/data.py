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

_CRAWLER_CHOICES = ["roster", "schedule", "opponent", "player-stats", "game-stats"]
_LOADER_CHOICES = ["roster", "game", "season-stats"]


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
    """
    if dry_run:
        _scout_dry_run(profile=profile, team=team, season=season)
        raise SystemExit(0)

    _scout_live(profile=profile, team=team, season=season)


def _scout_dry_run(
    profile: str,
    team: Optional[str],
    season: Optional[str],
) -> None:
    """Print dry-run summary for the scout command and return."""
    db_path = _resolve_db_path()
    typer.echo("Dry run -- no API calls or DB writes will be performed.")
    typer.echo(f"Profile: {profile}")
    typer.echo(f"DB path: {db_path}")
    if team:
        typer.echo(f"Would scout: public_id={team}")
    else:
        typer.echo("Would scout all opponents with a public_id.")
    if season:
        typer.echo(f"Season override: {season}")


def _scout_live(
    profile: str,
    team: Optional[str],
    season: Optional[str],
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

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        crawler = ScoutingCrawler(client, conn)
        loader = _ScoutingLoader(conn)
        try:
            exit_code = _run_scout_pipeline(conn, crawler, loader, data_root, team, season, started_at)
        except Exception as exc:
            logger.error("Scouting failed: %s", exc)
            typer.echo(f"Error: {exc}", err=True)
            exit_code = 1

    raise SystemExit(exit_code)


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
    from src.gamechanger.client import GameChangerClient
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
        except Exception as exc:
            logger.error("Opponent resolution failed: %s", exc)
            typer.echo(f"Error: {exc}", err=True)
            raise SystemExit(1) from exc

    typer.echo(f"Opponent resolution complete: resolved={result.resolved} unlinked={result.unlinked} stored_hidden={result.stored_hidden} errors={result.errors}")
    raise SystemExit(1 if result.errors else 0)

