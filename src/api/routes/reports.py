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

    Returns the self-contained HTML file for serveable, non-expired reports.
    A report is serveable when its status is ``ready`` (a full report) or
    ``no_games`` (the E-235-03 minimal explanatory page -- a shareable honest
    "no completed games" outcome, NOT a 404). Returns 404 for unknown slugs,
    expired reports, and any other status (e.g. ``generating``/``failed``).
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

    if report["status"] not in ("ready", "no_games"):
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

    try:
        html_content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        # TOCTOU race (E-252-10): a concurrent unlink can remove the file between
        # the is_file() guard above and this read -- cleanup_expired_reports() runs
        # opportunistically at every `bb report generate` / `bb report cleanup`, and
        # the E-252-08 stuck-'generating' reaper unlinks orphan HTML on the same
        # lifecycle. Fold the read failure (FileNotFoundError and any other OSError)
        # into the SAME uniform 404 as the is_file()-false case -- never a 500 --
        # preserving the route's no-information-leakage contract (AC-1/AC-2), with a
        # matching operator-visible warning (AC-3).
        logger.warning(
            "Report file unreadable, likely concurrent unlink: %s (slug=%s): %s",
            file_path, slug, exc,
        )
        return Response(status_code=404)

    # Revocation-respecting cache policy (E-254-04): reports are ephemeral
    # (14-day expiry; cleanup_expired_reports() unlinks the HTML and nulls
    # report_path) and served on a no-auth public-by-slug route. A shared/CDN
    # cache holding this for an hour would keep serving a report after it was
    # expired or deleted server-side, undermining revocation. The HTML is a
    # self-contained frozen snapshot, so there is no shared-cache benefit that
    # justifies that risk -- `private, no-store` keeps every fetch authoritative.
    return HTMLResponse(
        content=html_content,
        headers={"Cache-Control": "private, no-store"},
    )
