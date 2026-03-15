"""Tests for src/gamechanger/crawlers/opponent.py.

All HTTP calls are mocked -- no real network requests are made.
Tests cover:
- Opponents endpoint called with pagination (AC-1)
- opponents.json written for each owned team (AC-1)
- Roster fetched for opponents with progenitor_team_id (AC-2, AC-3)
- Opponents without progenitor_team_id skipped with INFO log (AC-5)
- Hidden opponents skipped (AC-2, is_hidden filter)
- 403 logged at WARNING level, crawl continues (AC-4)
- Deduplication of opponent IDs across teams (AC-2)
- Owned-team IDs excluded from roster fetching (AC-2)
- Freshness check for opponents.json registry (AC-6)
- Freshness check for roster files (AC-6)
- Summary log produced (AC-7)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from src.gamechanger.client import CredentialExpiredError, ForbiddenError, GameChangerAPIError
from src.gamechanger.config import CrawlConfig, TeamEntry
from src.gamechanger.crawlers import CrawlResult
from src.gamechanger.crawlers.opponent import OpponentCrawler


# ---------------------------------------------------------------------------
# Constants and fixtures
# ---------------------------------------------------------------------------

_OWNED_TEAM_ID = "owned-team-uuid-001"
_SEASON = "2025"

_OPPONENT_WITH_ID = {
    "root_team_id": "root-aaa",
    "owning_team_id": _OWNED_TEAM_ID,
    "name": "SE Elites 14U",
    "is_hidden": False,
    "progenitor_team_id": "progenitor-aaa-001",
}

_OPPONENT_NO_PROGENITOR = {
    "root_team_id": "root-bbb",
    "owning_team_id": _OWNED_TEAM_ID,
    "name": "Opponent TBD",
    "is_hidden": False,
    # No progenitor_team_id key
}

_OPPONENT_HIDDEN = {
    "root_team_id": "root-ccc",
    "owning_team_id": _OWNED_TEAM_ID,
    "name": "Old Duplicate (bad)",
    "is_hidden": True,
    "progenitor_team_id": "progenitor-ccc-001",
}

_SAMPLE_ROSTER = [
    {"id": "player-aaa", "first_name": "J", "last_name": "Smith", "number": "1", "avatar_url": ""},
]


def _make_config(
    owned_team_ids: list[str] | None = None,
) -> CrawlConfig:
    """Build a CrawlConfig with given team IDs (or a single default team)."""
    ids = owned_team_ids if owned_team_ids is not None else [_OWNED_TEAM_ID]
    teams = [TeamEntry(id=tid, name=f"Team {tid}", classification="jv") for tid in ids]
    return CrawlConfig(season=_SEASON, member_teams=teams)


def _make_client(
    paginated_return: list | None = None,
    get_return: object = None,
    paginated_side_effect: Exception | None = None,
    get_side_effect: Exception | None = None,
) -> MagicMock:
    """Return a mock GameChangerClient with configurable return values."""
    client = MagicMock()
    if paginated_side_effect is not None:
        client.get_paginated.side_effect = paginated_side_effect
    else:
        client.get_paginated.return_value = (
            paginated_return if paginated_return is not None else []
        )
    if get_side_effect is not None:
        client.get.side_effect = get_side_effect
    else:
        client.get.return_value = get_return if get_return is not None else _SAMPLE_ROSTER
    return client


# ---------------------------------------------------------------------------
# AC-1: Opponents endpoint called and opponents.json written
# ---------------------------------------------------------------------------


def test_crawl_all_calls_opponents_endpoint(tmp_path: Path) -> None:
    """crawl_all calls GET /teams/{team_id}/opponents for each owned team."""
    opponents = [_OPPONENT_WITH_ID]
    client = _make_client(paginated_return=opponents, get_return=_SAMPLE_ROSTER)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    crawler.crawl_all()

    client.get_paginated.assert_called_once_with(
        f"/teams/{_OWNED_TEAM_ID}/opponents",
        accept="application/vnd.gc.com.opponent_team:list+json; version=0.0.0",
    )


def test_crawl_all_writes_opponents_json(tmp_path: Path) -> None:
    """crawl_all writes the full opponents list to opponents.json."""
    opponents = [_OPPONENT_WITH_ID, _OPPONENT_NO_PROGENITOR]
    client = _make_client(paginated_return=opponents, get_return=_SAMPLE_ROSTER)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    crawler.crawl_all()

    dest = tmp_path / _SEASON / "teams" / _OWNED_TEAM_ID / "opponents.json"
    assert dest.exists()
    written = json.loads(dest.read_text())
    assert written == opponents


def test_crawl_all_calls_opponents_for_each_owned_team(tmp_path: Path) -> None:
    """crawl_all iterates over every owned team for the registry fetch."""
    team_a = "owned-aaa"
    team_b = "owned-bbb"
    client = _make_client(paginated_return=[], get_return=_SAMPLE_ROSTER)
    config = _make_config([team_a, team_b])
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    crawler.crawl_all()

    assert client.get_paginated.call_count == 2
    called_paths = [c.args[0] for c in client.get_paginated.call_args_list]
    assert f"/teams/{team_a}/opponents" in called_paths
    assert f"/teams/{team_b}/opponents" in called_paths


# ---------------------------------------------------------------------------
# AC-2 & AC-3: Roster fetched for opponents with progenitor_team_id
# ---------------------------------------------------------------------------


def test_crawl_all_fetches_roster_for_opponent_with_progenitor(tmp_path: Path) -> None:
    """Roster is fetched for each opponent that has a progenitor_team_id."""
    opponents = [_OPPONENT_WITH_ID]
    client = _make_client(paginated_return=opponents, get_return=_SAMPLE_ROSTER)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    crawler.crawl_all()

    progenitor = _OPPONENT_WITH_ID["progenitor_team_id"]
    client.get.assert_called_once_with(
        f"/teams/{progenitor}/players",
        accept="application/vnd.gc.com.player:list+json; version=0.1.0",
    )


def test_crawl_all_writes_roster_to_correct_path(tmp_path: Path) -> None:
    """Opponent roster is written to data/raw/{season}/teams/{opponent_id}/roster.json."""
    opponents = [_OPPONENT_WITH_ID]
    client = _make_client(paginated_return=opponents, get_return=_SAMPLE_ROSTER)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    crawler.crawl_all()

    progenitor = _OPPONENT_WITH_ID["progenitor_team_id"]
    dest = tmp_path / _SEASON / "teams" / progenitor / "roster.json"
    assert dest.exists()
    written = json.loads(dest.read_text())
    assert written == _SAMPLE_ROSTER


# ---------------------------------------------------------------------------
# AC-4: 403 logged as WARNING, crawl continues
# ---------------------------------------------------------------------------


def test_crawl_all_403_logged_as_warning_not_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A 403 (ForbiddenError) is logged at WARNING, not ERROR."""
    opponents = [_OPPONENT_WITH_ID]
    client = _make_client(
        paginated_return=opponents,
        get_side_effect=ForbiddenError("HTTP 403"),
    )
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.opponent"):
        result = crawler.crawl_all()

    assert result.errors == 1
    # Must appear as WARNING, not ERROR.
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("Access denied" in r.message for r in warning_records)


def test_crawl_all_continues_after_403(tmp_path: Path) -> None:
    """A 403 on one opponent does not abort the rest of the crawl."""
    opponent_blocked = {
        "root_team_id": "root-blocked",
        "owning_team_id": _OWNED_TEAM_ID,
        "name": "Blocked Team",
        "is_hidden": False,
        "progenitor_team_id": "progenitor-blocked",
    }
    opponent_ok = {
        "root_team_id": "root-ok",
        "owning_team_id": _OWNED_TEAM_ID,
        "name": "OK Team",
        "is_hidden": False,
        "progenitor_team_id": "progenitor-ok",
    }

    call_count = 0

    def get_side_effect(*args: object, **kwargs: object) -> list:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ForbiddenError("HTTP 403")
        return _SAMPLE_ROSTER

    client = _make_client(paginated_return=[opponent_blocked, opponent_ok])
    client.get.side_effect = get_side_effect
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.errors == 1
    # 1 opponents.json registry + 1 roster for opponent_ok = 2 files written
    assert result.files_written == 2


# ---------------------------------------------------------------------------
# AC-5: Opponents without progenitor_team_id skipped with INFO log
# ---------------------------------------------------------------------------


def test_crawl_all_skips_opponent_without_progenitor(tmp_path: Path) -> None:
    """Opponents without progenitor_team_id are skipped; no roster fetch."""
    opponents = [_OPPONENT_NO_PROGENITOR]
    client = _make_client(paginated_return=opponents)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    client.get.assert_not_called()
    assert result.files_written == 1  # Only the opponents.json registry
    assert result.errors == 0


def test_crawl_all_logs_info_for_opponent_without_progenitor(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """An INFO log is emitted when an opponent has no progenitor_team_id."""
    opponents = [_OPPONENT_NO_PROGENITOR]
    client = _make_client(paginated_return=opponents)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    with caplog.at_level(logging.INFO, logger="src.gamechanger.crawlers.opponent"):
        crawler.crawl_all()

    info_records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert any("progenitor_team_id" in r.message for r in info_records)
    assert any(_OPPONENT_NO_PROGENITOR["name"] in r.message for r in info_records)


# ---------------------------------------------------------------------------
# Hidden opponents skipped
# ---------------------------------------------------------------------------


def test_crawl_all_skips_hidden_opponents(tmp_path: Path) -> None:
    """Hidden opponents (is_hidden=True) are not crawled for rosters."""
    opponents = [_OPPONENT_HIDDEN]
    client = _make_client(paginated_return=opponents)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    client.get.assert_not_called()
    assert result.errors == 0


# ---------------------------------------------------------------------------
# AC-2: Deduplication of opponent IDs across teams
# ---------------------------------------------------------------------------


def test_crawl_all_deduplicates_opponent_ids_across_teams(tmp_path: Path) -> None:
    """The same progenitor_team_id from multiple owned teams is fetched once."""
    shared_progenitor = "progenitor-shared-001"
    opponent_from_team_a = {
        "root_team_id": "root-a",
        "owning_team_id": "owned-aaa",
        "name": "Shared Opponent",
        "is_hidden": False,
        "progenitor_team_id": shared_progenitor,
    }
    opponent_from_team_b = {
        "root_team_id": "root-b",
        "owning_team_id": "owned-bbb",
        "name": "Shared Opponent",
        "is_hidden": False,
        "progenitor_team_id": shared_progenitor,
    }

    team_a = "owned-aaa"
    team_b = "owned-bbb"

    call_count = 0

    def paginated_side_effect(path: str, **kwargs: object) -> list:
        nonlocal call_count
        call_count += 1
        if team_a in path:
            return [opponent_from_team_a]
        return [opponent_from_team_b]

    client = MagicMock()
    client.get_paginated.side_effect = paginated_side_effect
    client.get.return_value = _SAMPLE_ROSTER
    config = _make_config([team_a, team_b])
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    crawler.crawl_all()

    # Roster should only be fetched once despite appearing in two registries.
    assert client.get.call_count == 1
    client.get.assert_called_once_with(
        f"/teams/{shared_progenitor}/players",
        accept="application/vnd.gc.com.player:list+json; version=0.1.0",
    )


# ---------------------------------------------------------------------------
# AC-2: Owned-team IDs excluded from roster fetching
# ---------------------------------------------------------------------------


def test_crawl_all_excludes_owned_team_ids_from_roster_fetch(tmp_path: Path) -> None:
    """An opponent whose progenitor_team_id matches an owned team is skipped."""
    owned_id = _OWNED_TEAM_ID
    opponent_is_owned_team = {
        "root_team_id": "root-self",
        "owning_team_id": owned_id,
        "name": "Lincoln JV",
        "is_hidden": False,
        "progenitor_team_id": owned_id,  # same as the owned team
    }
    client = _make_client(paginated_return=[opponent_is_owned_team])
    config = _make_config([owned_id])
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    client.get.assert_not_called()
    assert result.errors == 0


# ---------------------------------------------------------------------------
# AC-6: Freshness check for opponents.json registry
# ---------------------------------------------------------------------------


def test_crawl_registry_skips_fresh_opponents_json(tmp_path: Path) -> None:
    """A fresh opponents.json is not re-fetched from the API."""
    stored_opponents = [_OPPONENT_WITH_ID]
    dest = tmp_path / _SEASON / "teams" / _OWNED_TEAM_ID / "opponents.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(stored_opponents), encoding="utf-8")

    client = _make_client(get_return=_SAMPLE_ROSTER)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    crawler.crawl_all()

    # Registry endpoint not called -- loaded from cache.
    client.get_paginated.assert_not_called()
    # But roster IS fetched for the cached opponent.
    client.get.assert_called_once()


def test_crawl_registry_counts_fresh_file_as_skipped(tmp_path: Path) -> None:
    """files_skipped is incremented when the opponents.json is fresh."""
    stored_opponents: list = []
    dest = tmp_path / _SEASON / "teams" / _OWNED_TEAM_ID / "opponents.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(stored_opponents), encoding="utf-8")

    client = _make_client()
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.files_skipped >= 1


def test_crawl_registry_refetches_stale_opponents_json(tmp_path: Path) -> None:
    """A stale opponents.json (older than freshness_hours) is re-fetched."""
    dest = tmp_path / _SEASON / "teams" / _OWNED_TEAM_ID / "opponents.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps([]), encoding="utf-8")

    # Set mtime to 25 hours ago.
    import os
    stale_mtime = time.time() - (25 * 3600)
    os.utime(dest, (stale_mtime, stale_mtime))

    client = _make_client(paginated_return=[_OPPONENT_WITH_ID], get_return=_SAMPLE_ROSTER)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    crawler.crawl_all()

    client.get_paginated.assert_called_once()


# ---------------------------------------------------------------------------
# AC-6: Freshness check for roster files (delegated to RosterCrawler)
# ---------------------------------------------------------------------------


def test_crawl_all_skips_fresh_opponent_roster(tmp_path: Path) -> None:
    """A fresh opponent roster file is not re-fetched."""
    progenitor = _OPPONENT_WITH_ID["progenitor_team_id"]
    roster_dest = tmp_path / _SEASON / "teams" / progenitor / "roster.json"
    roster_dest.parent.mkdir(parents=True, exist_ok=True)
    roster_dest.write_text(json.dumps(_SAMPLE_ROSTER), encoding="utf-8")

    opponents = [_OPPONENT_WITH_ID]
    client = _make_client(paginated_return=opponents)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    # Roster endpoint not called.
    client.get.assert_not_called()
    # Counted as skipped.
    assert result.files_skipped >= 1


# ---------------------------------------------------------------------------
# AC-7: Summary log produced
# ---------------------------------------------------------------------------


def test_crawl_all_logs_summary(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """crawl_all produces a summary log with all expected fields."""
    opponents = [_OPPONENT_WITH_ID, _OPPONENT_NO_PROGENITOR, _OPPONENT_HIDDEN]
    client = _make_client(paginated_return=opponents, get_return=_SAMPLE_ROSTER)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    with caplog.at_level(logging.INFO, logger="src.gamechanger.crawlers.opponent"):
        crawler.crawl_all()

    summary_records = [r for r in caplog.records if "Opponent crawl summary" in r.message]
    assert len(summary_records) == 1
    summary = summary_records[0].message

    assert "total_unique_opponents=" in summary
    assert "with_progenitor_id=" in summary
    assert "without_progenitor_id=" in summary
    assert "hidden=" in summary
    assert "successfully_crawled=" in summary
    assert "access_denied=" in summary
    assert "unexpected_errors=" in summary


# ---------------------------------------------------------------------------
# CrawlResult counts across phases
# ---------------------------------------------------------------------------


def test_crawl_all_returns_crawl_result(tmp_path: Path) -> None:
    """crawl_all returns a CrawlResult instance."""
    client = _make_client(paginated_return=[], get_return=_SAMPLE_ROSTER)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert isinstance(result, CrawlResult)


def test_crawl_all_files_written_counts_both_registry_and_roster(tmp_path: Path) -> None:
    """files_written includes both the opponents.json registry and each roster."""
    opponents = [_OPPONENT_WITH_ID]
    client = _make_client(paginated_return=opponents, get_return=_SAMPLE_ROSTER)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    # 1 opponents.json + 1 roster.json = 2
    assert result.files_written == 2
    assert result.files_skipped == 0
    assert result.errors == 0


def test_crawl_all_registry_api_error_counted_in_result(tmp_path: Path) -> None:
    """An API error fetching the opponent registry increments errors."""
    client = _make_client(paginated_side_effect=GameChangerAPIError("Server error"))
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.errors == 1
    assert result.files_written == 0


# ---------------------------------------------------------------------------
# E-002-11: 401 aborts the crawl; 403 (ForbiddenError) continues
# ---------------------------------------------------------------------------


def test_crawl_all_401_aborts_crawl(tmp_path: Path) -> None:
    """A 401 (CredentialExpiredError, non-ForbiddenError) during roster fetch re-raises and aborts."""
    opponent_a = {
        "root_team_id": "root-a",
        "owning_team_id": _OWNED_TEAM_ID,
        "name": "Team A",
        "is_hidden": False,
        "progenitor_team_id": "progenitor-aaa",
    }
    opponent_b = {
        "root_team_id": "root-b",
        "owning_team_id": _OWNED_TEAM_ID,
        "name": "Team B",
        "is_hidden": False,
        "progenitor_team_id": "progenitor-bbb",
    }

    call_count = 0

    def get_side_effect(*args: object, **kwargs: object) -> list:
        nonlocal call_count
        call_count += 1
        # Raise a plain CredentialExpiredError (401) on first call
        raise CredentialExpiredError("HTTP 401")

    client = _make_client(paginated_return=[opponent_a, opponent_b])
    client.get.side_effect = get_side_effect
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    with pytest.raises(CredentialExpiredError):
        crawler.crawl_all()

    # Only the first opponent's roster was attempted before abort
    assert call_count == 1


def test_crawl_all_401_logs_error_before_abort(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A 401 during roster fetch logs at ERROR level before re-raising."""
    opponent = {
        "root_team_id": "root-a",
        "owning_team_id": _OWNED_TEAM_ID,
        "name": "Team A",
        "is_hidden": False,
        "progenitor_team_id": "progenitor-aaa",
    }
    client = _make_client(
        paginated_return=[opponent],
        get_side_effect=CredentialExpiredError("HTTP 401"),
    )
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    with caplog.at_level(logging.ERROR, logger="src.gamechanger.crawlers.opponent"):
        with pytest.raises(CredentialExpiredError):
            crawler.crawl_all()

    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert any("Token expired" in r.message for r in error_records)


def test_crawl_all_403_continues_to_next_opponent(tmp_path: Path) -> None:
    """A ForbiddenError (403) on one opponent does not abort; next opponent is fetched."""
    opponent_blocked = {
        "root_team_id": "root-blocked",
        "owning_team_id": _OWNED_TEAM_ID,
        "name": "Blocked Team",
        "is_hidden": False,
        "progenitor_team_id": "progenitor-blocked",
    }
    opponent_ok = {
        "root_team_id": "root-ok",
        "owning_team_id": _OWNED_TEAM_ID,
        "name": "OK Team",
        "is_hidden": False,
        "progenitor_team_id": "progenitor-ok",
    }

    call_count = 0

    def get_side_effect(*args: object, **kwargs: object) -> list:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ForbiddenError("HTTP 403")
        return _SAMPLE_ROSTER

    client = _make_client(paginated_return=[opponent_blocked, opponent_ok])
    client.get.side_effect = get_side_effect
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    # Both opponents were attempted
    assert call_count == 2
    assert result.errors == 1
    # 1 opponents.json + 1 roster for opponent_ok
    assert result.files_written == 2


def test_crawl_all_403_logged_as_warning_forbidden_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """ForbiddenError (403) is logged at WARNING level with 'Access denied' message."""
    opponents = [_OPPONENT_WITH_ID]
    client = _make_client(
        paginated_return=opponents,
        get_side_effect=ForbiddenError("HTTP 403"),
    )
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.opponent"):
        result = crawler.crawl_all()

    assert result.errors == 1
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("Access denied" in r.message for r in warning_records)
    # Must not have been logged as ERROR
    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert not any("Access denied" in r.message for r in error_records)


def test_crawl_all_registry_error_does_not_abort_other_teams(tmp_path: Path) -> None:
    """A registry error on one team does not prevent fetching for other teams."""
    team_bad = "owned-bad"
    team_ok = "owned-ok"

    call_count = 0

    def paginated_side_effect(path: str, **kwargs: object) -> list:
        nonlocal call_count
        call_count += 1
        if team_bad in path:
            raise GameChangerAPIError("Server error")
        return [_OPPONENT_WITH_ID]

    client = MagicMock()
    client.get_paginated.side_effect = paginated_side_effect
    client.get.return_value = _SAMPLE_ROSTER
    config = _make_config([team_bad, team_ok])
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.errors == 1
    assert result.files_written >= 1  # team_ok's registry + roster
