"""Public serving route for standalone scouting reports.

Serves generated HTML reports by slug without authentication.
Reports are checked for existence, readiness, and expiration before serving.

Route:
    GET /reports/<slug> -- serve report HTML (no auth required)
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Response
from fastapi.responses import HTMLResponse

from src.api.db import get_connection

logger = logging.getLogger(__name__)

router = APIRouter()

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


@router.get("/reports/{slug}")
async def serve_report(slug: str) -> Response:
    """Serve a generated scouting report by its slug.

    Returns the self-contained HTML file for ready, non-expired reports.
    Returns 404 for unknown slugs, expired reports, and non-ready statuses.
    The 404 response is identical regardless of the reason to avoid
    information leakage about report existence or expiration.
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT status, expires_at, report_path FROM reports WHERE slug = ?",
                (slug,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("Database error looking up report slug=%s", slug)
        return Response(status_code=404)

    if row is None:
        return Response(status_code=404)

    report = dict(row)

    if report["status"] != "ready":
        return Response(status_code=404)

    # Check expiration
    try:
        expires_at = datetime.fromisoformat(
            report["expires_at"].replace("Z", "+00:00")
        )
        if datetime.now(timezone.utc) > expires_at:
            return Response(status_code=404)
    except (ValueError, AttributeError):
        logger.warning("Invalid expires_at for slug=%s: %s", slug, report["expires_at"])
        return Response(status_code=404)

    # Read and serve the HTML file
    report_path = report["report_path"]
    if not report_path:
        return Response(status_code=404)

    file_path = _PROJECT_ROOT / "data" / report_path
    if not file_path.is_file():
        logger.warning("Report file not found: %s (slug=%s)", file_path, slug)
        return Response(status_code=404)

    html_content = file_path.read_text(encoding="utf-8")
    return HTMLResponse(
        content=html_content,
        headers={"Cache-Control": "public, max-age=3600"},
    )
