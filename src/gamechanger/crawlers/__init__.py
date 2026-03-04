"""GameChanger crawlers package.

Provides the shared ``CrawlResult`` dataclass used as the return type for all
crawler ``crawl_all()`` methods.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CrawlResult:
    """Summary of a completed crawl run.

    Attributes:
        files_written: Number of files fetched from the API and written to disk.
        files_skipped: Number of files that were fresh and skipped.
        errors: Number of teams/targets where an API error was caught.
    """

    files_written: int = field(default=0)
    files_skipped: int = field(default=0)
    errors: int = field(default=0)
