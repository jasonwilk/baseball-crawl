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
# bb creds refresh
# ---------------------------------------------------------------------------


class TestCredsRefresh:
    """Argument mapping tests for ``bb creds refresh``."""

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
        result, mock_parse, _ = self._invoke(["creds", "refresh"])
        assert result.exit_code == 0
        mock_parse.assert_called_once()

    def test_curl_flag_passes_inline_string(self) -> None:
        """--curl flag passes the inline string directly to parse_curl."""
        inline = "curl 'https://api.gc.com' -H 'gc-token: tok'"
        with (
            patch("src.cli.creds.parse_curl", return_value=self._FAKE_CREDENTIALS) as mock_parse,
            patch("src.cli.creds.merge_env_file", return_value=self._MERGED),
        ):
            result = runner.invoke(app, ["creds", "refresh", "--curl", inline])
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
            result = runner.invoke(app, ["creds", "refresh", "--file", str(curl_file)])
        assert result.exit_code == 0
        mock_parse.assert_called_once()
        called_arg = mock_parse.call_args[0][0]
        assert "curl" in called_arg

    def test_curl_and_file_mutually_exclusive(self) -> None:
        """--curl and --file together produce an error exit."""
        result, _, _ = self._invoke(["creds", "refresh", "--curl", "curl ...", "--file", "/some/path"])
        assert result.exit_code != 0

    def test_output_contains_key_names_not_values(self) -> None:
        """Output lists key names (e.g., GAMECHANGER_REFRESH_TOKEN_WEB) but not their values."""
        result, _, _ = self._invoke(["creds", "refresh"])
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
        result, _, _ = self._invoke(["creds", "refresh"], curl_file_exists=False)
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
            result = runner.invoke(app, ["creds", "refresh"])
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
    def test_help_lists_refresh_and_check(self) -> None:
        """``bb creds --help`` lists both refresh and check sub-commands."""
        result = runner.invoke(app, ["creds", "--help"])
        assert result.exit_code == 0
        assert "refresh" in result.output
        assert "check" in result.output
