"""Tests for src/db/backup.py.

# noqa: fixture-schema
Fixture-schema rationale (E-221-03):
The backup tests create an arbitrary throwaway SQLite database with a
single-column sentinel table (`test (id, value)`) to verify the backup
mechanism round-trips ANY SQLite file. The schema content is irrelevant --
what matters is that `backup_database` produces a byte-identical copy. Loading
the full production schema would add unnecessary setup cost and obscure the
minimal property under test.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.db.backup import backup_database


def _create_db(path: Path) -> None:
    """Create a minimal SQLite database at *path* with one table and one row."""
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'hello')")
        conn.commit()


def test_backup_produces_valid_sqlite_database(tmp_path: Path, monkeypatch) -> None:
    """backup_database() produces a backup that can be opened and queried."""
    db = tmp_path / "app.db"
    _create_db(db)

    backups_dir = tmp_path / "backups"
    monkeypatch.setattr("src.db.backup._BACKUPS_DIR", backups_dir)

    backup_path = backup_database(db_path=db)

    assert backup_path.exists(), "Backup file was not created"

    # Verify the backup is a valid SQLite file that can be queried.
    with sqlite3.connect(backup_path) as conn:
        row = conn.execute("SELECT value FROM test WHERE id = 1").fetchone()
    assert row is not None
    assert row[0] == "hello"


def test_backup_filename_pattern(tmp_path: Path, monkeypatch) -> None:
    """Backup file follows the app-<timestamp>.db naming convention."""
    db = tmp_path / "app.db"
    _create_db(db)

    backups_dir = tmp_path / "backups"
    monkeypatch.setattr("src.db.backup._BACKUPS_DIR", backups_dir)

    backup_path = backup_database(db_path=db)

    assert backup_path.name.startswith("app-")
    assert backup_path.suffix == ".db"


def test_backup_raises_if_database_missing(tmp_path: Path, monkeypatch) -> None:
    """backup_database() raises FileNotFoundError when the source db is absent."""
    missing = tmp_path / "nonexistent.db"
    monkeypatch.setattr("src.db.backup._BACKUPS_DIR", tmp_path / "backups")

    with pytest.raises(FileNotFoundError, match="Database not found"):
        backup_database(db_path=missing)


def test_backup_is_self_contained_without_wal_files(tmp_path: Path, monkeypatch) -> None:
    """Backup file is a standalone database not dependent on WAL/SHM sidecars."""
    db = tmp_path / "app.db"
    _create_db(db)

    # Enable WAL mode to exercise the WAL-safe code path.
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA journal_mode=WAL")

    backups_dir = tmp_path / "backups"
    monkeypatch.setattr("src.db.backup._BACKUPS_DIR", backups_dir)

    backup_path = backup_database(db_path=db)

    # Neither a WAL nor a SHM file should exist alongside the backup.
    assert not (backups_dir / f"{backup_path.stem}.db-wal").exists()
    assert not (backups_dir / f"{backup_path.stem}.db-shm").exists()

    # And the backup itself must be readable.
    with sqlite3.connect(backup_path) as conn:
        row = conn.execute("SELECT value FROM test WHERE id = 1").fetchone()
    assert row is not None and row[0] == "hello"


def test_backup_closes_connections_on_failure(tmp_path: Path, monkeypatch) -> None:
    """Connections are closed even when backup() raises an exception."""
    db = tmp_path / "app.db"
    _create_db(db)

    backups_dir = tmp_path / "backups"
    monkeypatch.setattr("src.db.backup._BACKUPS_DIR", backups_dir)

    mock_src = MagicMock(spec=sqlite3.Connection)
    mock_dst = MagicMock(spec=sqlite3.Connection)
    mock_src.backup.side_effect = sqlite3.OperationalError("disk full")

    call_count = 0
    original_connect = sqlite3.connect

    def fake_connect(path, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_src
        return mock_dst

    with patch("src.db.backup.sqlite3.connect", side_effect=fake_connect):
        with pytest.raises(sqlite3.OperationalError, match="disk full"):
            backup_database(db_path=db)

    mock_src.close.assert_called_once()
    mock_dst.close.assert_called_once()
