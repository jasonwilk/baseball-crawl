"""Tests for E-229-06 coach prep page renderer.

Covers AC-9 + AC-10:
  * full state: 6 stars + outlier pills + density bg + sidebar
  * zero-coverage state (AC-7): dominant message, no field/sidebar
  * no-outliers state (AC-7a): field + stars + banner + sidebar
  * sidebar two-partition alpha sort (AC-4) + partition divider
  * cross-position collision handling (AC-8)
  * Tier 2 rationale slot rendering + collapse on None (AC-10)
  * pill format `{jersey}-{position}` per artifact §E exception table
"""

from __future__ import annotations

import sqlite3

import pytest

from src.reports.positioning import COVERED_POSITIONS
from src.reports.positioning_prep import (
    _build_sidebar_rows,
    _prep_pill_text,
    render_prep_page_context,
)
from tests.conftest import load_real_schema


# ---------------------------------------------------------------------------
# Schema + fixture helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path):
    path = tmp_path / "test.db"
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    load_real_schema(c)
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


def _seed_player(conn, player_id: str, first: str = "F", last: str = "Last"):
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, ?, ?)",
        (player_id, first, last),
    )


def _seed_roster(conn, player_id: str, jersey: str | None,
                 team_id: int = 1, season_id: str = "2026-spring-hs"):
    if jersey is not None:
        conn.execute(
            "INSERT OR IGNORE INTO team_rosters (team_id, player_id, "
            "season_id, jersey_number) VALUES (?, ?, ?, ?)",
            (team_id, player_id, season_id, jersey),
        )


def _seed_aggregate(
    conn, position: str, *,
    star_x: float = 160.0, star_y: float = 200.0,
    bip_count: int = 60, is_low_confidence: int = 0,
    team_id: int = 1, season_id: str = "2026-spring-hs",
    perspective_team_id: int = 1,
):
    conn.execute(
        """
        INSERT INTO team_position_aggregate (
            team_id, season_id, perspective_team_id, position,
            star_x, star_y, bip_count, is_low_confidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (team_id, season_id, perspective_team_id, position,
         star_x, star_y, bip_count, is_low_confidence),
    )


def _seed_batter_row(
    conn, *, player_id: str, position: str,
    direction_deviation: int = 0, depth_deviation: int = 0,
    zone_id: str | None = None, is_thin: int = 0,
    bip_count: int = 20, hr_count: int = 0,
    team_id: int = 1, season_id: str = "2026-spring-hs",
    perspective_team_id: int = 1,
):
    conn.execute(
        """
        INSERT INTO batter_positioning (
            player_id, team_id, season_id, perspective_team_id, position,
            direction_deviation, depth_deviation, zone_id,
            is_thin, bip_count, hr_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (player_id, team_id, season_id, perspective_team_id, position,
         direction_deviation, depth_deviation, zone_id,
         is_thin, bip_count, hr_count),
    )


def _seed_full_opponent(conn):
    """Seed a 6-aggregate opponent with two flagged batters + one
    all-default batter. Useful as a baseline for the full state tests.
    """
    # 6 aggregates (one per covered position), all in full tier
    # (bip_count=60, is_low_confidence=0).
    for position in COVERED_POSITIONS:
        _seed_aggregate(conn, position)

    # p1 (Ramirez, #7): flagged at LF (zone A), default elsewhere.
    _seed_player(conn, "p1", last="Ramirez")
    _seed_roster(conn, "p1", "7")
    _seed_batter_row(
        conn, player_id="p1", position="LF",
        direction_deviation=-1, depth_deviation=-1, zone_id="A",
    )
    for position in ("CF", "RF", "3B", "SS", "2B"):
        _seed_batter_row(
            conn, player_id="p1", position=position,
            direction_deviation=0, depth_deviation=0, zone_id=None,
        )

    # p2 (Davis, #11): flagged at CF (zone E) and at RF (zone H);
    # cross-position outlier (the prep-page-distinctive case).
    _seed_player(conn, "p2", last="Davis")
    _seed_roster(conn, "p2", "11")
    _seed_batter_row(
        conn, player_id="p2", position="CF",
        direction_deviation=0, depth_deviation=1, zone_id="E",
    )
    _seed_batter_row(
        conn, player_id="p2", position="RF",
        direction_deviation=1, depth_deviation=1, zone_id="H",
    )
    for position in ("LF", "3B", "SS", "2B"):
        _seed_batter_row(
            conn, player_id="p2", position=position,
            direction_deviation=0, depth_deviation=0, zone_id=None,
        )

    # p3 (Aaron, #3): all-default (no flagged cells).
    _seed_player(conn, "p3", last="Aaron")
    _seed_roster(conn, "p3", "3")
    for position in COVERED_POSITIONS:
        _seed_batter_row(
            conn, player_id="p3", position=position,
            direction_deviation=0, depth_deviation=0, zone_id=None,
        )

    conn.commit()


# ---------------------------------------------------------------------------
# Pill text (artifact §E exception table)
# ---------------------------------------------------------------------------


class TestPrepPillText:
    """AC-2: prep-page pill text format is `{jersey}-{position}` (no `#`,
    hyphen separator) per artifact §E exception table. NULL-jersey
    fallback is `{initial}-{position}`."""

    def test_jersey_position_format(self):
        text = _prep_pill_text(
            {"jersey_number": "7", "last_name": "Ramirez"}, "LF",
        )
        assert text == "7-LF"

    def test_null_jersey_uses_initial_position_format(self):
        text = _prep_pill_text(
            {"jersey_number": None, "last_name": "Wilkinson"}, "RF",
        )
        assert text == "W-RF"

    def test_empty_jersey_uses_initial(self):
        text = _prep_pill_text(
            {"jersey_number": "", "last_name": "Davis"}, "CF",
        )
        assert text == "D-CF"

    def test_no_pound_prefix(self):
        text = _prep_pill_text(
            {"jersey_number": "23", "last_name": "Thompson"}, "3B",
        )
        assert "#" not in text


# ---------------------------------------------------------------------------
# Full state
# ---------------------------------------------------------------------------


class TestFullState:
    def test_state_is_full(self, conn):
        _seed_full_opponent(conn)
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
            opponent_name="Opp Bears",
            through_date="Apr 12", game_count=8,
        )
        assert ctx["state"] == "full"

    def test_svg_contains_six_position_labels(self, conn):
        _seed_full_opponent(conn)
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        svg = ctx["svg"]
        # Each position is rendered as a small text label adjacent to its star.
        for position in COVERED_POSITIONS:
            assert f">{position}<" in svg, (
                f"position label {position!r} missing from SVG"
            )

    def test_svg_contains_cross_position_pills(self, conn):
        """p2 is flagged at CF AND RF; both pills should render."""
        _seed_full_opponent(conn)
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        svg = ctx["svg"]
        # Both prep-page pills appear (format `{jersey}-{position}`).
        assert "11-CF" in svg
        assert "11-RF" in svg

    def test_svg_contains_density_bg_when_full(self, conn):
        _seed_full_opponent(conn)
        # Seed a spray-charts row so density bg has data.
        _seed_player(conn, "p1")
        conn.execute(
            "INSERT INTO spray_charts (player_id, team_id, "
            "perspective_team_id, chart_type, play_type, play_result, "
            "x, y, season_id) VALUES ('p1', 1, 1, 'offensive', "
            "'line_drive', 'single', 160.0, 150.0, '2026-spring-hs')"
        )
        conn.commit()
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        # Density-bg opacity is 0.12.
        assert 'opacity="0.12"' in ctx["svg"]

    def test_header_includes_coverage_cue(self, conn):
        _seed_full_opponent(conn)
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
            opponent_name="Opp Bears",
            through_date="Apr 12", game_count=8,
        )
        assert ctx["header"]["opponent_name"] == "Opp Bears"
        assert ctx["header"]["coverage_cue"] == "Through Apr 12 (8 games)"

    def test_compass_legend_long_present(self, conn):
        _seed_full_opponent(conn)
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        # Artifact §F: COMPASS_LEGEND_LONG used on call sheet + prep page.
        assert ctx["compass_legend"].startswith("A in-left ·")


# ---------------------------------------------------------------------------
# Sidebar: two-partition alpha sort + partition divider (AC-4)
# ---------------------------------------------------------------------------


class TestSidebarSort:
    def test_two_partition_alpha_sort(self, conn):
        _seed_full_opponent(conn)
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        rows = ctx["sidebar_rows"]
        # Names: Aaron (#3, default), Davis (#11, flagged),
        # Ramirez (#7, flagged).
        # Partition 1 (flagged, alpha by last name): Davis, Ramirez.
        # Partition 2 (default): Aaron.
        assert [r["last_name"] for r in rows] == ["DAVIS", "RAMIREZ", "AARON"]

    def test_partition_divider_index_between_partitions(self, conn):
        _seed_full_opponent(conn)
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        # 2 flagged batters, 1 default; divider at index 2.
        assert ctx["partition_divider_index"] == 2

    def test_no_divider_when_all_one_partition(self, conn):
        # All three batters flagged: divider is None.
        _seed_full_opponent(conn)
        # Make Aaron flagged too by giving them a non-NULL zone at LF.
        conn.execute(
            "UPDATE batter_positioning SET zone_id = 'B', "
            "direction_deviation = -1 "
            "WHERE player_id = 'p3' AND position = 'LF'"
        )
        conn.commit()
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        # All flagged -> no partition divider.
        assert ctx["partition_divider_index"] is None

    def test_sidebar_cells_default_for_thin_batters(self, conn):
        # A thin (is_thin=1) batter row should still render with `·`
        # cells per AC-4 (the per-position cells are sourced from
        # batter_positioning regardless of is_thin; the thin gate only
        # blocks PILL rendering per AC-6 of E-229-04).
        # Actually -- by spec, the sidebar row matters for any batter
        # we know about. A thin batter with zone_id != NULL shouldn't
        # be flagged. Verify via the zone-grid lookup.
        _seed_full_opponent(conn)
        # Seed a thin batter with a non-NULL zone at LF.
        _seed_player(conn, "p-thin", last="Patel")
        _seed_roster(conn, "p-thin", "9")
        _seed_batter_row(
            conn, player_id="p-thin", position="LF",
            direction_deviation=-1, depth_deviation=0,
            zone_id="B", is_thin=1, bip_count=5,
        )
        for position in ("CF", "RF", "3B", "SS", "2B"):
            _seed_batter_row(
                conn, player_id="p-thin", position=position,
                direction_deviation=0, depth_deviation=0, zone_id=None,
            )
        conn.commit()
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        patel = next(r for r in ctx["sidebar_rows"]
                     if r["last_name"] == "PATEL")
        # Thin batters' zone-letter cells render as `·` (not their
        # zone letter) because the prep-page sidebar treats them as
        # team-default.
        lf_cell = next(c for c in patel["cells"] if c["position"] == "LF")
        assert lf_cell["zone_letter"] == "·"
        # And the batter is NOT flagged (no non-`·` cells).
        assert patel["is_flagged"] is False


# ---------------------------------------------------------------------------
# Zero-coverage state (AC-7)
# ---------------------------------------------------------------------------


class TestZeroCoverageState:
    def test_no_aggregate_rows_yields_zero_coverage(self, conn):
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
            opponent_name="Opp Bears",
        )
        assert ctx["state"] == "zero_coverage"

    def test_zero_coverage_svg_has_message(self, conn):
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
            opponent_name="Opp Bears",
        )
        assert "Not enough spray data" in ctx["zero_coverage_svg"]

    def test_zero_coverage_has_empty_sidebar(self, conn):
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        assert ctx["sidebar_rows"] == []

    def test_zero_coverage_renders_header(self, conn):
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
            opponent_name="Opp Bears",
            through_date="Apr 12", game_count=2,
        )
        # Header still renders (per AC-7 implicit).
        assert ctx["header"]["opponent_name"] == "Opp Bears"
        assert "Apr 12" in ctx["header"]["coverage_cue"]

    def test_low_bip_count_below_15_yields_zero_coverage(self, conn):
        # Aggregate rows exist but all have bip_count < 15.
        for position in COVERED_POSITIONS:
            _seed_aggregate(
                conn, position, bip_count=10, is_low_confidence=1,
            )
        conn.commit()
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        assert ctx["state"] == "zero_coverage"


# ---------------------------------------------------------------------------
# No-outliers state (AC-7a)
# ---------------------------------------------------------------------------


class TestNoOutliersState:
    def test_no_outliers_state_when_all_batters_at_default(self, conn):
        # Full tier (bip_count >= 15) but ALL batters' zone_id IS NULL.
        for position in COVERED_POSITIONS:
            _seed_aggregate(conn, position, bip_count=60)
        _seed_player(conn, "p1", last="Aaron")
        _seed_roster(conn, "p1", "3")
        for position in COVERED_POSITIONS:
            _seed_batter_row(
                conn, player_id="p1", position=position,
                direction_deviation=0, depth_deviation=0, zone_id=None,
            )
        conn.commit()
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        assert ctx["state"] == "no_outliers"

    def test_no_outliers_renders_banner(self, conn):
        for position in COVERED_POSITIONS:
            _seed_aggregate(conn, position, bip_count=60)
        _seed_player(conn, "p1", last="Aaron")
        _seed_roster(conn, "p1", "3")
        for position in COVERED_POSITIONS:
            _seed_batter_row(
                conn, player_id="p1", position=position,
                zone_id=None,
            )
        conn.commit()
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        assert ctx["no_outliers_banner"] is not None
        assert "No outlier batters" in ctx["no_outliers_banner"]

    def test_no_outliers_renders_field_with_stars(self, conn):
        for position in COVERED_POSITIONS:
            _seed_aggregate(conn, position, bip_count=60)
        _seed_player(conn, "p1", last="Aaron")
        _seed_roster(conn, "p1", "3")
        for position in COVERED_POSITIONS:
            _seed_batter_row(
                conn, player_id="p1", position=position,
                zone_id=None,
            )
        conn.commit()
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        # Field outline + 6 stars present.
        for position in COVERED_POSITIONS:
            assert f">{position}<" in ctx["svg"]
        assert "<polygon" in ctx["svg"]  # the star polygon


# ---------------------------------------------------------------------------
# AC-10: Tier 2 LLM rationale slot
# ---------------------------------------------------------------------------


class TestRationaleSlot:
    def test_rationale_threaded_into_row(self, conn):
        _seed_full_opponent(conn)
        rationales = {"p1": "Strong left-side pull-hitter; shade LF in."}
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
            rationales=rationales,
        )
        ramirez = next(r for r in ctx["sidebar_rows"]
                       if r["last_name"] == "RAMIREZ")
        assert ramirez["rationale"] == (
            "Strong left-side pull-hitter; shade LF in."
        )

    def test_rationale_none_when_not_provided(self, conn):
        _seed_full_opponent(conn)
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        for row in ctx["sidebar_rows"]:
            assert row["rationale"] is None

    def test_rationale_dict_missing_player_id_is_none(self, conn):
        _seed_full_opponent(conn)
        rationales = {"someone-else": "Some unrelated rationale."}
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
            rationales=rationales,
        )
        for row in ctx["sidebar_rows"]:
            assert row["rationale"] is None


# ---------------------------------------------------------------------------
# Cross-position collision handling (AC-8)
# ---------------------------------------------------------------------------


def _extract_pill_translate(svg: str, pill_text: str) -> tuple[str, str]:
    """Pull `translate(x, y)` from the <g> wrapping `pill_text`."""
    import re
    m = re.search(
        r'transform="translate\(([0-9.\-]+),\s*([0-9.\-]+)\)"'
        r'><rect[^>]*/>'
        r'<text[^>]*>' + re.escape(pill_text) + r'</text>',
        svg,
    )
    assert m, f"could not find pill {pill_text!r} translate"
    return (m.group(1), m.group(2))


class TestPillCollisionJitter:
    """AC-8 + AC-4 collision-jitter coverage. Two scenarios:

    1. Intra-position: two batters at the SAME position with identical
       deviations produce identical pre-jitter anchors; collision
       resolution must place them at different SVG coords. Covers the
       `_jersey_collision_key` primary sort (jersey ascending).
    2. Cross-position: two batters at DIFFERENT positions whose stars
       happen to coincide AND whose deviations point in the same
       direction produce identical pre-jitter anchors; collision
       resolution must place them at different SVG coords. Covers the
       secondary position-tag sort key (the `* 10 + position_index`
       packing in `_svg_prep_outlier_pills`).
    """

    def test_intra_position_collision_gets_jittered(self, conn):
        """Two batters at LF with identical deviations land on the
        same SVG anchor pre-jitter; the resolver must separate them."""
        _seed_full_opponent(conn)
        # p4 (Lopez, #5) flagged at LF zone A with the same deviation
        # as p1 (Ramirez, #7) -- identical anchor pre-jitter.
        _seed_player(conn, "p4", last="Lopez")
        _seed_roster(conn, "p4", "5")
        _seed_batter_row(
            conn, player_id="p4", position="LF",
            direction_deviation=-1, depth_deviation=-1, zone_id="A",
        )
        for position in ("CF", "RF", "3B", "SS", "2B"):
            _seed_batter_row(
                conn, player_id="p4", position=position,
                zone_id=None,
            )
        conn.commit()
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        svg = ctx["svg"]
        # Both pills rendered.
        assert "5-LF" in svg
        assert "7-LF" in svg
        # Pre-jitter both would anchor at the same position; post-jitter
        # they must differ.
        anchor_5 = _extract_pill_translate(svg, "5-LF")
        anchor_7 = _extract_pill_translate(svg, "7-LF")
        assert anchor_5 != anchor_7, (
            f"intra-position collision jitter failed: both LF pills "
            f"anchor at {anchor_5}"
        )

    def test_cross_position_collision_gets_jittered(self, conn):
        """Two batters at DIFFERENT positions whose pills project to
        the SAME SVG anchor (different stars + different deviations,
        but the projection coincides) must be separated by the jitter
        resolver. Exercises the `position_index` secondary sort key
        added to `_jersey_collision_key * 10` in
        `_svg_prep_outlier_pills`.

        Setup: seed LF and CF aggregates with the SAME engine-space
        star coords. Place one batter at LF and one at CF, each with
        the same deviation. Their pill anchors collapse to a single
        point pre-jitter, so the resolver must split them.
        """
        # Seed all 6 aggregates -- the LF and CF stars at the SAME
        # engine-space coords (so the card-space-rescaled stars also
        # coincide). The other 4 positions stay at the default location.
        for position in COVERED_POSITIONS:
            _seed_aggregate(conn, position)
        # Override LF and CF to the same shared star location.
        conn.execute(
            "UPDATE team_position_aggregate SET star_x = ?, star_y = ? "
            "WHERE position IN ('LF', 'CF') AND team_id = 1",
            (170.0, 220.0),
        )

        # One batter at LF zone A; another at CF zone A. Same deviation
        # under the same star -> pills project to the same SVG anchor.
        _seed_player(conn, "p-lf", last="Ramirez")
        _seed_roster(conn, "p-lf", "7")
        _seed_player(conn, "p-cf", last="Davis")
        _seed_roster(conn, "p-cf", "11")
        _seed_batter_row(
            conn, player_id="p-lf", position="LF",
            direction_deviation=-1, depth_deviation=-1, zone_id="A",
        )
        _seed_batter_row(
            conn, player_id="p-cf", position="CF",
            direction_deviation=-1, depth_deviation=-1, zone_id="A",
        )
        # Fill in default zones for the other positions so the batters
        # don't surface elsewhere as collisions.
        for position in ("RF", "3B", "SS", "2B"):
            _seed_batter_row(
                conn, player_id="p-lf", position=position,
                zone_id=None,
            )
            _seed_batter_row(
                conn, player_id="p-cf", position=position,
                zone_id=None,
            )
        # Also default rows for p-lf at CF and p-cf at LF so they exist
        # as known batters (not strictly necessary -- batter_positioning
        # rows at NULL zones don't contribute to outlier pills).
        _seed_batter_row(
            conn, player_id="p-lf", position="CF", zone_id=None,
        )
        _seed_batter_row(
            conn, player_id="p-cf", position="LF", zone_id=None,
        )
        conn.commit()

        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        svg = ctx["svg"]
        # Both pills rendered with their cross-position labels.
        assert "7-LF" in svg, "LF pill missing from cross-position fixture"
        assert "11-CF" in svg, "CF pill missing from cross-position fixture"

        # Sanity: the LF star and CF star really do coincide in card
        # space. Both stars project from engine (170, 220) via
        # _engine_to_card_xy to a single card-space anchor; both pills
        # also share the same -1/-1 deviation. Pre-jitter both pill
        # anchors collapse to one point. Post-jitter the resolver must
        # split them.
        anchor_lf = _extract_pill_translate(svg, "7-LF")
        anchor_cf = _extract_pill_translate(svg, "11-CF")
        assert anchor_lf != anchor_cf, (
            f"cross-position collision jitter failed: 7-LF and 11-CF "
            f"both anchor at {anchor_lf}. The position-index secondary "
            f"key in _jersey_collision_key * 10 + position_index should "
            f"have separated them."
        )


# ---------------------------------------------------------------------------
# Snapshot-stable: same input produces same SVG twice
# ---------------------------------------------------------------------------


class TestRenderDeterminism:
    def test_same_input_produces_same_svg_twice(self, conn):
        _seed_full_opponent(conn)
        ctx1 = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
            opponent_name="Opp Bears", through_date="Apr 12", game_count=8,
        )
        ctx2 = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
            opponent_name="Opp Bears", through_date="Apr 12", game_count=8,
        )
        assert ctx1["svg"] == ctx2["svg"]
        assert ctx1["sidebar_rows"] == ctx2["sidebar_rows"]


# ---------------------------------------------------------------------------
# Direct unit test for _build_sidebar_rows
# ---------------------------------------------------------------------------


class TestBuildSidebarRowsDirect:
    """Direct unit test on the helper -- isolates partition + sort logic
    from the SQL fetch."""

    def test_alphabetical_within_partition_jersey_tiebreaker(self):
        batters = [
            {"player_id": "p-a", "jersey_number": "11",
             "first_name": "F", "last_name": "Aaron"},
            {"player_id": "p-b", "jersey_number": "3",
             "first_name": "F", "last_name": "Aaron"},
            {"player_id": "p-c", "jersey_number": "7",
             "first_name": "F", "last_name": "Zhao"},
        ]
        # All flagged at LF.
        zone_grid = {
            ("p-a", "LF"): {"zone_id": "B", "is_thin": 0},
            ("p-b", "LF"): {"zone_id": "B", "is_thin": 0},
            ("p-c", "LF"): {"zone_id": "G", "is_thin": 0},
        }
        rows = _build_sidebar_rows(batters, zone_grid, rationales=None)
        # Same last name -> jersey ascending (3 < 11).
        assert [r["jersey_number"] for r in rows[:2]] == ["3", "11"]
        # Zhao sorts after Aaron alphabetically.
        assert rows[2]["last_name"] == "ZHAO"

    def test_flagged_partition_before_default_partition(self):
        batters = [
            {"player_id": "p-flag", "jersey_number": "99",
             "first_name": "F", "last_name": "Zhao"},
            {"player_id": "p-def", "jersey_number": "1",
             "first_name": "F", "last_name": "Aaron"},
        ]
        zone_grid = {
            ("p-flag", "LF"): {"zone_id": "B", "is_thin": 0},
        }
        rows = _build_sidebar_rows(batters, zone_grid, rationales=None)
        # Flagged comes first regardless of alphabetical order.
        assert rows[0]["last_name"] == "ZHAO"
        assert rows[1]["last_name"] == "AARON"


# ---------------------------------------------------------------------------
# Perspective scoping (TN-7 invariant)
# ---------------------------------------------------------------------------


class TestPrepPerspectiveScoping:
    def test_density_bg_dots_only_from_chosen_perspective(self, conn):
        # Seed two perspectives; the renderer should only surface the
        # picked perspective's density data.
        conn.execute(
            "INSERT INTO teams (id, name, membership_type) "
            "VALUES (100, 'Rival Scout', 'member')"
        )
        # Standalone (preferred) perspective = team_id = 1.
        for position in COVERED_POSITIONS:
            _seed_aggregate(conn, position, perspective_team_id=1)
            _seed_aggregate(conn, position, perspective_team_id=100)
        _seed_player(conn, "p1")
        # 5 density events under perspective 1.
        for i in range(5):
            conn.execute(
                "INSERT INTO spray_charts (player_id, team_id, "
                "perspective_team_id, chart_type, play_type, play_result, "
                "x, y, season_id, event_gc_id) VALUES "
                "('p1', 1, 1, 'offensive', 'line_drive', 'single', "
                "160.0, 150.0, '2026-spring-hs', ?)",
                (f"p1-{i}",),
            )
        # 3 density events under perspective 100 -- these MUST NOT leak.
        for i in range(3):
            conn.execute(
                "INSERT INTO spray_charts (player_id, team_id, "
                "perspective_team_id, chart_type, play_type, play_result, "
                "x, y, season_id, event_gc_id) VALUES "
                "('p1', 1, 100, 'offensive', 'line_drive', 'single', "
                "180.0, 130.0, '2026-spring-hs', ?)",
                (f"p100-{i}",),
            )
        conn.commit()
        ctx = render_prep_page_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        # Density-bg dots use r="1.8". Expected count: 5 (perspective 1).
        # Cross-perspective leakage would surface 8 dots.
        assert ctx["svg"].count('r="1.8"') == 5
