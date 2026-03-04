"""GameChanger loaders package.

Provides the shared ``LoadResult`` dataclass used as the return type for all
loader ``load_file()`` methods.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LoadResult:
    """Summary of a completed load run.

    Attributes:
        loaded: Number of records successfully upserted into the database.
        skipped: Number of records skipped due to missing required fields.
        errors: Number of records that caused unexpected errors.
    """

    loaded: int = field(default=0)
    skipped: int = field(default=0)
    errors: int = field(default=0)
