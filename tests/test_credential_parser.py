"""Unit tests for src/gamechanger/credential_parser.py.

Coverage:
- Happy path: gc-token extracted as GAMECHANGER_REFRESH_TOKEN
- Full header set from a real-style GameChanger curl command
- Cookie extraction via -H 'Cookie: ...' header
- Cookie extraction via -b flag
- Malformed / missing-auth curl command raises CurlParseError
- Input that is not a curl command raises CurlParseError
- Existing .env preservation: non-credential keys survive a merge
- Existing .env update: credential keys are replaced by new values
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.gamechanger.credential_parser import (
    CurlParseError,
    atomic_merge_env_file,
    merge_env_file,
    parse_curl,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

MINIMAL_CURL = (
    "curl 'https://api.team-manager.gc.com/teams/abc/game-summaries' "
    "-H 'gc-token: eyJhbGciOiJIUzI1NiJ9.payload.signature'"
)

FULL_GC_CURL = textwrap.dedent(
    """\
    curl 'https://api.team-manager.gc.com/teams/72bb77d8/game-summaries?start_at=136418700' \\
      -H 'gc-user-action-id: 0c472c05-9a45-4c63-b2e6-7e7686999c0c' \\
      -H 'sec-ch-ua-platform: "macOS"' \\
      -H 'Referer: https://web.gc.com/' \\
      -H 'sec-ch-ua: "Not:A-Brand";v="99", "Google Chrome";v="145"' \\
      -H 'gc-token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.sig' \\
      -H 'sec-ch-ua-mobile: ?0' \\
      -H 'gc-user-action: data_loading:events' \\
      -H 'gc-app-name: web' \\
      -H 'gc-device-id: 7b615e8c124f5d44575d4e6736ae1a82' \\
      -H 'x-pagination: true' \\
      -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)' \\
      -H 'Accept: application/vnd.gc.com.game_summary:list+json; version=0.1.0' \\
      -H 'DNT: 1' \\
      -H 'Content-Type: application/vnd.gc.com.none+json; version=undefined'
    """
)


# ---------------------------------------------------------------------------
# parse_curl -- happy path
# ---------------------------------------------------------------------------


class TestParseCurlHappyPath:
    """AC-1: Minimal curl with gc-token extracts GAMECHANGER_REFRESH_TOKEN_WEB."""

    def test_extracts_auth_token(self) -> None:
        result = parse_curl(MINIMAL_CURL)
        assert result["GAMECHANGER_REFRESH_TOKEN_WEB"] == (
            "eyJhbGciOiJIUzI1NiJ9.payload.signature"
        )

    def test_extracts_base_url(self) -> None:
        result = parse_curl(MINIMAL_CURL)
        assert result["GAMECHANGER_BASE_URL"] == "https://api.team-manager.gc.com"

    def test_base_url_strips_path_and_query(self) -> None:
        curl = (
            "curl 'https://api.team-manager.gc.com/teams/abc?start_at=1' "
            "-H 'gc-token: tok'"
        )
        result = parse_curl(curl)
        assert result["GAMECHANGER_BASE_URL"] == "https://api.team-manager.gc.com"

    def test_full_gc_curl_extracts_all_credential_headers(self) -> None:
        result = parse_curl(FULL_GC_CURL)
        assert result["GAMECHANGER_REFRESH_TOKEN_WEB"] == (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.sig"
        )
        assert result["GAMECHANGER_APP_NAME_WEB"] == "web"
        assert result["GAMECHANGER_DEVICE_ID_WEB"] == "7b615e8c124f5d44575d4e6736ae1a82"
        assert result["GAMECHANGER_BASE_URL"] == "https://api.team-manager.gc.com"

    def test_full_gc_curl_skips_per_request_headers(self) -> None:
        """gc-user-action-id and gc-user-action must NOT appear in the result."""
        result = parse_curl(FULL_GC_CURL)
        for key in result:
            assert "user-action" not in key.lower(), (
                f"Per-request header leaked into credentials: {key}"
            )
        assert "GAMECHANGER_COOKIE_X_PAGINATION" not in result
        # x-pagination is not a cookie, but also must not appear as a credential key
        for key in result:
            assert "PAGINATION" not in key, (
                f"x-pagination leaked into credentials: {key}"
            )


# ---------------------------------------------------------------------------
# parse_curl -- cookie extraction (AC-3)
# ---------------------------------------------------------------------------


class TestCookieExtraction:
    """AC-3: Cookies extracted and stored as GAMECHANGER_COOKIE_<NAME>."""

    def test_cookie_header_single(self) -> None:
        curl = (
            "curl 'https://api.team-manager.gc.com/data' "
            "-H 'gc-token: tok' "
            "-H 'Cookie: gc_session=abc123'"
        )
        result = parse_curl(curl)
        assert result["GAMECHANGER_COOKIE_GC_SESSION"] == "abc123"

    def test_cookie_header_multiple(self) -> None:
        curl = (
            "curl 'https://api.team-manager.gc.com/data' "
            "-H 'gc-token: tok' "
            "-H 'Cookie: gc_session=abc123; gc_user=ghi789'"
        )
        result = parse_curl(curl)
        assert result["GAMECHANGER_COOKIE_GC_SESSION"] == "abc123"
        assert result["GAMECHANGER_COOKIE_GC_USER"] == "ghi789"

    def test_cookie_via_b_flag(self) -> None:
        curl = (
            "curl 'https://api.team-manager.gc.com/data' "
            "-H 'gc-token: tok' "
            "-b 'session_id=def456; other=xyz'"
        )
        result = parse_curl(curl)
        assert result["GAMECHANGER_COOKIE_SESSION_ID"] == "def456"
        assert result["GAMECHANGER_COOKIE_OTHER"] == "xyz"

    def test_cookie_key_uppercased(self) -> None:
        curl = (
            "curl 'https://api.team-manager.gc.com/data' "
            "-H 'gc-token: tok' "
            "-H 'Cookie: MyLowercaseCookie=val'"
        )
        result = parse_curl(curl)
        assert "GAMECHANGER_COOKIE_MYLOWERCASECOOKIE" in result

    def test_cookie_key_hyphens_to_underscores(self) -> None:
        curl = (
            "curl 'https://api.team-manager.gc.com/data' "
            "-H 'gc-token: tok' "
            "-H 'Cookie: my-cookie=val'"
        )
        result = parse_curl(curl)
        assert "GAMECHANGER_COOKIE_MY_COOKIE" in result


# ---------------------------------------------------------------------------
# parse_curl -- malformed / invalid input (AC-4)
# ---------------------------------------------------------------------------


class TestMalformedInput:
    """AC-4: Malformed curl commands exit with CurlParseError."""

    def test_not_a_curl_command(self) -> None:
        with pytest.raises(CurlParseError, match="curl"):
            parse_curl("wget https://example.com")

    def test_empty_string(self) -> None:
        with pytest.raises(CurlParseError):
            parse_curl("")

    def test_curl_with_no_url(self) -> None:
        with pytest.raises(CurlParseError, match="URL"):
            parse_curl("curl -H 'gc-token: tok'")

    def test_missing_gc_token(self) -> None:
        curl = (
            "curl 'https://api.team-manager.gc.com/data' "
            "-H 'Accept: application/json'"
        )
        with pytest.raises(CurlParseError, match="gc-token"):
            parse_curl(curl)

    def test_error_message_is_human_readable(self) -> None:
        """Error messages must contain enough context for the user to act."""
        with pytest.raises(CurlParseError) as exc_info:
            parse_curl("not even a curl command")
        msg = str(exc_info.value)
        assert len(msg) > 10, "Error message is too short to be useful"

    def test_unbalanced_quotes(self) -> None:
        with pytest.raises(CurlParseError):
            parse_curl("curl 'https://example.com -H 'unterminated")


# ---------------------------------------------------------------------------
# merge_env_file -- .env preservation (AC-2)
# ---------------------------------------------------------------------------


class TestMergeEnvFile:
    """AC-2: Existing .env non-credential values are preserved; credentials updated."""

    def test_new_file_written_when_none_exists(self, tmp_path: Path) -> None:
        env_path = tmp_path / ".env"
        assert not env_path.exists()
        merged = merge_env_file(str(env_path), {"GAMECHANGER_REFRESH_TOKEN_WEB": "tok"})
        assert merged["GAMECHANGER_REFRESH_TOKEN_WEB"] == "tok"

    def test_existing_credentials_replaced(self, tmp_path: Path) -> None:
        env_path = tmp_path / ".env"
        env_path.write_text("GAMECHANGER_REFRESH_TOKEN_WEB=old_token\n", encoding="utf-8")
        merged = merge_env_file(
            str(env_path), {"GAMECHANGER_REFRESH_TOKEN_WEB": "new_token"}
        )
        assert merged["GAMECHANGER_REFRESH_TOKEN_WEB"] == "new_token"

    def test_non_credential_keys_preserved(self, tmp_path: Path) -> None:
        env_path = tmp_path / ".env"
        env_path.write_text(
            "UNRELATED_KEY=some_value\nANOTHER_KEY=another_value\n",
            encoding="utf-8",
        )
        merged = merge_env_file(
            str(env_path), {"GAMECHANGER_REFRESH_TOKEN_WEB": "tok"}
        )
        assert merged["UNRELATED_KEY"] == "some_value"
        assert merged["ANOTHER_KEY"] == "another_value"
        assert merged["GAMECHANGER_REFRESH_TOKEN_WEB"] == "tok"

    def test_mixed_update_preserves_and_adds(self, tmp_path: Path) -> None:
        env_path = tmp_path / ".env"
        env_path.write_text(
            "UNRELATED_KEY=keep_me\nGAMECHANGER_REFRESH_TOKEN_WEB=old\n",
            encoding="utf-8",
        )
        merged = merge_env_file(
            str(env_path),
            {
                "GAMECHANGER_REFRESH_TOKEN_WEB": "new",
                "GAMECHANGER_BASE_URL": "https://api.example.com",
            },
        )
        assert merged["UNRELATED_KEY"] == "keep_me"
        assert merged["GAMECHANGER_REFRESH_TOKEN_WEB"] == "new"
        assert merged["GAMECHANGER_BASE_URL"] == "https://api.example.com"

    def test_comments_preserved_in_env_file(self, tmp_path: Path) -> None:
        """Comment lines in .env are not parsed as key=value pairs."""
        env_path = tmp_path / ".env"
        env_path.write_text(
            "# This is a comment\nUNRELATED=val\n",
            encoding="utf-8",
        )
        merged = merge_env_file(str(env_path), {"GAMECHANGER_REFRESH_TOKEN": "tok"})
        # The comment should not appear as a key.
        assert "# This is a comment" not in merged
        assert merged["UNRELATED"] == "val"

    def test_multiple_runs_do_not_duplicate_keys(self, tmp_path: Path) -> None:
        """Running merge twice does not create duplicate entries."""
        env_path = tmp_path / ".env"
        merge_env_file(str(env_path), {"GAMECHANGER_REFRESH_TOKEN_WEB": "tok1"})
        merged = merge_env_file(
            str(env_path), {"GAMECHANGER_REFRESH_TOKEN_WEB": "tok2"}
        )
        # Only one occurrence of the key.
        content = env_path.read_text(encoding="utf-8")
        assert content.count("GAMECHANGER_REFRESH_TOKEN_WEB=") == 1
        assert merged["GAMECHANGER_REFRESH_TOKEN_WEB"] == "tok2"


# ---------------------------------------------------------------------------
# Integration: parse_curl -> merge_env_file round-trip
# ---------------------------------------------------------------------------


class TestWebSuffixedKeys:
    """AC-9 (E-053-02): parse_curl outputs _WEB suffixed credential keys."""

    def test_parse_curl_uses_web_suffix_for_token(self) -> None:
        result = parse_curl(MINIMAL_CURL)
        assert "GAMECHANGER_REFRESH_TOKEN_WEB" in result
        assert "GAMECHANGER_REFRESH_TOKEN" not in result

    def test_parse_curl_uses_web_suffix_for_device_id(self) -> None:
        curl = (
            "curl 'https://api.team-manager.gc.com/data' "
            "-H 'gc-token: tok' "
            "-H 'gc-device-id: device123'"
        )
        result = parse_curl(curl)
        assert "GAMECHANGER_DEVICE_ID_WEB" in result
        assert "GAMECHANGER_DEVICE_ID" not in result

    def test_parse_curl_uses_web_suffix_for_app_name(self) -> None:
        curl = (
            "curl 'https://api.team-manager.gc.com/data' "
            "-H 'gc-token: tok' "
            "-H 'gc-app-name: web'"
        )
        result = parse_curl(curl)
        assert "GAMECHANGER_APP_NAME_WEB" in result
        assert "GAMECHANGER_APP_NAME" not in result


class TestRoundTrip:
    """End-to-end: parse a curl command and merge result into a .env file."""

    def test_full_round_trip(self, tmp_path: Path) -> None:
        env_path = tmp_path / ".env"
        env_path.write_text("MY_OTHER_VAR=keep_me\n", encoding="utf-8")

        credentials = parse_curl(FULL_GC_CURL)
        merged = merge_env_file(str(env_path), credentials)

        assert merged["GAMECHANGER_REFRESH_TOKEN_WEB"] == (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.sig"
        )
        assert merged["GAMECHANGER_APP_NAME_WEB"] == "web"
        assert merged["GAMECHANGER_DEVICE_ID_WEB"] == "7b615e8c124f5d44575d4e6736ae1a82"
        assert merged["GAMECHANGER_BASE_URL"] == "https://api.team-manager.gc.com"
        assert merged["MY_OTHER_VAR"] == "keep_me"


# ---------------------------------------------------------------------------
# atomic_merge_env_file -- crash-safe write
# ---------------------------------------------------------------------------


class TestAtomicMergeEnvFile:
    """atomic_merge_env_file shares merge semantics but writes atomically."""

    def test_new_file_written_when_none_exists(self, tmp_path: Path) -> None:
        env_path = tmp_path / ".env"
        assert not env_path.exists()
        merged = atomic_merge_env_file(str(env_path), {"GAMECHANGER_REFRESH_TOKEN_WEB": "tok"})
        assert merged["GAMECHANGER_REFRESH_TOKEN_WEB"] == "tok"
        assert env_path.exists()

    def test_existing_credentials_replaced(self, tmp_path: Path) -> None:
        env_path = tmp_path / ".env"
        env_path.write_text("GAMECHANGER_REFRESH_TOKEN_WEB=old_token\n", encoding="utf-8")
        merged = atomic_merge_env_file(
            str(env_path), {"GAMECHANGER_REFRESH_TOKEN_WEB": "new_token"}
        )
        assert merged["GAMECHANGER_REFRESH_TOKEN_WEB"] == "new_token"

    def test_non_credential_keys_preserved(self, tmp_path: Path) -> None:
        env_path = tmp_path / ".env"
        env_path.write_text("UNRELATED_KEY=some_value\nANOTHER_KEY=another_value\n", encoding="utf-8")
        merged = atomic_merge_env_file(
            str(env_path), {"GAMECHANGER_REFRESH_TOKEN_WEB": "tok"}
        )
        assert merged["UNRELATED_KEY"] == "some_value"
        assert merged["ANOTHER_KEY"] == "another_value"
        assert merged["GAMECHANGER_REFRESH_TOKEN_WEB"] == "tok"

    def test_no_duplicate_keys_on_repeated_writes(self, tmp_path: Path) -> None:
        env_path = tmp_path / ".env"
        atomic_merge_env_file(str(env_path), {"GAMECHANGER_REFRESH_TOKEN_WEB": "tok1"})
        atomic_merge_env_file(str(env_path), {"GAMECHANGER_REFRESH_TOKEN_WEB": "tok2"})
        content = env_path.read_text(encoding="utf-8")
        assert content.count("GAMECHANGER_REFRESH_TOKEN_WEB=") == 1

    def test_comments_preserved(self, tmp_path: Path) -> None:
        env_path = tmp_path / ".env"
        env_path.write_text("# Comment line\nUNRELATED=val\n", encoding="utf-8")
        merged = atomic_merge_env_file(str(env_path), {"NEW_KEY": "val"})
        assert "# Comment line" not in merged  # comments not in returned dict
        assert merged["UNRELATED"] == "val"
        assert merged["NEW_KEY"] == "val"
        # But comment still in file
        assert "# Comment line" in env_path.read_text(encoding="utf-8")

    def test_original_file_intact_after_write(self, tmp_path: Path) -> None:
        """After a successful write the file must be complete and correct."""
        env_path = tmp_path / ".env"
        env_path.write_text("EXISTING=value\n", encoding="utf-8")
        atomic_merge_env_file(str(env_path), {"NEW_KEY": "new_value"})
        content = env_path.read_text(encoding="utf-8")
        assert "EXISTING=value" in content
        assert "NEW_KEY=new_value" in content

    def test_merge_env_file_still_works_unchanged(self, tmp_path: Path) -> None:
        """Verify the existing merge_env_file is unchanged after the refactor."""
        env_path = tmp_path / ".env"
        env_path.write_text("OLD_KEY=old_value\n", encoding="utf-8")
        merged = merge_env_file(str(env_path), {"NEW_KEY": "new_value"})
        assert merged["OLD_KEY"] == "old_value"
        assert merged["NEW_KEY"] == "new_value"
