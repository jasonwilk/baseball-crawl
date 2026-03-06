"""
Dual header profiles for all HTTP requests to GameChanger.

Two profiles are available:

- **BROWSER_HEADERS** (web): Chrome 145 on macOS fingerprint, used by default.
  Matches the header set observed in web browser captures of web.gc.com.
  Source: Real GameChanger API curl commands captured 2026-02-28 through 2026-03-05.

- **MOBILE_HEADERS** (mobile): iOS Odyssey app fingerprint.
  Matches the header set observed in mitmproxy capture of the iOS GameChanger
  (Odyssey) app on 2026-03-05.

Select the profile via ``create_session(profile="web")`` or
``create_session(profile="mobile")`` in ``src.http.session``.

IMPORTANT: Neither profile includes credentials (gc-token, gc-device-id, etc.).
Auth headers are injected by the consuming client (e.g., GameChangerClient).
"""

from __future__ import annotations

BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-site": "same-site",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "DNT": "1",
    "Referer": "https://web.gc.com/",
}

MOBILE_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Odyssey/2026.7.0 (com.gc.teammanager; build:0; iOS 26.3.0) "
        "Alamofire/5.9.0"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US;q=1.0",
    "Accept-Encoding": "br;q=1.0, gzip;q=0.9, deflate;q=0.8",
    "gc-app-version": "2026.7.0.0",
    "x-gc-features": "lazy-sync",
    "x-gc-application-state": "foreground",
}
