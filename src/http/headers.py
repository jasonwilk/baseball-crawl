"""
Canonical browser header profile for all HTTP requests.

Source: Real GameChanger API curl command captured 2026-02-28.
Chrome 131 on macOS. Update this profile when GameChanger's
expected fingerprint changes or when the Chrome version is
significantly outdated (>2 major versions behind current stable).

To update: replace the header values below with those from a fresh
curl command captured from a real browser session. Keep the User-Agent
and sec-ch-ua version numbers in sync with each other.

IMPORTANT: Do NOT add credentials (Authorization, Cookie, etc.) here.
Auth headers are injected by the consuming client (e.g., GameChangerClient).
"""

BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-site": "same-site",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
}
