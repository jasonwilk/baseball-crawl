"""Reconciliation engine: compare plays-derived aggregates against boxscore ground truth.

Detection mode (dry_run=True, default): produces discrepancy records without
modifying any data.  Execute mode (dry_run=False): detects discrepancies AND
applies pitcher attribution corrections in a single pass.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# Outcome sets used for plays-side derivation
_HIT_OUTCOMES = frozenset({"Single", "Double", "Triple", "Home Run"})
_SO_OUTCOMES = frozenset({"Strikeout", "Dropped 3rd Strike"})
_BB_OUTCOMES = frozenset({"Walk", "Intentional Walk"})
_HBP_OUTCOMES = frozenset({"Hit By Pitch"})

# AB exclusion: plays where the batter gets a PA but not an AB
_AB_EXCLUSIONS = frozenset({
    "Walk", "Hit By Pitch", "Sacrifice Fly", "Sacrifice Bunt",
    "Catcher's Interference", "Intentional Walk",
})

# Pitch results that count as strikes for total-strikes derivation
_STRIKE_PITCH_RESULTS = frozenset({
    "strike_looking", "strike_swinging", "foul", "foul_tip", "in_play",
})

GAME_LEVEL_PLAYER_ID = "__game__"


@dataclass
class ReconciliationSummary:
    """Summary of a reconciliation run."""

    games_processed: int = 0
    games_skipped_no_plays: int = 0
    signal_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    # signal_counts maps signal_name -> {MATCH: n, CORRECTABLE: n, ...}

    # Per-game outcome counts (populated by reconcile_all)
    games_all_match: int = 0
    games_with_correctable: int = 0
    games_with_ambiguous: int = 0

    # Correction tracking (populated in execute mode)
    games_corrected: int = 0
    games_unchanged: int = 0
    games_with_remaining_ambiguity: int = 0
    total_plays_reassigned: int = 0
    pre_correction_signal_counts: dict[str, dict[str, int]] = field(default_factory=dict)


@dataclass
class _Discrepancy:
    """Internal representation of a single discrepancy row.

    E-220 round 7 P1-2: ``perspective_team_id`` is the team whose API call
    produced the data under reconciliation; ``team_id`` is the participant
    team (home or away) the signal is scoped to.  Both are required so
    cross-perspective discrepancies for the same game do not collide on
    the UNIQUE key.
    """

    game_id: str
    perspective_team_id: int
    team_id: int
    player_id: str
    signal_name: str
    category: str
    boxscore_value: int | None
    plays_value: int | None
    delta: int | None
    status: str
    correction_detail: str | None = None


def reconcile_game(
    conn: sqlite3.Connection,
    game_id: str,
    dry_run: bool = True,
    run_id: str | None = None,
    *,
    perspective_team_id: int | None = None,
) -> ReconciliationSummary:
    """Run reconciliation detection for a single game.

    Args:
        conn: Open SQLite connection.
        game_id: The game to reconcile.
        dry_run: If True (default), only detect and log -- no corrections.
        run_id: UUID for this batch run.  Generated if not provided.
        perspective_team_id: E-220 round 6 cluster 4.  When provided,
            restricts reconciliation to the given perspective (target team
            for report generation, or explicit operator selection).  The
            idempotency check and perspective selection honor this value.
            When ``None``, uses the deterministic home-first preference
            for backwards compatibility with existing callers.

    Returns:
        ReconciliationSummary with signal match counts.
    """
    if run_id is None:
        run_id = str(uuid.uuid4())

    summary = ReconciliationSummary()

    # E-220 round 6 cluster 4: the idempotency check is per-perspective.
    # Before the fix, this was `WHERE game_id = ?` only, so once any
    # perspective of a game had plays, subsequent reconcile calls for
    # OTHER perspectives skipped as if already processed.
    if perspective_team_id is not None:
        plays_count = conn.execute(
            "SELECT COUNT(*) FROM plays WHERE game_id = ? AND perspective_team_id = ?",
            (game_id, perspective_team_id),
        ).fetchone()[0]
    else:
        plays_count = conn.execute(
            "SELECT COUNT(*) FROM plays WHERE game_id = ?", (game_id,)
        ).fetchone()[0]
    if plays_count == 0:
        logger.warning(
            "No plays data for game_id=%s%s; skipping reconciliation.",
            game_id,
            f" perspective={perspective_team_id}" if perspective_team_id is not None else "",
        )
        summary.games_skipped_no_plays = 1
        return summary

    # Load game metadata
    game_row = conn.execute(
        "SELECT season_id, home_team_id, away_team_id, game_stream_id, "
        "home_score, away_score "
        "FROM games WHERE game_id = ?",
        (game_id,),
    ).fetchone()
    if game_row is None:
        logger.warning("Game %s not found in games table.", game_id)
        summary.games_skipped_no_plays = 1
        return summary

    season_id, home_team_id, away_team_id, game_stream_id, game_home_score, game_away_score = game_row

    # E-220: pick a single perspective for the entire reconciliation pass.
    # Round 6 cluster 4: when perspective_team_id is provided, use it
    # directly (report-path and operator-scoped reconcile).  Otherwise fall
    # back to the home-first deterministic selection.
    if perspective_team_id is not None:
        # Verify the requested perspective actually has plays for this game.
        perspective_row = conn.execute(
            "SELECT perspective_team_id FROM plays "
            "WHERE game_id = ? AND perspective_team_id = ? LIMIT 1",
            (game_id, perspective_team_id),
        ).fetchone()
    else:
        perspective_row = conn.execute(
            """
            SELECT COALESCE(
                (SELECT perspective_team_id FROM plays
                  WHERE game_id = ? AND perspective_team_id IN (?, ?)
                  ORDER BY CASE perspective_team_id
                      WHEN ? THEN 0
                      WHEN ? THEN 1
                      ELSE 2
                  END, perspective_team_id
                  LIMIT 1),
                (SELECT MIN(perspective_team_id) FROM plays WHERE game_id = ?)
            )
            """,
            (game_id, home_team_id, away_team_id,
             home_team_id, away_team_id, game_id),
        ).fetchone()
    chosen_perspective_id = perspective_row[0] if perspective_row else None
    if chosen_perspective_id is None:
        logger.warning(
            "No perspective found for game_id=%s; skipping reconciliation.",
            game_id,
        )
        summary.games_skipped_no_plays = 1
        return summary

    # Load plays and play_events
    plays_rows = conn.execute(
        "SELECT id, play_order, inning, half, batting_team_id, batter_id, "
        "pitcher_id, outcome, pitch_count, is_first_pitch_strike, "
        "home_score, away_score, did_outs_change "
        "FROM plays WHERE game_id = ? AND perspective_team_id = ? "
        "ORDER BY play_order",
        (game_id, chosen_perspective_id),
    ).fetchall()

    play_events_rows = conn.execute(
        "SELECT pe.play_id, pe.event_order, pe.event_type, pe.pitch_result, pe.raw_template "
        "FROM play_events pe "
        "JOIN plays p ON pe.play_id = p.id "
        "WHERE p.game_id = ? AND p.perspective_team_id = ? "
        "ORDER BY pe.play_id, pe.event_order",
        (game_id, chosen_perspective_id),
    ).fetchall()

    # Index play_events by play_id
    events_by_play: dict[int, list[tuple]] = {}
    for ev_row in play_events_rows:
        play_id = ev_row[0]
        events_by_play.setdefault(play_id, []).append(ev_row)

    # Process both teams
    discrepancies: list[_Discrepancy] = []

    for team_id in (home_team_id, away_team_id):
        is_home = team_id == home_team_id

        # Pitcher signals: pitchers for this team pitch when the OTHER team bats
        pitching_half = "top" if is_home else "bottom"
        batting_half = "bottom" if is_home else "top"

        # Load boxscore pitching data for this team (own perspective if available;
        # otherwise the same chosen perspective the plays were loaded from)
        pitching_rows = conn.execute(
            "SELECT player_id, ip_outs, h, r, er, bb, so, wp, hbp, pitches, "
            "total_strikes, bf, decision "
            "FROM player_game_pitching "
            "WHERE game_id = ? AND team_id = ? AND perspective_team_id = ? "
            "ORDER BY id",
            (game_id, team_id, chosen_perspective_id),
        ).fetchall()

        # Load boxscore batting data for this team
        batting_rows = conn.execute(
            "SELECT player_id, ab, r, h, bb, so, hbp "
            "FROM player_game_batting "
            "WHERE game_id = ? AND team_id = ? AND perspective_team_id = ? ",
            (game_id, team_id, chosen_perspective_id),
        ).fetchall()

        # Get pitcher order from cached boxscore JSON
        pitcher_order_from_json = _extract_pitcher_order(
            conn, game_id, game_stream_id, season_id, team_id, is_home,
            perspective_team_id=chosen_perspective_id,
        )

        # Team's plays when pitching (other team is batting)
        team_pitching_plays = [
            p for p in plays_rows if p[3] == pitching_half  # half column
        ]
        # Team's plays when batting
        team_batting_plays = [
            p for p in plays_rows if p[3] == batting_half
        ]

        # Run pitcher signal checks
        _check_pitcher_signals(
            pitching_rows, team_pitching_plays, events_by_play,
            pitcher_order_from_json, game_id, chosen_perspective_id, team_id,
            discrepancies,
        )

        # Run batter signal checks
        _check_batter_signals(
            batting_rows, team_batting_plays, game_id, chosen_perspective_id,
            team_id, discrepancies,
        )

        # Run game-level sanity checks
        _check_game_level_signals(
            pitching_rows, batting_rows, team_pitching_plays,
            team_batting_plays, plays_rows,
            game_id, chosen_perspective_id, team_id, is_home,
            discrepancies,
            game_home_score=game_home_score,
            game_away_score=game_away_score,
        )

    # In execute mode: capture pre-correction status per signal/team/player,
    # apply corrections, then re-detect to get post-correction signals
    if not dry_run:
        # Save pre-correction status per (signal_name, team_id, player_id)
        pre_status_map: dict[tuple[str, int, str], str] = {}
        for d in discrepancies:
            pre_status_map[(d.signal_name, d.team_id, d.player_id)] = d.status
            pre = summary.pre_correction_signal_counts.setdefault(d.signal_name, {})
            pre[d.status] = pre.get(d.status, 0) + 1

        # Apply pitcher attribution corrections for each team
        total_reassigned = 0
        all_corrections: list[dict[str, Any]] = []
        for team_id in (home_team_id, away_team_id):
            is_home = team_id == home_team_id
            pitching_half = "top" if is_home else "bottom"

            pitching_rows = conn.execute(
                "SELECT player_id, ip_outs, h, r, er, bb, so, wp, hbp, pitches, "
                "total_strikes, bf, decision "
                "FROM player_game_pitching "
                "WHERE game_id = ? AND team_id = ? AND perspective_team_id = ? "
                "ORDER BY id",
                (game_id, team_id, chosen_perspective_id),
            ).fetchall()

            pitcher_order_from_json = _extract_pitcher_order(
                conn, game_id, game_stream_id, season_id, team_id, is_home,
                perspective_team_id=chosen_perspective_id,
            )

            corrections = _correct_pitcher_attribution(
                conn, game_id, team_id, pitching_half,
                pitching_rows, pitcher_order_from_json,
                chosen_perspective_id,
            )
            total_reassigned += len(corrections)
            all_corrections.extend(corrections)

        summary.total_plays_reassigned = total_reassigned

        # Re-detect after correction: reload plays and rebuild discrepancies
        discrepancies = []
        plays_rows = conn.execute(
            "SELECT id, play_order, inning, half, batting_team_id, batter_id, "
            "pitcher_id, outcome, pitch_count, is_first_pitch_strike, "
            "home_score, away_score, did_outs_change "
            "FROM plays WHERE game_id = ? AND perspective_team_id = ? "
            "ORDER BY play_order",
            (game_id, chosen_perspective_id),
        ).fetchall()

        play_events_rows = conn.execute(
            "SELECT pe.play_id, pe.event_order, pe.event_type, pe.pitch_result, pe.raw_template "
            "FROM play_events pe JOIN plays p ON pe.play_id = p.id "
            "WHERE p.game_id = ? AND p.perspective_team_id = ? "
            "ORDER BY pe.play_id, pe.event_order",
            (game_id, chosen_perspective_id),
        ).fetchall()
        events_by_play = {}
        for ev_row in play_events_rows:
            events_by_play.setdefault(ev_row[0], []).append(ev_row)

        for team_id in (home_team_id, away_team_id):
            is_home = team_id == home_team_id
            pitching_half = "top" if is_home else "bottom"
            batting_half = "bottom" if is_home else "top"

            pitching_rows = conn.execute(
                "SELECT player_id, ip_outs, h, r, er, bb, so, wp, hbp, pitches, "
                "total_strikes, bf, decision "
                "FROM player_game_pitching "
                "WHERE game_id = ? AND team_id = ? AND perspective_team_id = ? "
                "ORDER BY id",
                (game_id, team_id, chosen_perspective_id),
            ).fetchall()
            batting_rows = conn.execute(
                "SELECT player_id, ab, r, h, bb, so, hbp "
                "FROM player_game_batting "
                "WHERE game_id = ? AND team_id = ? AND perspective_team_id = ?",
                (game_id, team_id, chosen_perspective_id),
            ).fetchall()
            pitcher_order_from_json = _extract_pitcher_order(
                conn, game_id, game_stream_id, season_id, team_id, is_home,
                perspective_team_id=chosen_perspective_id,
            )

            team_pitching_plays = [p for p in plays_rows if p[3] == pitching_half]
            team_batting_plays = [p for p in plays_rows if p[3] == batting_half]

            _check_pitcher_signals(
                pitching_rows, team_pitching_plays, events_by_play,
                pitcher_order_from_json, game_id, chosen_perspective_id, team_id,
                discrepancies,
            )
            _check_batter_signals(
                batting_rows, team_batting_plays, game_id, chosen_perspective_id,
                team_id, discrepancies,
            )
            _check_game_level_signals(
                pitching_rows, batting_rows, team_pitching_plays,
                team_batting_plays, plays_rows, game_id,
                chosen_perspective_id, team_id, is_home,
                discrepancies,
                game_home_score=game_home_score,
                game_away_score=game_away_score,
            )

        # Build correction_detail JSON for affected pitcher signals
        correction_detail_json = json.dumps(all_corrections) if all_corrections else None

        # Upgrade signals to CORRECTED only when that specific signal was
        # non-MATCH pre-correction and is now MATCH post-correction
        for d in discrepancies:
            if d.status == "MATCH" and d.category == "pitcher":
                pre_status = pre_status_map.get(
                    (d.signal_name, d.team_id, d.player_id)
                )
                if pre_status == "CORRECTABLE":
                    d.status = "CORRECTED"
                    # Merge reassignment info with existing correction_detail
                    # (e.g., supplement metadata) rather than overwriting it.
                    if d.correction_detail and correction_detail_json:
                        existing = json.loads(d.correction_detail)
                        d.correction_detail = json.dumps({
                            **existing,
                            "reassignments": all_corrections,
                        })
                    elif correction_detail_json:
                        d.correction_detail = correction_detail_json

        # Track game-level correction outcomes
        post_statuses: set[str] = set()
        for d in discrepancies:
            post_statuses.add(d.status)
        if total_reassigned > 0:
            summary.games_corrected = 1
        else:
            summary.games_unchanged = 1
        post_statuses.discard("MATCH")
        post_statuses.discard("CORRECTED")
        if "AMBIGUOUS" in post_statuses:
            summary.games_with_remaining_ambiguity = 1

    # Write discrepancy rows (always -- dry_run only gates corrections, not logging)
    _write_discrepancies(conn, run_id, discrepancies)

    # Build summary
    summary.games_processed = 1
    for d in discrepancies:
        counts = summary.signal_counts.setdefault(d.signal_name, {})
        counts[d.status] = counts.get(d.status, 0) + 1

    return summary


def reconcile_all(
    conn: sqlite3.Connection,
    dry_run: bool = True,
) -> ReconciliationSummary:
    """Reconcile all games that have plays data.

    E-220 round 6 cluster 4: iterates ``(game_id, perspective_team_id)``
    pairs from the plays table.  Each perspective is reconciled
    independently so cross-perspective loads both get processed.

    Returns:
        Aggregated ReconciliationSummary across all loaded perspectives.
    """
    run_id = str(uuid.uuid4())
    total_summary = ReconciliationSummary()

    # One reconcile pass per (game_id, perspective_team_id) pair.
    game_perspective_pairs = [
        (row[0], row[1]) for row in conn.execute(
            "SELECT DISTINCT game_id, perspective_team_id FROM plays "
            "ORDER BY game_id, perspective_team_id"
        ).fetchall()
    ]

    for gid, ptid in game_perspective_pairs:
        game_summary = reconcile_game(
            conn, gid, dry_run=dry_run, run_id=run_id,
            perspective_team_id=ptid,
        )
        total_summary.games_processed += game_summary.games_processed
        total_summary.games_skipped_no_plays += game_summary.games_skipped_no_plays

        # Track per-game outcome classification
        if game_summary.games_processed > 0:
            game_statuses: set[str] = set()
            for counts in game_summary.signal_counts.values():
                game_statuses.update(counts.keys())
            game_statuses.discard("MATCH")

            if not game_statuses:
                total_summary.games_all_match += 1
            if "CORRECTABLE" in game_statuses:
                total_summary.games_with_correctable += 1
            if "AMBIGUOUS" in game_statuses:
                total_summary.games_with_ambiguous += 1

        # Aggregate correction tracking
        total_summary.games_corrected += game_summary.games_corrected
        total_summary.games_unchanged += game_summary.games_unchanged
        total_summary.games_with_remaining_ambiguity += game_summary.games_with_remaining_ambiguity
        total_summary.total_plays_reassigned += game_summary.total_plays_reassigned

        for sig, counts in game_summary.signal_counts.items():
            existing = total_summary.signal_counts.setdefault(sig, {})
            for status, n in counts.items():
                existing[status] = existing.get(status, 0) + n

        for sig, counts in game_summary.pre_correction_signal_counts.items():
            existing = total_summary.pre_correction_signal_counts.setdefault(sig, {})
            for status, n in counts.items():
                existing[status] = existing.get(status, 0) + n

    return total_summary


# ---------------------------------------------------------------------------
# Pitcher signal checks
# ---------------------------------------------------------------------------


def _check_pitcher_signals(
    pitching_rows: list[tuple],
    pitching_plays: list[tuple],
    events_by_play: dict[int, list[tuple]],
    pitcher_order_json: list[dict[str, Any]] | None,
    game_id: str,
    perspective_team_id: int,
    team_id: int,
    discrepancies: list[_Discrepancy],
) -> None:
    """Check all pitcher signals for one team in one game."""
    # Index boxscore data by player_id
    # pitching_rows cols: player_id, ip_outs, h, r, er, bb, so, wp, hbp, pitches, total_strikes, bf, decision
    box_pitchers: dict[str, dict[str, Any]] = {}
    for row in pitching_rows:
        pid = row[0]
        box_pitchers[pid] = {
            "ip_outs": row[1] or 0,
            "h": row[2] or 0,
            "r": row[3] or 0,
            "er": row[4] or 0,
            "bb": row[5] or 0,
            "so": row[6] or 0,
            "wp": row[7] or 0,
            "hbp": row[8] or 0,
            "pitches": row[9] or 0,
            "pitches_null": row[9] is None,
            "total_strikes": row[10] or 0,
            "total_strikes_null": row[10] is None,
            "bf": row[11] or 0,
            "decision": row[12],
        }

    # Derive plays-side aggregates per pitcher
    plays_pitchers: dict[str, dict[str, int]] = {}
    for play in pitching_plays:
        play_id, play_order, inning, half, batting_team_id, batter_id, pitcher_id = play[:7]
        outcome = play[7]
        pitch_count = play[8]
        did_outs_change = play[12]

        if pitcher_id is None:
            continue

        stats = plays_pitchers.setdefault(pitcher_id, {
            "bf": 0, "so": 0, "bb": 0, "hbp": 0, "h": 0, "pitches": 0,
            "outs": 0, "wp": 0, "total_strikes": 0,
        })
        stats["bf"] += 1
        stats["pitches"] += pitch_count or 0

        if outcome in _SO_OUTCOMES:
            stats["so"] += 1
        if outcome in _BB_OUTCOMES:
            stats["bb"] += 1
        if outcome in _HBP_OUTCOMES:
            stats["hbp"] += 1
        if outcome in _HIT_OUTCOMES:
            stats["h"] += 1
        if did_outs_change:
            stats["outs"] += 1

    # Count total strikes and wild pitches from play_events
    for play in pitching_plays:
        play_id = play[0]
        pitcher_id = play[6]
        if pitcher_id is None:
            continue
        events = events_by_play.get(play_id, [])
        stats = plays_pitchers.setdefault(pitcher_id, {
            "bf": 0, "so": 0, "bb": 0, "hbp": 0, "h": 0, "pitches": 0,
            "outs": 0, "wp": 0, "total_strikes": 0,
        })
        for ev in events:
            # ev: play_id, event_order, event_type, pitch_result, raw_template
            pitch_result = ev[3]
            raw_template = ev[4]
            if pitch_result in _STRIKE_PITCH_RESULTS:
                stats["total_strikes"] += 1
            if raw_template and ("wild pitch" in raw_template.lower()):
                stats["wp"] += 1

    # High-confidence boxscore supplement for pitches and total_strikes.
    # Gate: BF, SO, and BB all match between boxscore and plays.
    # When the gate passes, replace plays-side pitches/total_strikes with
    # boxscore values (the boxscore is authoritative for these).
    supplemented: dict[str, dict[str, int]] = {}  # pid -> {orig_pitches, orig_total_strikes}
    for pid, plays in plays_pitchers.items():
        box = box_pitchers.get(pid)
        if box is None:
            continue
        bf_match = box["bf"] == plays["bf"]
        so_match = box["so"] == plays["so"]
        bb_match = box["bb"] == plays["bb"]
        if bf_match and so_match and bb_match and not box["pitches_null"] and not box["total_strikes_null"]:
            orig_pitches = plays["pitches"]
            orig_total_strikes = plays["total_strikes"]
            plays["pitches"] = box["pitches"]
            plays["total_strikes"] = box["total_strikes"]
            supplemented[pid] = {
                "orig_pitches": orig_pitches,
                "orig_total_strikes": orig_total_strikes,
            }

    # Build plays-side pitcher order
    plays_pitcher_order: list[str] = []
    seen_pitchers: set[str] = set()
    for play in pitching_plays:
        pitcher_id = play[6]
        if pitcher_id and pitcher_id not in seen_pitchers:
            plays_pitcher_order.append(pitcher_id)
            seen_pitchers.add(pitcher_id)

    # Build boxscore pitcher order from JSON (or fallback to DB order)
    if pitcher_order_json is not None:
        box_pitcher_order = [p["player_id"] for p in pitcher_order_json]
    else:
        box_pitcher_order = [row[0] for row in pitching_rows]

    # 1A. Starter ID
    box_starter = box_pitcher_order[0] if box_pitcher_order else None
    plays_starter = plays_pitcher_order[0] if plays_pitcher_order else None
    if box_starter is not None or plays_starter is not None:
        is_match = box_starter == plays_starter
        discrepancies.append(_Discrepancy(
            game_id=game_id,
            perspective_team_id=perspective_team_id,
            team_id=team_id,
            player_id=box_starter or plays_starter or GAME_LEVEL_PLAYER_ID,
            signal_name="pitcher_starter_id",
            category="pitcher",
            boxscore_value=1 if box_starter else 0,
            plays_value=1 if plays_starter else 0,
            delta=0 if is_match else 1,
            status="MATCH" if is_match else "CORRECTABLE",
            correction_detail=json.dumps({
                "boxscore_starter": box_starter,
                "plays_starter": plays_starter,
            }) if not is_match else None,
        ))

    # 1L. Pitching order
    order_matches = box_pitcher_order == plays_pitcher_order
    # Use the first pitcher as player_id for the order signal
    order_player_id = box_pitcher_order[0] if box_pitcher_order else GAME_LEVEL_PLAYER_ID
    discrepancies.append(_Discrepancy(
        game_id=game_id,
        perspective_team_id=perspective_team_id,
        team_id=team_id,
        player_id=order_player_id,
        signal_name="pitcher_order",
        category="pitcher",
        boxscore_value=len(box_pitcher_order),
        plays_value=len(plays_pitcher_order),
        delta=0 if order_matches else 1,
        status="MATCH" if order_matches else "CORRECTABLE",
        correction_detail=json.dumps({
            "boxscore_order": box_pitcher_order,
            "plays_order": plays_pitcher_order,
        }) if not order_matches else None,
    ))

    # Per-pitcher signals: iterate over all pitchers from both sources
    all_pitcher_ids = set(box_pitchers.keys()) | set(plays_pitchers.keys())
    for pid in all_pitcher_ids:
        box = box_pitchers.get(pid, {})
        plays = plays_pitchers.get(pid, {})

        # Determine if player is missing from one side entirely
        missing_box = pid not in box_pitchers
        missing_plays = pid not in plays_pitchers

        # 1B. BF per pitcher
        _add_pitcher_signal(
            discrepancies, game_id, perspective_team_id, team_id, pid,
            "pitcher_bf",
            box.get("bf", 0), plays.get("bf", 0),
            missing_box, missing_plays,
            correctable=True,
        )

        # 1C. IP/Outs per pitcher (always AMBIGUOUS)
        box_outs = box.get("ip_outs", 0)
        plays_outs = plays.get("outs", 0)
        delta = box_outs - plays_outs
        discrepancies.append(_Discrepancy(
            game_id=game_id,
            perspective_team_id=perspective_team_id,
            team_id=team_id,
            player_id=pid,
            signal_name="pitcher_ip_outs",
            category="pitcher",
            boxscore_value=box_outs,
            plays_value=plays_outs,
            delta=delta,
            status="MATCH" if delta == 0 else "AMBIGUOUS",
        ))

        # 1D. SO per pitcher
        _add_pitcher_signal(
            discrepancies, game_id, perspective_team_id, team_id, pid,
            "pitcher_so",
            box.get("so", 0), plays.get("so", 0),
            missing_box, missing_plays,
            correctable=True,
        )

        # 1E. BB per pitcher
        _add_pitcher_signal(
            discrepancies, game_id, perspective_team_id, team_id, pid,
            "pitcher_bb",
            box.get("bb", 0), plays.get("bb", 0),
            missing_box, missing_plays,
            correctable=True,
        )

        # 1F. HBP per pitcher
        _add_pitcher_signal(
            discrepancies, game_id, perspective_team_id, team_id, pid,
            "pitcher_hbp",
            box.get("hbp", 0), plays.get("hbp", 0),
            missing_box, missing_plays,
            correctable=True,
        )

        # 1G. Pitch count per pitcher
        supp = supplemented.get(pid)
        pitches_detail = None
        if supp is not None:
            pitches_detail = json.dumps({
                "boxscore_supplement": True,
                "plays_pitches": supp["orig_pitches"],
                "boxscore_pitches": box.get("pitches", 0),
                "gate": "BF+SO+BB match",
            })
        _add_pitcher_signal(
            discrepancies, game_id, perspective_team_id, team_id, pid,
            "pitcher_pitches",
            box.get("pitches", 0), plays.get("pitches", 0),
            missing_box, missing_plays,
            correctable=True,
            correction_detail=pitches_detail,
        )

        # 1H. Total strikes per pitcher
        strikes_detail = None
        if supp is not None:
            strikes_detail = json.dumps({
                "boxscore_supplement": True,
                "plays_total_strikes": supp["orig_total_strikes"],
                "boxscore_total_strikes": box.get("total_strikes", 0),
                "gate": "BF+SO+BB match",
            })
        _add_pitcher_signal(
            discrepancies, game_id, perspective_team_id, team_id, pid,
            "pitcher_total_strikes",
            box.get("total_strikes", 0), plays.get("total_strikes", 0),
            missing_box, missing_plays,
            correctable=True,
            correction_detail=strikes_detail,
        )

        # 1I. Hits allowed per pitcher
        _add_pitcher_signal(
            discrepancies, game_id, perspective_team_id, team_id, pid,
            "pitcher_h",
            box.get("h", 0), plays.get("h", 0),
            missing_box, missing_plays,
            correctable=True,
        )

        # 1K. WP per pitcher (always AMBIGUOUS when non-zero delta)
        box_wp = box.get("wp", 0)
        plays_wp = plays.get("wp", 0)
        wp_delta = box_wp - plays_wp
        discrepancies.append(_Discrepancy(
            game_id=game_id,
            perspective_team_id=perspective_team_id,
            team_id=team_id,
            player_id=pid,
            signal_name="pitcher_wp",
            category="pitcher",
            boxscore_value=box_wp,
            plays_value=plays_wp,
            delta=wp_delta,
            status="MATCH" if wp_delta == 0 else "AMBIGUOUS",
        ))


def _add_pitcher_signal(
    discrepancies: list[_Discrepancy],
    game_id: str,
    perspective_team_id: int,
    team_id: int,
    player_id: str,
    signal_name: str,
    box_val: int,
    plays_val: int,
    missing_box: bool,
    missing_plays: bool,
    correctable: bool = True,
    correction_detail: str | None = None,
) -> None:
    """Add a standard pitcher signal discrepancy."""
    delta = box_val - plays_val
    if delta == 0:
        status = "MATCH"
    elif missing_box or missing_plays:
        status = "UNCORRECTABLE"
    elif correctable:
        status = "CORRECTABLE"
    else:
        status = "AMBIGUOUS"

    discrepancies.append(_Discrepancy(
        game_id=game_id,
        perspective_team_id=perspective_team_id,
        team_id=team_id,
        player_id=player_id,
        signal_name=signal_name,
        category="pitcher",
        boxscore_value=box_val,
        plays_value=plays_val,
        delta=delta,
        status=status,
        correction_detail=correction_detail,
    ))


# ---------------------------------------------------------------------------
# Batter signal checks
# ---------------------------------------------------------------------------


def _check_batter_signals(
    batting_rows: list[tuple],
    batting_plays: list[tuple],
    game_id: str,
    perspective_team_id: int,
    team_id: int,
    discrepancies: list[_Discrepancy],
) -> None:
    """Check batter signals (detection only, no correction)."""
    # batting_rows cols: player_id, ab, r, h, bb, so, hbp
    box_batters: dict[str, dict[str, int]] = {}
    for row in batting_rows:
        pid = row[0]
        box_batters[pid] = {
            "ab": row[1] or 0,
            "r": row[2] or 0,
            "h": row[3] or 0,
            "bb": row[4] or 0,
            "so": row[5] or 0,
            "hbp": row[6] or 0,
        }

    # Derive plays-side batter aggregates
    plays_batters: dict[str, dict[str, int]] = {}
    for play in batting_plays:
        batter_id = play[5]
        outcome = play[7]
        if batter_id is None:
            continue

        stats = plays_batters.setdefault(batter_id, {
            "ab": 0, "h": 0, "so": 0, "bb": 0, "hbp": 0,
        })
        # AB = all PAs minus exclusions
        if outcome not in _AB_EXCLUSIONS:
            stats["ab"] += 1
        if outcome in _HIT_OUTCOMES:
            stats["h"] += 1
        if outcome in _SO_OUTCOMES:
            stats["so"] += 1
        if outcome in _BB_OUTCOMES:
            stats["bb"] += 1
        if outcome in _HBP_OUTCOMES:
            stats["hbp"] += 1

    # Compare per batter -- only check batters in boxscore
    all_batter_ids = set(box_batters.keys()) | set(plays_batters.keys())
    for pid in all_batter_ids:
        box = box_batters.get(pid, {})
        plays = plays_batters.get(pid, {})

        for signal, key in [
            ("batter_ab", "ab"),
            ("batter_h", "h"),
            ("batter_so", "so"),
            ("batter_bb", "bb"),
            ("batter_hbp", "hbp"),
        ]:
            box_val = box.get(key, 0)
            plays_val = plays.get(key, 0)
            delta = box_val - plays_val
            discrepancies.append(_Discrepancy(
                game_id=game_id,
                perspective_team_id=perspective_team_id,
                team_id=team_id,
                player_id=pid,
                signal_name=signal,
                category="batter",
                boxscore_value=box_val,
                plays_value=plays_val,
                delta=delta,
                status="MATCH" if delta == 0 else "AMBIGUOUS",
            ))


# ---------------------------------------------------------------------------
# Game-level sanity checks
# ---------------------------------------------------------------------------


def _check_game_level_signals(
    pitching_rows: list[tuple],
    batting_rows: list[tuple],
    pitching_plays: list[tuple],
    batting_plays: list[tuple],
    all_plays: list[tuple],
    game_id: str,
    perspective_team_id: int,
    team_id: int,
    is_home: bool,
    discrepancies: list[_Discrepancy],
    *,
    game_home_score: int | None = None,
    game_away_score: int | None = None,
) -> None:
    """Check game-level sanity signals for one team."""
    # 4C. game_pa_count: data-availability check using boxscore BF sum for
    # both sides (handles abandoned final PAs that plays miss).
    # Skip when no boxscore pitching data exists (0 vs 0 is not meaningful).
    box_pa = sum((row[11] or 0) for row in pitching_rows)  # bf is index 11
    if box_pa > 0:
        discrepancies.append(_Discrepancy(
            game_id=game_id,
            perspective_team_id=perspective_team_id,
            team_id=team_id,
            player_id=GAME_LEVEL_PLAYER_ID,
            signal_name="game_pa_count",
            category="game_level",
            boxscore_value=box_pa,
            plays_value=box_pa,
            delta=0,
            status="MATCH",
        ))

    # 4A-runs. game_runs: data-availability check using games.home_score/away_score
    # for both sides. Skip entirely when EITHER score is NULL (per AC-4).
    team_score = game_home_score if is_home else game_away_score
    if game_home_score is not None and game_away_score is not None:
        discrepancies.append(_Discrepancy(
            game_id=game_id,
            perspective_team_id=perspective_team_id,
            team_id=team_id,
            player_id=GAME_LEVEL_PLAYER_ID,
            signal_name="game_runs",
            category="game_level",
            boxscore_value=team_score,
            plays_value=team_score,
            delta=0,
            status="MATCH",
        ))

    # 4A-hits. game_hits: SUM(batting.h) vs plays-derived hits
    box_hits = sum((row[3] or 0) for row in batting_rows)  # h is index 3
    plays_hits = sum(1 for p in batting_plays if p[7] in _HIT_OUTCOMES)
    hits_delta = box_hits - plays_hits
    discrepancies.append(_Discrepancy(
        game_id=game_id,
        perspective_team_id=perspective_team_id,
        team_id=team_id,
        player_id=GAME_LEVEL_PLAYER_ID,
        signal_name="game_hits",
        category="game_level",
        boxscore_value=box_hits,
        plays_value=plays_hits,
        delta=hits_delta,
        status="MATCH" if hits_delta == 0 else "AMBIGUOUS",
    ))


# ---------------------------------------------------------------------------
# Pitcher order extraction from cached boxscore JSON
# ---------------------------------------------------------------------------


def _extract_pitcher_order(
    conn: sqlite3.Connection,
    game_id: str,
    game_stream_id: str | None,
    season_id: str,
    team_id: int,
    is_home: bool,
    perspective_team_id: int | None = None,
) -> list[dict[str, Any]] | None:
    """Extract pitcher appearance order from the player_game_pitching table.

    Reads the ``appearance_order`` column (populated by the game loader from
    boxscore JSON pitcher ordering).  Returns a list of dicts with
    ``player_id`` key in appearance order, or ``None`` if no
    ``appearance_order`` data exists.

    E-220 round 4: replaced the disk-based JSON reading with a DB query.
    The ``appearance_order`` column is stable across perspectives (boxscore
    stat numbers are stable per the provenance rule).

    Args:
        conn: Open SQLite connection.
        game_id: The game to look up.
        game_stream_id: Unused (kept for call-site compatibility).
        season_id: Unused (kept for call-site compatibility).
        team_id: The team whose pitchers to look up.
        is_home: Unused (kept for call-site compatibility).
        perspective_team_id: When provided, filter to this perspective.
            When ``None``, uses team_id as perspective (own perspective).

    Returns:
        List of ``{"player_id": pid}`` dicts ordered by appearance, or
        ``None`` if ``appearance_order`` is not populated for any pitcher.
    """
    ptid = perspective_team_id if perspective_team_id is not None else team_id
    rows = conn.execute(
        "SELECT player_id, appearance_order "
        "FROM player_game_pitching "
        "WHERE game_id = ? AND team_id = ? AND perspective_team_id = ? "
        "ORDER BY appearance_order ASC NULLS LAST, id ASC",
        (game_id, team_id, ptid),
    ).fetchall()

    if not rows:
        return None

    # If all appearance_order values are NULL, return None so the caller
    # falls back to DB insertion order (the pre-E-220 behavior).
    if all(row[1] is None for row in rows):
        logger.debug(
            "No appearance_order data for game_id=%s, team_id=%d; "
            "falling back to DB insertion order.",
            game_id, team_id,
        )
        return None

    return [{"player_id": row[0]} for row in rows]


# ---------------------------------------------------------------------------
# Pitcher attribution correction
# ---------------------------------------------------------------------------


def _correct_pitcher_attribution(
    conn: sqlite3.Connection,
    game_id: str,
    team_id: int,
    pitching_half: str,
    pitching_rows: list[tuple],
    pitcher_order_json: list[dict[str, Any]] | None,
    perspective_team_id: int,
) -> list[dict[str, Any]]:
    """Apply BF-boundary pitcher attribution correction for one team.

    Walks plays in play_order sequence, assigning the first BF[pitcher_1]
    plays to pitcher_1, the next BF[pitcher_2] to pitcher_2, etc.

    Returns a list of correction records, each containing play_order,
    old_pitcher_id, and new_pitcher_id.
    """
    # Build pitcher order with BF counts
    if pitcher_order_json is not None:
        box_pitcher_order = [p["player_id"] for p in pitcher_order_json]
    else:
        box_pitcher_order = [row[0] for row in pitching_rows]

    # Edge case: no boxscore pitching data at all
    if not pitching_rows:
        logger.warning(
            "No boxscore pitching data for game_id=%s, team_id=%d; skipping correction.",
            game_id, team_id,
        )
        return []

    # Build BF map from boxscore DB data (sparse extras already loaded)
    box_bf: dict[str, int] = {}
    for row in pitching_rows:
        box_bf[row[0]] = row[11] or 0  # bf at index 11

    # Edge case: single pitcher per team -- no boundary to correct
    if len(box_pitcher_order) <= 1:
        return []

    # Edge case: pitcher re-entry (duplicate pitcher_id in order)
    if len(set(box_pitcher_order)) != len(box_pitcher_order):
        logger.warning(
            "Pitcher re-entry detected for game_id=%s, team_id=%d: %s. "
            "Skipping correction (AMBIGUOUS).",
            game_id, team_id, box_pitcher_order,
        )
        return []

    # Edge case: total BF from boxscore doesn't match plays count
    total_box_bf = sum(box_bf.get(pid, 0) for pid in box_pitcher_order)
    pitching_plays = conn.execute(
        "SELECT id, play_order, pitcher_id FROM plays "
        "WHERE game_id = ? AND half = ? AND perspective_team_id = ? "
        "ORDER BY play_order",
        (game_id, pitching_half, perspective_team_id),
    ).fetchall()

    if total_box_bf != len(pitching_plays):
        logger.warning(
            "BF total mismatch for game_id=%s, team_id=%d: "
            "boxscore_bf=%d, plays_count=%d. Skipping correction.",
            game_id, team_id, total_box_bf, len(pitching_plays),
        )
        return []

    # Walk plays in order, assign by BF boundaries
    corrections: list[dict[str, Any]] = []
    play_idx = 0
    for pid in box_pitcher_order:
        bf_count = box_bf.get(pid, 0)
        for _ in range(bf_count):
            if play_idx >= len(pitching_plays):
                break
            play_id, play_order, current_pitcher = pitching_plays[play_idx]
            if current_pitcher != pid:
                conn.execute(
                    "UPDATE plays SET pitcher_id = ? WHERE id = ?",
                    (pid, play_id),
                )
                corrections.append({
                    "play_order": play_order,
                    "old_pitcher_id": current_pitcher,
                    "new_pitcher_id": pid,
                })
            play_idx += 1

    if corrections:
        conn.commit()
        logger.info(
            "Corrected %d play(s) for game_id=%s, team_id=%d.",
            len(corrections), game_id, team_id,
        )

    return corrections


# ---------------------------------------------------------------------------
# Summary from DB (for --summary flag)
# ---------------------------------------------------------------------------


def get_summary_from_db(conn: sqlite3.Connection) -> dict[str, Any]:
    """Build aggregate statistics from reconciliation_discrepancies records.

    Deduplicates on ``(game_id, team_id, player_id, signal_name)`` so each
    discrepancy signal is counted once per reconciliation run family.  When
    multiple rows exist for the same composite key with different statuses
    (e.g., CORRECTABLE in run 1, CORRECTED in run 2), the most recent row
    wins (``created_at DESC, rowid DESC``).

    **Cross-perspective limitation**: ``player_id`` is perspective-specific
    (the same human gets different UUIDs from different perspectives — see
    ``data-model.md:30``).  Cross-perspective rows for the same real-world
    signal will have different ``player_id`` values and are NOT collapsed by
    this dedup.  Full cross-perspective dedup requires ``bb data dedup-players``
    to have merged the perspective-specific stubs first.  This is acceptable
    because the summary is a diagnostic tool and the standard pipeline runs
    dedup-players before summary inspection.

    Returns a dict with per-signal match rates, correction counts, and gaps.
    """
    rows = conn.execute(
        "SELECT signal_name, category, status, COUNT(*) "
        "FROM ("
        "  SELECT *, ROW_NUMBER() OVER ("
        "    PARTITION BY game_id, team_id, player_id, signal_name "
        "    ORDER BY created_at DESC, rowid DESC"
        "  ) AS rn "
        "  FROM reconciliation_discrepancies"
        ") "
        "WHERE rn = 1 "
        "GROUP BY signal_name, category, status "
        "ORDER BY category, signal_name, status"
    ).fetchall()

    result: dict[str, Any] = {
        "pitcher_signals": {},
        "batter_signals": {},
        "game_signals": {},
        "total_records": 0,
        "total_corrected": 0,
    }

    for signal_name, category, status, count in rows:
        result["total_records"] += count
        if status == "CORRECTED":
            result["total_corrected"] += count

        if category == "pitcher":
            bucket = result["pitcher_signals"]
        elif category == "batter":
            bucket = result["batter_signals"]
        else:
            bucket = result["game_signals"]

        sig_counts = bucket.setdefault(signal_name, {})
        sig_counts[status] = sig_counts.get(status, 0) + count

    return result


# ---------------------------------------------------------------------------
# Write discrepancy rows
# ---------------------------------------------------------------------------


def _write_discrepancies(
    conn: sqlite3.Connection,
    run_id: str,
    discrepancies: list[_Discrepancy],
) -> None:
    """Write discrepancy rows to the reconciliation_discrepancies table.

    E-220 round 7 P1-2: writes both ``perspective_team_id`` (the API-source
    team) and ``team_id`` (the participant team) so cross-perspective
    discrepancies for the same game persist independently.
    """
    for d in discrepancies:
        conn.execute(
            "INSERT OR REPLACE INTO reconciliation_discrepancies "
            "(run_id, game_id, perspective_team_id, team_id, player_id, "
            "signal_name, category, boxscore_value, plays_value, delta, "
            "status, correction_detail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id, d.game_id, d.perspective_team_id, d.team_id,
                d.player_id, d.signal_name, d.category,
                d.boxscore_value, d.plays_value, d.delta,
                d.status, d.correction_detail,
            ),
        )
    conn.commit()
