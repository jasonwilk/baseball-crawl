"""Tests for GET /health endpoint (E-009-02 AC-2).

Uses a temporary SQLite database so tests do not depend on Docker or the dev
database.  The FastAPI app is tested via the ASGI test client.

Run with:
    pytest tests/test_api_health.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.api.main import app  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_initialized_db(tmp_path: Path) -> Path:
    """Create a migrated SQLite database in tmp_path and return its path.

    Runs the real apply_migrations logic so the _migrations table exists.

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path to the initialized database file.
    """
    db_path = tmp_path / "test_app.db"
    conn = sqlite3.connect(str(db_path))
    # Minimal setup: just the _migrations table is enough for the health check.
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS _migrations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            filename   TEXT    NOT NULL UNIQUE,
            applied_at TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        INSERT OR IGNORE INTO _migrations (filename) VALUES ('001_initial_schema.sql');
    """)
    conn.commit()
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Tests for GET /health (AC-2)."""

    def test_health_returns_200_with_connected_db(self, tmp_path: Path) -> None:
        """GET /health returns 200 and db=connected when database is accessible."""
        db_path = _make_initialized_db(tmp_path)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db_path)}):
            client = TestClient(app)
            response = client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["db"] == "connected"

    def test_health_returns_503_when_db_missing(self, tmp_path: Path) -> None:
        """GET /health returns 503 and db=error when database does not exist."""
        missing_path = tmp_path / "nonexistent" / "app.db"

        with patch.dict("os.environ", {"DATABASE_PATH": str(missing_path)}):
            client = TestClient(app)
            response = client.get("/health")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "error"
        assert body["db"] == "error"

    def test_health_returns_503_when_migrations_table_missing(
        self, tmp_path: Path
    ) -> None:
        """GET /health returns 503 when db exists but _migrations table is absent."""
        # Create a bare database with no tables.
        db_path = tmp_path / "bare.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()

        with patch.dict("os.environ", {"DATABASE_PATH": str(db_path)}):
            client = TestClient(app)
            response = client.get("/health")

        assert response.status_code == 503
        body = response.json()
        assert body["db"] == "error"

    def test_health_json_keys(self, tmp_path: Path) -> None:
        """GET /health response body contains exactly 'status' and 'db' keys."""
        db_path = _make_initialized_db(tmp_path)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db_path)}):
            client = TestClient(app)
            response = client.get("/health")

        body = response.json()
        assert set(body.keys()) == {"status", "db"}
