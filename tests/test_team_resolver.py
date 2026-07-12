"""Tests for src/gamechanger/team_resolver.py."""

from __future__ import annotations

import httpx
import pytest
import respx

from src.gamechanger.team_resolver import (
    GameChangerAPIError,
    TeamNotFoundError,
    TeamProfile,
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


class TestResolveTeamTransportErrors:
    """E-252-09: the WHOLE httpx.RequestError family (not just timeout) is caught."""

    @respx.mock
    def test_connect_error_raises_api_error(self) -> None:
        """AC-1/AC-3: a connection-level ConnectError (DNS / refused / TLS) is
        caught and re-raised as the documented GameChangerAPIError -- NOT a raw
        httpx exception that would crash the caller (the morning run, map-opponent).
        """
        respx.get(_ENDPOINT).mock(side_effect=httpx.ConnectError("connection refused"))
        with pytest.raises(GameChangerAPIError, match="connection refused"):
            resolve_team(_PUBLIC_ID)

    @respx.mock
    def test_read_error_raises_api_error(self) -> None:
        """AC-1: another non-timeout httpx.RequestError subclass is also caught
        (proving the broadened catch covers the whole transport family)."""
        respx.get(_ENDPOINT).mock(side_effect=httpx.ReadError("read failed"))
        with pytest.raises(GameChangerAPIError, match="ReadError"):
            resolve_team(_PUBLIC_ID)
