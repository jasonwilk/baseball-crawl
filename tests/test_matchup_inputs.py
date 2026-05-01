"""Integration tests for ``build_matchup_inputs`` (E-228-12 AC-T3).

Seeds an in-memory SQLite DB with cross-perspective rows and verifies
the input builder assembles a complete ``MatchupInputs`` dataclass.
Pairs with ``tests/test_db_matchup_queries.py`` (helpers in isolation)
and ``tests/test_matchup.py`` (engine purity + fixture tests).
"""

from __future__ import annotations

import datetime
import sqlite3

import pytest

from src.reports.matchup import (
    MatchupInputs,
    PlayerSprayProfile,
    build_matchup_inputs,
    compute_matchup,
)
from tests.conftest import load_real_schema


# ---------------------------------------------------------------------------
# Schema fixture + seed helpers
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


def _seed_player(c, pid, first="F", last="L"):  # type: ignore[no-untyped-def]
    c.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, ?, ?)",
        (pid, first, last),
    )
    c.commit()


def _seed_roster(c, team_id, player_id, season_id, jersey=None):  # type: ignore[no-untyped-def]
    c.execute(
        "INSERT OR IGNORE INTO team_rosters "
        "(team_id, player_id, season_id, jersey_number) VALUES (?, ?, ?, ?)",
        (team_id, player_id, season_id, jersey),
    )
    c.commit()


def _seed_season_batting(  # type: ignore[no-untyped-def]
    c, *, player_id, team_id, season_id,
    pa=50, ab=40, h=14, hr=2, bb=6, hbp=1, so=8, sb=0,
    doubles=0, triples=0,
):
    tb = (h - doubles - triples - hr) + 2 * doubles + 3 * triples + 4 * hr
    c.execute(
        "INSERT INTO player_season_batting "
        "(player_id, team_id, season_id, pa, ab, h, doubles, triples, hr, "
        "bb, hbp, so, sb, tb) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (player_id, team_id, season_id, pa, ab, h, doubles, triples, hr,
         bb, hbp, so, sb, tb),
    )
    c.commit()


def _seed_game(  # type: ignore[no-untyped-def]
    c, *, game_id, season_id, home_team_id, away_team_id,
    home_score=5, away_score=3, status="completed", game_date="2026-04-08",
):
    c.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, "
        "away_team_id, home_score, away_score, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (game_id, season_id, game_date, home_team_id, away_team_id,
         home_score, away_score, status),
    )
    c.commit()


def _seed_pitching_row(  # type: ignore[no-untyped-def]
    c, *, game_id, player_id, team_id, perspective_team_id,
    appearance_order=1, ip_outs=21, er=2, bb=2, so=5, pitches=80,
    decision=None, h=5,
):
    c.execute(
        "INSERT INTO player_game_pitching "
        "(game_id, player_id, team_id, perspective_team_id, "
        "appearance_order, ip_outs, h, r, er, bb, so, pitches, decision, bf) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_id, player_id, team_id, perspective_team_id,
         appearance_order, ip_outs, h, er, er, bb, so, pitches, decision, 25),
    )
    c.commit()


def _seed_spray(  # type: ignore[no-untyped-def]
    c, *, player_id, team_id, perspective_team_id, season_id,
    x=0.7, y=0.5, play_result="Single", event_gc_id=None,
):
    if event_gc_id is None:
        event_gc_id = f"evt-{player_id}-{x}-{y}"
    c.execute(
        "INSERT OR IGNORE INTO spray_charts "
        "(player_id, team_id, perspective_team_id, chart_type, "
        "play_type, play_result, x, y, event_gc_id, season_id) "
        "VALUES (?, ?, ?, 'offensive', NULL, ?, ?, ?, ?, ?)",
        (player_id, team_id, perspective_team_id, play_result,
         x, y, event_gc_id, season_id),
    )
    c.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_build_matchup_inputs_with_our_team_id_none(conn) -> None:
    """AC-3: builder returns lsb_team=None and lsb_pitching=None.

    Also AC-T3: golden-path-ish object with all sub-fields populated.
    """
    season = _seed_season(conn)
    opp = _seed_team(conn, "Rival HS")
    _seed_player(conn, "h1", "Alpha", "Hitter")
    _seed_roster(conn, opp, "h1", season, jersey="7")
    _seed_season_batting(conn, player_id="h1", team_id=opp, season_id=season,
                         pa=40, ab=32, h=12, hr=2, bb=4, hbp=1)

    inputs = build_matchup_inputs(
        conn, opponent_team_id=opp, our_team_id=None,
        season_id=season, reference_date=datetime.date(2026, 4, 10),
    )
    assert isinstance(inputs, MatchupInputs)
    assert inputs.opponent_team["name"] == "Rival HS"
    assert inputs.lsb_team is None
    assert inputs.lsb_pitching is None
    assert inputs.season_id == season


def test_build_matchup_inputs_full_dataclass_populated(conn) -> None:
    """AC-T3 golden path: every sub-field present for a populated DB."""
    season = _seed_season(conn)
    opp = _seed_team(conn, "Rival HS")
    lsb = _seed_team(conn, "LSB Varsity", member=True)

    # Hitter on the opposing roster.
    _seed_player(conn, "h1", "Alpha", "One")
    _seed_roster(conn, opp, "h1", season, jersey="7")
    _seed_season_batting(conn, player_id="h1", team_id=opp, season_id=season,
                         pa=40, ab=32, h=12, hr=2, bb=4, hbp=1)

    # Roster member with spray data only (not a top-3 hitter).
    _seed_player(conn, "r1", "Roster", "One")
    _seed_roster(conn, opp, "r1", season, jersey="9")
    for i in range(15):
        _seed_spray(conn, player_id="r1", team_id=opp,
                    perspective_team_id=opp, season_id=season,
                    x=0.7 + i * 0.01, y=0.5,
                    event_gc_id=f"r1-evt-{i}")

    # One LSB pitcher with workload row.
    _seed_player(conn, "lsbp", "LSB", "Pitcher")
    _seed_roster(conn, lsb, "lsbp", season, jersey="11")
    _seed_game(conn, game_id="lsb-g1", season_id=season,
               home_team_id=lsb, away_team_id=opp,
               game_date="2026-04-08")
    _seed_pitching_row(conn, game_id="lsb-g1", player_id="lsbp",
                       team_id=lsb, perspective_team_id=lsb,
                       appearance_order=1, ip_outs=18, er=2)

    # One opposing pitcher.
    _seed_player(conn, "oppp", "Opp", "Pitcher")
    _seed_roster(conn, opp, "oppp", season, jersey="22")
    _seed_pitching_row(conn, game_id="lsb-g1", player_id="oppp",
                       team_id=opp, perspective_team_id=opp,
                       appearance_order=1, ip_outs=15, er=4,
                       decision="L")

    # An opponent loss in their own perspective: opp at home, lost.
    _seed_game(conn, game_id="opp-g1", season_id=season,
               home_team_id=opp, away_team_id=lsb,
               home_score=2, away_score=8, game_date="2026-04-05")
    _seed_pitching_row(conn, game_id="opp-g1", player_id="oppp",
                       team_id=opp, perspective_team_id=opp,
                       appearance_order=1, ip_outs=6, er=5,
                       decision="L")

    inputs = build_matchup_inputs(
        conn, opponent_team_id=opp, our_team_id=lsb,
        season_id=season, reference_date=datetime.date(2026, 4, 10),
    )
    # Shape sanity.
    assert inputs.opponent_team["id"] == opp
    assert inputs.lsb_team is not None and inputs.lsb_team["id"] == lsb
    # Top hitters list contains the qualifying batter.
    pids = [h["player_id"] for h in inputs.opponent_top_hitters]
    assert "h1" in pids
    # Roster spray includes r1 (full opposing roster, not top-3).
    spray_pids = [p.player_id for p in inputs.opponent_roster_spray]
    assert "r1" in spray_pids
    # Loss list includes the opp loss.
    loss_ids = [loss["game_id"] for loss in inputs.opponent_losses]
    assert "opp-g1" in loss_ids
    # SB and first-inning sub-dicts present.
    assert "sb_attempts" in inputs.opponent_sb_profile
    assert "games_played" in inputs.opponent_first_inning_pattern
    # Eligible pitcher rows exist for both teams.
    opp_pitcher_ids = [p["player_id"] for p in inputs.opponent_pitching]
    assert "oppp" in opp_pitcher_ids
    assert inputs.lsb_pitching is not None
    lsb_pitcher_ids = [p["player_id"] for p in inputs.lsb_pitching]
    assert "lsbp" in lsb_pitcher_ids


def test_build_matchup_inputs_filters_cross_perspective_rows(conn) -> None:
    """AC-T4: builder must not pull in cross-perspective contamination.

    Seeds a play under team_a's perspective with batter on team_b, and
    asserts the per-hitter pitch tendencies under team_b's perspective
    do NOT count it.
    """
    season = _seed_season(conn)
    team_a = _seed_team(conn, "Team A")
    team_b = _seed_team(conn, "Rival HS")
    _seed_player(conn, "h1", "Alpha", "One")
    _seed_roster(conn, team_b, "h1", season, jersey="7")
    _seed_season_batting(conn, player_id="h1", team_id=team_b,
                         season_id=season, pa=40, ab=32, h=12, hr=2,
                         bb=4, hbp=1)
    _seed_game(conn, game_id="g1", season_id=season,
               home_team_id=team_a, away_team_id=team_b)

    # Two plays for batter h1, but only one under team_b's perspective.
    cur = conn.execute(
        "INSERT INTO plays "
        "(game_id, play_order, inning, half, season_id, batting_team_id, "
        "perspective_team_id, batter_id, outcome, "
        "is_first_pitch_strike, did_score_change) "
        "VALUES ('g1', 0, 1, 'top', ?, ?, ?, 'h1', 'Single', 0, 0)",
        (season, team_b, team_b),
    )
    conn.execute(
        "INSERT INTO play_events (play_id, event_order, event_type, "
        "pitch_result, is_first_pitch, raw_template) "
        "VALUES (?, 0, 'pitch', 'in_play', 1, 'In play')",
        (cur.lastrowid,),
    )
    cur2 = conn.execute(
        "INSERT INTO plays "
        "(game_id, play_order, inning, half, season_id, batting_team_id, "
        "perspective_team_id, batter_id, outcome, "
        "is_first_pitch_strike, did_score_change) "
        "VALUES ('g1', 1, 1, 'top', ?, ?, ?, 'h1', 'Single', 0, 0)",
        (season, team_b, team_a),
    )
    conn.execute(
        "INSERT INTO play_events (play_id, event_order, event_type, "
        "pitch_result, is_first_pitch, raw_template) "
        "VALUES (?, 0, 'pitch', 'strike_swinging', 1, 'Strike 1 swinging')",
        (cur2.lastrowid,),
    )
    conn.commit()

    inputs = build_matchup_inputs(
        conn, opponent_team_id=team_b, our_team_id=None,
        season_id=season, reference_date=datetime.date(2026, 4, 10),
    )
    h1 = next(
        (h for h in inputs.opponent_top_hitters if h["player_id"] == "h1"),
        None,
    )
    assert h1 is not None
    # Only the team_b-perspective play should have been counted.
    assert h1["fps_seen"] == 1


def test_compute_matchup_e2e_with_input_builder(conn) -> None:
    """Smoke test: build_matchup_inputs feeding compute_matchup produces
    a non-suppressed analysis with at least the structural fields."""
    season = _seed_season(conn)
    opp = _seed_team(conn, "Rival HS")
    _seed_player(conn, "h1", "Alpha", "One")
    _seed_roster(conn, opp, "h1", season, jersey="7")
    _seed_season_batting(conn, player_id="h1", team_id=opp,
                         season_id=season,
                         pa=40, ab=32, h=12, hr=2, bb=4, hbp=1)
    # Loss row to pull confidence above suppress.
    _seed_game(conn, game_id="g1", season_id=season,
               home_team_id=opp, away_team_id=opp,  # placeholder; we only need a loss
               home_score=2, away_score=8)
    _seed_player(conn, "p1", "P", "Itcher")
    _seed_pitching_row(conn, game_id="g1", player_id="p1",
                       team_id=opp, perspective_team_id=opp,
                       appearance_order=1, ip_outs=6, er=5,
                       decision="L")
    inputs = build_matchup_inputs(
        conn, opponent_team_id=opp, our_team_id=None,
        season_id=season, reference_date=datetime.date(2026, 4, 10),
    )
    out = compute_matchup(inputs)
    assert out.confidence != "suppress"
    assert out.eligible_lsb_pitchers is None  # our_team_id was None
    # Loss recipe accumulator should reflect the seeded loss.
    assert (
        out.loss_recipe_buckets.starter_shelled_early.count
        + out.loss_recipe_buckets.bullpen_couldnt_hold.count
        + out.loss_recipe_buckets.close_game_lost_late.count
        + out.loss_recipe_buckets.uncategorized_count
    ) >= 1


def test_player_spray_profile_dataclass_shape() -> None:
    p = PlayerSprayProfile(
        player_id="r1", name="Roster One", jersey_number="9",
        pull_pct=0.62, bip_count=22,
    )
    assert p.bip_count == 22
    assert p.pull_pct == 0.62


def test_eligible_pitchers_ordered_most_rested_first(conn) -> None:
    """The eligibility list must surface MOST-rested pitchers first.

    Seeds 6 pitchers with varied ``last_outing_date`` values (oldest =
    most rested).  The list emitted by ``build_matchup_inputs`` is
    expected to put the 5 with the OLDEST outings at the top -- not the
    5 most-recent.  This guards the engine's top-N selection cap.
    """
    season = _seed_season(conn)
    opp = _seed_team(conn, "Rival HS")

    # last_outing_date schedule (most rested -> least rested):
    # p_oldest: 2026-03-20  (most rested)
    # p2:       2026-03-25
    # p3:       2026-03-30
    # p4:       2026-04-04
    # p5:       2026-04-08
    # p_newest: 2026-04-10  (least rested -- should be EXCLUDED by cap)
    pitcher_dates = [
        ("p_oldest", "2026-03-20"),
        ("p2", "2026-03-25"),
        ("p3", "2026-03-30"),
        ("p4", "2026-04-04"),
        ("p5", "2026-04-08"),
        ("p_newest", "2026-04-10"),
    ]
    # Lift confidence above suppress: seed at least one opponent loss and
    # one qualifying hitter so the engine actually emits the eligible
    # pitcher list (suppress would zero it out regardless of ordering).
    _seed_player(conn, "h1", "Alpha", "Hitter")
    _seed_roster(conn, opp, "h1", season, jersey="0")
    _seed_season_batting(conn, player_id="h1", team_id=opp,
                         season_id=season,
                         pa=40, ab=32, h=12, hr=2, bb=4, hbp=1)
    for idx, (pid, date) in enumerate(pitcher_dates):
        _seed_player(conn, pid, first=pid, last="P")
        _seed_roster(conn, opp, pid, season, jersey=str(idx + 1))
        # One game per pitcher on its outing date.
        gid = f"g-{pid}"
        _seed_game(conn, game_id=gid, season_id=season,
                   home_team_id=opp, away_team_id=opp,
                   game_date=date)
        # Mark p_oldest's game as a loss so opponent_losses is non-empty
        # (also lifts confidence above 'low').  Other games keep no
        # decision so they don't get classified as losses.
        decision = "L" if pid == "p_oldest" else None
        _seed_pitching_row(conn, game_id=gid, player_id=pid,
                           team_id=opp, perspective_team_id=opp,
                           appearance_order=1, ip_outs=6, er=5,
                           pitches=60, decision=decision)

    inputs = build_matchup_inputs(
        conn, opponent_team_id=opp, our_team_id=None,
        season_id=season, reference_date=datetime.date(2026, 4, 11),
    )
    # The builder returns the FULL list -- the engine applies the top-5
    # cap.  Verify ordering: oldest outing first (most rested first).
    pids = [e["player_id"] for e in inputs.opponent_pitching]
    assert pids[:5] == ["p_oldest", "p2", "p3", "p4", "p5"], (
        f"Expected most-rested-first ordering, got: {pids}"
    )
    # Sanity: p_newest is NOT in the top-5 of the ordered list.
    assert pids.index("p_newest") >= 5

    # Drive through the engine: the top-5 cap should match the same set.
    out = compute_matchup(inputs)
    eligible_pids = {e.player_id for e in out.eligible_opposing_pitchers}
    # Engine caps at 5; the captured set should be the 5 most-rested.
    assert eligible_pids == {"p_oldest", "p2", "p3", "p4", "p5"}, (
        f"Engine top-5 cap should pick most-rested, got: {eligible_pids}"
    )
    assert "p_newest" not in eligible_pids


def test_compute_matchup_suppress_clears_lsb_pitchers(conn) -> None:
    """Fix 3 contract: on ``confidence == 'suppress'`` the analysis MUST
    expose ``eligible_lsb_pitchers is None`` even when ``our_team_id``
    was set on the inputs (i.e., the LSB list was non-None going in).

    Suppress means "nothing to render"; leaking the LSB list contradicts
    that semantic and forces every renderer to special-case it.
    """
    season = _seed_season(conn)
    opp = _seed_team(conn, "Rival HS")
    lsb = _seed_team(conn, "LSB Varsity", member=True)

    # Seed a third team as a generic LSB opponent so the LSB game does
    # NOT involve ``opp`` -- otherwise that game would create an
    # opponent loss row and lift confidence above suppress.
    other = _seed_team(conn, "Some Other Team")
    _seed_player(conn, "lsbp", "LSB", "Pitcher")
    _seed_roster(conn, lsb, "lsbp", season, jersey="11")
    _seed_game(conn, game_id="lsb-g", season_id=season,
               home_team_id=lsb, away_team_id=other,
               game_date="2026-04-05")
    _seed_pitching_row(conn, game_id="lsb-g", player_id="lsbp",
                       team_id=lsb, perspective_team_id=lsb,
                       appearance_order=1, ip_outs=18, er=2)

    # No opponent hitters / losses / etc. -> suppress confidence.
    inputs = build_matchup_inputs(
        conn, opponent_team_id=opp, our_team_id=lsb,
        season_id=season, reference_date=datetime.date(2026, 4, 10),
    )
    # Precondition: the builder DID populate the LSB list -- otherwise
    # this test wouldn't actually exercise Fix 3.
    assert inputs.lsb_pitching is not None
    assert len(inputs.lsb_pitching) == 1

    out = compute_matchup(inputs)
    assert out.confidence == "suppress"
    # The fix: eligible_lsb_pitchers is None on suppress, regardless of
    # the LSB list having data.
    assert out.eligible_lsb_pitchers is None
