"""Shared GameChanger domain and traffic-source utilities.

Pure Python -- no mitmproxy imports. This makes the module easy to unit test
without mocking mitmproxy internals, and importable in any context.
"""


def is_gamechanger_domain(host: str) -> bool:
    """Return True if *host* belongs to a GameChanger domain.

    Matches:
    - Exact ``gc.com`` and any subdomain (``api.gc.com``, ``app.gc.com``, etc.)
    - Exact ``gamechanger.com`` and any subdomain
    """
    host = host.lower()
    return (
        host == "gc.com"
        or host.endswith(".gc.com")
        or host == "gamechanger.com"
        or host.endswith(".gamechanger.com")
    )


def detect_source(user_agent: str) -> str:
    """Classify traffic source from a User-Agent string.

    Returns:
        ``"ios"``     -- iOS app (GameChanger app or iOS network stack)
        ``"web"``     -- Desktop/mobile web browser
        ``"unknown"`` -- No recognisable patterns found

    iOS patterns are checked first so that Safari-on-iOS (whose User-Agent
    contains both iOS markers and ``Safari/``) is correctly classified as
    ``"ios"`` rather than ``"web"``.

    iOS patterns include native app markers (``GameChanger/``, ``CFNetwork/``,
    ``Darwin/``) as well as iOS device platform strings (``iPhone``, ``iPad``)
    which appear in mobile browser UAs (e.g. Safari on iOS).

    All checks are case-insensitive.
    """
    ua = user_agent.lower()

    # iOS patterns -- checked BEFORE web patterns (Safari-on-iOS contains "Safari/")
    # Includes both native app markers and iOS device platform strings.
    ios_patterns = ("gamechanger/", "cfnetwork/", "darwin/", "iphone", "ipad")
    for pattern in ios_patterns:
        if pattern in ua:
            return "ios"

    # Web browser patterns
    web_patterns = ("chrome/", "firefox/", "safari/")
    for pattern in web_patterns:
        if pattern in ua:
            return "web"

    return "unknown"
