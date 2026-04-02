"""Tests for derive_season_id_for_team() and ensure_season_row()."""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

from src.gamechanger.loaders import derive_season_id_for_team, ensure_season_row


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory database with programs and teams tables."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE programs (
            program_id   TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            program_type TEXT NOT NULL CHECK(program_type IN ('hs', 'usssa', 'legion')),
            org_name     TEXT,
            created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE teams (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            program_id      TEXT REFERENCES programs(program_id),
            membership_type TEXT NOT NULL DEFAULT 'member',
            public_id       TEXT,
            gc_uuid         TEXT,
            source          TEXT NOT NULL DEFAULT 'gamechanger',
            is_active       INTEGER NOT NULL DEFAULT 1,
            season_year     INTEGER,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE seasons (
            season_id   TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            season_type TEXT NOT NULL,
            year        INTEGER NOT NULL,
            program_id  TEXT REFERENCES programs(program_id),
            start_date  TEXT,
            end_date    TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    # Seed programs
    conn.executemany(
        "INSERT INTO programs (program_id, name, program_type) VALUES (?, ?, ?)",
        [
            ("lsb-hs", "Lincoln Standing Bear HS", "hs"),
            ("rebels-usssa", "Lincoln Rebels", "usssa"),
            ("lsb-legion", "LSB Legion", "legion"),
        ],
    )
    conn.commit()
    return conn


# ── derive_season_id_for_team ────────────────────────────────────────


class TestDeriveSeasonIdForTeam:
    """AC-1 and AC-5: derivation cases and error contract."""

    def test_usssa_team(self, db: sqlite3.Connection) -> None:
        db.execute(
            "INSERT INTO teams (name, program_id, season_year) VALUES ('Rebels 14U', 'rebels-usssa', 2025)"
        )
        team_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        season_id, season_year = derive_season_id_for_team(db, team_id)
        assert season_id == "2025-summer-usssa"
        assert season_year == 2025

    def test_hs_team(self, db: sqlite3.Connection) -> None:
        db.execute(
            "INSERT INTO teams (name, program_id, season_year) VALUES ('LSB Varsity', 'lsb-hs', 2026)"
        )
        team_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        season_id, season_year = derive_season_id_for_team(db, team_id)
        assert season_id == "2026-spring-hs"
        assert season_year == 2026

    def test_legion_team(self, db: sqlite3.Connection) -> None:
        db.execute(
            "INSERT INTO teams (name, program_id, season_year) VALUES ('LSB Legion', 'lsb-legion', 2025)"
        )
        team_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        season_id, season_year = derive_season_id_for_team(db, team_id)
        assert season_id == "2025-summer-legion"
        assert season_year == 2025

    def test_no_program(self, db: sqlite3.Connection) -> None:
        """Team with no program_id → year-only format."""
        db.execute(
            "INSERT INTO teams (name, program_id, season_year) VALUES ('Opponent', NULL, 2026)"
        )
        team_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        season_id, season_year = derive_season_id_for_team(db, team_id)
        assert season_id == "2026"
        assert season_year == 2026

    def test_null_season_year_with_program(self, db: sqlite3.Connection) -> None:
        """NULL season_year → falls back to current calendar year."""
        db.execute(
            "INSERT INTO teams (name, program_id, season_year) VALUES ('LSB JV', 'lsb-hs', NULL)"
        )
        team_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        with patch("src.gamechanger.loaders.datetime") as mock_dt:
            mock_dt.now.return_value.year = 2026
            season_id, season_year = derive_season_id_for_team(db, team_id)
        assert season_id == "2026-spring-hs"
        assert season_year is None

    def test_null_season_year_no_program(self, db: sqlite3.Connection) -> None:
        """Both NULL → current year, no suffix."""
        db.execute(
            "INSERT INTO teams (name, program_id, season_year) VALUES ('Unknown', NULL, NULL)"
        )
        team_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        with patch("src.gamechanger.loaders.datetime") as mock_dt:
            mock_dt.now.return_value.year = 2026
            season_id, season_year = derive_season_id_for_team(db, team_id)
        assert season_id == "2026"
        assert season_year is None

    def test_nonexistent_team_raises_value_error(self, db: sqlite3.Connection) -> None:
        """AC-5: nonexistent team_id → ValueError."""
        with pytest.raises(ValueError, match="team_id 9999 does not exist"):
            derive_season_id_for_team(db, 9999)

    def test_program_row_missing_but_program_id_set(self, db: sqlite3.Connection) -> None:
        """If program_id references a missing programs row, LEFT JOIN yields NULL program_type → year-only."""
        # Insert with FK enforcement off (in-memory DB doesn't enforce by default)
        db.execute(
            "INSERT INTO teams (name, program_id, season_year) VALUES ('Orphan', 'nonexistent', 2025)"
        )
        team_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        season_id, season_year = derive_season_id_for_team(db, team_id)
        assert season_id == "2025"
        assert season_year == 2025


# ── ensure_season_row ────────────────────────────────────────────────


class TestEnsureSeasonRow:
    """AC-2 and AC-7: ensure_season_row for both formats."""

    def test_year_suffix_format(self, db: sqlite3.Connection) -> None:
        ensure_season_row(db, "2025-summer-usssa")
        row = db.execute(
            "SELECT season_id, name, season_type, year FROM seasons WHERE season_id = ?",
            ("2025-summer-usssa",),
        ).fetchone()
        assert row == ("2025-summer-usssa", "2025-summer-usssa", "summer-usssa", 2025)

    def test_year_only_format(self, db: sqlite3.Connection) -> None:
        ensure_season_row(db, "2026")
        row = db.execute(
            "SELECT season_id, name, season_type, year FROM seasons WHERE season_id = ?",
            ("2026",),
        ).fetchone()
        assert row == ("2026", "2026", "default", 2026)

    def test_spring_hs_format(self, db: sqlite3.Connection) -> None:
        ensure_season_row(db, "2026-spring-hs")
        row = db.execute(
            "SELECT season_type, year FROM seasons WHERE season_id = '2026-spring-hs'"
        ).fetchone()
        assert row == ("spring-hs", 2026)

    def test_idempotent(self, db: sqlite3.Connection) -> None:
        """Calling twice does not raise or duplicate."""
        ensure_season_row(db, "2025-summer-usssa")
        ensure_season_row(db, "2025-summer-usssa")
        count = db.execute(
            "SELECT COUNT(*) FROM seasons WHERE season_id = '2025-summer-usssa'"
        ).fetchone()[0]
        assert count == 1

    def test_does_not_overwrite_existing(self, db: sqlite3.Connection) -> None:
        """INSERT OR IGNORE preserves the original row."""
        db.execute(
            "INSERT INTO seasons (season_id, name, season_type, year) VALUES ('2025-summer-usssa', 'Custom Name', 'custom', 2025)"
        )
        ensure_season_row(db, "2025-summer-usssa")
        row = db.execute(
            "SELECT name, season_type FROM seasons WHERE season_id = '2025-summer-usssa'"
        ).fetchone()
        assert row == ("Custom Name", "custom")
