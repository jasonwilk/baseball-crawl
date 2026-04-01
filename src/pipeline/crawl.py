"""Crawl orchestrator -- refresh all raw data from the GameChanger API.

Runs all available crawlers in dependency order and writes a manifest
summarising the run to ``data/raw/{season}/manifest.json``.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from src.gamechanger.client import GameChangerClient
from src.gamechanger.config import load_config, load_config_from_db
from src.gamechanger.crawlers import CrawlResult
from src.gamechanger.crawlers.roster import RosterCrawler
from src.gamechanger.crawlers.schedule import ScheduleCrawler
from src.gamechanger.crawlers.opponent import OpponentCrawler
from src.gamechanger.crawlers.player_stats import PlayerStatsCrawler
from src.gamechanger.crawlers.game_stats import GameStatsCrawler
from src.gamechanger.crawlers.plays import PlaysCrawler
from src.gamechanger.crawlers.spray_chart import SprayChartCrawler

logger = logging.getLogger(__name__)

# Repo root: src/pipeline/crawl.py is 3 levels deep, so .parents[2] is the repo root.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATA_ROOT = _PROJECT_ROOT / "data" / "raw"

# Ordered crawler names.  Order matters: schedule must run before game-stats.
# The actual class references are resolved lazily inside run() so that tests
# can patch module-level names (e.g. src.pipeline.crawl.RosterCrawler) and have
# the patches take effect.
_CRAWLER_NAMES: list[str] = [
    "roster",
    "schedule",
    "opponent",
    "player-stats",
    "game-stats",
    "spray-chart",
    "plays",
]


def _build_crawlers() -> list[tuple[str, object]]:
    """Return an ordered list of (name, crawler_instance_factory) pairs.

    Resolved at call time so that module-level name patches (in tests) take
    effect.  Each factory receives ``(client, config)`` and returns a crawler.
    """
    return [
        ("roster", lambda client, config: RosterCrawler(client, config)),
        ("schedule", lambda client, config: ScheduleCrawler(client, config)),
        ("opponent", lambda client, config: OpponentCrawler(client, config)),
        ("player-stats", lambda client, config: PlayerStatsCrawler(client, config)),
        ("game-stats", lambda client, config: GameStatsCrawler(client, config)),
        ("spray-chart", lambda client, config: SprayChartCrawler(client, config)),
        ("plays", lambda client, config: PlaysCrawler(client, config)),
    ]


def _write_manifest(
    season: str,
    crawl_results: dict[str, CrawlResult],
    data_root: Path = _DATA_ROOT,
) -> Path:
    """Write (or overwrite) the crawl manifest for this season.

    Args:
        season: Season label used as subdirectory under ``data_root``.
        crawl_results: Mapping of crawler name to its ``CrawlResult``.
        data_root: Root directory for raw data.

    Returns:
        Path to the written manifest file.
    """
    manifest_dir = data_root / season
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "manifest.json"

    manifest = {
        "crawled_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": season,
        "crawlers": {
            name: {
                "files_written": result.files_written,
                "files_skipped": result.files_skipped,
                "errors": result.errors,
            }
            for name, result in crawl_results.items()
        },
    }

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Manifest written to %s.", manifest_path)
    return manifest_path


def run(
    dry_run: bool = False,
    crawler_filter: str | None = None,
    data_root: Path = _DATA_ROOT,
    profile: str = "web",
    source: str = "yaml",
    db_path: Path | None = None,
    team_ids: list[int] | None = None,
) -> int:
    """Execute the crawl orchestration.

    Args:
        dry_run: If True, print plan and return without calling the API.
        crawler_filter: If set, run only the named crawler.
        data_root: Override the raw data root (used in tests).
        profile: Header profile for the HTTP session ("web" or "mobile").
            Passed to ``GameChangerClient``.  Defaults to ``"web"``.
        source: Config source -- ``"yaml"`` (default) or ``"db"``.
        db_path: Override the database path (used in tests; only relevant when
            ``source="db"``).  Defaults to ``DATABASE_PATH`` env var or
            ``data/app.db``.
        team_ids: Optional list of ``teams.id`` integers.  When provided and
            ``source="db"``, only teams whose ``TeamEntry.internal_id`` is in
            this list are processed.  Has no effect when ``source="yaml"``.
            Defaults to ``None`` (all active member teams).

    Returns:
        Exit code: 0 if all crawlers completed, 1 if any raised an exception.
    """
    logger.info("Loading team config from %s", source)
    if source == "db":
        default_db = _PROJECT_ROOT / "data" / "app.db"
        if db_path is not None:
            resolved_db = db_path
        else:
            env_db = os.environ.get("DATABASE_PATH")
            if env_db is not None:
                env_path = Path(env_db)
                resolved_db = env_path if env_path.is_absolute() else _PROJECT_ROOT / env_path
            else:
                resolved_db = default_db
        config = load_config_from_db(resolved_db)
        if team_ids is not None:
            config.member_teams = [
                t for t in config.member_teams if t.internal_id in team_ids
            ]
    else:
        config = load_config()

    # Build crawler list lazily so module-level patches in tests take effect.
    all_crawlers = _build_crawlers()

    # Determine which crawlers to run.
    selected = [
        (name, factory)
        for name, factory in all_crawlers
        if crawler_filter is None or name == crawler_filter
    ]

    if dry_run:
        logger.info("Dry run -- no API calls will be made.")
        logger.info("Season: %s", config.season)
        logger.info("Teams: %s", [t.id for t in config.member_teams])
        logger.info("Crawlers that would run (in order):")
        for name, _ in selected:
            logger.info("  %s", name)
        return 0

    client = GameChangerClient(profile=profile)
    crawl_results: dict[str, CrawlResult] = {}
    had_exception = False

    for name, factory in selected:
        logger.info("--- Starting crawler: %s ---", name)
        try:
            crawler = factory(client, config)  # type: ignore[operator]
            result: CrawlResult = crawler.crawl_all()
            crawl_results[name] = result
            logger.info(
                "Crawler %s done: written=%d skipped=%d errors=%d",
                name,
                result.files_written,
                result.files_skipped,
                result.errors,
            )
        except Exception as exc:  # noqa: BLE001 -- AC-5: log and continue
            logger.error("Crawler %s raised an unhandled exception: %s", name, exc)
            crawl_results[name] = CrawlResult(errors=1)
            had_exception = True

    _write_manifest(config.season, crawl_results, data_root=data_root)

    return 1 if had_exception else 0
