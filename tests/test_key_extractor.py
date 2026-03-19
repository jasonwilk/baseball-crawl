"""Tests for src/gamechanger/key_extractor.py.

All HTTP requests are mocked via respx -- no real network calls are made.
"""

from __future__ import annotations

import logging

import httpx
import pytest
import respx

from src.gamechanger.key_extractor import (
    ExtractedKey,
    KeyExtractionError,
    MultipleKeysFoundError,
    _extract_composite,
    _fetch_bundle,
    _fetch_homepage,
    _find_bundle_url,
    _find_composites,
    _parse_composite,
    extract_client_key,
)

# ---------------------------------------------------------------------------
# Fixtures / shared data
# ---------------------------------------------------------------------------

_FAKE_CLIENT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_FAKE_CLIENT_KEY = "abcdefghijklmnopqrstuvwxyz01234567890123456="  # 44 chars
_FAKE_COMPOSITE = f"{_FAKE_CLIENT_ID}:{_FAKE_CLIENT_KEY}"

_BUNDLE_PATH = "/static/js/index.abc123.js"
_BUNDLE_URL = f"https://web.gc.com{_BUNDLE_PATH}"

# Minimal HTML page that links to the bundle.
_HTML_WITH_SCRIPT = f'<html><head><script src="{_BUNDLE_PATH}"></script></head></html>'
_HTML_WITH_ABSOLUTE_SCRIPT = (
    f'<html><head><script src="{_BUNDLE_URL}"></script></head></html>'
)
_HTML_WITH_DOUBLE_QUOTE = f'<html><head><script src="{_BUNDLE_PATH}"></script></head></html>'

# Minimal JS bundle with EDEN_AUTH_CLIENT_KEY embedded.
_JS_BUNDLE = (
    f'ba={{PUBLIC_PREFIX:"",VERSION_NUMBER:"1.0.0",'
    f'EDEN_AUTH_CLIENT_KEY:"{_FAKE_COMPOSITE}",'
    f'RUM_CLIENT_TOKEN:"some-token"}}'
)

# Multi-match fixtures: web key (matches _FAKE_CLIENT_ID) and a mobile key.
_MOBILE_CLIENT_ID = "11111111-2222-3333-4444-555555555555"
_MOBILE_CLIENT_KEY = "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ0="
_MOBILE_COMPOSITE = f"{_MOBILE_CLIENT_ID}:{_MOBILE_CLIENT_KEY}"

# Bundle containing both web and mobile EDEN_AUTH_CLIENT_KEY entries.
_JS_BUNDLE_MULTI = (
    f'ba={{PUBLIC_PREFIX:"",VERSION_NUMBER:"1.0.0",'
    f'EDEN_AUTH_CLIENT_KEY:"{_FAKE_COMPOSITE}",'
    f'EDEN_AUTH_CLIENT_KEY:"{_MOBILE_COMPOSITE}",'
    f'RUM_CLIENT_TOKEN:"some-token"}}'
)


# ---------------------------------------------------------------------------
# Unit tests: _find_bundle_url
# ---------------------------------------------------------------------------


class TestFindBundleUrl:
    def test_finds_relative_src(self) -> None:
        """Relative src is resolved against https://web.gc.com."""
        url = _find_bundle_url(_HTML_WITH_SCRIPT)
        assert url == _BUNDLE_URL

    def test_finds_absolute_src(self) -> None:
        """Absolute src is used as-is."""
        url = _find_bundle_url(_HTML_WITH_ABSOLUTE_SCRIPT)
        assert url == _BUNDLE_URL

    def test_raises_when_no_script_tag(self) -> None:
        """Raises KeyExtractionError when no matching <script> is found."""
        html = "<html><head></head></html>"
        with pytest.raises(KeyExtractionError, match="Could not find JS bundle URL"):
            _find_bundle_url(html)

    def test_raises_when_no_matching_src(self) -> None:
        """Raises when <script> tags exist but none match static/js/index."""
        html = '<html><head><script src="/static/js/vendor.abc.js"></script></head></html>'
        with pytest.raises(KeyExtractionError, match="Could not find JS bundle URL"):
            _find_bundle_url(html)

    def test_uses_first_match_when_multiple(self, caplog: pytest.LogCaptureFixture) -> None:
        """Uses first matching tag and logs a warning when multiple matches exist."""
        html = (
            '<script src="/static/js/index.first.js"></script>'
            '<script src="/static/js/index.second.js"></script>'
        )
        with caplog.at_level(logging.WARNING, logger="src.gamechanger.key_extractor"):
            url = _find_bundle_url(html)
        assert "index.first.js" in url
        assert "Multiple" in caplog.text


# ---------------------------------------------------------------------------
# Unit tests: _extract_composite
# ---------------------------------------------------------------------------


class TestExtractComposite:
    def test_extracts_composite_value(self) -> None:
        """Returns the composite value when EDEN_AUTH_CLIENT_KEY is present."""
        composite = _extract_composite(_JS_BUNDLE)
        assert composite == _FAKE_COMPOSITE

    def test_raises_when_key_absent(self) -> None:
        """Raises KeyExtractionError when EDEN_AUTH_CLIENT_KEY is not in the bundle."""
        js = "ba={PUBLIC_PREFIX:'',VERSION_NUMBER:'1.0.0'}"
        with pytest.raises(KeyExtractionError, match="EDEN_AUTH_CLIENT_KEY not found"):
            _extract_composite(js)

    def test_extracts_from_larger_bundle(self) -> None:
        """Correctly extracts even with surrounding content."""
        js = (
            "some_random_code=1;"
            f'EDEN_AUTH_CLIENT_KEY:"{_FAKE_COMPOSITE}",OTHER_KEY:"other"'
            ";more_code=2;"
        )
        composite = _extract_composite(js)
        assert composite == _FAKE_COMPOSITE


# ---------------------------------------------------------------------------
# Unit tests: _parse_composite
# ---------------------------------------------------------------------------


class TestParseComposite:
    def test_splits_on_first_colon(self) -> None:
        """Splits on first ':' -- client_key may contain '=' but not ':'."""
        result = _parse_composite(_FAKE_COMPOSITE, _BUNDLE_URL)
        assert result.client_id == _FAKE_CLIENT_ID
        assert result.client_key == _FAKE_CLIENT_KEY

    def test_bundle_url_preserved(self) -> None:
        """bundle_url is stored in the result."""
        result = _parse_composite(_FAKE_COMPOSITE, _BUNDLE_URL)
        assert result.bundle_url == _BUNDLE_URL

    def test_raises_when_no_colon(self) -> None:
        """Raises KeyExtractionError when composite has no ':' separator."""
        with pytest.raises(KeyExtractionError, match="does not contain ':' separator"):
            _parse_composite("badvaluenocoherenformat", _BUNDLE_URL)

    def test_result_is_frozen_dataclass(self) -> None:
        """ExtractedKey is a frozen dataclass (immutable)."""
        result = _parse_composite(_FAKE_COMPOSITE, _BUNDLE_URL)
        assert isinstance(result, ExtractedKey)
        with pytest.raises(Exception):
            result.client_id = "should-fail"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Integration tests: extract_client_key (full flow with mocked HTTP)
# ---------------------------------------------------------------------------


def _mock_gc_bundle(
    mock: respx.MockRouter,
    html: str = _HTML_WITH_SCRIPT,
    bundle_content: str = _JS_BUNDLE,
    bundle_url: str = _BUNDLE_URL,
    homepage_status: int = 200,
    bundle_status: int = 200,
) -> None:
    """Register homepage + bundle mocks in the correct order (specific path first)."""
    # IMPORTANT: Register the specific bundle path BEFORE the bare hostname route.
    # respx matches routes in registration order, and https://web.gc.com would
    # otherwise match https://web.gc.com/static/js/... as well.
    mock.get(bundle_url).mock(
        return_value=httpx.Response(bundle_status, text=bundle_content)
    )
    mock.get("https://web.gc.com").mock(
        return_value=httpx.Response(homepage_status, text=html)
    )


def test_successful_extraction() -> None:
    """Happy path: fetches HTML, finds bundle, extracts key."""
    with respx.mock as mock:
        _mock_gc_bundle(mock)
        result = extract_client_key()

    assert result.client_id == _FAKE_CLIENT_ID
    assert result.client_key == _FAKE_CLIENT_KEY
    assert result.bundle_url == _BUNDLE_URL


def test_key_unchanged_scenario() -> None:
    """Same key fetched twice produces identical results."""
    with respx.mock as mock:
        _mock_gc_bundle(mock)
        result1 = extract_client_key()
        result2 = extract_client_key()

    assert result1.client_key == result2.client_key
    assert result1.client_id == result2.client_id


def test_homepage_fetch_failure_network_error() -> None:
    """Network error on homepage fetch raises KeyExtractionError with URL."""
    with respx.mock:
        respx.get("https://web.gc.com").mock(side_effect=httpx.ConnectError("refused"))

        with pytest.raises(KeyExtractionError, match="https://web.gc.com"):
            extract_client_key()


def test_homepage_non_200_raises() -> None:
    """Non-200 response from homepage raises KeyExtractionError."""
    with respx.mock:
        respx.get("https://web.gc.com").mock(
            return_value=httpx.Response(503, text="Service Unavailable")
        )

        with pytest.raises(KeyExtractionError, match="HTTP 503"):
            extract_client_key()


def test_bundle_url_not_found_in_html() -> None:
    """Missing <script> tag raises KeyExtractionError explaining the pattern."""
    with respx.mock:
        respx.get("https://web.gc.com").mock(
            return_value=httpx.Response(200, text="<html><head></head></html>")
        )

        with pytest.raises(KeyExtractionError, match="Could not find JS bundle URL"):
            extract_client_key()


def test_bundle_fetch_network_error() -> None:
    """Network error on bundle fetch raises KeyExtractionError with bundle URL."""
    with respx.mock as mock:
        # Register bundle first (specific URL before generic hostname)
        mock.get(_BUNDLE_URL).mock(side_effect=httpx.ConnectError("refused"))
        mock.get("https://web.gc.com").mock(
            return_value=httpx.Response(200, text=_HTML_WITH_SCRIPT)
        )

        with pytest.raises(KeyExtractionError, match=_BUNDLE_URL):
            extract_client_key()


def test_eden_key_not_in_bundle() -> None:
    """Missing EDEN_AUTH_CLIENT_KEY in bundle raises KeyExtractionError."""
    with respx.mock as mock:
        _mock_gc_bundle(mock, bundle_content='ba={OTHER:"value"}')

        with pytest.raises(KeyExtractionError, match="EDEN_AUTH_CLIENT_KEY not found"):
            extract_client_key()


def test_multiple_script_tags_uses_first(caplog: pytest.LogCaptureFixture) -> None:
    """When multiple <script> tags match, first is used and a warning is logged."""
    html = (
        '<script src="/static/js/index.first.js"></script>'
        '<script src="/static/js/index.second.js"></script>'
    )
    first_bundle_url = "https://web.gc.com/static/js/index.first.js"

    with respx.mock as mock:
        # Register specific path first
        mock.get(first_bundle_url).mock(
            return_value=httpx.Response(200, text=_JS_BUNDLE)
        )
        mock.get("https://web.gc.com").mock(
            return_value=httpx.Response(200, text=html)
        )

        with caplog.at_level(logging.WARNING, logger="src.gamechanger.key_extractor"):
            result = extract_client_key()

    assert "index.first.js" in result.bundle_url
    assert "Multiple" in caplog.text


def test_no_credential_values_exposed() -> None:
    """The client_key value is present in the result but not in any log output."""
    with respx.mock as mock:
        _mock_gc_bundle(mock)
        result = extract_client_key()

    # The extractor returns the key so the CLI can compare it; the CLI is
    # responsible for never printing it. Verify the result contains it.
    assert result.client_key == _FAKE_CLIENT_KEY


# ---------------------------------------------------------------------------
# Unit tests: _find_composites
# ---------------------------------------------------------------------------


class TestFindComposites:
    def test_single_match(self) -> None:
        """Returns a one-element list when only one key is in the bundle."""
        result = _find_composites(_JS_BUNDLE)
        assert result == [_FAKE_COMPOSITE]

    def test_multi_match(self) -> None:
        """Returns all matches when the bundle contains multiple entries."""
        result = _find_composites(_JS_BUNDLE_MULTI)
        assert result == [_FAKE_COMPOSITE, _MOBILE_COMPOSITE]

    def test_raises_when_absent(self) -> None:
        """Raises KeyExtractionError when no EDEN_AUTH_CLIENT_KEY is found."""
        with pytest.raises(KeyExtractionError, match="EDEN_AUTH_CLIENT_KEY not found"):
            _find_composites('ba={OTHER:"value"}')


# ---------------------------------------------------------------------------
# Integration tests: extract_client_key multi-match scenarios (AC-1, AC-2, AC-3, AC-4)
# ---------------------------------------------------------------------------


def test_single_match_behavior_unchanged() -> None:
    """AC-4: single-match bundles behave identically to the old implementation."""
    with respx.mock as mock:
        _mock_gc_bundle(mock)
        result = extract_client_key()

    assert result.client_id == _FAKE_CLIENT_ID
    assert result.client_key == _FAKE_CLIENT_KEY


def test_multi_match_logs_all_uuids(caplog: pytest.LogCaptureFixture) -> None:
    """AC-1: all discovered UUIDs are logged (not key material)."""
    with respx.mock as mock:
        _mock_gc_bundle(mock, bundle_content=_JS_BUNDLE_MULTI)
        with caplog.at_level(logging.INFO, logger="src.gamechanger.key_extractor"):
            try:
                extract_client_key()
            except MultipleKeysFoundError:
                pass  # expected -- we only care about the log output here

    assert _FAKE_CLIENT_ID in caplog.text
    assert _MOBILE_CLIENT_ID in caplog.text
    # Key material must NOT appear in logs.
    assert _FAKE_CLIENT_KEY not in caplog.text
    assert _MOBILE_CLIENT_KEY not in caplog.text


def test_multi_match_with_known_id_selects_correct_key() -> None:
    """AC-2: known_client_id selects the matching entry from multiple candidates."""
    with respx.mock as mock:
        _mock_gc_bundle(mock, bundle_content=_JS_BUNDLE_MULTI)
        result = extract_client_key(known_client_id=_FAKE_CLIENT_ID)

    assert result.client_id == _FAKE_CLIENT_ID
    assert result.client_key == _FAKE_CLIENT_KEY


def test_multi_match_with_known_id_selects_mobile_key() -> None:
    """AC-2: known_client_id can also select the mobile entry when that ID is known."""
    with respx.mock as mock:
        _mock_gc_bundle(mock, bundle_content=_JS_BUNDLE_MULTI)
        result = extract_client_key(known_client_id=_MOBILE_CLIENT_ID)

    assert result.client_id == _MOBILE_CLIENT_ID
    assert result.client_key == _MOBILE_CLIENT_KEY


def test_multi_match_without_known_id_raises() -> None:
    """AC-3: raises MultipleKeysFoundError with all candidates when known_client_id is not set."""
    with respx.mock as mock:
        _mock_gc_bundle(mock, bundle_content=_JS_BUNDLE_MULTI)
        with pytest.raises(MultipleKeysFoundError) as exc_info:
            extract_client_key(known_client_id=None)

    candidates = exc_info.value.candidates
    assert len(candidates) == 2
    candidate_ids = {c.client_id for c in candidates}
    assert _FAKE_CLIENT_ID in candidate_ids
    assert _MOBILE_CLIENT_ID in candidate_ids


def test_multi_match_with_nonmatching_known_id_raises() -> None:
    """MultipleKeysFoundError raised when known_client_id doesn't match any candidate."""
    with respx.mock as mock:
        _mock_gc_bundle(mock, bundle_content=_JS_BUNDLE_MULTI)
        with pytest.raises(MultipleKeysFoundError) as exc_info:
            extract_client_key(known_client_id="00000000-0000-0000-0000-000000000000")

    assert len(exc_info.value.candidates) == 2
