"""Tests for the dual header profile configuration."""

from src.http.headers import BROWSER_HEADERS, MOBILE_HEADERS


BROWSER_REQUIRED_KEYS = [
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
    "DNT",
    "Referer",
]

MOBILE_REQUIRED_KEYS = [
    "User-Agent",
    "Accept",
    "Accept-Language",
    "Accept-Encoding",
    "gc-app-version",
    "x-gc-features",
    "x-gc-application-state",
]

BASELINE_KEYS = [
    "User-Agent",
    "Accept",
    "Accept-Language",
    "Accept-Encoding",
]

CREDENTIAL_KEYS = [
    "Authorization",
    "Cookie",
    "Set-Cookie",
    "Proxy-Authorization",
    "X-Api-Key",
    "gc-token",
    "gc-device-id",
]


# --- BROWSER_HEADERS tests ---


def test_browser_headers_is_dict_of_strings() -> None:
    assert isinstance(BROWSER_HEADERS, dict)
    for key, value in BROWSER_HEADERS.items():
        assert isinstance(key, str), f"Key {key!r} is not a string"
        assert isinstance(value, str), f"Value for {key!r} is not a string"


def test_browser_all_required_keys_present() -> None:
    for key in BROWSER_REQUIRED_KEYS:
        assert key in BROWSER_HEADERS, f"Missing required browser header: {key}"


def test_browser_no_credential_keys() -> None:
    for key in CREDENTIAL_KEYS:
        assert key not in BROWSER_HEADERS, f"Credential key must not be in BROWSER_HEADERS: {key}"


def test_browser_user_agent_chrome_145_on_macos() -> None:
    ua = BROWSER_HEADERS["User-Agent"]
    assert "Macintosh" in ua
    assert "Mac OS X" in ua
    assert "Chrome/145.0.0.0" in ua
    assert "Safari/537.36" in ua
    assert ua.startswith("Mozilla/5.0")


def test_browser_sec_ch_ua_chrome_145() -> None:
    sec_ch_ua = BROWSER_HEADERS["sec-ch-ua"]
    assert '"Google Chrome";v="145"' in sec_ch_ua
    assert '"Chromium";v="145"' in sec_ch_ua


def test_browser_sec_ch_ua_mobile_and_platform() -> None:
    assert BROWSER_HEADERS["sec-ch-ua-mobile"] == "?0"
    assert BROWSER_HEADERS["sec-ch-ua-platform"] == '"macOS"'


def test_browser_accept_encoding_supported_only() -> None:
    """Accept-Encoding advertises only encodings httpx handles natively."""
    encoding = BROWSER_HEADERS["Accept-Encoding"]
    assert "gzip" in encoding
    assert "deflate" in encoding
    assert "br" not in encoding
    assert "zstd" not in encoding


def test_browser_dnt_and_referer() -> None:
    """Chrome 145 profile includes DNT and Referer headers."""
    assert BROWSER_HEADERS["DNT"] == "1"
    assert BROWSER_HEADERS["Referer"] == "https://web.gc.com/"


def test_browser_exactly_twelve_headers() -> None:
    assert len(BROWSER_HEADERS) == 12


# --- MOBILE_HEADERS tests ---


def test_mobile_headers_is_dict_of_strings() -> None:
    assert isinstance(MOBILE_HEADERS, dict)
    for key, value in MOBILE_HEADERS.items():
        assert isinstance(key, str), f"Key {key!r} is not a string"
        assert isinstance(value, str), f"Value for {key!r} is not a string"


def test_mobile_all_required_keys_present() -> None:
    for key in MOBILE_REQUIRED_KEYS:
        assert key in MOBILE_HEADERS, f"Missing required mobile header: {key}"


def test_mobile_no_credential_keys() -> None:
    for key in CREDENTIAL_KEYS:
        assert key not in MOBILE_HEADERS, f"Credential key must not be in MOBILE_HEADERS: {key}"


def test_mobile_user_agent_odyssey() -> None:
    ua = MOBILE_HEADERS["User-Agent"]
    assert "Odyssey/2026.7.0" in ua
    assert "com.gc.teammanager" in ua
    assert "Alamofire/5.9.0" in ua


def test_mobile_no_browser_specific_headers() -> None:
    """Mobile profile must not include sec-ch-ua* or sec-fetch-* headers."""
    browser_only = [
        "sec-ch-ua",
        "sec-ch-ua-mobile",
        "sec-ch-ua-platform",
        "sec-fetch-site",
        "sec-fetch-mode",
        "sec-fetch-dest",
    ]
    for key in browser_only:
        assert key not in MOBILE_HEADERS, f"Browser-only header {key} found in MOBILE_HEADERS"


def test_mobile_no_gc_app_name() -> None:
    """Mobile profile should NOT include gc-app-name (web-specific)."""
    assert "gc-app-name" not in MOBILE_HEADERS


def test_mobile_accept_encoding_includes_brotli() -> None:
    """Mobile profile includes Brotli in Accept-Encoding."""
    encoding = MOBILE_HEADERS["Accept-Encoding"]
    assert "br" in encoding
    assert "gzip" in encoding
    assert "deflate" in encoding


def test_mobile_exactly_seven_headers() -> None:
    assert len(MOBILE_HEADERS) == 7


# --- Cross-profile baseline tests ---


def test_both_profiles_contain_baseline_keys() -> None:
    """Both profiles must include User-Agent, Accept, Accept-Language, Accept-Encoding."""
    for key in BASELINE_KEYS:
        assert key in BROWSER_HEADERS, f"BROWSER_HEADERS missing baseline key: {key}"
        assert key in MOBILE_HEADERS, f"MOBILE_HEADERS missing baseline key: {key}"
