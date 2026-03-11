"""Tests for src/gamechanger/url_parser.py."""

from __future__ import annotations

import pytest

from src.gamechanger.url_parser import TeamIdResult, parse_team_url

_VALID_UUID = "72bb77d8-54ca-42d2-8547-9da4880d0cb4"
_VALID_PUBLIC_ID = "a1GFM9Ku0BbF"


class TestPublicIdHappyPaths:
    """AC-2, AC-3: public_id slugs and public_id URLs are parsed correctly."""

    def test_full_url_with_name_slug(self) -> None:
        """AC-3: full URL returns a public_id result."""
        result = parse_team_url(f"https://web.gc.com/teams/{_VALID_PUBLIC_ID}/some-slug")
        assert isinstance(result, TeamIdResult)
        assert result.value == _VALID_PUBLIC_ID
        assert result.id_type == "public_id"
        assert result.is_public_id
        assert not result.is_uuid

    def test_bare_public_id(self) -> None:
        """AC-2: bare public_id string returns a public_id result."""
        result = parse_team_url(_VALID_PUBLIC_ID)
        assert result.value == _VALID_PUBLIC_ID
        assert result.id_type == "public_id"

    def test_url_without_trailing_name_slug(self) -> None:
        """AC-3: URL with just /teams/{public_id} (no name slug)."""
        result = parse_team_url(f"https://web.gc.com/teams/{_VALID_PUBLIC_ID}")
        assert result.value == _VALID_PUBLIC_ID
        assert result.id_type == "public_id"

    def test_url_with_trailing_slash(self) -> None:
        """AC-3: trailing slash is handled correctly."""
        result = parse_team_url(f"https://web.gc.com/teams/{_VALID_PUBLIC_ID}/")
        assert result.value == _VALID_PUBLIC_ID
        assert result.id_type == "public_id"

    def test_url_with_query_params(self) -> None:
        """AC-3: query parameters do not interfere with extraction."""
        result = parse_team_url(
            f"https://web.gc.com/teams/{_VALID_PUBLIC_ID}/slug?ref=share&utm=x"
        )
        assert result.value == _VALID_PUBLIC_ID
        assert result.id_type == "public_id"

    def test_url_with_fragment(self) -> None:
        """AC-3: URL fragments do not interfere with extraction."""
        result = parse_team_url(
            f"https://web.gc.com/teams/{_VALID_PUBLIC_ID}/slug#section"
        )
        assert result.value == _VALID_PUBLIC_ID
        assert result.id_type == "public_id"

    def test_http_scheme(self) -> None:
        """AC-3: http:// scheme is accepted."""
        result = parse_team_url(f"http://web.gc.com/teams/{_VALID_PUBLIC_ID}/slug")
        assert result.value == _VALID_PUBLIC_ID
        assert result.id_type == "public_id"

    def test_non_gc_hostname(self) -> None:
        """AC-3: any hostname with /teams/{slug} path is accepted (mobile share links)."""
        result = parse_team_url("https://share.gc.com/teams/ABC123def/some-team")
        assert result.value == "ABC123def"
        assert result.id_type == "public_id"


class TestUuidHappyPaths:
    """AC-1, AC-3: UUID inputs (bare and in URLs) are parsed correctly."""

    def test_bare_uuid(self) -> None:
        """AC-1: bare UUID string returns a uuid result."""
        result = parse_team_url(_VALID_UUID)
        assert isinstance(result, TeamIdResult)
        assert result.value == _VALID_UUID
        assert result.id_type == "uuid"
        assert result.is_uuid
        assert not result.is_public_id

    def test_bare_uuid_with_surrounding_whitespace(self) -> None:
        """AC-7: UUID with surrounding whitespace is stripped and accepted."""
        result = parse_team_url(f"  {_VALID_UUID}  ")
        assert result.value == _VALID_UUID
        assert result.id_type == "uuid"

    def test_bare_uuid_uppercase(self) -> None:
        """AC-7: UUIDs are case-insensitive."""
        result = parse_team_url(_VALID_UUID.upper())
        assert result.value == _VALID_UUID.upper()
        assert result.id_type == "uuid"

    def test_url_with_uuid_in_teams_segment(self) -> None:
        """AC-3: URL with UUID in /teams/ segment returns a uuid result."""
        url = f"https://web.gc.com/teams/{_VALID_UUID}/some-team-slug"
        result = parse_team_url(url)
        assert result.value == _VALID_UUID
        assert result.id_type == "uuid"

    def test_url_with_uuid_no_name_slug(self) -> None:
        """AC-3: URL with UUID and no name slug."""
        url = f"https://web.gc.com/teams/{_VALID_UUID}"
        result = parse_team_url(url)
        assert result.value == _VALID_UUID
        assert result.id_type == "uuid"


class TestErrorCases:
    """AC-4: invalid inputs raise ValueError with descriptive messages."""

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
            parse_team_url(f"https://web.gc.com/players/{_VALID_PUBLIC_ID}")

    def test_gc_homepage_url_raises(self) -> None:
        """AC-4: GC homepage URL has no /teams/ segment."""
        with pytest.raises(ValueError, match="/teams/"):
            parse_team_url("https://web.gc.com/")

    def test_truncated_uuid_in_url_raises(self) -> None:
        """AC-4: partial UUID (not 8-4-4-4-12) in URL raises ValueError."""
        with pytest.raises(ValueError):
            parse_team_url("https://web.gc.com/teams/550e8400-e29b-41d4/slug")

    def test_public_id_too_short_raises(self) -> None:
        """AC-4: public_id shorter than 6 chars fails validation."""
        with pytest.raises(ValueError):
            parse_team_url("https://web.gc.com/teams/abc/slug")

    def test_public_id_too_long_raises(self) -> None:
        """AC-4: public_id longer than 20 chars (and not a UUID) fails validation."""
        with pytest.raises(ValueError):
            parse_team_url("https://web.gc.com/teams/ABCDEFGHIJKLMNOPQRSTU/slug")

    def test_random_text_raises(self) -> None:
        """AC-4: random text with no URL structure raises ValueError."""
        with pytest.raises(ValueError):
            parse_team_url("not-a-valid-id-or-url")

    def test_uuid_like_but_wrong_format_raises(self) -> None:
        """AC-7: UUID-like string that is not 8-4-4-4-12 format raises ValueError."""
        # 8-4-4-12 (missing a group) -- not valid UUID
        with pytest.raises(ValueError):
            parse_team_url("72bb77d8-54ca-42d2-9da4880d0cb4")

    def test_uuid_like_with_wrong_group_lengths_raises(self) -> None:
        """AC-7: string with dashes but wrong group sizes is not a UUID."""
        # 4-4-4-4-12 pattern (first group too short)
        with pytest.raises(ValueError):
            parse_team_url("72bb-54ca-42d2-8547-9da4880d0cb4")
