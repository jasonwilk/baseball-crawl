"""Tests for game chronological ordering with start_time tiebreaker.

Covers:
- AC-4: Games with NULL start_time sort after timed games on the same date.
- AC-5: Ordering behavior for same-day games with different start times.

Uses raw SQL to validate the ORDER BY convention independently of any
specific loader or query function, since the worktree pytest limitation
prevents testing the actual db.py/generator.py functions (they depend on
app infrastructure not available in-memory).
"""

from __future__ import annotations

import sqlite3

import pytest

from tests.conftest import load_real_schema


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory database with real schema plus minimal parent rows for FK integrity."""
    conn = sqlite3.connect(":memory:")
    load_real_schema(conn)
    # Seed the FK parents the games fixture needs: one season, two teams.
    # The 'lsb-hs' program row is seeded by the migration itself.
    conn.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) VALUES "
        "('s1', '2025 Spring HS', 'spring-hs', 2025)"
    )
    conn.executemany(
        "INSERT INTO teams (id, name, membership_type) VALUES (?, ?, ?)",
        [(1, "Home Test Team", "member"), (2, "Away Test Team", "tracked")],
    )
    # Same-day games: tournament doubleheader on 2025-04-26
    conn.executemany(
        """
        INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id,
                           home_score, away_score, status, start_time, timezone)
        VALUES (?, 's1', '2025-04-26', 1, 2, 5, 3, 'completed', ?, ?)
        """,
        [
            ("game-morning", "2025-04-26T09:00:00.000Z", "America/Chicago"),
            ("game-afternoon", "2025-04-26T14:00:00.000Z", "America/Chicago"),
            ("game-evening", "2025-04-26T19:00:00.000Z", "America/Chicago"),
            ("game-null-time", None, None),  # no start_time
        ],
    )
    # Different-day game for multi-day ordering
    conn.execute(
        """
        INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id,
                           home_score, away_score, status, start_time, timezone)
        VALUES ('game-next-day', 's1', '2025-04-27', 1, 2, 2, 1, 'completed',
                '2025-04-27T10:00:00.000Z', 'America/Chicago')
        """
    )
    conn.commit()
    return conn


class TestDescendingOrder:
    """DESC ordering: most recent game first, NULL start_time last within date."""

    def test_same_day_games_ordered_by_start_time_desc(self, db: sqlite3.Connection) -> None:
        rows = db.execute(
            """
            SELECT game_id FROM games
            WHERE game_date = '2025-04-26'
            ORDER BY game_date DESC, start_time DESC NULLS LAST
            """
        ).fetchall()
        ids = [r[0] for r in rows]
        assert ids == ["game-evening", "game-afternoon", "game-morning", "game-null-time"]

    def test_null_start_time_sorts_last_desc(self, db: sqlite3.Connection) -> None:
        rows = db.execute(
            """
            SELECT game_id FROM games
            WHERE game_date = '2025-04-26'
            ORDER BY game_date DESC, start_time DESC NULLS LAST
            """
        ).fetchall()
        ids = [r[0] for r in rows]
        assert ids[-1] == "game-null-time"

    def test_multi_day_desc_ordering(self, db: sqlite3.Connection) -> None:
        rows = db.execute(
            """
            SELECT game_id FROM games
            ORDER BY game_date DESC, start_time DESC NULLS LAST
            """
        ).fetchall()
        ids = [r[0] for r in rows]
        # 2025-04-27 first, then 2025-04-26 games in DESC start_time order
        assert ids[0] == "game-next-day"
        assert ids[1] == "game-evening"
        assert ids[-1] == "game-null-time"


class TestAscendingOrder:
    """ASC ordering: earliest game first, NULL start_time last within date."""

    def test_same_day_games_ordered_by_start_time_asc(self, db: sqlite3.Connection) -> None:
        rows = db.execute(
            """
            SELECT game_id FROM games
            WHERE game_date = '2025-04-26'
            ORDER BY game_date ASC, start_time ASC NULLS LAST
            """
        ).fetchall()
        ids = [r[0] for r in rows]
        assert ids == ["game-morning", "game-afternoon", "game-evening", "game-null-time"]

    def test_null_start_time_sorts_last_asc(self, db: sqlite3.Connection) -> None:
        rows = db.execute(
            """
            SELECT game_id FROM games
            WHERE game_date = '2025-04-26'
            ORDER BY game_date ASC, start_time ASC NULLS LAST
            """
        ).fetchall()
        ids = [r[0] for r in rows]
        assert ids[-1] == "game-null-time"

    def test_multi_day_asc_ordering(self, db: sqlite3.Connection) -> None:
        rows = db.execute(
            """
            SELECT game_id FROM games
            ORDER BY game_date ASC, start_time ASC NULLS LAST
            """
        ).fetchall()
        ids = [r[0] for r in rows]
        # 2025-04-26 games first in ASC start_time order, then 2025-04-27
        assert ids[0] == "game-morning"
        assert ids[-2] == "game-null-time"
        assert ids[-1] == "game-next-day"


class TestEdgeCases:
    """Edge cases for the ordering convention."""

    def test_all_null_start_times_stable(self, db: sqlite3.Connection) -> None:
        """All-NULL start_time games on the same date still return results."""
        db.execute("UPDATE games SET start_time = NULL")
        db.commit()
        rows = db.execute(
            """
            SELECT game_id FROM games
            WHERE game_date = '2025-04-26'
            ORDER BY game_date DESC, start_time DESC NULLS LAST
            """
        ).fetchall()
        assert len(rows) == 4

    def test_single_game_on_date(self, db: sqlite3.Connection) -> None:
        """Single game on a date works with the tiebreaker."""
        rows = db.execute(
            """
            SELECT game_id FROM games
            WHERE game_date = '2025-04-27'
            ORDER BY game_date ASC, start_time ASC NULLS LAST
            """
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "game-next-day"


class TestPythonSortOrderingParity:
    """Player profile uses Python sort -- verify it matches SQL ordering."""

    def test_python_sort_desc_with_start_time(self) -> None:
        """Python sort key (game_date, start_time or '') matches SQL DESC NULLS LAST."""
        rows = [
            {"game_id": "g1", "game_date": "2025-04-26", "start_time": "2025-04-26T09:00:00.000Z"},
            {"game_id": "g2", "game_date": "2025-04-26", "start_time": "2025-04-26T14:00:00.000Z"},
            {"game_id": "g3", "game_date": "2025-04-26", "start_time": None},
            {"game_id": "g4", "game_date": "2025-04-27", "start_time": "2025-04-27T10:00:00.000Z"},
        ]
        sorted_rows = sorted(
            rows,
            key=lambda r: (r["game_date"], r.get("start_time") or ""),
            reverse=True,
        )
        ids = [r["game_id"] for r in sorted_rows]
        # DESC: 2025-04-27 first, then 2025-04-26 afternoon, morning, null last
        assert ids == ["g4", "g2", "g1", "g3"]

    def test_python_sort_null_start_time_sorts_last_desc(self) -> None:
        """NULL start_time (mapped to '') sorts after all timed games in DESC."""
        rows = [
            {"game_id": "g1", "game_date": "2025-04-26", "start_time": "2025-04-26T09:00:00.000Z"},
            {"game_id": "g2", "game_date": "2025-04-26", "start_time": None},
        ]
        sorted_rows = sorted(
            rows,
            key=lambda r: (r["game_date"], r.get("start_time") or ""),
            reverse=True,
        )
        # In DESC, "" (None) sorts before actual timestamps (reversed),
        # meaning NULL comes last in the original ASC direction.
        # But in DESC with "", "2025..." > "" so timed game sorts first.
        assert sorted_rows[0]["game_id"] == "g1"
        assert sorted_rows[1]["game_id"] == "g2"
