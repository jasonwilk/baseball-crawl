"""Tests for E-229-03 + E-229-04 card field SVG generator.

E-229-03 coverage (AC-10):
  * three confidence states (full / thin / zero)
  * no-outliers branch (zero populated zones)
  * legend + header content sourced from module constants
  * always-render compass with faint-placeholder for empty zones (AC-4)
  * edge-clamping behavior
  * density bg gated by `is_low_confidence`

E-229-04 coverage (AC-7 + AC-8):
  * outlier pill projection (TN-15 sign convention)
  * jersey JOIN + truncated last name + NULL-jersey `(L. init)` fallback
  * deterministic radial jitter (same input -> same SVG)
  * stable angular order keyed on jersey number
  * z-order layering (pills atop everything except header/legend)
  * thin-gate + null-zone exclusion
  * AC-8 coord-system regression: (-1, -1) -> lower-left of star;
    (+1, +1) -> upper-right of star
"""

from __future__ import annotations

import sqlite3

import pytest

from src.reports.positioning import BASE_POSITIONS, compute_positioning
from src.reports.positioning_card import (
    COMPASS_LEGEND_LONG,
    COMPASS_LEGEND_SHORT,
    _CARD_VIEWBOX_H,
    _CARD_VIEWBOX_W,
    _PILL_COLLISION_EPSILON,
    _PILL_JITTER_RADIUS,
    _PILL_SCALE_X,
    _PILL_SCALE_Y,
    _ZONE_SIGNS,
    _clamp_to_field,
    _compass_letter_positions,
    _engine_to_card_xy,
    _jersey_sort_key,
    _pill_anchor_xy,
    _pill_text,
    _resolve_pill_collisions,
    _truncate_last_name,
    format_coverage_cue,
    render_field_svg,
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
    x: float = 160.0,
    y: float = 150.0,
    event_gc_id: str | None = None,
):
    _seed_player(conn, player_id)
    conn.execute(
        """
        INSERT INTO spray_charts (
            game_id, player_id, team_id, perspective_team_id,
            chart_type, play_type, play_result, x, y, season_id, event_gc_id
        ) VALUES (NULL, ?, 1, 99, 'offensive', 'line_drive', 'single',
                  ?, ?, '2026-spring-hs', ?)
        """,
        (player_id, x, y, event_gc_id),
    )


def _seed_full_tier_opponent(conn, n_events: int = 60):
    """Seed enough spray events to push the opponent into the full
    confidence tier (>= 50 BIP)."""
    for i in range(n_events):
        _seed_spray_event(conn, player_id="p1", x=160.0 + i * 0.1, y=150.0)
    conn.commit()
    compute_positioning(conn, 1, "2026-spring-hs")


def _seed_thin_tier_opponent(conn, n_events: int = 25):
    """Seed enough events for thin tier (15-49 BIP)."""
    for i in range(n_events):
        _seed_spray_event(conn, player_id="p1", x=160.0 + i * 0.1, y=150.0)
    conn.commit()
    compute_positioning(conn, 1, "2026-spring-hs")


def _seed_zero_tier_opponent(conn, n_events: int = 8):
    """Seed too-few events for zero-coverage (< 15 BIP)."""
    for i in range(n_events):
        _seed_spray_event(conn, player_id="p1", x=160.0 + i * 0.1, y=150.0)
    conn.commit()
    compute_positioning(conn, 1, "2026-spring-hs")


# ---------------------------------------------------------------------------
# Module-level constants and helpers
# ---------------------------------------------------------------------------


class TestModuleConstants:
    """AC-6: Legend wording is sourced from module-level constants per
    UXD M-1 + artifact §F."""

    def test_short_legend_matches_artifact_locked_value(self):
        assert COMPASS_LEGEND_SHORT == "★ default · ○ textbook · A-H outliers"

    def test_long_legend_matches_artifact_locked_value(self):
        # Per artifact §F.
        assert COMPASS_LEGEND_LONG.startswith("A in-left ·")
        assert "deep-right" in COMPASS_LEGEND_LONG
        assert COMPASS_LEGEND_LONG.endswith("· · = team default")

    def test_format_coverage_cue_single_game(self):
        assert format_coverage_cue("Apr 12", 1) == "Through Apr 12 (1 game)"

    def test_format_coverage_cue_plural(self):
        assert format_coverage_cue("Apr 12", 8) == "Through Apr 12 (8 games)"


# ---------------------------------------------------------------------------
# Coord-space mapping
# ---------------------------------------------------------------------------


class TestEngineToCardXY:
    """Per artifact §B (v1.2 anchor-based mapping, supersedes v1.1
    uniform-scalar): anchors engine field corners to card field
    corners. Engine (0, 0) -> card (10, 80) (LF foul / deep CF top);
    engine (320, 295) -> card (190, 305) (RF home plate).
    """

    def test_home_plate_maps_to_card_home(self):
        # Engine home plate (160, 295) -> card home plate (100, 305).
        cx, cy = _engine_to_card_xy(160.0, 295.0)
        assert cx == pytest.approx(100.0)
        assert cy == pytest.approx(305.0)

    def test_lf_corner_maps_to_card_lf_corner(self):
        cx, cy = _engine_to_card_xy(0.0, 0.0)
        assert cx == pytest.approx(10.0)
        assert cy == pytest.approx(80.0)

    def test_rf_corner_maps_to_card_rf_corner(self):
        cx, cy = _engine_to_card_xy(320.0, 0.0)
        assert cx == pytest.approx(190.0)
        assert cy == pytest.approx(80.0)

    def test_engine_rf_home_maps_to_card_rf_home(self):
        cx, cy = _engine_to_card_xy(320.0, 295.0)
        assert cx == pytest.approx(190.0)
        assert cy == pytest.approx(305.0)

    def test_sign_preservation_for_positive_coords(self):
        # Anchor-based mapping is a positive affine -- signs of engine
        # coords carry through unchanged in the card mapping.
        cx, cy = _engine_to_card_xy(150.0, 250.0)
        assert cx > 0
        assert cy > 0

    def test_mapping_is_strictly_monotonic(self):
        # Larger engine_x -> larger card_x; larger engine_y -> larger card_y.
        cx1, cy1 = _engine_to_card_xy(50.0, 100.0)
        cx2, cy2 = _engine_to_card_xy(100.0, 200.0)
        assert cx2 > cx1
        assert cy2 > cy1


# ---------------------------------------------------------------------------
# Compass letter positions + edge clamping (AC-4)
# ---------------------------------------------------------------------------


class TestCompassLetterPositions:
    """AC-4: 8 compass letters placed at fixed angular offsets via the
    sign-rule projection formula. Letters are edge-clamped to the field
    outline."""

    def test_all_eight_letters_present(self):
        positions = _compass_letter_positions(star_x=100.0, star_y=200.0)
        assert set(positions.keys()) == set("ABCDEFGH")

    def test_zone_d_is_directly_below_star(self):
        """Zone D = in (toward home). sign(direction)=0, sign(depth)=-1.
        Offset: x=0, y = -sign(-1) * R = +R -> below star."""
        positions = _compass_letter_positions(star_x=100.0, star_y=160.0)
        d_x, d_y = positions["D"]
        # x should equal star_x; y > star_y (toward home plate)
        assert d_x == pytest.approx(100.0)
        assert d_y > 160.0

    def test_zone_e_is_directly_above_star(self):
        """Zone E = deep (toward CF wall). sign(direction)=0,
        sign(depth)=+1. Offset: y = -sign(+1) * R = -R -> above star."""
        positions = _compass_letter_positions(star_x=100.0, star_y=200.0)
        e_x, e_y = positions["E"]
        assert e_x == pytest.approx(100.0)
        assert e_y < 200.0

    def test_zone_a_is_lower_left_of_star(self):
        """Zone A = in + left (sign_x=-1, sign_y=-1). x_offset negative
        (left), y_offset positive (below)."""
        positions = _compass_letter_positions(star_x=100.0, star_y=160.0)
        a_x, a_y = positions["A"]
        assert a_x < 100.0  # left of star
        assert a_y > 160.0  # below (in)

    def test_zone_h_is_upper_right_of_star(self):
        """Zone H = deep + right (+1, +1). x_offset positive, y_offset
        negative (above)."""
        positions = _compass_letter_positions(star_x=100.0, star_y=200.0)
        h_x, h_y = positions["H"]
        assert h_x > 100.0
        assert h_y < 200.0

    def test_edge_clamp_keeps_letter_inside_field(self):
        """If the star sits near the LF foul corner, Zone A (in+left)
        would normally project further off-field. Clamping pulls it
        back to the foul line."""
        # Star near deep LF; A projects further into LF territory.
        positions = _compass_letter_positions(star_x=20.0, star_y=200.0)
        a_x, a_y = positions["A"]
        # Left-foul-line equation: x_min = 100 - (305 - y) / 2.5
        # At y=a_y: x_min = 100 - (305 - a_y) / 2.5
        x_min_at_y = 100.0 - (305.0 - a_y) / 2.5
        # Clamped center should be at least one disc radius inside the foul line.
        assert a_x >= x_min_at_y

    def test_edge_clamp_top_keeps_letter_below_fence(self):
        positions = _compass_letter_positions(star_x=100.0, star_y=85.0)
        e_x, e_y = positions["E"]
        # Star near deep CF; Zone E would project above the fence (y=80)
        # without clamping. Clamping keeps it below.
        assert e_y >= 80.0  # at or below fence (some disc radius pad applied)

    def test_zone_signs_match_engine_table(self):
        """Vocabulary parity: card module's _ZONE_SIGNS must match the
        engine's sign-rule table per epic TN-3."""
        # The 8 letters and signs (epic TN-3 sign-rule table).
        expected = {
            "A": (-1, -1), "B": (-1,  0), "C": (-1,  1),
            "D": ( 0, -1),                "E": ( 0,  1),
            "F": ( 1, -1), "G": ( 1,  0), "H": ( 1,  1),
        }
        assert _ZONE_SIGNS == expected


class TestClampToField:
    def test_no_clamp_when_center_inside_field(self):
        cx, cy = _clamp_to_field(100.0, 200.0, disc_radius=6.5)
        assert cx == pytest.approx(100.0)
        assert cy == pytest.approx(200.0)

    def test_clamp_to_left_foul_line(self):
        # A point outside the left foul line gets pulled inward.
        cx, cy = _clamp_to_field(0.0, 200.0, disc_radius=6.5)
        # Left foul line at y=200: x_min = 100 - (305-200)/2.5 = 100 - 42 = 58
        assert cx >= 58.0 + 6.5
        # y unchanged (not constrained by deep-CF fence)
        assert cy == pytest.approx(200.0)

    def test_clamp_to_deep_cf_fence(self):
        cx, cy = _clamp_to_field(100.0, 50.0, disc_radius=6.5)
        # cy must be at least 80 + disc_radius
        assert cy >= 80.0 + 6.5


# ---------------------------------------------------------------------------
# Three confidence states (AC-9 + AC-2)
# ---------------------------------------------------------------------------


class TestConfidenceTierStates:
    """AC-2 + AC-9: the three confidence states (full / thin / zero)
    each produce structurally distinct SVG output."""

    def test_full_tier_renders_solid_star_and_bip_caption(self, conn):
        _seed_full_tier_opponent(conn)
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        # Solid star polygon present.
        assert "<polygon" in svg
        # BIP-count caption per coach BC-3 "always contextualize".
        assert "BIP)" in svg
        # No thin-tier dashed ring marker.
        assert "stroke-dasharray" not in svg

    def test_thin_tier_renders_dashed_ring_and_tilde_bip_caption(self, conn):
        _seed_thin_tier_opponent(conn)
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        # Dashed ring marker.
        assert "stroke-dasharray" in svg
        # "(~N BIP)" tilde caption.
        assert "(~" in svg
        # No density background (rendered ONLY when is_low_confidence=0).
        # Density bg uses opacity 0.12 -> "0.12".
        assert 'opacity="0.12"' not in svg

    def test_zero_tier_renders_message_no_star(self, conn):
        _seed_zero_tier_opponent(conn)
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        assert "Not enough spray data" in svg
        # No star polygon, no compass disc.
        assert "<polygon" not in svg
        # No density background.
        assert 'opacity="0.12"' not in svg

    def test_zero_tier_when_no_aggregate_row_exists(self, conn):
        # No spray events seeded -> no aggregate row at all.
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        assert "Not enough spray data" in svg


# ---------------------------------------------------------------------------
# Density background (AC-5)
# ---------------------------------------------------------------------------


class TestDensityBackground:
    def test_density_bg_rendered_in_full_tier(self, conn):
        _seed_full_tier_opponent(conn)
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        assert 'opacity="0.12"' in svg

    def test_density_bg_hidden_in_thin_tier(self, conn):
        _seed_thin_tier_opponent(conn)
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        assert 'opacity="0.12"' not in svg

    def test_density_bg_hidden_in_zero_tier(self, conn):
        _seed_zero_tier_opponent(conn)
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        assert 'opacity="0.12"' not in svg


# ---------------------------------------------------------------------------
# Perspective-provenance scoping (epic TN-7 + perspective-provenance rule)
# ---------------------------------------------------------------------------


class TestPerspectiveProvenanceScoping:
    """MUST FIX (CR R1): density-bg dots and populated-zone coloring must
    scope to the same perspective the star came from. Single-perspective
    fixtures can mask cross-perspective leakage; this class seeds TWO
    perspectives and asserts the renderer ignores rows from the
    non-chosen perspective.
    """

    def _seed_two_perspectives(self, conn):
        """Seed two perspectives writing into the same opponent + season.

        Perspective 99 (the standalone LSB perspective the renderer
        picks): 60 events near center, including 15 outlier-batter
        events that push one zone populated.

        Perspective 100 (rival scout's perspective): VERY different
        spray pattern -- all events in deep RF (a pull-side opponent
        viewed by the rival). If the renderer wrongly includes this
        perspective's data in density-bg or populated zones, the SVG
        will surface rows that the standalone perspective never
        produced.
        """
        conn.execute(
            "INSERT INTO teams (id, name, membership_type) "
            "VALUES (100, 'Rival Scout', 'member')"
        )

        # Perspective 99: 60 events at raw (160, 150) -- maps to center
        # in SVG space. Engine-aggregate is_low_confidence=0 (full tier).
        for i in range(60):
            _seed_spray_event(
                conn, player_id="p1", x=160.0, y=150.0,
                event_gc_id=f"evt-p99-{i}",
            )
        # Add a strong-pull outlier batter under perspective 99 so at
        # least one zone is populated under that perspective.
        for i in range(15):
            _seed_spray_event(
                conn, player_id="p99-outlier", x=10.0, y=200.0,
                event_gc_id=f"out-p99-{i}",
            )

        # Perspective 100: events that under naive perspective-blind
        # queries would leak into the density-bg + a DIFFERENT
        # populated zone. Use coords that map to deep RF in SVG.
        # Override the seed helper's default perspective_team_id=99.
        _seed_player(conn, "p100-deepRF")
        for i in range(60):
            conn.execute(
                """
                INSERT INTO spray_charts (
                    game_id, player_id, team_id, perspective_team_id,
                    chart_type, play_type, play_result, x, y,
                    season_id, event_gc_id
                ) VALUES (NULL, ?, 1, 100, 'offensive', 'fly_ball',
                          'single', 300.0, 50.0, '2026-spring-hs', ?)
                """,
                ("p100-deepRF", f"evt-p100-{i}"),
            )
        conn.commit()
        compute_positioning(conn, 1, "2026-spring-hs")

    def test_density_bg_dots_only_from_chosen_perspective(self, conn):
        """The density background MUST NOT include points from a
        perspective the renderer did not pick. We can't trivially read
        the dot coords back out of the SVG, but we can compare the
        density-bg dot COUNT against the per-perspective row count and
        confirm it matches the chosen perspective alone, NOT the union.
        """
        self._seed_two_perspectives(conn)
        # Perspective 99 has 60 + 15 = 75 placed events; perspective
        # 100 has 60 placed events. Union would be 135.
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        # The density-bg dot for perspective 100's points sits at
        # engine (300, 50) -> card via anchor-based mapping -> a
        # specific cy value that is well above the (cy>200) range of
        # perspective 99's points (centered around raw (160, 150) ->
        # svg ~(160, 200) -> card ~(100, ~230)). If perspective 100
        # leaked in, the SVG would contain density circles at the
        # corresponding card-y in the deep-RF / above-field region.
        # A precise dot-count check is the cleanest assertion:
        # perspective 99 contributes 75 placed events -> 75 density
        # dots. Perspective 100 alone would be 60. The union would
        # be 135.
        # Count density-bg circles. They're inside the `<g fill="#000"
        # opacity="0.12">` block, each as `<circle ... r="1.8"/>`.
        # Density dot radius is the artifact §B "1.8 px" -- distinct
        # from textbook dot (3.5) and compass disc (6.5).
        density_dot_count = svg.count('r="1.8"')
        assert density_dot_count == 75, (
            f"Expected 75 density-bg dots (perspective 99 alone), "
            f"got {density_dot_count}. Cross-perspective leakage "
            f"would produce 135."
        )

    def test_populated_zones_only_from_chosen_perspective(self, conn):
        """`_query_populated_zones` MUST scope to a single perspective.

        Direct SQL-level check (engine-side zone assignments make
        SVG-level differentiation fragile -- the engine produces
        per-perspective batter_positioning rows but their zone letters
        often align by accident because deviation signs are dominated
        by position-textbook offsets, not by perspective-induced
        centroid shifts). The MUST-FIX target is the SELECT itself --
        verify the filter, not the visual symptom.
        """
        from src.reports.positioning_card import _query_populated_zones

        conn.execute(
            "INSERT INTO teams (id, name, membership_type) "
            "VALUES (100, 'Rival Scout', 'member')"
        )
        # Two perspectives, each with their own batter_positioning row
        # at LF, each with a DIFFERENT zone_id (manually inserted to
        # bypass the engine's centroid-driven assignment so the test
        # exercises only the perspective-scope filter).
        _seed_player(conn, "p99-batter")
        _seed_player(conn, "p100-batter")
        conn.execute(
            """
            INSERT INTO team_position_aggregate (
                team_id, season_id, perspective_team_id, position,
                star_x, star_y, bip_count, is_low_confidence
            ) VALUES (1, '2026-spring-hs', 99, 'LF', 100.0, 150.0, 60, 0)
            """
        )
        conn.execute(
            """
            INSERT INTO team_position_aggregate (
                team_id, season_id, perspective_team_id, position,
                star_x, star_y, bip_count, is_low_confidence
            ) VALUES (1, '2026-spring-hs', 100, 'LF', 100.0, 150.0, 60, 0)
            """
        )
        # Perspective 99: batter with zone_id='B' (left).
        conn.execute(
            """
            INSERT INTO batter_positioning (
                player_id, team_id, season_id, perspective_team_id,
                position, direction_deviation, depth_deviation,
                zone_id, is_thin, bip_count, hr_count
            ) VALUES ('p99-batter', 1, '2026-spring-hs', 99, 'LF',
                      -1, 0, 'B', 0, 30, 0)
            """
        )
        # Perspective 100: batter with zone_id='G' (right) -- different
        # zone, so cross-perspective leakage would produce a strictly
        # larger zone set under wrong scoping.
        conn.execute(
            """
            INSERT INTO batter_positioning (
                player_id, team_id, season_id, perspective_team_id,
                position, direction_deviation, depth_deviation,
                zone_id, is_thin, bip_count, hr_count
            ) VALUES ('p100-batter', 1, '2026-spring-hs', 100, 'LF',
                      1, 0, 'G', 0, 30, 0)
            """
        )
        conn.commit()

        # Direct query check: perspective 99 returns {B} only.
        zones_p99 = _query_populated_zones(
            conn, team_id=1, season_id="2026-spring-hs",
            position="LF", perspective_team_id=99,
        )
        assert zones_p99 == {"B"}, (
            f"Expected {{'B'}} under perspective 99 scope, got {zones_p99}. "
            f"Cross-perspective leakage would have added 'G' from "
            f"perspective 100's batter."
        )

        # Symmetric check: perspective 100 returns {G} only.
        zones_p100 = _query_populated_zones(
            conn, team_id=1, season_id="2026-spring-hs",
            position="LF", perspective_team_id=100,
        )
        assert zones_p100 == {"G"}

        # End-to-end via the renderer: under perspective 99 (the
        # standalone-preferred picked by _query_team_aggregate's ORDER
        # BY ... but here there's no perspective_team_id=team_id=1 row,
        # so the renderer falls back to the first row, which is 99 by
        # season ordering). The SVG should show zone B populated and
        # zone G as a faint placeholder.
        svg = render_field_svg(
            conn, "opp-bears", "LF", "2026-spring-hs",
        )
        # Zone G text element should carry the faint-placeholder opacity
        # attribute (leakage from perspective 100 would render it solid).
        assert 'opacity="0.3">G<' in svg, (
            "zone G should render as faint placeholder when the "
            "renderer picks perspective 99 -- found a solid G, indicating "
            "cross-perspective leakage from perspective 100."
        )


# ---------------------------------------------------------------------------
# Compass-ring always-render with faint-placeholder behavior (AC-4)
# ---------------------------------------------------------------------------


class TestCompassRingAlwaysRenders:
    """AC-4: all 8 letters always render; populated full opacity; empty
    zones at 30% opacity. Stable visual language per epic TN-3."""

    def test_full_tier_renders_all_eight_letters(self, conn):
        _seed_full_tier_opponent(conn)
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        for letter in "ABCDEFGH":
            # Each letter present as text content.
            assert f">{letter}<" in svg

    def test_thin_tier_renders_all_eight_letters(self, conn):
        _seed_thin_tier_opponent(conn)
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        for letter in "ABCDEFGH":
            assert f">{letter}<" in svg

    def test_empty_zones_render_at_thirty_percent_opacity(self, conn):
        # Full tier with all zones empty (single batter at the star ->
        # no outliers, all zones empty).
        for _ in range(60):
            _seed_spray_event(
                conn, player_id="p1", x=160.0, y=150.0,  # near center
            )
        conn.commit()
        compute_positioning(conn, 1, "2026-spring-hs")
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        # All zones empty -> every compass letter rendered with
        # opacity="0.3" (or 0.30).
        assert 'opacity="0.3"' in svg

    def test_populated_zones_render_at_full_opacity(self, conn):
        """When a zone is populated, the letter is NOT marked with the
        empty-zone opacity attribute."""
        # Build an opponent where one batter is a strong outlier so at
        # least one zone is populated.
        # Center the team at one location, then add a single batter way
        # off (left-side strong-pull) with enough BIP to NOT be thin.
        for _ in range(70):  # large center group -> centroid at center
            _seed_spray_event(
                conn, player_id="p-center", x=160.0, y=150.0,
            )
        for i in range(15):  # outlier batter, BIP>=10 so not thin
            _seed_spray_event(
                conn, player_id="p-outlier", x=10.0, y=200.0,
                event_gc_id=f"outlier-{i}",
            )
        conn.commit()
        compute_positioning(conn, 1, "2026-spring-hs")

        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        # At least one zone has full-opacity letter (no opacity attr
        # adjacent to the letter text), proving the populated path
        # diverged from the empty placeholder path.
        # If every letter were faint, every letter text would carry an
        # opacity attribute -- so count `opacity="0.3"` occurrences
        # against total letter count.
        assert svg.count('opacity="0.3"') < 16  # 16 = 8 letters * (disc + text)


# ---------------------------------------------------------------------------
# No-outliers branch (AC-8)
# ---------------------------------------------------------------------------


class TestNoOutliersBranch:
    def test_no_outliers_note_present_when_no_populated_zones(self, conn):
        # Drive the renderer directly with a populated team_position_aggregate
        # row but ALL batter_positioning rows carrying zone_id=NULL (no
        # outliers). Bypass the engine: with the locked scale factors, a
        # single-batter team produces nonzero deviations against every
        # position's textbook-anchored star, so we cannot reach the
        # "no populated zones" state via the engine + single-batter seed.
        # The render-layer branch is the unit under test here, not the
        # engine -- direct INSERT is the correct fixture pattern.
        _seed_player(conn, "p1")
        for position in ("LF", "CF", "RF", "3B", "SS", "2B"):
            conn.execute(
                """
                INSERT INTO team_position_aggregate (
                    team_id, season_id, perspective_team_id, position,
                    star_x, star_y, bip_count, is_low_confidence
                ) VALUES (1, '2026-spring-hs', 1, ?, 160.0, 200.0, 60, 0)
                """,
                (position,),
            )
            conn.execute(
                """
                INSERT INTO batter_positioning (
                    player_id, team_id, season_id, perspective_team_id, position,
                    direction_deviation, depth_deviation, zone_id,
                    is_thin, bip_count, hr_count
                ) VALUES ('p1', 1, '2026-spring-hs', 1, ?, 0, 0, NULL,
                          0, 60, 0)
                """,
                (position,),
            )
        conn.commit()
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        assert "No outliers this opponent" in svg
        # Star + textbook dot + density bg still rendered.
        assert "<polygon" in svg
        # All 8 letters still present per AC-4 (faint placeholders).
        for letter in "ABCDEFGH":
            assert f">{letter}<" in svg

    def test_no_outliers_note_absent_when_zone_populated(self, conn):
        # Center-mass + an outlier batter (strong pull).
        for _ in range(70):
            _seed_spray_event(conn, player_id="p-center", x=160.0, y=150.0)
        for i in range(15):
            _seed_spray_event(
                conn, player_id="p-outlier", x=10.0, y=200.0,
                event_gc_id=f"outlier-{i}",
            )
        conn.commit()
        compute_positioning(conn, 1, "2026-spring-hs")
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        assert "No outliers this opponent" not in svg


# ---------------------------------------------------------------------------
# Header + legend content (AC-6 + AC-7)
# ---------------------------------------------------------------------------


class TestHeaderAndLegendContent:
    def test_header_includes_opponent_name(self, conn):
        _seed_full_tier_opponent(conn)
        svg = render_field_svg(
            conn, "opp-bears", "LF", "2026-spring-hs",
            opponent_name="Opp Bears", through_date="Apr 12", game_count=8,
        )
        assert "Opp Bears" in svg

    def test_header_includes_coverage_cue(self, conn):
        _seed_full_tier_opponent(conn)
        svg = render_field_svg(
            conn, "opp-bears", "LF", "2026-spring-hs",
            opponent_name="Opp Bears", through_date="Apr 12", game_count=8,
        )
        assert "Through Apr 12 (8 games)" in svg

    def test_header_includes_position_label(self, conn):
        _seed_full_tier_opponent(conn)
        svg = render_field_svg(
            conn, "opp-bears", "LF", "2026-spring-hs",
            opponent_name="Opp Bears",
        )
        assert "LEFT FIELD" in svg

    def test_legend_text_from_module_constant(self, conn):
        _seed_full_tier_opponent(conn)
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        # The locked legend wording must appear verbatim.
        assert COMPASS_LEGEND_SHORT in svg

    def test_legend_renders_in_zero_tier(self, conn):
        _seed_zero_tier_opponent(conn)
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        assert COMPASS_LEGEND_SHORT in svg

    def test_header_renders_in_zero_tier(self, conn):
        _seed_zero_tier_opponent(conn)
        svg = render_field_svg(
            conn, "opp-bears", "LF", "2026-spring-hs",
            opponent_name="Eastlake Bears", through_date="Apr 12", game_count=8,
        )
        assert "Eastlake Bears" in svg
        assert "Through Apr 12 (8 games)" in svg


# ---------------------------------------------------------------------------
# Textbook dot (AC-3)
# ---------------------------------------------------------------------------


class TestTextbookDot:
    def test_textbook_dot_rendered_in_full_tier(self, conn):
        _seed_full_tier_opponent(conn)
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        # Open-outline dot: fill=none, stroke=#000, opacity=0.45.
        assert 'opacity="0.45"' in svg
        assert 'fill="none"' in svg

    def test_textbook_dot_omitted_in_zero_tier(self, conn):
        _seed_zero_tier_opponent(conn)
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        # No textbook dot in the zero-coverage state.
        assert 'opacity="0.45"' not in svg


# ---------------------------------------------------------------------------
# SVG container (AC-1)
# ---------------------------------------------------------------------------


class TestSVGContainer:
    def test_svg_uses_locked_viewbox(self, conn):
        _seed_full_tier_opponent(conn)
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        # Artifact §B locks viewBox 200 x 320 (aspect 0.625).
        assert f'viewBox="0 0 {_CARD_VIEWBOX_W} {_CARD_VIEWBOX_H}"' in svg

    def test_svg_uses_locked_aspect_preserve(self, conn):
        _seed_full_tier_opponent(conn)
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        assert 'preserveAspectRatio="xMidYMid meet"' in svg

    def test_svg_well_formed_open_close_tag(self, conn):
        _seed_full_tier_opponent(conn)
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        assert svg.startswith("<svg ")
        assert svg.endswith("</svg>")

    def test_invalid_position_raises(self, conn):
        with pytest.raises(ValueError):
            render_field_svg(conn, "opp-bears", "P", "2026-spring-hs")

    def test_unknown_public_id_raises(self, conn):
        with pytest.raises(ValueError):
            render_field_svg(
                conn, "nonexistent-team", "LF", "2026-spring-hs",
            )


# ---------------------------------------------------------------------------
# AC-1 module placement enforcement (grep equivalent)
# ---------------------------------------------------------------------------


class TestModulePlacement:
    """CR M3 lock: the field SVG generator MUST live at
    src/reports/positioning_card.py, not in src/reports/renderer.py."""

    def test_render_field_svg_importable_from_positioning_card(self):
        # The import at the top of this test file would fail at
        # collection time if the module placement were wrong.
        from src.reports import positioning_card
        assert hasattr(positioning_card, "render_field_svg")
        assert hasattr(positioning_card, "COMPASS_LEGEND_SHORT")
        assert hasattr(positioning_card, "COMPASS_LEGEND_LONG")
        assert hasattr(positioning_card, "format_coverage_cue")


# ---------------------------------------------------------------------------
# E-229-04: Outlier pills
# ---------------------------------------------------------------------------


def _insert_aggregate_row(
    conn,
    *,
    team_id: int = 1,
    season_id: str = "2026-spring-hs",
    perspective_team_id: int = 1,
    position: str = "LF",
    star_x: float = 160.0,
    star_y: float = 240.0,
    bip_count: int = 60,
    is_low_confidence: int = 0,
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


def _insert_batter_row(
    conn,
    *,
    player_id: str,
    first_name: str = "First",
    last_name: str = "Last",
    jersey_number: str | None = "7",
    team_id: int = 1,
    season_id: str = "2026-spring-hs",
    perspective_team_id: int = 1,
    position: str = "LF",
    direction_deviation: int = -1,
    depth_deviation: int = -1,
    zone_id: str | None = "A",
    is_thin: int = 0,
    bip_count: int = 20,
    hr_count: int = 0,
):
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, ?, ?)",
        (player_id, first_name, last_name),
    )
    if jersey_number is not None:
        conn.execute(
            "INSERT OR IGNORE INTO team_rosters (team_id, player_id, "
            "season_id, jersey_number) VALUES (?, ?, ?, ?)",
            (team_id, player_id, season_id, jersey_number),
        )
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


# ---------------------------------------------------------------------------
# AC-1 + AC-8: pill projection per TN-15 sign convention
# ---------------------------------------------------------------------------


class TestPillProjection:
    """AC-1 + AC-8: outlier pill placement follows the TN-15 sign rule.

    Star at (160, 240) in card SVG space. Direction-negative -> left
    (smaller x); depth-negative -> "in" (toward home plate = larger y).
    Per the projection formula:
      pill_x = star_x + direction_dev * scale_x
      pill_y = star_y + (-depth_dev) * scale_y
    """

    def test_zone_a_lower_left_of_star(self):
        """Zone A (in+left): (-1, -1) -> x < star_x AND y > star_y."""
        star_x, star_y = 160.0, 240.0
        px, py = _pill_anchor_xy(star_x, star_y, -1, -1)
        assert px == pytest.approx(star_x - _PILL_SCALE_X)
        assert py == pytest.approx(star_y + _PILL_SCALE_Y)
        assert px < star_x
        assert py > star_y

    def test_zone_h_upper_right_of_star(self):
        """Zone H (deep+right): (+1, +1) -> x > star_x AND y < star_y."""
        star_x, star_y = 160.0, 240.0
        px, py = _pill_anchor_xy(star_x, star_y, 1, 1)
        assert px == pytest.approx(star_x + _PILL_SCALE_X)
        assert py == pytest.approx(star_y - _PILL_SCALE_Y)
        assert px > star_x
        assert py < star_y

    def test_zero_deviation_at_star(self):
        star_x, star_y = 160.0, 240.0
        px, py = _pill_anchor_xy(star_x, star_y, 0, 0)
        assert px == pytest.approx(star_x)
        assert py == pytest.approx(star_y)

    def test_scale_factors_match_artifact_locked_values(self):
        # Artifact §B locked: scale_x = 18, scale_y = 22.
        assert _PILL_SCALE_X == pytest.approx(18.0)
        assert _PILL_SCALE_Y == pytest.approx(22.0)


# ---------------------------------------------------------------------------
# AC-8 (coord-system regression test, end-to-end through render_field_svg)
# ---------------------------------------------------------------------------


class TestCoordSystemRegression:
    """AC-8: locked projection contract verified end-to-end through the
    SVG generator. Catches a future depth-axis sign flip.

    The engine writes star coords in 320x480 GC space; the renderer
    rescales them to card space via `_engine_to_card_xy` BEFORE the
    pill projection runs. The exact card-space anchor depends on the
    rescaling, so these tests assert the RELATIVE position of the pill
    versus the star, not absolute coordinates.
    """

    def _extract_pill_anchor(self, svg: str, pill_text: str) -> tuple[float, float]:
        """Pull `translate(x, y)` from the <g> wrapping pill_text."""
        import re
        pat = re.compile(
            r'transform="translate\(([0-9.\-]+),\s*([0-9.\-]+)\)"'
            r'><rect[^>]*/>'
            r'<text[^>]*>' + re.escape(pill_text) + r'</text>'
        )
        m = pat.search(svg)
        assert m, f"could not find pill {pill_text!r} translate in SVG"
        return float(m.group(1)), float(m.group(2))

    def _extract_star_center(self, svg: str) -> tuple[float, float]:
        """Pull `translate(x, y)` from the <g> wrapping the star polygon."""
        import re
        pat = re.compile(
            r'transform="translate\(([0-9.\-]+),\s*([0-9.\-]+)\)"'
            r'><polygon points="0,-8'
        )
        m = pat.search(svg)
        assert m, "could not find star center in SVG"
        return float(m.group(1)), float(m.group(2))

    def test_zone_a_pill_lower_left_in_svg(self, conn):
        """Zone A (-1, -1): pill x < star_x AND y > star_y (lower-left)."""
        _insert_aggregate_row(
            conn, star_x=160.0, star_y=240.0, perspective_team_id=1,
        )
        _insert_batter_row(
            conn, player_id="p1", last_name="Ramirez", jersey_number="7",
            direction_deviation=-1, depth_deviation=-1, zone_id="A",
            perspective_team_id=1,
        )
        conn.commit()
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        star_x, star_y = self._extract_star_center(svg)
        pill_x, pill_y = self._extract_pill_anchor(svg, "#7 RAMIRE")
        assert pill_x < star_x, "Zone A pill must be LEFT of star"
        assert pill_y > star_y, "Zone A pill must be BELOW (in) star"

    def test_zone_h_pill_upper_right_in_svg(self, conn):
        """Zone H (+1, +1): pill x > star_x AND y < star_y (upper-right)."""
        _insert_aggregate_row(
            conn, star_x=160.0, star_y=240.0, perspective_team_id=1,
        )
        _insert_batter_row(
            conn, player_id="p2", last_name="Wright", jersey_number="4",
            direction_deviation=1, depth_deviation=1, zone_id="H",
            perspective_team_id=1,
        )
        conn.commit()
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        star_x, star_y = self._extract_star_center(svg)
        pill_x, pill_y = self._extract_pill_anchor(svg, "#4 WRIGHT")
        assert pill_x > star_x, "Zone H pill must be RIGHT of star"
        assert pill_y < star_y, "Zone H pill must be ABOVE (deep) star"


# ---------------------------------------------------------------------------
# AC-2: pill text format (jersey + truncated last name; NULL fallback)
# ---------------------------------------------------------------------------


class TestPillText:
    def test_jersey_plus_truncated_last_name(self):
        text = _pill_text({"jersey_number": "7", "last_name": "Ramirez"})
        assert text == "#7 RAMIRE"  # 6-char truncation per artifact

    def test_short_last_name_not_truncated(self):
        text = _pill_text({"jersey_number": "11", "last_name": "Lopez"})
        assert text == "#11 LOPEZ"

    def test_null_jersey_fallback_uses_initial_init_form(self):
        """Artifact §B NULL-jersey fallback: `(L. init)` literal."""
        text = _pill_text({"jersey_number": None, "last_name": "Wilkinson"})
        assert text == "(W. init)"
        assert "#" not in text  # no jersey-number prefix per spec

    def test_empty_jersey_treated_as_null(self):
        text = _pill_text({"jersey_number": "", "last_name": "Davis"})
        assert text == "(D. init)"

    def test_null_jersey_empty_last_name(self):
        # Defensive: empty last name -> "(?" placeholder.
        text = _pill_text({"jersey_number": None, "last_name": ""})
        assert text == "(?. init)"

    def test_last_name_truncation_helper_handles_none(self):
        assert _truncate_last_name(None) == ""
        assert _truncate_last_name("") == ""
        assert _truncate_last_name("ramirez") == "RAMIRE"


# ---------------------------------------------------------------------------
# AC-4: deterministic radial jitter + stable angular order
# ---------------------------------------------------------------------------


class TestPillCollisionResolution:
    """AC-4: when two pills land within ε, deterministic radial jitter
    places them around the centroid. Stable angular order keyed on
    jersey number (ascending)."""

    def test_no_collision_returns_anchors_unchanged(self):
        # Two anchors far apart -> no collision, no jitter.
        anchors = [(50.0, 100.0, 7), (150.0, 100.0, 11)]
        result = _resolve_pill_collisions(anchors)
        assert result == anchors

    def test_collision_pair_anchored_at_centroid(self):
        # Two anchors within ε -> first (lowest jersey) at centroid,
        # second offset radially.
        eps = _PILL_COLLISION_EPSILON
        anchors = [
            (100.0, 100.0, 7),
            (100.0 + eps / 2, 100.0, 11),  # within ε
        ]
        result = _resolve_pill_collisions(anchors)
        # Centroid of the two anchors:
        cx = (100.0 + 100.0 + eps / 2) / 2
        cy = 100.0
        # Lowest jersey (7) sits at the centroid; jersey 11 offset.
        assert result[0] == pytest.approx((cx, cy, 7))
        # Jersey 11 must NOT be at the centroid (it's been jittered).
        assert result[1][:2] != pytest.approx((cx, cy))
        # Jittered position should be at distance _PILL_JITTER_RADIUS
        # from the centroid.
        dx = result[1][0] - cx
        dy = result[1][1] - cy
        dist = (dx ** 2 + dy ** 2) ** 0.5
        assert dist == pytest.approx(_PILL_JITTER_RADIUS, abs=0.01)

    def test_jitter_is_deterministic(self):
        # Same input -> same output, twice in a row.
        eps = _PILL_COLLISION_EPSILON
        anchors = [
            (100.0, 100.0, 7),
            (100.0 + eps / 2, 100.0, 11),
            (100.0 - eps / 2, 100.0 + eps / 2, 23),
        ]
        result1 = _resolve_pill_collisions(anchors)
        result2 = _resolve_pill_collisions(anchors)
        assert result1 == result2

    def test_angular_order_keyed_on_sort_key(self):
        """Lower sort_key (jersey number) takes the centroid; the next
        sits at the topmost offset (angle 0° = straight up); subsequent
        rotate clockwise."""
        eps = _PILL_COLLISION_EPSILON
        anchors = [
            (100.0, 100.0, 100),  # highest jersey
            (100.0, 100.0, 7),    # lowest jersey (anchored at centroid)
            (100.0, 100.0, 50),
        ]
        result = _resolve_pill_collisions(anchors)
        # By the sort_key in the result tuple, jersey 7 sits at the
        # centroid (which is just (100, 100) since all anchors stack).
        result_map = {key: (x, y) for (x, y, key) in result}
        assert result_map[7] == pytest.approx((100.0, 100.0))
        # Jersey 50 (second-lowest non-anchor) at angle 0° -> straight
        # up in card SVG (negative y delta).
        x50, y50 = result_map[50]
        assert x50 == pytest.approx(100.0, abs=0.01)
        assert y50 < 100.0  # above centroid
        # Jersey 100 at angle 60° (clockwise from up).
        x100, y100 = result_map[100]
        # Angle 60 CW from up: sin(60) > 0 (rightward), -cos(60) < 0 -> y < 100.
        # Specifically: ox = R * sin(60); oy = -R * cos(60).
        import math
        assert x100 == pytest.approx(
            100.0 + _PILL_JITTER_RADIUS * math.sin(math.radians(60))
        )
        assert y100 == pytest.approx(
            100.0 - _PILL_JITTER_RADIUS * math.cos(math.radians(60))
        )

    def test_input_order_preserved_in_output(self):
        """The resolver returns pills in the SAME order as the input
        list (callers `zip` with their batter list)."""
        eps = _PILL_COLLISION_EPSILON
        anchors = [
            (100.0, 100.0, 23),
            (100.0 + eps / 2, 100.0, 7),
            (100.0, 100.0 + eps / 2, 11),
        ]
        result = _resolve_pill_collisions(anchors)
        # Output retains input ordering: result[i] corresponds to anchors[i].
        # Sort keys threaded through:
        assert [r[2] for r in result] == [23, 7, 11]


# ---------------------------------------------------------------------------
# AC-2 / AC-7: jersey JOIN + last-name JOIN + fallback (end-to-end)
# ---------------------------------------------------------------------------


class TestJerseyJoinFallback:
    def test_pill_renders_jersey_from_team_rosters(self, conn):
        _insert_aggregate_row(conn, perspective_team_id=1)
        _insert_batter_row(
            conn, player_id="p1", last_name="Ramirez", jersey_number="7",
            zone_id="A", direction_deviation=-1, depth_deviation=-1,
            perspective_team_id=1,
        )
        conn.commit()
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        # Jersey + truncated last name.
        assert "#7 RAMIRE" in svg

    def test_pill_renders_null_jersey_fallback(self, conn):
        _insert_aggregate_row(conn, perspective_team_id=1)
        # NULL jersey -> no team_rosters row inserted.
        _insert_batter_row(
            conn, player_id="p2", last_name="Wilkinson",
            jersey_number=None,
            zone_id="A", direction_deviation=-1, depth_deviation=-1,
            perspective_team_id=1,
        )
        conn.commit()
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        # NULL-jersey fallback per artifact §B.
        assert "(W. init)" in svg
        # Pill text wraps inside `<text ...>...</text>` -- search the
        # text-content portions only. The SVG body contains hex color
        # literals like `#000` and `#4d4d4d`; those live in attribute
        # values, not in text content.
        import re
        text_contents = re.findall(r"<text[^>]*>([^<]*)</text>", svg)
        for content in text_contents:
            assert not content.startswith("#"), (
                f"NULL-jersey fallback must NOT render a `#<jersey>` "
                f"prefix in pill text; got text content: {content!r}"
            )


# ---------------------------------------------------------------------------
# AC-5: z-order (pills layer on top of star, compass, density, textbook)
# ---------------------------------------------------------------------------


class TestPillZOrder:
    def test_pill_appears_after_star_in_svg_text(self, conn):
        """SVG z-order is implicit in document order. The pill `<g>`
        should appear AFTER the star polygon and AFTER the compass
        letters in the rendered string."""
        _insert_aggregate_row(conn, perspective_team_id=1)
        _insert_batter_row(
            conn, player_id="p1", last_name="Ramirez", jersey_number="7",
            zone_id="A", direction_deviation=-1, depth_deviation=-1,
            perspective_team_id=1,
        )
        conn.commit()
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        # Locate the structural markers.
        star_pos = svg.find("<polygon")
        compass_letter_pos = svg.find(">A<")  # any compass letter A-H
        pill_text_pos = svg.find("#7 RAMIRE")
        assert star_pos > -1
        assert compass_letter_pos > -1
        assert pill_text_pos > -1
        # Pills draw last (back-to-front, per artifact §B z-order stack).
        assert pill_text_pos > star_pos
        assert pill_text_pos > compass_letter_pos


# ---------------------------------------------------------------------------
# AC-6: thin-gate + null-zone exclusion
# ---------------------------------------------------------------------------


class TestPillExclusions:
    def test_thin_batter_gets_no_pill(self, conn):
        _insert_aggregate_row(conn, perspective_team_id=1)
        # is_thin=1: per TN-5, no outlier marker even with non-NULL zone.
        _insert_batter_row(
            conn, player_id="p-thin", last_name="Patel", jersey_number="3",
            zone_id="B", direction_deviation=-1, depth_deviation=0,
            is_thin=1, bip_count=5,
            perspective_team_id=1,
        )
        conn.commit()
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        # Pill text should NOT appear in SVG.
        assert "#3" not in svg
        assert "PATEL" not in svg
        # "No outliers this opponent" note should be present.
        assert "No outliers this opponent" in svg

    def test_null_zone_batter_gets_no_pill(self, conn):
        _insert_aggregate_row(conn, perspective_team_id=1)
        # zone_id=NULL: per AC-6, batter is at the star, no outlier marker.
        _insert_batter_row(
            conn, player_id="p-atstar", last_name="Davis", jersey_number="9",
            zone_id=None, direction_deviation=0, depth_deviation=0,
            is_thin=0,
            perspective_team_id=1,
        )
        conn.commit()
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        assert "#9" not in svg
        assert "DAVIS" not in svg
        assert "No outliers this opponent" in svg

    def test_outliers_render_excludes_thin_includes_full(self, conn):
        """Mixed: one full-data outlier + one thin batter. Only the
        full-data batter's pill appears."""
        _insert_aggregate_row(conn, perspective_team_id=1)
        _insert_batter_row(
            conn, player_id="p-thin", last_name="Patel", jersey_number="3",
            zone_id="B", direction_deviation=-1, depth_deviation=0,
            is_thin=1, bip_count=5,
            perspective_team_id=1,
        )
        _insert_batter_row(
            conn, player_id="p-full", last_name="Ramirez", jersey_number="7",
            zone_id="A", direction_deviation=-1, depth_deviation=-1,
            is_thin=0, bip_count=20,
            perspective_team_id=1,
        )
        conn.commit()
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        assert "#7 RAMIRE" in svg
        assert "PATEL" not in svg
        # At least one outlier exists -> no "no outliers" note.
        assert "No outliers this opponent" not in svg


# ---------------------------------------------------------------------------
# AC-7: end-to-end determinism
# ---------------------------------------------------------------------------


class TestRenderDeterminism:
    def test_same_input_produces_same_svg_twice(self, conn):
        _insert_aggregate_row(conn, perspective_team_id=1)
        # Two near-colliding outliers to exercise the jitter path.
        _insert_batter_row(
            conn, player_id="p1", last_name="Ramirez", jersey_number="7",
            zone_id="A", direction_deviation=-1, depth_deviation=-1,
            perspective_team_id=1,
        )
        _insert_batter_row(
            conn, player_id="p2", last_name="Davis", jersey_number="11",
            zone_id="A", direction_deviation=-1, depth_deviation=-1,
            perspective_team_id=1,
        )
        conn.commit()
        svg1 = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        svg2 = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        assert svg1 == svg2


# ---------------------------------------------------------------------------
# Perspective-provenance continuity (TN-7 invariant carried forward to E-229-04)
# ---------------------------------------------------------------------------


class TestPillPerspectiveScoping:
    """The jersey-JOIN query is also perspective-scoped (TN-7). Verify
    pills from a non-chosen perspective don't leak in."""

    def test_pill_query_scopes_to_picked_perspective(self, conn):
        # Two perspectives writing pills for the same opponent. The
        # renderer picks the standalone perspective (=team_id=1) when
        # available; pills from perspective 100 must NOT appear.
        conn.execute(
            "INSERT INTO teams (id, name, membership_type) "
            "VALUES (100, 'Rival Scout', 'member')"
        )
        _insert_aggregate_row(conn, perspective_team_id=1)
        _insert_aggregate_row(conn, perspective_team_id=100)
        _insert_batter_row(
            conn, player_id="p-mine", last_name="Ramirez", jersey_number="7",
            zone_id="A", direction_deviation=-1, depth_deviation=-1,
            perspective_team_id=1,
        )
        _insert_batter_row(
            conn, player_id="p-other", last_name="Wright", jersey_number="4",
            zone_id="A", direction_deviation=-1, depth_deviation=-1,
            perspective_team_id=100,
        )
        conn.commit()
        svg = render_field_svg(conn, "opp-bears", "LF", "2026-spring-hs")
        # The picked perspective's pill renders.
        assert "#7 RAMIRE" in svg
        # The other perspective's pill must NOT render. Use the full
        # pill text rather than just the jersey number, because the SVG
        # legitimately contains `#4d4d4d` (grey-70 hex) etc.
        assert "#4 WRIGHT" not in svg
        assert "WRIGHT" not in svg
