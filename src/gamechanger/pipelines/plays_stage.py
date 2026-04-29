"""Shared plays-stage orchestration helper.

Single point of pipeline orchestration for the plays crawl + load + reconcile
sequence.  Used by:

- ``_scout_live`` (CLI scout, ``src/cli/data.py``)
- ``run_scouting_sync`` (web scout, ``src/pipeline/trigger.py``)
- ``generate_report`` (standalone reports, ``src/reports/generator.py``)

The helper encodes the scouting-pipeline-parity invariant: all three caller
paths invoke the same orchestration with equivalent inputs and produce
equivalent data artifacts (``plays``, ``play_events``,
``reconciliation_discrepancies``).

Public API::

    from src.gamechanger.pipelines import run_plays_stage, PlaysStageResult

    result = run_plays_stage(
        client,
        conn,
        perspective_team_id=team_id,
        public_id=public_id,
        game_ids=sorted(crawl_result.boxscores.keys()),
    )
"""

from __future__ import annotations

import json
import logging
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from src.gamechanger.client import CredentialExpiredError, GameChangerClient
from src.gamechanger.loaders.plays_loader import PlaysLoader
from src.gamechanger.types import TeamRef
from src.reconciliation.engine import reconcile_game

logger = logging.getLogger(__name__)

_PLAYS_ACCEPT = "application/vnd.gc.com.event_plays+json; version=0.0.0"


@dataclass
class PlaysStageResult:
    """Outcome of one ``run_plays_stage`` invocation.

    Field names follow ``LoadResult``'s bare-name convention (no ``games_``
    prefix); ``PlaysStageResult`` provides the "games" namespace via the
    class name.  ``errored`` is spelled with the participle here (rather than
    ``LoadResult``'s ``errors``) because it reads more naturally as a count
    in this dataclass's call sites -- the convention is still bare-name.
    Do NOT rename to a ``games_`` prefix in future refactors.

    Attributes:
        attempted: Number of game_ids the helper iterated over.
        loaded: Number of games whose plays were successfully loaded by this run
            (post-load DB probe).  Pre-fetch-skipped games are NOT counted here --
            those are already-loaded games and aggregate into ``skipped``.
        skipped: Games skipped on this run -- the union of pre-fetch DB skips
            (already loaded by a prior run) and loader-reported skips
            (idempotency-hit or FK-guard-skip).
        errored: Per-game failures across HTTP fetch and load (HTTP-fetch errors
            and loader-reported errors aggregate into the same counter).
        reconcile_errors: Per-game reconcile failures (each game's
            ``reconcile_game`` call wrapped in ``except Exception``).
        auth_expired: True iff a ``CredentialExpiredError`` interrupted the
            HTTP-fetch loop.  Plays loaded before the interrupt are persisted;
            unfetched game_ids appear in ``deferred_game_ids``.
        deferred_game_ids: Game IDs in the remaining suffix at auth-expiry that
            were NOT already loaded -- they need a re-fetch after
            ``bb creds setup web``.  Already-loaded games in the suffix are
            folded into ``skipped``, not deferred.
    """

    attempted: int
    loaded: int
    skipped: int
    errored: int
    reconcile_errors: int
    auth_expired: bool
    deferred_game_ids: list[str] = field(default_factory=list)


def run_plays_stage(
    client: GameChangerClient,
    conn: sqlite3.Connection,
    *,
    perspective_team_id: int,
    public_id: str,
    game_ids: list[str],
) -> PlaysStageResult:
    """Crawl, load, and reconcile plays for a list of games from one perspective.

    For each ``game_id`` the helper:

    1. Probes ``plays`` for an existing row at this perspective; on hit, skips
       the HTTP fetch (avoids redundant traffic on rerun).
    2. Otherwise issues ``GET /game-stream-processing/{game_id}/plays`` and
       writes the response to a tempdir as ``{game_id}.json``.
    3. After all fetches, runs ``PlaysLoader.load_all(tmp_dir)`` once to insert
       the per-game plays + events.
    4. For every game whose ``plays`` row is present after load, calls
       ``reconcile_game(conn, game_id, dry_run=False, perspective_team_id=...)``.

    The helper is non-fatal: ``CredentialExpiredError`` mid-fetch sets
    ``auth_expired=True`` and records remaining games in
    ``deferred_game_ids``; per-game errors increment counters and continue.

    Args:
        client: Authenticated ``GameChangerClient``.
        conn: Open ``sqlite3.Connection`` (caller-owned).  See caller
            invariants below.
        perspective_team_id: The scouted team's ``teams.id``.  Flows into both
            ``PlaysLoader(owned_team_ref=...)`` and ``reconcile_game(perspective_team_id=...)``;
            the shared name eliminates "which team_id?" ambiguity at call sites.
            Per ``.claude/rules/perspective-provenance.md``.
        public_id: The scouted team's ``public_id`` slug.  Log-only; the helper
            does not look the team up by slug.
        game_ids: Game IDs to process.  Empty list returns immediately.

    Returns:
        ``PlaysStageResult`` summarizing the outcome.

    Caller invariants (the helper assumes these and does NOT enforce them):
        1. ``PRAGMA foreign_keys=ON`` is set on ``conn``.  The helper does NOT
           silently set it -- a defensive helper-side pragma would mask caller
           bugs by silently turning FK enforcement on for connections that
           should have had it from the start.
        2. The helper does NOT close ``conn`` -- caller owns the lifecycle.
        3. ``game_perspectives`` rows for every ``game_id`` are already
           populated (by the upstream boxscore load via
           ``src/gamechanger/loaders/game_loader.py:640-647``).  Callers that
           bypass boxscore load -- if any exist outside the standard scout
           pipeline -- will produce ``plays`` rows tagged with a perspective
           that is NOT yet recorded in ``game_perspectives``, breaking
           perspective-provenance MUST #5 for that path.
        4. Pass a clean connection.  The first per-game ``PlaysLoader.commit()``
           will commit any uncommitted writes from earlier scout steps (e.g.,
           dedup).  In current code paths this is fine (dedup commits before
           plays starts), but future callers that pass a dirty connection
           would have those writes silently committed.  The helper does NOT
           own connection state and cannot guarantee atomicity across stages.
    """
    if not game_ids:
        logger.info(
            "run_plays_stage: empty game_ids for public_id=%s; nothing to do.",
            public_id,
        )
        return PlaysStageResult(
            attempted=0,
            loaded=0,
            skipped=0,
            errored=0,
            reconcile_errors=0,
            auth_expired=False,
            deferred_game_ids=[],
        )

    attempted = len(game_ids)
    errored = 0
    auth_expired = False
    deferred_game_ids: list[str] = []
    plays_data: dict[str, dict] = {}
    pre_skipped: set[str] = set()

    for index, game_id in enumerate(game_ids):
        # Pre-fetch DB skip avoids redundant HTTP traffic on rerun.
        # PlaysLoader._load_game() also gates on this same check; this is the
        # outer optimization so we don't pay the HTTP cost twice.
        existing = conn.execute(
            "SELECT 1 FROM plays "
            "WHERE game_id = ? AND perspective_team_id = ? LIMIT 1",
            (game_id, perspective_team_id),
        ).fetchone()
        if existing is not None:
            logger.debug(
                "Plays already loaded for game %s perspective %d; "
                "skipping HTTP fetch.",
                game_id,
                perspective_team_id,
            )
            pre_skipped.add(game_id)
            continue

        try:
            raw = client.get(
                f"/game-stream-processing/{game_id}/plays",
                accept=_PLAYS_ACCEPT,
            )
        except CredentialExpiredError:
            logger.warning(
                "PLAYS STAGE FAILED: auth expired during plays fetch for "
                "public_id=%s game_id=%s; deferring %d remaining games "
                "(some may already be loaded).",
                public_id,
                game_id,
                len(game_ids) - index,
            )
            auth_expired = True
            # Partition the remaining suffix: already-loaded games go to
            # pre_skipped (they don't need re-fetching post-auth-recovery),
            # only truly unfetched games go to deferred_game_ids.  Without
            # this partition, deferred_game_ids would overstate the work
            # remaining (and skipped would correspondingly understate
            # already-loaded games) on a rerun where auth fails mid-suffix
            # past games that are already loaded.
            remaining = game_ids[index:]
            for remaining_id in remaining:
                existing = conn.execute(
                    "SELECT 1 FROM plays "
                    "WHERE game_id = ? AND perspective_team_id = ? LIMIT 1",
                    (remaining_id, perspective_team_id),
                ).fetchone()
                if existing is not None:
                    pre_skipped.add(remaining_id)
                else:
                    deferred_game_ids.append(remaining_id)
            break
        except Exception:  # noqa: BLE001 -- per-game error isolation
            logger.warning(
                "PLAYS STAGE FAILED: failed to fetch plays for game %s "
                "(public_id=%s); continuing with remaining games.",
                game_id,
                public_id,
                exc_info=True,
            )
            errored += 1
            continue

        plays_data[game_id] = raw if isinstance(raw, dict) else {}

    # Load step: write fetched JSON to a tempdir and run PlaysLoader.load_all().
    loader_skipped = 0
    if plays_data:
        team_ref = TeamRef(
            id=perspective_team_id,
            gc_uuid=None,
            public_id=public_id,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            plays_dir = Path(tmp_dir) / "plays"
            plays_dir.mkdir()
            for gid, data in plays_data.items():
                (plays_dir / f"{gid}.json").write_text(
                    json.dumps(data), encoding="utf-8"
                )

            loader = PlaysLoader(conn, owned_team_ref=team_ref)
            load_result = loader.load_all(Path(tmp_dir))

        loader_skipped = load_result.skipped
        # Loader-reported errors aggregate into the same counter as
        # HTTP-fetch errors (already incremented above).
        errored += load_result.errors

        logger.info(
            "Plays load for public_id=%s perspective_team_id=%d: "
            "loaded=%d skipped=%d errors=%d",
            public_id,
            perspective_team_id,
            load_result.loaded,
            load_result.skipped,
            load_result.errors,
        )

    # Loaded-games selection (post-load DB probe).  ``loaded`` is a games
    # count, NOT a record count -- the operator-facing summary
    # (``"plays: {loaded}/{attempted} loaded"``) reads coherently only with
    # games semantics.  ``LoadResult`` is aggregate (a sum of plays inserted)
    # and does not expose per-game outcomes, so determine the loaded set by
    # probing ``plays`` for every game we attempted to fetch this run.
    # Pre-fetch-skipped games belong in ``skipped`` (they were loaded by a
    # prior run), so they are excluded from the loaded set here.
    loaded_game_ids: set[str] = set()
    for game_id in plays_data.keys():
        has_plays = conn.execute(
            "SELECT 1 FROM plays "
            "WHERE game_id = ? AND perspective_team_id = ? LIMIT 1",
            (game_id, perspective_team_id),
        ).fetchone()
        if has_plays is not None:
            loaded_game_ids.add(game_id)

    # Reconcile selection: iterate the loaded set computed above.  The
    # contract is "reconcile games whose plays were successfully loaded this
    # run."  Pre-fetch-skipped games (already loaded by a prior run),
    # deferred (auth-expiry), and HTTP-errored games are already excluded
    # because they never appear in ``plays_data`` (pre-fetch-skipped) or
    # never produced a row in this run (deferred/HTTP-errored).
    reconcile_errors = 0
    for game_id in sorted(loaded_game_ids):
        try:
            reconcile_game(
                conn,
                game_id,
                dry_run=False,
                perspective_team_id=perspective_team_id,
            )
        except Exception:  # noqa: BLE001 -- per-game error isolation
            logger.warning(
                "PLAYS STAGE FAILED: reconcile error for game %s "
                "(public_id=%s); plays data still usable.",
                game_id,
                public_id,
                exc_info=True,
            )
            reconcile_errors += 1

    return PlaysStageResult(
        attempted=attempted,
        loaded=len(loaded_game_ids),
        # Pre-fetch-skipped games (already loaded by a prior run) are folded
        # into ``skipped`` here so the operator-facing summary reports
        # ``loaded=0 skipped=N`` on a full rerun (AC-6 idempotency contract).
        skipped=loader_skipped + len(pre_skipped),
        errored=errored,
        reconcile_errors=reconcile_errors,
        auth_expired=auth_expired,
        deferred_game_ids=deferred_game_ids,
    )
