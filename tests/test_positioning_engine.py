"""Tests for E-229-02 -- team-aggregate defensive positioning engine.

Covers AC-10 of E-229-02:
  (a) team-aggregate centroid math against golden synthetic data
  (b) per-batter deviation math + the full A-H sign-rule table
  (c) thin-gate behavior (BIP < 10 -> is_thin=1, still contributes to centroid)
  (d) confidence-tier behavior (0 / 15 / 50 BIP boundaries flip is_low_confidence)
  (e) transactional atomicity (engine state rolls back on persist failure)

The engine writes NO retired-categorical columns (AC-8) -- the schema does
not have them, so this is enforced structurally by the v2 migration.
"""

from __future__ import annotations

import logging
import sqlite3
from unittest.mock import patch

import pytest

from src.charts.spray import _raw_to_svg
from src.reports.positioning import (
    BASE_POSITIONS,
    BIP_THIN_THRESHOLD,
    COVERED_POSITIONS,
    DEPTH_DEVIATION_THRESHOLDS,
    DIRECTION_DEVIATION_THRESHOLDS,
    LOW_CONFIDENCE_THRESHOLD,
    POSITION_SCALE_FACTORS,
    BatterPositioningResult,
    PerPositionRow,
    TeamAggregateRow,
    _compute_batter_deviations,
    _compute_team_aggregate,
    _quantize_axis,
    _quantize_to_zone,
    compute_positioning,
)
from tests.conftest import load_real_schema


# ---------------------------------------------------------------------------
# Schema + fixture helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path):
    """In-memory SQLite connection with the full schema + migration 002 applied."""
    path = tmp_path / "test.db"
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    load_real_schema(c)
    # Seed a minimal team / season / scouting perspective set so the engine's
    # FK-constrained inserts succeed.
    c.execute(
        "INSERT INTO teams (id, name, public_id, season_year, membership_type) "
        "VALUES (1, 'Opp Bears', 'opp-bears', 2026, 'tracked')"
    )
    c.execute(
        "INSERT INTO teams (id, name, membership_type) "
        "VALUES (99, 'LSB Varsity', 'member')"
    )
    c.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) "
        "VALUES ('2026-spring-hs', '2026', 'spring-hs', 2026)"
    )
    c.commit()
    yield c
    c.close()


def _seed_player(conn, player_id: str, first: str = "Test", last: str = "Player"):
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, ?, ?)",
        (player_id, first, last),
    )


def _seed_spray_event(
    conn,
    *,
    player_id: str,
    team_id: int = 1,
    perspective_team_id: int = 99,
    season_id: str = "2026-spring-hs",
    x: float | None = 160.0,
    y: float | None = 150.0,
    play_result: str = "single",
    play_type: str = "line_drive",
    event_gc_id: str | None = None,
):
    _seed_player(conn, player_id)
    conn.execute(
        """
        INSERT INTO spray_charts (
            game_id, player_id, team_id, perspective_team_id,
            chart_type, play_type, play_result, x, y, season_id, event_gc_id
        ) VALUES (NULL, ?, ?, ?, 'offensive', ?, ?, ?, ?, ?, ?)
        """,
        (
            player_id, team_id, perspective_team_id,
            play_type, play_result, x, y, season_id,
            event_gc_id,
        ),
    )


def _placed(x: float, y: float, *, play_result: str = "single",
            play_type: str = "line_drive") -> dict:
    return {"x": x, "y": y, "play_result": play_result, "play_type": play_type}


# ---------------------------------------------------------------------------
# AC-10(a): team-aggregate centroid math (golden, hand-verified)
# ---------------------------------------------------------------------------


class TestTeamAggregateCentroid:
    """AC-1 + AC-10(a): whole-spray centroid projected position-scaled per TN-8."""

    def test_empty_events_anchors_at_textbook_positions(self):
        """Zero events -> centroid coincides with the anchor; every star equals
        its textbook BASE_POSITIONS value (no lean applied)."""
        rows = _compute_team_aggregate([])
        assert set(rows.keys()) == set(COVERED_POSITIONS)
        for position in COVERED_POSITIONS:
            star = rows[position]
            assert star.position == position
            assert star.star_x == pytest.approx(BASE_POSITIONS[position][0])
            assert star.star_y == pytest.approx(BASE_POSITIONS[position][1])
            assert star.bip_count == 0
            assert star.is_low_confidence == 1

    def test_centroid_at_anchor_yields_textbook_stars(self):
        """Spray events whose SVG centroid lands exactly at the anchor produce
        zero lean -> every star = textbook BASE_POSITIONS."""
        # Anchor = mean of BASE_POSITIONS. Find a raw (x, y) that maps there.
        anchor_x = sum(p[0] for p in BASE_POSITIONS.values()) / len(BASE_POSITIONS)
        anchor_y = sum(p[1] for p in BASE_POSITIONS.values()) / len(BASE_POSITIONS)
        # Solve _raw_to_svg inverse to get raw coords.
        # From src/charts/spray.py:49-51: svg_x = 49.189 + raw_x * 0.6926,
        # svg_y = 104.158 + raw_y * 0.6447. We use a placed pair that averages
        # to the anchor in SVG space directly: place two raw points whose SVG
        # midpoint is the anchor.
        from src.charts.spray import _KUe, _NU, _YUe, _DU
        raw_x = (anchor_x - _KUe) / _NU
        raw_y = (anchor_y - _YUe) / _DU
        rows = _compute_team_aggregate([
            _placed(raw_x, raw_y),
            _placed(raw_x, raw_y),
        ])
        for position in COVERED_POSITIONS:
            assert rows[position].star_x == pytest.approx(BASE_POSITIONS[position][0])
            assert rows[position].star_y == pytest.approx(BASE_POSITIONS[position][1])
            assert rows[position].bip_count == 2

    def test_pull_side_lean_shifts_stars_toward_LF(self):
        """A left-of-anchor centroid pulls every star toward LF.

        Outfielder stars shift further than infielder stars because of
        POSITION_SCALE_FACTORS (outfielders 1.0, infielders 0.4-0.5).
        """
        # Two events both far left in SVG space (small x). Use small raw_x.
        # raw_x=0, raw_y=200 -> svg ≈ (49.189, 233.10). That's far-left.
        events = [_placed(0.0, 200.0), _placed(0.0, 200.0)]
        # Compute expected lean directly.
        sx, sy = _raw_to_svg(0.0, 200.0)
        anchor_x = sum(p[0] for p in BASE_POSITIONS.values()) / len(BASE_POSITIONS)
        anchor_y = sum(p[1] for p in BASE_POSITIONS.values()) / len(BASE_POSITIONS)
        lean_x = sx - anchor_x
        lean_y = sy - anchor_y
        assert lean_x < 0  # centroid is left of anchor -> negative lean_x

        rows = _compute_team_aggregate(events)
        # LF (factor 1.0): full lean applied.
        expected_lf_x = BASE_POSITIONS["LF"][0] + lean_x * 1.0
        expected_lf_y = BASE_POSITIONS["LF"][1] + lean_y * 1.0
        assert rows["LF"].star_x == pytest.approx(expected_lf_x)
        assert rows["LF"].star_y == pytest.approx(expected_lf_y)
        # 2B (factor 0.5): half lean applied.
        expected_2b_x = BASE_POSITIONS["2B"][0] + lean_x * 0.5
        expected_2b_y = BASE_POSITIONS["2B"][1] + lean_y * 0.5
        assert rows["2B"].star_x == pytest.approx(expected_2b_x)
        assert rows["2B"].star_y == pytest.approx(expected_2b_y)
        # 3B (factor 0.4): smallest shade.
        expected_3b_x = BASE_POSITIONS["3B"][0] + lean_x * 0.4
        expected_3b_y = BASE_POSITIONS["3B"][1] + lean_y * 0.4
        assert rows["3B"].star_x == pytest.approx(expected_3b_x)
        assert rows["3B"].star_y == pytest.approx(expected_3b_y)
        # Outfielders shift further left (in SVG x) than infielders.
        of_shift = abs(rows["LF"].star_x - BASE_POSITIONS["LF"][0])
        if_shift = abs(rows["3B"].star_x - BASE_POSITIONS["3B"][0])
        assert of_shift > if_shift

    def test_bip_count_total_set_on_every_position(self):
        """All 6 rows carry the full opponent BIP count (AC-1)."""
        events = [_placed(100.0, 200.0)] * 7
        rows = _compute_team_aggregate(events)
        for position in COVERED_POSITIONS:
            assert rows[position].bip_count == 7


# ---------------------------------------------------------------------------
# AC-10(b): per-batter deviation + full A-H sign-rule table (TN-3)
# ---------------------------------------------------------------------------


class TestQuantizeToZone:
    """AC-3 + AC-10(b): the full 9-cell sign-rule table from TN-3."""

    @pytest.mark.parametrize("direction, depth, expected", [
        # (sign of direction, sign of depth, expected zone)
        (-1, -1, "A"),  # in + left
        (-1,  0, "B"),  # left
        (-1,  1, "C"),  # deep + left
        ( 0, -1, "D"),  # in
        ( 0,  0, None), # at the star -> NULL
        ( 0,  1, "E"),  # deep
        ( 1, -1, "F"),  # in + right
        ( 1,  0, "G"),  # right
        ( 1,  1, "H"),  # deep + right
    ])
    def test_sign_rule_table_complete(self, direction, depth, expected):
        assert _quantize_to_zone(direction, depth) == expected

    def test_magnitude_ignored_only_sign_matters(self):
        """AC-3: magnitude is ignored for letter assignment."""
        # All four "left + deep" cells map to C regardless of magnitude.
        assert _quantize_to_zone(-1, 1) == "C"
        assert _quantize_to_zone(-2, 1) == "C"
        assert _quantize_to_zone(-1, 2) == "C"
        assert _quantize_to_zone(-2, 2) == "C"

    def test_zero_zero_is_null(self):
        """AC-3: (0, 0) -> NULL (no zone label, the star itself)."""
        assert _quantize_to_zone(0, 0) is None


class TestPerBatterDeviation:
    """AC-2 + AC-10(b): per-batter deviation against each position's star."""

    def test_batter_at_star_has_zero_deviation_and_null_zone(self):
        """A batter whose centroid coincides with a position's star yields
        (0, 0) deviation for that position -> zone_id = NULL."""
        # Build a team aggregate where every star sits at BASE_POSITIONS.
        aggregates = _compute_team_aggregate([])
        # Build a single batter at the textbook LF base position. Need a raw
        # (x, y) whose _raw_to_svg image equals BASE_POSITIONS["LF"].
        from src.charts.spray import _KUe, _NU, _YUe, _DU
        lf_svg_x, lf_svg_y = BASE_POSITIONS["LF"]
        raw_x = (lf_svg_x - _KUe) / _NU
        raw_y = (lf_svg_y - _YUe) / _DU
        events = [_placed(raw_x, raw_y) for _ in range(15)]
        rows, bip_count, is_thin = _compute_batter_deviations(events, hr_count=0,
                                                              team_aggregate=aggregates)
        lf_row = next(r for r in rows if r.position == "LF")
        assert lf_row.direction_deviation == 0
        assert lf_row.depth_deviation == 0
        assert lf_row.zone_id is None
        assert bip_count == 15
        assert is_thin == 0

    def test_returns_six_rows_one_per_position(self):
        aggregates = _compute_team_aggregate([])
        rows, _, _ = _compute_batter_deviations([_placed(100.0, 200.0)] * 10,
                                                hr_count=0,
                                                team_aggregate=aggregates)
        assert len(rows) == 6
        assert {r.position for r in rows} == set(COVERED_POSITIONS)

    def test_left_deep_batter_yields_zone_C_at_a_position(self):
        """A batter centered well left of and deeper than the star -> zone C."""
        # Aggregates: empty, so stars sit at textbook BASE_POSITIONS.
        aggregates = _compute_team_aggregate([])
        # Build a batter whose centroid is far left + deeper than LF's star
        # (LF star at SVG (75, 130); deep = smaller SVG y).
        # raw_x=0, raw_y=0 -> svg ≈ (49.189, 104.158): left of and shallower
        # than LF? svg_y=104 vs star_y=130 -> star_y - batter_y = 26 > 0
        # -> depth_dev positive (deep). svg_x=49 vs star_x=75 -> delta_x=-26
        # -> direction_dev negative (left). -> Zone C.
        events = [_placed(0.0, 0.0) for _ in range(15)]
        rows, _, _ = _compute_batter_deviations(events, hr_count=0,
                                                team_aggregate=aggregates)
        lf_row = next(r for r in rows if r.position == "LF")
        assert lf_row.direction_deviation < 0
        assert lf_row.depth_deviation > 0
        assert lf_row.zone_id == "C"

    def test_hr_count_threaded_through_every_row(self):
        aggregates = _compute_team_aggregate([])
        rows, _, _ = _compute_batter_deviations([_placed(100.0, 100.0)] * 10,
                                                hr_count=3,
                                                team_aggregate=aggregates)
        for r in rows:
            assert r.hr_count == 3


class TestQuantizeAxis:
    """Stage A axis quantization (used by deviation math)."""

    def test_zero_when_below_first_threshold(self):
        t1, _ = DIRECTION_DEVIATION_THRESHOLDS
        assert _quantize_axis(0, DIRECTION_DEVIATION_THRESHOLDS) == 0
        assert _quantize_axis(t1 - 0.01, DIRECTION_DEVIATION_THRESHOLDS) == 0
        assert _quantize_axis(-(t1 - 0.01), DIRECTION_DEVIATION_THRESHOLDS) == 0

    def test_pm1_between_thresholds(self):
        t1, t2 = DIRECTION_DEVIATION_THRESHOLDS
        assert _quantize_axis(t1, DIRECTION_DEVIATION_THRESHOLDS) == 1
        assert _quantize_axis(-(t1 + 0.5), DIRECTION_DEVIATION_THRESHOLDS) == -1
        assert _quantize_axis(t2 - 0.01, DIRECTION_DEVIATION_THRESHOLDS) == 1

    def test_pm2_at_or_above_second_threshold(self):
        _, t2 = DIRECTION_DEVIATION_THRESHOLDS
        assert _quantize_axis(t2, DIRECTION_DEVIATION_THRESHOLDS) == 2
        assert _quantize_axis(-(t2 + 5), DIRECTION_DEVIATION_THRESHOLDS) == -2


# ---------------------------------------------------------------------------
# AC-10(c): thin-gate behavior
# ---------------------------------------------------------------------------


class TestThinGate:
    """AC-4 + AC-10(c): batters with total BIP < 10 are is_thin=1 across all
    6 of their rows AND still contribute to the team-aggregate centroid."""

    def test_thin_batter_has_is_thin_set_on_all_six_rows(self, conn):
        # Add 5 BIPs from one (thin) batter -> is_thin=1 for that batter.
        for _ in range(5):
            _seed_spray_event(conn, player_id="p-thin", x=100.0, y=200.0)
        conn.commit()
        results = compute_positioning(conn, team_id=1, season_id="2026-spring-hs")
        thin = [r for r in results if r.player_id == "p-thin"][0]
        assert thin.is_thin == 1
        assert thin.bip_count == 5
        assert all(row.is_thin == 1 for row in thin.per_position_rows)
        assert len(thin.per_position_rows) == 6

    def test_thin_batter_bips_contribute_to_team_centroid(self, conn):
        """AC-4: thin batters still shape the star.

        Two batters: one thin (5 BIP far left), one full-data (15 BIP at
        anchor). The team centroid should pull noticeably left of the
        anchor (more than zero) because the thin batter's 5 BIPs count.
        """
        from src.charts.spray import _KUe, _NU, _YUe, _DU
        anchor_x = sum(p[0] for p in BASE_POSITIONS.values()) / len(BASE_POSITIONS)
        anchor_y = sum(p[1] for p in BASE_POSITIONS.values()) / len(BASE_POSITIONS)
        anchor_raw_x = (anchor_x - _KUe) / _NU
        anchor_raw_y = (anchor_y - _YUe) / _DU

        for _ in range(15):
            _seed_spray_event(
                conn, player_id="p-full",
                x=anchor_raw_x, y=anchor_raw_y,
            )
        for _ in range(5):
            _seed_spray_event(conn, player_id="p-thin", x=0.0, y=200.0)
        conn.commit()
        compute_positioning(conn, team_id=1, season_id="2026-spring-hs")
        # Centroid shifted left of anchor -> LF star moves left of textbook LF.
        agg = conn.execute(
            "SELECT star_x FROM team_position_aggregate "
            "WHERE position='LF' AND team_id=1 AND season_id=?",
            ("2026-spring-hs",),
        ).fetchone()
        assert agg["star_x"] < BASE_POSITIONS["LF"][0]

    def test_threshold_is_strictly_less_than(self):
        """AC-4: is_thin=1 when BIP < threshold. At threshold -> is_thin=0."""
        # Build a batter with exactly BIP_THIN_THRESHOLD placed events.
        aggregates = _compute_team_aggregate([])
        events = [_placed(100.0, 100.0)] * BIP_THIN_THRESHOLD
        rows, bip_count, is_thin = _compute_batter_deviations(
            events, hr_count=0, team_aggregate=aggregates,
        )
        assert bip_count == BIP_THIN_THRESHOLD
        assert is_thin == 0
        for r in rows:
            assert r.is_thin == 0

        # One fewer -> thin.
        events_short = [_placed(100.0, 100.0)] * (BIP_THIN_THRESHOLD - 1)
        _, _, is_thin_short = _compute_batter_deviations(
            events_short, hr_count=0, team_aggregate=aggregates,
        )
        assert is_thin_short == 1


# ---------------------------------------------------------------------------
# AC-10(d): confidence-tier behavior
# ---------------------------------------------------------------------------


class TestConfidenceTier:
    """AC-5 + AC-10(d): is_low_confidence=1 when total BIP < 50, else 0.
    Boundaries: 0 / 15 / 50 BIP all behaviorally tested."""

    def test_zero_bip_is_low_confidence(self):
        rows = _compute_team_aggregate([])
        for position in COVERED_POSITIONS:
            assert rows[position].bip_count == 0
            assert rows[position].is_low_confidence == 1

    def test_fifteen_bip_is_low_confidence(self):
        rows = _compute_team_aggregate([_placed(100.0, 100.0)] * 15)
        for position in COVERED_POSITIONS:
            assert rows[position].bip_count == 15
            assert rows[position].is_low_confidence == 1

    def test_just_below_fifty_is_low_confidence(self):
        rows = _compute_team_aggregate([_placed(100.0, 100.0)] * 49)
        for position in COVERED_POSITIONS:
            assert rows[position].bip_count == 49
            assert rows[position].is_low_confidence == 1

    def test_fifty_bip_is_full_confidence(self):
        """AC-5 boundary: 50+ BIP -> is_low_confidence=0."""
        rows = _compute_team_aggregate([_placed(100.0, 100.0)] * LOW_CONFIDENCE_THRESHOLD)
        for position in COVERED_POSITIONS:
            assert rows[position].bip_count == LOW_CONFIDENCE_THRESHOLD
            assert rows[position].is_low_confidence == 0

    def test_well_above_threshold_is_full_confidence(self):
        rows = _compute_team_aggregate([_placed(100.0, 100.0)] * 120)
        for position in COVERED_POSITIONS:
            assert rows[position].bip_count == 120
            assert rows[position].is_low_confidence == 0


# ---------------------------------------------------------------------------
# AC-10(e): transactional atomicity
# ---------------------------------------------------------------------------


class TestAtomicity:
    """AC-6 + AC-10(e): both tables refresh in a single SQLite transaction.

    Pattern (DE I-7): patch the second INSERT to raise; assert that after
    the exception propagates, the database state matches pre-call state
    for both batter_positioning and team_position_aggregate (no partial
    writes, no stale rows from a previous run).
    """

    def test_partial_write_failure_rolls_back_both_tables(self, tmp_path):
        # Build a connection from a custom sqlite3.Connection subclass so we
        # can intercept .execute() to simulate a mid-transaction failure.
        # sqlite3.Connection's methods are not directly monkey-patchable on
        # instances or the class, so the factory= parameter is the only way
        # in.
        class FailingConn(sqlite3.Connection):
            batter_inserts_seen = 0
            should_fail = False

            def execute(self, sql, params=()):
                if (
                    self.should_fail
                    and isinstance(sql, str)
                    and "INSERT INTO batter_positioning" in sql
                ):
                    FailingConn.batter_inserts_seen += 1
                    if FailingConn.batter_inserts_seen == 2:
                        raise sqlite3.OperationalError(
                            "simulated mid-transaction failure"
                        )
                return super().execute(sql, params)

        path = tmp_path / "atomic.db"
        conn = sqlite3.connect(str(path), factory=FailingConn)
        conn.row_factory = sqlite3.Row
        load_real_schema(conn)
        conn.execute(
            "INSERT INTO teams (id, name, public_id, season_year, "
            "membership_type) VALUES (1, 'Opp', 'opp', 2026, 'tracked')"
        )
        conn.execute(
            "INSERT INTO teams (id, name, membership_type) "
            "VALUES (99, 'LSB', 'member')"
        )
        conn.execute(
            "INSERT INTO seasons (season_id, name, season_type, year) "
            "VALUES ('2026-spring-hs', '2026', 'spring-hs', 2026)"
        )
        conn.commit()

        # Seed a clean baseline state: one prior run produced 6 aggregate
        # rows and 6 batter rows. We mutate spray data, induce a failure,
        # then verify nothing changed.
        for _ in range(15):
            _seed_spray_event(conn, player_id="p-first", x=100.0, y=200.0)
        conn.commit()
        compute_positioning(conn, team_id=1, season_id="2026-spring-hs")
        baseline_agg = sorted(conn.execute(
            "SELECT position, star_x, star_y, bip_count, is_low_confidence "
            "FROM team_position_aggregate "
            "WHERE team_id=1 AND season_id='2026-spring-hs'"
        ).fetchall(), key=lambda r: r["position"])
        baseline_batter = sorted(conn.execute(
            "SELECT player_id, position, direction_deviation, depth_deviation, "
            "zone_id, is_thin, bip_count, hr_count "
            "FROM batter_positioning "
            "WHERE team_id=1 AND season_id='2026-spring-hs'"
        ).fetchall(), key=lambda r: (r["player_id"], r["position"]))
        assert len(baseline_agg) == 6
        assert len(baseline_batter) == 6

        # Add MORE spray data so a successful re-run would change row contents.
        for _ in range(20):
            _seed_spray_event(conn, player_id="p-second", x=50.0, y=100.0)
        conn.commit()

        # Arm the failure: second INSERT INTO batter_positioning will raise.
        FailingConn.should_fail = True
        FailingConn.batter_inserts_seen = 0
        with pytest.raises(sqlite3.OperationalError):
            compute_positioning(
                conn, team_id=1, season_id="2026-spring-hs",
            )
        FailingConn.should_fail = False

        # ROLLBACK should have restored baseline.
        post_agg = sorted(conn.execute(
            "SELECT position, star_x, star_y, bip_count, is_low_confidence "
            "FROM team_position_aggregate "
            "WHERE team_id=1 AND season_id='2026-spring-hs'"
        ).fetchall(), key=lambda r: r["position"])
        post_batter = sorted(conn.execute(
            "SELECT player_id, position, direction_deviation, depth_deviation, "
            "zone_id, is_thin, bip_count, hr_count "
            "FROM batter_positioning "
            "WHERE team_id=1 AND season_id='2026-spring-hs'"
        ).fetchall(), key=lambda r: (r["player_id"], r["position"]))

        # Same row counts.
        assert len(post_agg) == len(baseline_agg)
        assert len(post_batter) == len(baseline_batter)
        # Same row contents (no partial second-run state survived).
        for before, after in zip(baseline_agg, post_agg):
            assert tuple(before) == tuple(after)
        for before, after in zip(baseline_batter, post_batter):
            assert tuple(before) == tuple(after)
        # The second-run player should NOT be in the table (its inserts
        # rolled back).
        post_players = {r["player_id"] for r in post_batter}
        assert "p-second" not in post_players
        conn.close()

    def test_clean_rebuild_wipes_stale_perspectives(self, conn):
        """DELETE scope = (team_id, season_id) covers ALL perspectives. A
        perspective that drops out between runs disappears from both tables."""
        # First run: two perspectives writing rows.
        conn.execute(
            "INSERT INTO teams (id, name, membership_type) "
            "VALUES (100, 'Other Scout', 'member')"
        )
        # Both perspectives seed events for the same player; each event has
        # a distinct event_gc_id so the UNIQUE(event_gc_id, perspective_team_id)
        # constraint is satisfied.
        for i in range(15):
            _seed_spray_event(
                conn, player_id="p1", perspective_team_id=99,
                x=100.0, y=200.0,
                event_gc_id=f"evt-p99-{i}",
            )
        for i in range(15):
            _seed_spray_event(
                conn, player_id="p1", perspective_team_id=100,
                x=100.0, y=200.0,
                event_gc_id=f"evt-p100-{i}",
            )
        conn.commit()
        compute_positioning(conn, 1, "2026-spring-hs")
        perspectives_first = conn.execute(
            "SELECT DISTINCT perspective_team_id FROM team_position_aggregate "
            "WHERE team_id=1"
        ).fetchall()
        assert {r[0] for r in perspectives_first} == {99, 100}

        # Drop perspective 100's spray rows -> second run should clean it out.
        conn.execute(
            "DELETE FROM spray_charts WHERE perspective_team_id=100"
        )
        conn.commit()
        compute_positioning(conn, 1, "2026-spring-hs")
        perspectives_second = conn.execute(
            "SELECT DISTINCT perspective_team_id FROM team_position_aggregate "
            "WHERE team_id=1"
        ).fetchall()
        assert {r[0] for r in perspectives_second} == {99}
        # batter_positioning likewise.
        bp_perspectives = conn.execute(
            "SELECT DISTINCT perspective_team_id FROM batter_positioning "
            "WHERE team_id=1"
        ).fetchall()
        assert {r[0] for r in bp_perspectives} == {99}


# ---------------------------------------------------------------------------
# End-to-end engine: AC-1 + AC-2 + AC-6 + AC-7 integration
# ---------------------------------------------------------------------------


class TestComputePositioningEndToEnd:
    """Wiring tests: compute_positioning reads spray_charts, writes both
    tables, returns the per-batter result list."""

    def test_writes_six_aggregate_rows_per_opponent(self, conn):
        for _ in range(15):
            _seed_spray_event(conn, player_id="p1", x=100.0, y=200.0)
        conn.commit()
        compute_positioning(conn, 1, "2026-spring-hs")
        agg_rows = conn.execute(
            "SELECT position FROM team_position_aggregate "
            "WHERE team_id=1 AND season_id=?",
            ("2026-spring-hs",),
        ).fetchall()
        assert {r[0] for r in agg_rows} == set(COVERED_POSITIONS)
        assert len(agg_rows) == 6

    def test_writes_six_batter_rows_per_batter(self, conn):
        for _ in range(15):
            _seed_spray_event(conn, player_id="p1", x=100.0, y=200.0)
        for _ in range(15):
            _seed_spray_event(conn, player_id="p2", x=180.0, y=150.0)
        conn.commit()
        compute_positioning(conn, 1, "2026-spring-hs")
        rows = conn.execute(
            "SELECT player_id, position FROM batter_positioning "
            "WHERE team_id=1 AND season_id=?",
            ("2026-spring-hs",),
        ).fetchall()
        assert len(rows) == 12  # 2 players * 6 positions
        for player_id in ("p1", "p2"):
            positions = {r[1] for r in rows if r[0] == player_id}
            assert positions == set(COVERED_POSITIONS)

    def test_hr_count_includes_null_coord_home_runs(self, conn):
        """Over-the-fence HRs have NULL x/y but still count for hr_count."""
        for _ in range(10):
            _seed_spray_event(conn, player_id="p1", x=180.0, y=150.0)
        # Add two HR events with NULL coords.
        _seed_player(conn, "p1")
        for _ in range(2):
            conn.execute(
                """
                INSERT INTO spray_charts (
                    game_id, player_id, team_id, perspective_team_id,
                    chart_type, play_type, play_result, x, y, season_id
                ) VALUES (NULL, 'p1', 1, 99, 'offensive', 'fly_ball',
                          'home_run', NULL, NULL, '2026-spring-hs')
                """
            )
        conn.commit()
        results = compute_positioning(conn, 1, "2026-spring-hs")
        p1 = next(r for r in results if r.player_id == "p1")
        assert p1.hr_count == 2
        # bip_count is just the placed (non-NULL) events.
        assert p1.bip_count == 10

    def test_returns_one_result_per_batter_perspective_pair(self, conn):
        for _ in range(15):
            _seed_spray_event(conn, player_id="p1", x=100.0, y=200.0)
        for _ in range(15):
            _seed_spray_event(conn, player_id="p2", x=180.0, y=150.0)
        conn.commit()
        results = compute_positioning(conn, 1, "2026-spring-hs")
        assert {r.player_id for r in results} == {"p1", "p2"}
        for result in results:
            assert isinstance(result, BatterPositioningResult)
            assert len(result.per_position_rows) == 6

    def test_no_retired_categorical_columns_on_per_position_row(self, conn):
        """AC-8: PerPositionRow MUST NOT carry retired-categorical fields."""
        for _ in range(15):
            _seed_spray_event(conn, player_id="p1", x=100.0, y=200.0)
        conn.commit()
        results = compute_positioning(conn, 1, "2026-spring-hs")
        row = results[0].per_position_rows[0]
        for retired_field in ("call_state", "team_state_call", "direction_shade",
                              "depth_shade", "zone_concentration"):
            assert not hasattr(row, retired_field), (
                f"PerPositionRow must not expose retired field {retired_field!r}"
            )
        # Also assert PerPositionRow exposes the v2 fields explicitly.
        for v2_field in ("direction_deviation", "depth_deviation", "zone_id",
                         "is_thin", "bip_count", "hr_count"):
            assert hasattr(row, v2_field), (
                f"PerPositionRow missing v2 field {v2_field!r}"
            )

    def test_null_season_id_rows_are_skipped_and_logged(self, conn, caplog):
        _seed_player(conn, "p1")
        # One valid row, one NULL-season row.
        _seed_spray_event(conn, player_id="p1", x=100.0, y=200.0)
        conn.execute(
            """
            INSERT INTO spray_charts (
                game_id, player_id, team_id, perspective_team_id,
                chart_type, play_type, play_result, x, y, season_id
            ) VALUES (NULL, 'p1', 1, 99, 'offensive', 'fly_ball',
                      'single', 100.0, 100.0, NULL)
            """
        )
        conn.commit()
        with caplog.at_level(logging.WARNING):
            compute_positioning(conn, 1, "2026-spring-hs")
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("skipped 1" in r.getMessage() for r in warnings)

    def test_zero_data_path_still_rebuilds_table_cleanly(self, conn):
        """Zero-row rebuild is a valid state -- no INSERTs, no error."""
        # No spray data seeded.
        results = compute_positioning(conn, 1, "2026-spring-hs")
        assert results == []
        # Tables are empty for the scope, no error raised.
        agg = conn.execute(
            "SELECT COUNT(*) FROM team_position_aggregate "
            "WHERE team_id=1 AND season_id='2026-spring-hs'"
        ).fetchone()[0]
        bp = conn.execute(
            "SELECT COUNT(*) FROM batter_positioning "
            "WHERE team_id=1 AND season_id='2026-spring-hs'"
        ).fetchone()[0]
        assert agg == 0
        assert bp == 0


class TestEngineSolelyWritesAggregateTable:
    """AC-7 enforcement check: structural grep -- src/reports/ has no other
    INSERT/UPDATE/UPSERT against team_position_aggregate.
    """

    def test_no_other_writers_in_src_reports(self):
        import pathlib
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        reports_dir = repo_root / "src" / "reports"
        engine_file = reports_dir / "positioning.py"
        for py in reports_dir.rglob("*.py"):
            if py == engine_file:
                continue
            text = py.read_text()
            # No write statements to team_position_aggregate from other modules.
            for op in (
                "INSERT INTO team_position_aggregate",
                "UPDATE team_position_aggregate",
                "UPSERT team_position_aggregate",
            ):
                assert op not in text, (
                    f"Found illegal write {op!r} in {py} -- only "
                    f"src/reports/positioning.py may write to "
                    f"team_position_aggregate (epic TN-2)."
                )
