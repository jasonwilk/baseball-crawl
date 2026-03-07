"""bb data -- data pipeline commands (crawl, load, sync)."""

from __future__ import annotations

from enum import Enum
from typing import Optional

import typer

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
    from scripts.bootstrap import run

    raise SystemExit(run(check_only=check_only, profile=profile, dry_run=dry_run))


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

    from scripts.crawl import run

    raise SystemExit(
        run(
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

    from scripts.load import run

    raise SystemExit(
        run(
            dry_run=dry_run,
            loader_filter=loader,
            source=source.value,
        )
    )
