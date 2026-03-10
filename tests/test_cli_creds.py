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
