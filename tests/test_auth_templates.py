"""Tests for auth page template and error pages (E-063-03).

Verifies:
- AC-7: GET /auth/login response body does not contain operator top-nav markup
  (the Admin link that base.html renders). Confirms login uses base_auth.html.

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

# Operator top-nav chrome present in base.html but absent from base_auth.html.
# The login page must extend base_auth.html (the bare auth chrome), so the Admin
# link that base.html renders must NOT appear in the /auth/login body.
#
# NOTE: the former bottom-nav markers (href="/dashboard/pitching" etc.) were
# removed from base.html in E-239-02, so they can no longer distinguish the two
# templates -- asserting their absence would be vacuous.  The Admin link is the
# surviving base.html-only marker.
_BASE_HTML_ONLY_MARKERS = [
    'href="/admin/reports"',
    ">Admin<",
]


def test_login_page_has_no_operator_nav() -> None:
    """GET /auth/login extends base_auth.html, so it lacks base.html's Admin nav link."""
    with TestClient(app, follow_redirects=False) as client:
        response = client.get("/auth/login")

    assert response.status_code == 200
    body = response.text
    for marker in _BASE_HTML_ONLY_MARKERS:
        assert marker not in body, f"base.html-only nav marker found in login page: {marker!r}"
