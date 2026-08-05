"""Tests for src.gamechanger.search.

GC-side storage convention: GameChanger normalizes team names with a curly
apostrophe (U+2019) at index time. A query using a straight apostrophe
(U+0027) returns zero hits even when a curly-apostrophe team is indexed --
this is the Unicode apostrophe trap covered explicitly below per TN-8.
"""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.gamechanger.exceptions import CredentialExpiredError
from src.gamechanger.search import (
    _SEARCH_CONTENT_TYPE,
    _SEARCH_PAGE_SIZE,
    is_team_hit,
    resolve_gc_uuid_by_public_id,
    search_teams_by_name,
)


def _hit(name: str) -> dict[str, Any]:
    return {
        "result": {
            "name": name,
            "public_id": "yecaUcoSVpJa",
            "id": "ac053e2c-ee27-4f55-9b16-ed77c1bdfebb",
        }
    }


def _make_client(side_effect: Any) -> MagicMock:
    client = MagicMock()
    client.post_json.side_effect = side_effect
    return client


# ---------------------------------------------------------------------------
# AC-1: Signature
# ---------------------------------------------------------------------------


def test_signature_keyword_only_start_at_page() -> None:
    sig = inspect.signature(search_teams_by_name)
    params = sig.parameters

    assert list(params) == ["client", "team_name", "start_at_page"]
    assert params["client"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert params["team_name"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert params["start_at_page"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["start_at_page"].default == 0


# ---------------------------------------------------------------------------
# AC-2: Single call for gate-clean names
# ---------------------------------------------------------------------------


def test_clean_name_single_call_hits_passed_through() -> None:
    response = {"hits": [_hit("Lincoln Northwest Falcons")]}
    client = _make_client([response])

    result = search_teams_by_name(client, "Lincoln Northwest Falcons")

    assert result == response["hits"]
    assert client.post_json.call_count == 1
    call = client.post_json.call_args_list[0]
    assert call.args == ("/search",)
    assert call.kwargs["body"] == {"name": "Lincoln Northwest Falcons"}
    assert call.kwargs["params"] == {
        "start_at_page": 0,
        "search_source": "search",
    }
    assert call.kwargs["content_type"] == _SEARCH_CONTENT_TYPE


def test_clean_name_single_call_empty_hits_returned() -> None:
    client = _make_client([{"hits": []}])

    result = search_teams_by_name(client, "Lincoln")

    assert result == []
    assert client.post_json.call_count == 1


# ---------------------------------------------------------------------------
# AC-10: Negative regression -- multi-word clean name should not trigger fallback
# ---------------------------------------------------------------------------


def test_clean_multiword_name_empty_hits_no_fallback() -> None:
    client = _make_client([{"hits": []}])

    result = search_teams_by_name(client, "Lincoln Northwest Falcons")

    assert result == []
    assert client.post_json.call_count == 1


# ---------------------------------------------------------------------------
# AC-3: Fallback fires for each trigger character
# ---------------------------------------------------------------------------


def test_slash_name_first_empty_triggers_normalized_fallback_returns_hits() -> None:
    fallback_response = {"hits": [_hit("Lincoln Northwest JV/Reserve Falcons")]}
    client = _make_client([{"hits": []}, fallback_response])

    result = search_teams_by_name(
        client, "Lincoln Northwest JV/Reserve Falcons"
    )

    assert result == fallback_response["hits"]
    assert client.post_json.call_count == 2
    assert (
        client.post_json.call_args_list[0].kwargs["body"]["name"]
        == "Lincoln Northwest JV/Reserve Falcons"
    )
    assert (
        client.post_json.call_args_list[1].kwargs["body"]["name"]
        == "Lincoln Northwest JV Reserve Falcons"
    )


def test_percent_name_first_empty_triggers_normalized_fallback_returns_hits() -> None:
    fallback_response = {"hits": [_hit("Team 20 Varsity")]}
    client = _make_client([{"hits": []}, fallback_response])

    result = search_teams_by_name(client, "Team%20 Varsity")

    assert result == fallback_response["hits"]
    assert client.post_json.call_count == 2
    assert (
        client.post_json.call_args_list[0].kwargs["body"]["name"]
        == "Team%20 Varsity"
    )
    assert (
        client.post_json.call_args_list[1].kwargs["body"]["name"]
        == "Team 20 Varsity"
    )


def test_hash_name_first_empty_triggers_normalized_fallback_returns_hits() -> None:
    fallback_response = {"hits": [_hit("Team 1 Varsity")]}
    client = _make_client([{"hits": []}, fallback_response])

    result = search_teams_by_name(client, "Team#1 Varsity")

    assert result == fallback_response["hits"]
    assert client.post_json.call_count == 2
    assert (
        client.post_json.call_args_list[0].kwargs["body"]["name"]
        == "Team#1 Varsity"
    )
    assert (
        client.post_json.call_args_list[1].kwargs["body"]["name"]
        == "Team 1 Varsity"
    )


def test_straight_apostrophe_name_first_empty_triggers_normalized_fallback_returns_hits() -> None:
    fallback_response = {"hits": [_hit("O\u2019Connor Academy Varsity")]}
    client = _make_client([{"hits": []}, fallback_response])

    result = search_teams_by_name(client, "O'Connor Academy Varsity")

    assert result == fallback_response["hits"]
    assert client.post_json.call_count == 2
    assert (
        client.post_json.call_args_list[0].kwargs["body"]["name"]
        == "O'Connor Academy Varsity"
    )
    assert (
        client.post_json.call_args_list[1].kwargs["body"]["name"]
        == "O Connor Academy Varsity"
    )


# ---------------------------------------------------------------------------
# AC-8: Curly apostrophe -- first attempt hits, fallback never fires
# ---------------------------------------------------------------------------


def test_curly_apostrophe_name_first_hits_no_fallback() -> None:
    response = {"hits": [_hit("Kearney A\u2019s 10U")]}
    client = _make_client([response])

    result = search_teams_by_name(client, "Kearney A\u2019s 10U")

    assert result == response["hits"]
    assert client.post_json.call_count == 1
    assert (
        client.post_json.call_args_list[0].kwargs["body"]["name"]
        == "Kearney A\u2019s 10U"
    )


# ---------------------------------------------------------------------------
# AC-4: Punctuation name with non-empty first attempt -- no fallback
# ---------------------------------------------------------------------------


def test_punctuation_name_first_nonempty_no_fallback() -> None:
    response = {"hits": [_hit("Lincoln Northwest JV/Reserve Falcons")]}
    client = _make_client([response])

    result = search_teams_by_name(
        client, "Lincoln Northwest JV/Reserve Falcons"
    )

    assert result == response["hits"]
    assert client.post_json.call_count == 1


# ---------------------------------------------------------------------------
# AC-5: Both attempts empty -- returns empty list
# ---------------------------------------------------------------------------


def test_punctuation_name_both_attempts_empty_returns_empty_list() -> None:
    client = _make_client([{"hits": []}, {"hits": []}])

    result = search_teams_by_name(
        client, "Lincoln Northwest JV/Reserve Falcons"
    )

    assert result == []
    assert client.post_json.call_count == 2
    assert (
        client.post_json.call_args_list[0].kwargs["body"]["name"]
        == "Lincoln Northwest JV/Reserve Falcons"
    )
    assert (
        client.post_json.call_args_list[1].kwargs["body"]["name"]
        == "Lincoln Northwest JV Reserve Falcons"
    )


# ---------------------------------------------------------------------------
# AC-6: Exception propagation
# ---------------------------------------------------------------------------


def test_credential_expired_error_propagates() -> None:
    client = _make_client(CredentialExpiredError("token expired"))

    with pytest.raises(CredentialExpiredError, match="token expired"):
        search_teams_by_name(client, "Lincoln Northwest JV/Reserve Falcons")

    assert client.post_json.call_count == 1


# ---------------------------------------------------------------------------
# AC-9: start_at_page threaded to both attempts
# ---------------------------------------------------------------------------


def test_start_at_page_passed_through_to_both_attempts() -> None:
    fallback_response = {"hits": [_hit("Lincoln Northwest JV Reserve Falcons")]}
    client = _make_client([{"hits": []}, fallback_response])

    result = search_teams_by_name(
        client,
        "Lincoln Northwest JV/Reserve Falcons",
        start_at_page=2,
    )

    assert result == fallback_response["hits"]
    assert client.post_json.call_count == 2
    assert (
        client.post_json.call_args_list[0].kwargs["params"]["start_at_page"]
        == 2
    )
    assert (
        client.post_json.call_args_list[1].kwargs["params"]["start_at_page"]
        == 2
    )


# ---------------------------------------------------------------------------
# AC-11: Exact normalization output
# ---------------------------------------------------------------------------


def test_normalization_exact_output() -> None:
    fallback_response = {"hits": [_hit("Lincoln JV Team")]}
    client = _make_client([{"hits": []}, fallback_response])

    result = search_teams_by_name(client, "Lincoln // JV  Team")

    assert result == fallback_response["hits"]
    assert client.post_json.call_count == 2
    assert (
        client.post_json.call_args_list[1].kwargs["body"]["name"]
        == "Lincoln JV Team"
    )


def test_normalization_collapses_tab_and_newline() -> None:
    fallback_response = {"hits": [_hit("Lincoln JV Team")]}
    client = _make_client([{"hits": []}, fallback_response])

    result = search_teams_by_name(client, "Lincoln\tJV\nTeam")

    assert result == fallback_response["hits"]
    assert client.post_json.call_count == 2
    assert (
        client.post_json.call_args_list[1].kwargs["body"]["name"]
        == "Lincoln JV Team"
    )


def test_accented_letter_preserved_in_normalization() -> None:
    fallback_response = {"hits": [_hit("Gonz\u00e0lez Varsity JV")]}
    client = _make_client([{"hits": []}, fallback_response])

    result = search_teams_by_name(client, "Gonz\u00e0lez Varsity/JV")

    assert result == fallback_response["hits"]
    assert client.post_json.call_count == 2
    assert (
        client.post_json.call_args_list[1].kwargs["body"]["name"]
        == "Gonz\u00e0lez Varsity JV"
    )


# ---------------------------------------------------------------------------
# Edge case: empty string -- gate condition false, single call (TN-11)
# ---------------------------------------------------------------------------


def test_empty_string_name_single_call_no_fallback() -> None:
    client = _make_client([{"hits": []}])

    result = search_teams_by_name(client, "")

    assert result == []
    assert client.post_json.call_count == 1
    assert client.post_json.call_args_list[0].kwargs["body"]["name"] == ""


# ---------------------------------------------------------------------------
# Defensive guard: post_json is typed -> Any; treat non-dict as zero hits
# (matches the existing pattern at all four current call sites)
# ---------------------------------------------------------------------------


def test_non_dict_first_response_treated_as_empty_triggers_fallback() -> None:
    fallback_response = {"hits": [_hit("Lincoln Northwest JV Reserve Falcons")]}
    client = _make_client([["unexpected", "list"], fallback_response])

    result = search_teams_by_name(
        client, "Lincoln Northwest JV/Reserve Falcons"
    )

    assert result == fallback_response["hits"]
    assert client.post_json.call_count == 2


def test_non_dict_fallback_response_returns_empty_list() -> None:
    client = _make_client([{"hits": []}, "unexpected string"])

    result = search_teams_by_name(
        client, "Lincoln Northwest JV/Reserve Falcons"
    )

    assert result == []
    assert client.post_json.call_count == 2


# ---------------------------------------------------------------------------
# Entity class: POST /search returns TEAMS and ORGANIZATIONS in one result set.
# Organizations carry a public_id (93/93 measured), so a public_id-only filter
# can select one, and an organization's id is not a team id.
# ---------------------------------------------------------------------------

_SOUGHT_PUBLIC_ID = "yecaUcoSVpJa"
_TEAM_UUID = "ac053e2c-ee27-4f55-9b16-ed77c1bdfebb"
_ORG_UUID = "11111111-2222-3333-4444-555555555555"


def _team_hit(public_id: str = _SOUGHT_PUBLIC_ID, team_id: str = _TEAM_UUID) -> dict[str, Any]:
    """A TEAM hit in the real shape.

    Note what is ABSENT: teams carry no ``result.type`` key at all (the key is
    OMITTED, not null). That omission is what makes a ``result.type`` check
    reject every real team.
    """
    return {
        "type": "team",
        "result": {
            "name": "Lincoln Northwest Falcons",
            "public_id": public_id,
            "id": team_id,
            "number_of_players": 14,
            "staff": ["Coach One", "Coach Two"],
        },
    }


def _organization_hit(
    public_id: str = _SOUGHT_PUBLIC_ID, org_id: str = _ORG_UUID
) -> dict[str, Any]:
    """An ORGANIZATION hit in the real shape.

    ``result.type`` is the organization SUBTYPE (travel/tournament/league) --
    never the string ``"team"``. ``number_of_players`` and ``staff`` are
    omitted entirely, the inverse of the team shape above.
    """
    return {
        "type": "organization",
        "result": {
            "name": "Lincoln Northwest Falcons",
            "public_id": public_id,
            "id": org_id,
            "type": "travel",
            "tournament_dates": {"start": "2026-05-01", "end": "2026-05-03"},
        },
    }


def test_is_team_hit_reads_envelope_type_not_result_type() -> None:
    """The predicate reads the ENVELOPE type.

    This is the anti-inversion guard. ``result.type`` is the organization
    SUBTYPE and is absent on teams, so a check rewritten to
    ``result.get("type") == "team"`` matches NOTHING -- it would reject the
    team below and still reject the organization. Both assertions on the shape
    are what make that inversion fail here rather than pass silently.
    """
    team = _team_hit()
    organization = _organization_hit()

    # The shape the inversion depends on: teams OMIT result.type entirely,
    # organizations carry a subtype string that is never "team".
    assert "type" not in team["result"]
    assert organization["result"]["type"] == "travel"
    assert organization["result"]["type"] != "team"

    assert is_team_hit(team) is True
    assert is_team_hit(organization) is False


def test_is_team_hit_fails_closed_on_absent_or_unknown_envelope_type() -> None:
    """A missing or unrecognized entity class is NOT a team."""
    assert is_team_hit({"result": {"public_id": _SOUGHT_PUBLIC_ID}}) is False
    assert is_team_hit({"type": None, "result": {}}) is False
    assert is_team_hit({"type": "organization", "result": {}}) is False
    assert is_team_hit({"type": "Team", "result": {}}) is False
    assert is_team_hit("not a dict") is False


def test_organization_sharing_public_id_is_skipped_and_team_is_yielded() -> None:
    """An organization and a team share one public_id -> only the team yields.

    This is the defect the filter exists to prevent: both hits pass a
    public_id-only filter, and the organization is listed FIRST, so an
    unfiltered loop yields the organization's id as a gc_uuid.
    """
    client = _make_client(
        [{"hits": [_organization_hit(), _team_hit()]}]
    )

    yielded = list(
        resolve_gc_uuid_by_public_id(
            client, "Lincoln Northwest Falcons", _SOUGHT_PUBLIC_ID
        )
    )

    assert yielded == [(0, _TEAM_UUID)]
    assert _ORG_UUID not in [candidate for _, candidate in yielded]


def test_organization_with_sought_public_id_warns_and_paging_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Skip-and-continue, not refuse: a later page's team is still reached.

    Page 0 is FULL (so paging continues) and contains an organization carrying
    the exact sought public_id; the real team is on page 1. A refuse-on-org
    design would return nothing here.
    """
    page_zero = [_organization_hit()] + [
        {
            "type": "team",
            "result": {
                "name": "Lincoln Northwest Falcons",
                "public_id": f"other-{i}",
                "id": f"uuid-{i}",
            },
        }
        for i in range(_SEARCH_PAGE_SIZE - 1)
    ]
    client = _make_client(
        [{"hits": page_zero}, {"hits": [_team_hit()]}]
    )

    with caplog.at_level("WARNING", logger="src.gamechanger.search"):
        yielded = list(
            resolve_gc_uuid_by_public_id(
                client, "Lincoln Northwest Falcons", _SOUGHT_PUBLIC_ID
            )
        )

    assert yielded == [(1, _TEAM_UUID)]
    assert client.post_json.call_count == 2
    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.levelname == "WARNING"
    ]
    assert len(warnings) == 1
    assert "organization id is not a team id" in warnings[0]
    assert _SOUGHT_PUBLIC_ID in warnings[0]


def test_all_organization_hits_yield_no_candidate() -> None:
    """An all-organization result set resolves to nothing, never to an org id."""
    client = _make_client(
        [{"hits": [_organization_hit(), _organization_hit(org_id="other-org")]}]
    )

    yielded = list(
        resolve_gc_uuid_by_public_id(
            client, "Lincoln Northwest Falcons", _SOUGHT_PUBLIC_ID
        )
    )

    assert yielded == []


def test_entity_class_check_does_not_shorten_pagination() -> None:
    """Filtering happens per hit, NOT inside search_teams_by_name.

    A full page of 25 organizations must still read as a FULL page so paging
    continues. Were the filter applied at the source, this page would arrive
    as 0 hits, look partial, and strand the team on page 1.
    """
    org_page = [
        _organization_hit(public_id=f"org-{i}", org_id=f"org-uuid-{i}")
        for i in range(_SEARCH_PAGE_SIZE)
    ]
    client = _make_client([{"hits": org_page}, {"hits": [_team_hit()]}])

    yielded = list(
        resolve_gc_uuid_by_public_id(
            client, "Lincoln Northwest Falcons", _SOUGHT_PUBLIC_ID
        )
    )

    assert yielded == [(1, _TEAM_UUID)]
    assert client.post_json.call_count == 2
