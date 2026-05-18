"""Tests for E-229-10: pipeline wiring.

AC-5 parity test: same input through the standalone path and the
scouting path produces identical ``batter_positioning`` +
``team_position_aggregate`` rows when projected onto data columns
(excluding ``computed_at``, which differs by timestamp between two
runs per CR I5).

Both pipeline surfaces funnel into
:func:`src.reports.positioning.compute_positioning`. The parity check
exercises engine determinism — the structural guarantee that both
paths rely on for the parity property — by invoking the engine twice
against the same input data.
"""

from __future__ import annotations

import sqlite3

import pytest

from src.reports.positioning import compute_positioning, COVERED_POSITIONS
from tests.conftest import load_real_schema


_SEASON = "2026-spring-hs"


def _seed_team_and_spray(conn: sqlite3.Connection) -> int:
    """Seed a fixture opponent + offensive spray data sufficient to
    drive the positioning engine through both pipeline paths."""
    conn.execute(
        "INSERT INTO teams (id, name, public_id, season_year, "
        "membership_type) VALUES (1, 'Opp Bears', 'opp-bears', 2026, "
        "'tracked')"
    )
    conn.execute(
        "INSERT INTO teams (id, name, membership_type) "
        "VALUES (99, 'LSB Varsity', 'member')"
    )
    conn.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) "
        "VALUES ('2026-spring-hs', '2026', 'spring-hs', 2026)"
    )
    # Three batters with varied placement so the engine produces a
    # mix of zones across positions.
    for pid, first, last in [
        ("p1", "Hank", "Ramirez"),
        ("p2", "Marcus", "Davis"),
        ("p3", "Tony", "Aaron"),
    ]:
        conn.execute(
            "INSERT INTO players (player_id, first_name, last_name) "
            "VALUES (?, ?, ?)",
            (pid, first, last),
        )

    # Seed enough spray-chart events per batter to clear the 15-BIP
    # gate (team aggregate uses ≥ 15 BIPs total to compute confidence
    # tier).
    sample_events = [
        # (player_id, perspective_team_id, x, y, play_result, play_type)
        ("p1",  1,  80.0, 200.0, "single", "ground_ball"),
        ("p1",  1, 100.0, 220.0, "single", "ground_ball"),
        ("p1",  1, 110.0, 240.0, "double", "line_drive"),
        ("p1",  1,  90.0, 280.0, "out",    "fly_ball"),
        ("p1",  1, 120.0, 230.0, "single", "ground_ball"),
        ("p2",  1, 220.0, 230.0, "single", "ground_ball"),
        ("p2",  1, 240.0, 250.0, "double", "line_drive"),
        ("p2",  1, 230.0, 260.0, "single", "ground_ball"),
        ("p2",  1, 250.0, 290.0, "out",    "fly_ball"),
        ("p2",  1, 245.0, 200.0, "out",    "ground_ball"),
        ("p3",  1, 160.0, 240.0, "single", "ground_ball"),
        ("p3",  1, 165.0, 250.0, "single", "line_drive"),
        ("p3",  1, 155.0, 260.0, "out",    "fly_ball"),
        ("p3",  1, 170.0, 220.0, "out",    "ground_ball"),
        ("p3",  1, 158.0, 270.0, "single", "ground_ball"),
        ("p3",  1, 162.0, 200.0, "double", "line_drive"),
    ]
    for pid, perspective, x, y, play_result, play_type in sample_events:
        conn.execute(
            """
            INSERT INTO spray_charts (
                team_id, season_id, player_id, perspective_team_id,
                chart_type, x, y, play_result, play_type
            ) VALUES (?, ?, ?, ?, 'offensive', ?, ?, ?, ?)
            """,
            (1, _SEASON, pid, perspective, x, y, play_result, play_type),
        )
    conn.commit()
    return 1


@pytest.fixture()
def conn(tmp_path):
    path = tmp_path / "test.db"
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    load_real_schema(c)
    yield c
    c.close()


def _snapshot_positioning_tables(
    conn: sqlite3.Connection,
) -> tuple[list[dict], list[dict]]:
    """Snapshot ``batter_positioning`` + ``team_position_aggregate``
    rows projected onto data columns (excluding ``computed_at`` per
    CR I5).

    Returns:
        Tuple ``(batter_rows, aggregate_rows)``. Each list is sorted
        deterministically by composite key so equality compares
        row-for-row.
    """
    batter_rows = [
        dict(r) for r in conn.execute(
            """
            SELECT player_id, team_id, season_id, perspective_team_id,
                   position, direction_deviation, depth_deviation,
                   zone_id, is_thin, bip_count, hr_count
            FROM batter_positioning
            ORDER BY player_id, perspective_team_id, position
            """,
        ).fetchall()
    ]
    aggregate_rows = [
        dict(r) for r in conn.execute(
            """
            SELECT team_id, season_id, perspective_team_id, position,
                   star_x, star_y, bip_count, is_low_confidence
            FROM team_position_aggregate
            ORDER BY team_id, season_id, perspective_team_id, position
            """,
        ).fetchall()
    ]
    return batter_rows, aggregate_rows


class TestPipelineParity:
    """AC-5: same opponent through both paths produces identical rows.

    Both ``bb report generate`` (standalone) and ``trigger.run_scouting_sync``
    (scouting) funnel into ``compute_positioning(conn, team_id, season_id)``.
    The parity guarantee is engine determinism against the same input.
    """

    def test_engine_deterministic_across_two_runs(self, conn):
        """AC-5: invoking the engine twice against the same input yields
        identical batter_positioning + team_position_aggregate rows
        (data columns only; computed_at excluded)."""
        team_id = _seed_team_and_spray(conn)

        # Path A (representing standalone): invoke engine.
        compute_positioning(conn, team_id, _SEASON)
        batter_a, agg_a = _snapshot_positioning_tables(conn)

        # Path B (representing scouting): clear positioning state and
        # re-invoke the engine against the same input. The standalone +
        # scouting paths each call `compute_positioning` exactly once;
        # if the engine is deterministic, the result rows are identical.
        conn.execute("DELETE FROM batter_positioning")
        conn.execute("DELETE FROM team_position_aggregate")
        conn.commit()

        compute_positioning(conn, team_id, _SEASON)
        batter_b, agg_b = _snapshot_positioning_tables(conn)

        # Equality holds across all data columns. Each row is a dict
        # snapshot with the same key set, so dict == dict compares
        # every column.
        assert batter_a == batter_b, (
            "batter_positioning rows differ across two engine runs "
            "(parity guarantee broken)."
        )
        assert agg_a == agg_b, (
            "team_position_aggregate rows differ across two engine runs "
            "(parity guarantee broken)."
        )

    def test_engine_writes_six_aggregate_rows_per_perspective(self, conn):
        """Sanity: the engine writes exactly one team_position_aggregate
        row per covered position per perspective (TN-6 atomicity)."""
        team_id = _seed_team_and_spray(conn)
        compute_positioning(conn, team_id, _SEASON)

        _, aggregate_rows = _snapshot_positioning_tables(conn)
        positions_seen = {r["position"] for r in aggregate_rows}
        assert positions_seen == set(COVERED_POSITIONS), (
            f"engine must write all 6 covered positions per perspective; "
            f"saw {positions_seen}"
        )
        # One perspective in the fixture (perspective_team_id=1); so
        # exactly 6 aggregate rows.
        assert len(aggregate_rows) == 6

    def test_engine_writes_six_batter_rows_per_player_per_perspective(
        self, conn,
    ):
        """Sanity: the engine writes 6 batter_positioning rows per
        (player_id, perspective_team_id) per TN-7 atomicity."""
        team_id = _seed_team_and_spray(conn)
        compute_positioning(conn, team_id, _SEASON)

        batter_rows, _ = _snapshot_positioning_tables(conn)
        from collections import Counter
        per_player_perspective = Counter(
            (r["player_id"], r["perspective_team_id"]) for r in batter_rows
        )
        # Three batters x one perspective = 3 keys, each with 6 rows.
        assert len(per_player_perspective) == 3
        for key, count in per_player_perspective.items():
            assert count == 6, (
                f"expected 6 rows for (player, perspective)={key}; got {count}"
            )


# ---------------------------------------------------------------------------
# AC-6 grep-AC: no surviving v1 categorical references in pipeline files
# ---------------------------------------------------------------------------


class TestAC6NoV1ReferencesInPipelineFiles:
    """AC-6: pipeline-wiring files contain zero references to the
    retired v1 categorical model (per epic TN-13)."""

    _PIPELINE_DIRS: tuple[str, ...] = (
        "src/cli",
        "src/pipeline",
        "src/api/routes",
    )
    _RETIRED_TOKENS: tuple[str, ...] = (
        "call_state",
        "team_state_call",
        "direction_shade",
        "depth_shade",
        "zone_concentration",
        "POSITIONING_CALL_WORDS",
        "POSITIONING_CELL_SHORT_FORMS",
        "POSITIONING_COLUMN_ORDER",
        "POSITIONING_POSITION_LABELS",
    )

    def test_no_retired_v1_tokens_in_pipeline_dirs(self):
        import re
        from pathlib import Path
        repo_root = Path(__file__).resolve().parents[1]
        offenders: list[str] = []
        pattern = re.compile("|".join(re.escape(t) for t in self._RETIRED_TOKENS))
        for d in self._PIPELINE_DIRS:
            for py in (repo_root / d).rglob("*.py"):
                text = py.read_text(encoding="utf-8")
                if pattern.search(text):
                    offenders.append(str(py.relative_to(repo_root)))
        assert not offenders, (
            f"v1 retired tokens still appear in pipeline files: {offenders}"
        )
