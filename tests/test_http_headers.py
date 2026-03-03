"""Tests for the canonical browser header configuration."""

from src.http.headers import BROWSER_HEADERS


REQUIRED_KEYS = [
    "User-Agent",
    "Accept",
    "Accept-Language",
    "Accept-Encoding",
    "sec-ch-ua",
    "sec-ch-ua-mobile",
    "sec-ch-ua-platform",
    "sec-fetch-site",
    "sec-fetch-mode",
    "sec-fetch-dest",
]

CREDENTIAL_KEYS = [
    "Authorization",
    "Cookie",
    "Set-Cookie",
    "Proxy-Authorization",
    "X-Api-Key",
]


def test_browser_headers_is_dict_of_strings() -> None:
    assert isinstance(BROWSER_HEADERS, dict)
    for key, value in BROWSER_HEADERS.items():
        assert isinstance(key, str), f"Key {key!r} is not a string"
        assert isinstance(value, str), f"Value for {key!r} is not a string"


def test_all_required_keys_present() -> None:
    for key in REQUIRED_KEYS:
        assert key in BROWSER_HEADERS, f"Missing required header: {key}"


def test_no_credential_keys() -> None:
    for key in CREDENTIAL_KEYS:
        assert key not in BROWSER_HEADERS, f"Credential key must not be in BROWSER_HEADERS: {key}"


def test_user_agent_chrome_on_macos() -> None:
    ua = BROWSER_HEADERS["User-Agent"]
    assert "Macintosh" in ua
    assert "Mac OS X" in ua
    assert "Chrome/131.0.0.0" in ua
    assert "Safari/537.36" in ua
    assert ua.startswith("Mozilla/5.0")


def test_sec_ch_ua_chrome_131() -> None:
    sec_ch_ua = BROWSER_HEADERS["sec-ch-ua"]
    assert '"Google Chrome";v="131"' in sec_ch_ua
    assert '"Chromium";v="131"' in sec_ch_ua


def test_sec_ch_ua_mobile_and_platform() -> None:
    assert BROWSER_HEADERS["sec-ch-ua-mobile"] == "?0"
    assert BROWSER_HEADERS["sec-ch-ua-platform"] == '"macOS"'


def test_accept_encoding_supported_only() -> None:
    """Accept-Encoding advertises only encodings httpx handles natively."""
    encoding = BROWSER_HEADERS["Accept-Encoding"]
    assert "gzip" in encoding
    assert "deflate" in encoding
    assert "br" not in encoding
    assert "zstd" not in encoding


def test_exactly_ten_headers() -> None:
    assert len(BROWSER_HEADERS) == 10
