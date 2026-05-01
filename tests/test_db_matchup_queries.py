"""Tests for new matchup-section query helpers in src/api/db.py (E-228-12).

Covers (AC-T3 + AC-T4):
- get_top_hitters: filters by team_id, season_id, min_pa; OPS ranking
  correct; tie-breaker on PA works; cross-team contamination guard.
- get_hitter_pitch_tendencies: filters by perspective_team_id;
  cross-perspective contamination guard.
- get_sb_tendency: aggregates SB/CS from boxscore + caught-stealing
  events from plays; opposing perspective filter.
- get_first_inning_pattern: counts 1st-inning runs scored/allowed.

All tests use an in-memory SQLite database created from the production
schema -- no real DB file is read or written.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing

import pytest

from src.api.db import (
    get_first_inning_pattern,
    get_hitter_pitch_tendencies,
    get_players_spray_events_batch,
    get_sb_tendency,
    get_top_hitters,
)
from tests.conftest import load_real_schema


# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    load_real_schema(c)
    c.row_factory = sqlite3.Row
    return c


def _seed_team(c: sqlite3.Connection, name: str, member: bool = False) -> int:
    cur = c.execute(
        "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
        (name, "member" if member else "tracked"),
    )
    c.commit()
    return cur.lastrowid  # type: ignore[return-value]


def _seed_season(c: sqlite3.Connection, season_id: str = "2026-spring-hs") -> str:
    c.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, 'Spring 2026 HS', 'spring-hs', 2026)",
        (season_id,),
    )
    c.commit()
    return season_id


def _seed_player(c: sqlite3.Connection, pid: str, first: str = "F", last: str = "L") -> str:
    c.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, ?, ?)",
        (pid, first, last),
    )
    c.commit()
    return pid


def _seed_roster(
    c: sqlite3.Connection, *, team_id: int, player_id: str, season_id: str,
    jersey: str | None = None,
) -> None:
    c.execute(
        "INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id, jersey_number) "
        "VALUES (?, ?, ?, ?)",
        (team_id, player_id, season_id, jersey),
    )
    c.commit()


def _seed_season_batting(
    c: sqlite3.Connection, *, player_id: str, team_id: int, season_id: str,
    pa: int = 50, ab: int = 40, h: int = 14, doubles: int = 2, triples: int = 0,
    hr: int = 1, bb: int = 6, hbp: int = 1, so: int = 8, sb: int = 0,
) -> None:
    tb = (h - doubles - triples - hr) + 2 * doubles + 3 * triples + 4 * hr
    c.execute(
        "INSERT INTO player_season_batting "
        "(player_id, team_id, season_id, pa, ab, h, doubles, triples, hr, "
        "bb, hbp, so, sb, tb) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (player_id, team_id, season_id, pa, ab, h, doubles, triples, hr,
         bb, hbp, so, sb, tb),
    )
    c.commit()


# ---------------------------------------------------------------------------
# get_top_hitters
# ---------------------------------------------------------------------------


def test_get_top_hitters_filters_by_team_id_and_season_id(conn) -> None:
    season = _seed_season(conn)
    season_b = _seed_season(conn, "2025-spring-hs")
    team_a = _seed_team(conn, "Team A")
    team_b = _seed_team(conn, "Team B")
    _seed_player(conn, "p_a", "Alpha", "A")
    _seed_player(conn, "p_b", "Bravo", "B")
    _seed_player(conn, "p_c", "Charlie", "C")

    _seed_roster(conn, team_id=team_a, player_id="p_a", season_id=season,
                 jersey="1")
    _seed_roster(conn, team_id=team_b, player_id="p_b", season_id=season)
    _seed_roster(conn, team_id=team_a, player_id="p_c", season_id=season_b)

    _seed_season_batting(conn, player_id="p_a", team_id=team_a, season_id=season,
                         pa=50, ab=40, h=14, hr=2, bb=6, hbp=2)
    _seed_season_batting(conn, player_id="p_b", team_id=team_b, season_id=season,
                         pa=50, ab=40, h=20, hr=5, bb=8, hbp=2)
    _seed_season_batting(conn, player_id="p_c", team_id=team_a, season_id=season_b,
                         pa=50, ab=40, h=10)

    rows = get_top_hitters(team_a, season, db=conn)
    pids = [r["player_id"] for r in rows]
    assert pids == ["p_a"]
    assert rows[0]["pa"] == 50

    # Different season for team_a should pick up p_c only.
    rows_b = get_top_hitters(team_a, season_b, db=conn)
    assert [r["player_id"] for r in rows_b] == ["p_c"]


def test_get_top_hitters_min_pa_filter(conn) -> None:
    season = _seed_season(conn)
    team = _seed_team(conn, "Team A")
    _seed_player(conn, "p_low", "Low", "PA")
    _seed_player(conn, "p_ok", "Ok", "PA")
    _seed_roster(conn, team_id=team, player_id="p_low", season_id=season)
    _seed_roster(conn, team_id=team, player_id="p_ok", season_id=season)
    _seed_season_batting(conn, player_id="p_low", team_id=team, season_id=season,
                         pa=5, ab=4, h=2)
    _seed_season_batting(conn, player_id="p_ok", team_id=team, season_id=season,
                         pa=20, ab=18, h=6)

    rows = get_top_hitters(team, season, min_pa=10, db=conn)
    assert [r["player_id"] for r in rows] == ["p_ok"]

    rows_lower = get_top_hitters(team, season, min_pa=1, db=conn)
    assert {r["player_id"] for r in rows_lower} == {"p_low", "p_ok"}


def test_get_top_hitters_ops_ranking_and_pa_tiebreaker(conn) -> None:
    season = _seed_season(conn)
    team = _seed_team(conn, "Team A")
    # All 3 players have similar OBP/SLG -- p_high has the best OPS,
    # tie_a / tie_b have identical OBP+SLG but tie_b has higher PA.
    _seed_player(conn, "p_high", "High", "OPS")
    _seed_player(conn, "tie_a", "Tie", "A")
    _seed_player(conn, "tie_b", "Tie", "B")
    for pid in ("p_high", "tie_a", "tie_b"):
        _seed_roster(conn, team_id=team, player_id=pid, season_id=season)

    # p_high: pa=50, ab=40, h=18 (higher)
    _seed_season_batting(conn, player_id="p_high", team_id=team, season_id=season,
                         pa=50, ab=40, h=18, doubles=0, triples=0, hr=3,
                         bb=8, hbp=2)
    # tie_a: pa=40, ab=32, h=12, hr=2 -- same OPS as tie_b
    _seed_season_batting(conn, player_id="tie_a", team_id=team, season_id=season,
                         pa=40, ab=32, h=12, doubles=0, triples=0, hr=2,
                         bb=6, hbp=2)
    # tie_b: pa=60, ab=48, h=18, hr=3 (proportional)
    _seed_season_batting(conn, player_id="tie_b", team_id=team, season_id=season,
                         pa=60, ab=48, h=18, doubles=0, triples=0, hr=3,
                         bb=9, hbp=3)

    rows = get_top_hitters(team, season, db=conn)
    assert rows[0]["player_id"] == "p_high"
    # tie_b (higher PA) should appear before tie_a even when OPS ties.
    pids = [r["player_id"] for r in rows]
    assert pids.index("tie_b") < pids.index("tie_a")


def test_get_top_hitters_limit(conn) -> None:
    season = _seed_season(conn)
    team = _seed_team(conn, "Team A")
    for i in range(10):
        pid = f"p_{i}"
        _seed_player(conn, pid, f"P{i}", "X")
        _seed_roster(conn, team_id=team, player_id=pid, season_id=season)
        _seed_season_batting(
            conn, player_id=pid, team_id=team, season_id=season,
            pa=50, ab=40, h=10 + i,  # ascending OPS
        )
    rows = get_top_hitters(team, season, limit=3, db=conn)
    assert len(rows) == 3


def test_get_top_hitters_zero_ab_safe(conn) -> None:
    """A row with ab=0 must not divide-by-zero; rate is 0.0 and row appears."""
    season = _seed_season(conn)
    team = _seed_team(conn, "Team A")
    _seed_player(conn, "p_zero", "Zero", "AB")
    _seed_roster(conn, team_id=team, player_id="p_zero", season_id=season)
    _seed_season_batting(conn, player_id="p_zero", team_id=team, season_id=season,
                         pa=12, ab=0, h=0, bb=12, hbp=0)
    rows = get_top_hitters(team, season, db=conn)
    assert len(rows) == 1
    r = rows[0]
    assert r["slg"] == 0.0
    # OBP = (h + bb + hbp) / pa = 12/12 = 1.0
    assert r["obp"] == pytest.approx(1.0)


def test_get_top_hitters_isolates_team_perspectives_for_shared_player(conn) -> None:
    """A player with separate (player_id, team_id, season_id) batting rows
    for two different teams in the same season must yield distinct
    per-team stats -- ``get_top_hitters(team_a)`` must NEVER surface the
    team_b row, and vice versa.  This guards the natural perspective key
    ``team_id + season_id`` in ``player_season_batting``.
    """
    season = _seed_season(conn)
    team_a = _seed_team(conn, "Team A")
    team_b = _seed_team(conn, "Team B")
    # Same player_id appears for BOTH teams in the same season -- this
    # is legitimate (e.g., a player rostered on Varsity AND Legion in
    # the same calendar year) and the query must not commingle them.
    _seed_player(conn, "p_shared", "Shared", "Player")
    _seed_roster(conn, team_id=team_a, player_id="p_shared", season_id=season,
                 jersey="12")
    _seed_roster(conn, team_id=team_b, player_id="p_shared", season_id=season,
                 jersey="34")

    # Team A row: strong line.
    _seed_season_batting(
        conn, player_id="p_shared", team_id=team_a, season_id=season,
        pa=50, ab=40, h=20, hr=4, bb=8, hbp=2, doubles=4, triples=0, so=6,
    )
    # Team B row: weaker line.  Different stats prove the rows are
    # actually distinct (not collapsing on player_id).
    _seed_season_batting(
        conn, player_id="p_shared", team_id=team_b, season_id=season,
        pa=30, ab=25, h=5, hr=0, bb=4, hbp=1, doubles=1, triples=0, so=10,
    )

    rows_a = get_top_hitters(team_a, season, db=conn)
    rows_b = get_top_hitters(team_b, season, db=conn)

    # Each call returns exactly one row (the player on its own team).
    assert [r["player_id"] for r in rows_a] == ["p_shared"]
    assert [r["player_id"] for r in rows_b] == ["p_shared"]

    # Stats differ -- proves the rows are perspective-keyed by team_id.
    a = rows_a[0]
    b = rows_b[0]
    assert a["pa"] == 50 and b["pa"] == 30
    assert a["h"] == 20 and b["h"] == 5
    assert a["hr"] == 4 and b["hr"] == 0
    # Jersey number reflects the per-team roster.
    assert a["jersey_number"] == "12"
    assert b["jersey_number"] == "34"
    # Higher OPS line on team A -- sanity-check rates are different.
    assert a["ops"] != b["ops"]


# ---------------------------------------------------------------------------
# get_hitter_pitch_tendencies
# ---------------------------------------------------------------------------


def _seed_game(
    c: sqlite3.Connection, *, game_id: str, season_id: str,
    home_team_id: int, away_team_id: int,
    home_score: int = 5, away_score: int = 3, status: str = "completed",
) -> str:
    c.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, "
        "away_team_id, home_score, away_score, status) "
        "VALUES (?, ?, '2026-04-10', ?, ?, ?, ?, ?)",
        (game_id, season_id, home_team_id, away_team_id,
         home_score, away_score, status),
    )
    c.commit()
    return game_id


def _seed_play_with_events(
    c: sqlite3.Connection, *, game_id: str, batter_id: str,
    season_id: str, batting_team_id: int, perspective_team_id: int,
    inning: int = 1, half: str = "top",
    play_order: int = 0,
    events: list[tuple[str, bool]] | None = None,
    did_score_change: int = 0,
    pitcher_id: str | None = None,
) -> int:
    cur = c.execute(
        "INSERT INTO plays "
        "(game_id, play_order, inning, half, season_id, batting_team_id, "
        "perspective_team_id, batter_id, pitcher_id, outcome, "
        "is_first_pitch_strike, did_score_change) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Single', 0, ?)",
        (game_id, play_order, inning, half, season_id, batting_team_id,
         perspective_team_id, batter_id, pitcher_id, did_score_change),
    )
    play_id = cur.lastrowid
    for i, (pitch_result, is_first_pitch) in enumerate(events or []):
        c.execute(
            "INSERT INTO play_events "
            "(play_id, event_order, event_type, pitch_result, is_first_pitch, "
            "raw_template) "
            "VALUES (?, ?, 'pitch', ?, ?, ?)",
            (play_id, i, pitch_result, 1 if is_first_pitch else 0, "pitch"),
        )
    c.commit()
    return play_id  # type: ignore[return-value]


def test_get_hitter_pitch_tendencies_filters_by_perspective_team_id(conn) -> None:
    """AC-T4: cross-perspective contamination guard."""
    season = _seed_season(conn)
    team_a = _seed_team(conn, "Team A")
    team_b = _seed_team(conn, "Team B")
    _seed_player(conn, "batter1", "Bat", "One")
    game = _seed_game(conn, game_id="g1", season_id=season,
                      home_team_id=team_a, away_team_id=team_b)

    # Two plays for the same batter -- one under team_a's perspective,
    # one under team_b's.  Each has 1 first-pitch swing.
    _seed_play_with_events(
        conn, game_id=game, batter_id="batter1", season_id=season,
        batting_team_id=team_a, perspective_team_id=team_a, play_order=0,
        events=[("strike_swinging", True), ("ball", False)],
    )
    _seed_play_with_events(
        conn, game_id=game, batter_id="batter1", season_id=season,
        batting_team_id=team_a, perspective_team_id=team_b, play_order=1,
        events=[("strike_swinging", True), ("ball", False)],
    )

    # Asking for team_a perspective: 1 PA, 1 first-pitch swing.
    res_a = get_hitter_pitch_tendencies("batter1", season, team_a, db=conn)
    assert res_a["total_pa_with_plays"] == 1
    assert res_a["fps_seen"] == 1
    assert res_a["fps_swing_count"] == 1

    # Asking for team_b perspective: also 1 PA.
    res_b = get_hitter_pitch_tendencies("batter1", season, team_b, db=conn)
    assert res_b["total_pa_with_plays"] == 1


def test_get_hitter_pitch_tendencies_first_pitch_swing_aggregation(conn) -> None:
    season = _seed_season(conn)
    team = _seed_team(conn, "Team A")
    other = _seed_team(conn, "Team B")
    _seed_player(conn, "b1", "B", "1")
    _seed_game(conn, game_id="g1", season_id=season,
               home_team_id=team, away_team_id=other)
    # 3 PAs: 2 first-pitch swings (one strike_swinging, one in_play),
    # 1 first-pitch ball (no swing).
    _seed_play_with_events(
        conn, game_id="g1", batter_id="b1", season_id=season,
        batting_team_id=team, perspective_team_id=team, play_order=0,
        events=[("strike_swinging", True)],
    )
    _seed_play_with_events(
        conn, game_id="g1", batter_id="b1", season_id=season,
        batting_team_id=team, perspective_team_id=team, play_order=1,
        events=[("in_play", True)],
    )
    _seed_play_with_events(
        conn, game_id="g1", batter_id="b1", season_id=season,
        batting_team_id=team, perspective_team_id=team, play_order=2,
        events=[("ball", True), ("strike_looking", False)],
    )
    res = get_hitter_pitch_tendencies("b1", season, team, db=conn)
    assert res["total_pa_with_plays"] == 3
    assert res["fps_seen"] == 3
    assert res["fps_swing_count"] == 2


def test_get_hitter_pitch_tendencies_empty_when_no_plays(conn) -> None:
    season = _seed_season(conn)
    team = _seed_team(conn, "Team A")
    _seed_player(conn, "noplays", "No", "Plays")
    res = get_hitter_pitch_tendencies("noplays", season, team, db=conn)
    assert res["total_pa_with_plays"] == 0
    assert res["fps_seen"] == 0
    assert res["fps_swing_count"] == 0
    assert res["swing_rate_by_count"] == {}


# ---------------------------------------------------------------------------
# get_sb_tendency
# ---------------------------------------------------------------------------


def _seed_game_batting(
    c: sqlite3.Connection, *, game_id: str, player_id: str,
    team_id: int, perspective_team_id: int,
    sb: int = 0, cs: int = 0,
) -> None:
    c.execute(
        "INSERT INTO player_game_batting "
        "(game_id, player_id, team_id, perspective_team_id, "
        "ab, h, sb, cs) VALUES (?, ?, ?, ?, 0, 0, ?, ?)",
        (game_id, player_id, team_id, perspective_team_id, sb, cs),
    )
    c.commit()


def test_get_sb_tendency_aggregates_sb_attempts(conn) -> None:
    season = _seed_season(conn)
    team_a = _seed_team(conn, "Team A")
    team_b = _seed_team(conn, "Team B")
    _seed_player(conn, "runner", "Run", "Ner")
    _seed_game(conn, game_id="g1", season_id=season,
               home_team_id=team_a, away_team_id=team_b)
    _seed_game(conn, game_id="g2", season_id=season,
               home_team_id=team_a, away_team_id=team_b)
    # Team A perspective: 2 SB, 1 CS.
    _seed_game_batting(conn, game_id="g1", player_id="runner",
                       team_id=team_a, perspective_team_id=team_a, sb=2, cs=1)
    _seed_game_batting(conn, game_id="g2", player_id="runner",
                       team_id=team_a, perspective_team_id=team_a, sb=1, cs=0)
    # Team B perspective row -- must NOT be counted toward team_a aggregates.
    _seed_game_batting(conn, game_id="g1", player_id="runner",
                       team_id=team_a, perspective_team_id=team_b, sb=99, cs=99)

    res = get_sb_tendency(team_a, season, perspective_team_id=team_a, db=conn)
    assert res["sb_successes"] == 3
    # Attempts = sb + cs = 4
    assert res["sb_attempts"] == 4
    assert res["sb_success_rate"] == pytest.approx(0.75)


def test_get_sb_tendency_catcher_cs_against_from_play_events(conn) -> None:
    season = _seed_season(conn)
    team_a = _seed_team(conn, "Team A")
    team_b = _seed_team(conn, "Team B")
    _seed_player(conn, "batter_b", "B", "B")
    _seed_game(conn, game_id="g1", season_id=season,
               home_team_id=team_a, away_team_id=team_b)

    # Team A is on defense -- batting_team_id = team_b.  Two CS-against
    # events and one SB-against event at the perspective_team_id = A.
    cur = conn.execute(
        "INSERT INTO plays "
        "(game_id, play_order, inning, half, season_id, batting_team_id, "
        "perspective_team_id, batter_id, outcome, "
        "is_first_pitch_strike, did_score_change) "
        "VALUES (?, ?, 1, 'top', ?, ?, ?, ?, 'Walk', 0, 0)",
        ("g1", 0, season, team_b, team_a, "batter_b"),
    )
    play_id = cur.lastrowid
    conn.execute(
        "INSERT INTO play_events (play_id, event_order, event_type, "
        "pitch_result, is_first_pitch, raw_template) "
        "VALUES (?, 0, 'baserunner', NULL, 0, 'Runner caught stealing 2B')",
        (play_id,),
    )
    conn.execute(
        "INSERT INTO play_events (play_id, event_order, event_type, "
        "pitch_result, is_first_pitch, raw_template) "
        "VALUES (?, 1, 'baserunner', NULL, 0, 'Runner caught stealing 3B')",
        (play_id,),
    )
    conn.execute(
        "INSERT INTO play_events (play_id, event_order, event_type, "
        "pitch_result, is_first_pitch, raw_template) "
        "VALUES (?, 2, 'baserunner', NULL, 0, 'Runner steals 2B')",
        (play_id,),
    )
    conn.commit()

    res = get_sb_tendency(team_a, season, perspective_team_id=team_a, db=conn)
    # 2 CS + 1 SB = 3 attempts, 2 caught.
    assert res["catcher_cs_against_attempts"] == 3
    assert res["catcher_cs_against_count"] == 2
    assert res["catcher_cs_against_rate"] == pytest.approx(2 / 3, rel=1e-3)


def test_get_sb_tendency_zero_attempts(conn) -> None:
    season = _seed_season(conn)
    team = _seed_team(conn, "Team A")
    res = get_sb_tendency(team, season, perspective_team_id=team, db=conn)
    assert res["sb_attempts"] == 0
    assert res["sb_success_rate"] == 0.0
    assert res["catcher_cs_against_rate"] == 0.0


# ---------------------------------------------------------------------------
# get_first_inning_pattern
# ---------------------------------------------------------------------------


def test_get_first_inning_pattern_counts_scored_and_allowed(conn) -> None:
    season = _seed_season(conn)
    team_a = _seed_team(conn, "Team A")
    team_b = _seed_team(conn, "Team B")
    _seed_player(conn, "b1", "B", "1")

    # 4 games for team_a:
    # g1 - A scored in 1st, B did not.
    # g2 - B scored in 1st against A.
    # g3 - neither scored in 1st.
    # g4 - both scored in 1st.
    for gid in ("g1", "g2", "g3", "g4"):
        _seed_game(conn, game_id=gid, season_id=season,
                   home_team_id=team_a, away_team_id=team_b)

    play_counter = {"n": 0}

    def _add_play(game, batting_team, did_score, half="bottom"):
        play_counter["n"] += 1
        cur = conn.execute(
            "INSERT INTO plays "
            "(game_id, play_order, inning, half, season_id, batting_team_id, "
            "perspective_team_id, batter_id, outcome, "
            "is_first_pitch_strike, did_score_change) "
            "VALUES (?, ?, 1, ?, ?, ?, ?, ?, 'Single', 0, ?)",
            (game, play_counter["n"], half, season, batting_team, team_a,
             "b1", did_score),
        )
        return cur.lastrowid

    # g1: A scored.
    _add_play("g1", team_a, 1)
    # g2: B scored.
    _add_play("g2", team_b, 1)
    # g3: A batted but did not score.
    _add_play("g3", team_a, 0)
    # g4: both scored -- two plays in 1st inning, top + bottom.
    _add_play("g4", team_a, 1, half="bottom")
    _add_play("g4", team_b, 1, half="top")
    conn.commit()

    res = get_first_inning_pattern(team_a, season, db=conn)
    assert res["games_played"] == 4
    assert res["games_with_first_inning_runs_scored"] == 2  # g1, g4
    assert res["games_with_first_inning_runs_allowed"] == 2  # g2, g4
    assert res["first_inning_scored_rate"] == pytest.approx(0.5)
    assert res["first_inning_allowed_rate"] == pytest.approx(0.5)


def test_get_first_inning_pattern_empty_when_no_games(conn) -> None:
    season = _seed_season(conn)
    team = _seed_team(conn, "Team A")
    res = get_first_inning_pattern(team, season, db=conn)
    assert res["games_played"] == 0
    assert res["first_inning_scored_rate"] == 0.0
    assert res["first_inning_allowed_rate"] == 0.0


def test_get_first_inning_pattern_dedupes_cross_perspective_plays(conn) -> None:
    """Same play loaded under two perspectives must count once per (game, half)."""
    season = _seed_season(conn)
    team_a = _seed_team(conn, "Team A")
    team_b = _seed_team(conn, "Team B")
    _seed_player(conn, "b1", "B", "1")
    _seed_game(conn, game_id="g1", season_id=season,
               home_team_id=team_a, away_team_id=team_b)

    # Two plays for the same (game_id, half=bottom) under different
    # perspectives -- counts as one game-half toward 1st-inning scored.
    for persp in (team_a, team_b):
        conn.execute(
            "INSERT INTO plays "
            "(game_id, play_order, inning, half, season_id, batting_team_id, "
            "perspective_team_id, batter_id, outcome, "
            "is_first_pitch_strike, did_score_change) "
            "VALUES ('g1', ?, 1, 'bottom', ?, ?, ?, 'b1', 'Single', 0, 1)",
            (0 if persp == team_a else 1, season, team_a, persp),
        )
    conn.commit()
    res = get_first_inning_pattern(team_a, season, db=conn)
    assert res["games_played"] == 1
    assert res["games_with_first_inning_runs_scored"] == 1


# ---------------------------------------------------------------------------
# get_players_spray_events_batch -- perspective_team_id isolation
# (Codex Phase 4b MUST FIX 1)
# ---------------------------------------------------------------------------


def _seed_spray_event(
    c: sqlite3.Connection, *, player_id: str, team_id: int, game_id: str,
    season_id: str, perspective_team_id: int,
    play_type: str = "ground_ball", play_result: str = "single",
    x: float = 160.0, y: float = 100.0,
) -> None:
    c.execute(
        "INSERT INTO spray_charts "
        "(player_id, team_id, game_id, season_id, chart_type, x, y, "
        "play_type, play_result, perspective_team_id) "
        "VALUES (?, ?, ?, ?, 'offensive', ?, ?, ?, ?, ?)",
        (player_id, team_id, game_id, season_id, x, y, play_type,
         play_result, perspective_team_id),
    )
    c.commit()


def test_get_players_spray_events_batch_filters_by_perspective(conn) -> None:
    """A player on two teams in the same season -- explicit perspective
    isolates events to that team's view.

    Without ``perspective_team_id`` scoping, querying ``['p1']`` would
    return BOTH teams' events.  This is the regression Codex flagged.
    """
    season = _seed_season(conn)
    team_a = _seed_team(conn, "Team A")
    team_b = _seed_team(conn, "Team B")
    _seed_player(conn, "p1", "Cross", "Team")

    _seed_game(conn, game_id="g-a", season_id=season,
               home_team_id=team_a, away_team_id=team_b)
    _seed_game(conn, game_id="g-b", season_id=season,
               home_team_id=team_b, away_team_id=team_a)

    # Player p1 has two events captured under Team A's perspective and
    # one under Team B's perspective.
    _seed_spray_event(conn, player_id="p1", team_id=team_a, game_id="g-a",
                      season_id=season, perspective_team_id=team_a,
                      play_type="ground_ball")
    _seed_spray_event(conn, player_id="p1", team_id=team_a, game_id="g-a",
                      season_id=season, perspective_team_id=team_a,
                      play_type="line_drive")
    _seed_spray_event(conn, player_id="p1", team_id=team_b, game_id="g-b",
                      season_id=season, perspective_team_id=team_b,
                      play_type="fly_ball")

    # Querying with team_a's perspective returns only the two team-A events.
    res_a = get_players_spray_events_batch(
        ["p1"], season, perspective_team_id=team_a, db=conn,
    )
    assert "p1" in res_a
    assert len(res_a["p1"]) == 2
    assert {ev["play_type"] for ev in res_a["p1"]} == {"ground_ball", "line_drive"}

    # Team B's perspective returns only the single team-B event.
    res_b = get_players_spray_events_batch(
        ["p1"], season, perspective_team_id=team_b, db=conn,
    )
    assert "p1" in res_b
    assert len(res_b["p1"]) == 1
    assert res_b["p1"][0]["play_type"] == "fly_ball"


def test_get_players_spray_events_batch_legacy_self_join_fallback(conn) -> None:
    """When ``perspective_team_id`` is omitted, the legacy
    ``perspective_team_id = team_id`` self-join behavior is preserved.
    """
    season = _seed_season(conn)
    team_a = _seed_team(conn, "Team A")
    team_b = _seed_team(conn, "Team B")
    _seed_player(conn, "p1", "Player", "One")

    _seed_game(conn, game_id="g-a", season_id=season,
               home_team_id=team_a, away_team_id=team_b)

    # Self-perspective row (team_id == perspective_team_id) should match
    # under the legacy fallback...
    _seed_spray_event(conn, player_id="p1", team_id=team_a, game_id="g-a",
                      season_id=season, perspective_team_id=team_a,
                      play_type="ground_ball")
    # ...and a foreign-perspective row (team_id != perspective_team_id)
    # should NOT match the legacy fallback.
    _seed_spray_event(conn, player_id="p1", team_id=team_a, game_id="g-a",
                      season_id=season, perspective_team_id=team_b,
                      play_type="line_drive")

    res = get_players_spray_events_batch(["p1"], season, db=conn)
    assert "p1" in res
    assert len(res["p1"]) == 1
    assert res["p1"][0]["play_type"] == "ground_ball"


# ---------------------------------------------------------------------------
# get_first_inning_pattern -- denominator alignment with plays-loaded games
# (Codex Phase 4b MUST FIX 2)
# ---------------------------------------------------------------------------


def test_get_first_inning_pattern_denominator_excludes_games_without_plays(
    conn,
) -> None:
    """Denominator counts only games where plays data exists.

    When plays-stage incompleteness leaves some games without rows in
    ``plays``, the rate must be over the games-with-plays count, not
    every completed game (which would understate by treating
    "unknown" as "0").
    """
    season = _seed_season(conn)
    team_a = _seed_team(conn, "Team A")
    team_b = _seed_team(conn, "Team B")
    _seed_player(conn, "b1", "B", "1")

    # Four completed games for team_a:
    #   g1 + g2 have plays loaded; g3 + g4 have NO plays rows.
    for gid in ("g1", "g2", "g3", "g4"):
        _seed_game(conn, game_id=gid, season_id=season,
                   home_team_id=team_a, away_team_id=team_b)

    # g1: team_a scored in 1st (offense) -- batting_team = team_a.
    conn.execute(
        "INSERT INTO plays "
        "(game_id, play_order, inning, half, season_id, batting_team_id, "
        "perspective_team_id, batter_id, outcome, "
        "is_first_pitch_strike, did_score_change) "
        "VALUES ('g1', 0, 1, 'bottom', ?, ?, ?, 'b1', 'Single', 0, 1)",
        (season, team_a, team_a),
    )
    # g2: team_a allowed in 1st -- batting_team = team_b.
    conn.execute(
        "INSERT INTO plays "
        "(game_id, play_order, inning, half, season_id, batting_team_id, "
        "perspective_team_id, batter_id, outcome, "
        "is_first_pitch_strike, did_score_change) "
        "VALUES ('g2', 0, 1, 'top', ?, ?, ?, 'b1', 'Single', 0, 1)",
        (season, team_b, team_a),
    )
    conn.commit()

    res = get_first_inning_pattern(team_a, season, db=conn)
    # games_played reflects ONLY games with plays loaded (g1, g2).
    assert res["games_played"] == 2
    assert res["games_with_first_inning_runs_scored"] == 1  # g1
    assert res["games_with_first_inning_runs_allowed"] == 1  # g2
    # Rates are 1/2, not 1/4 (which would be the bug -- treating g3/g4
    # as "0 of N" when they should be "unknown / not counted").
    assert res["first_inning_scored_rate"] == pytest.approx(0.5)
    assert res["first_inning_allowed_rate"] == pytest.approx(0.5)


def test_get_first_inning_pattern_no_plays_loaded_returns_zero_games(conn) -> None:
    """All games completed but no plays loaded -> games_played == 0."""
    season = _seed_season(conn)
    team_a = _seed_team(conn, "Team A")
    team_b = _seed_team(conn, "Team B")

    for gid in ("g1", "g2"):
        _seed_game(conn, game_id=gid, season_id=season,
                   home_team_id=team_a, away_team_id=team_b)

    res = get_first_inning_pattern(team_a, season, db=conn)
    assert res["games_played"] == 0
    assert res["games_with_first_inning_runs_scored"] == 0
    assert res["games_with_first_inning_runs_allowed"] == 0
    assert res["first_inning_scored_rate"] == 0.0
    assert res["first_inning_allowed_rate"] == 0.0
