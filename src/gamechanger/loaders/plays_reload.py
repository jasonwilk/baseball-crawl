"""In-place reload of already-loaded plays from stored ``raw_template`` (E-245).

The plays parser historically dropped pitch events that carried a trailing
type/velocity annotation (e.g. ``"Strike 1 looking (Curveball)"``),
classifying them as ``event_type='other'`` and collapsing the parent
``plays.pitch_count`` / ``is_first_pitch_strike`` to 0 (E-245 TN-2/TN-3).
E-245-02 fixes the parser on the FORWARD path, but already-loaded games will
NOT self-heal: whole-game idempotency means a plain report regen skips them.

This module re-derives those games IN PLACE.  The full annotated text is
retained verbatim in ``play_events.raw_template``, so recovery requires NO API
re-fetch: each stored event row is re-classified, the new ``pitch_type`` /
``pitch_speed_mph`` columns are populated, and the parent ``plays`` flags are
recomputed from the recovered events.

Two reload-path subtleties are mandatory (E-245 TN-3a):

* ``is_qab`` is recomputed via an OR-MERGE, never a from-scratch
  ``_compute_qab``.  ``final_details`` (needed for the hard-hit-ball QAB
  condition) is not persisted, so a from-scratch recompute would silently drop
  HHB-only QABs.  The pitch-drop bug only ever produces FALSE-NEGATIVE QABs on
  the two pitch-count-dependent conditions, so
  ``stored_is_qab OR check_2s_plus_3 OR pitch_count >= 6`` recovers them.  The
  ONE wrinkle is that the forward ``_compute_qab`` excludes three outcomes
  (Intentional Walk / Dropped 3rd Strike / Catcher's Interference) BEFORE any
  pitch-count condition; the OR-merge therefore applies the SAME exclusion
  first, otherwise a long-count excluded PA would be (wrongly) flipped to a
  QAB -- including on games the annotation bug never touched, since the batch
  pass visits every play.  With that guard the merge is sound and a true no-op
  on already-correct games.
* ``is_first_pitch`` / ``is_first_pitch_strike`` are RE-DERIVED, not trusted:
  on affected games the annotated true-first pitch was logged as ``'other'`` so
  the stored flag landed on a later bare pitch.

The per-game entry point (:func:`reload_game_plays`) also re-reads home/away
FRESH from the current ``games`` row and re-derives ``batting_team_id`` per
``half`` (E-245 TN-3b).  For E-245-02's own affected games this is a no-op
(their home/away is already correct), but it is the exact mechanism E-245-04
reuses after correcting a self-game's home/away.

This is an IN-PLACE re-derivation: it only UPDATEs existing ``play_events`` and
``plays`` rows.  It NEVER DELETEs (that would destroy ``raw_template``, the only
DB copy of the annotated text) and NEVER invokes ``PlaysParser.parse_game``
(which needs ``final_details``).  Boxscore-derived ``player_game_*`` and
season-aggregate rows are NOT touched.

Usage::

    import sqlite3
    from src.gamechanger.loaders.plays_reload import (
        reload_all_games,
        reload_game_plays,
    )

    conn = sqlite3.connect("./data/app.db")
    conn.execute("PRAGMA foreign_keys=ON;")

    # Single game + perspective (the reusable entry point E-245-04 calls):
    result = reload_game_plays(conn, game_id="abc-123", perspective_team_id=133)
    conn.commit()

    # One-time batch over every loaded (game, perspective) pair:
    summary = reload_all_games(conn)
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from src.gamechanger.parsers.plays_parser import (
    _QAB_EXCLUDED_OUTCOMES,
    ParsedEvent,
    PlaysParser,
)

logger = logging.getLogger(__name__)


@dataclass
class GameReloadResult:
    """Outcome of re-deriving a single ``(game_id, perspective_team_id)`` game.

    Attributes:
        game_id: The game's ``event_id``.
        perspective_team_id: The perspective the plays were loaded from.
        found: ``True`` if plays rows existed for this game+perspective.
        plays_updated: Count of parent ``plays`` rows re-derived (== plays
            found for the game+perspective; every one is rewritten in place).
        events_recovered: Count of ``play_events`` rows that flipped from a
            non-pitch classification to ``event_type='pitch'`` (the stranded
            annotated pitches recovered by this run).
    """

    game_id: str
    perspective_team_id: int
    found: bool = False
    plays_updated: int = 0
    events_recovered: int = 0


def reload_game_plays(
    conn: sqlite3.Connection,
    game_id: str,
    perspective_team_id: int,
) -> GameReloadResult:
    """Re-derive one game's plays + events IN PLACE from stored ``raw_template``.

    This is the reusable per-game entry point (E-245 TN-3/TN-3b).  For the
    given ``(game_id, perspective_team_id)`` it:

    1. Re-reads home/away FRESH from the current ``games`` row and derives
       ``batting_team_id`` per ``half`` (AC-9).
    2. Re-classifies every stored ``play_events`` row from its ``raw_template``
       (recovering stranded annotated pitches; populating ``pitch_type`` /
       ``pitch_speed_mph``) and re-derives ``is_first_pitch``.
    3. Recomputes the parent ``plays`` flags: ``pitch_count``,
       ``is_first_pitch_strike``, ``is_qab`` (via the TN-3a OR-merge), and
       ``batting_team_id``.

    Does NOT commit -- the caller owns the transaction boundary (so E-245-04 can
    call this within its own self-game correction transaction).  Idempotent:
    re-running yields identical re-classifications and recomputed flags.

    Args:
        conn: Open SQLite connection.
        game_id: The game's ``event_id`` (== ``games.game_id``).
        perspective_team_id: The perspective whose plays rows are re-derived.

    Returns:
        A :class:`GameReloadResult`.  ``found=False`` when no plays exist for
        the game+perspective (nothing to do).
    """
    game_row = conn.execute(
        "SELECT home_team_id, away_team_id FROM games WHERE game_id = ?",
        (game_id,),
    ).fetchone()
    if game_row is None:
        logger.warning(
            "Game %s not in games table; cannot reload plays.", game_id,
        )
        return GameReloadResult(game_id, perspective_team_id, found=False)
    home_team_id, away_team_id = game_row

    play_rows = conn.execute(
        """
        SELECT id, play_order, half, is_qab, outcome
        FROM plays
        WHERE game_id = ? AND perspective_team_id = ?
        ORDER BY play_order
        """,
        (game_id, perspective_team_id),
    ).fetchall()

    if not play_rows:
        logger.debug(
            "No plays for game %s perspective %s; nothing to reload.",
            game_id,
            perspective_team_id,
        )
        return GameReloadResult(game_id, perspective_team_id, found=False)

    result = GameReloadResult(
        game_id, perspective_team_id, found=True,
    )

    for play_id, play_order, half, stored_is_qab, outcome in play_rows:
        # Derive batting team from half + FRESH games-row home/away (AC-9).
        batting_team_id = away_team_id if half == "top" else home_team_id

        event_rows = conn.execute(
            """
            SELECT id, event_order, event_type, raw_template
            FROM play_events
            WHERE play_id = ?
            ORDER BY event_order
            """,
            (play_id,),
        ).fetchall()

        recovered_events: list[ParsedEvent] = []
        first_pitch_found = False
        for ev_id, event_order, old_event_type, raw_template in event_rows:
            event_type, pitch_result, pitch_type, pitch_speed_mph = (
                PlaysParser._classify_template(
                    raw_template or "",
                    game_id=game_id,
                    play_order=play_order,
                )
            )

            is_first_pitch = False
            if event_type == "pitch" and not first_pitch_found:
                is_first_pitch = True
                first_pitch_found = True

            if event_type == "pitch" and old_event_type != "pitch":
                result.events_recovered += 1

            conn.execute(
                """
                UPDATE play_events
                SET event_type = ?, pitch_result = ?, is_first_pitch = ?,
                    pitch_type = ?, pitch_speed_mph = ?
                WHERE id = ?
                """,
                (
                    event_type,
                    pitch_result,
                    1 if is_first_pitch else 0,
                    pitch_type,
                    pitch_speed_mph,
                    ev_id,
                ),
            )

            recovered_events.append(ParsedEvent(
                event_order=event_order,
                event_type=event_type,
                pitch_result=pitch_result,
                is_first_pitch=is_first_pitch,
                raw_template=raw_template or "",
                pitch_type=pitch_type,
                pitch_speed_mph=pitch_speed_mph,
            ))

        pitch_events = [e for e in recovered_events if e.event_type == "pitch"]
        pitch_count = len(pitch_events)
        is_fps = PlaysParser._compute_fps(pitch_events)

        # OR-merge QAB (TN-3a) -- NEVER a from-scratch _compute_qab, which
        # needs final_details (not persisted).  The pitch-count-dependent
        # conditions (2S+3, 6+ pitches) are the only ones the bug can
        # false-negative, so OR-ing them onto the stored value recovers those
        # without touching the final_details-derived conditions baked into
        # stored_is_qab.  EXCEPTION: the forward _compute_qab excludes three
        # outcomes (IBB / Dropped 3rd Strike / Catcher's Interference) BEFORE
        # any pitch-count condition, so the OR-merge MUST apply the same
        # exclusion -- otherwise a long-count excluded PA (e.g. a Dropped 3rd
        # Strike at 6+ pitches) would be flipped to is_qab=1, including on
        # games never touched by the annotation bug.  Reuse the SAME excluded
        # set the forward path uses so the two paths stay in lockstep.
        if outcome in _QAB_EXCLUDED_OUTCOMES:
            new_is_qab = 0
        else:
            new_is_qab = 1 if (
                stored_is_qab
                or PlaysParser._check_2s_plus_3(pitch_events)
                or pitch_count >= 6
            ) else 0

        conn.execute(
            """
            UPDATE plays
            SET pitch_count = ?, is_first_pitch_strike = ?,
                is_qab = ?, batting_team_id = ?
            WHERE id = ?
            """,
            (pitch_count, is_fps, new_is_qab, batting_team_id, play_id),
        )
        result.plays_updated += 1

    return result


def reload_all_games(conn: sqlite3.Connection) -> dict[str, int]:
    """Re-derive every loaded ``(game_id, perspective_team_id)`` game in place.

    One-time operator-runnable batch driver (the ``bb data`` command wraps this)
    following the ``bb data backfill-appearance-order`` precedent.  Iterates
    every distinct ``(game_id, perspective_team_id)`` pair present in ``plays``
    and calls :func:`reload_game_plays` for each, committing per game so a
    mid-run failure isolates to one game.  Idempotent and re-runnable.

    Unaffected (correctly-parsed) games are still visited; their re-derivation
    is a no-op (identical re-classification, identical recomputed flags), so the
    pass is safe to run over the whole database.

    Args:
        conn: Open SQLite connection.

    Returns:
        Summary dict with keys ``games_processed``, ``games_changed``,
        ``plays_updated``, ``events_recovered``, ``games_with_errors``.
    """
    summary = {
        "games_processed": 0,
        "games_changed": 0,
        "plays_updated": 0,
        "events_recovered": 0,
        "games_with_errors": 0,
    }

    pairs = conn.execute(
        """
        SELECT DISTINCT game_id, perspective_team_id
        FROM plays
        ORDER BY game_id, perspective_team_id
        """,
    ).fetchall()

    if not pairs:
        logger.info("No plays rows found; nothing to reload.")
        return summary

    logger.info(
        "Reloading annotated pitches across %d (game, perspective) pair(s).",
        len(pairs),
    )

    for game_id, perspective_team_id in pairs:
        try:
            result = reload_game_plays(conn, game_id, perspective_team_id)
            conn.commit()
        except Exception as exc:  # noqa: BLE001 -- per-game error isolation
            conn.rollback()
            logger.error(
                "Reload error for game %s perspective %s: %s",
                game_id,
                perspective_team_id,
                exc,
            )
            summary["games_with_errors"] += 1
            continue

        if not result.found:
            continue
        summary["games_processed"] += 1
        summary["plays_updated"] += result.plays_updated
        summary["events_recovered"] += result.events_recovered
        if result.events_recovered > 0:
            summary["games_changed"] += 1

    logger.info(
        "Reload complete: processed=%d changed=%d plays_updated=%d "
        "events_recovered=%d errors=%d",
        summary["games_processed"],
        summary["games_changed"],
        summary["plays_updated"],
        summary["events_recovered"],
        summary["games_with_errors"],
    )
    return summary
