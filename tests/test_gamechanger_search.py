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
