"""Tests for the per-pitcher per-appearance derivation (E-265-01 / E-266-06).

Covers the derivation module ``src/reports/pitcher_outings.py``: per-outing
fields (boxscore + plays), the six E-266-06 columns (XBH, Outcome, Score, S/R,
#P, S%), per-outing ERA on the E-264 basis, the season summary rate set with
small-sample flags, the perspective/role filter (two-perspective
no-double-count, incl. XBH), and None-on-zero-denom.

None-handling note: the "unknown" presentational fields (``outcome``, ``score``,
``start_relief``, ``pitches``) store ``None`` at this data layer; the renderer
(E-266-01) displays ``None`` as an em-dash, exactly as it already does for
``opponent`` and the rate fields.  These tests assert ``None`` accordingly.
"""

from __future__ import annotations

import sqlite3

import pytest

from src.reports.pitcher_outings import (
    Outing,
    SeasonSummary,
    build_pitcher_outings,
    is_pitcher_outings_enabled,
)
from tests.conftest import load_real_schema

SCOUTED = 1
OPPONENT = 999


# ── Seeding helpers ────────────────────────────────────────────────────


def _seed_season_and_teams(
    conn: sqlite3.Connection,
    *,
    season_id: str = "2026",
    innings_per_game: int | None = None,
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) VALUES (?, ?, 2026)",
        (season_id, season_id),
    )
    conn.execute(
        "INSERT OR IGNORE INTO teams (id, name, membership_type, innings_per_game) "
        "VALUES (?, 'Scouted', 'tracked', ?)",
        (SCOUTED, innings_per_game),
    )
    conn.execute(
        "INSERT OR IGNORE INTO teams (id, name, membership_type) "
        "VALUES (?, 'Opponent', 'tracked')",
        (OPPONENT,),
    )


def _insert_player(
    conn: sqlite3.Connection,
    player_id: str,
    first_name: str,
    last_name: str,
    *,
    team_id: int = SCOUTED,
    season_id: str = "2026",
    jersey_number: str | None = None,
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (player_id, first_name, last_name),
    )
    conn.execute(
        "INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id, jersey_number) "
        "VALUES (?, ?, ?, ?)",
        (team_id, player_id, season_id, jersey_number),
    )


def _insert_game(
    conn: sqlite3.Connection,
    game_id: str,
    game_date: str,
    *,
    season_id: str = "2026",
    home_team_id: int = SCOUTED,
    away_team_id: int = OPPONENT,
    start_time: str | None = None,
    status: str = "completed",
    home_score: int | None = None,
    away_score: int | None = None,
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO games "
        "(game_id, season_id, game_date, start_time, home_team_id, away_team_id, "
        "status, home_score, away_score) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            game_id, season_id, game_date, start_time, home_team_id, away_team_id,
            status, home_score, away_score,
        ),
    )


def _insert_pitching_line(
    conn: sqlite3.Connection,
    game_id: str,
    player_id: str,
    *,
    team_id: int = SCOUTED,
    perspective_team_id: int | None = None,
    ip_outs: int | None = 0,
    so: int | None = 0,
    bb: int | None = 0,
    h: int | None = 0,
    r: int | None = 0,
    er: int | None = 0,
    bf: int | None = None,
    pitches: int | None = None,
    total_strikes: int | None = None,
    appearance_order: int | None = None,
) -> None:
    conn.execute(
        "INSERT INTO player_game_pitching "
        "(game_id, player_id, team_id, perspective_team_id, ip_outs, pitches, "
        "total_strikes, so, bb, h, r, er, bf, appearance_order) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            game_id, player_id, team_id,
            perspective_team_id if perspective_team_id is not None else team_id,
            ip_outs, pitches, total_strikes, so, bb, h, r, er, bf, appearance_order,
        ),
    )


def _insert_play(
    conn: sqlite3.Connection,
    game_id: str,
    play_order: int,
    pitcher_id: str,
    *,
    season_id: str = "2026",
    batting_team_id: int = OPPONENT,
    perspective_team_id: int = SCOUTED,
    batter_id: str = "opp_bat",
    outcome: str | None = None,
    pitch_count: int = 1,
    is_first_pitch_strike: int = 0,
) -> None:
    conn.execute(
        "INSERT INTO plays "
        "(game_id, play_order, inning, half, season_id, batting_team_id, "
        "perspective_team_id, batter_id, pitcher_id, outcome, pitch_count, "
        "is_first_pitch_strike) "
        "VALUES (?, ?, 1, 'top', ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            game_id, play_order, season_id, batting_team_id, perspective_team_id,
            batter_id, pitcher_id, outcome, pitch_count, is_first_pitch_strike,
        ),
    )


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    load_real_schema(conn)
    yield conn
    conn.close()


# ── Feature flag (TN-1) ────────────────────────────────────────────────


class TestFeatureFlag:
    def test_off_by_default(self, monkeypatch):
        monkeypatch.delenv("FEATURE_PITCHER_OUTINGS", raising=False)
        assert is_pitcher_outings_enabled() is False

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "Yes"])
    def test_enabled_values(self, monkeypatch, value):
        monkeypatch.setenv("FEATURE_PITCHER_OUTINGS", value)
        assert is_pitcher_outings_enabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
    def test_disabled_values(self, monkeypatch, value):
        monkeypatch.setenv("FEATURE_PITCHER_OUTINGS", value)
        assert is_pitcher_outings_enabled() is False


# ── AC-1: per-outing fields incl. plays-derived HR + FPS% ──────────────


class TestPerOutingFields:
    @pytest.fixture(autouse=True)
    def setup(self, db):
        _seed_season_and_teams(db, innings_per_game=7)
        _insert_player(db, "p1", "Ace", "Smith", jersey_number="22")
        _insert_player(db, "opp_bat", "Opp", "Batter", team_id=OPPONENT)
        _insert_game(db, "g1", "2026-03-10")
        _insert_pitching_line(
            db, "g1", "p1", ip_outs=18, so=6, bb=2, h=4, r=2, er=1, bf=22,
            appearance_order=1,
        )
        # 4 charted PAs, 3 first-pitch strikes; one PA is a Home Run.
        _insert_play(db, "g1", 1, "p1", outcome="Home Run", is_first_pitch_strike=1)
        _insert_play(db, "g1", 2, "p1", outcome="Strikeout", is_first_pitch_strike=1)
        _insert_play(db, "g1", 3, "p1", outcome="Single", is_first_pitch_strike=1)
        _insert_play(db, "g1", 4, "p1", outcome="Walk", is_first_pitch_strike=0)
        db.commit()

    def test_one_entry_per_pitcher(self, db):
        result = build_pitcher_outings(db, SCOUTED, "2026")
        assert len(result) == 1
        assert result[0].player_id == "p1"
        assert result[0].name == "Ace Smith"
        assert result[0].jersey_number == "22"

    def test_outing_boxscore_fields(self, db):
        outing = build_pitcher_outings(db, SCOUTED, "2026")[0].outings[0]
        assert outing.game_id == "g1"
        assert outing.game_date == "2026-03-10"
        assert outing.opponent == "Opponent"
        assert outing.ip_outs == 18
        assert outing.bf == 22
        assert outing.h == 4
        assert outing.bb == 2
        assert outing.so == 6
        assert outing.r == 2
        assert outing.appearance_order == 1

    def test_hr_allowed_from_plays(self, db):
        outing = build_pitcher_outings(db, SCOUTED, "2026")[0].outings[0]
        assert outing.hr_allowed == 1

    def test_fps_pct_from_plays_charted_denominator(self, db):
        outing = build_pitcher_outings(db, SCOUTED, "2026")[0].outings[0]
        # 3 first-pitch strikes over 4 charted PAs.
        assert outing.fps_pct == pytest.approx(0.75)
        assert outing.charted_pa == 4


# ── AC-2: per-outing ERA on the E-264 basis ────────────────────────────


class TestPerOutingEra:
    def test_era_uses_team_basis(self, db):
        _seed_season_and_teams(db, innings_per_game=6)
        _insert_player(db, "p1", "Ace", "Smith")
        _insert_game(db, "g1", "2026-03-10")
        # basis=6 -> ERA = er * (6*3) / ip_outs = 2 * 18 / 18 = 2.00
        _insert_pitching_line(db, "g1", "p1", ip_outs=18, er=2, appearance_order=1)
        db.commit()
        outing = build_pitcher_outings(db, SCOUTED, "2026")[0].outings[0]
        assert outing.era == pytest.approx(2.0)

    def test_era_fallback_basis_7_when_null(self, db):
        _seed_season_and_teams(db, innings_per_game=None)
        _insert_player(db, "p1", "Ace", "Smith")
        _insert_game(db, "g1", "2026-03-10")
        # basis fallback 7 -> ERA = 2 * (7*3) / 21 = 2.00
        _insert_pitching_line(db, "g1", "p1", ip_outs=21, er=2, appearance_order=1)
        db.commit()
        outing = build_pitcher_outings(db, SCOUTED, "2026")[0].outings[0]
        assert outing.era == pytest.approx(2.0)

    def test_era_none_when_zero_ip(self, db):
        _seed_season_and_teams(db, innings_per_game=7)
        _insert_player(db, "p1", "Ace", "Smith")
        _insert_game(db, "g1", "2026-03-10")
        _insert_pitching_line(db, "g1", "p1", ip_outs=0, er=0, appearance_order=1)
        db.commit()
        outing = build_pitcher_outings(db, SCOUTED, "2026")[0].outings[0]
        assert outing.era is None

    def test_era_not_hardcoded_nine_inning(self, db):
        # A 9-inning (x27) basis would give 3.00; the team basis (6) gives 2.00.
        _seed_season_and_teams(db, innings_per_game=6)
        _insert_player(db, "p1", "Ace", "Smith")
        _insert_game(db, "g1", "2026-03-10")
        _insert_pitching_line(db, "g1", "p1", ip_outs=18, er=2, appearance_order=1)
        db.commit()
        outing = build_pitcher_outings(db, SCOUTED, "2026")[0].outings[0]
        assert outing.era != pytest.approx(3.0)


# ── AC-3 / AC-6: season summary rate set + flags ───────────────────────


class TestSeasonSummary:
    def _one_pitcher(self, db, **line):
        _seed_season_and_teams(db, innings_per_game=7)
        _insert_player(db, "p1", "Ace", "Smith")
        _insert_game(db, "g1", "2026-03-10")
        _insert_pitching_line(db, "g1", "p1", appearance_order=1, **line)
        db.commit()
        return build_pitcher_outings(db, SCOUTED, "2026")[0].season

    def test_full_context_and_rate_set(self, db):
        season = self._one_pitcher(
            db, ip_outs=45, so=20, bb=10, h=15, r=8, er=6, bf=60,
        )
        assert season.ip_outs == 45
        assert season.games == 1
        assert season.games_started == 1
        # ERA = 6 * (7*3) / 45 = 2.80
        assert season.era == pytest.approx(6 * 21 / 45)
        # WHIP = (10 + 15) * 3 / 45 = 1.6667
        assert season.whip == pytest.approx((10 + 15) * 3 / 45)
        # Rate set
        assert season.k_per_bf == pytest.approx(20 / 60)
        assert season.bb_per_inn == pytest.approx(10 * 3 / 45)
        assert season.k_per_bb == pytest.approx(20 / 10)
        assert season.h_per_bf == pytest.approx(15 / 60)

    def test_small_sample_flag_below_15_ip(self, db):
        season = self._one_pitcher(db, ip_outs=44, so=5, bb=6, h=5, bf=20)
        assert season.small_sample is True

    def test_no_small_sample_flag_at_15_ip(self, db):
        season = self._one_pitcher(db, ip_outs=45, so=5, bb=6, h=5, bf=20)
        assert season.small_sample is False

    def test_low_bb_badge_below_five_walks(self, db):
        season = self._one_pitcher(db, ip_outs=60, so=20, bb=3, h=10, bf=60)
        assert season.low_bb is True
        assert season.bb == 3

    def test_no_low_bb_badge_at_five_walks(self, db):
        season = self._one_pitcher(db, ip_outs=60, so=20, bb=5, h=10, bf=60)
        assert season.low_bb is False

    def test_zero_bb_distinguishable_from_no_data(self, db):
        # Zero-walk command strength: pitcher FACED batters (bf>0) and walked
        # none.  k_per_bb is None (division impossible) but zero_bb marks it a
        # strength, distinguishable from the no-data case below.
        season = self._one_pitcher(db, ip_outs=21, so=10, bb=0, h=4, bf=25)
        assert season.k_per_bb is None       # division impossible
        assert season.zero_bb is True         # ... but distinguishable as strength
        assert season.bb == 0

    def test_zero_bb_false_for_empty_no_data_line(self, db):
        # No-data case (F11): an empty line -- faced no batters (bf=0), no walks.
        # Must NOT masquerade as a zero-walk command strength.
        season = self._one_pitcher(db, ip_outs=0, so=0, bb=0, h=0, bf=0)
        assert season.k_per_bb is None
        assert season.zero_bb is False        # no-data, not command strength

    def test_rates_none_when_denominator_zero(self, db):
        season = self._one_pitcher(db, ip_outs=0, so=0, bb=0, h=0, bf=0)
        assert season.era is None
        assert season.whip is None
        assert season.k_per_bf is None
        assert season.bb_per_inn is None
        assert season.k_per_bb is None
        assert season.h_per_bf is None
        assert season.fps_pct is None
        # Faced no batters (bf=0) -> the no-data case, NOT a zero-walk command
        # strength (F11).  zero_bb must be False here.
        assert season.zero_bb is False

    def test_games_started_counts_appearance_order_one(self, db):
        _seed_season_and_teams(db, innings_per_game=7)
        _insert_player(db, "p1", "Spot", "Starter")
        _insert_game(db, "g1", "2026-03-10")
        _insert_game(db, "g2", "2026-03-12")
        _insert_pitching_line(db, "g1", "p1", ip_outs=18, appearance_order=1)
        _insert_pitching_line(db, "g2", "p1", ip_outs=3, appearance_order=2)
        db.commit()
        season = build_pitcher_outings(db, SCOUTED, "2026")[0].season
        assert season.games == 2
        assert season.games_started == 1

    def test_games_started_none_when_all_null_appearance_order(self, db):
        # Every appearance has NULL appearance_order -> GS is unknown (None),
        # mirroring get_season_pitching's MAX-IS-NULL -> NULL semantics, so the
        # Outings line never falsely claims "0 GS" (pure reliever).
        _seed_season_and_teams(db, innings_per_game=7)
        _insert_player(db, "p1", "Null", "Order")
        _insert_game(db, "g1", "2026-03-10")
        _insert_game(db, "g2", "2026-03-12")
        _insert_pitching_line(db, "g1", "p1", ip_outs=18, appearance_order=None)
        _insert_pitching_line(db, "g2", "p1", ip_outs=9, appearance_order=None)
        db.commit()
        season = build_pitcher_outings(db, SCOUTED, "2026")[0].season
        assert season.games == 2
        assert season.games_started is None

    def test_games_started_zero_when_populated_but_no_starts(self, db):
        # appearance_order populated (all relief) -> a real 0, NOT unknown.
        _seed_season_and_teams(db, innings_per_game=7)
        _insert_player(db, "p1", "Pure", "Reliever")
        _insert_game(db, "g1", "2026-03-10")
        _insert_pitching_line(db, "g1", "p1", ip_outs=3, appearance_order=2)
        db.commit()
        season = build_pitcher_outings(db, SCOUTED, "2026")[0].season
        assert season.games_started == 0


# ── Ordering: per-pitcher blocks by season IP descending (spec §4) ────


class TestOrdering:
    def test_ordered_by_season_ip_desc(self, db):
        _seed_season_and_teams(db, innings_per_game=7)
        _insert_player(db, "low", "Low", "IP")
        _insert_player(db, "high", "High", "IP")
        _insert_player(db, "mid", "Mid", "IP")
        # g1: high (starter) appears before low (reliever) in chronological
        # (first-appearance) order -> first-appearance order is high, low, mid.
        _insert_game(db, "g1", "2026-03-10")
        _insert_pitching_line(db, "g1", "high", ip_outs=21, appearance_order=1)
        _insert_pitching_line(db, "g1", "low", ip_outs=6, appearance_order=2)
        _insert_game(db, "g2", "2026-03-12")
        _insert_pitching_line(db, "g2", "mid", ip_outs=12, appearance_order=1)
        db.commit()
        result = build_pitcher_outings(db, SCOUTED, "2026")
        # IP-desc (21, 12, 6) reorders mid ahead of low -- proving the sort, not
        # first-appearance order (which would be high, low, mid).
        assert [p.player_id for p in result] == ["high", "mid", "low"]


# ── AC-4: perspective/role filter — two-perspective no double-count ────


class TestTwoPerspectiveNoDoubleCount:
    @pytest.fixture(autouse=True)
    def setup(self, db):
        _seed_season_and_teams(db, innings_per_game=7)
        _insert_player(db, "p1", "Ace", "Smith")
        _insert_player(db, "opp_bat", "Opp", "Batter", team_id=OPPONENT)
        _insert_game(db, "g1", "2026-03-10")

        # Same game loaded from BOTH perspectives.
        _insert_pitching_line(
            db, "g1", "p1", perspective_team_id=SCOUTED,
            ip_outs=18, so=6, bb=1, h=3, r=1, er=1, bf=20, appearance_order=1,
        )
        _insert_pitching_line(
            db, "g1", "p1", perspective_team_id=OPPONENT,
            ip_outs=18, so=6, bb=1, h=3, r=1, er=1, bf=20, appearance_order=1,
        )
        # Plays from both perspectives (same real PAs, distinct perspective).
        for persp in (SCOUTED, OPPONENT):
            _insert_play(
                db, "g1", 1, "p1", perspective_team_id=persp,
                outcome="Home Run", is_first_pitch_strike=1,
            )
            _insert_play(
                db, "g1", 2, "p1", perspective_team_id=persp,
                outcome="Strikeout", is_first_pitch_strike=1,
            )
        db.commit()

    def test_single_set_of_outings(self, db):
        result = build_pitcher_outings(db, SCOUTED, "2026")
        assert len(result) == 1
        assert len(result[0].outings) == 1  # NOT doubled

    def test_plays_not_double_counted(self, db):
        outing = build_pitcher_outings(db, SCOUTED, "2026")[0].outings[0]
        assert outing.hr_allowed == 1        # NOT 2
        assert outing.xbh_allowed == 1       # the HR is an XBH; NOT 2 (deduped)
        assert outing.charted_pa == 2        # NOT 4
        assert outing.fps_pct == pytest.approx(1.0)

    def test_xbh_not_double_counted(self, db):
        # AC-7: a non-HR XBH (Double) loaded from BOTH perspectives must count
        # once.  The setup already has one HR (also an XBH) from both
        # perspectives; adding a Double from both perspectives -> xbh_allowed = 2
        # (1 HR + 1 Double), each deduped by the perspective/role clause.
        for persp in (SCOUTED, OPPONENT):
            _insert_play(
                db, "g1", 3, "p1", perspective_team_id=persp,
                outcome="Double", is_first_pitch_strike=0,
            )
        db.commit()
        outing = build_pitcher_outings(db, SCOUTED, "2026")[0].outings[0]
        assert outing.xbh_allowed == 2       # HR + Double, NOT 4
        assert outing.hr_allowed == 1        # HR still deduped, Double not an HR

    def test_role_clause_excludes_scouted_batting_plays(self, db):
        # A stray play where the scouted team is BATTING must never count toward
        # a scouted pitcher's outing (the batting_team_id != scouted role clause).
        _insert_play(
            db, "g1", 3, "p1", batting_team_id=SCOUTED,
            perspective_team_id=SCOUTED, outcome="Home Run",
            is_first_pitch_strike=1,
        )
        db.commit()
        outing = build_pitcher_outings(db, SCOUTED, "2026")[0].outings[0]
        assert outing.hr_allowed == 1        # still 1, stray row excluded
        assert outing.xbh_allowed == 1       # stray scouted-batting HR excluded
        assert outing.charted_pa == 2


# ── AC-1 / AC-2: #P and S% (boxscore, denominator-governed) ────────────


class TestPitchCountAndStrikePct:
    def _outing(self, db, **line):
        _seed_season_and_teams(db, innings_per_game=7)
        _insert_player(db, "p1", "Ace", "Smith")
        _insert_game(db, "g1", "2026-03-10")
        _insert_pitching_line(db, "g1", "p1", appearance_order=1, **line)
        db.commit()
        return build_pitcher_outings(db, SCOUTED, "2026")[0].outings[0]

    def test_pitch_count_integer_when_reported(self, db):
        outing = self._outing(db, ip_outs=18, pitches=85, total_strikes=55)
        assert outing.pitches == 85

    def test_pitch_count_none_when_zero(self, db):
        # A stored 0 is "not reported" (the loader coerces an absent count to 0),
        # so #P collapses to None -> the renderer em-dashes it (AC-1).
        outing = self._outing(db, ip_outs=18, pitches=0, total_strikes=0)
        assert outing.pitches is None

    def test_pitch_count_none_when_null(self, db):
        # Defensive: a stray legacy NULL is also falsy -> None (one falsy check).
        outing = self._outing(db, ip_outs=18, pitches=None, total_strikes=None)
        assert outing.pitches is None

    def test_strike_pct_from_boxscore(self, db):
        # S% = total_strikes / pitches = 55 / 85.
        outing = self._outing(db, ip_outs=18, pitches=85, total_strikes=55)
        assert outing.strike_pct == pytest.approx(55 / 85)

    def test_strike_pct_none_when_pitches_zero(self, db):
        # Falsy denominator -> None (em-dash), NOT a divide-by-zero (AC-2).
        outing = self._outing(db, ip_outs=18, pitches=0, total_strikes=0)
        assert outing.strike_pct is None

    def test_strike_pct_none_when_pitches_null(self, db):
        outing = self._outing(db, ip_outs=18, pitches=None, total_strikes=10)
        assert outing.strike_pct is None

    def test_strike_pct_legitimate_zero_when_no_strikes(self, db):
        # total_strikes == 0 with pitches > 0 -> a REAL 0% (all-balls wildness),
        # NOT em-dashed (AC-2): 0.0, distinct from the None em-dash case above.
        outing = self._outing(db, ip_outs=1, pitches=6, total_strikes=0)
        assert outing.strike_pct == pytest.approx(0.0)
        assert outing.strike_pct is not None


# ── AC-3: S/R (start vs relief from appearance_order) ──────────────────


class TestStartRelief:
    def _outing(self, db, *, appearance_order):
        _seed_season_and_teams(db, innings_per_game=7)
        _insert_player(db, "p1", "Ace", "Smith")
        _insert_game(db, "g1", "2026-03-10")
        _insert_pitching_line(
            db, "g1", "p1", ip_outs=9, appearance_order=appearance_order,
        )
        db.commit()
        return build_pitcher_outings(db, SCOUTED, "2026")[0].outings[0]

    def test_starter_is_s(self, db):
        assert self._outing(db, appearance_order=1).start_relief == "S"

    def test_reliever_is_r(self, db):
        assert self._outing(db, appearance_order=2).start_relief == "R"

    def test_later_reliever_is_r(self, db):
        assert self._outing(db, appearance_order=4).start_relief == "R"

    def test_null_appearance_order_is_none_not_r(self, db):
        # NULL must NOT default to "R" (fabricating a role) -> None (em-dash).
        assert self._outing(db, appearance_order=None).start_relief is None


# ── AC-4: Outcome (team W/L/T) + Score (scouted-first) ─────────────────


class TestOutcomeAndScore:
    def _outing(self, db, *, home_team_id, away_team_id, home_score, away_score):
        _seed_season_and_teams(db, innings_per_game=7)
        _insert_player(db, "p1", "Ace", "Smith")
        _insert_game(
            db, "g1", "2026-03-10",
            home_team_id=home_team_id, away_team_id=away_team_id,
            home_score=home_score, away_score=away_score,
        )
        _insert_pitching_line(db, "g1", "p1", ip_outs=18, appearance_order=1)
        db.commit()
        return build_pitcher_outings(db, SCOUTED, "2026")[0].outings[0]

    def test_scouted_home_win(self, db):
        outing = self._outing(
            db, home_team_id=SCOUTED, away_team_id=OPPONENT,
            home_score=7, away_score=3,
        )
        assert outing.outcome == "W"
        assert outing.score == "7-3"   # scouted (home) runs first

    def test_scouted_home_loss(self, db):
        outing = self._outing(
            db, home_team_id=SCOUTED, away_team_id=OPPONENT,
            home_score=2, away_score=5,
        )
        assert outing.outcome == "L"
        assert outing.score == "2-5"

    def test_scouted_away_win_score_orientation(self, db):
        # Scouted is the AWAY team -> its runs still render FIRST in the score.
        outing = self._outing(
            db, home_team_id=OPPONENT, away_team_id=SCOUTED,
            home_score=3, away_score=7,
        )
        assert outing.outcome == "W"
        assert outing.score == "7-3"   # scouted (away) runs first, NOT "3-7"

    def test_tie(self, db):
        outing = self._outing(
            db, home_team_id=SCOUTED, away_team_id=OPPONENT,
            home_score=4, away_score=4,
        )
        assert outing.outcome == "T"
        assert outing.score == "4-4"

    def test_null_scores_are_none(self, db):
        # NULL scores -> Outcome and Score both None (never fabricated).
        outing = self._outing(
            db, home_team_id=SCOUTED, away_team_id=OPPONENT,
            home_score=None, away_score=None,
        )
        assert outing.outcome is None
        assert outing.score is None


# ── AC-5: XBH (plays-derived, 2B+3B+HR) ────────────────────────────────


class TestXbhAllowed:
    def _outing(self, db, *, play_outcomes):
        _seed_season_and_teams(db, innings_per_game=7)
        _insert_player(db, "p1", "Ace", "Smith")
        _insert_player(db, "opp_bat", "Opp", "Batter", team_id=OPPONENT)
        _insert_game(db, "g1", "2026-03-10")
        _insert_pitching_line(db, "g1", "p1", ip_outs=18, bf=20, appearance_order=1)
        for i, outcome in enumerate(play_outcomes, start=1):
            _insert_play(db, "g1", i, "p1", outcome=outcome)
        db.commit()
        return build_pitcher_outings(db, SCOUTED, "2026")[0].outings[0]

    def test_counts_double_triple_homerun(self, db):
        # 2B + 3B + HR = 3 XBH; the Single and Strikeout are excluded.
        outing = self._outing(
            db, play_outcomes=["Double", "Triple", "Home Run", "Single", "Strikeout"],
        )
        assert outing.xbh_allowed == 3
        # HR <= XBH <= H (per-row consistency): the HR is one of the 3 XBH.
        assert outing.hr_allowed == 1

    def test_zero_when_no_extra_base_hits(self, db):
        outing = self._outing(db, play_outcomes=["Single", "Walk", "Strikeout"])
        assert outing.xbh_allowed == 0

    def test_hr_is_subset_of_xbh(self, db):
        outing = self._outing(db, play_outcomes=["Home Run", "Home Run"])
        assert outing.hr_allowed == 2
        assert outing.xbh_allowed == 2   # both HRs are XBH


# ── Scope isolation + empty result ─────────────────────────────────────


class TestScopeIsolation:
    def test_empty_when_no_pitchers(self, db):
        _seed_season_and_teams(db, innings_per_game=7)
        db.commit()
        assert build_pitcher_outings(db, SCOUTED, "2026") == []

    def test_season_filter_isolates_boxscore_and_plays(self, db):
        # Two seasons for the same pitcher; the query must not bleed the other
        # season's outing or its plays-derived HR into the target season.
        _seed_season_and_teams(db, season_id="2026", innings_per_game=7)
        db.execute(
            "INSERT OR IGNORE INTO seasons (season_id, name, year) VALUES ('2025', '2025', 2025)"
        )
        _insert_player(db, "p1", "Ace", "Smith")
        _insert_player(db, "opp_bat", "Opp", "Batter", team_id=OPPONENT)

        _insert_game(db, "g2026", "2026-03-10", season_id="2026")
        _insert_pitching_line(db, "g2026", "p1", ip_outs=18, so=5, bf=20, appearance_order=1)
        _insert_play(db, "g2026", 1, "p1", season_id="2026", outcome="Home Run")

        _insert_game(db, "g2025", "2025-03-10", season_id="2025")
        _insert_pitching_line(db, "g2025", "p1", ip_outs=18, so=5, bf=20, appearance_order=1)
        _insert_play(db, "g2025", 1, "p1", season_id="2025", outcome="Home Run")
        _insert_play(db, "g2025", 2, "p1", season_id="2025", outcome="Home Run")
        db.commit()

        result = build_pitcher_outings(db, SCOUTED, "2026")
        assert len(result) == 1
        assert len(result[0].outings) == 1
        assert result[0].outings[0].game_id == "g2026"
        assert result[0].outings[0].hr_allowed == 1   # NOT 3 (2025 HRs excluded)
        assert result[0].season.games == 1


# ── Excluded stats are absent ──────────────────────────────────────────


class TestExcludedStatsAbsent:
    def test_no_excluded_fields_on_dataclasses(self):
        outing_fields = set(Outing.__dataclass_fields__)
        season_fields = set(SeasonSummary.__dataclass_fields__)
        # E-266-06 ADDS S% (strike_pct) as a legitimate field, so it is no longer
        # forbidden.  The pitcher's win/loss ``decision`` stays excluded: the new
        # Outcome field is the TEAM result (W/L/T), NOT the pitcher's decision.
        forbidden = {
            "velocity", "pitch_speed_mph", "pitch_type", "pitch_mix",
            "decision", "w", "l", "sv", "save",
        }
        assert forbidden.isdisjoint(outing_fields)
        assert forbidden.isdisjoint(season_fields)
