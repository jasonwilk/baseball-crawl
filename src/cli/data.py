"""bb data -- data pipeline commands (crawl, load, sync, resolve-opponents)."""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import closing
from enum import Enum
from pathlib import Path
from typing import Optional

import typer

from src.pipeline import bootstrap as bootstrap_module
from src.pipeline import crawl as crawl_module
from src.pipeline import load as load_module

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "app.db"

app = typer.Typer(help="Data pipeline commands.")

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

    config = load_config()

    if dry_run:
        typer.echo("Dry run -- no API calls or DB writes will be performed.")
        typer.echo(f"Season: {config.season}")
        typer.echo(f"Owned teams ({len(config.owned_teams)}):")
        for team in config.owned_teams:
            typer.echo(f"  {team.name} ({team.id})")
        raise SystemExit(0)

    env_db = os.environ.get("DATABASE_PATH")
    if env_db is not None:
        env_path = Path(env_db)
        db_path = env_path if env_path.is_absolute() else _PROJECT_ROOT / env_path
    else:
        db_path = _DEFAULT_DB_PATH

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

    typer.echo(
        f"Opponent resolution complete: "
        f"resolved={result.resolved} "
        f"unlinked={result.unlinked} "
        f"skipped_hidden={result.skipped_hidden} "
        f"errors={result.errors}"
    )
    raise SystemExit(1 if result.errors else 0)
