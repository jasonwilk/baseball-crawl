"""Tests for auth page template and error pages (E-063-03).

Verifies:
- AC-7: GET /auth/login response body does not contain bottom nav markup.

Run with:
    pytest tests/test_auth_templates.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.api.main import app  # noqa: E402

# Bottom nav link text present in base.html but absent from base_auth.html.
# We check for the href values that only appear in the bottom nav.
_BOTTOM_NAV_MARKERS = [
    'href="/dashboard/pitching"',
    'href="/dashboard/games"',
    'href="/dashboard/opponents"',
]


def test_login_page_has_no_bottom_nav() -> None:
    """GET /auth/login response body does not contain bottom nav link markup."""
    with TestClient(app, follow_redirects=False) as client:
        response = client.get("/auth/login")

    assert response.status_code == 200
    body = response.text
    for marker in _BOTTOM_NAV_MARKERS:
        assert marker not in body, f"Bottom nav marker found in login page: {marker!r}"
