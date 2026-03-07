"""Tests for src/gamechanger/team_resolver.py."""

from __future__ import annotations

import httpx
import pytest
import respx

from src.gamechanger.team_resolver import (
    DiscoveredOpponent,
    GameChangerAPIError,
    TeamNotFoundError,
    TeamProfile,
    discover_opponents,
    resolve_team,
)

_BASE_URL = "https://api.team-manager.gc.com"
_PUBLIC_ID = "a1GFM9Ku0BbF"
_ENDPOINT = f"{_BASE_URL}/public/teams/{_PUBLIC_ID}"

_FULL_RESPONSE = {
    "id": "a1GFM9Ku0BbF",
    "name": "Lincoln Rebels 14U",
    "sport": "baseball",
    "ngb": '["usssa"]',
    "location": {"city": "Lincoln", "state": "NE", "country": "United States"},
    "age_group": "14U",
    "team_season": {
        "season": "summer",
        "year": 2025,
        "record": {"win": 61, "loss": 29, "tie": 2},
    },
    "avatar_url": "https://media-service.gc.com/some-signed-url",
    "staff": ["Ryan Treat", "Jason Jackson", "Jason Wilkinson"],
}


class TestResolveTeamSuccess:
    """AC-7, AC-8: successful 200 response is parsed into TeamProfile."""

    @respx.mock
    def test_returns_team_profile(self) -> None:
        """AC-8: all TeamProfile fields are populated from the API response."""
        respx.get(_ENDPOINT).mock(return_value=httpx.Response(200, json=_FULL_RESPONSE))
        profile = resolve_team(_PUBLIC_ID)

        assert isinstance(profile, TeamProfile)
        assert profile.public_id == "a1GFM9Ku0BbF"
        assert profile.name == "Lincoln Rebels 14U"
        assert profile.sport == "baseball"
        assert profile.city == "Lincoln"
        assert profile.state == "NE"
        assert profile.age_group == "14U"
        assert profile.season == "summer"
        assert profile.year == 2025
        assert profile.record_wins == 61
        assert profile.record_losses == 29
        assert profile.staff == ["Ryan Treat", "Jason Jackson", "Jason Wilkinson"]

    @respx.mock
    def test_correct_url_called(self) -> None:
        """AC-7: the resolver calls GET /public/teams/{public_id}."""
        route = respx.get(_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_FULL_RESPONSE)
        )
        resolve_team(_PUBLIC_ID)
        assert route.called

    @respx.mock
    def test_correct_accept_header_sent(self) -> None:
        """AC-7: the resolver sends the correct Accept header."""
        route = respx.get(_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_FULL_RESPONSE)
        )
        resolve_team(_PUBLIC_ID)
        request = route.calls.last.request
        assert (
            request.headers.get("accept")
            == "application/vnd.gc.com.public_team_profile+json; version=0.1.0"
        )

    @respx.mock
    def test_no_auth_headers_sent(self) -> None:
        """AC-7: no gc-token or gc-device-id headers are sent."""
        route = respx.get(_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_FULL_RESPONSE)
        )
        resolve_team(_PUBLIC_ID)
        request = route.calls.last.request
        assert "gc-token" not in request.headers
        assert "gc-device-id" not in request.headers

    @respx.mock
    def test_gc_app_name_header_sent(self) -> None:
        """AC-7: gc-app-name: web header is sent."""
        route = respx.get(_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_FULL_RESPONSE)
        )
        resolve_team(_PUBLIC_ID)
        request = route.calls.last.request
        assert request.headers.get("gc-app-name") == "web"

    @respx.mock
    def test_optional_fields_default_to_none_when_absent(self) -> None:
        """AC-8: optional fields default to None when absent from response."""
        minimal = {"id": _PUBLIC_ID, "name": "Test Team", "sport": "baseball"}
        respx.get(_ENDPOINT).mock(return_value=httpx.Response(200, json=minimal))
        profile = resolve_team(_PUBLIC_ID)

        assert profile.city is None
        assert profile.state is None
        assert profile.age_group is None
        assert profile.season is None
        assert profile.year is None
        assert profile.record_wins is None
        assert profile.record_losses is None
        assert profile.staff == []


class TestResolveTeam404:
    """AC-9: 404 response raises TeamNotFoundError."""

    @respx.mock
    def test_404_raises_team_not_found(self) -> None:
        respx.get(_ENDPOINT).mock(return_value=httpx.Response(404))
        with pytest.raises(TeamNotFoundError, match=_PUBLIC_ID):
            resolve_team(_PUBLIC_ID)

    def test_team_not_found_is_value_error(self) -> None:
        """AC-9: TeamNotFoundError inherits from ValueError."""
        assert issubclass(TeamNotFoundError, ValueError)


class TestResolveTeam500:
    """AC-10: non-200/non-404 responses raise GameChangerAPIError."""

    @respx.mock
    def test_500_raises_api_error(self) -> None:
        respx.get(_ENDPOINT).mock(return_value=httpx.Response(500))
        with pytest.raises(GameChangerAPIError, match="500"):
            resolve_team(_PUBLIC_ID)

    @respx.mock
    def test_503_raises_api_error(self) -> None:
        respx.get(_ENDPOINT).mock(return_value=httpx.Response(503))
        with pytest.raises(GameChangerAPIError, match="503"):
            resolve_team(_PUBLIC_ID)


class TestResolveTeamMalformedResponse:
    """AC-11: 200 with missing required fields raises GameChangerAPIError."""

    @respx.mock
    def test_missing_name_raises_api_error(self) -> None:
        """AC-11: response missing 'name' raises GameChangerAPIError."""
        data = {"id": _PUBLIC_ID, "sport": "baseball"}
        respx.get(_ENDPOINT).mock(return_value=httpx.Response(200, json=data))
        with pytest.raises(GameChangerAPIError, match="name"):
            resolve_team(_PUBLIC_ID)

    @respx.mock
    def test_missing_sport_raises_api_error(self) -> None:
        """AC-11: response missing 'sport' raises GameChangerAPIError."""
        data = {"id": _PUBLIC_ID, "name": "Test Team"}
        respx.get(_ENDPOINT).mock(return_value=httpx.Response(200, json=data))
        with pytest.raises(GameChangerAPIError, match="sport"):
            resolve_team(_PUBLIC_ID)


class TestResolveTeamTimeout:
    """AC-12: timeout raises GameChangerAPIError."""

    @respx.mock
    def test_timeout_raises_api_error(self) -> None:
        """AC-12: httpx timeout raises GameChangerAPIError."""
        respx.get(_ENDPOINT).mock(side_effect=httpx.TimeoutException("timed out"))
        with pytest.raises(GameChangerAPIError, match="timed out"):
            resolve_team(_PUBLIC_ID)


# ---------------------------------------------------------------------------
# discover_opponents tests (E-042-05)
# ---------------------------------------------------------------------------

_GAMES_ENDPOINT = f"{_BASE_URL}/public/teams/{_PUBLIC_ID}/games"

_GAMES_RESPONSE = [
    {
        "id": "game-1",
        "opponent_team": {"name": "Jr Bluejays 15U", "avatar_url": "https://cdn.example.com/a.jpg"},
        "score": {"team": 5, "opponent_team": 3},
    },
    {
        "id": "game-2",
        "opponent_team": {"name": "Riverside Tigers"},
        "score": {"team": 7, "opponent_team": 2},
    },
    {
        "id": "game-3",
        "opponent_team": {"name": "Jr Bluejays 15U"},  # duplicate
        "score": {"team": 4, "opponent_team": 6},
    },
    {
        "id": "game-4",
        "opponent_team": {"name": "jr bluejays 15u"},  # case-insensitive duplicate
        "score": {"team": 0, "opponent_team": 10},
    },
]


class TestDiscoverOpponentsSuccess:
    """AC-1, AC-2, AC-3, AC-4: successful parsing and deduplication."""

    @respx.mock
    def test_returns_list_of_discovered_opponents(self) -> None:
        """AC-1, AC-2: returns list of DiscoveredOpponent dataclasses."""
        respx.get(_GAMES_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_GAMES_RESPONSE)
        )
        result = discover_opponents(_PUBLIC_ID)

        assert all(isinstance(o, DiscoveredOpponent) for o in result)

    @respx.mock
    def test_deduplicates_by_name_case_insensitive(self) -> None:
        """AC-3: same name in different cases appears only once."""
        respx.get(_GAMES_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_GAMES_RESPONSE)
        )
        result = discover_opponents(_PUBLIC_ID)
        names = [o.name for o in result]

        # Jr Bluejays appears 3 times (2 exact + 1 lowercase) -- only 1 expected
        assert names.count("Jr Bluejays 15U") == 1
        assert len(names) == 2

    @respx.mock
    def test_skips_empty_and_none_names(self) -> None:
        """AC-4: games with missing or empty opponent name are skipped."""
        games = [
            {"id": "g1", "opponent_team": {"name": ""}},
            {"id": "g2", "opponent_team": {}},
            {"id": "g3", "opponent_team": None},
            {"id": "g4"},
            {"id": "g5", "opponent_team": {"name": "Valid Team"}},
        ]
        respx.get(_GAMES_ENDPOINT).mock(
            return_value=httpx.Response(200, json=games)
        )
        result = discover_opponents(_PUBLIC_ID)

        assert len(result) == 1
        assert result[0].name == "Valid Team"

    @respx.mock
    def test_empty_schedule_returns_empty_list(self) -> None:
        """Empty game list returns empty opponents list."""
        respx.get(_GAMES_ENDPOINT).mock(return_value=httpx.Response(200, json=[]))
        result = discover_opponents(_PUBLIC_ID)
        assert result == []

    @respx.mock
    def test_correct_accept_header_sent(self) -> None:
        """AC-5: correct Accept header is sent."""
        route = respx.get(_GAMES_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_GAMES_RESPONSE)
        )
        discover_opponents(_PUBLIC_ID)
        request = route.calls.last.request
        assert request.headers.get("accept") == (
            "application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0"
        )

    @respx.mock
    def test_no_auth_headers_sent(self) -> None:
        """No gc-token or gc-device-id headers are sent (public endpoint)."""
        route = respx.get(_GAMES_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_GAMES_RESPONSE)
        )
        discover_opponents(_PUBLIC_ID)
        request = route.calls.last.request
        assert "gc-token" not in request.headers
        assert "gc-device-id" not in request.headers


class TestDiscoverOpponentsErrors:
    """AC-6: non-200 responses raise GameChangerAPIError."""

    @respx.mock
    def test_500_raises_api_error(self) -> None:
        """AC-6: 500 raises GameChangerAPIError."""
        respx.get(_GAMES_ENDPOINT).mock(return_value=httpx.Response(500))
        with pytest.raises(GameChangerAPIError, match="500"):
            discover_opponents(_PUBLIC_ID)

    @respx.mock
    def test_404_raises_api_error(self) -> None:
        """AC-6: 404 raises GameChangerAPIError (no special case for games endpoint)."""
        respx.get(_GAMES_ENDPOINT).mock(return_value=httpx.Response(404))
        with pytest.raises(GameChangerAPIError, match="404"):
            discover_opponents(_PUBLIC_ID)

    @respx.mock
    def test_timeout_raises_api_error(self) -> None:
        """AC-6: timeout raises GameChangerAPIError."""
        respx.get(_GAMES_ENDPOINT).mock(side_effect=httpx.TimeoutException("timed out"))
        with pytest.raises(GameChangerAPIError, match="timed out"):
            discover_opponents(_PUBLIC_ID)
