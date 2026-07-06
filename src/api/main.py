"""FastAPI application factory for baseball-crawl.

This module defines the FastAPI app instance and registers all route routers.
It is the entrypoint referenced by the Dockerfile:

    uvicorn src.api.main:app --host 0.0.0.0 --port 8000

Route structure (current):
    GET  /               -- Root redirect to /admin/reports
    GET  /health         -- Database and API health check (see routes/health.py)
    GET  /auth/login     -- Login page (see routes/auth.py)
    POST /auth/login     -- Magic link issuance (see routes/auth.py)
    GET  /auth/verify    -- Magic link verification (see routes/auth.py)
    POST /auth/logout    -- Session logout (see routes/auth.py)
    GET  /admin/users    -- Admin user list (see routes/reports_admin.py)
    POST /admin/users    -- Create user (see routes/reports_admin.py)
    GET  /admin/reports  -- Reports management (see routes/reports_admin.py)
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.api.auth import SessionMiddleware
from src.api.csrf import CSRFMiddleware
from src.api.routes.auth import router as auth_router
from src.api.routes.health import router as health_router
from src.api.routes.reports import router as reports_router
from src.api.routes.reports_admin import router as reports_admin_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown events.

    Args:
        application: The FastAPI application instance.

    Yields:
        None -- control passes to the running application.
    """
    app_env = os.environ.get("APP_ENV", "development")
    logger.info("baseball-crawl API starting (env=%s)", app_env)

    # E-252-08: reap reports stuck at status='generating' from a generation process
    # that died mid-run (SIGKILL, a prior container restart). Running this at
    # startup means a stuck row is cleared on the next app boot with no operator
    # action. Isolated so a reaper failure never blocks app startup. (The reaper
    # also rides the opportunistic cleanup_expired_reports path at report-generation
    # time; startup covers the restart case.)
    try:
        from src.reports.generator import reap_stale_generating_reports

        reaped = reap_stale_generating_reports()
        if reaped.reaped:
            logger.info(
                "Startup reaper: %d stale 'generating' report(s) marked failed",
                reaped.reaped,
            )
    except Exception:  # noqa: BLE001 -- startup reaping is best-effort
        logger.warning("Startup stale-'generating' reaper failed; continuing", exc_info=True)

    yield
    logger.info("baseball-crawl API shutting down")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="baseball-crawl API",
    description=(
        "High school baseball coaching analytics platform. "
        "Provides access to GameChanger game data, player stats, and scouting reports."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware (registered before route handlers)
# ---------------------------------------------------------------------------

app.add_middleware(SessionMiddleware)
app.add_middleware(CSRFMiddleware)

# ---------------------------------------------------------------------------
# Static files and templates
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_STATIC_DIR = _PROJECT_ROOT / "src" / "api" / "static"
_TEMPLATES_DIR = _PROJECT_ROOT / "src" / "api" / "templates"

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> HTMLResponse:
    """Render the 404 error page."""
    return _templates.TemplateResponse(
        request, "errors/404.html", status_code=404
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception) -> HTMLResponse:
    """Render the 500 error page."""
    return _templates.TemplateResponse(
        request, "errors/500.html", status_code=500
    )


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


@app.get("/")
async def root_redirect() -> RedirectResponse:
    """Redirect root URL to the reports page.

    The reports flow is the live product surface (the dashboard surface was
    removed in E-239).  The auth middleware handles the unauthenticated case
    by redirecting to /auth/login.
    """
    return RedirectResponse(url="/admin/reports", status_code=302)


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(reports_admin_router)
app.include_router(reports_router)
