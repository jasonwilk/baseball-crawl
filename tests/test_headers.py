"""Tests for HTTP header profiles in src/http/headers.py."""

from src.http.headers import MOBILE_HEADERS


def test_mobile_headers_accept_encoding_includes_br() -> None:
    """Mobile headers must include 'br' in Accept-Encoding to match iOS app behavior."""
    assert "br" in MOBILE_HEADERS["Accept-Encoding"]
