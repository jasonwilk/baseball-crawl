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
- parse_credentials: GC auth response JSON (with/without user_id/type fields)
- parse_credentials: simple token map JSON
- parse_credentials: single token JSON
- parse_credentials: bare JWT (access and refresh)
- parse_credentials: curl command unchanged
- parse_credentials: unknown format raises CredentialImportError
- parse_credentials: --profile mobile with JSON input
"""

from __future__ import annotations

import base64
import json
import textwrap
import time
from pathlib import Path

import pytest

from src.gamechanger.credential_parser import (
    CredentialImportError,
    CurlParseError,
    atomic_merge_env_file,
    merge_env_file,
    parse_credentials,
    parse_curl,
)


def _make_access_token() -> str:
    """Build a minimal JWT with type='user' (access token)."""
    payload = {"type": "user", "exp": int(time.time()) + 3600, "iat": int(time.time())}
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    )
    return f"eyJhbGciOiJIUzI1NiJ9.{payload_b64}.sig"


def _make_refresh_token() -> str:
    """Build a minimal JWT with no type field (refresh token)."""
    payload = {"id": "uuid:uuid", "exp": int(time.time()) + 1209600, "iat": int(time.time())}
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    )
    return f"eyJhbGciOiJIUzI1NiJ9.{payload_b64}.sig"


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


# ---------------------------------------------------------------------------
# parse_curl -- mobile profile (AC-1 through AC-7)
# ---------------------------------------------------------------------------


class TestMobileProfile:
    """parse_curl(profile='mobile') tests."""

    def _curl(self, token: str, extra_headers: str = "") -> str:
        return (
            f"curl 'https://api.team-manager.gc.com/teams/abc/game-summaries' "
            f"-H 'gc-token: {token}' {extra_headers}"
        )

    # AC-2: access token (type=='user') saved to GAMECHANGER_ACCESS_TOKEN_MOBILE
    def test_access_token_saved_to_mobile_key(self) -> None:
        token = _make_access_token()
        result = parse_curl(self._curl(token), profile="mobile")
        assert result["GAMECHANGER_ACCESS_TOKEN_MOBILE"] == token
        assert "GAMECHANGER_REFRESH_TOKEN_MOBILE" not in result

    # AC-3: refresh token (no type field) saved to GAMECHANGER_REFRESH_TOKEN_MOBILE
    def test_refresh_token_saved_to_mobile_key(self) -> None:
        token = _make_refresh_token()
        result = parse_curl(self._curl(token), profile="mobile")
        assert result["GAMECHANGER_REFRESH_TOKEN_MOBILE"] == token
        assert "GAMECHANGER_ACCESS_TOKEN_MOBILE" not in result

    # AC-1: _MOBILE suffix on all credential keys
    def test_mobile_suffix_on_device_id(self) -> None:
        token = _make_access_token()
        curl = self._curl(token, "-H 'gc-device-id: dev123'")
        result = parse_curl(curl, profile="mobile")
        assert result["GAMECHANGER_DEVICE_ID_MOBILE"] == "dev123"
        assert "GAMECHANGER_DEVICE_ID_WEB" not in result

    def test_mobile_suffix_on_app_name(self) -> None:
        token = _make_access_token()
        curl = self._curl(token, "-H 'gc-app-name: gc'")
        result = parse_curl(curl, profile="mobile")
        assert result["GAMECHANGER_APP_NAME_MOBILE"] == "gc"
        assert "GAMECHANGER_APP_NAME_WEB" not in result

    # AC-7: gc-client-id captured for mobile
    def test_client_id_captured_for_mobile(self) -> None:
        token = _make_access_token()
        curl = self._curl(token, "-H 'gc-client-id: 0f18f027-c51e-4122-a330-9d537beb83e0'")
        result = parse_curl(curl, profile="mobile")
        assert result["GAMECHANGER_CLIENT_ID_MOBILE"] == "0f18f027-c51e-4122-a330-9d537beb83e0"

    # AC-7: gc-client-id captured for web too
    def test_client_id_captured_for_web(self) -> None:
        curl = (
            "curl 'https://api.team-manager.gc.com/data' "
            "-H 'gc-token: eyJhbGciOiJIUzI1NiJ9.payload.sig' "
            "-H 'gc-client-id: 07cb985d-0000-0000-0000-000000000000'"
        )
        result = parse_curl(curl)  # default web profile
        assert result["GAMECHANGER_CLIENT_ID_WEB"] == "07cb985d-0000-0000-0000-000000000000"

    # AC-4: web profile still rejects access tokens
    def test_web_profile_rejects_access_token(self) -> None:
        token = _make_access_token()
        curl = self._curl(token)
        with pytest.raises(CurlParseError, match="gc-token"):
            parse_curl(curl, profile="web")

    # AC-5 / AC-6: web profile (explicit or default) has same behavior
    def test_web_explicit_same_as_default(self) -> None:
        curl = (
            "curl 'https://api.team-manager.gc.com/data' "
            "-H 'gc-token: eyJhbGciOiJIUzI1NiJ9.payload.sig'"
        )
        result_default = parse_curl(curl)
        result_web = parse_curl(curl, profile="web")
        assert result_default == result_web

    # Missing gc-token raises for mobile too
    def test_missing_gc_token_raises_for_mobile(self) -> None:
        curl = (
            "curl 'https://api.team-manager.gc.com/data' "
            "-H 'gc-device-id: dev123'"
        )
        with pytest.raises(CurlParseError, match="gc-token"):
            parse_curl(curl, profile="mobile")


# ---------------------------------------------------------------------------
# parse_credentials -- auto-detection: curl commands (AC-3)
# ---------------------------------------------------------------------------


class TestParseCredentialsCurl:
    """parse_credentials delegates to parse_curl for curl-format inputs."""

    def test_curl_command_routed_correctly(self) -> None:
        result = parse_credentials(MINIMAL_CURL)
        assert "GAMECHANGER_REFRESH_TOKEN_WEB" in result
        assert "GAMECHANGER_BASE_URL" in result

    def test_curl_command_case_insensitive(self) -> None:
        curl = MINIMAL_CURL.replace("curl ", "CURL ", 1)
        result = parse_credentials(curl)
        assert "GAMECHANGER_REFRESH_TOKEN_WEB" in result

    def test_curl_raises_curl_parse_error_as_credential_import_error(self) -> None:
        """CurlParseError is a subclass of CredentialImportError."""
        with pytest.raises(CredentialImportError):
            parse_credentials("curl 'https://example.com'")  # no gc-token


# ---------------------------------------------------------------------------
# parse_credentials -- JSON: GC auth response (AC-1)
# ---------------------------------------------------------------------------


def _gc_auth_json(access_token: str, refresh_token: str, extra: dict | None = None) -> str:
    """Build a GC auth response JSON string."""
    payload: dict = {
        "type": "token",
        "access": {"data": access_token, "expires": int(time.time()) + 3600},
        "refresh": {"data": refresh_token, "expires": int(time.time()) + 1209600},
    }
    if extra:
        payload.update(extra)
    return json.dumps(payload)


class TestParseCredentialsGcAuthJson:
    """AC-1: GC auth response JSON format."""

    def test_extracts_refresh_token_web_profile(self) -> None:
        refresh = _make_refresh_token()
        access = _make_access_token()
        input_json = _gc_auth_json(access, refresh)
        result = parse_credentials(input_json, profile="web")
        assert result["GAMECHANGER_REFRESH_TOKEN_WEB"] == refresh
        # Access token not stored for web profile
        assert "GAMECHANGER_ACCESS_TOKEN_WEB" not in result

    def test_extracts_both_tokens_mobile_profile(self) -> None:
        refresh = _make_refresh_token()
        access = _make_access_token()
        input_json = _gc_auth_json(access, refresh)
        result = parse_credentials(input_json, profile="mobile")
        assert result["GAMECHANGER_REFRESH_TOKEN_MOBILE"] == refresh
        assert result["GAMECHANGER_ACCESS_TOKEN_MOBILE"] == access

    def test_tolerates_extra_user_id_field(self) -> None:
        """Top-level user_id field must be tolerated."""
        refresh = _make_refresh_token()
        access = _make_access_token()
        input_json = _gc_auth_json(access, refresh, extra={"user_id": "some-uuid"})
        result = parse_credentials(input_json, profile="web")
        assert result["GAMECHANGER_REFRESH_TOKEN_WEB"] == refresh

    def test_tolerates_missing_type_field(self) -> None:
        """GC auth shape detected from 'access'/'refresh' keys, not 'type'."""
        refresh = _make_refresh_token()
        access = _make_access_token()
        payload = {
            "access": {"data": access, "expires": int(time.time()) + 3600},
            "refresh": {"data": refresh, "expires": int(time.time()) + 1209600},
        }
        result = parse_credentials(json.dumps(payload), profile="web")
        assert result["GAMECHANGER_REFRESH_TOKEN_WEB"] == refresh

    def test_refresh_only_json_web_profile(self) -> None:
        """JSON with only 'refresh' key works for web profile."""
        refresh = _make_refresh_token()
        payload = {"refresh": {"data": refresh, "expires": int(time.time()) + 1209600}}
        result = parse_credentials(json.dumps(payload), profile="web")
        assert result["GAMECHANGER_REFRESH_TOKEN_WEB"] == refresh


# ---------------------------------------------------------------------------
# parse_credentials -- JSON: simple token map (AC-1b)
# ---------------------------------------------------------------------------


class TestParseCredentialsTokenMap:
    """AC-1b: Simple token map JSON format."""

    def test_access_and_refresh_mobile_profile(self) -> None:
        access = _make_access_token()
        refresh = _make_refresh_token()
        payload = {"access_token": access, "refresh_token": refresh}
        result = parse_credentials(json.dumps(payload), profile="mobile")
        assert result["GAMECHANGER_ACCESS_TOKEN_MOBILE"] == access
        assert result["GAMECHANGER_REFRESH_TOKEN_MOBILE"] == refresh

    def test_refresh_only_web_profile(self) -> None:
        refresh = _make_refresh_token()
        payload = {"refresh_token": refresh}
        result = parse_credentials(json.dumps(payload), profile="web")
        assert result["GAMECHANGER_REFRESH_TOKEN_WEB"] == refresh

    def test_access_only_web_profile_raises(self) -> None:
        """Web profile does not store access tokens -- error when that's all we have."""
        access = _make_access_token()
        payload = {"access_token": access}
        with pytest.raises(CredentialImportError):
            parse_credentials(json.dumps(payload), profile="web")


# ---------------------------------------------------------------------------
# parse_credentials -- JSON: single token (AC-1b)
# ---------------------------------------------------------------------------


class TestParseCredentialsSingleToken:
    """AC-1b: Single token JSON format."""

    def test_refresh_token_web_profile(self) -> None:
        refresh = _make_refresh_token()
        payload = {"token": refresh}
        result = parse_credentials(json.dumps(payload), profile="web")
        assert result["GAMECHANGER_REFRESH_TOKEN_WEB"] == refresh

    def test_access_token_mobile_profile(self) -> None:
        access = _make_access_token()
        payload = {"token": access}
        result = parse_credentials(json.dumps(payload), profile="mobile")
        assert result["GAMECHANGER_ACCESS_TOKEN_MOBILE"] == access

    def test_access_token_web_profile_raises(self) -> None:
        access = _make_access_token()
        payload = {"token": access}
        with pytest.raises(CredentialImportError):
            parse_credentials(json.dumps(payload), profile="web")

    def test_unrecognised_json_shape_raises(self) -> None:
        payload = {"something_else": "value"}
        with pytest.raises(CredentialImportError):
            parse_credentials(json.dumps(payload))


# ---------------------------------------------------------------------------
# parse_credentials -- bare JWT (AC-2)
# ---------------------------------------------------------------------------


class TestParseCredentialsBareJwt:
    """AC-2: Bare JWT string auto-detection and routing."""

    def test_refresh_token_web_profile(self) -> None:
        refresh = _make_refresh_token()
        result = parse_credentials(refresh, profile="web")
        assert result["GAMECHANGER_REFRESH_TOKEN_WEB"] == refresh

    def test_access_token_mobile_profile(self) -> None:
        access = _make_access_token()
        result = parse_credentials(access, profile="mobile")
        assert result["GAMECHANGER_ACCESS_TOKEN_MOBILE"] == access

    def test_refresh_token_mobile_profile(self) -> None:
        refresh = _make_refresh_token()
        result = parse_credentials(refresh, profile="mobile")
        assert result["GAMECHANGER_REFRESH_TOKEN_MOBILE"] == refresh

    def test_access_token_web_profile_raises(self) -> None:
        """Access token passed with web profile should raise CredentialImportError."""
        access = _make_access_token()
        with pytest.raises(CredentialImportError):
            parse_credentials(access, profile="web")

    def test_bare_jwt_with_leading_whitespace(self) -> None:
        """Leading whitespace is stripped before detection."""
        refresh = _make_refresh_token()
        result = parse_credentials("  \n" + refresh, profile="web")
        assert result["GAMECHANGER_REFRESH_TOKEN_WEB"] == refresh


# ---------------------------------------------------------------------------
# parse_credentials -- unknown format (AC-4)
# ---------------------------------------------------------------------------


class TestParseCredentialsUnknownFormat:
    """AC-4: Unknown input format raises CredentialImportError."""

    def test_plain_text_raises(self) -> None:
        with pytest.raises(CredentialImportError):
            parse_credentials("not a curl, json, or jwt")

    def test_empty_string_raises(self) -> None:
        with pytest.raises((CredentialImportError, CurlParseError)):
            parse_credentials("")

    def test_error_message_mentions_accepted_formats(self) -> None:
        with pytest.raises(CredentialImportError) as exc_info:
            parse_credentials("totally unrecognized input here")
        msg = str(exc_info.value)
        assert "curl" in msg.lower() or "json" in msg.lower() or "jwt" in msg.lower()


# ---------------------------------------------------------------------------
# parse_credentials -- mobile profile with JSON input (AC-6)
# ---------------------------------------------------------------------------


class TestParseCredentialsMobileJson:
    """AC-6: --profile mobile applies to all non-curl formats."""

    def test_gc_auth_mobile_profile_stores_both_tokens(self) -> None:
        access = _make_access_token()
        refresh = _make_refresh_token()
        input_json = _gc_auth_json(access, refresh)
        result = parse_credentials(input_json, profile="mobile")
        assert result["GAMECHANGER_ACCESS_TOKEN_MOBILE"] == access
        assert result["GAMECHANGER_REFRESH_TOKEN_MOBILE"] == refresh
        assert "GAMECHANGER_ACCESS_TOKEN_WEB" not in result
        assert "GAMECHANGER_REFRESH_TOKEN_WEB" not in result

    def test_token_map_mobile_profile_uses_mobile_keys(self) -> None:
        access = _make_access_token()
        refresh = _make_refresh_token()
        payload = {"access_token": access, "refresh_token": refresh}
        result = parse_credentials(json.dumps(payload), profile="mobile")
        assert "GAMECHANGER_ACCESS_TOKEN_MOBILE" in result
        assert "GAMECHANGER_REFRESH_TOKEN_MOBILE" in result
        assert "GAMECHANGER_ACCESS_TOKEN_WEB" not in result
        assert "GAMECHANGER_REFRESH_TOKEN_WEB" not in result

    def test_bare_jwt_mobile_profile_access_token(self) -> None:
        access = _make_access_token()
        result = parse_credentials(access, profile="mobile")
        assert result["GAMECHANGER_ACCESS_TOKEN_MOBILE"] == access


# ---------------------------------------------------------------------------
# CredentialImportError hierarchy
# ---------------------------------------------------------------------------


class TestCredentialImportErrorHierarchy:
    """CurlParseError must be a subclass of CredentialImportError."""

    def test_curl_parse_error_is_credential_import_error(self) -> None:
        err = CurlParseError("test")
        assert isinstance(err, CredentialImportError)

    def test_catch_base_class_catches_curl_parse_error(self) -> None:
        with pytest.raises(CredentialImportError):
            parse_credentials("not a curl but looks like wget https://example.com")
