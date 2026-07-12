"""GameChanger crawlers package.

Provides the shared ``CrawlResult`` dataclass, the summary return type of a
crawler run (``ScoutingCrawler.scout_team``).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CrawlResult:
    """Summary of a completed crawl run.

    Attributes:
        files_written: Number of API responses fetched.  The name predates the
            in-memory crawl-to-load pipeline (E-220); nothing is written to disk.
        files_skipped: Number of targets that were fresh and skipped.
        errors: Number of teams/targets where an API error was caught.
    """

    files_written: int = field(default=0)
    files_skipped: int = field(default=0)
    errors: int = field(default=0)
