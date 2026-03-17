"""Tests for the ``bb creds`` CLI sub-app (src/cli/creds.py).

Tests use CliRunner to exercise argument mapping only -- business logic
(curl parsing, credential writing, API calls) is mocked.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# bb creds import
# ---------------------------------------------------------------------------


class TestCredsImport:
    """Argument mapping tests for ``bb creds import``."""

    _FAKE_CREDENTIALS = {
        "GAMECHANGER_REFRESH_TOKEN_WEB": "tok_abc",
        "GAMECHANGER_DEVICE_ID_WEB": "dev_xyz",
        "GAMECHANGER_BASE_URL": "https://api.gc.com",
    }
    _MERGED = {**_FAKE_CREDENTIALS, "SOME_OTHER_KEY": "other_value"}

    def _invoke(self, args: list[str], curl_file_exists: bool = True):
        """Run the CLI with parse_curl and merge_env_file mocked."""
        with (
            patch("src.cli.creds.parse_curl", return_value=self._FAKE_CREDENTIALS) as mock_parse,
            patch("src.cli.creds.merge_env_file", return_value=self._MERGED) as mock_merge,
            patch("src.cli.creds._DEFAULT_CURL_FILE") as mock_default,
        ):
            mock_default.exists.return_value = curl_file_exists
            mock_default.read_text.return_value = "curl 'https://api.gc.com' -H 'gc-token: tok'"
            mock_default.__str__ = lambda _: "secrets/gamechanger-curl.txt"
            result = runner.invoke(app, args)
            return result, mock_parse, mock_merge

    def test_default_reads_from_default_file(self) -> None:
        """Default (no flags) reads from DEFAULT_CURL_FILE."""
        result, mock_parse, _ = self._invoke(["creds", "import"])
        assert result.exit_code == 0
        mock_parse.assert_called_once()

    def test_curl_flag_passes_inline_string(self) -> None:
        """--curl flag passes the inline string directly to parse_curl with profile='web'."""
        inline = "curl 'https://api.gc.com' -H 'gc-token: tok'"
        with (
            patch("src.cli.creds.parse_curl", return_value=self._FAKE_CREDENTIALS) as mock_parse,
            patch("src.cli.creds.merge_env_file", return_value=self._MERGED),
        ):
            result = runner.invoke(app, ["creds", "import", "--curl", inline])
        assert result.exit_code == 0
        mock_parse.assert_called_once_with(inline, profile="web")

    def test_file_flag_reads_from_path(self, tmp_path: Path) -> None:
        """--file flag reads from the given path."""
        curl_file = tmp_path / "my-curl.txt"
        curl_file.write_text("curl 'https://api.gc.com' -H 'gc-token: tok'", encoding="utf-8")
        with (
            patch("src.cli.creds.parse_curl", return_value=self._FAKE_CREDENTIALS) as mock_parse,
            patch("src.cli.creds.merge_env_file", return_value=self._MERGED),
        ):
            result = runner.invoke(app, ["creds", "import", "--file", str(curl_file)])
        assert result.exit_code == 0
        mock_parse.assert_called_once()
        called_arg = mock_parse.call_args[0][0]
        assert "curl" in called_arg

    def test_curl_and_file_mutually_exclusive(self) -> None:
        """--curl and --file together produce an error exit."""
        result, _, _ = self._invoke(["creds", "import", "--curl", "curl ...", "--file", "/some/path"])
        assert result.exit_code != 0

    def test_output_contains_key_names_not_values(self) -> None:
        """Output lists key names (e.g., GAMECHANGER_REFRESH_TOKEN_WEB) but not their values."""
        result, _, _ = self._invoke(["creds", "import"])
        assert result.exit_code == 0
        output = result.output
        # Key names must appear in output.
        for key in self._FAKE_CREDENTIALS:
            assert key in output
        # Actual secret values must NOT appear in output.
        for value in self._FAKE_CREDENTIALS.values():
            assert value not in output

    def test_missing_default_file_exits_nonzero(self) -> None:
        """Missing default curl file produces a non-zero exit and helpful message."""
        result, _, _ = self._invoke(["creds", "import"], curl_file_exists=False)
        assert result.exit_code != 0

    def test_curl_parse_error_exits_nonzero(self) -> None:
        """CurlParseError from parse_curl produces a non-zero exit."""
        from src.gamechanger.credential_parser import CurlParseError

        with (
            patch("src.cli.creds.parse_curl", side_effect=CurlParseError("bad curl")),
            patch("src.cli.creds._DEFAULT_CURL_FILE") as mock_default,
        ):
            mock_default.exists.return_value = True
            mock_default.read_text.return_value = "not a curl command"
            mock_default.__str__ = lambda _: "secrets/gamechanger-curl.txt"
            result = runner.invoke(app, ["creds", "import"])
        assert result.exit_code != 0

    def test_profile_mobile_passes_to_parse_curl(self) -> None:
        """--profile mobile is forwarded to parse_curl."""
        inline = "curl 'https://api.gc.com' -H 'gc-token: tok'"
        mobile_creds = {
            "GAMECHANGER_ACCESS_TOKEN_MOBILE": "access_tok",
            "GAMECHANGER_BASE_URL": "https://api.gc.com",
        }
        with (
            patch("src.cli.creds.parse_curl", return_value=mobile_creds) as mock_parse,
            patch("src.cli.creds.merge_env_file", return_value=mobile_creds),
        ):
            result = runner.invoke(app, ["creds", "import", "--profile", "mobile", "--curl", inline])
        assert result.exit_code == 0
        mock_parse.assert_called_once_with(inline, profile="mobile")

    def test_profile_web_explicit_same_as_default(self) -> None:
        """--profile web explicit behaves identically to no-flag (default)."""
        inline = "curl 'https://api.gc.com' -H 'gc-token: tok'"
        with (
            patch("src.cli.creds.parse_curl", return_value=self._FAKE_CREDENTIALS) as mock_parse,
            patch("src.cli.creds.merge_env_file", return_value=self._MERGED),
        ):
            result = runner.invoke(app, ["creds", "import", "--profile", "web", "--curl", inline])
        assert result.exit_code == 0
        mock_parse.assert_called_once_with(inline, profile="web")

    def test_output_shows_mobile_key_names(self) -> None:
        """Output lists MOBILE-suffixed key names when --profile mobile is used."""
        mobile_creds = {
            "GAMECHANGER_ACCESS_TOKEN_MOBILE": "access_tok",
            "GAMECHANGER_BASE_URL": "https://api.gc.com",
        }
        inline = "curl 'https://api.gc.com' -H 'gc-token: tok'"
        with (
            patch("src.cli.creds.parse_curl", return_value=mobile_creds),
            patch("src.cli.creds.merge_env_file", return_value=mobile_creds),
        ):
            result = runner.invoke(app, ["creds", "import", "--profile", "mobile", "--curl", inline])
        assert result.exit_code == 0
        assert "GAMECHANGER_ACCESS_TOKEN_MOBILE" in result.output
        # Actual token values must NOT appear.
        assert "access_tok" not in result.output

    def test_token_metadata_shown_for_valid_jwt(self) -> None:
        """AC-8: After import a token lifetime line appears in output for a real JWT."""
        import base64
        import json
        import time

        exp = int(time.time()) + 43200  # ~12 hours
        payload = {"exp": exp}
        payload_b64 = (
            base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        )
        real_token = f"header.{payload_b64}.sig"
        creds_with_real_token = {
            "GAMECHANGER_REFRESH_TOKEN_WEB": real_token,
            "GAMECHANGER_BASE_URL": "https://api.gc.com",
        }
        with (
            patch("src.cli.creds.parse_curl", return_value=creds_with_real_token),
            patch("src.cli.creds.merge_env_file", return_value=creds_with_real_token),
        ):
            result = runner.invoke(app, ["creds", "import"])
        assert result.exit_code == 0
        # Some kind of lifetime info should appear.
        assert "hour" in result.output or "day" in result.output or "minute" in result.output
        # The raw token value must NOT appear.
        assert real_token not in result.output


# ---------------------------------------------------------------------------
# bb creds check
# ---------------------------------------------------------------------------


def _make_profile_result(
    profile: str = "web",
    exit_code: int = 0,
    keys_present: list[str] | None = None,
    keys_missing: list[str] | None = None,
) -> "ProfileCheckResult":
    """Build a minimal ProfileCheckResult for CLI tests."""
    import time

    from src.gamechanger.credentials import (
        ApiCheckResult,
        CredentialPresence,
        ProfileCheckResult,
        TokenHealth,
    )
    from src.http.proxy_check import ProxyCheckOutcome, ProxyCheckResult

    api_msg = "200 OK, logged in as Jason Smith" if exit_code == 0 else "Credentials expired"
    return ProfileCheckResult(
        profile=profile,
        presence=CredentialPresence(
            keys_present=keys_present or ["GAMECHANGER_BASE_URL"],
            keys_missing=keys_missing or [],
        ),
        token_health=TokenHealth(exp=int(time.time()) + 86400, is_expired=False),
        api_result=ApiCheckResult(
            exit_code=exit_code,
            display_name="Jason Smith" if exit_code == 0 else None,
            message=api_msg,
        ),
        proxy_result=ProxyCheckResult(profile=profile, outcome=ProxyCheckOutcome.NOT_CONFIGURED),
        exit_code=exit_code,
    )


class TestCredsCheck:
    """Argument mapping and output format tests for ``bb creds check``."""

    def _invoke_check(self, args: list[str], exit_code: int = 0, profile: str = "web"):
        result_obj = _make_profile_result(profile=profile, exit_code=exit_code)
        with patch(
            "src.cli.creds.check_profile_detailed", return_value=result_obj
        ) as mock_fn:
            result = runner.invoke(app, args)
        return result, mock_fn

    def test_check_single_profile_calls_check_profile_detailed(self) -> None:
        """``bb creds check --profile web`` calls check_profile_detailed with 'web'."""
        result, mock_fn = self._invoke_check(["creds", "check", "--profile", "web"])
        assert result.exit_code == 0
        mock_fn.assert_called_once_with("web")

    def test_check_mobile_profile(self) -> None:
        """``bb creds check --profile mobile`` calls check_profile_detailed with 'mobile'."""
        result, mock_fn = self._invoke_check(
            ["creds", "check", "--profile", "mobile"], profile="mobile"
        )
        assert result.exit_code == 0
        mock_fn.assert_called_once_with("mobile")

    def test_check_expired_exits_1(self) -> None:
        """Expired credentials: exit code 1."""
        result, _ = self._invoke_check(["creds", "check", "--profile", "web"], exit_code=1)
        assert result.exit_code == 1

    def test_check_missing_exits_2(self) -> None:
        """Missing credentials: exit code 2."""
        missing_result = _make_profile_result(exit_code=2, keys_missing=["GAMECHANGER_BASE_URL"])
        with patch("src.cli.creds.check_profile_detailed", return_value=missing_result):
            result = runner.invoke(app, ["creds", "check", "--profile", "web"])
        assert result.exit_code == 2

    def test_check_output_shows_status_indicators(self) -> None:
        """Output contains Rich status indicator text."""
        result, _ = self._invoke_check(["creds", "check", "--profile", "web"])
        # Rich strips markup but the literal bracket text is rendered
        assert "[OK]" in result.output or "OK" in result.output

    def test_check_output_shows_profile_name(self) -> None:
        """Panel title contains the profile name."""
        result, _ = self._invoke_check(["creds", "check", "--profile", "web"])
        assert "web" in result.output

    def test_check_output_shows_test_endpoint(self) -> None:
        """AC-6: Output displays the test endpoint used."""
        result, _ = self._invoke_check(["creds", "check", "--profile", "web"])
        assert "/me/user" in result.output

    def test_check_output_no_credential_values(self) -> None:
        """AC-9: Credential values (tokens, proxy URLs) never appear in output."""
        secret_token = "super-secret-token-value"
        result_obj = _make_profile_result()
        with patch("src.cli.creds.check_profile_detailed", return_value=result_obj):
            result = runner.invoke(app, ["creds", "check", "--profile", "web"])
        assert secret_token not in result.output

    def test_check_no_profile_calls_each_profile(self) -> None:
        """``bb creds check`` (no --profile) calls check_profile_detailed for each profile."""
        web_result = _make_profile_result(profile="web", exit_code=0)
        mobile_result = _make_profile_result(profile="mobile", exit_code=1)
        with patch(
            "src.cli.creds.check_profile_detailed", side_effect=[web_result, mobile_result]
        ) as mock_fn:
            result = runner.invoke(app, ["creds", "check"])
        assert mock_fn.call_count == 2

    def test_check_no_profile_exit_0_if_any_valid(self) -> None:
        """Multi-profile: exit 0 when at least one profile valid."""
        web_result = _make_profile_result(profile="web", exit_code=0)
        mobile_result = _make_profile_result(profile="mobile", exit_code=1)
        with patch(
            "src.cli.creds.check_profile_detailed", side_effect=[web_result, mobile_result]
        ):
            result = runner.invoke(app, ["creds", "check"])
        assert result.exit_code == 0

    def test_check_no_profile_exit_1_if_all_fail(self) -> None:
        """Multi-profile: exit 1 when all profiles fail."""
        web_result = _make_profile_result(profile="web", exit_code=1)
        mobile_result = _make_profile_result(profile="mobile", exit_code=1)
        with patch(
            "src.cli.creds.check_profile_detailed", side_effect=[web_result, mobile_result]
        ):
            result = runner.invoke(app, ["creds", "check"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Client Key Validation rendering tests
# ---------------------------------------------------------------------------


def _make_profile_result_with_client_key(
    status: str,
    message: str,
    skew_seconds: int | None = None,
) -> "ProfileCheckResult":
    """Build a ProfileCheckResult with a specific client_key_result for rendering tests."""
    import time

    from src.gamechanger.credentials import (
        ApiCheckResult,
        ClientKeyCheckResult,
        CredentialPresence,
        ProfileCheckResult,
        TokenHealth,
    )
    from src.http.proxy_check import ProxyCheckOutcome, ProxyCheckResult

    return ProfileCheckResult(
        profile="web",
        presence=CredentialPresence(keys_present=["GAMECHANGER_BASE_URL"], keys_missing=[]),
        token_health=TokenHealth(exp=int(time.time()) + 86400, is_expired=False),
        api_result=ApiCheckResult(exit_code=0, display_name="Coach", message="200 OK"),
        proxy_result=ProxyCheckResult(profile="web", outcome=ProxyCheckOutcome.NOT_CONFIGURED),
        exit_code=0,
        client_key_result=ClientKeyCheckResult(
            status=status, message=message, skew_seconds=skew_seconds
        ),
    )


class TestClientKeyRendering:
    """Tests for _render_client_key_section output in bb creds check."""

    def _invoke_with_key_result(self, status: str, message: str, skew_seconds: int | None = None):
        result_obj = _make_profile_result_with_client_key(status, message, skew_seconds)
        with patch("src.cli.creds.check_profile_detailed", return_value=result_obj):
            return runner.invoke(app, ["creds", "check", "--profile", "web"])

    def test_valid_key_shows_ok_indicator(self) -> None:
        """AC-5: valid status → [OK] indicator."""
        result = self._invoke_with_key_result(
            "valid", "Client key verified (POST /auth client-auth succeeded)"
        )
        assert "[OK]" in result.output or "OK" in result.output
        assert "verified" in result.output.lower() or "succeeded" in result.output.lower()

    def test_invalid_key_shows_xx_indicator(self) -> None:
        """AC-6: invalid status → [XX] indicator."""
        result = self._invoke_with_key_result(
            "invalid", "Client key rejected -- update via: bb creds extract-key"
        )
        assert "[XX]" in result.output or "XX" in result.output
        assert "extract-key" in result.output

    def test_clock_skew_shows_warning_indicator(self) -> None:
        """AC-7: clock_skew status → [!!] indicator."""
        result = self._invoke_with_key_result(
            "clock_skew",
            "Possible clock skew (95 seconds difference) -- check system clock",
            skew_seconds=95,
        )
        assert "[!!]" in result.output or "!!" in result.output
        assert "clock" in result.output.lower() or "skew" in result.output.lower()

    def test_error_shows_warning_indicator(self) -> None:
        """AC-9a: error status → [!!] indicator (cannot confirm key is bad)."""
        result = self._invoke_with_key_result(
            "error", "Client key validation failed (network error: connection refused)"
        )
        assert "[!!]" in result.output or "!!" in result.output
        assert "network" in result.output.lower() or "error" in result.output.lower()

    def test_skipped_missing_key_shows_dim_indicator(self) -> None:
        """AC-8: skipped status (missing key) → [--] indicator."""
        result = self._invoke_with_key_result(
            "skipped", "Client key not configured (GAMECHANGER_CLIENT_KEY_WEB)"
        )
        assert "[--]" in result.output or "--" in result.output
        assert "GAMECHANGER_CLIENT_KEY_WEB" in result.output

    def test_skipped_mobile_shows_dim_indicator(self) -> None:
        """AC-9: skipped status (mobile) → [--] indicator."""
        from src.gamechanger.credentials import (
            ApiCheckResult,
            ClientKeyCheckResult,
            CredentialPresence,
            ProfileCheckResult,
            TokenHealth,
        )
        from src.http.proxy_check import ProxyCheckOutcome, ProxyCheckResult
        import time

        result_obj = ProfileCheckResult(
            profile="mobile",
            presence=CredentialPresence(keys_present=[], keys_missing=[]),
            token_health=TokenHealth(exp=int(time.time()) + 86400, is_expired=False),
            api_result=ApiCheckResult(exit_code=0, display_name=None, message="ok"),
            proxy_result=ProxyCheckResult(profile="mobile", outcome=ProxyCheckOutcome.NOT_CONFIGURED),
            exit_code=0,
            client_key_result=ClientKeyCheckResult(
                status="skipped", message="Client key not available for mobile profile"
            ),
        )
        with patch("src.cli.creds.check_profile_detailed", return_value=result_obj):
            result = runner.invoke(app, ["creds", "check", "--profile", "mobile"])
        assert "[--]" in result.output or "--" in result.output
        assert "mobile" in result.output.lower()

    def test_none_client_key_result_shows_dim_indicator(self) -> None:
        """AC-15: client_key_result=None → [--] dim indicator (legacy result)."""
        result_obj = _make_profile_result()  # client_key_result defaults to None
        with patch("src.cli.creds.check_profile_detailed", return_value=result_obj):
            result = runner.invoke(app, ["creds", "check", "--profile", "web"])
        assert "[--]" in result.output or "--" in result.output

    def test_client_key_section_heading_present(self) -> None:
        """AC-4: 'Client Key Validation' section heading appears in output."""
        result = self._invoke_with_key_result(
            "valid", "Client key verified (POST /auth client-auth succeeded)"
        )
        assert "Client Key" in result.output

    def test_client_key_section_between_token_and_api(self) -> None:
        """AC-4: Client Key Validation section appears between Refresh Token and API Health."""
        result = self._invoke_with_key_result(
            "valid", "Client key verified"
        )
        output = result.output
        token_pos = output.find("Refresh Token")
        key_pos = output.find("Client Key")
        api_pos = output.find("API Health")
        assert token_pos != -1, "Refresh Token section not found"
        assert key_pos != -1, "Client Key section not found"
        assert api_pos != -1, "API Health section not found"
        assert token_pos < key_pos < api_pos, (
            "Client Key section must appear between Refresh Token and API Health"
        )


# ---------------------------------------------------------------------------
# bb creds --help
# ---------------------------------------------------------------------------


class TestCredsHelp:
    def test_help_lists_import_check_and_refresh(self) -> None:
        """``bb creds --help`` lists import, check, and refresh sub-commands."""
        result = runner.invoke(app, ["creds", "--help"])
        assert result.exit_code == 0
        assert "import" in result.output
        assert "check" in result.output
        assert "refresh" in result.output

    def test_import_help_mentions_curl(self) -> None:
        """``bb creds import --help`` help string mentions 'curl'."""
        result = runner.invoke(app, ["creds", "import", "--help"])
        assert result.exit_code == 0
        assert "curl" in result.output.lower()

    def test_refresh_help_mentions_token(self) -> None:
        """``bb creds refresh --help`` help string mentions 'token'."""
        result = runner.invoke(app, ["creds", "refresh", "--help"])
        assert result.exit_code == 0
        assert "token" in result.output.lower()


# ---------------------------------------------------------------------------
# bb creds refresh (programmatic token refresh)
# ---------------------------------------------------------------------------

_FAKE_ACCESS_TOKEN = (
    # A minimal JWT: header.payload.signature where payload has exp = now + 3600.
    # We build it dynamically in the helper below.
    "placeholder"
)


def _make_fake_token(exp_offset: int = 3600) -> str:
    """Build a minimal JWT with a real exp claim for testing."""
    import base64, json, time  # noqa: E401

    payload = {"exp": int(time.time()) + exp_offset}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"header.{payload_b64}.sig"


_ENV_PATCH = {
    "GAMECHANGER_CLIENT_ID_WEB": "client-id",
    "GAMECHANGER_CLIENT_KEY_WEB": "client-key",
    "GAMECHANGER_REFRESH_TOKEN_WEB": "refresh-tok",
    "GAMECHANGER_DEVICE_ID_WEB": "device-id",
    "GAMECHANGER_BASE_URL": "https://api.gc.com",
}


class TestCredsRefresh:
    """Tests for ``bb creds refresh`` (programmatic token refresh)."""

    def _invoke(self, args: list[str], token_return: str | None = None, side_effect: Exception | None = None):
        with (
            patch("src.cli.creds.dotenv_values", return_value=_ENV_PATCH),
            patch("src.cli.creds.TokenManager") as MockTM,
        ):
            instance = MockTM.return_value
            if side_effect is not None:
                instance.force_refresh.side_effect = side_effect
            else:
                instance.force_refresh.return_value = token_return or _make_fake_token()
            result = runner.invoke(app, args)
        return result, MockTM

    def test_success_web_profile(self) -> None:
        """Success path: prints token expiry and .env update confirmation."""
        result, _ = self._invoke(["creds", "refresh"])
        assert result.exit_code == 0
        assert "refreshed" in result.output
        assert "web" in result.output
        # Confirm the softened message is present (not the false-success ".env updated" wording)
        assert "TokenManager" in result.output or "write-back" in result.output or ".env" in result.output

    def test_success_expiry_in_output(self) -> None:
        """Success path: output includes 'expires in Ns'."""
        result, _ = self._invoke(["creds", "refresh"], token_return=_make_fake_token(3547))
        assert result.exit_code == 0
        assert "expires in" in result.output

    def test_web_flag_same_as_default(self) -> None:
        """--profile web behaves identically to no-flag invocation."""
        result, _ = self._invoke(["creds", "refresh", "--profile", "web"])
        assert result.exit_code == 0
        assert "web" in result.output

    def test_mobile_profile_exits_nonzero(self) -> None:
        """--profile mobile prints clear error and exits non-zero."""
        result = runner.invoke(app, ["creds", "refresh", "--profile", "mobile"])
        assert result.exit_code != 0
        assert "mobile" in result.output.lower()
        assert "not yet available" in result.output.lower() or "not" in result.output.lower()

    def test_missing_credentials_exits_nonzero(self) -> None:
        """Missing .env keys print helpful error naming the missing keys."""
        empty_env: dict = {}
        with patch("src.cli.creds.dotenv_values", return_value=empty_env):
            result = runner.invoke(app, ["creds", "refresh"])
        assert result.exit_code != 0
        assert "Missing" in result.output or "missing" in result.output

    def test_credential_expired_error_exits_nonzero(self) -> None:
        """CredentialExpiredError: message directs user to bb creds import."""
        from src.gamechanger.exceptions import CredentialExpiredError

        result, _ = self._invoke(["creds", "refresh"], side_effect=CredentialExpiredError("expired"))
        assert result.exit_code != 0
        assert "import" in result.output
        # The exception message itself should appear in the output (P2-3 fix).
        assert "expired" in result.output

    def test_auth_signing_error_exits_nonzero(self) -> None:
        """AuthSigningError: message mentions clock skew."""
        from src.gamechanger.token_manager import AuthSigningError

        result, _ = self._invoke(["creds", "refresh"], side_effect=AuthSigningError("bad sig"))
        assert result.exit_code != 0
        assert "clock" in result.output.lower() or "signature" in result.output.lower()

    def test_cli_does_not_write_env_directly(self) -> None:
        """CLI command does not call merge_env_file or atomic_merge_env_file."""
        with (
            patch("src.cli.creds.dotenv_values", return_value=_ENV_PATCH),
            patch("src.cli.creds.TokenManager") as MockTM,
            patch("src.cli.creds.merge_env_file") as mock_merge,
        ):
            MockTM.return_value.force_refresh.return_value = _make_fake_token()
            runner.invoke(app, ["creds", "refresh"])
        mock_merge.assert_not_called()

    def test_network_error_exits_nonzero(self) -> None:
        """Network errors from force_refresh produce a non-zero exit and user-friendly message."""
        import httpx

        result, _ = self._invoke(
            ["creds", "refresh"],
            side_effect=httpx.ConnectError("Connection refused"),
        )
        assert result.exit_code != 0
        # Output should include the error message, not a raw traceback heading.
        assert "Error" in result.output or "Connection" in result.output
        assert "Traceback" not in result.output

    def test_credential_expired_includes_message(self) -> None:
        """CredentialExpiredError output preserves the exception message (e.g., HTTP status)."""
        from src.gamechanger.exceptions import CredentialExpiredError

        result, _ = self._invoke(
            ["creds", "refresh"],
            side_effect=CredentialExpiredError("POST /auth returned unexpected status 503"),
        )
        assert result.exit_code != 0
        # The specific status code from the exception must appear in the output.
        assert "503" in result.output


# ---------------------------------------------------------------------------
# bb creds capture
# ---------------------------------------------------------------------------


_MOBILE_ENV = {
    "GAMECHANGER_ACCESS_TOKEN_MOBILE": _make_fake_token(43200),  # ~12 hours
    "GAMECHANGER_REFRESH_TOKEN_MOBILE": _make_fake_token(1209600),  # 14 days
    "GAMECHANGER_DEVICE_ID_MOBILE": "device-mobile-id",
    "GAMECHANGER_CLIENT_ID_MOBILE": "client-mobile-id",
    "GAMECHANGER_BASE_URL": "https://api.gc.com",
}


def _make_api_result(exit_code: int = 0) -> "ApiCheckResult":
    """Build a minimal ApiCheckResult for capture tests."""
    from src.gamechanger.credentials import ApiCheckResult

    if exit_code == 0:
        return ApiCheckResult(exit_code=0, display_name="Jason Smith", message="200 OK, logged in as Jason Smith")
    return ApiCheckResult(exit_code=1, display_name=None, message="Credentials expired -- refresh via proxy capture")


class TestCredsCapture:
    """Tests for ``bb creds capture --profile mobile``."""

    def _invoke_with_creds(self, creds: dict, api_exit: int = 0):
        """Invoke capture with mocked .env credentials and API result."""
        with (
            patch("src.cli.creds.dotenv_values", return_value=creds),
            patch("src.cli.creds.run_api_check", return_value=_make_api_result(api_exit)),
        ):
            return runner.invoke(app, ["creds", "capture", "--profile", "mobile"])

    def _invoke_no_creds(self, sessions_dir_path: str | None = None, has_ios: bool = False):
        """Invoke capture with no mobile creds, optionally faking session dir scanning."""
        from unittest.mock import MagicMock

        def fake_find_most_recent(sessions_dir):
            if sessions_dir_path is None:
                return None
            mock_session = MagicMock()
            mock_session.name = "2026-03-09_062059"
            return mock_session

        with (
            patch("src.cli.creds.dotenv_values", return_value={}),
            patch("src.cli.creds._find_most_recent_session", side_effect=fake_find_most_recent),
            patch("src.cli.creds._has_ios_traffic", return_value=has_ios),
        ):
            return runner.invoke(app, ["creds", "capture", "--profile", "mobile"])

    # AC-1: checks .env for mobile credentials
    def test_all_credentials_present_exits_0(self) -> None:
        """All mobile creds present: exit 0."""
        result = self._invoke_with_creds(_MOBILE_ENV)
        assert result.exit_code == 0

    def test_present_credentials_show_ok_indicators(self) -> None:
        """AC-7: Each present key shows [OK] indicator."""
        result = self._invoke_with_creds(_MOBILE_ENV)
        assert "[OK]" in result.output or "OK" in result.output

    def test_present_credentials_show_key_names(self) -> None:
        """AC-1: Key names (not values) appear in output."""
        result = self._invoke_with_creds(_MOBILE_ENV)
        for key in ("GAMECHANGER_ACCESS_TOKEN_MOBILE", "GAMECHANGER_REFRESH_TOKEN_MOBILE",
                    "GAMECHANGER_DEVICE_ID_MOBILE", "GAMECHANGER_CLIENT_ID_MOBILE"):
            assert key in result.output

    # AC-8: access token always [!!] yellow
    def test_access_token_uses_yellow_indicator(self) -> None:
        """AC-8: Mobile access token health uses [!!] (yellow) indicator."""
        result = self._invoke_with_creds(_MOBILE_ENV)
        assert "[!!]" in result.output or "!!" in result.output

    def test_access_token_shows_hours_remaining(self) -> None:
        """AC-2/AC-8: Output includes human-readable remaining lifetime."""
        result = self._invoke_with_creds(_MOBILE_ENV)
        assert "hour" in result.output or "minute" in result.output

    # AC-3: expired access token
    def test_expired_access_token_shows_yellow_not_green(self) -> None:
        """AC-3/AC-8: Expired access token still uses [!!], not [XX]."""
        expired_env = {**_MOBILE_ENV, "GAMECHANGER_ACCESS_TOKEN_MOBILE": _make_fake_token(-60)}
        result = self._invoke_with_creds(expired_env)
        assert "[!!]" in result.output or "!!" in result.output
        assert "[XX]" not in result.output

    def test_expired_access_shows_refresh_token_days(self) -> None:
        """AC-3: When access token expired, output shows refresh token remaining days."""
        expired_env = {
            **_MOBILE_ENV,
            "GAMECHANGER_ACCESS_TOKEN_MOBILE": _make_fake_token(-60),  # expired
            "GAMECHANGER_REFRESH_TOKEN_MOBILE": _make_fake_token(14 * 86400),  # 14 days
        }
        result = self._invoke_with_creds(expired_env)
        assert "GAMECHANGER_REFRESH_TOKEN_MOBILE" in result.output
        # Should mention days remaining
        assert "day" in result.output

    def test_valid_access_does_not_show_refresh_lifetime(self) -> None:
        """Refresh token lifetime row only appears when access token is expired."""
        result = self._invoke_with_creds(_MOBILE_ENV)
        # Access token is valid (~12h), so no "recapture to get fresh access token" line
        assert "recapture to get fresh access token" not in result.output

    # AC-9: no credential values in output
    def test_no_credential_values_in_output(self) -> None:
        """AC-9: Actual token/ID values never appear in output."""
        result = self._invoke_with_creds(_MOBILE_ENV)
        for value in ("device-mobile-id", "client-mobile-id"):
            assert value not in result.output

    # AC-2: API validation call
    def test_api_validation_called_for_mobile_profile(self) -> None:
        """AC-2: run_api_check is called with 'mobile' profile."""
        with (
            patch("src.cli.creds.dotenv_values", return_value=_MOBILE_ENV),
            patch("src.cli.creds.run_api_check", return_value=_make_api_result()) as mock_api,
        ):
            runner.invoke(app, ["creds", "capture", "--profile", "mobile"])
        mock_api.assert_called_once_with("mobile")

    def test_api_success_message_in_output(self) -> None:
        """AC-2: API success message (200 OK) appears in output."""
        result = self._invoke_with_creds(_MOBILE_ENV)
        assert "200" in result.output or "OK" in result.output or "logged in" in result.output

    # AC-10: suggest bb creds check
    def test_suggests_bb_creds_check_after_success(self) -> None:
        """AC-10: After successful capture, output suggests bb creds check."""
        result = self._invoke_with_creds(_MOBILE_ENV)
        assert "bb creds check" in result.output or "creds check" in result.output

    # AC-4/AC-5: no proxy sessions
    def test_no_sessions_prints_setup_guide(self) -> None:
        """AC-5: No proxy sessions → inline numbered setup guide."""
        result = self._invoke_no_creds(sessions_dir_path=None)
        assert result.exit_code != 0
        # Should include multiple numbered steps
        assert "1." in result.output
        assert "mitmproxy" in result.output.lower() or "proxy" in result.output.lower()

    def test_no_sessions_mentions_mitmproxy_guide(self) -> None:
        """AC-5: Setup guide references mitmproxy-guide.md."""
        result = self._invoke_no_creds(sessions_dir_path=None)
        assert "mitmproxy-guide.md" in result.output

    # AC-6: sessions exist but no iOS traffic
    def test_sessions_no_ios_traffic_suggests_force_quit(self) -> None:
        """AC-6: Sessions with no iOS traffic → suggest force-quit and reopen."""
        result = self._invoke_no_creds(sessions_dir_path="/some/session", has_ios=False)
        assert result.exit_code != 0
        output_lower = result.output.lower()
        assert "force" in output_lower or "quit" in output_lower or "reopen" in output_lower

    def test_sessions_with_ios_traffic_gives_ios_guidance(self) -> None:
        """iOS traffic detected but no creds → guidance to force-quit app."""
        result = self._invoke_no_creds(sessions_dir_path="/some/session", has_ios=True)
        assert result.exit_code != 0
        output_lower = result.output.lower()
        assert "ios" in output_lower or "force" in output_lower

    # Profile validation
    def test_non_mobile_profile_exits_error(self) -> None:
        """Only mobile profile is supported by capture."""
        result = runner.invoke(app, ["creds", "capture", "--profile", "web"])
        assert result.exit_code != 0
        assert "mobile" in result.output.lower()

    # Partial credentials
    def test_partial_creds_still_shows_result(self) -> None:
        """Partial mobile creds (e.g. only access + refresh) still validate and show output."""
        partial_env = {
            "GAMECHANGER_ACCESS_TOKEN_MOBILE": _MOBILE_ENV["GAMECHANGER_ACCESS_TOKEN_MOBILE"],
            "GAMECHANGER_REFRESH_TOKEN_MOBILE": _MOBILE_ENV["GAMECHANGER_REFRESH_TOKEN_MOBILE"],
        }
        result = self._invoke_with_creds(partial_env)
        assert result.exit_code == 0
        # Missing keys shown with dim indicator
        assert "GAMECHANGER_DEVICE_ID_MOBILE" in result.output
        assert "GAMECHANGER_CLIENT_ID_MOBILE" in result.output


class TestCredsCaptureSessionScanning:
    """Unit tests for the proxy session scanning helpers."""

    def test_find_most_recent_session_returns_latest(self, tmp_path: Path) -> None:
        """_find_most_recent_session returns the directory with the latest timestamp name."""
        from src.cli.creds import _find_most_recent_session

        (tmp_path / "2026-03-06_204244").mkdir()
        (tmp_path / "2026-03-09_062059").mkdir()
        (tmp_path / "2026-03-07_171705").mkdir()
        result = _find_most_recent_session(tmp_path)
        assert result is not None
        assert result.name == "2026-03-09_062059"

    def test_find_most_recent_session_empty_dir_returns_none(self, tmp_path: Path) -> None:
        """Empty sessions directory returns None."""
        from src.cli.creds import _find_most_recent_session

        result = _find_most_recent_session(tmp_path)
        assert result is None

    def test_find_most_recent_session_nonexistent_dir_returns_none(self, tmp_path: Path) -> None:
        """Non-existent sessions directory returns None."""
        from src.cli.creds import _find_most_recent_session

        result = _find_most_recent_session(tmp_path / "nonexistent")
        assert result is None

    def test_has_ios_traffic_detects_ios_source(self, tmp_path: Path) -> None:
        """_has_ios_traffic returns True when any entry has source='ios'."""
        import json as _json
        from src.cli.creds import _has_ios_traffic

        log = tmp_path / "endpoint-log.jsonl"
        log.write_text(
            _json.dumps({"method": "GET", "path": "/me/teams", "source": "web"}) + "\n"
            + _json.dumps({"method": "POST", "path": "/auth", "source": "ios"}) + "\n",
            encoding="utf-8",
        )
        assert _has_ios_traffic(tmp_path) is True

    def test_has_ios_traffic_returns_false_for_web_only(self, tmp_path: Path) -> None:
        """_has_ios_traffic returns False when all entries are web source."""
        import json as _json
        from src.cli.creds import _has_ios_traffic

        log = tmp_path / "endpoint-log.jsonl"
        log.write_text(
            _json.dumps({"method": "GET", "path": "/me/teams", "source": "web"}) + "\n",
            encoding="utf-8",
        )
        assert _has_ios_traffic(tmp_path) is False

    def test_has_ios_traffic_returns_false_when_no_log(self, tmp_path: Path) -> None:
        """_has_ios_traffic returns False when endpoint-log.jsonl doesn't exist."""
        from src.cli.creds import _has_ios_traffic

        assert _has_ios_traffic(tmp_path) is False


# ---------------------------------------------------------------------------
# bb creds extract-key
# ---------------------------------------------------------------------------

_FAKE_CLIENT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_FAKE_CLIENT_KEY = "abcdefghijklmnopqrstuvwxyz01234567890123456="


def _make_extracted_key(
    client_id: str = _FAKE_CLIENT_ID,
    client_key: str = _FAKE_CLIENT_KEY,
):
    """Build a minimal ExtractedKey for CLI tests."""
    from src.gamechanger.key_extractor import ExtractedKey

    return ExtractedKey(
        client_id=client_id,
        client_key=client_key,
        bundle_url="https://web.gc.com/static/js/index.abc123.js",
    )


_CURRENT_ENV_MATCHING = {
    "GAMECHANGER_CLIENT_ID_WEB": _FAKE_CLIENT_ID,
    "GAMECHANGER_CLIENT_KEY_WEB": _FAKE_CLIENT_KEY,
}
_CURRENT_ENV_DIFFERENT = {
    "GAMECHANGER_CLIENT_ID_WEB": "old-client-id",
    "GAMECHANGER_CLIENT_KEY_WEB": "old-client-key-value-that-does-not-match==",
}


class TestCredsExtractKey:
    """Tests for ``bb creds extract-key``."""

    def _invoke(
        self,
        args: list[str],
        extracted=None,
        side_effect=None,
        current_env: dict | None = None,
        write_ok: bool = True,
    ):
        extracted = extracted or _make_extracted_key()
        current_env = current_env if current_env is not None else _CURRENT_ENV_MATCHING

        patches = [
            patch(
                "src.cli.creds.extract_client_key",
                return_value=extracted if side_effect is None else None,
                side_effect=side_effect,
            ),
            patch("src.cli.creds.dotenv_values", return_value=current_env),
        ]
        if not write_ok:
            patches.append(
                patch(
                    "src.cli.creds.atomic_merge_env_file",
                    side_effect=OSError("disk full"),
                )
            )

        ctx = [p.__enter__() for p in patches]
        try:
            result = runner.invoke(app, args)
        finally:
            for i, p in enumerate(reversed(patches)):
                p.__exit__(None, None, None)

        return result

    # ---- helper that uses context managers properly ----

    def _run(
        self,
        args: list[str],
        extracted=None,
        side_effect=None,
        current_env: dict | None = None,
    ):
        """Run via context managers (clean approach)."""
        extracted = extracted or _make_extracted_key()
        current_env = current_env if current_env is not None else _CURRENT_ENV_MATCHING

        with (
            patch(
                "src.cli.creds.extract_client_key",
                return_value=extracted if side_effect is None else None,
                side_effect=side_effect,
            ),
            patch("src.cli.creds.dotenv_values", return_value=current_env),
            patch("src.cli.creds.atomic_merge_env_file", return_value=current_env) as mock_write,
        ):
            result = runner.invoke(app, args)
        return result, mock_write

    # AC-4a: dry-run banner
    def test_dry_run_shows_banner(self) -> None:
        """Default (no --apply) shows dry-run banner."""
        result, _ = self._run(["creds", "extract-key"])
        assert "dry run" in result.output.lower() or "Dry run" in result.output

    # AC-2: dry run does not write .env
    def test_dry_run_does_not_write_env(self) -> None:
        """Default mode: atomic_merge_env_file is NOT called."""
        result, mock_write = self._run(
            ["creds", "extract-key"],
            current_env=_CURRENT_ENV_DIFFERENT,
        )
        assert result.exit_code == 0
        mock_write.assert_not_called()

    # AC-4: unchanged key
    def test_key_unchanged_shows_no_update_needed(self) -> None:
        """When key matches .env, output says key is current."""
        result, _ = self._run(
            ["creds", "extract-key"],
            current_env=_CURRENT_ENV_MATCHING,
        )
        assert result.exit_code == 0
        assert "no update needed" in result.output.lower() or "current" in result.output.lower()

    # AC-4: changed key
    def test_key_changed_shows_changed(self) -> None:
        """When key differs from .env, output says key changed."""
        result, _ = self._run(
            ["creds", "extract-key"],
            current_env=_CURRENT_ENV_DIFFERENT,
        )
        assert result.exit_code == 0
        assert "[changed]" in result.output or "changed" in result.output.lower()

    # AC-4: client ID display
    def test_unchanged_client_id_shows_unchanged(self) -> None:
        """Unchanged client_id shows '[unchanged]' in output."""
        same_id_env = {
            "GAMECHANGER_CLIENT_ID_WEB": _FAKE_CLIENT_ID,
            "GAMECHANGER_CLIENT_KEY_WEB": "different-key-value-so-we-keep-going==",
        }
        result, _ = self._run(
            ["creds", "extract-key"],
            current_env=same_id_env,
        )
        assert "unchanged" in result.output.lower()

    def test_changed_client_id_shows_old_and_new(self) -> None:
        """Changed client_id shows old -> new in output."""
        result, _ = self._run(
            ["creds", "extract-key"],
            current_env=_CURRENT_ENV_DIFFERENT,
        )
        assert "->" in result.output

    # AC-3: --apply writes .env
    def test_apply_writes_env(self) -> None:
        """--apply calls atomic_merge_env_file with updated keys."""
        result, mock_write = self._run(
            ["creds", "extract-key", "--apply"],
            current_env=_CURRENT_ENV_DIFFERENT,
        )
        assert result.exit_code == 0
        mock_write.assert_called_once()
        call_args = mock_write.call_args[0]
        new_values = call_args[1]
        assert "GAMECHANGER_CLIENT_KEY_WEB" in new_values
        assert "GAMECHANGER_CLIENT_ID_WEB" in new_values

    # AC-4b: after --apply shows confirmation and next steps
    def test_apply_shows_confirmation(self) -> None:
        """After --apply, output includes confirmation message."""
        result, _ = self._run(
            ["creds", "extract-key", "--apply"],
            current_env=_CURRENT_ENV_DIFFERENT,
        )
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "updated" in output_lower
        assert "gamechanger_client_key_web" in output_lower

    def test_apply_shows_next_steps(self) -> None:
        """After --apply, output includes next-step guidance."""
        result, _ = self._run(
            ["creds", "extract-key", "--apply"],
            current_env=_CURRENT_ENV_DIFFERENT,
        )
        assert result.exit_code == 0
        assert "creds check" in result.output or "bb creds" in result.output
        assert "creds refresh" in result.output or "refresh" in result.output

    # AC-5: HTML fetch failure
    def test_html_fetch_failure_exits_1(self) -> None:
        """Network error from extract_client_key exits with code 1."""
        from src.gamechanger.key_extractor import KeyExtractionError

        result, _ = self._run(
            ["creds", "extract-key"],
            side_effect=KeyExtractionError("Network error fetching https://web.gc.com: refused"),
        )
        assert result.exit_code == 1
        assert "Error" in result.output or "error" in result.output.lower()

    # AC-6: bundle URL not found
    def test_bundle_url_not_found_exits_1(self) -> None:
        """KeyExtractionError for missing bundle URL exits 1."""
        from src.gamechanger.key_extractor import KeyExtractionError

        result, _ = self._run(
            ["creds", "extract-key"],
            side_effect=KeyExtractionError("Could not find JS bundle URL"),
        )
        assert result.exit_code == 1

    # AC-7: EDEN_AUTH_CLIENT_KEY not found
    def test_eden_key_not_found_exits_1(self) -> None:
        """KeyExtractionError for missing EDEN_AUTH_CLIENT_KEY exits 1."""
        from src.gamechanger.key_extractor import KeyExtractionError

        result, _ = self._run(
            ["creds", "extract-key"],
            side_effect=KeyExtractionError("EDEN_AUTH_CLIENT_KEY not found in the JS bundle"),
        )
        assert result.exit_code == 1
        assert "EDEN_AUTH_CLIENT_KEY" in result.output

    # AC-12: key value never printed
    def test_client_key_value_never_printed(self) -> None:
        """The actual client_key value NEVER appears in output (AC-12)."""
        result, _ = self._run(
            ["creds", "extract-key"],
            current_env=_CURRENT_ENV_DIFFERENT,
        )
        assert _FAKE_CLIENT_KEY not in result.output

    def test_client_key_value_never_printed_on_apply(self) -> None:
        """The actual client_key value NEVER appears in output even with --apply."""
        result, _ = self._run(
            ["creds", "extract-key", "--apply"],
            current_env=_CURRENT_ENV_DIFFERENT,
        )
        assert _FAKE_CLIENT_KEY not in result.output

    # OSError path: _write_env_update fails
    def test_apply_oserror_exits_1(self) -> None:
        """When atomic_merge_env_file raises OSError, exit code is 1 with error message."""
        result = self._invoke(
            ["creds", "extract-key", "--apply"],
            current_env=_CURRENT_ENV_DIFFERENT,
            write_ok=False,
        )
        assert result.exit_code == 1
        assert "disk full" in result.output.lower() or "error" in result.output.lower()

    # help text
    def test_extract_key_in_help(self) -> None:
        """``bb creds --help`` lists extract-key sub-command."""
        result = runner.invoke(app, ["creds", "--help"])
        assert result.exit_code == 0
        assert "extract-key" in result.output
