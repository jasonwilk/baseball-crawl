"""Opponent resolution crawler for the GameChanger data ingestion pipeline.

Chains authenticated API calls to resolve opponents from the opponent registry
to their canonical GameChanger team identities, populating the
``opponent_links`` table.

Resolution flow for each member team:

1. Fetch ``GET /teams/{team_id}/opponents`` (paginated).
2. For each opponent with a non-null ``progenitor_team_id``:
   a. Fetch ``GET /teams/{progenitor_team_id}`` to extract ``public_id``.
   b. Ensure the team row exists in ``teams`` (name-aware stub upsert).
   c. Upsert into ``opponent_links`` with ``resolution_method='auto'``.
3. For each opponent with null ``progenitor_team_id``:
   Insert as an unlinked row (``resolution_method=NULL``).

~86% of opponents auto-resolve via ``progenitor_team_id``; ~14% are unlinked.

Manual links (``resolution_method='manual'``) are never overwritten by the
auto-resolution pass -- the upsert COALESCE logic preserves them.

Usage::

    import sqlite3
    from src.gamechanger.client import GameChangerClient
    from src.gamechanger.config import load_config
    from src.gamechanger.crawlers.opponent_resolver import OpponentResolver

    client = GameChangerClient()
    config = load_config()
    conn = sqlite3.connect("./data/app.db")
    conn.execute("PRAGMA foreign_keys=ON;")
    resolver = OpponentResolver(client, config, conn)
    result = resolver.resolve()
    print(result)
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any

from src.gamechanger.client import (
    CredentialExpiredError,
    ForbiddenError,
    GameChangerAPIError,
    GameChangerClient,
)
from src.gamechanger.config import CrawlConfig, TeamEntry

logger = logging.getLogger(__name__)

_OPPONENTS_ACCEPT = "application/vnd.gc.com.opponent_team:list+json; version=0.0.0"
_TEAM_ACCEPT = "application/vnd.gc.com.team+json; version=0.10.0"
_DELAY_SECONDS = 1.5

# SQL for the auto-resolved upsert with manual-link protection (TN-5).
# Manual links (resolution_method='manual') preserve resolved_team_id, public_id,
# resolution_method, and resolved_at unchanged.  Only opponent_name and is_hidden
# are always overwritten.
_UPSERT_RESOLVED_SQL = """
    INSERT INTO opponent_links
        (our_team_id, root_team_id, opponent_name, resolved_team_id,
         public_id, resolution_method, resolved_at, is_hidden)
    VALUES (?, ?, ?, ?, ?, 'auto', datetime('now'), ?)
    ON CONFLICT(our_team_id, root_team_id) DO UPDATE SET
        opponent_name = excluded.opponent_name,
        resolved_team_id = CASE
            WHEN opponent_links.resolution_method = 'manual'
                THEN opponent_links.resolved_team_id
            ELSE excluded.resolved_team_id
        END,
        public_id = CASE
            WHEN opponent_links.resolution_method = 'manual'
                THEN opponent_links.public_id
            ELSE excluded.public_id
        END,
        resolution_method = COALESCE(
            opponent_links.resolution_method, excluded.resolution_method
        ),
        resolved_at = CASE
            WHEN opponent_links.resolution_method = 'manual'
                THEN opponent_links.resolved_at
            ELSE excluded.resolved_at
        END,
        is_hidden = excluded.is_hidden
"""


@dataclass
class ResolveResult:
    """Summary of a completed opponent resolution run.

    Attributes:
        resolved: Opponents successfully resolved to a canonical team ID.
        unlinked: Opponents inserted as unlinked (no progenitor_team_id).
        stored_hidden: Opponents stored with is_hidden=1.
        errors: Opponents where a skippable error was encountered.
    """

    resolved: int = field(default=0)
    unlinked: int = field(default=0)
    stored_hidden: int = field(default=0)
    errors: int = field(default=0)


class OpponentResolver:
    """Resolves opponents from the GC registry to canonical team identities.

    Args:
        client: Authenticated ``GameChangerClient`` for API requests.
        config: ``CrawlConfig`` containing the member team list.
        db: Open SQLite connection with ``PRAGMA foreign_keys=ON;`` applied.
    """

    def __init__(
        self,
        client: GameChangerClient,
        config: CrawlConfig,
        db: sqlite3.Connection,
    ) -> None:
        self._client = client
        self._config = config
        self._db = db

    def resolve(self) -> ResolveResult:
        """Run the resolution loop for all member teams.

        Returns:
            A ``ResolveResult`` with counts of resolved, unlinked, and error
            outcomes across all member teams.

        Raises:
            CredentialExpiredError: On 401 -- aborts immediately.
        """
        result = ResolveResult()

        for team in self._config.member_teams:
            logger.info(
                "Resolving opponents for member team '%s' (%s)", team.name, team.id
            )
            try:
                team_result = self._resolve_team(team)
                result.resolved += team_result.resolved
                result.unlinked += team_result.unlinked
                result.stored_hidden += team_result.stored_hidden
                result.errors += team_result.errors
            except CredentialExpiredError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Unexpected error resolving team %s: %s", team.id, exc
                )
                result.errors += 1

        logger.info(
            "Opponent resolution complete -- "
            "resolved=%d unlinked=%d stored_hidden=%d errors=%d",
            result.resolved,
            result.unlinked,
            result.stored_hidden,
            result.errors,
        )
        return result

    # ------------------------------------------------------------------
    # Per-team resolution
    # ------------------------------------------------------------------

    def _resolve_team(self, team: TeamEntry) -> ResolveResult:
        """Fetch and resolve all opponents for one member team.

        Args:
            team: ``TeamEntry`` for the member team.  ``team.id`` is the GC
                UUID used for API calls; ``team.internal_id`` is the INTEGER PK
                used for DB foreign keys.

        Returns:
            ``ResolveResult`` for this team's opponents.

        Raises:
            CredentialExpiredError: On 401 -- propagated to caller.
        """
        result = ResolveResult()

        # Use the GC UUID (team.id) for the API call.
        opponents: list[dict[str, Any]] = self._client.get_paginated(
            f"/teams/{team.id}/opponents",
            accept=_OPPONENTS_ACCEPT,
        )
        time.sleep(_DELAY_SECONDS)

        # our_team_id for DB operations is the INTEGER PK.
        if team.internal_id is None:
            raise ValueError(
                f"Team '{team.id}' has no internal_id — ensure load_config() was called with db_path"
            )
        our_team_id: int = team.internal_id

        for opponent in opponents:
            self._process_opponent(opponent, our_team_id, result)

        self._db.commit()
        return result

    def _process_opponent(
        self,
        opponent: dict[str, Any],
        our_team_id: int,
        result: ResolveResult,
    ) -> None:
        """Process a single opponent record and update result counts in-place.

        Args:
            opponent: Raw opponent dict from the GC opponents API response.
            our_team_id: INTEGER PK of the member team in the ``teams`` table.
            result: Mutable ``ResolveResult`` to accumulate counts into.

        Raises:
            CredentialExpiredError: On 401 -- propagated to caller.
        """
        is_hidden: bool = opponent.get("is_hidden", False)
        root_team_id: str = opponent["root_team_id"]
        name: str = opponent.get("name", "")
        progenitor_team_id: str | None = opponent.get("progenitor_team_id")

        if progenitor_team_id:
            self._process_with_progenitor(
                our_team_id, root_team_id, name, progenitor_team_id, is_hidden, result
            )
        else:
            self._upsert_unlinked(
                our_team_id=our_team_id,
                root_team_id=root_team_id,
                opponent_name=name,
                is_hidden=is_hidden,
            )
            result.unlinked += 1

        if is_hidden:
            result.stored_hidden += 1
            logger.debug("Stored hidden opponent '%s' (%s)", name, root_team_id)

    def _process_with_progenitor(
        self,
        our_team_id: int,
        root_team_id: str,
        name: str,
        progenitor_team_id: str,
        is_hidden: bool,
        result: ResolveResult,
    ) -> None:
        """Attempt to resolve one opponent that has a progenitor_team_id.

        Calls ``_resolve_opponent`` and handles skippable errors (403, 5xx, 404).
        Re-raises ``CredentialExpiredError`` (401) to abort the run.
        Updates ``result`` counts in-place.
        """
        try:
            self._resolve_opponent(
                our_team_id=our_team_id,
                root_team_id=root_team_id,
                opponent_name=name,
                progenitor_team_id=progenitor_team_id,
                is_hidden=is_hidden,
            )
            result.resolved += 1
        except ForbiddenError as exc:
            logger.warning(
                "Access denied resolving opponent '%s' (%s): %s",
                name, progenitor_team_id, exc,
            )
            result.errors += 1
        except CredentialExpiredError:
            raise
        except GameChangerAPIError as exc:
            logger.warning(
                "API error resolving opponent '%s' (%s): %s",
                name, progenitor_team_id, exc,
            )
            result.errors += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Unexpected error resolving opponent '%s' (%s): %s",
                name, progenitor_team_id, exc,
            )
            result.errors += 1
        finally:
            time.sleep(_DELAY_SECONDS)

    # ------------------------------------------------------------------
    # Resolution helpers
    # ------------------------------------------------------------------

    def _resolve_opponent(
        self,
        our_team_id: int,
        root_team_id: str,
        opponent_name: str,
        progenitor_team_id: str,
        is_hidden: bool,
    ) -> None:
        """Fetch team detail and upsert an auto-resolved row into opponent_links.

        Args:
            our_team_id: INTEGER PK of the member team.
            root_team_id: Local registry key for this opponent.
            opponent_name: Display name of the opponent.
            progenitor_team_id: Canonical GC UUID for the opponent team.
            is_hidden: Whether this opponent is hidden in the GC UI.

        Raises:
            ForbiddenError: On 403 (caller logs and skips).
            CredentialExpiredError: On 401 (caller aborts).
            GameChangerAPIError: On 4xx/5xx other than 403/401 (caller logs and skips).
        """
        team_data: dict[str, Any] = self._client.get(
            f"/teams/{progenitor_team_id}",
            accept=_TEAM_ACCEPT,
        )
        public_id: str = team_data["public_id"]
        team_name: str = team_data.get("name", progenitor_team_id)

        resolved_team_id = self._ensure_opponent_team_row(progenitor_team_id, team_name)
        self._upsert_resolved(
            our_team_id=our_team_id,
            root_team_id=root_team_id,
            opponent_name=opponent_name,
            resolved_team_id=resolved_team_id,
            public_id=public_id,
            is_hidden=is_hidden,
        )

        logger.debug(
            "Resolved opponent '%s' -> team %s (id=%d, public_id=%s)",
            opponent_name,
            progenitor_team_id,
            resolved_team_id,
            public_id,
        )

    def _ensure_opponent_team_row(self, gc_uuid: str, team_name: str) -> int:
        """Ensure a teams row exists for the resolved opponent team.

        Uses INSERT OR IGNORE with membership_type='tracked'.  If the row
        already exists (IGNORE fires), falls back to SELECT to retrieve the
        INTEGER PK.

        Args:
            gc_uuid: Canonical GC team UUID (progenitor_team_id).
            team_name: Human-readable name from the team detail endpoint.

        Returns:
            The INTEGER PK (``teams.id``) for the opponent team row.
        """
        cursor = self._db.execute(
            "INSERT OR IGNORE INTO teams (name, membership_type, gc_uuid, is_active) "
            "VALUES (?, 'tracked', ?, 0)",
            (team_name, gc_uuid),
        )
        if cursor.rowcount:
            return cursor.lastrowid

        row = self._db.execute(
            "SELECT id, name FROM teams WHERE gc_uuid = ?", (gc_uuid,)
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Failed to find or create teams row for gc_uuid={gc_uuid!r}")
        existing_id, existing_name = row
        # Update UUID-as-name stubs (created by game_loader before team resolution)
        # with the real team name. Preserve any existing non-UUID name.
        if existing_name == gc_uuid:
            self._db.execute(
                "UPDATE teams SET name = ? WHERE id = ?", (team_name, existing_id)
            )
            logger.debug(
                "Updated UUID-stub name for team %d: %r -> %r",
                existing_id, existing_name, team_name,
            )
        return existing_id

    def _upsert_resolved(
        self,
        our_team_id: int,
        root_team_id: str,
        opponent_name: str,
        resolved_team_id: int,
        public_id: str,
        is_hidden: bool,
    ) -> None:
        """Upsert an auto-resolved opponent_links row with manual-link protection.

        If a row already exists with resolution_method='manual', the
        resolved_team_id, public_id, resolution_method, and resolved_at fields
        are preserved unchanged.  Only opponent_name and is_hidden are always
        overwritten.

        Args:
            our_team_id: INTEGER PK of the member team.
            root_team_id: Local registry key for this opponent.
            opponent_name: Display name of the opponent.
            resolved_team_id: INTEGER PK of the resolved team in ``teams``.
            public_id: Public slug for the resolved team.
            is_hidden: Whether this opponent is hidden in the GC UI.
        """
        self._db.execute(
            _UPSERT_RESOLVED_SQL,
            (
                our_team_id,
                root_team_id,
                opponent_name,
                resolved_team_id,
                public_id,
                1 if is_hidden else 0,
            ),
        )

    def _upsert_unlinked(
        self,
        our_team_id: int,
        root_team_id: str,
        opponent_name: str,
        is_hidden: bool,
    ) -> None:
        """Insert an unlinked opponent row (no canonical team UUID available).

        On conflict, only opponent_name and is_hidden are updated -- existing
        resolution data (if any) is left unchanged.

        Args:
            our_team_id: INTEGER PK of the member team.
            root_team_id: Local registry key for this opponent.
            opponent_name: Display name of the opponent.
            is_hidden: Whether this opponent is hidden in the GC UI.
        """
        self._db.execute(
            """
            INSERT INTO opponent_links
                (our_team_id, root_team_id, opponent_name, is_hidden)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(our_team_id, root_team_id) DO UPDATE SET
                opponent_name = excluded.opponent_name,
                is_hidden = excluded.is_hidden
            """,
            (our_team_id, root_team_id, opponent_name, 1 if is_hidden else 0),
        )
        logger.debug(
            "Inserted unlinked opponent '%s' (%s)", opponent_name, root_team_id
        )
