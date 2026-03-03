"""FastAPI application factory for baseball-crawl.

This module defines the FastAPI app instance and registers all route routers.
It is the entrypoint referenced by the Dockerfile:

    uvicorn src.api.main:app --host 0.0.0.0 --port 8000

Route structure (current):
    GET /health      -- Database and API health check (see routes/health.py)
    GET /dashboard   -- Team batting stats dashboard (see routes/dashboard.py)
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.routes.health import router as health_router
from src.api.routes.dashboard import router as dashboard_router

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
    yield
    logger.info("baseball-crawl API shutting down")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="baseball-crawl API",
    description=(
        "Coaching analytics platform for Lincoln Standing Bear High School. "
        "Provides access to GameChanger game data, player stats, and scouting reports."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Static files and templates
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_STATIC_DIR = _PROJECT_ROOT / "src" / "api" / "static"
_TEMPLATES_DIR = _PROJECT_ROOT / "src" / "api" / "templates"

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

app.include_router(health_router)
app.include_router(dashboard_router)
