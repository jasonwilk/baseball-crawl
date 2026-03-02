"""Health check route: GET /health.

Returns HTTP 200 with ``{"status": "ok", "db": "connected"}`` when the
database is reachable, or HTTP 503 with ``{"status": "error", "db": "error"}``
when it is not.

The database call is executed via ``run_in_threadpool`` so the synchronous
SQLite operation does not block the async event loop.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from src.api import db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health() -> JSONResponse:
    """Return the health status of the API and its database connection.

    Returns:
        200 JSON ``{"status": "ok", "db": "connected"}`` when healthy.
        503 JSON ``{"status": "error", "db": "error"}`` when the database
        is unreachable or the schema is not initialized.
    """
    db_ok = await run_in_threadpool(db.check_connection)
    if db_ok:
        return JSONResponse(
            content={"status": "ok", "db": "connected"},
            status_code=200,
        )
    logger.warning("Health check: database not reachable")
    return JSONResponse(
        content={"status": "error", "db": "error"},
        status_code=503,
    )
