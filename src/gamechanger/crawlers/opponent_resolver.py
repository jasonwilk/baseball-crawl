"""Opponent resolution crawler for the GameChanger data ingestion pipeline.

Chains authenticated API calls to resolve opponents from the opponent registry
to their canonical GameChanger team identities, populating the
``opponent_links`` table.

Resolution flow for each owned team:

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
from src.gamechanger.config import CrawlConfig

logger = logging.getLogger(__name__)

_OPPONENTS_ACCEPT = "application/vnd.gc.com.opponent_team:list+json; version=0.0.0"
_TEAM_ACCEPT = "application/vnd.gc.com.team+json; version=0.10.0"
_DELAY_SECONDS = 1.5

# SQL for the auto-resolved upsert with manual-link protection (TN-5).
# Manual links (resolution_method='manual') preserve resolved_team_id, public_id,
# resolution_method, and resolved_at unchanged.  Only opponent_name, is_hidden,
# and updated_at are always overwritten.
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
        is_hidden = excluded.is_hidden,
        updated_at = datetime('now')
"""


@dataclass
class ResolveResult:
    """Summary of a completed opponent resolution run.

    Attributes:
        resolved: Opponents successfully resolved to a canonical team ID.
        unlinked: Opponents inserted as unlinked (no progenitor_team_id).
        skipped_hidden: Opponents skipped because is_hidden is True.
        errors: Opponents where a skippable error was encountered.
    """

    resolved: int = field(default=0)
    unlinked: int = field(default=0)
    skipped_hidden: int = field(default=0)
    errors: int = field(default=0)


class OpponentResolver:
    """Resolves opponents from the GC registry to canonical team identities.

    Args:
        client: Authenticated ``GameChangerClient`` for API requests.
        config: ``CrawlConfig`` containing the owned team list.
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
        """Run the resolution loop for all owned teams.

        Returns:
            A ``ResolveResult`` with counts of resolved, unlinked, and error
            outcomes across all owned teams.

        Raises:
            CredentialExpiredError: On 401 -- aborts immediately.
        """
        result = ResolveResult()

        for team in self._config.owned_teams:
            logger.info(
                "Resolving opponents for owned team '%s' (%s)", team.name, team.id
            )
            try:
                team_result = self._resolve_team(team.id)
                result.resolved += team_result.resolved
                result.unlinked += team_result.unlinked
                result.skipped_hidden += team_result.skipped_hidden
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
            "resolved=%d unlinked=%d skipped_hidden=%d errors=%d",
            result.resolved,
            result.unlinked,
            result.skipped_hidden,
            result.errors,
        )
        return result

    # ------------------------------------------------------------------
    # Per-team resolution
    # ------------------------------------------------------------------

    def _resolve_team(self, our_team_id: str) -> ResolveResult:
        """Fetch and resolve all opponents for one owned team.

        Args:
            our_team_id: UUID of the owned team.

        Returns:
            ``ResolveResult`` for this team's opponents.

        Raises:
            CredentialExpiredError: On 401 -- propagated to caller.
        """
        result = ResolveResult()

        opponents: list[dict[str, Any]] = self._client.get_paginated(
            f"/teams/{our_team_id}/opponents",
            accept=_OPPONENTS_ACCEPT,
        )
        time.sleep(_DELAY_SECONDS)

        for opponent in opponents:
            self._process_opponent(opponent, our_team_id, result)

        self._db.commit()
        return result

    def _process_opponent(
        self,
        opponent: dict[str, Any],
        our_team_id: str,
        result: ResolveResult,
    ) -> None:
        """Process a single opponent record and update result counts in-place.

        Args:
            opponent: Raw opponent dict from the GC opponents API response.
            our_team_id: UUID of the owned team.
            result: Mutable ``ResolveResult`` to accumulate counts into.

        Raises:
            CredentialExpiredError: On 401 -- propagated to caller.
        """
        is_hidden: bool = opponent.get("is_hidden", False)
        root_team_id: str = opponent["root_team_id"]
        name: str = opponent.get("name", "")
        progenitor_team_id: str | None = opponent.get("progenitor_team_id")

        if is_hidden:
            result.skipped_hidden += 1
            logger.debug("Skipping hidden opponent '%s' (%s)", name, root_team_id)
            return

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

    def _process_with_progenitor(
        self,
        our_team_id: str,
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
        our_team_id: str,
        root_team_id: str,
        opponent_name: str,
        progenitor_team_id: str,
        is_hidden: bool,
    ) -> None:
        """Fetch team detail and upsert an auto-resolved row into opponent_links.

        Args:
            our_team_id: UUID of the owned team.
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

        self._ensure_opponent_team_row(progenitor_team_id, team_name)
        self._upsert_resolved(
            our_team_id=our_team_id,
            root_team_id=root_team_id,
            opponent_name=opponent_name,
            resolved_team_id=progenitor_team_id,
            public_id=public_id,
            is_hidden=is_hidden,
        )

        logger.debug(
            "Resolved opponent '%s' -> team %s (public_id=%s)",
            opponent_name,
            progenitor_team_id,
            public_id,
        )

    def _ensure_opponent_team_row(self, team_id: str, team_name: str) -> None:
        """Ensure a teams row exists for the resolved team.

        Creates a stub with the real team name.  If a stub already exists with
        name=team_id (UUID-as-name placeholder left by game_loader), updates it
        to the real name.  If a row with a real name already exists, leaves it
        unchanged.

        Args:
            team_id: Canonical GC team UUID.
            team_name: Human-readable name from the team detail endpoint.
        """
        self._db.execute(
            """
            INSERT INTO teams (team_id, name, is_owned, is_active)
            VALUES (?, ?, 0, 0)
            ON CONFLICT(team_id) DO UPDATE SET
                name = excluded.name
                WHERE teams.name = teams.team_id
            """,
            (team_id, team_name),
        )

    def _upsert_resolved(
        self,
        our_team_id: str,
        root_team_id: str,
        opponent_name: str,
        resolved_team_id: str,
        public_id: str,
        is_hidden: bool,
    ) -> None:
        """Upsert an auto-resolved opponent_links row with manual-link protection.

        If a row already exists with resolution_method='manual', the
        resolved_team_id, public_id, resolution_method, and resolved_at fields
        are preserved unchanged.  Only opponent_name, is_hidden, and updated_at
        are always overwritten.

        Args:
            our_team_id: UUID of the owned team.
            root_team_id: Local registry key for this opponent.
            opponent_name: Display name of the opponent.
            resolved_team_id: Canonical GC UUID for the resolved team.
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
        our_team_id: str,
        root_team_id: str,
        opponent_name: str,
        is_hidden: bool,
    ) -> None:
        """Insert an unlinked opponent row (no canonical team UUID available).

        On conflict, only opponent_name and is_hidden are updated -- existing
        resolution data (if any) is left unchanged.

        Args:
            our_team_id: UUID of the owned team.
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
                is_hidden = excluded.is_hidden,
                updated_at = datetime('now')
            """,
            (our_team_id, root_team_id, opponent_name, 1 if is_hidden else 0),
        )
        logger.debug(
            "Inserted unlinked opponent '%s' (%s)", opponent_name, root_team_id
        )
