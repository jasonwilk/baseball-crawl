"""Tests for the deterministic rotation analysis engine (Tier 1).

Tests ``compute_starter_prediction()`` and supporting functions in
``src/reports/starter_prediction.py``.
"""

from __future__ import annotations

import datetime

import pytest

from src.api.db import build_pitcher_profiles
from src.reports.starter_prediction import (
    LEGION,
    NSAA_POST_APRIL,
    NSAA_PRE_APRIL,
    RestTier,
    StarterPrediction,
    _is_excluded,
    _is_nsaa_excluded,
    compute_starter_prediction,
    get_nsaa_rules,
    is_predicted_starter_enabled,
)


# ── Test data builders ──────────────────────────────────────────────────


def _make_appearance(
    player_id: str,
    game_id: str,
    game_date: str,
    *,
    first_name: str = "",
    last_name: str = "",
    jersey_number: str | None = None,
    start_time: str | None = None,
    ip_outs: int = 0,
    pitches: int | None = None,
    so: int = 0,
    bb: int = 0,
    h: int = 0,
    r: int = 0,
    er: int = 0,
    bf: int | None = None,
    decision: str | None = None,
    appearance_order: int | None = None,
    rest_days: int | None = None,
    team_game_number: int = 1,
) -> dict:
    return {
        "player_id": player_id,
        "first_name": first_name or player_id.title(),
        "last_name": last_name or "Player",
        "jersey_number": jersey_number,
        "game_id": game_id,
        "game_date": game_date,
        "start_time": start_time,
        "ip_outs": ip_outs,
        "pitches": pitches,
        "so": so,
        "bb": bb,
        "h": h,
        "r": r,
        "er": er,
        "bf": bf,
        "decision": decision,
        "appearance_order": appearance_order,
        "rest_days": rest_days,
        "team_game_number": team_game_number,
    }


def _build_rotation_history(
    starters: list[str],
    dates: list[str],
    *,
    reliever: str | None = None,
    starter_ip: int = 18,
    starter_pitches: int = 80,
    starter_so: int = 5,
    reliever_ip: int = 3,
    reliever_pitches: int = 15,
) -> list[dict]:
    """Build a pitching history for a simple rotation pattern.

    Args:
        starters: list of player_ids in rotation order, one per game.
        dates: list of game dates matching starters.
        reliever: optional single reliever who appears in every game.
    """
    history: list[dict] = []
    pitcher_last_date: dict[str, str] = {}

    for i, (starter_pid, game_date) in enumerate(zip(starters, dates)):
        game_id = f"g{i + 1:02d}"
        game_num = i + 1

        # Starter appearance
        rest = None
        if starter_pid in pitcher_last_date:
            d1 = datetime.date.fromisoformat(pitcher_last_date[starter_pid])
            d2 = datetime.date.fromisoformat(game_date)
            rest = (d2 - d1).days
        history.append(_make_appearance(
            starter_pid, game_id, game_date,
            ip_outs=starter_ip, pitches=starter_pitches, so=starter_so,
            bb=2, h=4, r=2, er=1, bf=22,
            appearance_order=1, decision="W",
            rest_days=rest, team_game_number=game_num,
        ))
        pitcher_last_date[starter_pid] = game_date

        # Reliever
        if reliever and reliever != starter_pid:
            r_rest = None
            if reliever in pitcher_last_date:
                d1 = datetime.date.fromisoformat(pitcher_last_date[reliever])
                d2 = datetime.date.fromisoformat(game_date)
                r_rest = (d2 - d1).days
            history.append(_make_appearance(
                reliever, game_id, game_date,
                ip_outs=reliever_ip, pitches=reliever_pitches, so=1,
                bb=0, h=1, r=0, er=0, bf=4,
                appearance_order=2,
                rest_days=r_rest, team_game_number=game_num,
            ))
            pitcher_last_date[reliever] = game_date

    return history


# ── AC-13: Clear 3-man rotation ─────────────────────────────────────────


class TestThreeManRotation:
    """A-B-C-A-B-C pattern over 12 games.

    Uses 70 pitches (below the 75-pitch exclusion threshold) so that
    pitchers with 3-day rest are not excluded by the 75+/4-day gate.
    Charlie starts the last game and is excluded by within-1-day;
    ace and bravo remain as candidates.
    """

    @pytest.fixture
    def prediction(self):
        rotation = ["ace", "bravo", "charlie"] * 4
        dates = [
            "2026-03-10", "2026-03-13", "2026-03-16",
            "2026-03-19", "2026-03-22", "2026-03-25",
            "2026-03-28", "2026-03-31", "2026-04-03",
            "2026-04-06", "2026-04-09", "2026-04-12",
        ]
        history = _build_rotation_history(rotation, dates, starter_pitches=70)
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 4, 12),
        )

    def test_pattern_detected(self, prediction):
        assert prediction.rotation_pattern == "3-man rotation"

    def test_predicts_next_in_rotation(self, prediction):
        # Last starter was charlie (game 12). Next should be ace.
        assert prediction.predicted_starter is not None
        assert prediction.predicted_starter["player_id"] == "ace"

    def test_confidence_high(self, prediction):
        assert prediction.confidence == "high"

    def test_candidates_populated(self, prediction):
        # Charlie excluded (0 days rest), ace and bravo remain
        assert len(prediction.top_candidates) >= 2

    def test_rest_table_populated(self, prediction):
        assert len(prediction.rest_table) > 0


# ── AC-13: 2-man rotation ──────────────────────────────────────────────


class TestTwoManRotation:
    """A-B-A-B pattern over 8 games.

    Uses 70 pitches so alpha (3 days rest) is not excluded by 75+/4-day.
    Bravo starts last game and is excluded by within-1-day.
    """

    @pytest.fixture
    def prediction(self):
        rotation = ["alpha", "bravo"] * 4
        dates = [
            "2026-03-10", "2026-03-13", "2026-03-16", "2026-03-19",
            "2026-03-22", "2026-03-25", "2026-03-28", "2026-03-31",
        ]
        history = _build_rotation_history(rotation, dates, starter_pitches=70)
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 3, 31),
        )

    def test_pattern_detected(self, prediction):
        assert prediction.rotation_pattern == "2-man rotation"

    def test_predicts_next(self, prediction):
        # Last starter was bravo (game 8, excluded). Alpha is next.
        assert prediction.predicted_starter is not None
        assert prediction.predicted_starter["player_id"] == "alpha"


# ── AC-13: Ace-dominant with GS% >= 70% workload flag ───────────────────


class TestAceDominant:
    """One pitcher has 7/10 starts (70%).

    "other" starts the last game so ace has rest and is predicted.
    """

    @pytest.fixture
    def prediction(self):
        # Ace starts 7 of 10 games, "other" starts 3 (including last game)
        rotation = [
            "ace", "ace", "ace", "ace", "other",
            "ace", "ace", "other", "ace", "other",
        ]
        dates = [
            "2026-03-10", "2026-03-13", "2026-03-16", "2026-03-19",
            "2026-03-22", "2026-03-25", "2026-03-28", "2026-03-31",
            "2026-04-03", "2026-04-06",
        ]
        history = _build_rotation_history(rotation, dates, starter_pitches=70)
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 4, 6),
        )

    def test_pattern_ace_dominant(self, prediction):
        assert prediction.rotation_pattern == "ace-dominant"

    def test_predicts_ace(self, prediction):
        assert prediction.predicted_starter is not None
        assert prediction.predicted_starter["player_id"] == "ace"

    def test_heavy_usage_flag(self, prediction):
        # GS% = 70% >= 70%, should flag heavy usage
        assert "heavy usage" in prediction.predicted_starter["reasoning"]


# ── AC-13: Committee (4 pitchers similar starts) ────────────────────────


class TestCommittee:
    """Four pitchers with similar start counts, no clear rotation."""

    @pytest.fixture
    def prediction(self):
        # 8 games, each pitcher starts 2 -- shuffled order (no cycle)
        rotation = ["p1", "p2", "p3", "p4", "p3", "p1", "p4", "p2"]
        dates = [
            "2026-03-10", "2026-03-13", "2026-03-16", "2026-03-19",
            "2026-03-22", "2026-03-25", "2026-03-28", "2026-03-31",
        ]
        history = _build_rotation_history(rotation, dates)
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 3, 31),
        )

    def test_pattern_committee(self, prediction):
        assert prediction.rotation_pattern == "committee"

    def test_confidence_low(self, prediction):
        assert prediction.confidence == "low"

    def test_no_predicted_starter(self, prediction):
        assert prediction.predicted_starter is None


# ── AC-13: Team with only 3 games (suppress) ───────────────────────────


class TestSuppressThreeGames:
    """Fewer than 4 games -> suppress."""

    @pytest.fixture
    def prediction(self):
        rotation = ["ace", "bravo", "charlie"]
        dates = ["2026-03-10", "2026-03-13", "2026-03-16"]
        history = _build_rotation_history(rotation, dates)
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 3, 16),
        )

    def test_confidence_suppress(self, prediction):
        assert prediction.confidence == "suppress"

    def test_predicted_starter_none(self, prediction):
        assert prediction.predicted_starter is None

    def test_rest_table_still_populated(self, prediction):
        assert len(prediction.rest_table) > 0

    def test_data_note_3_games(self, prediction):
        assert prediction.data_note is not None
        assert "3 games played" in prediction.data_note
        assert "rest data accumulating" in prediction.data_note


class TestSuppressTwoGames:
    """1-2 games -> suppress with different note."""

    @pytest.fixture
    def prediction(self):
        rotation = ["ace", "bravo"]
        dates = ["2026-03-10", "2026-03-13"]
        history = _build_rotation_history(rotation, dates)
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 3, 13),
        )

    def test_confidence_suppress(self, prediction):
        assert prediction.confidence == "suppress"

    def test_data_note_2_games(self, prediction):
        assert prediction.data_note is not None
        assert "2 game(s) played" in prediction.data_note

    def test_bullpen_order_populated(self, prediction):
        # With only starters, bullpen may be empty -- that's correct
        assert isinstance(prediction.bullpen_order, list)


class TestSuppressOneGame:
    """Single game -> suppress."""

    @pytest.fixture
    def prediction(self):
        rotation = ["ace"]
        dates = ["2026-03-10"]
        history = _build_rotation_history(rotation, dates)
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 3, 10),
        )

    def test_data_note_1_game(self, prediction):
        assert prediction.data_note is not None
        assert "1 game(s) played" in prediction.data_note


# ── AC-13: All NULL appearance_order ────────────────────────────────────


class TestNullAppearanceOrder:
    """Engine still produces a prediction when appearance_order is NULL."""

    @pytest.fixture
    def prediction(self):
        # 6 games, 2-man rotation, but all appearance_order = None
        # "ace" gets more IP (starter heuristic)
        history = []
        rotation = ["ace", "bravo"] * 3
        dates = [
            "2026-03-10", "2026-03-13", "2026-03-16",
            "2026-03-19", "2026-03-22", "2026-03-25",
        ]
        pitcher_last: dict[str, str] = {}
        for i, (starter, date) in enumerate(zip(rotation, dates)):
            gid = f"g{i + 1:02d}"
            gnum = i + 1
            reliever = "bravo" if starter == "ace" else "ace"
            s_rest = None
            if starter in pitcher_last:
                d1 = datetime.date.fromisoformat(pitcher_last[starter])
                d2 = datetime.date.fromisoformat(date)
                s_rest = (d2 - d1).days
            history.append(_make_appearance(
                starter, gid, date,
                ip_outs=18, pitches=80, so=5,
                appearance_order=None,
                rest_days=s_rest, team_game_number=gnum,
            ))
            pitcher_last[starter] = date
            r_rest = None
            if reliever in pitcher_last:
                d1 = datetime.date.fromisoformat(pitcher_last[reliever])
                d2 = datetime.date.fromisoformat(date)
                r_rest = (d2 - d1).days
            history.append(_make_appearance(
                reliever, gid, date,
                ip_outs=3, pitches=15, so=1,
                appearance_order=None,
                rest_days=r_rest, team_game_number=gnum,
            ))
            pitcher_last[reliever] = date

        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 3, 25),
        )

    def test_not_suppress(self, prediction):
        """Engine should not suppress with 6 games of data."""
        assert prediction.confidence != "suppress"

    def test_produces_prediction(self, prediction):
        assert prediction.rotation_pattern in (
            "2-man rotation", "ace-dominant", "3-man rotation", "committee"
        )


# ── AC-13: 10+ day gap flagged as availability unknown ──────────────────


class TestAvailabilityUnknown:
    """Pitcher with 10+ day gap gets availability unknown flag."""

    @pytest.fixture
    def prediction(self):
        # 5 games, ace starts first 3, then 12-day gap before game 4-5
        dates = [
            "2026-03-10", "2026-03-13", "2026-03-16",
            "2026-03-19", "2026-03-28",  # game 5 is 12 days after ace's last
        ]
        rotation = ["ace", "bravo", "ace", "bravo", "ace"]
        history = _build_rotation_history(rotation, dates)
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 3, 28),
        )

    @pytest.fixture
    def prediction_with_gap(self):
        """Pitcher with 10+ day gap."""
        dates = [
            "2026-03-10", "2026-03-13", "2026-03-16",
            "2026-03-19", "2026-03-22", "2026-04-02",
        ]
        # ace starts games 1,3,5 (last: Mar 22). bravo starts 2,4,6 (last: Apr 2).
        rotation = ["ace", "bravo", "ace", "bravo", "ace", "bravo"]
        history = _build_rotation_history(rotation, dates)
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 4, 2),
        )

    def test_gap_flagged(self, prediction_with_gap):
        """Ace's last game is Mar 22, latest is Apr 2 = 11 days."""
        # Find ace in candidates
        ace_cand = None
        for c in prediction_with_gap.top_candidates:
            if c["player_id"] == "ace":
                ace_cand = c
                break
        assert ace_cand is not None
        assert "availability unknown" in ace_cand["reasoning"]


# ── AC-1: Low pitch count (1-30) yesterday → NOT excluded ─────────────


class TestLowPitchYesterdayNotExcluded:
    """Pitcher who threw 1-30 pitches yesterday is NOT excluded (NSAA 0-day rest)."""

    @pytest.fixture
    def prediction(self):
        dates = [
            "2026-03-10", "2026-03-13", "2026-03-16", "2026-03-19",
            "2026-03-22", "2026-03-25", "2026-03-28", "2026-03-29",
        ]
        rotation = ["ace", "bravo", "ace", "bravo", "ace", "bravo", "ace", "bravo"]
        history = _build_rotation_history(rotation, dates, starter_pitches=20)
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 3, 29),
        )

    def test_ace_not_excluded(self, prediction):
        """Ace threw 20 pitches yesterday → 1-30 tier → 0 days rest → available."""
        candidate_ids = [c["player_id"] for c in prediction.top_candidates]
        # Bravo also pitched yesterday with 20 pitches (0 rest needed) so
        # both should be available; ace is in candidates.
        assert "ace" in candidate_ids


# ── AC-2: NSAA rest-tier exclusion ────────────────────────────────────


class TestNSAARestTierExclusion:
    """55 pitches with 1 day rest → excluded (needs 2 days for 51-70 tier)."""

    @pytest.fixture
    def prediction(self):
        dates = [
            "2026-03-10", "2026-03-13", "2026-03-16", "2026-03-19",
            "2026-03-22", "2026-03-25", "2026-03-28", "2026-03-30",
        ]
        rotation = ["ace", "bravo", "ace", "bravo", "ace", "bravo", "ace", "bravo"]
        history = _build_rotation_history(
            rotation, dates, starter_pitches=55,
        )
        profiles = build_pitcher_profiles(history)
        # reference_date=Mar 30, ace last pitched Mar 28 (2 days rest),
        # bravo last pitched Mar 30 (0 days rest). 55 pitches → 51-70 → 2d rest.
        # Ace: 2 >= 2 → not excluded. Bravo: 0 < 2 → excluded.
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 3, 30),
        )

    def test_bravo_excluded_short_rest(self, prediction):
        """Bravo threw 55 pitches today (0 rest) → needs 2 → excluded."""
        candidate_ids = [c["player_id"] for c in prediction.top_candidates]
        assert "bravo" not in candidate_ids

    def test_ace_not_excluded_enough_rest(self, prediction):
        """Ace threw 55 pitches 2 days ago → needs 2 → exactly enough."""
        candidate_ids = [c["player_id"] for c in prediction.top_candidates]
        assert "ace" in candidate_ids


# ── AC-13: High pitch count reasoning flag ──────────────────────────────


class TestHighPitchCountFlag:
    """High pitch count last outing -> reasoning flag."""

    @pytest.fixture
    def prediction(self):
        dates = [
            "2026-03-10", "2026-03-13", "2026-03-16", "2026-03-19",
            "2026-03-22", "2026-03-25", "2026-03-28", "2026-04-02",
        ]
        rotation = ["ace", "bravo"] * 4
        # All games 70 pitches, except ace's last game (game 7) = 100 pitches
        history = _build_rotation_history(rotation, dates, starter_pitches=70)
        # Override ace's last start (game 7) to have high pitches
        for row in history:
            if row["game_id"] == "g07" and row["player_id"] == "ace":
                row["pitches"] = 100
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 4, 2),
        )

    def test_high_pitch_flag(self, prediction):
        ace_cand = None
        for c in prediction.top_candidates:
            if c["player_id"] == "ace":
                ace_cand = c
                break
        assert ace_cand is not None
        assert "high pitch count last outing" in ace_cand["reasoning"]


# ── AC-13: Low pitch count (<50) reasoning flag ─────────────────────────


class TestLowPitchCountFlag:
    """Low pitch count (<50) -> reasoning flag."""

    @pytest.fixture
    def prediction(self):
        dates = [
            "2026-03-10", "2026-03-13", "2026-03-16", "2026-03-19",
            "2026-03-22", "2026-03-25", "2026-03-28", "2026-04-02",
        ]
        rotation = ["ace", "bravo"] * 4
        history = _build_rotation_history(rotation, dates, starter_pitches=80)
        # Override ace's last start to have low pitches
        for row in history:
            if row["game_id"] == "g07" and row["player_id"] == "ace":
                row["pitches"] = 35
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 4, 2),
        )

    def test_low_pitch_flag(self, prediction):
        ace_cand = None
        for c in prediction.top_candidates:
            if c["player_id"] == "ace":
                ace_cand = c
                break
        assert ace_cand is not None
        assert "low pitch count last outing" in ace_cand["reasoning"]


# ── AC-13: Spot-starting reliever flagged as anomalous ──────────────────


class TestSpotStarterAnomaly:
    """A reliever who spot-starts gets an anomaly note."""

    @pytest.fixture
    def prediction(self):
        dates = [
            "2026-03-10", "2026-03-13", "2026-03-16", "2026-03-19",
            "2026-03-22", "2026-03-25", "2026-03-28", "2026-03-31",
        ]
        # Ace starts 7 of 8 games, reliever_guy gets 1 spot start
        rotation = ["ace", "ace", "ace", "reliever_guy",
                     "ace", "ace", "ace", "ace"]
        history = _build_rotation_history(rotation, dates, reliever="closer")
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 3, 31),
        )

    def test_spot_starter_flag(self, prediction):
        rg_cand = None
        for c in prediction.top_candidates:
            if c["player_id"] == "reliever_guy":
                rg_cand = c
                break
        assert rg_cand is not None
        assert "spot starter" in rg_cand["reasoning"]


# ── AC-13: Moderate confidence triggered by K/9 delta ───────────────────


class TestModerateK9Delta:
    """A rested starter with K/9 > 2.0 higher triggers moderate.

    3-man rotation (ace-bravo-charlie). Charlie starts last game (excluded).
    Both ace and bravo have 6 days rest and are available. Ace is the
    rotation pick; bravo's much higher K/9 triggers moderate confidence.
    """

    @pytest.fixture
    def prediction(self):
        dates = [
            "2026-03-10", "2026-03-13", "2026-03-16",
            "2026-03-19", "2026-03-22", "2026-03-25",
            "2026-03-28", "2026-03-31", "2026-04-03",
        ]
        rotation = ["ace", "bravo", "charlie"] * 3
        history = _build_rotation_history(
            rotation, dates, starter_pitches=70, starter_so=3,
        )
        # Override bravo's SO to be much higher -> higher K/9
        for row in history:
            if row["player_id"] == "bravo":
                row["so"] = 10  # high K/9
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 4, 3),
        )

    def test_moderate_confidence(self, prediction):
        assert prediction.confidence == "moderate"

    def test_alternative_is_high_k_pitcher(self, prediction):
        assert prediction.alternative is not None
        assert prediction.alternative["player_id"] == "bravo"


# ── AC-13: Bullpen order ranked correctly ───────────────────────────────


class TestBullpenOrder:
    """Bullpen order ranks relievers by first-relief frequency."""

    @pytest.fixture
    def prediction(self):
        dates = [
            "2026-03-10", "2026-03-13", "2026-03-16", "2026-03-19",
            "2026-03-22",
        ]
        rotation = ["ace"] * 5
        # Build base history with ace as starter
        history = _build_rotation_history(rotation, dates)
        # Add multiple relievers with varying frequency
        pitcher_last: dict[str, str] = {}
        for i, date in enumerate(dates):
            gid = f"g{i + 1:02d}"
            gnum = i + 1
            # closer appears as first reliever (order=2) in games 1-4
            if i < 4:
                r_rest = None
                if "closer" in pitcher_last:
                    d1 = datetime.date.fromisoformat(pitcher_last["closer"])
                    d2 = datetime.date.fromisoformat(date)
                    r_rest = (d2 - d1).days
                history.append(_make_appearance(
                    "closer", gid, date,
                    ip_outs=3, pitches=15, so=1,
                    appearance_order=2,
                    rest_days=r_rest, team_game_number=gnum,
                ))
                pitcher_last["closer"] = date
            # setup appears as first reliever (order=2) in game 5 only
            if i == 4:
                history.append(_make_appearance(
                    "setup", gid, date,
                    ip_outs=3, pitches=15, so=1,
                    appearance_order=2,
                    rest_days=None, team_game_number=gnum,
                ))

        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 3, 22),
        )

    def test_bullpen_ranked(self, prediction):
        assert len(prediction.bullpen_order) >= 2
        assert prediction.bullpen_order[0]["name"] == "Closer Player"
        assert prediction.bullpen_order[0]["frequency"] == 4
        assert prediction.bullpen_order[1]["name"] == "Setup Player"
        assert prediction.bullpen_order[1]["frequency"] == 1

    def test_bullpen_games_sampled(self, prediction):
        for entry in prediction.bullpen_order:
            assert "games_sampled" in entry
            assert entry["games_sampled"] == 5


# ── AC-13: Tournament density flag ──────────────────────────────────────


class TestTournamentDensity:
    """3+ games on consecutive days triggers tournament flag."""

    @pytest.fixture
    def prediction(self):
        # 7 games total, last 3 on consecutive days
        dates = [
            "2026-03-10", "2026-03-14", "2026-03-18", "2026-03-22",
            "2026-03-26", "2026-03-27", "2026-03-28",
        ]
        rotation = ["ace", "bravo", "charlie", "ace",
                     "bravo", "charlie", "ace"]
        history = _build_rotation_history(rotation, dates)
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 3, 28),
        )

    def test_tournament_note(self, prediction):
        assert prediction.data_note is not None
        assert "Compressed schedule" in prediction.data_note


# ── AC-13: Mixed starts/relief for same pitcher ────────────────────────


class TestMixedStartsRelief:
    """Pitcher who both starts and relieves.

    Ace starts and also relieves. Charlie starts the last game (no ace
    or bravo), so ace has rest and appears as a candidate.
    """

    @pytest.fixture
    def prediction(self):
        dates = [
            "2026-03-10", "2026-03-14", "2026-03-18", "2026-03-22",
            "2026-03-26", "2026-03-30", "2026-04-03",
        ]
        # ace starts g1,g3,g5 and relieves in g2,g4 (bravo's games).
        # bravo starts g2,g4. charlie starts g6,g7 so ace has rest.
        history = []
        pitcher_last: dict[str, str] = {}
        starters = ["ace", "bravo", "ace", "bravo", "ace", "charlie", "charlie"]
        for i, (starter, date) in enumerate(zip(starters, dates)):
            gid = f"g{i + 1:02d}"
            gnum = i + 1

            s_rest = None
            if starter in pitcher_last:
                d1 = datetime.date.fromisoformat(pitcher_last[starter])
                d2 = datetime.date.fromisoformat(date)
                s_rest = (d2 - d1).days
            history.append(_make_appearance(
                starter, gid, date,
                ip_outs=18, pitches=70, so=5,
                appearance_order=1, rest_days=s_rest,
                team_game_number=gnum,
            ))
            pitcher_last[starter] = date

            # Ace relieves in bravo's starts (g2, g4) only
            if starter == "bravo":
                r_rest = None
                if "ace" in pitcher_last:
                    d1 = datetime.date.fromisoformat(pitcher_last["ace"])
                    d2 = datetime.date.fromisoformat(date)
                    r_rest = (d2 - d1).days
                history.append(_make_appearance(
                    "ace", gid, date,
                    ip_outs=3, pitches=15, so=1,
                    appearance_order=2, rest_days=r_rest,
                    team_game_number=gnum,
                ))
                pitcher_last["ace"] = date

        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 4, 3),
        )

    def test_mixed_pitcher_counted(self, prediction):
        """Ace should have both starts and relief appearances."""
        ace_cand = None
        for c in prediction.top_candidates:
            if c["player_id"] == "ace":
                ace_cand = c
                break
        assert ace_cand is not None
        assert ace_cand["games_started"] == 3


# ── AC-9: Recent starts game logs ──────────────────────────────────────


class TestRecentStarts:
    """Each candidate has recent_starts with correct fields.

    Ace starts 6 games, then "other" starts game 7 so ace has rest and
    is predicted as the next starter.
    """

    @pytest.fixture
    def prediction(self):
        rotation = ["ace"] * 6 + ["other"]
        dates = [
            "2026-03-10", "2026-03-14", "2026-03-18",
            "2026-03-22", "2026-03-26", "2026-03-30",
            "2026-04-03",
        ]
        history = _build_rotation_history(rotation, dates, starter_pitches=70)
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 4, 3),
        )

    def test_recent_starts_fields(self, prediction):
        assert prediction.predicted_starter is not None
        recent = prediction.predicted_starter["recent_starts"]
        assert len(recent) >= 3
        assert len(recent) <= 5
        for entry in recent:
            assert "game_date" in entry
            assert "ip_outs" in entry
            assert "pitches" in entry
            assert "so" in entry
            assert "bb" in entry
            assert "decision" in entry
            assert "rest_days_from_previous_start" in entry

    def test_rest_days_from_previous_start(self, prediction):
        recent = prediction.predicted_starter["recent_starts"]
        # First entry may have None rest if it's the first start
        for entry in recent[1:]:
            assert entry["rest_days_from_previous_start"] == 4


# ── AC-10: Rest table with workload data ────────────────────────────────


class TestRestTableWithWorkload:
    """Rest table sources workload data from get_pitching_workload output."""

    @pytest.fixture
    def prediction(self):
        rotation = ["ace", "bravo"] * 3
        dates = [
            "2026-03-10", "2026-03-13", "2026-03-16",
            "2026-03-19", "2026-03-22", "2026-03-25",
        ]
        history = _build_rotation_history(rotation, dates, reliever="closer")
        profiles = build_pitcher_profiles(history)
        workload = {
            "ace": {
                "last_outing_date": "2026-03-22",
                "last_outing_days_ago": 3,
                "pitches_7d": 80,
                "span_days_7d": 1,
                "appearances_7d": 1,
            },
            "bravo": {
                "last_outing_date": "2026-03-25",
                "last_outing_days_ago": 0,
                "pitches_7d": 80,
                "span_days_7d": 1,
                "appearances_7d": 1,
            },
        }
        return compute_starter_prediction(
            profiles, history,
            reference_date=datetime.date(2026, 3, 25),
            workload=workload,
        )

    def test_rest_table_has_workload_fields(self, prediction):
        assert len(prediction.rest_table) > 0
        for entry in prediction.rest_table:
            assert "last_outing_date" in entry
            assert "days_since_last_appearance" in entry
            assert "last_outing_pitches" in entry
            assert "workload_7d" in entry
            assert "games_started" in entry

    def test_rest_table_workload_populated(self, prediction):
        ace_entry = None
        for e in prediction.rest_table:
            if "Ace" in e["name"]:
                ace_entry = e
                break
        assert ace_entry is not None
        assert ace_entry["last_outing_date"] == "2026-03-22"
        assert ace_entry["days_since_last_appearance"] == 3
        assert ace_entry["workload_7d"] == 80

    def test_rest_table_last_outing_pitches_from_history(self, prediction):
        """last_outing_pitches comes from history, not workload."""
        for entry in prediction.rest_table:
            # All starters had 80 pitches per game
            if entry["games_started"] > 0:
                assert entry["last_outing_pitches"] == 80


class TestRestTableWithoutWorkload:
    """Rest table works when workload is None."""

    @pytest.fixture
    def prediction(self):
        rotation = ["ace", "bravo"] * 3
        dates = [
            "2026-03-10", "2026-03-13", "2026-03-16",
            "2026-03-19", "2026-03-22", "2026-03-25",
        ]
        history = _build_rotation_history(rotation, dates)
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history,
            reference_date=datetime.date(2026, 3, 25),
            workload=None,
        )

    def test_rest_table_populated(self, prediction):
        assert len(prediction.rest_table) > 0

    def test_workload_fields_none(self, prediction):
        for entry in prediction.rest_table:
            assert entry["last_outing_date"] is None
            assert entry["days_since_last_appearance"] is None
            assert entry["workload_7d"] is None


# ── AC-2: StarterPrediction dataclass fields ────────────────────────────


class TestDataclassStructure:
    """Verify StarterPrediction has all required fields."""

    def test_fields_present(self):
        pred = StarterPrediction(confidence="suppress")
        assert hasattr(pred, "confidence")
        assert hasattr(pred, "predicted_starter")
        assert hasattr(pred, "alternative")
        assert hasattr(pred, "top_candidates")
        assert hasattr(pred, "rotation_pattern")
        assert hasattr(pred, "rest_table")
        assert hasattr(pred, "bullpen_order")
        assert hasattr(pred, "data_note")

    def test_defaults(self):
        pred = StarterPrediction(confidence="low")
        assert pred.predicted_starter is None
        assert pred.alternative is None
        assert pred.top_candidates == []
        assert pred.rest_table == []
        assert pred.bullpen_order == []
        assert pred.data_note is None


# ── AC-4: reference_date anchors reasoning, not latest_game_date ──────


class TestReferenceDateAnchorsReasoning:
    """Prove rest days are computed from reference_date, not latest_game_date.

    Pitcher last appeared 2026-03-28. Team game on 2026-03-31 means
    latest_game_date = 2026-03-31. With reference_date = 2026-04-06,
    rest = 9 days (not 3).
    """

    @pytest.fixture
    def prediction(self):
        # 4 games minimum to avoid suppress path.
        # ace starts games 1-3, bravo starts game 4 (latest_game_date=2026-03-31).
        rotation = ["ace", "ace", "ace", "bravo"]
        dates = [
            "2026-03-19", "2026-03-22", "2026-03-28", "2026-03-31",
        ]
        history = _build_rotation_history(rotation, dates, starter_pitches=70)
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 4, 6),
        )

    def test_reasoning_uses_reference_date(self, prediction):
        """Ace's last appearance was 2026-03-28; reference_date=2026-04-06 -> 9 days rest."""
        ace_cand = None
        for c in prediction.top_candidates:
            if c["player_id"] == "ace":
                ace_cand = c
                break
        assert ace_cand is not None
        assert "9 days rest" in ace_cand["reasoning"]


# ── AC-2/AC-3: NSAA rest tier unit tests via _is_nsaa_excluded ────────


class TestNSAAExcludedUnit:
    """Direct unit tests for _is_nsaa_excluded covering rest tiers."""

    def _make_profile(
        self, pitches: int | None, game_date: str = "2026-03-28",
    ) -> dict:
        return {
            "total_starts": 3,
            "total_games": 3,
            "first_name": "Ace",
            "last_name": "Pitcher",
            "appearances": [
                {"game_date": game_date, "pitches": pitches},
            ],
        }

    # ── Pre-April tiers ────────────────────────────────────────────
    def test_pre_april_1_30_pitches_0_rest_ok(self):
        """1-30 pitches, 0 days rest → not excluded."""
        profile = self._make_profile(25, "2026-03-28")
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 3, 28))
        assert not excluded

    def test_pre_april_31_50_needs_1_day(self):
        """40 pitches, 0 days rest → excluded (needs 1)."""
        profile = self._make_profile(40, "2026-03-28")
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 3, 28))
        assert excluded
        assert "needs 1" in reason

    def test_pre_april_31_50_has_1_day_ok(self):
        """40 pitches, 1 day rest → not excluded."""
        profile = self._make_profile(40, "2026-03-28")
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 3, 29))
        assert not excluded

    def test_pre_april_51_70_needs_2(self):
        """60 pitches, 1 day rest → excluded (needs 2)."""
        profile = self._make_profile(60, "2026-03-28")
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 3, 29))
        assert excluded
        assert "needs 2" in reason

    def test_pre_april_71_90_needs_3(self):
        """80 pitches, 2 days rest → excluded (needs 3)."""
        profile = self._make_profile(80, "2026-03-28")
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 3, 30))
        assert excluded
        assert "needs 3" in reason

    def test_pre_april_71_90_has_3_ok(self):
        """80 pitches, 3 days rest → not excluded."""
        profile = self._make_profile(80, "2026-03-28")
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 3, 31))
        assert not excluded

    # ── Post-April tiers ───────────────────────────────────────────
    def test_post_april_91_110_needs_4(self):
        """100 pitches (post-April), 3 days rest → excluded (needs 4)."""
        profile = self._make_profile(100, "2026-04-10")
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 4, 13))
        assert excluded
        assert "needs 4" in reason

    def test_post_april_91_110_has_4_ok(self):
        """100 pitches (post-April), 4 days rest → not excluded."""
        profile = self._make_profile(100, "2026-04-10")
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 4, 14))
        assert not excluded

    # ── Null pitch count ───────────────────────────────────────────
    def test_null_pitch_count_excluded(self):
        """AC-9: null pitch count → excluded."""
        profile = self._make_profile(None, "2026-04-05")
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 4, 6))
        assert excluded
        assert "pitch count unavailable" in reason

    # ── Exceeds max pitches ───────────────────────────────────────
    def test_pre_april_exceeds_max_needs_max_rest(self):
        """95 pitches pre-April (max 90) → max tier rest (3 days)."""
        profile = self._make_profile(95, "2026-03-28")
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 3, 30))
        assert excluded
        assert "needs 3" in reason

    def test_pre_april_exceeds_max_with_enough_rest_ok(self):
        """95 pitches pre-April, 3 days rest → not excluded."""
        profile = self._make_profile(95, "2026-03-28")
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 3, 31))
        assert not excluded

    # ── No appearances ─────────────────────────────────────────────
    def test_no_appearances_not_excluded(self):
        profile = {
            "total_starts": 0, "total_games": 0,
            "first_name": "X", "last_name": "Y", "appearances": [],
        }
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 4, 6))
        assert not excluded


# ── AC-5 (E-214-02): Same history, different reference_date → different rest ─


class TestReferenceDateChangesRestInReasoning:
    """Same pitching history, two different reference_date values.

    Ace's last appearance is 2026-03-28. With reference_date=2026-04-02
    rest = 5 days. With reference_date=2026-04-06 rest = 9 days.
    Reasoning strings must reflect the respective reference_date.
    """

    def _build_history_and_profiles(self):
        rotation = ["ace", "ace", "ace", "bravo"]
        dates = ["2026-03-19", "2026-03-22", "2026-03-28", "2026-03-31"]
        history = _build_rotation_history(rotation, dates, starter_pitches=70)
        profiles = build_pitcher_profiles(history)
        return profiles, history

    def test_different_reference_dates_produce_different_rest(self):
        profiles, history = self._build_history_and_profiles()

        pred_early = compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 4, 2),
        )
        pred_late = compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 4, 6),
        )

        # Find ace in both predictions
        ace_early = next(
            c for c in pred_early.top_candidates if c["player_id"] == "ace"
        )
        ace_late = next(
            c for c in pred_late.top_candidates if c["player_id"] == "ace"
        )

        assert "5 days rest" in ace_early["reasoning"]
        assert "9 days rest" in ace_late["reasoning"]


# ── AC-6 (E-214-03): is_predicted_starter_enabled() ─────────────────────


class TestIsPredictedStarterEnabled:
    """Feature flag returns True only for 1/true/yes (case-insensitive)."""

    @pytest.mark.parametrize("val", ["1", "true", "yes", "TRUE", "True", "YES"])
    def test_enabled_values(self, monkeypatch, val):
        monkeypatch.setenv("FEATURE_PREDICTED_STARTER", val)
        assert is_predicted_starter_enabled() is True

    @pytest.mark.parametrize("val", ["", "0", "false", "no", "FALSE", "off"])
    def test_disabled_values(self, monkeypatch, val):
        monkeypatch.setenv("FEATURE_PREDICTED_STARTER", val)
        assert is_predicted_starter_enabled() is False

    def test_absent(self, monkeypatch):
        monkeypatch.delenv("FEATURE_PREDICTED_STARTER", raising=False)
        assert is_predicted_starter_enabled() is False


# ── AC-3: Pre/post April 1 rule selection ──────────────────────────────


class TestNSAARuleSelection:
    """get_nsaa_rules selects pre-April vs post-April based on date."""

    def test_pre_april(self):
        rules = get_nsaa_rules(datetime.date(2026, 3, 31))
        assert rules is NSAA_PRE_APRIL
        assert rules.max_pitches == 90
        assert len(rules.rest_tiers) == 4

    def test_post_april(self):
        rules = get_nsaa_rules(datetime.date(2026, 4, 1))
        assert rules is NSAA_POST_APRIL
        assert rules.max_pitches == 110
        assert len(rules.rest_tiers) == 5

    def test_year_parameterized(self):
        """April 1 boundary uses reference_date.year."""
        rules_2027 = get_nsaa_rules(datetime.date(2027, 3, 31))
        assert rules_2027 is NSAA_PRE_APRIL


# ── AC-4: Consecutive-days rule ────────────────────────────────────────


class TestConsecutiveDaysRule:
    """NSAA max 2 appearances in 3-day window {ref-2, ref-1, ref}."""

    def _make_profile_with_apps(self, app_dates: list[str]) -> dict:
        apps = [{"game_date": d, "pitches": 15} for d in app_dates]
        return {
            "total_starts": 0, "total_games": len(apps),
            "first_name": "Test", "last_name": "Pitcher",
            "appearances": apps,
        }

    def test_2_appearances_in_window_excluded(self):
        """2 appearances on ref-2 and ref-1 → pitching on ref = 3rd → excluded."""
        profile = self._make_profile_with_apps(
            ["2026-04-08", "2026-04-09"],
        )
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 4, 10))
        assert excluded
        assert "2 appearances" in reason

    def test_1_appearance_in_window_not_excluded(self):
        """1 appearance in window → ok."""
        profile = self._make_profile_with_apps(["2026-04-09"])
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 4, 10))
        assert not excluded

    def test_2_appearances_outside_window_not_excluded(self):
        """2 appearances on ref-3 and ref-4 → outside window → not excluded."""
        profile = self._make_profile_with_apps(
            ["2026-04-06", "2026-04-07"],
        )
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 4, 10))
        assert not excluded

    def test_doubleheader_counts_as_2_appearances(self):
        """Two appearances on the same day = 2 appearances (doubleheader)."""
        apps = [
            {"game_date": "2026-04-09", "pitches": 15},
            {"game_date": "2026-04-09", "pitches": 15},
        ]
        profile = {
            "total_starts": 0, "total_games": 2,
            "first_name": "Test", "last_name": "Pitcher",
            "appearances": apps,
        }
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 4, 10))
        assert excluded
        assert "2 appearances" in reason


# ── AC-2: Doubleheader pitch aggregation ───────────────────────────────


class TestDoubleheaderPitchAggregation:
    """Same-day pitches aggregated for rest-tier lookup."""

    def test_combined_pitches_determine_tier(self):
        """25 pitches game 1 + 30 game 2 = 55 → 51-70 tier → needs 2 days."""
        apps = [
            {"game_date": "2026-04-05", "pitches": 25},
            {"game_date": "2026-04-05", "pitches": 30},
        ]
        profile = {
            "total_starts": 0, "total_games": 2,
            "first_name": "Test", "last_name": "Pitcher",
            "appearances": apps,
        }
        # 1 day rest → needs 2 → excluded
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 4, 6))
        assert excluded
        assert "needs 2" in reason

    def test_combined_pitches_low_enough(self):
        """15 + 10 = 25 → 1-30 tier → 0 rest needed → ok after window."""
        apps = [
            {"game_date": "2026-04-05", "pitches": 15},
            {"game_date": "2026-04-05", "pitches": 10},
        ]
        profile = {
            "total_starts": 0, "total_games": 2,
            "first_name": "Test", "last_name": "Pitcher",
            "appearances": apps,
        }
        # Use ref 3 days later so doubleheader appearances are outside
        # the consecutive-days window (only rest-tier matters here).
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 4, 8))
        assert not excluded


# ── AC-9: Null pitch count edge cases ──────────────────────────────────


class TestNullPitchCount:
    """Null pitch count on most recent game date → unavailable."""

    def test_single_game_null(self):
        apps = [{"game_date": "2026-04-05", "pitches": None}]
        profile = {
            "total_starts": 1, "total_games": 1,
            "first_name": "Test", "last_name": "Pitcher",
            "appearances": apps,
        }
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 4, 6))
        assert excluded
        assert "pitch count unavailable" in reason

    def test_doubleheader_partial_null(self):
        """One game has data, other null → still excluded."""
        apps = [
            {"game_date": "2026-04-05", "pitches": 25},
            {"game_date": "2026-04-05", "pitches": None},
        ]
        profile = {
            "total_starts": 0, "total_games": 2,
            "first_name": "Test", "last_name": "Pitcher",
            "appearances": apps,
        }
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 4, 6))
        assert excluded
        assert "pitch count unavailable" in reason

    def test_older_null_not_affected(self):
        """Null on an older date, but most recent date has data → ok."""
        apps = [
            {"game_date": "2026-04-01", "pitches": None},
            {"game_date": "2026-04-05", "pitches": 20},
        ]
        profile = {
            "total_starts": 1, "total_games": 2,
            "first_name": "Test", "last_name": "Pitcher",
            "appearances": apps,
        }
        excluded, reason = _is_nsaa_excluded(profile, datetime.date(2026, 4, 7))
        assert not excluded


# ── AC-10: Relievers subject to same NSAA rules ───────────────────────


class TestRelieverExclusion:
    """Relievers are checked by NSAA rules, not skipped."""

    @pytest.fixture
    def prediction(self):
        dates = [
            "2026-04-01", "2026-04-04", "2026-04-07", "2026-04-10",
            "2026-04-13",
        ]
        rotation = ["ace"] * 5
        history = _build_rotation_history(
            rotation, dates, reliever="closer", reliever_pitches=80,
        )
        profiles = build_pitcher_profiles(history)
        # reference_date = Apr 14. Closer last pitched Apr 13 (1 day rest).
        # 80 pitches → 71-90 tier → needs 3 days rest → excluded.
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 4, 14),
        )

    def test_reliever_excluded_in_bullpen(self, prediction):
        """Closer threw 80 pitches yesterday → needs 3 days → unavailable in bullpen."""
        bp = prediction.bullpen_order
        assert len(bp) > 0
        closer_entry = next(b for b in bp if "Closer" in b["name"])
        assert closer_entry["available"] is False
        assert closer_entry["unavailability_reason"] is not None
        assert "needs 3" in closer_entry["unavailability_reason"]


# ── AC-5: Bullpen available/unavailable sorting ───────────────────────


class TestBullpenAvailabilitySorting:
    """Available pitchers sort before unavailable ones in bullpen order."""

    @pytest.fixture
    def prediction(self):
        dates = [
            "2026-04-01", "2026-04-03", "2026-04-05", "2026-04-07",
            "2026-04-09",
        ]
        rotation = ["ace"] * 5
        history = _build_rotation_history(rotation, dates)
        # Add two relievers: "closer" in all 5 games, "setup" in 3 games
        pitcher_last: dict[str, str] = {}
        for i, date in enumerate(dates):
            gid = f"g{i + 1:02d}"
            gnum = i + 1
            # closer appears as order=2 in all games, 80 pitches (high)
            r_rest = None
            if "closer" in pitcher_last:
                d1 = datetime.date.fromisoformat(pitcher_last["closer"])
                d2 = datetime.date.fromisoformat(date)
                r_rest = (d2 - d1).days
            history.append(_make_appearance(
                "closer", gid, date,
                ip_outs=3, pitches=80, so=1,
                appearance_order=2,
                rest_days=r_rest, team_game_number=gnum,
            ))
            pitcher_last["closer"] = date
            # setup appears in games 1-3 only, 15 pitches (low)
            if i < 3:
                sr_rest = None
                if "setup" in pitcher_last:
                    d1 = datetime.date.fromisoformat(pitcher_last["setup"])
                    d2 = datetime.date.fromisoformat(date)
                    sr_rest = (d2 - d1).days
                history.append(_make_appearance(
                    "setup", gid, date,
                    ip_outs=2, pitches=15, so=0,
                    appearance_order=2,
                    rest_days=sr_rest, team_game_number=gnum,
                ))
                pitcher_last["setup"] = date

        profiles = build_pitcher_profiles(history)
        # reference_date = Apr 10. Closer last pitched Apr 9 (1 day rest),
        # 80 pitches → needs 3 → excluded. Setup last pitched Apr 5 (5d rest),
        # 15 pitches → needs 0 → available.
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 4, 10),
        )

    def test_available_sorts_first(self, prediction):
        bp = prediction.bullpen_order
        assert len(bp) >= 2
        # Setup (available) should come before Closer (unavailable)
        setup_idx = next(i for i, b in enumerate(bp) if "Setup" in b["name"])
        closer_idx = next(i for i, b in enumerate(bp) if "Closer" in b["name"])
        assert setup_idx < closer_idx

    def test_bullpen_has_availability_fields(self, prediction):
        for entry in prediction.bullpen_order:
            assert "available" in entry
            assert "unavailability_reason" in entry

    def test_available_pitcher_fields(self, prediction):
        setup = next(b for b in prediction.bullpen_order if "Setup" in b["name"])
        assert setup["available"] is True
        assert setup["unavailability_reason"] is None

    def test_unavailable_pitcher_fields(self, prediction):
        closer = next(b for b in prediction.bullpen_order if "Closer" in b["name"])
        assert closer["available"] is False
        assert closer["unavailability_reason"] is not None


# ── Legion pitch count rules ──────────────────────────────────────────


class TestLegionConstants:
    """AC-1, AC-5: Legion rule set constants."""

    def test_legion_max_pitches(self):
        assert LEGION.max_pitches == 105

    def test_legion_rest_tiers(self):
        tiers = LEGION.rest_tiers
        assert len(tiers) == 5
        assert tiers[0] == RestTier(1, 30, 0)
        assert tiers[1] == RestTier(31, 45, 1)
        assert tiers[2] == RestTier(46, 60, 2)
        assert tiers[3] == RestTier(61, 80, 3)
        assert tiers[4] == RestTier(81, 105, 4)


class TestLegionExclusion:
    """AC-2 through AC-6: Legion-specific availability checks via _is_excluded."""

    def _make_profile(self, pitches: int, game_date: str) -> dict:
        return {
            "total_starts": 1,
            "total_games": 1,
            "appearances": [
                {"game_date": game_date, "pitches": pitches},
            ],
        }

    def _make_multi_day_profile(self, appearances: list[dict]) -> dict:
        return {
            "total_starts": len(appearances),
            "total_games": len(appearances),
            "appearances": appearances,
        }

    # ── AC-3: 48 pitches, 1 day rest → excluded under Legion ──────────

    def test_48_pitches_1_day_excluded_legion(self):
        """AC-3: 48 pitches, 1 day ago → excluded (46-60 tier = 2 days rest)."""
        profile = self._make_profile(48, "2026-04-05")
        excluded, reason = _is_excluded(profile, datetime.date(2026, 4, 6), LEGION)
        assert excluded is True
        assert "1d rest" in reason

    def test_48_pitches_1_day_available_nsaa(self):
        """AC-3 inverse: same pitcher available under NSAA (31-50 tier = 1 day)."""
        profile = self._make_profile(48, "2026-04-05")
        excluded, _reason = _is_nsaa_excluded(profile, datetime.date(2026, 4, 6))
        assert excluded is False

    def test_48_pitches_2_days_available_legion(self):
        """48 pitches, 2 days ago → available under Legion (2 days met)."""
        profile = self._make_profile(48, "2026-04-04")
        excluded, _reason = _is_excluded(profile, datetime.date(2026, 4, 6), LEGION)
        assert excluded is False

    # ── AC-4: 82 pitches, 3 days rest → excluded under Legion ─────────

    def test_82_pitches_3_days_excluded_legion(self):
        """AC-4: 82 pitches, 3 days ago → excluded (81+ tier = 4 days rest)."""
        profile = self._make_profile(82, "2026-04-03")
        excluded, reason = _is_excluded(profile, datetime.date(2026, 4, 6), LEGION)
        assert excluded is True
        assert "3d rest" in reason

    def test_82_pitches_3_days_available_nsaa(self):
        """AC-4 inverse: same pitcher available under NSAA pre-April (71-90 = 3 days)."""
        profile = self._make_profile(82, "2026-03-03")
        excluded, _reason = _is_nsaa_excluded(profile, datetime.date(2026, 3, 6))
        assert excluded is False

    def test_82_pitches_4_days_available_legion(self):
        """82 pitches, 4 days ago → available under Legion (4 days met)."""
        profile = self._make_profile(82, "2026-04-02")
        excluded, _reason = _is_excluded(profile, datetime.date(2026, 4, 6), LEGION)
        assert excluded is False

    # ── AC-6: Consecutive-days rule under Legion ──────────────────────

    def test_consecutive_days_excluded_legion(self):
        """AC-6: 2 appearances on prior 2 days → excluded (max 2 in 3-day window)."""
        profile = self._make_multi_day_profile([
            {"game_date": "2026-04-04", "pitches": 20},
            {"game_date": "2026-04-05", "pitches": 15},
        ])
        excluded, reason = _is_excluded(profile, datetime.date(2026, 4, 6), LEGION)
        assert excluded is True
        assert "3-day period" in reason

    # ── AC-8: Rest tier boundary edge cases ───────────────────────────

    def test_boundary_30_pitches_no_rest(self):
        """30 pitches → 0 days rest (top of tier 1)."""
        profile = self._make_profile(30, "2026-04-05")
        excluded, _reason = _is_excluded(profile, datetime.date(2026, 4, 6), LEGION)
        assert excluded is False

    def test_boundary_31_pitches_needs_1_day(self):
        """31 pitches → 1 day rest (bottom of tier 2)."""
        profile = self._make_profile(31, "2026-04-05")
        # 1 day elapsed, 1 day required → available
        excluded, _reason = _is_excluded(profile, datetime.date(2026, 4, 6), LEGION)
        assert excluded is False

    def test_boundary_31_pitches_0_days_excluded(self):
        """31 pitches, same day → excluded (needs 1 day)."""
        profile = self._make_profile(31, "2026-04-06")
        excluded, reason = _is_excluded(profile, datetime.date(2026, 4, 6), LEGION)
        assert excluded is True

    def test_boundary_45_pitches_needs_1_day(self):
        """45 pitches → 1 day rest (top of tier 2)."""
        profile = self._make_profile(45, "2026-04-05")
        excluded, _reason = _is_excluded(profile, datetime.date(2026, 4, 6), LEGION)
        assert excluded is False

    def test_boundary_46_pitches_needs_2_days(self):
        """46 pitches → 2 days rest (bottom of tier 3)."""
        profile = self._make_profile(46, "2026-04-05")
        # 1 day elapsed, 2 required → excluded
        excluded, _reason = _is_excluded(profile, datetime.date(2026, 4, 6), LEGION)
        assert excluded is True

    def test_boundary_60_pitches_needs_2_days(self):
        """60 pitches → 2 days rest (top of tier 3)."""
        profile = self._make_profile(60, "2026-04-04")
        # 2 days elapsed, 2 required → available
        excluded, _reason = _is_excluded(profile, datetime.date(2026, 4, 6), LEGION)
        assert excluded is False

    def test_boundary_61_pitches_needs_3_days(self):
        """61 pitches → 3 days rest (bottom of tier 4)."""
        profile = self._make_profile(61, "2026-04-04")
        # 2 days elapsed, 3 required → excluded
        excluded, _reason = _is_excluded(profile, datetime.date(2026, 4, 6), LEGION)
        assert excluded is True

    def test_boundary_80_pitches_needs_3_days(self):
        """80 pitches → 3 days rest (top of tier 4)."""
        profile = self._make_profile(80, "2026-04-03")
        # 3 days elapsed, 3 required → available
        excluded, _reason = _is_excluded(profile, datetime.date(2026, 4, 6), LEGION)
        assert excluded is False

    def test_boundary_81_pitches_needs_4_days(self):
        """81 pitches → 4 days rest (bottom of tier 5)."""
        profile = self._make_profile(81, "2026-04-03")
        # 3 days elapsed, 4 required → excluded
        excluded, _reason = _is_excluded(profile, datetime.date(2026, 4, 6), LEGION)
        assert excluded is True

    def test_boundary_105_pitches_needs_4_days(self):
        """105 pitches → 4 days rest (max pitches)."""
        profile = self._make_profile(105, "2026-04-02")
        # 4 days elapsed, 4 required → available
        excluded, _reason = _is_excluded(profile, datetime.date(2026, 4, 6), LEGION)
        assert excluded is False

    def test_over_105_applies_max_rest(self):
        """Pitches exceeding max (e.g., 110) still apply 4-day max rest."""
        profile = self._make_profile(110, "2026-04-03")
        # 3 days elapsed, 4 required → excluded
        excluded, _reason = _is_excluded(profile, datetime.date(2026, 4, 6), LEGION)
        assert excluded is True


class TestLegionEndToEnd:
    """AC-2, AC-7: compute_starter_prediction with league='legion'."""

    @pytest.fixture
    def prediction(self):
        """5-game rotation with one starter, Legion rules."""
        history = []
        dates = [
            "2026-03-10", "2026-03-14", "2026-03-18",
            "2026-03-22", "2026-03-26",
        ]
        for i, d in enumerate(dates):
            gid = f"g{i + 1:02d}"
            history.append(_make_appearance(
                "ace", gid, d,
                ip_outs=18, pitches=75, so=6, bb=2,
                appearance_order=1,
            ))
            history.append(_make_appearance(
                "reliever", gid, d,
                ip_outs=3, pitches=15, so=1, bb=0,
                appearance_order=2,
            ))
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history,
            reference_date=datetime.date(2026, 4, 1),
            league="legion",
        )

    def test_legion_applies_rules_not_warning(self, prediction):
        """AC-7: Legion no longer shows 'rules not available' warning."""
        assert prediction.confidence != "suppress" or (
            prediction.data_note is not None
            and "not yet supported" not in prediction.data_note
            and "not detected" not in prediction.data_note
        )

    def test_legion_has_candidates(self, prediction):
        """AC-2: Legion applies rules, producing candidates."""
        assert len(prediction.top_candidates) > 0

    def test_legion_has_bullpen(self, prediction):
        """AC-2: Bullpen order populated under Legion rules."""
        assert len(prediction.bullpen_order) > 0
