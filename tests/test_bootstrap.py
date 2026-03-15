# synthetic-test-data
"""Unit tests for scripts/bootstrap.py.

All external dependencies are mocked -- no real API calls, file I/O, or DB writes.
Tests import ``run()`` directly for assertion convenience.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.bootstrap import run
from src.gamechanger.config import CrawlConfig, TeamEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REAL_TEAM = TeamEntry(id="abc123", name="Lincoln JV", classification="jv")
_PLACEHOLDER_TEAM = TeamEntry(id="REPLACE_WITH_TEAM_ID", name="Placeholder", classification="jv")
_VALID_CONFIG = CrawlConfig(season="2025", member_teams=[_REAL_TEAM])
_PLACEHOLDER_CONFIG = CrawlConfig(season="2025", member_teams=[_PLACEHOLDER_TEAM])
_EMPTY_CONFIG = CrawlConfig(season="2025", member_teams=[])


def _patch_all(
    cred_result: tuple[int, str] = (0, "Credentials valid -- logged in as Jason Smith"),
    config: CrawlConfig | None = _VALID_CONFIG,
    config_missing: bool = False,
    crawl_code: int = 0,
    load_code: int = 0,
):
    """Return a context manager stack that patches all external dependencies."""
    patches = [
        patch("src.pipeline.bootstrap.check_credentials", return_value=cred_result),
        patch("src.pipeline.bootstrap.crawl_module.run", return_value=crawl_code),
        patch("src.pipeline.bootstrap.load_module.run", return_value=load_code),
    ]
    if config_missing:
        patches.append(
            patch(
                "scripts.bootstrap.load_config",
                side_effect=FileNotFoundError("not found"),
            )
        )
    else:
        patches.append(patch("src.pipeline.bootstrap.load_config", return_value=config))
    return patches


# ---------------------------------------------------------------------------
# Successful full run
# ---------------------------------------------------------------------------


def test_successful_full_run_returns_0() -> None:
    with (
        patch("src.pipeline.bootstrap.check_credentials", return_value=(0, "Credentials valid -- logged in as Jason Smith")),
        patch("src.pipeline.bootstrap.load_config", return_value=_VALID_CONFIG),
        patch("src.pipeline.bootstrap.crawl_module.run", return_value=0) as mock_crawl,
        patch("src.pipeline.bootstrap.load_module.run", return_value=0) as mock_load,
    ):
        result = run()
    assert result == 0
    mock_crawl.assert_called_once()
    mock_load.assert_called_once()


def test_successful_full_run_passes_profile_to_crawl() -> None:
    with (
        patch("src.pipeline.bootstrap.check_credentials", return_value=(0, "Credentials valid -- logged in as Jason Smith")),
        patch("src.pipeline.bootstrap.load_config", return_value=_VALID_CONFIG),
        patch("src.pipeline.bootstrap.crawl_module.run", return_value=0) as mock_crawl,
        patch("src.pipeline.bootstrap.load_module.run", return_value=0),
    ):
        run(profile="mobile")
    call_kwargs = mock_crawl.call_args
    assert call_kwargs.kwargs.get("profile") == "mobile" or call_kwargs.args[1] == "mobile" or "mobile" in str(call_kwargs)


def test_bootstrap_passes_profile_to_check_credentials() -> None:
    """AC-5: bootstrap passes --profile to check_credentials so the right profile is validated."""
    with (
        patch("src.pipeline.bootstrap.check_credentials", return_value=(0, "Credentials valid -- logged in as Jason Smith")) as mock_creds,
        patch("src.pipeline.bootstrap.load_config", return_value=_VALID_CONFIG),
        patch("src.pipeline.bootstrap.crawl_module.run", return_value=0),
        patch("src.pipeline.bootstrap.load_module.run", return_value=0),
    ):
        run(profile="mobile")
    mock_creds.assert_called_once_with(profile="mobile")


def test_bootstrap_default_profile_passes_web_to_check_credentials() -> None:
    """Default profile is web -- check_credentials receives profile='web'."""
    with (
        patch("src.pipeline.bootstrap.check_credentials", return_value=(0, "Credentials valid -- logged in as Jason Smith")) as mock_creds,
        patch("src.pipeline.bootstrap.load_config", return_value=_VALID_CONFIG),
        patch("src.pipeline.bootstrap.crawl_module.run", return_value=0),
        patch("src.pipeline.bootstrap.load_module.run", return_value=0),
    ):
        run()
    mock_creds.assert_called_once_with(profile="web")


def test_successful_full_run_passes_dry_run_to_crawl_and_load() -> None:
    with (
        patch("src.pipeline.bootstrap.check_credentials", return_value=(0, "Credentials valid -- logged in as Jason Smith")),
        patch("src.pipeline.bootstrap.load_config", return_value=_VALID_CONFIG),
        patch("src.pipeline.bootstrap.crawl_module.run", return_value=0) as mock_crawl,
        patch("src.pipeline.bootstrap.load_module.run", return_value=0) as mock_load,
    ):
        run(dry_run=True)
    assert mock_crawl.call_args.kwargs.get("dry_run") is True
    assert mock_load.call_args.kwargs.get("dry_run") is True


# ---------------------------------------------------------------------------
# Credential failure -- early exit
# ---------------------------------------------------------------------------


def test_credential_failure_exits_without_crawl() -> None:
    with (
        patch("src.pipeline.bootstrap.check_credentials", return_value=(1, "Credentials expired -- refresh via proxy capture")),
        patch("src.pipeline.bootstrap.load_config", return_value=_VALID_CONFIG),
        patch("src.pipeline.bootstrap.crawl_module.run", return_value=0) as mock_crawl,
        patch("src.pipeline.bootstrap.load_module.run", return_value=0) as mock_load,
    ):
        result = run()
    assert result == 1
    mock_crawl.assert_not_called()
    mock_load.assert_not_called()


def test_credential_missing_exits_with_code_1() -> None:
    with (
        patch("src.pipeline.bootstrap.check_credentials", return_value=(2, "Missing required credential(s): GAMECHANGER_AUTH_TOKEN")),
        patch("src.pipeline.bootstrap.load_config", return_value=_VALID_CONFIG),
        patch("src.pipeline.bootstrap.crawl_module.run", return_value=0) as mock_crawl,
        patch("src.pipeline.bootstrap.load_module.run", return_value=0) as mock_load,
    ):
        result = run()
    assert result == 1
    mock_crawl.assert_not_called()
    mock_load.assert_not_called()


# ---------------------------------------------------------------------------
# Team config failure -- placeholder IDs
# ---------------------------------------------------------------------------


def test_placeholder_team_ids_exits_without_crawl() -> None:
    with (
        patch("src.pipeline.bootstrap.check_credentials", return_value=(0, "Credentials valid -- logged in as Jason Smith")),
        patch("src.pipeline.bootstrap.load_config", return_value=_PLACEHOLDER_CONFIG),
        patch("src.pipeline.bootstrap.crawl_module.run", return_value=0) as mock_crawl,
        patch("src.pipeline.bootstrap.load_module.run", return_value=0) as mock_load,
    ):
        result = run()
    assert result == 1
    mock_crawl.assert_not_called()
    mock_load.assert_not_called()


def test_empty_team_list_exits_without_crawl() -> None:
    with (
        patch("src.pipeline.bootstrap.check_credentials", return_value=(0, "Credentials valid -- logged in as Jason Smith")),
        patch("src.pipeline.bootstrap.load_config", return_value=_EMPTY_CONFIG),
        patch("src.pipeline.bootstrap.crawl_module.run", return_value=0) as mock_crawl,
        patch("src.pipeline.bootstrap.load_module.run", return_value=0) as mock_load,
    ):
        result = run()
    assert result == 1
    mock_crawl.assert_not_called()
    mock_load.assert_not_called()


# ---------------------------------------------------------------------------
# Team config failure -- missing YAML file
# ---------------------------------------------------------------------------


def test_missing_teams_yaml_exits_without_crawl() -> None:
    with (
        patch("src.pipeline.bootstrap.check_credentials", return_value=(0, "Credentials valid -- logged in as Jason Smith")),
        patch("src.pipeline.bootstrap.load_config", side_effect=FileNotFoundError("not found")),
        patch("src.pipeline.bootstrap.crawl_module.run", return_value=0) as mock_crawl,
        patch("src.pipeline.bootstrap.load_module.run", return_value=0) as mock_load,
    ):
        result = run()
    assert result == 1
    mock_crawl.assert_not_called()
    mock_load.assert_not_called()


# ---------------------------------------------------------------------------
# Check-only mode
# ---------------------------------------------------------------------------


def test_check_only_skips_crawl_and_load() -> None:
    with (
        patch("src.pipeline.bootstrap.check_credentials", return_value=(0, "Credentials valid -- logged in as Jason Smith")),
        patch("src.pipeline.bootstrap.load_config", return_value=_VALID_CONFIG),
        patch("src.pipeline.bootstrap.crawl_module.run", return_value=0) as mock_crawl,
        patch("src.pipeline.bootstrap.load_module.run", return_value=0) as mock_load,
    ):
        result = run(check_only=True)
    assert result == 0
    mock_crawl.assert_not_called()
    mock_load.assert_not_called()


def test_check_only_with_bad_credentials_returns_1() -> None:
    with (
        patch("src.pipeline.bootstrap.check_credentials", return_value=(1, "Credentials expired")),
        patch("src.pipeline.bootstrap.load_config", return_value=_VALID_CONFIG),
        patch("src.pipeline.bootstrap.crawl_module.run", return_value=0) as mock_crawl,
        patch("src.pipeline.bootstrap.load_module.run", return_value=0) as mock_load,
    ):
        result = run(check_only=True)
    assert result == 1
    mock_crawl.assert_not_called()
    mock_load.assert_not_called()


# ---------------------------------------------------------------------------
# Crawl failure -- load still runs
# ---------------------------------------------------------------------------


def test_crawl_failure_does_not_skip_load() -> None:
    with (
        patch("src.pipeline.bootstrap.check_credentials", return_value=(0, "Credentials valid -- logged in as Jason Smith")),
        patch("src.pipeline.bootstrap.load_config", return_value=_VALID_CONFIG),
        patch("src.pipeline.bootstrap.crawl_module.run", return_value=1),
        patch("src.pipeline.bootstrap.load_module.run", return_value=0) as mock_load,
    ):
        result = run()
    mock_load.assert_called_once()
    # Non-zero crawl means non-zero overall exit
    assert result == 1


def test_crawl_failure_with_load_success_returns_1() -> None:
    with (
        patch("src.pipeline.bootstrap.check_credentials", return_value=(0, "Credentials valid -- logged in as Jason Smith")),
        patch("src.pipeline.bootstrap.load_config", return_value=_VALID_CONFIG),
        patch("src.pipeline.bootstrap.crawl_module.run", return_value=1),
        patch("src.pipeline.bootstrap.load_module.run", return_value=0),
    ):
        result = run()
    assert result == 1


# ---------------------------------------------------------------------------
# Dry-run passthrough
# ---------------------------------------------------------------------------


def test_dry_run_passes_to_crawl() -> None:
    with (
        patch("src.pipeline.bootstrap.check_credentials", return_value=(0, "Credentials valid -- logged in as Jason Smith")),
        patch("src.pipeline.bootstrap.load_config", return_value=_VALID_CONFIG),
        patch("src.pipeline.bootstrap.crawl_module.run", return_value=0) as mock_crawl,
        patch("src.pipeline.bootstrap.load_module.run", return_value=0),
    ):
        run(dry_run=True)
    assert mock_crawl.call_args.kwargs.get("dry_run") is True


def test_dry_run_passes_to_load() -> None:
    with (
        patch("src.pipeline.bootstrap.check_credentials", return_value=(0, "Credentials valid -- logged in as Jason Smith")),
        patch("src.pipeline.bootstrap.load_config", return_value=_VALID_CONFIG),
        patch("src.pipeline.bootstrap.crawl_module.run", return_value=0),
        patch("src.pipeline.bootstrap.load_module.run", return_value=0) as mock_load,
    ):
        run(dry_run=True)
    assert mock_load.call_args.kwargs.get("dry_run") is True
