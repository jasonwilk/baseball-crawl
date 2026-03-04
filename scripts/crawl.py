#!/usr/bin/env python3
"""Crawl orchestrator -- refresh all raw data from the GameChanger API.

Runs all available crawlers in dependency order and writes a manifest
summarising the run to ``data/raw/{season}/manifest.json``.

Usage::

    python scripts/crawl.py                     # run all crawlers
    python scripts/crawl.py --dry-run           # preview without API calls
    python scripts/crawl.py --crawler roster    # run one crawler only

Available crawler names: roster, schedule, opponent, player-stats, game-stats
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root on sys.path so src.* imports work when run directly.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.gamechanger.client import GameChangerClient  # noqa: E402
from src.gamechanger.config import load_config  # noqa: E402
from src.gamechanger.crawlers import CrawlResult  # noqa: E402
from src.gamechanger.crawlers.roster import RosterCrawler  # noqa: E402
from src.gamechanger.crawlers.schedule import ScheduleCrawler  # noqa: E402
from src.gamechanger.crawlers.opponent import OpponentCrawler  # noqa: E402
from src.gamechanger.crawlers.player_stats import PlayerStatsCrawler  # noqa: E402
from src.gamechanger.crawlers.game_stats import GameStatsCrawler  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s -- %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

_DATA_ROOT = _PROJECT_ROOT / "data" / "raw"

# Ordered crawler names.  Order matters: schedule must run before game-stats.
# The actual class references are resolved lazily inside run() so that tests
# can patch module-level names (e.g. scripts.crawl.RosterCrawler) and have
# the patches take effect.
_CRAWLER_NAMES: list[str] = [
    "roster",
    "schedule",
    "opponent",
    "player-stats",
    "game-stats",
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


def _build_arg_parser() -> argparse.ArgumentParser:
    """Return the argument parser for crawl.py."""
    parser = argparse.ArgumentParser(
        description="Refresh all raw GameChanger data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would run without making API calls or writing files.",
    )
    parser.add_argument(
        "--crawler",
        metavar="NAME",
        choices=_CRAWLER_NAMES,
        help=f"Run only one crawler. Choices: {', '.join(_CRAWLER_NAMES)}",
    )
    return parser


def run(
    dry_run: bool = False,
    crawler_filter: str | None = None,
    data_root: Path = _DATA_ROOT,
) -> int:
    """Execute the crawl orchestration.

    Args:
        dry_run: If True, print plan and return without calling the API.
        crawler_filter: If set, run only the named crawler.
        data_root: Override the raw data root (used in tests).

    Returns:
        Exit code: 0 if all crawlers completed, 1 if any raised an exception.
    """
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
        print("Dry run -- no API calls will be made.")
        print(f"Season: {config.season}")
        print(f"Teams: {[t.id for t in config.owned_teams]}")
        print("Crawlers that would run (in order):")
        for name, _ in selected:
            print(f"  {name}")
        return 0

    client = GameChangerClient()
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


def main() -> None:
    """Entry point for ``python scripts/crawl.py``."""
    parser = _build_arg_parser()
    args = parser.parse_args()
    sys.exit(run(dry_run=args.dry_run, crawler_filter=args.crawler))


if __name__ == "__main__":
    main()
