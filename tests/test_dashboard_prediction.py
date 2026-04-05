"""Tests for predicted starter integration in dashboard opponent detail.

Tests the opponent_detail and opponent_print route handlers with mocked
DB calls to verify prediction data flows to the template.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from src.reports.starter_prediction import StarterPrediction


# ── Fixtures ────────────────────────────────────────────────────────────


def _make_prediction() -> StarterPrediction:
    """Build a StarterPrediction for testing."""
    return StarterPrediction(
        confidence="high",
        predicted_starter={
            "player_id": "p1",
            "name": "Ace Smith",
            "jersey_number": "22",
            "likelihood": 0.85,
            "reasoning": "Next in rotation, 5 days rest",
            "games_started": 8,
            "recent_starts": [
                {
                    "game_date": "2026-03-28",
                    "ip_outs": 18,
                    "pitches": 70,
                    "so": 6,
                    "bb": 2,
                    "decision": "W",
                    "rest_days_from_previous_start": 4,
                },
            ],
        },
        rotation_pattern="ace-dominant",
        rest_table=[
            {
                "name": "Ace Smith",
                "jersey_number": "22",
                "games_started": 8,
                "last_outing_date": "2026-03-28",
                "days_since_last_appearance": 3,
                "last_outing_pitches": 70,
                "workload_7d": 70,
            },
        ],
        bullpen_order=[
            {"name": "Closer Jones", "jersey_number": "45", "frequency": 5, "games_sampled": 10},
        ],
    )


_SCOUTING_REPORT = {
    "team_name": "Opponent Team",
    "record": {"wins": 10, "losses": 5},
    "pitching": [],
    "batting": [],
}

_TEAM_INFOS = [{"id": 1, "name": "Our Team"}]

_PITCHING_HISTORY = [
    {
        "player_id": "p1",
        "first_name": "Ace",
        "last_name": "Smith",
        "jersey_number": "22",
        "game_id": "g01",
        "game_date": "2026-03-28",
        "start_time": None,
        "ip_outs": 18,
        "pitches": 70,
        "so": 6,
        "bb": 2,
        "h": 4,
        "r": 2,
        "er": 1,
        "bf": 22,
        "decision": "W",
        "appearance_order": 1,
        "rest_days": None,
        "team_game_number": 1,
    },
]


def _create_test_client():
    """Create a test client with mocked auth middleware."""
    from fastapi import FastAPI
    from src.api.routes.dashboard import router

    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def fake_auth(request, call_next):
        request.state.permitted_teams = [1]
        request.state.user = {"user_id": 1}
        return await call_next(request)

    return TestClient(app)


# ── AC-13: Opponent detail renders with prediction ──────────────────────


class TestOpponentDetailWithPrediction:

    @patch("src.api.routes.dashboard._check_opponent_authorization", return_value=True)
    @patch("src.api.routes.dashboard.db")
    @patch("src.api.routes.dashboard._fetch_opponent_detail_data")
    def test_renders_prediction_section(
        self, mock_fetch, mock_db, mock_auth,
    ):
        mock_fetch.return_value = (_SCOUTING_REPORT, _TEAM_INFOS)
        mock_db.get_available_seasons.return_value = [{"season_id": "2026-spring-hs"}]
        mock_db.get_opponent_scouting_status.return_value = {"status": "full_stats", "link_id": 1}
        mock_db.get_pitching_workload.return_value = {}
        mock_db.get_pitching_history.return_value = _PITCHING_HISTORY
        mock_db.build_pitcher_profiles.return_value = {
            "p1": {
                "player_id": "p1",
                "first_name": "Ace",
                "last_name": "Smith",
                "jersey_number": "22",
                "appearances": _PITCHING_HISTORY,
                "starts": _PITCHING_HISTORY,
                "total_games": 1,
                "total_starts": 1,
                "season_ip_outs": 18,
                "season_k9": 9.0,
                "start_to_start_rest": [],
            },
        }
        mock_db.get_last_meeting.return_value = None
        mock_db.get_team_spray_bip_count.return_value = 0
        mock_db.get_player_spray_bip_counts.return_value = {}
        mock_db.get_team_spray_events.return_value = ([], None)
        mock_db.get_game_coverage.return_value = None

        client = _create_test_client()
        response = client.get("/dashboard/opponents/99?team_id=1")

        assert response.status_code == 200
        html = response.text
        assert "Predicted Starter" in html
        assert "Ace Smith" in html


# ── AC-13: Opponent detail renders without prediction ───────────────────


class TestOpponentDetailWithoutPrediction:

    @patch("src.api.routes.dashboard._check_opponent_authorization", return_value=True)
    @patch("src.api.routes.dashboard.db")
    @patch("src.api.routes.dashboard._fetch_opponent_detail_data")
    def test_no_prediction_section_when_no_history(
        self, mock_fetch, mock_db, mock_auth,
    ):
        mock_fetch.return_value = (_SCOUTING_REPORT, _TEAM_INFOS)
        mock_db.get_available_seasons.return_value = [{"season_id": "2026-spring-hs"}]
        mock_db.get_opponent_scouting_status.return_value = {"status": "full_stats", "link_id": 1}
        mock_db.get_pitching_workload.return_value = {}
        mock_db.get_pitching_history.return_value = []  # No history
        mock_db.get_last_meeting.return_value = None
        mock_db.get_team_spray_bip_count.return_value = 0
        mock_db.get_player_spray_bip_counts.return_value = {}
        mock_db.get_team_spray_events.return_value = ([], None)
        mock_db.get_game_coverage.return_value = None

        client = _create_test_client()
        response = client.get("/dashboard/opponents/99?team_id=1")

        assert response.status_code == 200
        assert "Predicted Starter" not in response.text


# ── AC-13: Prediction failure does not break the page ───────────────────


class TestPredictionFailure:

    @patch("src.api.routes.dashboard._check_opponent_authorization", return_value=True)
    @patch("src.api.routes.dashboard.db")
    @patch("src.api.routes.dashboard._fetch_opponent_detail_data")
    def test_engine_error_does_not_crash(
        self, mock_fetch, mock_db, mock_auth,
    ):
        mock_fetch.return_value = (_SCOUTING_REPORT, _TEAM_INFOS)
        mock_db.get_available_seasons.return_value = [{"season_id": "2026-spring-hs"}]
        mock_db.get_opponent_scouting_status.return_value = {"status": "full_stats", "link_id": 1}
        mock_db.get_pitching_workload.return_value = {}
        mock_db.get_pitching_history.side_effect = Exception("DB connection lost")
        mock_db.get_last_meeting.return_value = None
        mock_db.get_team_spray_bip_count.return_value = 0
        mock_db.get_player_spray_bip_counts.return_value = {}
        mock_db.get_team_spray_events.return_value = ([], None)
        mock_db.get_game_coverage.return_value = None

        client = _create_test_client()
        response = client.get("/dashboard/opponents/99?team_id=1")

        # Page renders successfully despite prediction failure
        assert response.status_code == 200
        # No prediction section since it failed
        assert "Predicted Starter" not in response.text
