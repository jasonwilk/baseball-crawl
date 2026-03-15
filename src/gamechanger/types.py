"""Shared type definitions for the baseball-crawl ingestion pipeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TeamRef:
    """Internal reference to a team in the database.

    Separates the internal INTEGER primary key from the external GC identifiers.
    Use ``id`` for all FK references to ``teams(id)``.  Use ``gc_uuid`` or
    ``public_id`` only when calling GameChanger API endpoints.

    Attributes:
        id: INTEGER primary key from ``teams.id``.
        gc_uuid: GC team UUID for authenticated API endpoints.  May be ``None``
            if the UUID has not yet been discovered.
        public_id: GC public_id slug for unauthenticated public API endpoints.
            May be ``None`` if the slug has not yet been resolved.
    """

    id: int
    gc_uuid: str | None = None
    public_id: str | None = None
