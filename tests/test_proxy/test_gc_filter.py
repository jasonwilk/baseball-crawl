"""Unit tests for proxy/addons/gc_filter.py."""

from proxy.addons.gc_filter import detect_source, is_gamechanger_domain


# ---------------------------------------------------------------------------
# is_gamechanger_domain()
# ---------------------------------------------------------------------------


class TestIsGamechangerDomain:
    def test_gc_com_exact(self) -> None:
        assert is_gamechanger_domain("gc.com") is True

    def test_api_gc_com_subdomain(self) -> None:
        assert is_gamechanger_domain("api.gc.com") is True

    def test_deep_subdomain_gc_com(self) -> None:
        assert is_gamechanger_domain("app.api.gc.com") is True

    def test_gamechanger_com_exact(self) -> None:
        assert is_gamechanger_domain("gamechanger.com") is True

    def test_subdomain_gamechanger_com(self) -> None:
        assert is_gamechanger_domain("www.gamechanger.com") is True

    def test_case_insensitive(self) -> None:
        assert is_gamechanger_domain("API.GC.COM") is True

    def test_non_gc_domain(self) -> None:
        assert is_gamechanger_domain("google.com") is False

    def test_httpbin_non_gc(self) -> None:
        assert is_gamechanger_domain("httpbin.org") is False

    def test_partial_match_does_not_count(self) -> None:
        # "notgc.com" should not match -- not a subdomain of gc.com
        assert is_gamechanger_domain("notgc.com") is False

    def test_suffix_only_does_not_match(self) -> None:
        # "evil-gc.com" is not a subdomain of gc.com
        assert is_gamechanger_domain("evil-gc.com") is False

    def test_empty_string(self) -> None:
        assert is_gamechanger_domain("") is False


# ---------------------------------------------------------------------------
# detect_source()
# ---------------------------------------------------------------------------


class TestDetectSource:
    # iOS: GameChanger app User-Agent
    def test_ios_gamechanger_app(self) -> None:
        ua = "GameChanger/1234 CFNetwork/1410.0.3 Darwin/22.6.0"
        assert detect_source(ua) == "ios"

    # iOS: CFNetwork marker alone
    def test_ios_cfnetwork(self) -> None:
        ua = "CFNetwork/1410.0.3 Darwin/22.6.0"
        assert detect_source(ua) == "ios"

    # iOS: Darwin marker alone
    def test_ios_darwin(self) -> None:
        ua = "SomeApp/1.0 Darwin/22.6.0"
        assert detect_source(ua) == "ios"

    # Safari on iOS must be classified as "ios" (contains Safari/ but also iOS markers)
    def test_safari_on_ios_classified_as_ios(self) -> None:
        ua = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Mobile/15E148 Safari/604.1"
        )
        assert detect_source(ua) == "ios"

    # Desktop Chrome
    def test_web_chrome(self) -> None:
        ua = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        assert detect_source(ua) == "web"

    # Firefox
    def test_web_firefox(self) -> None:
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) "
            "Gecko/20100101 Firefox/121.0"
        )
        assert detect_source(ua) == "web"

    # Desktop Safari (macOS) -- no iOS markers
    def test_web_safari_desktop(self) -> None:
        ua = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15"
        )
        assert detect_source(ua) == "web"

    # Unknown / empty
    def test_empty_user_agent(self) -> None:
        assert detect_source("") == "unknown"

    def test_unknown_user_agent(self) -> None:
        assert detect_source("curl/7.81.0") == "unknown"

    # Case-insensitivity spot-check
    def test_ios_case_insensitive(self) -> None:
        assert detect_source("GAMECHANGER/1234") == "ios"

    def test_web_case_insensitive(self) -> None:
        assert detect_source("CHROME/120.0") == "web"
