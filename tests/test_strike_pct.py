"""Unit tests for AC-8: strike_pct computation in pitching rate helpers.

Tests call the compute functions directly with crafted input dicts,
verifying correct computation for the normal case, zero-pitches guard,
and NULL-pitches guard.

Run with:
    pytest tests/test_strike_pct.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.api.routes.dashboard import (  # noqa: E402
    _compute_game_pitching_rates,
    _compute_opponent_pitching_rates,
    _compute_pitching_rates,
    _compute_player_pitching_rates,
)


# ---------------------------------------------------------------------------
# _compute_pitching_rates (team pitching page)
# ---------------------------------------------------------------------------


def _base_pitcher(**kwargs) -> dict:
    """Return a minimal pitcher row with sensible defaults."""
    row: dict = {
        "ip_outs": 9,
        "er": 1,
        "so": 6,
        "bb": 2,
        "h": 3,
        "pitches": 0,
        "total_strikes": 0,
    }
    row.update(kwargs)
    return row


class TestComputePitchingRates:
    def test_normal_case(self):
        row = _base_pitcher(pitches=100, total_strikes=65)
        result = _compute_pitching_rates([row])
        assert result[0]["strike_pct"] == "65.0%"

    def test_zero_pitches_guard(self):
        row = _base_pitcher(pitches=0, total_strikes=0)
        result = _compute_pitching_rates([row])
        assert result[0]["strike_pct"] == "-"

    def test_null_pitches_guard(self):
        row = _base_pitcher(pitches=None, total_strikes=None)
        result = _compute_pitching_rates([row])
        assert result[0]["strike_pct"] == "-"

    def test_rounding(self):
        # 63 / 100 = 63.0%
        row = _base_pitcher(pitches=100, total_strikes=63)
        result = _compute_pitching_rates([row])
        assert result[0]["strike_pct"] == "63.0%"

    def test_multiple_rows(self):
        rows = [
            _base_pitcher(pitches=80, total_strikes=52),
            _base_pitcher(pitches=0, total_strikes=0),
            _base_pitcher(pitches=120, total_strikes=72),
        ]
        result = _compute_pitching_rates(rows)
        assert result[0]["strike_pct"] == "65.0%"
        assert result[1]["strike_pct"] == "-"
        assert result[2]["strike_pct"] == "60.0%"

    def test_existing_rate_fields_still_computed(self):
        """Existing ERA/K9/BB9/WHIP are unaffected by the new field."""
        row = _base_pitcher(ip_outs=27, er=3, so=9, bb=3, h=9, pitches=90, total_strikes=58)
        result = _compute_pitching_rates([row])
        assert result[0]["era"] == "3.00"
        assert result[0]["k9"] == "9.0"
        assert result[0]["strike_pct"] == "64.4%"

    def test_zero_ip_outs_with_pitches(self):
        """Zero ip_outs yields '-' for rate stats but strike_pct still computed."""
        row = _base_pitcher(ip_outs=0, pitches=50, total_strikes=30)
        result = _compute_pitching_rates([row])
        assert result[0]["era"] == "-"
        assert result[0]["strike_pct"] == "60.0%"


# ---------------------------------------------------------------------------
# _compute_opponent_pitching_rates (opponent scouting page)
# ---------------------------------------------------------------------------


class TestComputeOpponentPitchingRates:
    def _row(self, **kwargs) -> dict:
        row: dict = {
            "ip_outs": 9,
            "er": 1,
            "so": 5,
            "bb": 2,
            "h": 3,
            "games": 3,
            "pitches": 0,
            "total_strikes": 0,
        }
        row.update(kwargs)
        return row

    def test_normal_case(self):
        row = self._row(pitches=100, total_strikes=62)
        result = _compute_opponent_pitching_rates([row])
        assert result[0]["strike_pct"] == "62.0%"

    def test_zero_pitches_guard(self):
        row = self._row(pitches=0, total_strikes=0)
        result = _compute_opponent_pitching_rates([row])
        assert result[0]["strike_pct"] == "-"

    def test_null_pitches_guard(self):
        row = self._row(pitches=None, total_strikes=None)
        result = _compute_opponent_pitching_rates([row])
        assert result[0]["strike_pct"] == "-"

    def test_avg_pitches_still_computed(self):
        """avg_pitches field is unaffected by new strike_pct field."""
        row = self._row(pitches=90, total_strikes=57, games=3)
        result = _compute_opponent_pitching_rates([row])
        assert result[0]["avg_pitches"] == "30"
        assert result[0]["strike_pct"] == "63.3%"


# ---------------------------------------------------------------------------
# _compute_player_pitching_rates (player profile page)
# ---------------------------------------------------------------------------


class TestComputePlayerPitchingRates:
    def _row(self, **kwargs) -> dict:
        row: dict = {
            "ip_outs": 9,
            "er": 2,
            "so": 7,
            "bb": 3,
            "h": 5,
            "pitches": 0,
            "total_strikes": 0,
        }
        row.update(kwargs)
        return row

    def test_normal_case(self):
        row = self._row(pitches=95, total_strikes=60)
        result = _compute_player_pitching_rates([row])
        assert result[0]["strike_pct"] == "63.2%"

    def test_zero_pitches_guard(self):
        row = self._row(pitches=0, total_strikes=0)
        result = _compute_player_pitching_rates([row])
        assert result[0]["strike_pct"] == "-"

    def test_null_pitches_guard(self):
        row = self._row(pitches=None, total_strikes=None)
        result = _compute_player_pitching_rates([row])
        assert result[0]["strike_pct"] == "-"


# ---------------------------------------------------------------------------
# _compute_game_pitching_rates (game box score page)
# ---------------------------------------------------------------------------


class TestComputeGamePitchingRates:
    def _row(self, **kwargs) -> dict:
        row: dict = {
            "ip_outs": 9,
            "er": 1,
            "so": 5,
            "bb": 2,
            "h": 4,
            "pitches": 0,
            "total_strikes": 0,
        }
        row.update(kwargs)
        return row

    def test_normal_case(self):
        row = self._row(pitches=85, total_strikes=55)
        result = _compute_game_pitching_rates([row])
        assert result[0]["strike_pct"] == "64.7%"

    def test_zero_pitches_guard(self):
        row = self._row(pitches=0, total_strikes=0)
        result = _compute_game_pitching_rates([row])
        assert result[0]["strike_pct"] == "-"

    def test_null_pitches_guard(self):
        row = self._row(pitches=None, total_strikes=None)
        result = _compute_game_pitching_rates([row])
        assert result[0]["strike_pct"] == "-"

    def test_one_hundred_percent(self):
        row = self._row(pitches=50, total_strikes=50)
        result = _compute_game_pitching_rates([row])
        assert result[0]["strike_pct"] == "100.0%"

    def test_empty_list(self):
        result = _compute_game_pitching_rates([])
        assert result == []
