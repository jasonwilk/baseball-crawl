# synthetic-test-data
"""Tests for src.gamechanger.crawlers.opponents.

Probe-confirmation + regression tests pinning the F4 registry probe findings
(2026-06-17): the opponents endpoint returns upcoming opponents keyed by
root_team_id, with progenitor_team_id PRESENT on search-linked entries and the
key OMITTED on manual entries. Fixtures mirror the authoritative shape in
docs/api/endpoints/get-teams-team_id-opponents.md (Test-Validates-Spec).

Two layers of mocking:
  * The parsing + own-team-resolver tests mock a MagicMock client (the
    established pattern for higher-level GameChanger helpers).
  * The pagination test drives a REAL GameChangerClient through respx so the
    x-next-page cursor-following is proven across the page boundary (AC-5/AC-7)
    -- the crawler delegates pagination to client.get_paginated(), so a true
    page-boundary test must exercise that real machinery.

No real HTTP, per .claude/rules/testing.md.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from src.gamechanger.client import GameChangerClient
from src.gamechanger.crawlers.opponents import (
    OPPONENTS_ACCEPT,
    OpponentRecord,
    fetch_opponents,
    resolve_own_team_gc_uuid,
)
from src.gamechanger.exceptions import (
    CredentialExpiredError,
    ForbiddenError,
)
from src.gamechanger.team_resolver import TeamProfile

_GC_UUID = "72bb77d8-0000-4000-8000-000000000001"
_BASE_URL = "https://api.team-manager.gc.com"

_FAKE_CREDENTIALS = {
    "GAMECHANGER_REFRESH_TOKEN_WEB": "fake-refresh-token",
    "GAMECHANGER_CLIENT_ID_WEB": "07cb985d-ff6c-429d-992c-b8a0d44e6fc3",
    "GAMECHANGER_CLIENT_KEY_WEB": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    "GAMECHANGER_DEVICE_ID_WEB": "abcdef1234567890abcdef1234567890",
    "GAMECHANGER_BASE_URL": _BASE_URL,
    "GAMECHANGER_APP_NAME_WEB": "web",
}


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _linked_opponent(
    *, root_team_id: str, name: str, progenitor_team_id: str
) -> dict[str, Any]:
    """A team-lookup opponent: progenitor_team_id KEY present."""
    return {
        "root_team_id": root_team_id,
        "owning_team_id": _GC_UUID,
        "name": name,
        "is_hidden": False,
        "progenitor_team_id": progenitor_team_id,
    }


def _manual_opponent(*, root_team_id: str, name: str) -> dict[str, Any]:
    """A manual-entry opponent: progenitor_team_id KEY omitted entirely."""
    return {
        "root_team_id": root_team_id,
        "owning_team_id": _GC_UUID,
        "name": name,
        "is_hidden": False,
    }


def _make_paginated_client(get_paginated_return: Any) -> MagicMock:
    client = MagicMock()
    client.get_paginated.return_value = get_paginated_return
    return client


# ---------------------------------------------------------------------------
# AC-4: per-opponent records keyed by root_team_id; progenitor present/absent
# ---------------------------------------------------------------------------


def test_fetch_opponents_parses_linked_record() -> None:
    raw = [
        _linked_opponent(
            root_team_id="root-1",
            name="Berthoud Badgers 15U",
            progenitor_team_id="895fa512-0000-4000-8000-000000000002",
        )
    ]
    client = _make_paginated_client(raw)

    records = fetch_opponents(client, _GC_UUID)

    assert len(records) == 1
    record = records[0]
    assert isinstance(record, OpponentRecord)
    assert record.root_team_id == "root-1"
    assert record.name == "Berthoud Badgers 15U"
    assert record.progenitor_team_id == "895fa512-0000-4000-8000-000000000002"
    assert record.has_progenitor is True
    assert record.owning_team_id == _GC_UUID
    assert record.is_hidden is False


def test_fetch_opponents_distinguishes_manual_record_by_key_absence() -> None:
    raw = [_manual_opponent(root_team_id="root-2", name="Gretna")]
    client = _make_paginated_client(raw)

    records = fetch_opponents(client, _GC_UUID)

    assert len(records) == 1
    record = records[0]
    # Key absent -> has_progenitor False, progenitor None.
    assert record.has_progenitor is False
    assert record.progenitor_team_id is None
    assert record.root_team_id == "root-2"


def test_fetch_opponents_null_progenitor_key_present_is_distinct_from_absent() -> None:
    """A PRESENT-but-null progenitor key is key-present (has_progenitor True).

    Rung (a)'s eligibility test is key-presence, not truthiness; this pins that
    a record explicitly carrying ``progenitor_team_id: null`` is treated as
    key-present (even though the value is unusable). The endpoint OMITS the key
    on manual entries, so this is a defensive edge, but the distinction must
    hold.
    """
    raw = [
        {
            "root_team_id": "root-3",
            "owning_team_id": _GC_UUID,
            "name": "Edge Case",
            "is_hidden": False,
            "progenitor_team_id": None,
        }
    ]
    client = _make_paginated_client(raw)

    records = fetch_opponents(client, _GC_UUID)

    assert records[0].has_progenitor is True
    assert records[0].progenitor_team_id is None


def test_fetch_opponents_uses_correct_version_pin() -> None:
    client = _make_paginated_client([])

    fetch_opponents(client, _GC_UUID)

    client.get_paginated.assert_called_once()
    call = client.get_paginated.call_args
    assert call.args[0] == f"/teams/{_GC_UUID}/opponents"
    assert call.kwargs["accept"] == OPPONENTS_ACCEPT
    assert OPPONENTS_ACCEPT == (
        "application/vnd.gc.com.opponent_team:list+json; version=0.0.0"
    )


def test_fetch_opponents_mixed_registry_probe_shape() -> None:
    """F4 probe shape: 6 opponents, 3 linked + 3 manual."""
    raw = [
        _linked_opponent(
            root_team_id=f"root-l{i}",
            name=f"Linked {i}",
            progenitor_team_id=f"prog-{i}",
        )
        for i in range(3)
    ] + [
        _manual_opponent(root_team_id=f"root-m{i}", name=f"Manual {i}")
        for i in range(3)
    ]
    client = _make_paginated_client(raw)

    records = fetch_opponents(client, _GC_UUID)

    assert len(records) == 6
    linked = [r for r in records if r.has_progenitor]
    manual = [r for r in records if not r.has_progenitor]
    assert len(linked) == 3
    assert len(manual) == 3
    assert all(r.progenitor_team_id is not None for r in linked)
    assert all(r.progenitor_team_id is None for r in manual)


def test_fetch_opponents_empty_registry_returns_empty_list() -> None:
    client = _make_paginated_client([])

    assert fetch_opponents(client, _GC_UUID) == []


# ---------------------------------------------------------------------------
# AC-5/AC-7: real pagination across the x-next-page page boundary
# ---------------------------------------------------------------------------


def _build_real_client(monkeypatch: pytest.MonkeyPatch) -> GameChangerClient:
    """Construct a real GameChangerClient with fake creds and a stub token mgr."""
    monkeypatch.setattr(
        "src.gamechanger.client.dotenv_values",
        lambda *_a, **_kw: _FAKE_CREDENTIALS,
    )
    mock_tm = MagicMock()
    mock_tm.get_access_token.return_value = "fake-access-token"
    mock_tm.force_refresh.return_value = "fake-access-token"
    monkeypatch.setattr(
        "src.gamechanger.client.TokenManager", lambda **kwargs: mock_tm
    )
    return GameChangerClient(min_delay_ms=0, jitter_ms=0)


@respx.mock
def test_fetch_opponents_paginates_across_page_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A multi-page registry returns ALL records by following x-next-page.

    Page 1 carries 2 records + an x-next-page header; page 2 carries 1 record
    and NO x-next-page (last page). The crawler must return all 3 -- proving the
    cursor is followed across the boundary, not truncated to page 1.
    """
    page1_url = f"{_BASE_URL}/teams/{_GC_UUID}/opponents"
    next_cursor_url = f"{_BASE_URL}/teams/{_GC_UUID}/opponents?start_at=CURSOR2"

    page1 = [
        _linked_opponent(
            root_team_id="root-1", name="Page1 A", progenitor_team_id="prog-1"
        ),
        _manual_opponent(root_team_id="root-2", name="Page1 B"),
    ]
    page2 = [
        _linked_opponent(
            root_team_id="root-3", name="Page2 A", progenitor_team_id="prog-3"
        ),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if "start_at=CURSOR2" in str(request.url):
            return httpx.Response(200, json=page2)
        return httpx.Response(
            200, json=page1, headers={"x-next-page": next_cursor_url}
        )

    respx.get(url__startswith=page1_url).mock(side_effect=handler)

    client = _build_real_client(monkeypatch)
    records = fetch_opponents(client, _GC_UUID)

    assert [r.root_team_id for r in records] == ["root-1", "root-2", "root-3"]
    assert records[0].has_progenitor is True
    assert records[1].has_progenitor is False
    assert records[2].has_progenitor is True


@respx.mock
def test_fetch_opponents_sends_version_pin_on_real_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Accept version pin reaches the wire (TN-4)."""
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["accept"] = request.headers.get("accept", "")
        return httpx.Response(200, json=[])

    respx.get(f"{_BASE_URL}/teams/{_GC_UUID}/opponents").mock(side_effect=handler)

    client = _build_real_client(monkeypatch)
    fetch_opponents(client, _GC_UUID)

    assert captured["accept"] == OPPONENTS_ACCEPT


# ---------------------------------------------------------------------------
# AC-6: 403 surfaces as ForbiddenError (distinct from auth-expiry 401)
# ---------------------------------------------------------------------------


def test_fetch_opponents_propagates_forbidden_error() -> None:
    client = MagicMock()
    client.get_paginated.side_effect = ForbiddenError("Access denied")

    with pytest.raises(ForbiddenError):
        fetch_opponents(client, _GC_UUID)


def test_fetch_opponents_forbidden_not_collapsed_into_plain_auth_expiry() -> None:
    client = MagicMock()
    client.get_paginated.side_effect = ForbiddenError("Access denied")

    with pytest.raises(CredentialExpiredError) as exc_info:
        fetch_opponents(client, _GC_UUID)

    assert isinstance(exc_info.value, ForbiddenError)


def test_fetch_opponents_propagates_credential_expired_error() -> None:
    client = MagicMock()
    client.get_paginated.side_effect = CredentialExpiredError("token expired")

    with pytest.raises(CredentialExpiredError):
        fetch_opponents(client, _GC_UUID)


# ---------------------------------------------------------------------------
# AC-8: own-team public_id -> gc_uuid resolver
# ---------------------------------------------------------------------------


def _profile(name: str, public_id: str = "dD9PtF0YbKad") -> TeamProfile:
    return TeamProfile(public_id=public_id, name=name, sport="baseball")


def _search_hit(*, name: str, public_id: str, team_id: str) -> dict[str, Any]:
    """A TEAM search hit. The envelope ``type`` is required: the shared
    resolution loop now drops hits whose envelope type is not ``"team"``."""
    return {
        "type": "team",
        "result": {
            "name": name,
            "public_id": public_id,
            "id": team_id,
        },
    }


def test_resolve_own_team_gc_uuid_happy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    public_id = "dD9PtF0YbKad"
    gc_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    monkeypatch.setattr(
        "src.gamechanger.crawlers.opponents.resolve_team",
        lambda pid: _profile("MBA Top Dogg Gold 14U", public_id=pid),
    )
    # Mock at client.post_json (not search_teams_by_name): the resolution loop
    # relocated into search.py (E-247-03), so mocking the transport keeps this
    # test agnostic to where the search call is made.
    client = MagicMock()
    client.post_json.return_value = {
        "hits": [
            _search_hit(
                name="Some Other Team",
                public_id="other-slug",
                team_id="11111111-1111-1111-1111-111111111111",
            ),
            _search_hit(
                name="MBA Top Dogg Gold 14U",
                public_id=public_id,
                team_id=gc_uuid,
            ),
        ]
    }
    result = resolve_own_team_gc_uuid(client, public_id)

    assert result == gc_uuid


def test_resolve_own_team_gc_uuid_pages_until_match_on_later_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex Finding 2: the exact public_id match can land on a LATER page.

    For a common team name, page 0/1 are FULL (page_size hits) with non-matching
    public_ids; the match is on page 2. The resolver must keep paging (mirroring
    the sibling generator.py::_resolve_gc_uuid) rather than inspecting page 0
    only and returning None (which would silently skip the whole team).
    """
    public_id = "dD9PtF0YbKad"
    gc_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    # 25 = _SEARCH_PAGE_SIZE -> a full page signals "more pages may follow".
    def full_page_of_others(page: int) -> list[dict[str, Any]]:
        return [
            _search_hit(
                name="Common Name",
                public_id=f"other-{page}-{i}",
                team_id=f"{page:08d}-1111-1111-1111-{i:012d}",
            )
            for i in range(25)
        ]

    pages = [
        {"hits": full_page_of_others(0)},
        {"hits": full_page_of_others(1)},
        {
            "hits": [
                _search_hit(
                    name="Common Name",
                    public_id=public_id,  # the exact match, on page 2
                    team_id=gc_uuid,
                )
            ]
        },
    ]

    monkeypatch.setattr(
        "src.gamechanger.crawlers.opponents.resolve_team",
        lambda pid: _profile("Common Name", public_id=pid),
    )
    client = MagicMock()
    client.post_json.side_effect = pages

    result = resolve_own_team_gc_uuid(client, public_id)

    assert result == gc_uuid
    # Paged through start_at_page 0, 1, 2 (stopped at the page-2 match).
    pages_requested = [
        c.kwargs["params"]["start_at_page"]
        for c in client.post_json.call_args_list
    ]
    assert pages_requested == [0, 1, 2]


def test_resolve_own_team_gc_uuid_stops_on_partial_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A partial first page (< page_size, no match) short-circuits -- no further
    pages are fetched (mirrors the sibling resolver's short-circuit)."""
    monkeypatch.setattr(
        "src.gamechanger.crawlers.opponents.resolve_team",
        lambda pid: _profile("Clean Name", public_id=pid),
    )
    client = MagicMock()
    # 2 hits (< 25) with no matching public_id -> no more pages.
    client.post_json.return_value = {
        "hits": [
            _search_hit(name="X", public_id="nope-a", team_id="a"),
            _search_hit(name="X", public_id="nope-b", team_id="b"),
        ]
    }

    result = resolve_own_team_gc_uuid(client, "dD9PtF0YbKad")

    assert result is None
    # Short-circuited after the partial first page (one /search call).
    assert client.post_json.call_count == 1


def test_resolve_own_team_gc_uuid_passes_real_name_not_slug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The resolver must search with the team's real NAME, never the slug."""
    public_id = "dD9PtF0YbKad"

    monkeypatch.setattr(
        "src.gamechanger.crawlers.opponents.resolve_team",
        lambda pid: _profile("Real Team Name", public_id=pid),
    )

    client = MagicMock()
    client.post_json.return_value = {
        "hits": [
            _search_hit(
                name="Real Team Name",
                public_id=public_id,
                team_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            )
        ]
    }

    resolve_own_team_gc_uuid(client, public_id)

    # The /search body must carry the team's real NAME, never the slug.
    searched_name = client.post_json.call_args.kwargs["body"]["name"]
    assert searched_name == "Real Team Name"
    assert searched_name != public_id


def test_resolve_own_team_gc_uuid_no_public_id_match_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    public_id = "dD9PtF0YbKad"

    monkeypatch.setattr(
        "src.gamechanger.crawlers.opponents.resolve_team",
        lambda pid: _profile("Team", public_id=pid),
    )
    client = MagicMock()
    client.post_json.return_value = {
        "hits": [
            _search_hit(
                name="Team",
                public_id="different-slug",
                team_id="11111111-1111-1111-1111-111111111111",
            )
        ]
    }

    assert resolve_own_team_gc_uuid(client, public_id) is None


def test_resolve_own_team_gc_uuid_non_uuid_id_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    public_id = "dD9PtF0YbKad"

    monkeypatch.setattr(
        "src.gamechanger.crawlers.opponents.resolve_team",
        lambda pid: _profile("Team", public_id=pid),
    )
    client = MagicMock()
    client.post_json.return_value = {
        "hits": [
            _search_hit(
                name="Team",
                public_id=public_id,
                team_id="not-a-uuid",
            )
        ]
    }

    assert resolve_own_team_gc_uuid(client, public_id) is None


def test_resolve_own_team_gc_uuid_profile_fetch_fails_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.gamechanger.exceptions import TeamNotFoundError

    def boom(pid: str) -> TeamProfile:
        raise TeamNotFoundError("404")

    monkeypatch.setattr(
        "src.gamechanger.crawlers.opponents.resolve_team", boom
    )
    # search must not even be issued when the profile fetch fails.
    client = MagicMock()

    assert resolve_own_team_gc_uuid(client, "dD9PtF0YbKad") is None
    assert client.post_json.call_count == 0


def test_resolve_own_team_gc_uuid_empty_hits_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.gamechanger.crawlers.opponents.resolve_team",
        lambda pid: _profile("Team", public_id=pid),
    )
    client = MagicMock()
    client.post_json.return_value = {"hits": []}

    assert resolve_own_team_gc_uuid(client, "dD9PtF0YbKad") is None


def test_resolve_own_team_gc_uuid_propagates_credential_expired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.gamechanger.crawlers.opponents.resolve_team",
        lambda pid: _profile("Team", public_id=pid),
    )

    client = MagicMock()
    client.post_json.side_effect = CredentialExpiredError("token expired")

    with pytest.raises(CredentialExpiredError):
        resolve_own_team_gc_uuid(client, "dD9PtF0YbKad")


def test_both_resolver_paths_resolve_same_gc_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E-247-03 AC-5: the report-generator path and the own-team opponent path
    resolve the SAME gc_uuid from the same search fixture.

    Both now delegate to the shared ``resolve_gc_uuid_by_public_id`` loop. The
    fixture forces a page-0-full / match-on-page-1 scenario so the shared
    pagination is exercised on both paths. Mocking at ``client.post_json``
    keeps the assertion agnostic to where the search call is issued.
    """
    from src.reports.generator import _resolve_gc_uuid

    public_id = "target-slug"
    gc_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    team_name = "Target Team"

    def fixture_pages() -> list[dict[str, Any]]:
        # Page 0: 25 non-matching hits (full page -> keep paging).
        page0 = [
            _search_hit(
                name="Common",
                public_id=f"other-{i}",
                team_id=f"{i:08d}-1111-1111-1111-111111111111",
            )
            for i in range(25)
        ]
        # Page 1: the exact public_id match.
        page1 = [
            _search_hit(name=team_name, public_id=public_id, team_id=gc_uuid)
        ]
        return [{"hits": page0}, {"hits": page1}]

    # Generator path: team_name is supplied directly.
    gen_client = MagicMock()
    gen_client.post_json.side_effect = fixture_pages()
    gen_result = _resolve_gc_uuid(gen_client, team_name, public_id)

    # Opponent path: the real name is fetched via resolve_team first.
    monkeypatch.setattr(
        "src.gamechanger.crawlers.opponents.resolve_team",
        lambda pid: _profile(team_name, public_id=pid),
    )
    opp_client = MagicMock()
    opp_client.post_json.side_effect = fixture_pages()
    opp_result = resolve_own_team_gc_uuid(opp_client, public_id)

    assert gen_result == gc_uuid
    assert opp_result == gc_uuid
    assert gen_result == opp_result
