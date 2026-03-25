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
_FOLLOW_BRIDGE_DELAY_SECONDS = 2.0
_ME_USER_ACCEPT = "application/vnd.gc.com.user+json; version=0.3.0"
_BRIDGE_ACCEPT = "application/vnd.gc.com.team_public_profile_id+json; version=0.0.0"

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
        follow_bridge_failed: Distinct root_team_ids where the follow→bridge
            flow failed to produce a public_id (follow failure or bridge failure).
    """

    resolved: int = field(default=0)
    unlinked: int = field(default=0)
    stored_hidden: int = field(default=0)
    errors: int = field(default=0)
    follow_bridge_failed: int = field(default=0)


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
        public_id: str | None = team_data.get("public_id")
        if public_id is None:
            logger.warning(
                "Team detail for %r missing public_id -- continuing without it",
                progenitor_team_id,
            )
        team_name: str = team_data.get("name", progenitor_team_id)
        season_year: int | None = team_data.get("season_year")

        resolved_team_id, effective_public_id = self._ensure_opponent_team_row(
            progenitor_team_id, team_name, public_id=public_id, season_year=season_year
        )
        self._upsert_resolved(
            our_team_id=our_team_id,
            root_team_id=root_team_id,
            opponent_name=opponent_name,
            resolved_team_id=resolved_team_id,
            public_id=effective_public_id,
            is_hidden=is_hidden,
        )

        logger.debug(
            "Resolved opponent '%s' -> team %s (id=%d, public_id=%s)",
            opponent_name,
            progenitor_team_id,
            resolved_team_id,
            effective_public_id,
        )

    def _ensure_opponent_team_row(
        self,
        gc_uuid: str,
        team_name: str,
        public_id: str | None = None,
        season_year: int | None = None,
    ) -> tuple[int, str | None]:
        """Ensure a teams row exists for the resolved opponent team.

        Uses INSERT OR IGNORE with membership_type='tracked'.  If the row
        already exists (IGNORE fires), falls back to SELECT to retrieve the
        INTEGER PK.  Updates ``public_id`` and ``season_year`` only when the
        existing row has NULL values for those columns (only-write-when-NULL).

        UNIQUE collision handling for ``public_id``: if another row already
        has the same ``public_id``, a WARNING is logged and the write is
        skipped (manual row reconciliation is needed).

        Args:
            gc_uuid: Canonical GC team UUID (progenitor_team_id).
            team_name: Human-readable name from the team detail endpoint.
            public_id: Public slug from the team detail response, or None.
            season_year: Four-digit season year from the team detail response,
                or None if absent.

        Returns:
            A tuple of (teams.id, effective_public_id) where effective_public_id
            is the public_id value to use for opponent_links -- None when the
            write was skipped due to a UNIQUE collision so that downstream callers
            do not propagate a colliding public_id to other tables.
        """
        # public_id is intentionally excluded from INSERT to avoid triggering the
        # UNIQUE constraint on teams.public_id when another row already holds the
        # same slug.  It is written after INSERT via the shared _write_public_id
        # helper, which performs the collision check regardless of code path.
        cursor = self._db.execute(
            "INSERT OR IGNORE INTO teams "
            "(name, membership_type, gc_uuid, is_active, season_year) "
            "VALUES (?, 'tracked', ?, 0, ?)",
            (team_name, gc_uuid, season_year),
        )
        if cursor.rowcount:
            new_id: int = cursor.lastrowid
            written = self._write_public_id(new_id, gc_uuid, public_id)
            return new_id, (public_id if written else None)

        row = self._db.execute(
            "SELECT id, name, public_id, season_year FROM teams WHERE gc_uuid = ?",
            (gc_uuid,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Failed to find or create teams row for gc_uuid={gc_uuid!r}")
        existing_id, existing_name, existing_public_id, existing_season_year = row

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

        # Write public_id only when existing row has NULL (only-write-when-NULL).
        if existing_public_id is None:
            written = self._write_public_id(existing_id, gc_uuid, public_id)
            effective_public_id: str | None = public_id if written else None
        else:
            effective_public_id = existing_public_id

        # Write season_year only when existing row has NULL (only-write-when-NULL).
        if season_year is not None and existing_season_year is None:
            self._db.execute(
                "UPDATE teams SET season_year = ? WHERE id = ?", (season_year, existing_id)
            )

        return existing_id, effective_public_id

    def _write_public_id(self, team_id: int, gc_uuid: str, public_id: str | None) -> bool:
        """Write public_id to a teams row, checking for UNIQUE collisions first.

        Skips the write if ``public_id`` is None.  Logs a WARNING and skips if
        another row already holds the same ``public_id``.

        Args:
            team_id: INTEGER PK of the target teams row.
            gc_uuid: GC UUID of the target team (for log context).
            public_id: Slug to write, or None to skip entirely.

        Returns:
            True if the write was performed, False if skipped (None input or collision).
        """
        if public_id is None:
            return False
        collision = self._db.execute(
            "SELECT id FROM teams WHERE public_id = ? AND id != ?",
            (public_id, team_id),
        ).fetchone()
        if collision:
            logger.warning(
                "UNIQUE collision: public_id=%r already assigned to team id=%d; "
                "skipping public_id write for team id=%d (gc_uuid=%r)",
                public_id, collision[0], team_id, gc_uuid,
            )
            return False
        else:
            self._db.execute(
                "UPDATE teams SET public_id = ? WHERE id = ?", (public_id, team_id)
            )
            return True

    def _upsert_resolved(
        self,
        our_team_id: int,
        root_team_id: str,
        opponent_name: str,
        resolved_team_id: int,
        public_id: str | None,
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

    # ------------------------------------------------------------------
    # Experimental: follow→bridge→unfollow resolution
    # ------------------------------------------------------------------

    def resolve_unlinked(self) -> ResolveResult:
        """Attempt auto-resolution of null-progenitor opponents via follow→bridge→unfollow.

        For each distinct ``root_team_id`` in ``opponent_links`` with no
        ``public_id`` and no ``resolution_method``, this method:

        1. Follows the team via ``POST /teams/{root_team_id}/follow``.
        2. Fetches ``public_id`` via the bridge endpoint.
        3. Fan-out updates all matching ``opponent_links`` rows.
        4. Unfollows via two DELETE calls (best-effort cleanup).

        This is an experimental flow -- whether ``root_team_id`` works with the
        follow/bridge endpoints is unverified.  All failures are handled
        gracefully and logged.

        Returns:
            A ``ResolveResult`` with ``resolved`` (successful public_id stored)
            and ``follow_bridge_failed`` (follow or bridge failure) counts.
        """
        result = ResolveResult()

        # Fetch user UUID once for the unfollow DELETE step.
        user_data = self._client.get("/me/user", accept=_ME_USER_ACCEPT)
        user_id: str = user_data["id"]

        rows = self._db.execute(
            "SELECT DISTINCT root_team_id FROM opponent_links "
            "WHERE public_id IS NULL AND resolution_method IS NULL AND is_hidden = 0"
        ).fetchall()
        root_team_ids = [row[0] for row in rows]

        for root_team_id in root_team_ids:
            try:
                self._follow_bridge_unfollow(root_team_id, user_id, result)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Unexpected error in follow-bridge cycle for root_team_id=%s: %s",
                    root_team_id,
                    exc,
                )
                result.errors += 1
            time.sleep(_FOLLOW_BRIDGE_DELAY_SECONDS)

        logger.info(
            "resolve_unlinked complete -- resolved=%d follow_bridge_failed=%d errors=%d",
            result.resolved,
            result.follow_bridge_failed,
            result.errors,
        )
        return result

    def _follow_bridge_unfollow(
        self,
        root_team_id: str,
        user_id: str,
        result: ResolveResult,
    ) -> None:
        """Execute the follow→bridge→unfollow cycle for one root_team_id.

        Args:
            root_team_id: The team UUID to follow, query, and unfollow.
            user_id: The authenticated user's UUID (for the unfollow DELETE).
            result: Mutable ``ResolveResult`` to accumulate counts into.
        """
        # Step 1: Follow the team.  Any exception means skip the cycle entirely.
        try:
            self._client.post(f"/teams/{root_team_id}/follow")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Follow failed for root_team_id=%s: %s -- skipping cycle",
                root_team_id,
                exc,
            )
            result.follow_bridge_failed += 1
            return

        # Step 2: Fetch public_id via bridge endpoint.
        public_id: str | None = None
        try:
            bridge_data = self._client.get(
                f"/teams/{root_team_id}/public-team-profile-id",
                accept=_BRIDGE_ACCEPT,
            )
            public_id = bridge_data.get("id")
            if public_id is None:
                logger.warning(
                    "Bridge returned 200 but no 'id' field for root_team_id=%s "
                    "-- proceeding to unfollow",
                    root_team_id,
                )
                result.follow_bridge_failed += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Bridge failed for root_team_id=%s: %s -- proceeding to unfollow",
                root_team_id,
                exc,
            )
            result.follow_bridge_failed += 1

        # Step 3: Store public_id if bridge succeeded.
        if public_id is not None:
            self._db.execute(
                """
                UPDATE opponent_links
                SET public_id = ?,
                    resolution_method = 'follow-bridge',
                    resolved_at = datetime('now')
                WHERE root_team_id = ? AND resolution_method IS NULL
                """,
                (public_id, root_team_id),
            )
            self._db.commit()
            result.resolved += 1
            logger.debug(
                "Stored public_id=%s for root_team_id=%s via follow-bridge",
                public_id,
                root_team_id,
            )

        # Step 4: Unfollow (best-effort cleanup -- failures logged but not counted).
        try:
            self._client.delete(f"/teams/{root_team_id}/users/{user_id}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Unfollow step 1 failed for root_team_id=%s: %s", root_team_id, exc
            )

        try:
            self._client.delete(f"/me/relationship-requests/{root_team_id}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Unfollow step 2 failed for root_team_id=%s: %s", root_team_id, exc
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
