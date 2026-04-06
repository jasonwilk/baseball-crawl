"""Tests for the deterministic rotation analysis engine (Tier 1).

Tests ``compute_starter_prediction()`` and supporting functions in
``src/reports/starter_prediction.py``.
"""

from __future__ import annotations

import datetime

import pytest

from src.api.db import build_pitcher_profiles
from src.reports.starter_prediction import (
    StarterPrediction,
    _is_excluded_high_pitch_short_rest,
    _is_excluded_within_1_day,
    compute_starter_prediction,
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


# ── AC-13: Within-1-day exclusion ───────────────────────────────────────


class TestWithin1DayExclusion:
    """Pitcher who pitched yesterday is excluded from candidates."""

    @pytest.fixture
    def prediction(self):
        dates = [
            "2026-03-10", "2026-03-13", "2026-03-16", "2026-03-19",
            "2026-03-22", "2026-03-25", "2026-03-28", "2026-03-29",
        ]
        # ace-bravo rotation, but ace also pitches relief in game 8 (Mar 29)
        rotation = ["ace", "bravo", "ace", "bravo", "ace", "bravo", "ace", "bravo"]
        history = _build_rotation_history(rotation, dates)
        # Add ace as relief in game 8 (latest game, 1 day after his start)
        history.append(_make_appearance(
            "ace", "g08", "2026-03-29",
            ip_outs=3, pitches=20, so=1,
            appearance_order=2,
            rest_days=1, team_game_number=8,
        ))
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 3, 29),
        )

    def test_ace_excluded(self, prediction):
        """Ace pitched on Mar 29 (latest game) so should be excluded."""
        candidate_ids = [c["player_id"] for c in prediction.top_candidates]
        assert "ace" not in candidate_ids


# ── AC-13: 75+ pitch / short rest gate ──────────────────────────────────


class TestHighPitchShortRest:
    """75+ pitches with < 4 days rest -> excluded from candidates."""

    @pytest.fixture
    def prediction(self):
        dates = [
            "2026-03-10", "2026-03-13", "2026-03-16", "2026-03-19",
            "2026-03-22", "2026-03-25", "2026-03-28", "2026-03-30",
        ]
        # ace-bravo rotation. ace starts game 7 (Mar 28) with 90 pitches.
        # game 8 is Mar 30 (2 days later). ace should be excluded.
        rotation = ["ace", "bravo", "ace", "bravo", "ace", "bravo", "ace", "bravo"]
        history = _build_rotation_history(
            rotation, dates, starter_pitches=90,
        )
        profiles = build_pitcher_profiles(history)
        return compute_starter_prediction(
            profiles, history, reference_date=datetime.date(2026, 3, 30),
        )

    def test_ace_excluded_high_pitch(self, prediction):
        """Ace threw 90 pitches 2 days ago -- should be excluded."""
        candidate_ids = [c["player_id"] for c in prediction.top_candidates]
        assert "ace" not in candidate_ids


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


# ── AC-5: reference_date controls high-pitch/short-rest exclusion ─────


class TestReferenceDateHighPitchExclusion:
    """80 pitches, reference_date controls whether pitcher is excluded.

    Last appearance 2026-03-28, 80 pitches (>= 75 threshold).
    reference_date=2026-04-02 -> 5 days rest (>= 4) -> NOT excluded.
    reference_date=2026-03-31 -> 3 days rest (< 4) -> excluded.
    """

    def _make_profile(self) -> dict:
        return {
            "total_starts": 3,
            "total_games": 3,
            "first_name": "Ace",
            "last_name": "Pitcher",
            "appearances": [
                {"game_date": "2026-03-28", "pitches": 80},
            ],
        }

    def test_not_excluded_with_enough_rest(self):
        profile = self._make_profile()
        assert not _is_excluded_high_pitch_short_rest(
            profile, datetime.date(2026, 4, 2),
        )

    def test_excluded_with_short_rest(self):
        profile = self._make_profile()
        assert _is_excluded_high_pitch_short_rest(
            profile, datetime.date(2026, 3, 31),
        )


# ── AC-6: reference_date controls within-1-day exclusion ─────────────


class TestReferenceDateWithin1DayExclusion:
    """Last appearance 2026-04-05, reference_date=2026-04-06 -> 1 day -> excluded."""

    def test_excluded_within_1_day(self):
        profile = {
            "total_starts": 3,
            "total_games": 3,
            "first_name": "Ace",
            "last_name": "Pitcher",
            "appearances": [
                {"game_date": "2026-04-05", "pitches": 70},
            ],
        }
        assert _is_excluded_within_1_day(
            profile, datetime.date(2026, 4, 6),
        )


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
