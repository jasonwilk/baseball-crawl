"""Per-pitcher per-appearance outings derivation (E-265-01).

For a scouted opponent this module produces, per pitcher, a season summary line
plus a chronological list of per-appearance outings.  It follows the project's
established read-and-derive pattern (``starter_prediction.py`` /
``recon_scoreboard.py``): a connection-in / dataclass-out core that writes
nothing to the DB.  The renderer (E-265-02) consumes the returned dataclasses.

All stats derive from already-stored per-game boxscores
(``player_game_pitching``) and plays (``plays``); the opponent's season-stats
endpoint is 403, so nothing here re-fetches the API.

Two data sources feed each outing:

* **Boxscore-direct** (``get_pitching_history``): IP (``ip_outs``), BF, H, BB,
  K (``so``), R, ER -- already perspective-filtered
  (``team_id = perspective_team_id = scouted``) and scoped to completed games.
* **Plays-derived** (this module): HR-allowed (``plays.outcome = 'Home Run'``)
  and FPS% (``is_first_pitch_strike`` over the charted-PA denominator
  ``pitch_count > 0``).  The plays aggregation is driven OFF the boxscore
  outings (TN-6, F12) and carries the load-bearing role clause
  ``batting_team_id != scouted`` so a game loaded from two perspectives yields
  exactly one set of outings (no double-count).

ERA basis: E-264's ``teams.innings_per_game`` (fallback 7 via
:func:`src.api.helpers.era_basis_innings`).  E-264 exposes no reusable accessor
and does NOT thread the basis onto ``get_pitching_history``, so this module owns
its own scalar read of the column (TN-5, F1).  It does not touch E-264's two
season-ERA sites.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass

from src.api.db import get_pitching_history
from src.api.helpers import era_basis_innings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The single canonical HR outcome value GameChanger emits on ``plays.outcome``
# (mirrors ``recon_scoreboard.HIT_OUTCOMES`` / ``plays_parser._XBH_OUTCOMES``).
# No grand-slam / inside-the-park variants exist in the plays vocabulary.
_HR_OUTCOMES = frozenset({"Home Run"})

# Small-sample caveat: flag the four season rate stats below 15 IP (45 outs).
_SMALL_SAMPLE_IP_OUTS = 45
# K/BB additionally badges its underlying BB count below this walk total.
_LOW_BB_THRESHOLD = 5

# Green "strong-outing" thresholds (TN-4).  A row is GREEN iff it meets ANY ONE.
_GREEN_COMMAND_IP_OUTS = 9        # (1) Command: BB=0 across IP >= 3 (9 outs)
_GREEN_AGGRESSION_FPS = 0.65      # (2) Aggression: FPS% >= 65% ...
_GREEN_AGGRESSION_CHARTED_PA = 10  #     ... across charted-PA count >= 10
_GREEN_DOMINANCE_RATIO = 2 / 3    # (3) Dominance: per-outing K/BF >= 2/3 ...
_GREEN_DOMINANCE_BF = 10          #     ... across BF >= 10
_GREEN_SHUTDOWN_IP_OUTS = 12      # (4) Shutdown: R=0 across IP >= 4 (12 outs)


def is_pitcher_outings_enabled() -> bool:
    """Return True when the ``FEATURE_PITCHER_OUTINGS`` env var is enabled.

    Mirrors :func:`src.reports.starter_prediction.is_predicted_starter_enabled`
    exactly (same ``.lower() in (...)`` shape).  Off by default.
    """
    return os.environ.get("FEATURE_PITCHER_OUTINGS", "").lower() in (
        "1", "true", "yes",
    )


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Outing:
    """One pitching appearance (TN-2).

    Boxscore fields may be ``None`` when the boxscore omitted them.  Rate fields
    (``fps_pct``, ``era``) are ``None`` when their denominator is absent/zero --
    never 0, never a divide-by-zero (TN-6).
    """

    game_id: str
    game_date: str | None
    opponent: str | None
    ip_outs: int | None
    bf: int | None
    h: int | None
    hr_allowed: int
    bb: int | None
    so: int | None
    r: int | None
    fps_pct: float | None
    charted_pa: int
    era: float | None
    appearance_order: int | None
    is_strong: bool


@dataclass(frozen=True)
class SeasonSummary:
    """Per-pitcher season summary line (TN-3).

    Carries the standard context set (IP via ``ip_outs``, G, GS, ERA, WHIP,
    FPS%) plus the rate set K/BF, BB/INN, K/BB, H/BF.  Every rate is ``None``
    when its denominator is zero.  ``zero_bb`` distinguishes the zero-walk
    command-strength case (``k_per_bb`` is ``None`` but ``zero_bb`` is True) from
    the genuine no-data case (``k_per_bb`` ``None`` and ``zero_bb`` False), so
    the renderer can present it as a strength rather than a blank (F11).

    ``games_started`` is ``None`` (unknown, renders "—") when EVERY appearance
    in the scope has a NULL ``appearance_order`` -- mirroring
    ``get_season_pitching``'s ``CASE WHEN MAX(appearance_order) IS NULL THEN
    NULL`` semantics, so the Outings line never claims "0 GS" (pure reliever)
    where the Pitching season line honestly shows unknown.
    """

    ip_outs: int
    games: int
    games_started: int | None
    er: int
    so: int
    bb: int
    h: int
    bf: int
    era: float | None
    whip: float | None
    fps_pct: float | None
    k_per_bf: float | None
    bb_per_inn: float | None
    k_per_bb: float | None
    h_per_bf: float | None
    small_sample: bool
    low_bb: bool
    zero_bb: bool


@dataclass(frozen=True)
class PitcherOutings:
    """A scouted pitcher's season summary plus chronological outings."""

    player_id: str
    name: str
    jersey_number: str | None
    season: SeasonSummary
    outings: list[Outing]


# ---------------------------------------------------------------------------
# DB reads (this module owns its own reads; keeps writes out entirely)
# ---------------------------------------------------------------------------


def _scouted_era_basis(conn: sqlite3.Connection, team_id: int) -> int:
    """Return the scouted team's ERA basis (``teams.innings_per_game``, fb 7).

    E-264 threads ``innings_per_game`` onto ``get_season_pitching`` only, not
    onto ``get_pitching_history`` (F1), and ships no reusable accessor -- so this
    module reads the column directly and re-applies the shared ``is not None``
    fallback via :func:`era_basis_innings`.  Does NOT re-fetch from the API and
    does NOT touch E-264's two season-ERA sites (TN-5).
    """
    row = conn.execute(
        "SELECT innings_per_game FROM teams WHERE id = ?", (team_id,)
    ).fetchone()
    raw = row[0] if row is not None else None
    return era_basis_innings(raw)


def _opponent_name_by_game(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> dict[str, str | None]:
    """Map each completed game_id to the opposing team's name.

    The opponent is whichever side of the game is not the scouted team.
    """
    rows = conn.execute(
        """
        SELECT
            g.game_id,
            CASE WHEN g.home_team_id = :team_id THEN t_away.name
                 ELSE t_home.name END AS opponent
        FROM games g
        LEFT JOIN teams t_home ON t_home.id = g.home_team_id
        LEFT JOIN teams t_away ON t_away.id = g.away_team_id
        WHERE g.season_id = :season_id
          AND g.status = 'completed'
          AND (g.home_team_id = :team_id OR g.away_team_id = :team_id)
        """,
        {"team_id": team_id, "season_id": season_id},
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def _plays_by_pitcher_game(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> dict[tuple[str, str], dict]:
    """Aggregate plays-derived stats per ``(pitcher_id, game_id)`` (TN-6).

    Scoped with the load-bearing role/perspective filter:
    ``perspective_team_id = scouted`` (dedup across perspectives) AND
    ``batting_team_id != scouted`` (ROLE: the scouted team is fielding/pitching)
    AND ``pitcher_id IS NOT NULL``, over the scouted team's completed games.

    This is a NEW per-``(pitcher, game)`` query -- NOT
    ``_query_plays_pitching_stats`` (which lacks the ``batting_team_id`` role
    clause and groups by pitcher only, F7).  FPS% reuses the charted-PA
    ``pitch_count > 0`` denominator CONVENTION.

    Returns a dict keyed by ``(pitcher_id, game_id)`` with ``hr_allowed``,
    ``fps_sum``, and ``charted_pa``.  The caller left-joins this onto the
    boxscore outings.
    """
    hr_placeholders = ",".join("?" for _ in _HR_OUTCOMES)
    rows = conn.execute(
        f"""
        SELECT
            p.pitcher_id,
            p.game_id,
            SUM(CASE WHEN p.outcome IN ({hr_placeholders}) THEN 1 ELSE 0 END)
                AS hr_allowed,
            SUM(p.is_first_pitch_strike) AS fps_sum,
            SUM(CASE WHEN p.pitch_count > 0 THEN 1 ELSE 0 END) AS charted_pa
        FROM plays p
        JOIN games g ON g.game_id = p.game_id
        WHERE g.season_id = ?
          AND g.status = 'completed'
          AND p.perspective_team_id = ?
          AND p.batting_team_id != ?
          AND p.pitcher_id IS NOT NULL
        GROUP BY p.pitcher_id, p.game_id
        """,
        [*_HR_OUTCOMES, season_id, team_id, team_id],
    ).fetchall()
    return {
        (r[0], r[1]): {
            "hr_allowed": r[2] or 0,
            "fps_sum": r[3] or 0,
            "charted_pa": r[4] or 0,
        }
        for r in rows
    }


# ---------------------------------------------------------------------------
# Derivation helpers
# ---------------------------------------------------------------------------


def _rate(numerator: int | None, denominator: int | None) -> float | None:
    """Return ``numerator / denominator`` or ``None`` when the denominator is
    absent or zero (TN-6: never 0, never divide-by-zero)."""
    if not denominator:
        return None
    return (numerator or 0) / denominator


def _per_outing_era(er: int | None, ip_outs: int | None, basis: int) -> float | None:
    """Per-outing ERA = ``ER * (basis * 3) / ip_outs`` (TN-5).

    Returns ``None`` when ``ip_outs`` is absent or zero -- never a
    divide-by-zero.  The 9-inning ``* 27`` constant is deliberately NOT used;
    the basis comes from the scouted team's ``innings_per_game``.
    """
    if not ip_outs:
        return None
    return (er or 0) * (basis * 3) / ip_outs


def _is_strong_outing(
    *,
    bb: int | None,
    ip_outs: int | None,
    fps_pct: float | None,
    charted_pa: int,
    so: int | None,
    bf: int | None,
    r: int | None,
) -> bool:
    """Return True when an outing meets ANY ONE green criterion (TN-4).

    Each criterion's own gate already clears the defensive sample floor
    (``BF < 10 AND IP < 2``), so no separate floor suppression is applied -- a
    post-floor check keyed on boxscore BF could contradict criterion (2), which
    gates on the charted-PA count instead (AC-5, F2/F8).  A sub-floor outing
    meets no criterion and is unflagged.
    """
    # (1) Command: BB = 0 across IP >= 3.
    if bb == 0 and ip_outs is not None and ip_outs >= _GREEN_COMMAND_IP_OUTS:
        return True
    # (2) Aggression: FPS% >= 65% across a charted-PA count >= 10 (NOT raw BF).
    if (
        fps_pct is not None
        and fps_pct >= _GREEN_AGGRESSION_FPS
        and charted_pa >= _GREEN_AGGRESSION_CHARTED_PA
    ):
        return True
    # (3) Dominance: per-outing K/BF >= 2/3 across BF >= 10.
    if (
        bf is not None
        and bf >= _GREEN_DOMINANCE_BF
        and so is not None
        and so / bf >= _GREEN_DOMINANCE_RATIO
    ):
        return True
    # (4) Shutdown: R = 0 (raw runs, NOT ER) across IP >= 4.
    if r == 0 and ip_outs is not None and ip_outs >= _GREEN_SHUTDOWN_IP_OUTS:
        return True
    return False


@dataclass
class _SeasonTotals:
    """Mutable per-pitcher accumulator for the season summary aggregation."""

    ip_outs: int = 0
    er: int = 0
    so: int = 0
    bb: int = 0
    h: int = 0
    bf: int = 0
    fps_sum: int = 0
    charted_pa: int = 0
    games: int = 0
    games_started: int = 0
    # True once ANY appearance in the scope carries a non-NULL appearance_order.
    # When it stays False (every row NULL), GS is reported as None (unknown),
    # mirroring get_season_pitching's MAX(appearance_order) IS NULL -> NULL.
    has_appearance_order: bool = False


def _build_season_summary(totals: _SeasonTotals, *, basis: int) -> SeasonSummary:
    """Aggregate a pitcher's accumulated totals into the season line (TN-3)."""
    ip_outs = totals.ip_outs
    bb = totals.bb
    h = totals.h
    bf = totals.bf
    so = totals.so

    era = _per_outing_era(totals.er, ip_outs, basis)
    whip = (bb + h) * 3 / ip_outs if ip_outs else None
    fps_pct = _rate(totals.fps_sum, totals.charted_pa)
    k_per_bf = _rate(so, bf)
    # BB/INN uses innings = ip_outs / 3, so BB/INN = bb * 3 / ip_outs.
    bb_per_inn = (bb * 3 / ip_outs) if ip_outs else None
    h_per_bf = _rate(h, bf)
    # K/BB: None when BB = 0.  ``zero_bb`` distinguishes the zero-walk command
    # strength from the genuine no-data case (F11): a real zero-walk performance
    # requires having FACED batters (``bf > 0``), so an empty line (ip_outs=0,
    # bf=0/NULL, bb=0/NULL) falls through to no-data (``zero_bb=False``) rather
    # than masquerading as command strength.  Both leave ``k_per_bb`` None; the
    # flag is what tells them apart.
    k_per_bb = _rate(so, bb)
    zero_bb = bf > 0 and bb == 0

    # GS is None (unknown) when NO appearance in the scope had a non-NULL
    # appearance_order -- else the count of starts. Mirrors the season-stats
    # surface so the two lines never disagree ("—" vs a false "0 GS").
    games_started = totals.games_started if totals.has_appearance_order else None

    return SeasonSummary(
        ip_outs=ip_outs,
        games=totals.games,
        games_started=games_started,
        er=totals.er,
        so=so,
        bb=bb,
        h=h,
        bf=bf,
        era=era,
        whip=whip,
        fps_pct=fps_pct,
        k_per_bf=k_per_bf,
        bb_per_inn=bb_per_inn,
        k_per_bb=k_per_bb,
        h_per_bf=h_per_bf,
        small_sample=ip_outs < _SMALL_SAMPLE_IP_OUTS,
        low_bb=bb < _LOW_BB_THRESHOLD,
        zero_bb=zero_bb,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_pitcher_outings(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> list[PitcherOutings]:
    """Return one :class:`PitcherOutings` per pitcher for the scouted team.

    Drives the plays aggregation OFF the boxscore outings returned by
    ``get_pitching_history`` (TN-6, F12): each outing's plays values come from a
    left-join into :func:`_plays_by_pitcher_game` keyed on
    ``(player_id, game_id)``.  Writes nothing to the DB.

    Args:
        conn: Open SQLite connection.
        team_id: INTEGER PK of the SCOUTED team.
        season_id: Season slug to scope the query.

    Returns:
        A list of :class:`PitcherOutings`, one per pitcher, ordered by season
        IP descending (matching the main Pitching table's sort; spec §4).  Each
        pitcher's ``outings`` list is chronological.
    """
    history = get_pitching_history(team_id, season_id, db=conn)
    basis = _scouted_era_basis(conn, team_id)
    opponents = _opponent_name_by_game(conn, team_id, season_id)
    plays = _plays_by_pitcher_game(conn, team_id, season_id)

    # Group appearances per pitcher, preserving chronological order and
    # first-seen pitcher order.
    grouped: dict[str, list[dict]] = {}
    identity: dict[str, dict] = {}
    for row in history:
        pid = row["player_id"]
        if pid not in grouped:
            grouped[pid] = []
            identity[pid] = {
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "jersey_number": row["jersey_number"],
            }
        grouped[pid].append(row)

    result: list[PitcherOutings] = []
    for pid, rows in grouped.items():
        outings: list[Outing] = []
        totals = _SeasonTotals()
        for row in rows:
            game_id = row["game_id"]
            ip_outs = row["ip_outs"]
            bf = row["bf"]
            so = row["so"]
            bb = row["bb"]
            h = row["h"]
            r = row["r"]
            er = row["er"]
            appearance_order = row["appearance_order"]

            pkey = plays.get((pid, game_id), {})
            hr_allowed = pkey.get("hr_allowed", 0)
            fps_sum = pkey.get("fps_sum", 0)
            charted_pa = pkey.get("charted_pa", 0)
            fps_pct = _rate(fps_sum, charted_pa)
            era = _per_outing_era(er, ip_outs, basis)

            is_strong = _is_strong_outing(
                bb=bb,
                ip_outs=ip_outs,
                fps_pct=fps_pct,
                charted_pa=charted_pa,
                so=so,
                bf=bf,
                r=r,
            )

            outings.append(Outing(
                game_id=game_id,
                game_date=row["game_date"],
                opponent=opponents.get(game_id),
                ip_outs=ip_outs,
                bf=bf,
                h=h,
                hr_allowed=hr_allowed,
                bb=bb,
                so=so,
                r=r,
                fps_pct=fps_pct,
                charted_pa=charted_pa,
                era=era,
                appearance_order=appearance_order,
                is_strong=is_strong,
            ))

            # Accumulate season totals from the raw boxscore + plays values
            # (ER and the FPS numerator are not part of the rendered per-outing
            # row, so they are summed here rather than off the Outing).
            totals.ip_outs += ip_outs or 0
            totals.er += er or 0
            totals.so += so or 0
            totals.bb += bb or 0
            totals.h += h or 0
            totals.bf += bf or 0
            totals.fps_sum += fps_sum
            totals.charted_pa += charted_pa
            totals.games += 1
            if appearance_order is not None:
                totals.has_appearance_order = True
            if appearance_order == 1:
                totals.games_started += 1

        season = _build_season_summary(totals, basis=basis)
        ident = identity[pid]
        result.append(
            PitcherOutings(
                player_id=pid,
                name=f"{ident['first_name']} {ident['last_name']}",
                jersey_number=ident["jersey_number"],
                season=season,
                outings=outings,
            )
        )

    # Order per-pitcher blocks by season IP descending, matching the main
    # Pitching table's sort so the two sections read in the same order (spec
    # §4). Stable sort preserves first-appearance order among equal-IP pitchers.
    result.sort(key=lambda p: p.season.ip_outs or 0, reverse=True)
    return result
