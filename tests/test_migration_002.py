# synthetic-test-data
"""Tests for migration 002 (E-229 v2 batter positioning schema).

Verifies the E-229 v2 schema introduced by ``002_batter_positioning.sql``:
- ``batter_positioning`` table: column set, types, PK shape, FK targets, no
  retired E-228 v1 categorical columns.
- ``team_position_aggregate`` table: column set, types, PK shape, FK targets.
- CHECK constraints on ``zone_id`` and ``position``.
- FK enforcement under ``PRAGMA foreign_keys=ON``.
- Runner-level idempotency of the migration.

Tests use ``run_migrations`` against a temporary SQLite database; no Docker
required.

Run with::

    python -m pytest tests/test_migration_002.py -v
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from migrations.apply_migrations import run_migrations  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def migrated_db(tmp_path: Path) -> sqlite3.Connection:
    """Apply all migrations (001 + 002) to a fresh temp DB.

    FK enforcement is enabled on the returned connection.
    """
    db_path = tmp_path / "test_e229_pos.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    return conn


@pytest.fixture()
def seeded_db(migrated_db: sqlite3.Connection) -> sqlite3.Connection:
    """Migrated DB pre-seeded with one team, one season, one player.

    Provides a valid FK target set so positive-path inserts on the positioning
    tables can succeed without spurious IntegrityErrors.
    """
    migrated_db.execute(
        "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
        ("Lincoln Varsity", "member"),
    )
    migrated_db.execute(
        "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
        ("Opponent Tracked", "tracked"),
    )
    migrated_db.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
        ("2026-spring-hs", "Spring 2026 HS", "spring-hs", 2026),
    )
    migrated_db.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        ("player-1", "Test", "Batter"),
    )
    migrated_db.commit()
    return migrated_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _table_info(conn: sqlite3.Connection, table: str) -> dict[str, dict]:
    """Return ``{column_name: {type, notnull, default, pk}}`` for ``table``."""
    cursor = conn.execute(f"PRAGMA table_info({table});")  # noqa: S608
    return {
        row[1]: {
            "type": row[2].upper(),
            "notnull": row[3],
            "default": row[4],
            "pk": row[5],
        }
        for row in cursor.fetchall()
    }


def _foreign_key_list(conn: sqlite3.Connection, table: str) -> list[dict]:
    """Return list of ``{from, table, to}`` FK descriptors for ``table``."""
    cursor = conn.execute(f"PRAGMA foreign_key_list({table});")  # noqa: S608
    # PRAGMA foreign_key_list columns: id, seq, table, from, to, on_update,
    # on_delete, match
    return [
        {"from": row[3], "table": row[2], "to": row[4]}
        for row in cursor.fetchall()
    ]


def _get_member_team_id(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT id FROM teams WHERE membership_type='member' LIMIT 1;"
    ).fetchone()
    assert row is not None
    return row[0]


def _get_tracked_team_id(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT id FROM teams WHERE membership_type='tracked' LIMIT 1;"
    ).fetchone()
    assert row is not None
    return row[0]


# ---------------------------------------------------------------------------
# batter_positioning column / PK shape
# ---------------------------------------------------------------------------


class TestBatterPositioningShape:
    """Column set, types, PK shape on ``batter_positioning``."""

    EXPECTED_COLUMNS = {
        "player_id",
        "team_id",
        "season_id",
        "perspective_team_id",
        "position",
        "direction_deviation",
        "depth_deviation",
        "zone_id",
        "is_thin",
        "bip_count",
        "hr_count",
        "computed_at",
    }

    # E-228 v1 categorical columns retired by E-229 (epic TN-13).
    RETIRED_COLUMNS = {
        "call_state",
        "team_state_call",
        "direction_shade",
        "depth_shade",
        "zone_concentration",
    }

    def test_table_exists(self, migrated_db: sqlite3.Connection) -> None:
        cursor = migrated_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='batter_positioning';"
        )
        assert cursor.fetchone() is not None

    def test_expected_columns_present(self, migrated_db: sqlite3.Connection) -> None:
        cols = _table_info(migrated_db, "batter_positioning")
        missing = self.EXPECTED_COLUMNS - set(cols)
        assert not missing, f"Missing columns: {missing}"

    def test_retired_columns_absent(self, migrated_db: sqlite3.Connection) -> None:
        """AC-6: no E-228 v1 categorical column survives the rewrite."""
        cols = _table_info(migrated_db, "batter_positioning")
        present_retired = self.RETIRED_COLUMNS & set(cols)
        assert not present_retired, (
            f"Retired E-228 v1 column(s) still present on batter_positioning: "
            f"{present_retired}"
        )

    def test_no_extra_columns(self, migrated_db: sqlite3.Connection) -> None:
        cols = _table_info(migrated_db, "batter_positioning")
        unexpected = set(cols) - self.EXPECTED_COLUMNS
        assert not unexpected, f"Unexpected columns on batter_positioning: {unexpected}"

    def test_column_types(self, migrated_db: sqlite3.Connection) -> None:
        cols = _table_info(migrated_db, "batter_positioning")
        assert cols["player_id"]["type"] == "TEXT"
        assert cols["team_id"]["type"] == "INTEGER"
        assert cols["season_id"]["type"] == "TEXT"
        assert cols["perspective_team_id"]["type"] == "INTEGER"
        assert cols["position"]["type"] == "TEXT"
        assert cols["direction_deviation"]["type"] == "INTEGER"
        assert cols["depth_deviation"]["type"] == "INTEGER"
        assert cols["zone_id"]["type"] == "TEXT"
        assert cols["is_thin"]["type"] == "INTEGER"
        assert cols["bip_count"]["type"] == "INTEGER"
        assert cols["hr_count"]["type"] == "INTEGER"
        assert cols["computed_at"]["type"] == "TEXT"

    def test_not_null_columns(self, migrated_db: sqlite3.Connection) -> None:
        cols = _table_info(migrated_db, "batter_positioning")
        # FK columns + position + bip_count + flags + computed_at are NOT NULL.
        for required in (
            "player_id",
            "team_id",
            "season_id",
            "perspective_team_id",
            "position",
            "is_thin",
            "bip_count",
            "hr_count",
            "computed_at",
        ):
            assert cols[required]["notnull"] == 1, (
                f"{required} should be NOT NULL"
            )
        # Deviation and zone columns are nullable.
        for nullable in ("direction_deviation", "depth_deviation", "zone_id"):
            assert cols[nullable]["notnull"] == 0, (
                f"{nullable} should be nullable"
            )

    def test_primary_key_shape(self, migrated_db: sqlite3.Connection) -> None:
        """AC-4: PK is (player_id, team_id, season_id, perspective_team_id, position)."""
        cursor = migrated_db.execute("PRAGMA table_info(batter_positioning);")
        # The pk field is the 1-based ordinal of each column within the PK
        # (0 means not in PK). Sort by pk to recover the PK column order.
        pk_cols = sorted(
            ((row[1], row[5]) for row in cursor.fetchall() if row[5] > 0),
            key=lambda x: x[1],
        )
        pk_names = [name for name, _ in pk_cols]
        assert pk_names == [
            "player_id",
            "team_id",
            "season_id",
            "perspective_team_id",
            "position",
        ]


class TestBatterPositioningForeignKeys:
    """AC-5: FK columns carry REFERENCES clauses."""

    def test_player_id_references_players(self, migrated_db: sqlite3.Connection) -> None:
        fks = _foreign_key_list(migrated_db, "batter_positioning")
        match = [fk for fk in fks if fk["from"] == "player_id"]
        assert match, "player_id has no FK"
        assert match[0]["table"] == "players"
        assert match[0]["to"] == "player_id"

    def test_team_id_references_teams(self, migrated_db: sqlite3.Connection) -> None:
        fks = _foreign_key_list(migrated_db, "batter_positioning")
        match = [fk for fk in fks if fk["from"] == "team_id"]
        assert match, "team_id has no FK"
        assert match[0]["table"] == "teams"
        assert match[0]["to"] == "id"

    def test_season_id_references_seasons(self, migrated_db: sqlite3.Connection) -> None:
        fks = _foreign_key_list(migrated_db, "batter_positioning")
        match = [fk for fk in fks if fk["from"] == "season_id"]
        assert match, "season_id has no FK"
        assert match[0]["table"] == "seasons"
        assert match[0]["to"] == "season_id"

    def test_perspective_team_id_references_teams(
        self, migrated_db: sqlite3.Connection
    ) -> None:
        fks = _foreign_key_list(migrated_db, "batter_positioning")
        match = [fk for fk in fks if fk["from"] == "perspective_team_id"]
        assert match, "perspective_team_id has no FK"
        assert match[0]["table"] == "teams"
        assert match[0]["to"] == "id"


class TestBatterPositioningIndex:
    """AC-4: lookup index on (team_id, season_id, perspective_team_id)."""

    def test_lookup_index_exists(self, migrated_db: sqlite3.Connection) -> None:
        cursor = migrated_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='idx_batter_positioning_lookup';"
        )
        assert cursor.fetchone() is not None

    def test_lookup_index_column_order(self, migrated_db: sqlite3.Connection) -> None:
        cursor = migrated_db.execute(
            "PRAGMA index_info(idx_batter_positioning_lookup);"
        )
        # index_info columns: seqno, cid, name -- sort by seqno.
        cols = [row[2] for row in sorted(cursor.fetchall(), key=lambda r: r[0])]
        assert cols == ["team_id", "season_id", "perspective_team_id"]


# ---------------------------------------------------------------------------
# team_position_aggregate column / PK shape
# ---------------------------------------------------------------------------


class TestTeamPositionAggregateShape:
    """AC-3: column set, types, PK shape on ``team_position_aggregate``."""

    EXPECTED_COLUMNS = {
        "team_id",
        "season_id",
        "perspective_team_id",
        "position",
        "star_x",
        "star_y",
        "bip_count",
        "is_low_confidence",
        "computed_at",
    }

    def test_table_exists(self, migrated_db: sqlite3.Connection) -> None:
        cursor = migrated_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='team_position_aggregate';"
        )
        assert cursor.fetchone() is not None

    def test_expected_columns_present(self, migrated_db: sqlite3.Connection) -> None:
        cols = _table_info(migrated_db, "team_position_aggregate")
        missing = self.EXPECTED_COLUMNS - set(cols)
        assert not missing, f"Missing columns: {missing}"

    def test_no_extra_columns(self, migrated_db: sqlite3.Connection) -> None:
        cols = _table_info(migrated_db, "team_position_aggregate")
        unexpected = set(cols) - self.EXPECTED_COLUMNS
        assert not unexpected, (
            f"Unexpected columns on team_position_aggregate: {unexpected}"
        )

    def test_column_types(self, migrated_db: sqlite3.Connection) -> None:
        cols = _table_info(migrated_db, "team_position_aggregate")
        assert cols["team_id"]["type"] == "INTEGER"
        assert cols["season_id"]["type"] == "TEXT"
        assert cols["perspective_team_id"]["type"] == "INTEGER"
        assert cols["position"]["type"] == "TEXT"
        assert cols["star_x"]["type"] == "REAL"
        assert cols["star_y"]["type"] == "REAL"
        assert cols["bip_count"]["type"] == "INTEGER"
        assert cols["is_low_confidence"]["type"] == "INTEGER"
        assert cols["computed_at"]["type"] == "TEXT"

    def test_not_null_columns(self, migrated_db: sqlite3.Connection) -> None:
        cols = _table_info(migrated_db, "team_position_aggregate")
        for required in (
            "team_id",
            "season_id",
            "perspective_team_id",
            "position",
            "star_x",
            "star_y",
            "bip_count",
            "is_low_confidence",
            "computed_at",
        ):
            assert cols[required]["notnull"] == 1, (
                f"{required} should be NOT NULL"
            )

    def test_primary_key_shape(self, migrated_db: sqlite3.Connection) -> None:
        """PK is (team_id, season_id, perspective_team_id, position)."""
        cursor = migrated_db.execute("PRAGMA table_info(team_position_aggregate);")
        pk_cols = sorted(
            ((row[1], row[5]) for row in cursor.fetchall() if row[5] > 0),
            key=lambda x: x[1],
        )
        pk_names = [name for name, _ in pk_cols]
        assert pk_names == ["team_id", "season_id", "perspective_team_id", "position"]


class TestTeamPositionAggregateForeignKeys:
    """AC-5: FK columns on ``team_position_aggregate`` carry REFERENCES."""

    def test_team_id_references_teams(self, migrated_db: sqlite3.Connection) -> None:
        fks = _foreign_key_list(migrated_db, "team_position_aggregate")
        match = [fk for fk in fks if fk["from"] == "team_id"]
        assert match, "team_id has no FK"
        assert match[0]["table"] == "teams"
        assert match[0]["to"] == "id"

    def test_season_id_references_seasons(self, migrated_db: sqlite3.Connection) -> None:
        fks = _foreign_key_list(migrated_db, "team_position_aggregate")
        match = [fk for fk in fks if fk["from"] == "season_id"]
        assert match, "season_id has no FK"
        assert match[0]["table"] == "seasons"
        assert match[0]["to"] == "season_id"

    def test_perspective_team_id_references_teams(
        self, migrated_db: sqlite3.Connection
    ) -> None:
        fks = _foreign_key_list(migrated_db, "team_position_aggregate")
        match = [fk for fk in fks if fk["from"] == "perspective_team_id"]
        assert match, "perspective_team_id has no FK"
        assert match[0]["table"] == "teams"
        assert match[0]["to"] == "id"


# ---------------------------------------------------------------------------
# CHECK constraint enforcement
# ---------------------------------------------------------------------------


class TestCheckConstraints:
    """AC-8: CHECK constraints reject invalid values."""

    def test_zone_id_rejects_invalid_letter(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        """zone_id must be NULL or one of A..H."""
        member_id = _get_member_team_id(seeded_db)
        tracked_id = _get_tracked_team_id(seeded_db)
        with pytest.raises(sqlite3.IntegrityError):
            seeded_db.execute(
                """
                INSERT INTO batter_positioning (
                    player_id, team_id, season_id, perspective_team_id,
                    position, zone_id, bip_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                ("player-1", tracked_id, "2026-spring-hs", member_id, "LF", "Z", 10),
            )
            seeded_db.commit()

    def test_zone_id_accepts_null(self, seeded_db: sqlite3.Connection) -> None:
        """NULL zone_id is allowed."""
        member_id = _get_member_team_id(seeded_db)
        tracked_id = _get_tracked_team_id(seeded_db)
        seeded_db.execute(
            """
            INSERT INTO batter_positioning (
                player_id, team_id, season_id, perspective_team_id,
                position, zone_id, bip_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            ("player-1", tracked_id, "2026-spring-hs", member_id, "LF", None, 10),
        )
        seeded_db.commit()
        cursor = seeded_db.execute(
            "SELECT COUNT(*) FROM batter_positioning WHERE zone_id IS NULL;"
        )
        assert cursor.fetchone()[0] == 1

    def test_zone_id_accepts_valid_letters(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        """A..H are all accepted on the positive insert path."""
        member_id = _get_member_team_id(seeded_db)
        tracked_id = _get_tracked_team_id(seeded_db)
        # 8 zones, 6 positions: rotate position twice to cover all 8 zones,
        # and use a unique player_id per insert so the PK
        # (player_id, team_id, season_id, perspective_team_id, position) is
        # distinct on every row (positions repeat for zones G/H).
        positions = ("LF", "CF", "RF", "3B", "SS", "2B")
        rotated = positions + positions[:2]  # 8 positions matching 8 zones
        for zone_letter, position in zip("ABCDEFGH", rotated, strict=True):
            player_id = f"player-zone-{zone_letter}"
            seeded_db.execute(
                "INSERT INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
                (player_id, "Zone", zone_letter),
            )
            seeded_db.execute(
                """
                INSERT INTO batter_positioning (
                    player_id, team_id, season_id, perspective_team_id,
                    position, zone_id, bip_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    player_id,
                    tracked_id,
                    "2026-spring-hs",
                    member_id,
                    position,
                    zone_letter,
                    10,
                ),
            )
        seeded_db.commit()
        cursor = seeded_db.execute(
            "SELECT zone_id FROM batter_positioning ORDER BY zone_id;"
        )
        assert [row[0] for row in cursor.fetchall()] == list("ABCDEFGH")

    def test_batter_positioning_position_rejects_invalid(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        """position must be one of the six covered fielding positions."""
        member_id = _get_member_team_id(seeded_db)
        tracked_id = _get_tracked_team_id(seeded_db)
        with pytest.raises(sqlite3.IntegrityError):
            seeded_db.execute(
                """
                INSERT INTO batter_positioning (
                    player_id, team_id, season_id, perspective_team_id,
                    position, bip_count
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                ("player-1", tracked_id, "2026-spring-hs", member_id, "P", 10),
            )
            seeded_db.commit()

    def test_team_position_aggregate_position_rejects_invalid(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        """team_position_aggregate.position carries the same CHECK constraint."""
        member_id = _get_member_team_id(seeded_db)
        tracked_id = _get_tracked_team_id(seeded_db)
        with pytest.raises(sqlite3.IntegrityError):
            seeded_db.execute(
                """
                INSERT INTO team_position_aggregate (
                    team_id, season_id, perspective_team_id,
                    position, star_x, star_y, bip_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (tracked_id, "2026-spring-hs", member_id, "1B", 0.0, 0.0, 100),
            )
            seeded_db.commit()


# ---------------------------------------------------------------------------
# Foreign-key enforcement
# ---------------------------------------------------------------------------


class TestForeignKeyEnforcement:
    """AC-5/AC-8: FKs are enforced when PRAGMA foreign_keys=ON."""

    def test_batter_positioning_rejects_nonexistent_player(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        member_id = _get_member_team_id(seeded_db)
        tracked_id = _get_tracked_team_id(seeded_db)
        with pytest.raises(sqlite3.IntegrityError):
            seeded_db.execute(
                """
                INSERT INTO batter_positioning (
                    player_id, team_id, season_id, perspective_team_id,
                    position, bip_count
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                ("nonexistent-player", tracked_id, "2026-spring-hs", member_id, "LF", 10),
            )
            seeded_db.commit()

    def test_batter_positioning_rejects_nonexistent_team(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        member_id = _get_member_team_id(seeded_db)
        with pytest.raises(sqlite3.IntegrityError):
            seeded_db.execute(
                """
                INSERT INTO batter_positioning (
                    player_id, team_id, season_id, perspective_team_id,
                    position, bip_count
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                ("player-1", 999999, "2026-spring-hs", member_id, "LF", 10),
            )
            seeded_db.commit()

    def test_batter_positioning_rejects_nonexistent_season(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        member_id = _get_member_team_id(seeded_db)
        tracked_id = _get_tracked_team_id(seeded_db)
        with pytest.raises(sqlite3.IntegrityError):
            seeded_db.execute(
                """
                INSERT INTO batter_positioning (
                    player_id, team_id, season_id, perspective_team_id,
                    position, bip_count
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                ("player-1", tracked_id, "no-such-season", member_id, "LF", 10),
            )
            seeded_db.commit()

    def test_batter_positioning_rejects_nonexistent_perspective_team(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        tracked_id = _get_tracked_team_id(seeded_db)
        with pytest.raises(sqlite3.IntegrityError):
            seeded_db.execute(
                """
                INSERT INTO batter_positioning (
                    player_id, team_id, season_id, perspective_team_id,
                    position, bip_count
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                ("player-1", tracked_id, "2026-spring-hs", 999999, "LF", 10),
            )
            seeded_db.commit()

    def test_team_position_aggregate_rejects_nonexistent_team(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        member_id = _get_member_team_id(seeded_db)
        with pytest.raises(sqlite3.IntegrityError):
            seeded_db.execute(
                """
                INSERT INTO team_position_aggregate (
                    team_id, season_id, perspective_team_id,
                    position, star_x, star_y, bip_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (999999, "2026-spring-hs", member_id, "LF", 0.0, 0.0, 50),
            )
            seeded_db.commit()

    def test_team_position_aggregate_rejects_nonexistent_season(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        member_id = _get_member_team_id(seeded_db)
        tracked_id = _get_tracked_team_id(seeded_db)
        with pytest.raises(sqlite3.IntegrityError):
            seeded_db.execute(
                """
                INSERT INTO team_position_aggregate (
                    team_id, season_id, perspective_team_id,
                    position, star_x, star_y, bip_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (tracked_id, "no-such-season", member_id, "LF", 0.0, 0.0, 50),
            )
            seeded_db.commit()

    def test_team_position_aggregate_rejects_nonexistent_perspective_team(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        tracked_id = _get_tracked_team_id(seeded_db)
        with pytest.raises(sqlite3.IntegrityError):
            seeded_db.execute(
                """
                INSERT INTO team_position_aggregate (
                    team_id, season_id, perspective_team_id,
                    position, star_x, star_y, bip_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (tracked_id, "2026-spring-hs", 999999, "LF", 0.0, 0.0, 50),
            )
            seeded_db.commit()

    def test_team_position_aggregate_accepts_valid_row(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        member_id = _get_member_team_id(seeded_db)
        tracked_id = _get_tracked_team_id(seeded_db)
        seeded_db.execute(
            """
            INSERT INTO team_position_aggregate (
                team_id, season_id, perspective_team_id,
                position, star_x, star_y, bip_count, is_low_confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (tracked_id, "2026-spring-hs", member_id, "SS", 160.0, 240.0, 75, 0),
        )
        seeded_db.commit()
        cursor = seeded_db.execute("SELECT COUNT(*) FROM team_position_aggregate;")
        assert cursor.fetchone()[0] == 1


# ---------------------------------------------------------------------------
# Migration runner behavior
# ---------------------------------------------------------------------------


class TestMigrationRunnerBehavior:
    """AC-9: migration is runner-level idempotent and recorded."""

    def test_002_recorded_in_tracking_table(
        self, migrated_db: sqlite3.Connection
    ) -> None:
        cursor = migrated_db.execute(
            "SELECT filename FROM _migrations "
            "WHERE filename='002_batter_positioning.sql';"
        )
        assert cursor.fetchone() is not None

    def test_idempotent_second_run(self, tmp_path: Path) -> None:
        """Running run_migrations twice does not duplicate _migrations rows
        and does not error on the existing tables."""
        db_path = tmp_path / "idempotent_002.db"

        run_migrations(db_path=db_path)
        conn = sqlite3.connect(str(db_path))
        count_first = conn.execute(
            "SELECT COUNT(*) FROM _migrations;"
        ).fetchone()[0]
        conn.close()

        run_migrations(db_path=db_path)
        conn = sqlite3.connect(str(db_path))
        count_second = conn.execute(
            "SELECT COUNT(*) FROM _migrations;"
        ).fetchone()[0]
        conn.close()

        assert count_first == count_second
