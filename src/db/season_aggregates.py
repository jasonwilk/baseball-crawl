"""Canonical boxscore_only season-aggregate recompute (E-237-03).

This module owns the ONE canonical recompute that rebuilds
``player_season_batting`` and ``player_season_pitching`` aggregate rows from
the per-game event tables (``player_game_batting`` / ``player_game_pitching``).

Before E-237-03 two divergent recomputes coexisted:

* ``ScoutingLoader._compute_*_aggregates`` -- ON CONFLICT DO UPDATE of a
  16-batting / 14-pitching (incl. ``gs``) column subset.
* ``player_dedup.recompute_season_*`` -- DELETE+INSERT that additionally wrote
  the dedup-derived extras (batting ``pa``/``singles``/``xbh``; pitching
  ``w``/``l``/``sv``) but OMITTED ``gs``.

Whether a player ended up with a *hybrid* row depended on whether a dedup
merge had touched it -- non-deterministic column population for the same
per-game rows.  This module collapses both writers into a single
perspective-scoped recompute writing the **Option B superset** (the union of
both writers' columns), so every ``boxscore_only`` player -- merged or not --
gets the same deterministic full column set.

Design properties (epic Technical Notes TN-4 / TN-5 / TN-11):

* **Perspective-scoped**: filters ``perspective_team_id = team_id``, joins
  ``games`` on ``season_id``, ``GROUP BY player_id`` -- identical aggregation
  semantics to the prior ScoutingLoader queries.
* **Scope = (team_id, season_id)**: DELETE all ``boxscore_only`` rows for the
  team+season, then INSERT every player.  DELETE-then-INSERT (not partial
  ON CONFLICT) guarantees no stale column survives from a prior writer.
* **Provenance guard**: only ``boxscore_only`` rows are ever deleted or
  written.  ``full`` and ``supplemented`` rows (member-owned, authoritative)
  are never touched -- and players that already own a ``full``/``supplemented``
  row for the scope are excluded from the INSERT so the member row survives
  intact (fixes the latent dedup data-loss bug, TN-4 / AC-8).
* **Superset column contract** (TN-5): the parity-checked subset equals the
  prior ScoutingLoader set exactly (so ``aggregate_parity`` and the seeded
  fixture are unchanged); the dedup-derived extras are populated for every
  player.

The function takes a ``sqlite3.Connection`` and does NOT commit -- the caller
owns the transaction/commit boundary (ScoutingLoader commits it together with
the dedup sweep; the dedup CLI/Hook-2 callers manage their own transactions).
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)


# Member-provenance rows are authoritative; the canonical recompute never
# touches them and never re-creates a boxscore_only row for a player that
# already owns one of these for the scope.
_MEMBER_PROVENANCE = ("full", "supplemented")


# ---------------------------------------------------------------------------
# Shared season-aggregate SUM projection (E-246-04 / H1)
# ---------------------------------------------------------------------------
# The parity-checked SUM column list is declared exactly ONCE per table here.
# Both consumers build their recompute SELECT from these constants/builders:
#
#   * canonical_recompute (this module) -- the protected boxscore_only recompute.
#     It appends its own member-provenance ``NOT EXISTS`` WHERE guard + GROUP BY,
#     and (pitching only) the non-parity decision-derived ``w``/``l``/``sv``
#     extras (see ``include_decision_extras``).
#   * src/reports/aggregate_parity.py -- the verify-aggregates parity check. It
#     appends only its own WHERE scope + GROUP BY around the same projection.
#
# Because the SUM list lives in ONE place, a parity-checked column added here
# flows to BOTH paths with no second edit site -- closing the H1 silent-drift
# hazard where the parity copy could sum a STALE subset and report false parity.
# The builders return the shared ``SELECT ... FROM ... JOIN`` body only; each
# caller composes its own ``WHERE ... GROUP BY`` scope around it.

# Batting parity-checked SUM subset (16 cols).  The canonical recompute's
# superset extras (pa/singles/xbh) are derived in Python AFTER the fetch, not in
# this projection, so this SELECT is identical for both consumers.
_BATTING_SUM_SELECT = """\
SELECT
    pgb.player_id,
    COUNT(*)         AS games_tracked,
    SUM(pgb.ab)      AS ab,
    SUM(pgb.h)       AS h,
    SUM(pgb.doubles) AS doubles,
    SUM(pgb.triples) AS triples,
    SUM(pgb.hr)      AS hr,
    SUM(pgb.rbi)     AS rbi,
    SUM(pgb.r)       AS r,
    SUM(pgb.bb)      AS bb,
    SUM(pgb.so)      AS so,
    SUM(pgb.sb)      AS sb,
    SUM(pgb.tb)      AS tb,
    SUM(pgb.hbp)     AS hbp,
    SUM(pgb.shf)     AS shf,
    SUM(pgb.cs)      AS cs"""

_BATTING_FROM = """
FROM player_game_batting pgb
JOIN games g ON pgb.game_id = g.game_id"""

# Pitching parity-checked SUM subset (14 cols, through the NULL-safe ``gs``
# CASE).  The canonical-recompute-only decision extras are appended SEPARATELY
# (they sit between ``gs`` and ``FROM`` in the SELECT list).
_PITCHING_SUM_SELECT = """\
SELECT
    pgp.player_id,
    COUNT(*)               AS games_tracked,
    SUM(pgp.ip_outs)       AS ip_outs,
    SUM(pgp.h)             AS h,
    SUM(pgp.r)             AS r,
    SUM(pgp.er)            AS er,
    SUM(pgp.bb)            AS bb,
    SUM(pgp.so)            AS so,
    SUM(pgp.wp)            AS wp,
    SUM(pgp.hbp)           AS hbp,
    SUM(pgp.pitches)       AS pitches,
    SUM(pgp.total_strikes) AS total_strikes,
    SUM(pgp.bf)            AS bf,
    CASE WHEN MAX(pgp.appearance_order) IS NULL THEN NULL
         ELSE SUM(CASE WHEN pgp.appearance_order = 1 THEN 1 ELSE 0 END)
    END AS gs"""

# canonical_recompute-only superset extras (NOT parity-checked): per-game
# decision-derived win/loss/save counts, appended to the SELECT list before
# ``FROM``.  The parity check never includes these (they are renderer-derived,
# not summed-stat parity columns).
_PITCHING_DECISION_EXTRAS = """,
    SUM(CASE WHEN pgp.decision = 'W' THEN 1 ELSE 0 END)  AS w,
    SUM(CASE WHEN pgp.decision = 'L' THEN 1 ELSE 0 END)  AS l,
    SUM(CASE WHEN pgp.decision = 'SV' THEN 1 ELSE 0 END) AS sv"""

_PITCHING_FROM = """
FROM player_game_pitching pgp
JOIN games g ON pgp.game_id = g.game_id"""

# Positional result keys for the parity check's row unpacking -- the
# parity-checked subset only (the canonical-only w/l/sv extras are intentionally
# absent).  Kept adjacent to the projection they describe so a column added to
# the shared SELECT updates these keys in lock-step.
BATTING_RECOMPUTE_KEYS = (
    "player_id", "games_tracked", "ab", "h", "doubles", "triples", "hr",
    "rbi", "r", "bb", "so", "sb", "tb", "hbp", "shf", "cs",
)
PITCHING_RECOMPUTE_KEYS = (
    "player_id", "games_tracked", "ip_outs", "h", "r", "er", "bb", "so",
    "wp", "hbp", "pitches", "total_strikes", "bf", "gs",
)


def batting_recompute_select() -> str:
    """Return the shared batting ``SELECT ... FROM ... JOIN`` SUM projection.

    The result is the parity-checked SUM subset (the columns in
    :data:`BATTING_RECOMPUTE_KEYS`, in that order).  Callers append their own
    ``WHERE ... GROUP BY pgb.player_id`` scope.  Both ``canonical_recompute``
    and ``src/reports/aggregate_parity.py`` consume this so the SUM column list
    cannot drift between the two paths.
    """
    return _BATTING_SUM_SELECT + _BATTING_FROM


def pitching_recompute_select(*, include_decision_extras: bool) -> str:
    """Return the shared pitching ``SELECT ... FROM ... JOIN`` SUM projection.

    The base result is the parity-checked SUM subset (the columns in
    :data:`PITCHING_RECOMPUTE_KEYS`, in that order).  When
    ``include_decision_extras`` is True the canonical-recompute-only
    ``w``/``l``/``sv`` columns are appended (between ``gs`` and ``FROM``); the
    parity check passes ``False``.  Callers append their own
    ``WHERE ... GROUP BY pgp.player_id`` scope.
    """
    extras = _PITCHING_DECISION_EXTRAS if include_decision_extras else ""
    return _PITCHING_SUM_SELECT + extras + _PITCHING_FROM


def canonical_recompute(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
) -> None:
    """Recompute ``boxscore_only`` season aggregates for one (team, season).

    Rebuilds ``player_season_batting`` and ``player_season_pitching`` rows for
    the scope from the per-game event tables, writing the Option B superset.
    Does NOT commit -- the caller owns the transaction boundary.

    Args:
        conn: Open ``sqlite3.Connection`` (caller manages the transaction).
        team_id: INTEGER PK of the team to recompute.
        season_id: Season slug (text) to scope the recompute.
    """
    n_batting = _recompute_batting(conn, team_id, season_id)
    n_pitching = _recompute_pitching(conn, team_id, season_id)
    logger.info(
        "Canonical season recompute: %d batting, %d pitching boxscore_only "
        "row(s) for team=%d season=%s.",
        n_batting, n_pitching, team_id, season_id,
    )


def _recompute_batting(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
) -> int:
    """DELETE+INSERT the boxscore_only batting aggregate rows for the scope.

    The parity-checked subset (gp, games_tracked, ab, h, doubles, triples, hr,
    rbi, r, bb, so, sb, tb, hbp, shf, cs) is stored as the raw ``SUM`` (NULL
    preserved when every game value is NULL).  The superset extras
    (pa, singles, xbh) are computed NULL-safe (NULL treated as 0).
    """
    # Provenance guard: never delete full/supplemented rows.
    conn.execute(
        "DELETE FROM player_season_batting "
        "WHERE team_id = ? AND season_id = ? AND stat_completeness = 'boxscore_only'",
        (team_id, season_id),
    )

    # Shared SUM projection (single source); this recompute adds its own
    # member-provenance guard + GROUP BY scope around it.
    rows = conn.execute(
        batting_recompute_select() + """
        WHERE pgb.team_id = ? AND g.season_id = ?
          AND pgb.perspective_team_id = ?
          AND NOT EXISTS (
              SELECT 1 FROM player_season_batting m
              WHERE m.player_id = pgb.player_id
                AND m.team_id = ?
                AND m.season_id = ?
                AND m.stat_completeness IN ('full', 'supplemented')
          )
        GROUP BY pgb.player_id
        """,
        (team_id, season_id, team_id, team_id, season_id),
    ).fetchall()

    for (player_id, games_tracked,
         ab, h, doubles, triples, hr, rbi, r, bb, so, sb,
         tb, hbp, shf, cs) in rows:
        # Superset extras (NULL-safe; NULL summands treated as 0).
        pa = (ab or 0) + (bb or 0) + (hbp or 0) + (shf or 0)
        singles = (h or 0) - (doubles or 0) - (triples or 0) - (hr or 0)
        xbh = (doubles or 0) + (triples or 0) + (hr or 0)
        conn.execute(
            """
            INSERT INTO player_season_batting
                (player_id, team_id, season_id, stat_completeness,
                 gp, games_tracked, pa, ab, h, singles, doubles, triples, hr,
                 rbi, r, bb, so, sb, tb, hbp, shf, cs, xbh)
            VALUES (?, ?, ?, 'boxscore_only',
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (player_id, team_id, season_id,
             games_tracked, games_tracked, pa, ab, h, singles, doubles,
             triples, hr, rbi, r, bb, so, sb, tb, hbp, shf, cs, xbh),
        )
    return len(rows)


def _recompute_pitching(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
) -> int:
    """DELETE+INSERT the boxscore_only pitching aggregate rows for the scope.

    The parity-checked subset (gp_pitcher, games_tracked, ip_outs, h, r, er,
    bb, so, wp, hbp, pitches, total_strikes, bf, gs) is stored as the raw
    ``SUM`` (NULL preserved) -- except ``gs``, which uses the NULL-safe CASE on
    ``appearance_order`` (NULL when every game row's appearance_order is NULL,
    i.e. pre-backfill).  The superset extras (w, l, sv) are derived from the
    per-game ``decision`` field and are never NULL (``SUM(CASE...)`` >= 0).
    Pitching ``hr`` is deliberately NOT written (no HR-allowed in boxscore
    pitching).
    """
    conn.execute(
        "DELETE FROM player_season_pitching "
        "WHERE team_id = ? AND season_id = ? AND stat_completeness = 'boxscore_only'",
        (team_id, season_id),
    )

    # Shared SUM projection (single source) plus the canonical-only w/l/sv
    # decision extras; this recompute adds its own member-provenance guard +
    # GROUP BY scope around it.
    rows = conn.execute(
        pitching_recompute_select(include_decision_extras=True) + """
        WHERE pgp.team_id = ? AND g.season_id = ?
          AND pgp.perspective_team_id = ?
          AND NOT EXISTS (
              SELECT 1 FROM player_season_pitching m
              WHERE m.player_id = pgp.player_id
                AND m.team_id = ?
                AND m.season_id = ?
                AND m.stat_completeness IN ('full', 'supplemented')
          )
        GROUP BY pgp.player_id
        """,
        (team_id, season_id, team_id, team_id, season_id),
    ).fetchall()

    for (player_id, games_tracked,
         ip_outs, h, r, er, bb, so,
         wp, hbp, pitches, total_strikes, bf, gs, w, l, sv) in rows:
        conn.execute(
            """
            INSERT INTO player_season_pitching
                (player_id, team_id, season_id, stat_completeness,
                 gp_pitcher, games_tracked, ip_outs, h, r, er, bb, so,
                 wp, hbp, pitches, total_strikes, bf, gs, w, l, sv)
            VALUES (?, ?, ?, 'boxscore_only',
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (player_id, team_id, season_id,
             games_tracked, games_tracked, ip_outs, h, r, er, bb, so,
             wp, hbp, pitches, total_strikes, bf, gs, w, l, sv),
        )
    return len(rows)
