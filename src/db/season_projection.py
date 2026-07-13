"""Shared season-aggregate SUM projection.

Since the E-259 query-time cutover this module no longer WRITES the
``player_season_batting`` / ``player_season_pitching`` tables (E-259-02 retired
every season-aggregate writer; E-259-03 drops the tables). What survives is the
single shared SUM *projection* over the
per-game event tables (``player_game_batting`` / ``player_game_pitching``):
``batting_recompute_select()`` / ``pitching_recompute_select()`` and the
positional key tuples they describe.

``src.api.db.get_season_batting`` / ``get_season_pitching`` (the query-time
season readers, E-259-01) wrap this projection as a subquery to derive the
season line at read time. Keeping the projection in ONE place means the SUM
column list cannot drift between consumers.

Design properties carried by the projection:

* **Perspective-scoped by the caller**: the builders return the
  ``SELECT ... FROM ... JOIN games`` body only; each caller appends its own
  ``WHERE ... GROUP BY player_id`` scope (the readers apply
  ``perspective_team_id = team_id`` -- the perspective filter the stored rows
  once carried implicitly).
* **NULL-safe ``gs``**: pitching carries the ``gs`` CASE over
  ``appearance_order`` (NULL when every game row's order is NULL).
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Shared season-aggregate SUM projection (E-246-04 / H1)
# ---------------------------------------------------------------------------
# The SUM column list is declared exactly ONCE per table here, so the query-time
# readers (``src.api.db.get_season_batting`` / ``get_season_pitching``) that wrap
# this projection cannot drift from it. Post-E-259 the reader is the projection's
# consumer; each caller composes its own ``WHERE ... GROUP BY`` scope (the
# perspective filter + season scope) around the shared ``SELECT ... FROM ... JOIN``
# body the builders return.

# Batting SUM subset (16 cols).
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

# Pitching SUM subset (14 cols, through the NULL-safe ``gs`` CASE).
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

_PITCHING_FROM = """
FROM player_game_pitching pgp
JOIN games g ON pgp.game_id = g.game_id"""

# Positional result keys describing the projection's column order. Kept adjacent
# to the projection they describe so a column added to the shared SELECT updates
# these keys in lock-step.
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

    The result is the SUM subset (the columns in
    :data:`BATTING_RECOMPUTE_KEYS`, in that order).  Callers append their own
    ``WHERE ... GROUP BY pgb.player_id`` scope.  The query-time season reader
    (``src.api.db.get_season_batting``) wraps this as a subquery, so the SUM
    column list has a single source.
    """
    return _BATTING_SUM_SELECT + _BATTING_FROM


def pitching_recompute_select() -> str:
    """Return the shared pitching ``SELECT ... FROM ... JOIN`` SUM projection.

    The result is the SUM subset (the columns in
    :data:`PITCHING_RECOMPUTE_KEYS`, in that order), including the NULL-safe
    ``gs`` CASE.  Callers append their own ``WHERE ... GROUP BY pgp.player_id``
    scope.  The query-time season reader (``src.api.db.get_season_pitching``)
    wraps this as a subquery, so the SUM column list has a single source.
    """
    return _PITCHING_SUM_SELECT + _PITCHING_FROM
