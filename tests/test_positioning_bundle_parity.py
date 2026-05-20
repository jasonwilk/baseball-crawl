"""Bundle parity regression test for E-230 (AC-9).

The E-230 changes touch the shared ``positioning_cards.html`` partial
(adds a ``chart_mode`` gate) and the scouting-report payload helper,
but MUST NOT change the standalone positioning-bundle output at
``data/reports/{slug}/index.html``. This test pins that invariant.

The assertions are content-level slot-fill per ``.claude/rules/testing.md``:
we verify the bundle HTML CONTAINS the distinguishing bundle markup
(position labels, star polygons, BIP captions, compass letters,
compass-key card) AND does NOT contain the scouting-report image-mode
markup. Byte-equality is intentionally NOT tested — that would couple
to incidental whitespace and footer timestamp drift.
"""
from __future__ import annotations

import sqlite3

import pytest

from src.reports.positioning import COVERED_POSITIONS
from src.reports.positioning_bundle import generate_positioning_bundle
from tests.conftest import load_real_schema

_SEASON = "2026-spring-hs"


# ---------------------------------------------------------------------------
# Fixture seeding (mirrors tests/test_positioning_bundle.py shape so the
# bundle has enough data to render its full sheet 1 + sheet 2 layout).
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path):
    """Schema-loaded connection seeded with tracked opponent + member team."""
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


def _seed_aggregates(conn):
    """Seed full-tier aggregates across all 6 positions."""
    for p in COVERED_POSITIONS:
        conn.execute(
            """
            INSERT INTO team_position_aggregate (
                team_id, season_id, perspective_team_id, position,
                star_x, star_y, bip_count, is_low_confidence
            ) VALUES (1, ?, 1, ?, 160.0, 200.0, 60, 0)
            """,
            (_SEASON, p),
        )


def _seed_batter_rows(conn):
    """Three batters with at least one outlier each for sheet-1 sidebar fill."""
    conn.execute(
        "INSERT INTO players (player_id, first_name, last_name) "
        "VALUES ('p1', 'Hank', 'Ramirez')"
    )
    conn.execute(
        "INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number) "
        "VALUES (1, 'p1', ?, '7')",
        (_SEASON,),
    )
    # Outlier: LF zone A
    conn.execute(
        """
        INSERT INTO batter_positioning (
            player_id, team_id, season_id, perspective_team_id, position,
            direction_deviation, depth_deviation, zone_id,
            is_thin, bip_count, hr_count
        ) VALUES ('p1', 1, ?, 1, 'LF', -1, -1, 'A', 0, 20, 0)
        """,
        (_SEASON,),
    )
    # Default rows for the remaining positions.
    for p in ("CF", "RF", "3B", "SS", "2B"):
        conn.execute(
            """
            INSERT INTO batter_positioning (
                player_id, team_id, season_id, perspective_team_id, position,
                direction_deviation, depth_deviation, zone_id,
                is_thin, bip_count, hr_count
            ) VALUES ('p1', 1, ?, 1, ?, 0, 0, NULL, 0, 20, 0)
            """,
            (_SEASON, p),
        )


def _seed_full_opponent(conn):
    """Seed enough data for the bundle to render its full cards layout."""
    _seed_aggregates(conn)
    _seed_batter_rows(conn)
    conn.commit()


# ---------------------------------------------------------------------------
# AC-9 parity assertions
# ---------------------------------------------------------------------------


def _generate_bundle_html(conn) -> str:
    """Generate the bundle HTML with stable inputs for content-level
    parity. through_date + game_count are caller-supplied so the
    rendered cue is invariant across test runs.
    """
    return generate_positioning_bundle(
        conn, "opp-bears", _SEASON,
        opponent_name="Opp Bears",
        through_date="Apr 12",
        game_count=12,
    )


def test_bundle_renders_full_html_document(conn):
    """Sanity check: bundle returns a complete HTML document."""
    _seed_full_opponent(conn)
    html = _generate_bundle_html(conn)
    assert isinstance(html, str)
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html


@pytest.mark.parametrize("position", list(COVERED_POSITIONS))
def test_bundle_contains_each_position_label(conn, position: str):
    """AC-9: bundle's per-card position labels render verbatim.

    The bundle's cards layout emits position labels via
    `_position_full_name()` (e.g. ``LEFT FIELD``, ``CENTER FIELD``) AND
    via `position_label` in the template. The position-key letter
    appears in the sidebar title (``Outliers (LF)``) and the data
    attribute (``data-position="LF"``). All three forms are bundle
    invariants — none should disappear when chart_mode='svg' is set
    explicitly.
    """
    _seed_full_opponent(conn)
    html = _generate_bundle_html(conn)
    # Position key in the data-position attribute (sheet 1 + sheet 2).
    assert f'data-position="{position}"' in html
    # Position key in the sidebar title.
    assert f"Outliers ({position})" in html


def test_bundle_contains_star_polygon_for_populated_cards(conn):
    """AC-9: per-card star polygons render in the cards' field SVGs.

    The team-aggregate star is rendered via `<polygon points="...">`
    inside each card's field SVG. With aggregates seeded for all 6
    positions, every card should carry the star polygon markup.
    """
    _seed_full_opponent(conn)
    html = _generate_bundle_html(conn)
    # `_star_polygon_points()` in src/reports/positioning_card.py
    # returns the same point string for every star; assert the marker
    # appears at least 6 times (one per populated card).
    star_marker = '<polygon points="0,-8'
    assert html.count(star_marker) >= 6, (
        f"expected ≥6 star polygons (one per populated card), got "
        f"{html.count(star_marker)}"
    )


def test_bundle_contains_bip_count_captions(conn):
    """AC-9: per-card BIP captions render in the populated cards.

    The card SVG emits ``({N} BIP)`` text below each star (the engine
    seeded bip_count=60 across all 6 positions).
    """
    _seed_full_opponent(conn)
    html = _generate_bundle_html(conn)
    # Each populated card carries `(60 BIP)`.
    assert "(60 BIP)" in html


def test_bundle_contains_compass_letters(conn):
    """AC-9: compass discs A through H render on each per-position card.

    The cards' compass ring emits 8 `<text>` elements per card with
    letters A..H. These should appear in the bundle HTML.
    """
    _seed_full_opponent(conn)
    html = _generate_bundle_html(conn)
    # Each letter should appear at least once in the rendered HTML.
    for letter in "ABCDEFGH":
        # Match the `>X<` form to avoid false-positive on stray chars.
        assert f">{letter}<" in html, (
            f"compass letter {letter} missing from bundle HTML"
        )


def test_bundle_contains_compass_key_card(conn):
    """AC-9: the bundle-specific compass-key reference card renders.

    Page 4 / slot 3 of the bundle is the opponent-independent compass-
    key reference (E-229-09 / F2a). It carries a distinguishing CSS
    class and its own SVG markup that does NOT appear in the scouting-
    report path.
    """
    _seed_full_opponent(conn)
    html = _generate_bundle_html(conn)
    assert 'class="positioning-card compass-key"' in html
    assert "Compass Key" in html


def test_bundle_renders_in_svg_mode_not_image_mode(conn):
    """AC-9: the bundle HTML MUST NOT contain image-mode markup.

    If the partial's `chart_mode='svg'` gate were broken (or the
    bundle's `cards_ctx` lost the `chart_mode='svg'` flag), the partial
    would render the scouting-report's image-mode block instead of the
    inline-SVG bundle layout. The image-mode block emits `<img
    src="data:image/png;base64,..."` markup, which has no business
    appearing in the bundle. This assertion pins that.
    """
    _seed_full_opponent(conn)
    html = _generate_bundle_html(conn)
    assert "<img src=\"data:image/png;base64," not in html, (
        "bundle HTML contains scouting-report image-mode markup; "
        "chart_mode='svg' gate is broken"
    )
    # Also confirm the image-mode wrapper elements aren't rendered.
    # NOTE: the class names themselves appear in the partial's <style>
    # block (CSS definitions are emitted in both modes), so we check
    # for the actual element form `<div class="...">` to scope the
    # assertion to rendered DOM rather than CSS rules.
    assert '<div class="positioning-card-grid-image"' not in html
    assert '<div class="positioning-image-section"' not in html


def test_bundle_renders_two_sheets(conn):
    """AC-9: the bundle's 2-sheet quarter-letter layout is preserved.

    Two `.positioning-cards-sheet` sections (sheet-1 + sheet-2) are the
    bundle's distinguishing layout. The image-mode block has none.
    """
    _seed_full_opponent(conn)
    html = _generate_bundle_html(conn)
    assert html.count("positioning-cards-sheet") >= 2
    assert "sheet-1" in html
    assert "sheet-2" in html


def test_bundle_contains_coverage_cue(conn):
    """AC-9: bundle's coverage cue text format is preserved.

    The bundle renders ``Through {date} ({N} games)`` (bundle's
    legacy format from E-229) — distinct from the scouting-report's
    new ``Through {date} · {N} games · {M} BIP`` format. Pinning the
    bundle's format here protects the standalone print artifact's
    visual contract.
    """
    _seed_full_opponent(conn)
    html = _generate_bundle_html(conn)
    assert "Through Apr 12 (12 games)" in html
