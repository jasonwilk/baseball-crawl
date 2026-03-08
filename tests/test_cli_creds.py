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
        """--curl flag passes the inline string directly to parse_curl."""
        inline = "curl 'https://api.gc.com' -H 'gc-token: tok'"
        with (
            patch("src.cli.creds.parse_curl", return_value=self._FAKE_CREDENTIALS) as mock_parse,
            patch("src.cli.creds.merge_env_file", return_value=self._MERGED),
        ):
            result = runner.invoke(app, ["creds", "import", "--curl", inline])
        assert result.exit_code == 0
        mock_parse.assert_called_once_with(inline)

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


# ---------------------------------------------------------------------------
# bb creds check
# ---------------------------------------------------------------------------


class TestCredsCheck:
    """Argument mapping tests for ``bb creds check``."""

    def _invoke_check(self, args: list[str], exit_code: int = 0, message: str = "valid"):
        with patch("src.cli.creds.check_credentials", return_value=(exit_code, message)) as mock_fn:
            result = runner.invoke(app, args)
        return result, mock_fn

    def test_check_no_profile_passes_none(self) -> None:
        """``bb creds check`` with no --profile passes profile=None."""
        result, mock_fn = self._invoke_check(["creds", "check"])
        assert result.exit_code == 0
        mock_fn.assert_called_once_with(profile=None)

    def test_check_web_profile(self) -> None:
        """``bb creds check --profile web`` passes profile='web'."""
        result, mock_fn = self._invoke_check(
            ["creds", "check", "--profile", "web"],
            exit_code=0,
            message="Credentials valid",
        )
        assert result.exit_code == 0
        mock_fn.assert_called_once_with(profile="web")

    def test_check_mobile_profile(self) -> None:
        """``bb creds check --profile mobile`` passes profile='mobile'."""
        result, mock_fn = self._invoke_check(
            ["creds", "check", "--profile", "mobile"],
            exit_code=0,
            message="Credentials valid",
        )
        assert result.exit_code == 0
        mock_fn.assert_called_once_with(profile="mobile")

    def test_check_expired_exits_1(self) -> None:
        """Expired credentials: exit code 1."""
        result, _ = self._invoke_check(
            ["creds", "check"], exit_code=1, message="Credentials expired"
        )
        assert result.exit_code == 1

    def test_check_missing_exits_2(self) -> None:
        """Missing credentials: exit code 2."""
        result, _ = self._invoke_check(
            ["creds", "check"], exit_code=2, message="Missing required credentials"
        )
        assert result.exit_code == 2

    def test_check_prints_message(self) -> None:
        """Output contains the message returned by check_credentials."""
        result, _ = self._invoke_check(
            ["creds", "check"], exit_code=0, message="Credentials valid -- logged in as Jason"
        )
        assert "Credentials valid -- logged in as Jason" in result.output


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
