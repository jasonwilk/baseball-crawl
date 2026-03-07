"""Tests for src/gamechanger/url_parser.py."""

from __future__ import annotations

import pytest

from src.gamechanger.url_parser import parse_team_url


class TestHappyPaths:
    """AC-1, AC-2, AC-3: standard URLs and bare slugs are parsed correctly."""

    def test_full_url_with_name_slug(self) -> None:
        """AC-1: full URL returns the public_id segment."""
        result = parse_team_url("https://web.gc.com/teams/a1GFM9Ku0BbF/some-slug")
        assert result == "a1GFM9Ku0BbF"

    def test_bare_public_id(self) -> None:
        """AC-2: bare public_id string is returned unchanged."""
        result = parse_team_url("a1GFM9Ku0BbF")
        assert result == "a1GFM9Ku0BbF"

    def test_url_without_trailing_name_slug(self) -> None:
        """AC-3: URL with just /teams/{public_id} (no name slug)."""
        result = parse_team_url("https://web.gc.com/teams/a1GFM9Ku0BbF")
        assert result == "a1GFM9Ku0BbF"

    def test_url_with_trailing_slash(self) -> None:
        """AC-3: trailing slash is handled correctly."""
        result = parse_team_url("https://web.gc.com/teams/a1GFM9Ku0BbF/")
        assert result == "a1GFM9Ku0BbF"

    def test_url_with_query_params(self) -> None:
        """AC-3: query parameters do not interfere with extraction."""
        result = parse_team_url("https://web.gc.com/teams/a1GFM9Ku0BbF/slug?ref=share&utm=x")
        assert result == "a1GFM9Ku0BbF"

    def test_url_with_fragment(self) -> None:
        """AC-3: URL fragments do not interfere with extraction."""
        result = parse_team_url("https://web.gc.com/teams/a1GFM9Ku0BbF/slug#section")
        assert result == "a1GFM9Ku0BbF"

    def test_http_scheme(self) -> None:
        """AC-3: http:// scheme is accepted."""
        result = parse_team_url("http://web.gc.com/teams/a1GFM9Ku0BbF/slug")
        assert result == "a1GFM9Ku0BbF"

    def test_non_gc_hostname(self) -> None:
        """AC-4: any hostname with /teams/{slug} path is accepted (mobile share links)."""
        result = parse_team_url("https://share.gc.com/teams/ABC123def/some-team")
        assert result == "ABC123def"


class TestErrorCases:
    """AC-4, AC-5: invalid inputs raise ValueError with descriptive messages."""

    def test_empty_string_raises(self) -> None:
        """AC-4: empty string raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            parse_team_url("")

    def test_whitespace_only_raises(self) -> None:
        """AC-4: whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            parse_team_url("   ")

    def test_url_without_teams_segment_raises(self) -> None:
        """AC-4: URL with no /teams/ path raises ValueError."""
        with pytest.raises(ValueError, match="/teams/"):
            parse_team_url("https://web.gc.com/players/a1GFM9Ku0BbF")

    def test_gc_homepage_url_raises(self) -> None:
        """AC-4: GC homepage URL has no /teams/ segment."""
        with pytest.raises(ValueError, match="/teams/"):
            parse_team_url("https://web.gc.com/")

    def test_public_id_with_hyphens_raises(self) -> None:
        """AC-5: public_id with hyphens (UUID-like) fails alphanumeric validation."""
        with pytest.raises(ValueError, match="alphanumeric"):
            parse_team_url("https://web.gc.com/teams/550e8400-e29b-41d4/slug")

    def test_public_id_too_short_raises(self) -> None:
        """AC-5: public_id shorter than 6 chars fails validation."""
        with pytest.raises(ValueError, match="alphanumeric"):
            parse_team_url("https://web.gc.com/teams/abc/slug")

    def test_public_id_too_long_raises(self) -> None:
        """AC-5: public_id longer than 20 chars fails validation."""
        with pytest.raises(ValueError, match="alphanumeric"):
            parse_team_url("https://web.gc.com/teams/ABCDEFGHIJKLMNOPQRSTU/slug")

    def test_bare_public_id_with_hyphens_raises(self) -> None:
        """AC-5: bare UUID-style slug fails validation (not alphanumeric)."""
        with pytest.raises(ValueError, match="alphanumeric"):
            parse_team_url("550e8400-e29b-41d4-a716-446655440000")
