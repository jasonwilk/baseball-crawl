"""FastAPI application factory for baseball-crawl.

This module defines the FastAPI app instance and registers all route routers.
It is the entrypoint referenced by the Dockerfile:

    uvicorn src.api.main:app --host 0.0.0.0 --port 8000

Route structure (current):
    GET /health     -- Database and API health check (see routes/health.py)

Route structure (planned -- E-009-03):
    # Dashboard routes will be mounted here when E-009-03 is implemented.
    # Use a Jinja2 router or APIRouter with HTML responses.
    # Example: app.include_router(dashboard_router, prefix="")
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from src.api.routes.health import router as health_router

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
# Route registration
# ---------------------------------------------------------------------------

app.include_router(health_router)

# E-009-03: Dashboard routes will be registered here.
# When implementing E-009-03, add:
#   from src.api.routes.dashboard import router as dashboard_router
#   app.include_router(dashboard_router)
