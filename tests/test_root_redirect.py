"""Tests for root URL redirect (E-063-02; retargeted in E-238-05).

Verifies that GET / returns a 302 redirect to /admin/reports through the real
middleware (/ is an excluded path so auth middleware passes it through).
E-238-05 retargeted the root redirect off the removed /dashboard to the
reports flow (the live product surface).

Run with:
    pytest tests/test_root_redirect.py
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


def test_root_redirects_to_reports() -> None:
    """GET / returns 302 with Location: /admin/reports through the real middleware.

    / is excluded from auth checks so the route handler responds directly
    with a redirect to /admin/reports, which the middleware then handles
    normally on the next request (redirect to login if unauthenticated).
    E-238-05: retargeted off the removed /dashboard.
    """
    with TestClient(app, follow_redirects=False) as client:
        response = client.get("/")

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/reports"
    assert "/dashboard" not in response.headers["location"]
