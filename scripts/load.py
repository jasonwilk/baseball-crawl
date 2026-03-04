#!/usr/bin/env python3
"""Load orchestrator -- load all raw JSON files into the SQLite database.

Runs all available loaders in dependency order and prints a summary of
records loaded, skipped, and errored.

Usage::

    python scripts/load.py                        # run all loaders
    python scripts/load.py --dry-run              # preview without touching the DB
    python scripts/load.py --loader roster        # run one loader only
    python scripts/load.py --loader game          # run game loader only
    python scripts/load.py --loader season-stats  # run season-stats loader only

Available loader names: roster, game, season-stats
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root on sys.path so src.* imports work when run directly.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.gamechanger.config import load_config  # noqa: E402
from src.gamechanger.loaders import LoadResult  # noqa: E402
from src.gamechanger.loaders.game_loader import GameLoader  # noqa: E402
from src.gamechanger.loaders.roster import RosterLoader  # noqa: E402
from src.gamechanger.loaders.season_stats_loader import SeasonStatsLoader  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s -- %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

_DATA_ROOT = _PROJECT_ROOT / "data" / "raw"
_DB_PATH = _PROJECT_ROOT / "data" / "app.db"


# ---------------------------------------------------------------------------
# Loader registry
# ---------------------------------------------------------------------------

def _run_roster_loader(db: sqlite3.Connection, config: object, data_root: Path) -> LoadResult:
    """Run the roster loader for all owned teams.

    Loads each team's roster.json file found under data_root.

    Args:
        db: Open SQLite connection.
        config: Parsed CrawlConfig (season + owned_teams).
        data_root: Raw data root directory.

    Returns:
        Aggregated LoadResult across all teams.
    """
    loader = RosterLoader(db)
    combined = LoadResult()

    for team in config.owned_teams:
        roster_path = data_root / config.season / "teams" / team.id / "roster.json"
        if not roster_path.exists():
            logger.warning(
                "Roster file not found for team %s at %s; skipping.", team.id, roster_path
            )
            continue
        result = loader.load_file(roster_path)
        combined.loaded += result.loaded
        combined.skipped += result.skipped
        combined.errors += result.errors

    return combined


def _run_game_loader(db: sqlite3.Connection, config: object, data_root: Path) -> LoadResult:
    """Run the game loader for all owned teams.

    Loads each team's boxscore JSON files found under data_root/season/teams/team_id/games/.

    Args:
        db: Open SQLite connection.
        config: Parsed CrawlConfig (season + owned_teams).
        data_root: Raw data root directory.

    Returns:
        Aggregated LoadResult across all teams.
    """
    combined = LoadResult()

    for team in config.owned_teams:
        team_dir = data_root / config.season / "teams" / team.id
        loader = GameLoader(db, season_id=config.season, owned_team_id=team.id)
        if not team_dir.is_dir():
            logger.warning(
                "Team directory not found for team %s at %s; skipping.", team.id, team_dir
            )
            continue
        result = loader.load_all(team_dir)
        combined.loaded += result.loaded
        combined.skipped += result.skipped
        combined.errors += result.errors

    return combined


def _run_season_stats_loader(db: sqlite3.Connection, config: object, data_root: Path) -> LoadResult:
    """Run the season stats loader for all owned teams.

    Loads each team's stats.json file found under data_root/season/teams/team_id/stats.json.

    Args:
        db: Open SQLite connection.
        config: Parsed CrawlConfig (season + owned_teams).
        data_root: Raw data root directory.

    Returns:
        Aggregated LoadResult across all teams.
    """
    loader = SeasonStatsLoader(db)
    combined = LoadResult()

    for team in config.owned_teams:
        stats_path = data_root / config.season / "teams" / team.id / "stats.json"
        if not stats_path.exists():
            logger.warning(
                "Stats file not found for team %s at %s; skipping.", team.id, stats_path
            )
            continue
        result = loader.load_file(stats_path)
        combined.loaded += result.loaded
        combined.skipped += result.skipped
        combined.errors += result.errors

    return combined


# Ordered list of (name, runner) pairs.
# runner signature: (db, config, data_root) -> LoadResult
_LOADERS: list[tuple[str, object]] = [
    ("roster", _run_roster_loader),
    ("game", _run_game_loader),
    ("season-stats", _run_season_stats_loader),
]

_LOADER_NAMES = [name for name, _ in _LOADERS]


def _build_arg_parser() -> argparse.ArgumentParser:
    """Return the argument parser for load.py."""
    parser = argparse.ArgumentParser(
        description="Load raw GameChanger JSON files into the database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would load without touching the database.",
    )
    parser.add_argument(
        "--loader",
        metavar="NAME",
        choices=_LOADER_NAMES,
        help=f"Run only one loader. Choices: {', '.join(_LOADER_NAMES)}",
    )
    return parser


def run(
    dry_run: bool = False,
    loader_filter: str | None = None,
    data_root: Path = _DATA_ROOT,
    db_path: Path = _DB_PATH,
) -> int:
    """Execute the load orchestration.

    Args:
        dry_run: If True, print plan and return without writing to the DB.
        loader_filter: If set, run only the named loader.
        data_root: Override the raw data root (used in tests).
        db_path: Override the database path (used in tests).

    Returns:
        Exit code: 0 if all loaders completed, 1 if any raised an exception.
    """
    config = load_config()

    selected = [
        (name, runner)
        for name, runner in _LOADERS
        if loader_filter is None or name == loader_filter
    ]

    if dry_run:
        print("Dry run -- no database writes will be made.")
        print(f"Season: {config.season}")
        print(f"Database: {db_path}")
        print("Loaders that would run (in order):")
        for name, _ in selected:
            print(f"  {name}")
        return 0

    db = sqlite3.connect(str(db_path))
    db.execute("PRAGMA foreign_keys=ON;")

    had_exception = False
    total_loaded = 0
    total_skipped = 0
    total_errors = 0

    try:
        for name, runner in selected:
            logger.info("--- Starting loader: %s ---", name)
            try:
                result: LoadResult = runner(db, config, data_root)  # type: ignore[operator]
                total_loaded += result.loaded
                total_skipped += result.skipped
                total_errors += result.errors
                logger.info(
                    "Loader %s done: loaded=%d skipped=%d errors=%d",
                    name,
                    result.loaded,
                    result.skipped,
                    result.errors,
                )
            except Exception as exc:  # noqa: BLE001 -- log and continue
                logger.error("Loader %s raised an unhandled exception: %s", name, exc)
                total_errors += 1
                had_exception = True
    finally:
        db.close()

    logger.info(
        "Load complete: total loaded=%d skipped=%d errors=%d",
        total_loaded,
        total_skipped,
        total_errors,
    )
    return 1 if had_exception else 0


def main() -> None:
    """Entry point for ``python scripts/load.py``."""
    parser = _build_arg_parser()
    args = parser.parse_args()
    sys.exit(run(dry_run=args.dry_run, loader_filter=args.loader))


if __name__ == "__main__":
    main()
