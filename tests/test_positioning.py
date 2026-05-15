"""Tests for E-228-02 -- Tier 1 deterministic positioning engine.

Covers the three-stage pipeline (Stage A optimal-point computation +
per-axis ordinal-bucket quantization; Stage B per-position direction +
depth via the swappable responsibility-subset seam; Stage C sample
gates + quantization to the 8 ``call_state`` enum keys including the
TN-4a ``MIXED`` rule), the per-zone gates, the NULL-``season_id`` skip
rule, the delete-then-insert idempotency contract, per-position
direction/depth re-evaluation (different positions producing different
``call_state`` for the same batter), an end-to-end ``MIXED`` scenario
through ``compute_positioning``, and the AC-7 edge cases.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from src.charts.spray import _raw_to_svg
from src.reports.positioning import (
    ADJACENCY_LATTICE,
    BASE_POSITIONS,
    BIP_DEPTH_THRESHOLD,
    BIP_THIN_THRESHOLD,
    COVERED_POSITIONS,
    DEPTH_DEVIATION_THRESHOLDS,
    DIRECTION_DEVIATION_THRESHOLDS,
    INFIELD_OUTFIELD_SVG_Y_THRESHOLD,
    POSITION_RESPONSIBILITY_SECTORS,
    ZONE_MIN_BIP,
    ZONE_MIN_CONCENTRATION,
    BatterPositioningResult,
    PerZoneAggregation,
    ZoneAssignment,
    _are_adjacent,
    _compute_team_state_call,
    _depth_band,
    _depth_from_contact_type,
    _direction_shade_from_dominant,
    _quantize_axis,
    assign_zone,
    bips_for_position,
    compute_positioning,
)
from tests.conftest import load_real_schema

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def _apply_positioning_migration(conn: sqlite3.Connection) -> None:
    """Apply the ``002_batter_positioning.sql`` migration on top of the base."""
    sql = (_MIGRATIONS_DIR / "002_batter_positioning.sql").read_text()
    conn.executescript(sql)


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory DB with the base schema + the ``batter_positioning`` table."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    load_real_schema(conn)
    _apply_positioning_migration(conn)
    yield conn
    conn.close()


_SEASON_ID = "2026-spring-hs"
_OTHER_SEASON_ID = "2025-spring-hs"
_OPPONENT_TEAM_ID = 1     # batter's team (scouted opponent)
_PERSPECTIVE_ID = 2       # whose API pull produced the spray rows
_OTHER_PERSPECTIVE_ID = 3


def _seed_base(db: sqlite3.Connection) -> None:
    """Seed teams, seasons, programs, players referenced by the tests."""
    db.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, ?, ?, ?)",
        (_SEASON_ID, "Spring 2026 HS", "spring-hs", 2026),
    )
    db.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, ?, ?, ?)",
        (_OTHER_SEASON_ID, "Spring 2025 HS", "spring-hs", 2025),
    )
    db.execute(
        "INSERT INTO teams (id, name, membership_type) "
        "VALUES (?, 'Opponent HS', 'tracked')",
        (_OPPONENT_TEAM_ID,),
    )
    db.execute(
        "INSERT INTO teams (id, name, membership_type) "
        "VALUES (?, 'LSB Varsity', 'member')",
        (_PERSPECTIVE_ID,),
    )
    db.execute(
        "INSERT INTO teams (id, name, membership_type) "
        "VALUES (?, 'LSB JV', 'member')",
        (_OTHER_PERSPECTIVE_ID,),
    )


def _seed_player(db: sqlite3.Connection, player_id: str, last_name: str = "Smith") -> None:
    db.execute(
        "INSERT INTO players (player_id, first_name, last_name) "
        "VALUES (?, ?, ?)",
        (player_id, "Test", last_name),
    )


def _insert_event(
    db: sqlite3.Connection,
    *,
    player_id: str,
    team_id: int = _OPPONENT_TEAM_ID,
    perspective_team_id: int = _PERSPECTIVE_ID,
    season_id: str | None = _SEASON_ID,
    x: float | None,
    y: float | None,
    play_result: str = "single",
    play_type: str | None = "ground_ball",
    event_id: str | None = None,
) -> None:
    """Insert one offensive spray_charts row."""
    if event_id is None:
        event_id = f"evt-{player_id}-{x}-{y}-{play_type}-{play_result}-{id(player_id)}"
    db.execute(
        """
        INSERT INTO spray_charts (
            player_id, team_id, perspective_team_id, chart_type,
            play_result, play_type, x, y, season_id, event_gc_id
        ) VALUES (?, ?, ?, 'offensive', ?, ?, ?, ?, ?, ?)
        """,
        (player_id, team_id, perspective_team_id, play_result, play_type, x, y,
         season_id, event_id),
    )


# Raw -> SVG coords (via _raw_to_svg):
#   x=50,  y=100 -> svg(83.8, 168.6)   -> (left,   outfield)  -> LF responsibility
#   x=270, y=100 -> svg(236.2, 168.6)  -> (right,  outfield)  -> RF responsibility
#   x=160, y=100 -> svg(160.0, 168.6)  -> (center, outfield)  -> CF responsibility
#   x=75,  y=180 -> svg(101.1, 220.2)  -> (left,   infield)   -> SS + 3B responsibility
#   x=245, y=180 -> svg(218.9, 220.2)  -> (right,  infield)   -> 2B responsibility
#   x=160, y=180 -> svg(160.0, 220.2)  -> (center, infield)   -> SS + 2B responsibility


def _insert_left_outfield_event(db, player_id: str, **kwargs) -> None:
    """LF outfield: (left, outfield) -> LF responsibility only."""
    _insert_event(db, player_id=player_id, x=50.0, y=100.0, **kwargs)


def _insert_right_outfield_event(db, player_id: str, **kwargs) -> None:
    """RF outfield: (right, outfield) -> RF responsibility only."""
    _insert_event(db, player_id=player_id, x=270.0, y=100.0, **kwargs)


def _insert_center_outfield_event(db, player_id: str, **kwargs) -> None:
    """CF outfield: (center, outfield) -> CF responsibility only."""
    _insert_event(db, player_id=player_id, x=160.0, y=100.0, **kwargs)


def _insert_left_infield_event(db, player_id: str, **kwargs) -> None:
    """Left infield: (left, infield) -> SS and 3B responsibility."""
    _insert_event(db, player_id=player_id, x=75.0, y=180.0, **kwargs)


def _insert_right_infield_event(db, player_id: str, **kwargs) -> None:
    """Right infield: (right, infield) -> 2B responsibility only."""
    _insert_event(db, player_id=player_id, x=245.0, y=180.0, **kwargs)


def _insert_center_infield_event(db, player_id: str, **kwargs) -> None:
    """Center infield: (center, infield) -> SS and 2B responsibility."""
    _insert_event(db, player_id=player_id, x=160.0, y=180.0, **kwargs)


def _row_by_position(result: BatterPositioningResult, position: str):
    for r in result.per_position_rows:
        if r.position == position:
            return r
    raise AssertionError(f"position {position!r} missing from result rows")


# ---------------------------------------------------------------------------
# AC-1c: BASE_POSITIONS + two distinct per-axis quantization ladders
# ---------------------------------------------------------------------------


class TestStageAConstants:
    def test_base_positions_covers_all_six_positions(self):
        """BASE_POSITIONS must cover the 6 covered positions (AC-1c)."""
        assert set(BASE_POSITIONS.keys()) == set(COVERED_POSITIONS)
        for pos, (x, y) in BASE_POSITIONS.items():
            assert isinstance(x, float)
            assert isinstance(y, float)

    def test_two_distinct_ladders_named_and_documented(self):
        """The two per-axis ladders must be named and documented separately.

        AC-1c anisotropy guard: a single shared ladder would silently
        re-introduce the anisotropy bug.
        """
        assert DIRECTION_DEVIATION_THRESHOLDS is not DEPTH_DEVIATION_THRESHOLDS
        assert len(DIRECTION_DEVIATION_THRESHOLDS) == 2
        assert len(DEPTH_DEVIATION_THRESHOLDS) == 2
        assert DIRECTION_DEVIATION_THRESHOLDS != DEPTH_DEVIATION_THRESHOLDS

    def test_recalibrate_annotations_present_in_source(self):
        """Module source must carry ``# RECALIBRATE`` annotations (AC-9)."""
        from src.reports import positioning as mod
        src = Path(mod.__file__).read_text()
        assert "RECALIBRATE" in src
        assert src.count("RECALIBRATE") >= 4

    def test_position_responsibility_sectors_covers_all_six(self):
        """POSITION_RESPONSIBILITY_SECTORS must cover all 6 covered positions."""
        assert set(POSITION_RESPONSIBILITY_SECTORS.keys()) == set(COVERED_POSITIONS)
        for pos, cells in POSITION_RESPONSIBILITY_SECTORS.items():
            assert isinstance(cells, frozenset)
            assert len(cells) >= 1
            for cell in cells:
                zone, band = cell
                assert zone in {"left", "center", "right"}
                assert band in {"infield", "outfield"}


# ---------------------------------------------------------------------------
# Stage A: signed-delta -> ordinal bucket quantization (AC-1a, AC-11)
# ---------------------------------------------------------------------------


class TestQuantizeAxis:
    def test_zero_delta_is_bucket_zero(self):
        assert _quantize_axis(0.0, DIRECTION_DEVIATION_THRESHOLDS) == 0
        assert _quantize_axis(0.0, DEPTH_DEVIATION_THRESHOLDS) == 0

    def test_direction_below_lower_threshold_is_zero(self):
        lo, _hi = DIRECTION_DEVIATION_THRESHOLDS
        assert _quantize_axis(lo - 0.01, DIRECTION_DEVIATION_THRESHOLDS) == 0
        assert _quantize_axis(-(lo - 0.01), DIRECTION_DEVIATION_THRESHOLDS) == 0

    def test_direction_at_lower_threshold_is_one(self):
        lo, _hi = DIRECTION_DEVIATION_THRESHOLDS
        assert _quantize_axis(lo, DIRECTION_DEVIATION_THRESHOLDS) == 1
        assert _quantize_axis(-lo, DIRECTION_DEVIATION_THRESHOLDS) == -1

    def test_direction_below_upper_threshold_is_one(self):
        _lo, hi = DIRECTION_DEVIATION_THRESHOLDS
        assert _quantize_axis(hi - 0.01, DIRECTION_DEVIATION_THRESHOLDS) == 1
        assert _quantize_axis(-(hi - 0.01), DIRECTION_DEVIATION_THRESHOLDS) == -1

    def test_direction_at_upper_threshold_is_two(self):
        _lo, hi = DIRECTION_DEVIATION_THRESHOLDS
        assert _quantize_axis(hi, DIRECTION_DEVIATION_THRESHOLDS) == 2
        assert _quantize_axis(-hi, DIRECTION_DEVIATION_THRESHOLDS) == -2

    def test_direction_large_delta_is_two(self):
        _lo, hi = DIRECTION_DEVIATION_THRESHOLDS
        assert _quantize_axis(hi * 5, DIRECTION_DEVIATION_THRESHOLDS) == 2
        assert _quantize_axis(-hi * 5, DIRECTION_DEVIATION_THRESHOLDS) == -2

    def test_depth_ladder_boundaries(self):
        """Depth ladder has its own boundaries, independent of direction (AC-1c)."""
        lo, hi = DEPTH_DEVIATION_THRESHOLDS
        assert _quantize_axis(lo - 0.01, DEPTH_DEVIATION_THRESHOLDS) == 0
        assert _quantize_axis(lo, DEPTH_DEVIATION_THRESHOLDS) == 1
        assert _quantize_axis(hi - 0.01, DEPTH_DEVIATION_THRESHOLDS) == 1
        assert _quantize_axis(hi, DEPTH_DEVIATION_THRESHOLDS) == 2
        assert _quantize_axis(-lo, DEPTH_DEVIATION_THRESHOLDS) == -1
        assert _quantize_axis(-hi, DEPTH_DEVIATION_THRESHOLDS) == -2


# ---------------------------------------------------------------------------
# Stage B: swappable zone-assignment seam + responsibility seam (AC-1b)
# ---------------------------------------------------------------------------


class TestZoneAssignmentSeam:
    def test_assign_zone_returns_dataclass(self):
        za = assign_zone(50.0, 100.0)
        assert isinstance(za, ZoneAssignment)
        assert za.zone in {"left", "center", "right"}

    def test_assign_zone_left_field(self):
        assert assign_zone(50.0, 100.0).zone == "left"

    def test_assign_zone_right_field(self):
        assert assign_zone(270.0, 100.0).zone == "right"

    def test_assign_zone_center_field(self):
        svg_x, _ = _raw_to_svg(160.0, 100.0)
        assert assign_zone(160.0, 100.0).zone == "center"
        assert 155 <= svg_x <= 165


class TestResponsibilitySeam:
    """The swappable per-position responsibility-subset seam (epic TN-3 Stage B)."""

    def test_depth_band_threshold(self):
        assert _depth_band(INFIELD_OUTFIELD_SVG_Y_THRESHOLD) == "infield"
        assert _depth_band(INFIELD_OUTFIELD_SVG_Y_THRESHOLD - 0.01) == "outfield"
        assert _depth_band(295.0) == "infield"   # home plate svg y
        assert _depth_band(100.0) == "outfield"  # deep CF

    def test_bips_for_position_lf_takes_only_left_outfield(self):
        events = [
            {"x": 50.0, "y": 100.0, "play_type": "fly_ball"},      # left outfield
            {"x": 270.0, "y": 100.0, "play_type": "fly_ball"},     # right outfield
            {"x": 75.0, "y": 180.0, "play_type": "ground_ball"},   # left infield
        ]
        subset = bips_for_position(events, "LF")
        assert len(subset) == 1
        assert subset[0]["x"] == 50.0

    def test_bips_for_position_ss_takes_left_and_center_infield(self):
        events = [
            {"x": 75.0, "y": 180.0, "play_type": "ground_ball"},   # left infield
            {"x": 160.0, "y": 180.0, "play_type": "line_drive"},   # center infield
            {"x": 245.0, "y": 180.0, "play_type": "ground_ball"},  # right infield (not SS)
            {"x": 50.0, "y": 100.0, "play_type": "fly_ball"},      # left outfield (not SS)
        ]
        subset = bips_for_position(events, "SS")
        xs = sorted(ev["x"] for ev in subset)
        assert xs == [75.0, 160.0]

    def test_bips_for_position_3b_takes_only_left_infield(self):
        events = [
            {"x": 75.0, "y": 180.0, "play_type": "ground_ball"},   # left infield -> 3B ✓
            {"x": 160.0, "y": 180.0, "play_type": "line_drive"},   # center infield (not 3B)
            {"x": 50.0, "y": 100.0, "play_type": "fly_ball"},      # left outfield (not 3B)
        ]
        subset = bips_for_position(events, "3B")
        assert len(subset) == 1
        assert subset[0]["x"] == 75.0

    def test_bips_for_position_null_coords_skipped(self):
        events = [
            {"x": None, "y": None, "play_type": None},
            {"x": 50.0, "y": 100.0, "play_type": "fly_ball"},
        ]
        subset = bips_for_position(events, "LF")
        assert len(subset) == 1


# ---------------------------------------------------------------------------
# Depth-from-contact-type knob (AC-11)
# ---------------------------------------------------------------------------


class TestDepthFromContactType:
    def test_ground_ball_is_in(self):
        assert _depth_from_contact_type("gb") == "in"

    def test_bunt_is_in(self):
        assert _depth_from_contact_type("bu") == "in"

    def test_line_drive_is_normal(self):
        assert _depth_from_contact_type("ld") == "normal"

    def test_fly_ball_is_deep(self):
        assert _depth_from_contact_type("fb") == "deep"

    def test_popup_is_deep(self):
        assert _depth_from_contact_type("pu") == "deep"

    def test_unknown_falls_back_to_normal(self):
        assert _depth_from_contact_type("???") == "normal"


# ---------------------------------------------------------------------------
# MIXED rule adjacency (AC-4, TN-4a)
# ---------------------------------------------------------------------------


class TestAdjacencyLattice:
    def test_lattice_chain_order(self):
        assert ADJACENCY_LATTICE == (
            "LEFT_DEEP", "LEFT", "LEFT_SHALLOW",
            "TRUE",
            "RIGHT_SHALLOW", "RIGHT", "RIGHT_DEEP",
        )

    def test_adjacent_neighbors_are_adjacent(self):
        assert _are_adjacent("LEFT_SHALLOW", "TRUE")
        assert _are_adjacent("LEFT", "LEFT_SHALLOW")
        assert _are_adjacent("RIGHT_SHALLOW", "TRUE")
        assert _are_adjacent("LEFT_SHALLOW", "LEFT")

    def test_non_adjacent_pairs(self):
        assert not _are_adjacent("LEFT_DEEP", "RIGHT")
        assert not _are_adjacent("LEFT", "RIGHT_SHALLOW")
        assert not _are_adjacent("LEFT", "RIGHT_DEEP")

    def test_team_state_call_all_true(self):
        assert _compute_team_state_call(["TRUE"] * 6) == "TRUE"

    def test_team_state_call_single_named_state(self):
        assert _compute_team_state_call(["LEFT"] * 6) == "LEFT"

    def test_team_state_call_with_true_positions_still_named(self):
        # TRUE positions don't force MIXED (TN-4a).
        assert _compute_team_state_call(
            ["LEFT", "LEFT", "TRUE", "TRUE", "TRUE", "TRUE"]
        ) == "LEFT"

    def test_team_state_call_adjacent_states_picks_dominant(self):
        # LEFT and LEFT_SHALLOW are adjacent -> dominant LEFT wins.
        assert _compute_team_state_call(
            ["LEFT", "LEFT", "LEFT", "LEFT_SHALLOW", "TRUE", "TRUE"]
        ) == "LEFT"

    def test_team_state_call_mixed_on_non_adjacent_pair(self):
        # LEFT_DEEP and RIGHT_SHALLOW are far apart -> MIXED.
        assert _compute_team_state_call(
            ["LEFT_DEEP", "TRUE", "RIGHT_SHALLOW", "TRUE", "TRUE", "TRUE"]
        ) == "MIXED"

    def test_team_state_call_mixed_left_and_right(self):
        assert _compute_team_state_call(
            ["LEFT", "RIGHT", "TRUE", "TRUE", "TRUE", "TRUE"]
        ) == "MIXED"


# ---------------------------------------------------------------------------
# Direction gate -- unit test (AC-5)
# ---------------------------------------------------------------------------


class TestDirectionGateUnit:
    """Direct unit tests of `_direction_shade_from_dominant`.

    The strict per-zone 4-BIP and 35% thresholds are otherwise hard to
    reach end-to-end with v1's narrow responsibility sectors (each
    position has at most two cells, with the non-target cell being
    ``center``, so once L/R is dominant in a subset its share is almost
    always well above 35%). The helper is unit-tested here so the gate
    is verified directly and to keep the recalibration path open for
    future seam swaps.
    """

    def test_dominant_zone_center_never_triggers_shade(self):
        assert _direction_shade_from_dominant("center", 50, 50) is None

    def test_dominant_left_passes_both_gates(self):
        assert _direction_shade_from_dominant("left", 4, 11) == "left"  # 36%

    def test_dominant_right_passes_both_gates(self):
        assert _direction_shade_from_dominant("right", 5, 12) == "right"  # 41%

    def test_dominant_zone_below_min_bip_fails(self):
        """4-BIP gate: count must be >= ZONE_MIN_BIP (4)."""
        assert _direction_shade_from_dominant("left", ZONE_MIN_BIP - 1, 5) is None

    def test_dominant_zone_below_concentration_fails(self):
        """35% gate: dominant share must be >= ZONE_MIN_CONCENTRATION."""
        # 4 / 13 = 30.7%, below 35%.
        assert _direction_shade_from_dominant("left", 4, 13) is None

    def test_dominant_zone_at_4_bip_passes_when_share_high(self):
        # 4 / 10 = 40% (>=35%) AND count==4 (>=4). Should pass.
        assert _direction_shade_from_dominant("left", 4, 10) == "left"

    def test_zero_total_returns_none_no_division_error(self):
        assert _direction_shade_from_dominant("left", 0, 0) is None


# ---------------------------------------------------------------------------
# Sample gate boundaries -- per-position re-evaluation (AC-2, AC-3, AC-11)
# ---------------------------------------------------------------------------


class TestSampleGates:
    def test_thin_batter_writes_all_six_rows_true_isthin(self, db):
        """AC-2: <10 BIP -> all 6 rows TRUE, is_thin=1, batter never skipped."""
        _seed_base(db)
        batter = "bat-thin"
        _seed_player(db, batter)
        for i in range(5):
            _insert_left_outfield_event(db, batter, event_id=f"thin-{i}")
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        assert len(results) == 1
        rows = results[0].per_position_rows
        assert len(rows) == 6
        for r in rows:
            assert r.call_state == "TRUE"
            assert r.is_thin == 1
            assert r.direction_shade is None
            assert r.depth_shade is None
            assert r.direction_deviation is None
            assert r.depth_deviation is None
        assert {r.position for r in rows} == set(COVERED_POSITIONS)

    def test_direction_only_at_10_to_24_subset(self, db):
        """AC-3: 10-24 BIP per-position subset -> direction lean, depth NULL."""
        _seed_base(db)
        batter = "bat-mid"
        _seed_player(db, batter)
        # 15 left-OUTFIELD events: only LF's subset is populated.
        for i in range(15):
            _insert_left_outfield_event(db, batter, event_id=f"mid-{i}")
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        result = results[0]
        # bip_count is per-batter (denormalized).
        for r in result.per_position_rows:
            assert r.bip_count == 15
            assert r.is_thin == 0
        # LF takes the direction lean; others are TRUE (empty subset).
        lf = _row_by_position(result, "LF")
        assert lf.call_state == "LEFT"
        assert lf.direction_shade == "left"
        assert lf.depth_shade is None
        assert lf.direction_deviation is not None
        assert lf.depth_deviation is None
        for position in ("SS", "2B", "3B", "CF", "RF"):
            other = _row_by_position(result, position)
            assert other.call_state == "TRUE"
            assert other.direction_shade is None

    def test_full_call_state_at_25_plus_subset(self, db):
        """AC-3: 25+ subset BIP -> depth populated for that position."""
        _seed_base(db)
        batter = "bat-25"
        _seed_player(db, batter)
        # 25 left-outfield GB events -> LF subset=25, dominant CT=gb.
        for i in range(25):
            _insert_left_outfield_event(
                db, batter, play_type="ground_ball", event_id=f"25-{i}"
            )
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        lf = _row_by_position(results[0], "LF")
        assert lf.bip_count == 25
        assert lf.direction_shade == "left"
        assert lf.depth_shade == "in"
        assert lf.call_state == "LEFT_SHALLOW"
        assert lf.direction_deviation is not None
        assert lf.depth_deviation is not None
        # Other positions still TRUE.
        for position in ("SS", "2B", "3B", "CF", "RF"):
            other = _row_by_position(results[0], position)
            assert other.call_state == "TRUE"

    def test_boundary_at_thin_threshold_subset_count(self, db):
        """LF subset == BIP_THIN_THRESHOLD -> exits the thin tier for LF."""
        _seed_base(db)
        batter = "bat-10"
        _seed_player(db, batter)
        for i in range(BIP_THIN_THRESHOLD):
            _insert_left_outfield_event(db, batter, event_id=f"b10-{i}")
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        lf = _row_by_position(results[0], "LF")
        assert lf.is_thin == 0  # batter-level
        assert lf.call_state == "LEFT"
        assert lf.depth_shade is None

    def test_boundary_just_below_thin_threshold_subset(self, db):
        """Subset < BIP_THIN_THRESHOLD -> per-position TRUE (whole batter thin)."""
        _seed_base(db)
        batter = "bat-9"
        _seed_player(db, batter)
        for i in range(BIP_THIN_THRESHOLD - 1):
            _insert_left_outfield_event(db, batter, event_id=f"b9-{i}")
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        for r in results[0].per_position_rows:
            assert r.is_thin == 1
            assert r.call_state == "TRUE"

    def test_boundary_just_below_depth_threshold_subset(self, db):
        """Subset == BIP_DEPTH_THRESHOLD - 1 -> direction lean, depth NULL."""
        _seed_base(db)
        batter = "bat-24"
        _seed_player(db, batter)
        for i in range(BIP_DEPTH_THRESHOLD - 1):
            _insert_left_outfield_event(
                db, batter, play_type="ground_ball", event_id=f"b24-{i}"
            )
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        lf = _row_by_position(results[0], "LF")
        assert lf.bip_count == BIP_DEPTH_THRESHOLD - 1
        assert lf.depth_shade is None
        assert lf.depth_deviation is None
        assert lf.call_state == "LEFT"


# ---------------------------------------------------------------------------
# Per-zone gate behaviour -- center dominance + L/R unreachability comment
# ---------------------------------------------------------------------------


class TestPerZoneGateBehaviour:
    """The strict 4-BIP / 35% per-zone gates fire on the dominant L/R zone
    within a position's subset. With v1's narrow responsibility sectors
    (single-zone outfielders + two-zone middle infielders) the gate
    rarely fires end-to-end; the unit-level coverage lives in
    :class:`TestDirectionGateUnit`. The end-to-end tests below cover the
    observable behaviours that ARE reachable from real data:
    center-dominance suppresses an L/R shade.
    """

    def test_center_dominance_in_ss_subset_does_not_shade(self, db):
        """When SS subset's dominant zone is center, SS plays straight up."""
        _seed_base(db)
        batter = "bat-ss-center"
        _seed_player(db, batter)
        # SS subset = (left, infield) U (center, infield).
        # 3 left + 7 center events -> SS subset = 10, dominant=center.
        for i in range(3):
            _insert_left_infield_event(db, batter, event_id=f"ssc-l-{i}")
        for i in range(7):
            _insert_center_infield_event(db, batter, event_id=f"ssc-c-{i}")
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        ss = _row_by_position(results[0], "SS")
        assert ss.call_state == "TRUE"
        assert ss.direction_shade is None

    def test_zone_passes_gate_when_left_dominant_in_subset(self, db):
        """Left dominant in SS subset (well above 4-BIP and 35%) -> SS=LEFT."""
        _seed_base(db)
        batter = "bat-ss-left"
        _seed_player(db, batter)
        # 8 left + 3 center infield events -> SS subset = 11, dominant=left (73%).
        for i in range(8):
            _insert_left_infield_event(db, batter, event_id=f"ssl-{i}")
        for i in range(3):
            _insert_center_infield_event(db, batter, event_id=f"ssl-c-{i}")
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        ss = _row_by_position(results[0], "SS")
        assert ss.direction_shade == "left"
        assert ss.call_state == "LEFT"


# ---------------------------------------------------------------------------
# Per-position re-evaluation -- different call_states for same batter (AC-4)
# ---------------------------------------------------------------------------


class TestPerPositionReEvaluation:
    def test_different_per_position_call_states_same_batter(self, db):
        """One batter's BIPs naturally produce different per-position call_states.

        12 left-infield events -> SS=LEFT, 3B=LEFT, others (2B, LF, CF, RF)=TRUE.
        Same batter, different per-position outputs.
        """
        _seed_base(db)
        batter = "bat-diff"
        _seed_player(db, batter)
        for i in range(12):
            _insert_left_infield_event(db, batter, event_id=f"diff-{i}")
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        ss = _row_by_position(results[0], "SS")
        third = _row_by_position(results[0], "3B")
        second = _row_by_position(results[0], "2B")
        lf = _row_by_position(results[0], "LF")
        cf = _row_by_position(results[0], "CF")
        rf = _row_by_position(results[0], "RF")
        # SS and 3B both share (left, infield) -> direction lean fires.
        assert ss.call_state == "LEFT"
        assert third.call_state == "LEFT"
        assert ss.direction_shade == "left"
        assert third.direction_shade == "left"
        # 2B's subset is empty (it covers center/right infield).
        assert second.call_state == "TRUE"
        # Outfielders have empty subsets too.
        assert lf.call_state == "TRUE"
        assert cf.call_state == "TRUE"
        assert rf.call_state == "TRUE"
        # team_state_call: qualifying = [LEFT, LEFT], adjacent -> LEFT.
        assert results[0].team_state_call == "LEFT"

    def test_split_lineup_produces_different_call_states_per_position(self, db):
        """Mixed BIP profile yields different per-position calls.

        15 right-infield events -> 2B=RIGHT. Others=TRUE.
        """
        _seed_base(db)
        batter = "bat-mixed-positions"
        _seed_player(db, batter)
        for i in range(15):
            _insert_right_infield_event(db, batter, event_id=f"mix-{i}")
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        second = _row_by_position(results[0], "2B")
        assert second.call_state == "RIGHT"
        assert second.direction_shade == "right"
        # SS doesn't include right-infield in responsibility -> subset empty.
        ss = _row_by_position(results[0], "SS")
        assert ss.call_state == "TRUE"


class TestEndToEndMixed:
    def test_end_to_end_mixed_via_per_position_reeval(self, db):
        """A batter whose per-position subsets produce non-adjacent calls
        triggers ``team_state_call='MIXED'`` end-to-end through
        ``compute_positioning`` (AC-4)."""
        _seed_base(db)
        batter = "bat-mixed-e2e"
        _seed_player(db, batter)
        # 25 left-outfield FB -> LF subset=25, depth gate fires -> LF=LEFT_DEEP
        # 25 right-outfield FB -> RF subset=25 -> RF=RIGHT_DEEP
        # LEFT_DEEP and RIGHT_DEEP are non-adjacent (distance 6 in lattice) -> MIXED
        for i in range(25):
            _insert_left_outfield_event(
                db, batter, play_type="fly_ball", event_id=f"e2e-l-{i}"
            )
        for i in range(25):
            _insert_right_outfield_event(
                db, batter, play_type="fly_ball", event_id=f"e2e-r-{i}"
            )
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        result = results[0]

        lf = _row_by_position(result, "LF")
        rf = _row_by_position(result, "RF")
        assert lf.call_state == "LEFT_DEEP"
        assert rf.call_state == "RIGHT_DEEP"

        # team_state_call replicated MIXED onto all 6 rows.
        assert result.team_state_call == "MIXED"
        for r in result.per_position_rows:
            assert r.team_state_call == "MIXED"

        # Per-position rows still carry differing individual call_state values.
        call_states = {r.position: r.call_state for r in result.per_position_rows}
        assert call_states["LF"] == "LEFT_DEEP"
        assert call_states["RF"] == "RIGHT_DEEP"
        for position in ("SS", "2B", "3B", "CF"):
            assert call_states[position] == "TRUE"

        # Verify persistence to DB matches the in-memory result.
        db_rows = db.execute(
            "SELECT position, call_state, team_state_call FROM batter_positioning "
            "WHERE player_id = ? ORDER BY position",
            (batter,),
        ).fetchall()
        db_call_states = {r["position"]: r["call_state"] for r in db_rows}
        db_team_states = {r["team_state_call"] for r in db_rows}
        assert db_call_states["LF"] == "LEFT_DEEP"
        assert db_call_states["RF"] == "RIGHT_DEEP"
        assert db_call_states["SS"] == "TRUE"
        assert db_team_states == {"MIXED"}


# ---------------------------------------------------------------------------
# Stage A optimal-point: signed deltas and ordinal buckets (AC-1a, AC-1c)
# ---------------------------------------------------------------------------


class TestStageADeviations:
    def test_deviation_set_only_for_positions_with_direction_shade(self, db):
        """direction_deviation is non-NULL exactly when direction_shade is non-NULL."""
        _seed_base(db)
        batter = "bat-dev"
        _seed_player(db, batter)
        # 12 left-outfield -> LF takes the lean; others stay TRUE.
        for i in range(12):
            _insert_left_outfield_event(db, batter, event_id=f"dev-{i}")
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        lf = _row_by_position(results[0], "LF")
        assert lf.direction_deviation is not None
        assert isinstance(lf.direction_deviation, int)
        assert lf.direction_deviation in (-2, -1, 0, 1, 2)
        # depth gate not met (12 < 25): depth_deviation NULL.
        assert lf.depth_deviation is None
        for position in ("SS", "2B", "3B", "CF", "RF"):
            other = _row_by_position(results[0], position)
            assert other.direction_deviation is None
            assert other.depth_deviation is None

    def test_deviation_null_when_call_is_true_thin_batter(self, db):
        """Thin batter -> all positions TRUE -> all deviations NULL."""
        _seed_base(db)
        batter = "bat-true"
        _seed_player(db, batter)
        for i in range(3):
            _insert_left_outfield_event(db, batter, event_id=f"t-{i}")
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        for r in results[0].per_position_rows:
            assert r.call_state == "TRUE"
            assert r.direction_deviation is None
            assert r.depth_deviation is None

    def test_depth_deviation_null_when_depth_shade_null(self, db):
        """AC-1a NULL rule: depth_deviation NULL iff depth_shade NULL."""
        _seed_base(db)
        batter = "bat-no-depth"
        _seed_player(db, batter)
        # 12 LF events: direction lean qualifies, depth gate (25) does not.
        for i in range(12):
            _insert_left_outfield_event(db, batter, event_id=f"nd-{i}")
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        lf = _row_by_position(results[0], "LF")
        assert lf.depth_shade is None
        assert lf.depth_deviation is None
        assert lf.direction_deviation is not None

    def test_deviation_signed_axes(self):
        """Sign convention: direction <0=toward LF, depth <0=shallower."""
        lo_dir, hi_dir = DIRECTION_DEVIATION_THRESHOLDS
        assert _quantize_axis(-(hi_dir + 1), DIRECTION_DEVIATION_THRESHOLDS) == -2
        assert _quantize_axis(hi_dir + 1, DIRECTION_DEVIATION_THRESHOLDS) == 2
        lo_dep, hi_dep = DEPTH_DEVIATION_THRESHOLDS
        assert _quantize_axis(-(hi_dep + 1), DEPTH_DEVIATION_THRESHOLDS) == -2
        assert _quantize_axis(hi_dep + 1, DEPTH_DEVIATION_THRESHOLDS) == 2


# ---------------------------------------------------------------------------
# Stage C quantization to each named state (AC-11)
# ---------------------------------------------------------------------------


class TestQuantizationToNamedStates:
    """Each named call_state value is reached end-to-end via the engine."""

    def test_left_shallow_via_ground_balls(self, db):
        """LF subset of 30 GB -> LEFT_SHALLOW for LF (other positions TRUE)."""
        _seed_base(db)
        batter = "bat-LS"
        _seed_player(db, batter)
        for i in range(30):
            _insert_left_outfield_event(
                db, batter, play_type="ground_ball", event_id=f"LS-{i}"
            )
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        lf = _row_by_position(results[0], "LF")
        assert lf.call_state == "LEFT_SHALLOW"

    def test_left_deep_via_fly_balls(self, db):
        _seed_base(db)
        batter = "bat-LD"
        _seed_player(db, batter)
        for i in range(30):
            _insert_left_outfield_event(
                db, batter, play_type="fly_ball", event_id=f"LD-{i}"
            )
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        lf = _row_by_position(results[0], "LF")
        assert lf.call_state == "LEFT_DEEP"
        assert lf.depth_shade == "deep"

    def test_left_normal_via_line_drives(self, db):
        _seed_base(db)
        batter = "bat-L-LD"
        _seed_player(db, batter)
        for i in range(30):
            _insert_left_outfield_event(
                db, batter, play_type="line_drive", event_id=f"LN-{i}"
            )
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        lf = _row_by_position(results[0], "LF")
        assert lf.call_state == "LEFT"
        assert lf.depth_shade == "normal"

    def test_right_shallow(self, db):
        _seed_base(db)
        batter = "bat-RS"
        _seed_player(db, batter)
        for i in range(30):
            _insert_right_outfield_event(
                db, batter, play_type="ground_ball", event_id=f"RS-{i}"
            )
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        rf = _row_by_position(results[0], "RF")
        assert rf.call_state == "RIGHT_SHALLOW"

    def test_right_deep(self, db):
        _seed_base(db)
        batter = "bat-RD"
        _seed_player(db, batter)
        for i in range(30):
            _insert_right_outfield_event(
                db, batter, play_type="fly_ball", event_id=f"RD-{i}"
            )
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        rf = _row_by_position(results[0], "RF")
        assert rf.call_state == "RIGHT_DEEP"

    def test_right_normal_via_line_drives(self, db):
        """Plain RIGHT (right-field LDs at normal depth) -- symmetric to test_left_normal_via_line_drives."""
        _seed_base(db)
        batter = "bat-R-LD"
        _seed_player(db, batter)
        for i in range(30):
            _insert_right_outfield_event(
                db, batter, play_type="line_drive", event_id=f"RN-{i}"
            )
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        rf = _row_by_position(results[0], "RF")
        assert rf.call_state == "RIGHT"
        assert rf.depth_shade == "normal"

    def test_true_when_center_dominates(self, db):
        """30 CF events -> CF subset=30 all center -> CF=TRUE (center never shades)."""
        _seed_base(db)
        batter = "bat-CTR"
        _seed_player(db, batter)
        for i in range(30):
            _insert_center_outfield_event(db, batter, event_id=f"CTR-{i}")
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        for r in results[0].per_position_rows:
            assert r.call_state == "TRUE"
            assert r.direction_shade is None


# ---------------------------------------------------------------------------
# team_state_call denormalization on persisted rows (AC-6)
# ---------------------------------------------------------------------------


class TestTeamStateCallDenormalization:
    def test_team_state_call_same_on_all_six_rows(self, db):
        _seed_base(db)
        batter = "bat-team"
        _seed_player(db, batter)
        for i in range(30):
            _insert_left_outfield_event(
                db, batter, play_type="ground_ball", event_id=f"team-{i}"
            )
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        team_call = results[0].team_state_call
        assert team_call == "LEFT_SHALLOW"
        for r in results[0].per_position_rows:
            assert r.team_state_call == team_call

    def test_team_state_call_replicates_on_db_rows(self, db):
        _seed_base(db)
        batter = "bat-persist"
        _seed_player(db, batter)
        for i in range(30):
            _insert_left_outfield_event(
                db, batter, play_type="fly_ball", event_id=f"persist-{i}"
            )
        db.commit()
        compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        rows = db.execute(
            "SELECT position, call_state, team_state_call FROM batter_positioning "
            "WHERE player_id = ?",
            (batter,),
        ).fetchall()
        assert len(rows) == 6
        team_calls = {r["team_state_call"] for r in rows}
        assert team_calls == {"LEFT_DEEP"}
        positions = {r["position"] for r in rows}
        assert positions == set(COVERED_POSITIONS)

    def test_team_state_call_true_replicates_on_all_rows(self, db):
        _seed_base(db)
        batter = "bat-true-team"
        _seed_player(db, batter)
        for i in range(5):
            _insert_left_outfield_event(db, batter, event_id=f"thin-{i}")
        db.commit()
        compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        rows = db.execute(
            "SELECT team_state_call FROM batter_positioning WHERE player_id = ?",
            (batter,),
        ).fetchall()
        assert len(rows) == 6
        assert all(r["team_state_call"] == "TRUE" for r in rows)


# ---------------------------------------------------------------------------
# NULL season_id skip (AC-8)
# ---------------------------------------------------------------------------


class TestNullSeasonIdSkip:
    def test_null_season_rows_skipped_and_logged(self, db, caplog):
        _seed_base(db)
        batter = "bat-null-season"
        _seed_player(db, batter)
        for i in range(12):
            _insert_left_outfield_event(db, batter, event_id=f"null-ok-{i}")
        for i in range(3):
            _insert_left_outfield_event(
                db, batter, season_id=None, event_id=f"null-skip-{i}"
            )
        db.commit()

        caplog.set_level(logging.WARNING, logger="src.reports.positioning")
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        # bip_count (per-batter) is 12; NULL-season rows excluded.
        for r in results[0].per_position_rows:
            assert r.bip_count == 12
        warnings = [
            rec for rec in caplog.records
            if rec.levelno == logging.WARNING and "NULL season_id" in rec.getMessage()
        ]
        assert warnings, "expected a WARNING for NULL season_id skip"
        assert "3" in warnings[0].getMessage()

    def test_other_season_id_rows_excluded(self, db):
        _seed_base(db)
        batter = "bat-cross-season"
        _seed_player(db, batter)
        for i in range(10):
            _insert_left_outfield_event(db, batter, event_id=f"in-season-{i}")
        for i in range(5):
            _insert_left_outfield_event(
                db, batter, season_id=_OTHER_SEASON_ID,
                event_id=f"out-of-season-{i}",
            )
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        for r in results[0].per_position_rows:
            assert r.bip_count == 10


# ---------------------------------------------------------------------------
# Edge cases (AC-7)
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_spray_data_produces_empty_result(self, db):
        _seed_base(db)
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        assert results == []
        assert db.execute("SELECT COUNT(*) FROM batter_positioning").fetchone()[0] == 0

    def test_null_coordinate_hr_counted_only_in_hr_count(self, db):
        _seed_base(db)
        batter = "bat-hr"
        _seed_player(db, batter)
        for i in range(5):
            _insert_left_outfield_event(db, batter, event_id=f"hr-bip-{i}")
        _insert_event(db, player_id=batter, x=None, y=None,
                      play_result="home_run", play_type=None,
                      event_id="hr-null-1")
        _insert_event(db, player_id=batter, x=None, y=None,
                      play_result="home_run", play_type=None,
                      event_id="hr-null-2")
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        rows = results[0].per_position_rows
        for r in rows:
            assert r.bip_count == 5
            assert r.hr_count == 2
            assert r.is_thin == 1  # 5 BIP is thin per-batter
            assert r.call_state == "TRUE"

    def test_single_zone_batter_produces_full_lf_concentration(self, db):
        _seed_base(db)
        batter = "bat-single-zone"
        _seed_player(db, batter)
        for i in range(12):
            _insert_left_outfield_event(db, batter, event_id=f"sz-{i}")
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        lf = _row_by_position(results[0], "LF")
        # LF subset = 12, all in left -> 100% concentration.
        assert lf.zone_concentration == 1.0
        assert lf.call_state == "LEFT"


# ---------------------------------------------------------------------------
# Idempotent rebuild: delete-then-insert (AC-6)
# ---------------------------------------------------------------------------


class TestIdempotentRebuild:
    def test_second_run_replaces_prior_rows(self, db):
        _seed_base(db)
        batter_a = "bat-A"
        batter_b = "bat-B"
        _seed_player(db, batter_a)
        _seed_player(db, batter_b)
        for i in range(15):
            _insert_left_outfield_event(db, batter_a, event_id=f"A1-{i}")
            _insert_right_outfield_event(db, batter_b, event_id=f"B1-{i}")
        db.commit()
        compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        # 2 batters * 6 positions = 12 rows.
        assert db.execute(
            "SELECT COUNT(*) FROM batter_positioning WHERE team_id = ? AND season_id = ?",
            (_OPPONENT_TEAM_ID, _SEASON_ID),
        ).fetchone()[0] == 12

        # Remove batter_a's spray rows; rebuild.
        db.execute("DELETE FROM spray_charts WHERE player_id = ?", (batter_a,))
        db.commit()
        compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)

        remaining = db.execute(
            "SELECT player_id, COUNT(*) c FROM batter_positioning "
            "WHERE team_id = ? AND season_id = ? GROUP BY player_id",
            (_OPPONENT_TEAM_ID, _SEASON_ID),
        ).fetchall()
        assert len(remaining) == 1
        assert remaining[0]["player_id"] == batter_b
        assert remaining[0]["c"] == 6

    def test_rebuild_writes_all_columns(self, db):
        _seed_base(db)
        batter = "bat-all-cols"
        _seed_player(db, batter)
        for i in range(30):
            _insert_left_outfield_event(
                db, batter, play_type="ground_ball", event_id=f"all-{i}"
            )
        db.commit()
        compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        rows = db.execute(
            """
            SELECT position, call_state, team_state_call, direction_shade,
                   depth_shade, bip_count, hr_count, is_thin, zone_concentration,
                   direction_deviation, depth_deviation
            FROM batter_positioning WHERE player_id = ?
            """,
            (batter,),
        ).fetchall()
        by_position = {r["position"]: r for r in rows}
        assert len(rows) == 6
        # LF gets the populated call (responsibility match).
        lf = by_position["LF"]
        assert lf["call_state"] == "LEFT_SHALLOW"
        assert lf["team_state_call"] == "LEFT_SHALLOW"
        assert lf["direction_shade"] == "left"
        assert lf["depth_shade"] == "in"
        assert lf["bip_count"] == 30
        assert lf["hr_count"] == 0
        assert lf["is_thin"] == 0
        assert lf["zone_concentration"] is not None
        assert lf["direction_deviation"] is not None
        assert lf["depth_deviation"] is not None
        # Non-LF positions land at TRUE but still carry the denormalized fields.
        for position in ("SS", "2B", "3B", "CF", "RF"):
            r = by_position[position]
            assert r["call_state"] == "TRUE"
            assert r["team_state_call"] == "LEFT_SHALLOW"
            assert r["bip_count"] == 30
            assert r["hr_count"] == 0
            assert r["is_thin"] == 0
            assert r["direction_deviation"] is None
            assert r["depth_deviation"] is None

    def test_rebuild_clears_perspective_that_no_longer_has_data(self, db):
        """Codex finding #1: a perspective that previously had rows in
        `batter_positioning` but is no longer present in current spray
        data must be cleared. The DELETE scope is (team_id, season_id),
        not (team_id, season_id, perspective_team_id), so all stale
        perspectives are removed on rebuild."""
        _seed_base(db)
        batter = "bat-multi-perspective"
        _seed_player(db, batter)
        # First run: insert spray events under BOTH perspectives.
        for i in range(15):
            _insert_left_outfield_event(
                db, batter,
                perspective_team_id=_PERSPECTIVE_ID, event_id=f"P1-{i}",
            )
            _insert_right_outfield_event(
                db, batter,
                perspective_team_id=_OTHER_PERSPECTIVE_ID, event_id=f"P2-{i}",
            )
        db.commit()
        compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        # 2 perspectives * 6 positions = 12 rows.
        before = db.execute(
            "SELECT COUNT(*) FROM batter_positioning "
            "WHERE team_id = ? AND season_id = ?",
            (_OPPONENT_TEAM_ID, _SEASON_ID),
        ).fetchone()[0]
        assert before == 12

        # Now remove perspective B's spray data and rebuild.
        db.execute(
            "DELETE FROM spray_charts WHERE perspective_team_id = ?",
            (_OTHER_PERSPECTIVE_ID,),
        )
        db.commit()
        compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)

        # Perspective A's 6 rows remain; perspective B's 6 rows are gone.
        remaining = db.execute(
            "SELECT perspective_team_id, COUNT(*) c FROM batter_positioning "
            "WHERE team_id = ? AND season_id = ? "
            "GROUP BY perspective_team_id ORDER BY perspective_team_id",
            (_OPPONENT_TEAM_ID, _SEASON_ID),
        ).fetchall()
        assert len(remaining) == 1
        assert remaining[0]["perspective_team_id"] == _PERSPECTIVE_ID
        assert remaining[0]["c"] == 6

    def test_rebuild_clears_all_rows_when_no_spray_data_remains(self, db):
        """Codex finding #1: a team that has lost all qualifying spray
        rows must have its `batter_positioning` rows cleared entirely on
        rebuild. The engine does NOT early-return when there is no data --
        it runs the DELETE-then-no-INSERT path in a single transaction."""
        _seed_base(db)
        batter = "bat-disappears"
        _seed_player(db, batter)
        # First run: populate rows.
        for i in range(15):
            _insert_left_outfield_event(db, batter, event_id=f"first-{i}")
        db.commit()
        compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        assert db.execute(
            "SELECT COUNT(*) FROM batter_positioning "
            "WHERE team_id = ? AND season_id = ?",
            (_OPPONENT_TEAM_ID, _SEASON_ID),
        ).fetchone()[0] == 6

        # Delete all spray data for this team -- zero placed events on rebuild.
        db.execute("DELETE FROM spray_charts WHERE team_id = ?",
                   (_OPPONENT_TEAM_ID,))
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)

        # Rebuild produces no results AND clears the prior rows.
        assert results == []
        remaining = db.execute(
            "SELECT COUNT(*) FROM batter_positioning "
            "WHERE team_id = ? AND season_id = ?",
            (_OPPONENT_TEAM_ID, _SEASON_ID),
        ).fetchone()[0]
        assert remaining == 0


# ---------------------------------------------------------------------------
# Multi-perspective: scope is per perspective_team_id (AC-6, TN-6)
# ---------------------------------------------------------------------------


class TestPerspectiveScoping:
    def test_two_perspectives_recompute_independently(self, db):
        _seed_base(db)
        batter = "bat-multi"
        _seed_player(db, batter)
        for i in range(15):
            _insert_left_outfield_event(
                db, batter,
                perspective_team_id=_PERSPECTIVE_ID, event_id=f"P1-{i}",
            )
            _insert_right_outfield_event(
                db, batter,
                perspective_team_id=_OTHER_PERSPECTIVE_ID, event_id=f"P2-{i}",
            )
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        assert len(results) == 2
        by_perspective = {r.perspective_team_id: r for r in results}
        # Perspective 1: only LF takes the lean.
        p1_lf = _row_by_position(by_perspective[_PERSPECTIVE_ID], "LF")
        p1_rf = _row_by_position(by_perspective[_PERSPECTIVE_ID], "RF")
        assert p1_lf.direction_shade == "left"
        assert p1_rf.call_state == "TRUE"
        # Perspective 2: only RF takes the lean.
        p2_lf = _row_by_position(by_perspective[_OTHER_PERSPECTIVE_ID], "LF")
        p2_rf = _row_by_position(by_perspective[_OTHER_PERSPECTIVE_ID], "RF")
        assert p2_rf.direction_shade == "right"
        assert p2_lf.call_state == "TRUE"
        # Persistence under both perspectives.
        counts = db.execute(
            """
            SELECT perspective_team_id, COUNT(*) c FROM batter_positioning
            WHERE team_id = ? AND season_id = ?
            GROUP BY perspective_team_id
            """,
            (_OPPONENT_TEAM_ID, _SEASON_ID),
        ).fetchall()
        assert {r["perspective_team_id"]: r["c"] for r in counts} == {
            _PERSPECTIVE_ID: 6, _OTHER_PERSPECTIVE_ID: 6,
        }


# ---------------------------------------------------------------------------
# Per-zone aggregation (epic TN-1a Tier 2 input -- still per-batter)
# ---------------------------------------------------------------------------


class TestPerZoneAggregation:
    def test_aggregation_reachable_from_result(self, db):
        _seed_base(db)
        batter = "bat-agg"
        _seed_player(db, batter)
        for i in range(6):
            _insert_left_outfield_event(
                db, batter, play_type="ground_ball", event_id=f"agg-l-gb-{i}"
            )
        for i in range(4):
            _insert_right_outfield_event(
                db, batter, play_type="fly_ball", event_id=f"agg-r-fb-{i}"
            )
        db.commit()
        results = compute_positioning(db, _OPPONENT_TEAM_ID, _SEASON_ID)
        agg: PerZoneAggregation = results[0].zone_aggregation
        assert isinstance(agg, PerZoneAggregation)
        assert agg.zone_totals.get("left") == 6
        assert agg.zone_totals.get("right") == 4
        assert agg.contact_type_totals.get("gb") == 6
        assert agg.contact_type_totals.get("fb") == 4
        keys = {(e.zone, e.contact_type) for e in agg.entries}
        assert ("left", "gb") in keys
        assert ("right", "fb") in keys
