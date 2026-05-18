"""Tests for E-229-05 compact card template (positioning_cards.html).

Covers AC-1 through AC-9 of E-229-05:

  * AC-1: 4.25"x5.5" card geometry consumed from locked-constants artifact
  * AC-2: layout per card (header / body / legend) -- structural shape
  * AC-3: sidebar lookup contents (jersey + truncated last name + zone)
  * AC-4: 4-up portrait + cut-line CSS midlines only
  * AC-5: B&W primary readability (no color-only differentiation)
  * AC-6: mobile responsive at <=640px (sm: breakpoint)
  * AC-7: state variants (no-outliers + zero-coverage)
  * AC-9: sheet-2 slots 3-4 (compass key + opponent context card)
  * AC-10: grep AC -- no retired v1 tokens in renderer.py
  * AC-11: grep AC -- no E-229-05 xfail markers remain

AC-8 (coach design review) is process-gated -- see story Notes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.reports.renderer import _build_positioning_context, render_report


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_minimal_data(positioning_rows=None, **kwargs):
    """Build a minimal `data` dict for `render_report`.

    The pitching/batting/spray/plays sections are intentionally empty;
    we only exercise the positioning-cards partial. The scouting_report
    template references many top-level data keys we want to leave
    unset, but the template's pitching template has a pre-existing
    Jinja error (pitcher.gs) when `pitching` is empty -- so we provide
    a stub that includes the gs field on the pitcher dict.
    """
    base = {
        "team": {"name": "Eastlake Bears", "season_year": 2026,
                 "record": {"wins": 5, "losses": 3}},
        "generated_at": "2026-04-13T12:00:00Z",
        "expires_at": "2026-04-27T12:00:00Z",
        "freshness_date": "2026-04-12",
        "game_count": 8,
        "recent_form": [],
        "pitching": [],
        "batting": [],
        "spray_charts": {},
        "roster": [],
        "positioning_rows": positioning_rows or [],
    }
    base.update(kwargs)
    return base


def _make_v2_row(
    *,
    player_id: str,
    position: str,
    zone_id: str | None = None,
    direction_deviation: int = 0,
    depth_deviation: int = 0,
    is_thin: int = 0,
    bip_count: int = 30,
    hr_count: int = 0,
    first_name: str = "First",
    last_name: str = "Last",
    jersey_number: str | None = "7",
) -> dict:
    """v2-shape batter_positioning row (per E-229-02's _query_batter_positioning)."""
    return {
        "player_id": player_id,
        "position": position,
        "zone_id": zone_id,
        "direction_deviation": direction_deviation,
        "depth_deviation": depth_deviation,
        "is_thin": is_thin,
        "bip_count": bip_count,
        "hr_count": hr_count,
        "first_name": first_name,
        "last_name": last_name,
        "jersey_number": jersey_number,
    }


def _make_six_v2_rows(
    *,
    player_id: str,
    per_position_zones: dict[str, str | None] | None = None,
    **batter_overrides,
) -> list[dict]:
    """Build 6 v2 batter_positioning rows (one per covered position)."""
    per_position_zones = per_position_zones or {}
    return [
        _make_v2_row(
            player_id=player_id,
            position=position,
            zone_id=per_position_zones.get(position),
            **batter_overrides,
        )
        for position in ("LF", "CF", "RF", "3B", "SS", "2B")
    ]


# ---------------------------------------------------------------------------
# AC-1 / AC-2: structural shape of the new context dict
# ---------------------------------------------------------------------------


class TestNewContextShape:
    """The rewritten `_build_positioning_context` emits a v2 shape with
    `cards` (6 cards in column order), state markers, and the locked
    legend constants imported from positioning_card.py."""

    def test_empty_rows_yields_empty_state(self):
        ctx = _build_positioning_context([])
        assert ctx["has_data"] is False
        # Still 6 cards in column order (each in zero_coverage state).
        assert len(ctx["cards"]) == 6
        assert [c["position_key"] for c in ctx["cards"]] == [
            "LF", "CF", "RF", "3B", "SS", "2B"
        ]
        for card in ctx["cards"]:
            assert card["sidebar_rows"] == []
            assert card["state"] == "zero_coverage"

    def test_locked_legend_constants_threaded(self):
        ctx = _build_positioning_context([])
        # Locked constants from positioning_card.py per artifact §F.
        assert ctx["compass_legend_short"] == "★ default · ○ textbook · A-H outliers"
        assert ctx["compass_legend_long"].startswith("A in-left ·")

    def test_card_state_inferred_from_bip_count(self):
        """Card state branches on bip_count + outlier presence."""
        # Full tier (60 BIPs) with one outlier at LF.
        rows = _make_six_v2_rows(
            player_id="p1",
            per_position_zones={"LF": "A"},
            direction_deviation=-1, depth_deviation=-1,
            bip_count=60, last_name="Ramirez", jersey_number="7",
        )
        ctx = _build_positioning_context(rows)
        lf_card = next(c for c in ctx["cards"] if c["position_key"] == "LF")
        # LF has an outlier -> full state.
        assert lf_card["state"] == "full"

    def test_card_state_no_outliers_at_full_tier(self):
        """Full tier (>=50 BIPs) with no zone_id rows -> no_outliers."""
        rows = _make_six_v2_rows(
            player_id="p1",
            per_position_zones={},  # all NULL zones
            bip_count=60, last_name="Aaron", jersey_number="3",
        )
        ctx = _build_positioning_context(rows)
        for card in ctx["cards"]:
            assert card["state"] == "no_outliers"

    def test_card_state_thin_tier(self):
        """15-49 BIPs -> thin state."""
        rows = _make_six_v2_rows(
            player_id="p1",
            per_position_zones={"LF": "B"},
            direction_deviation=-1, bip_count=25,
            last_name="Davis", jersey_number="11",
        )
        ctx = _build_positioning_context(rows)
        lf_card = next(c for c in ctx["cards"] if c["position_key"] == "LF")
        assert lf_card["state"] == "thin"

    def test_card_state_zero_coverage(self):
        """<15 BIPs -> zero_coverage."""
        rows = _make_six_v2_rows(
            player_id="p1",
            per_position_zones={"LF": "A"},
            bip_count=10, last_name="Lopez", jersey_number="9",
        )
        ctx = _build_positioning_context(rows)
        for card in ctx["cards"]:
            assert card["state"] == "zero_coverage"


# ---------------------------------------------------------------------------
# AC-3: sidebar lookup contents
# ---------------------------------------------------------------------------


class TestSidebarLookup:
    def test_sidebar_row_carries_jersey_truncated_name_zone(self):
        rows = _make_six_v2_rows(
            player_id="p1",
            per_position_zones={"LF": "A"},
            direction_deviation=-1, depth_deviation=-1,
            bip_count=60, last_name="Ramirez", jersey_number="7",
        )
        ctx = _build_positioning_context(rows)
        lf_card = next(c for c in ctx["cards"] if c["position_key"] == "LF")
        assert len(lf_card["sidebar_rows"]) == 1
        row = lf_card["sidebar_rows"][0]
        assert row["jersey_number"] == "7"
        # "Ramirez" is 7 chars -- fits the artifact §C ≤7-char budget; uppercased.
        assert row["last_name"] == "RAMIREZ"
        assert row["zone_letter"] == "A"

    def test_sidebar_row_truncates_long_last_name(self):
        """Names longer than 7 chars are truncated upstream per artifact §C."""
        rows = _make_six_v2_rows(
            player_id="p2",
            per_position_zones={"LF": "B"},
            direction_deviation=-1,
            bip_count=60, last_name="Wilkinson", jersey_number="14",
        )
        ctx = _build_positioning_context(rows)
        lf_card = next(c for c in ctx["cards"] if c["position_key"] == "LF")
        row = lf_card["sidebar_rows"][0]
        # 9 chars -> truncated to 7.
        assert row["last_name"] == "WILKINS"

    def test_thin_batter_excluded_from_sidebar(self):
        # is_thin=1 batter doesn't render as outlier (per E-229-04 AC-6).
        rows = _make_six_v2_rows(
            player_id="p-thin",
            per_position_zones={"LF": "B"},
            direction_deviation=-1, bip_count=60,  # opponent is full tier
            is_thin=1,  # but this batter is below 10-BIP gate
            last_name="Patel", jersey_number="3",
        )
        ctx = _build_positioning_context(rows)
        lf_card = next(c for c in ctx["cards"] if c["position_key"] == "LF")
        assert lf_card["sidebar_rows"] == []

    def test_null_zone_excluded_from_sidebar(self):
        # zone_id=None batter not surfaced as outlier.
        rows = _make_six_v2_rows(
            player_id="p-default",
            per_position_zones={"LF": None},
            bip_count=60, last_name="Davis", jersey_number="11",
        )
        ctx = _build_positioning_context(rows)
        lf_card = next(c for c in ctx["cards"] if c["position_key"] == "LF")
        assert lf_card["sidebar_rows"] == []

    def test_sidebar_rows_sorted_by_jersey_ascending(self):
        # Three outliers at LF with different jerseys; verify sort order.
        rows: list[dict] = []
        for jersey, last_name in (("23", "Thompson"), ("7", "Ramirez"), ("11", "Davis")):
            rows.extend(_make_six_v2_rows(
                player_id=f"p{jersey}",
                per_position_zones={"LF": "A"},
                direction_deviation=-1, depth_deviation=-1,
                bip_count=60, last_name=last_name, jersey_number=jersey,
            ))
        ctx = _build_positioning_context(rows)
        lf_card = next(c for c in ctx["cards"] if c["position_key"] == "LF")
        assert [r["jersey_number"] for r in lf_card["sidebar_rows"]] == [
            "7", "11", "23",
        ]

    def test_sidebar_truncated_when_more_than_max_rows(self):
        # 7 outliers at LF; sidebar caps at 5 with +N more footer.
        rows: list[dict] = []
        for i in range(7):
            rows.extend(_make_six_v2_rows(
                player_id=f"p{i}",
                per_position_zones={"LF": "A"},
                direction_deviation=-1, depth_deviation=-1,
                bip_count=60,
                last_name=f"P{i}", jersey_number=str(i + 1),
            ))
        ctx = _build_positioning_context(rows)
        lf_card = next(c for c in ctx["cards"] if c["position_key"] == "LF")
        assert len(lf_card["sidebar_rows"]) == 5
        assert lf_card["truncated_count"] == 2


# ---------------------------------------------------------------------------
# AC-1 / AC-4 / AC-6: Print CSS + 4-up layout + mobile breakpoint
# ---------------------------------------------------------------------------


class TestPrintCSS:
    def test_named_page_block_uses_letter_portrait(self):
        html = render_report(_make_minimal_data())
        assert "@page positioning-cards" in html
        # Per artifact §A: letter portrait at margin: 0 (the printable
        # area must equal the full 8.5"x11" sheet; any positive margin
        # would overflow the 2x2 grid -- F1 (codex P1) pre-closure
        # remediation tightened margin from 0.25in to 0).
        assert "size: letter portrait" in html
        assert "margin: 0" in html
        assert "margin: 0.25in" not in html

    def test_card_grid_is_2x2(self):
        html = render_report(_make_minimal_data())
        # 2x2 grid: grid-template-columns 1fr 1fr + grid-template-rows 1fr 1fr.
        assert "grid-template-columns: 1fr 1fr" in html
        assert "grid-template-rows: 1fr 1fr" in html

    def test_card_dimensions_match_artifact(self):
        html = render_report(_make_minimal_data())
        # Per artifact §A: 4.25 x 5.5 quarter-letter.
        assert "width: 4.25in" in html
        assert "height: 5.5in" in html

    def test_cut_lines_present_no_corner_marks(self):
        """Per AC-4 + artifact §A: dashed midline cuts; no corner crop marks
        or full-card borders."""
        html = render_report(_make_minimal_data())
        # Dashed cut-line stroke on internal card edges.
        assert "dashed" in html
        # No corner crop marks or full perimeter borders.
        assert "crop-mark" not in html.lower()


class TestMobileResponsive:
    def test_mobile_breakpoint_uses_sm_640px_not_md(self):
        """Per AC-6 + UXD I-5: breakpoint is sm: (640px), NOT md: (768px)."""
        html = render_report(_make_minimal_data())
        # @media query at max-width: 640px.
        assert "@media screen and (max-width: 640px)" in html
        # No md: breakpoint at 768px (would be wrong).
        assert "max-width: 768px" not in html

    def test_mobile_collapses_to_single_column(self):
        html = render_report(_make_minimal_data())
        # Inside the @media block, the grid-template-columns reduces.
        # The exact rule depends on the CSS body; assert a marker
        # that's specific to the mobile path.
        assert "grid-template-columns: 1fr" in html


# ---------------------------------------------------------------------------
# AC-5: B&W primary readability
# ---------------------------------------------------------------------------


class TestBlackAndWhitePrimary:
    """Per AC-5 + artifact §F color-not-load-bearing rule. All information
    is communicated by shape, position, or text -- color is decorative
    only. SVG/CSS color values are restricted to black, white, and
    grey-scale."""

    def test_no_disallowed_colors_in_template(self):
        """The positioning_cards.html template should use only black,
        white, and grey-scale colors (R=G=B hex literals or named
        greys). Specifically: no saturated hex like #1e3a5f or #ff0000.
        """
        # Load the raw template file (the rendered output also embeds
        # the template's CSS).
        template_path = (
            Path(__file__).parent.parent
            / "src" / "api" / "templates" / "reports" / "positioning_cards.html"
        )
        text = template_path.read_text()
        # Find all hex color literals.
        import re
        hex_colors = re.findall(r"#([0-9a-fA-F]{3,8})\b", text)
        for color in hex_colors:
            # Normalize 3-char hex to 6-char.
            if len(color) == 3:
                color = "".join(c * 2 for c in color)
            elif len(color) == 4:  # rgba shorthand
                color = "".join(c * 2 for c in color[:3])
            elif len(color) == 8:  # 8-char hex (rgba)
                color = color[:6]
            assert len(color) == 6, f"unexpected hex color: {color!r}"
            r, g, b = color[0:2], color[2:4], color[4:6]
            assert r == g == b, (
                f"Non-grey color in positioning_cards.html: #{color} -- "
                f"AC-5 / artifact §F forbids color-only differentiation"
            )

    def test_no_saturated_color_names_in_template(self):
        template_path = (
            Path(__file__).parent.parent
            / "src" / "api" / "templates" / "reports" / "positioning_cards.html"
        )
        text = template_path.read_text().lower()
        # Disallowed CSS color names that aren't black/white/grey.
        for forbidden in (
            "red", "green", "blue", "yellow", "orange", "purple",
            "magenta", "cyan", "pink", "brown", "navy", "teal",
            "olive", "maroon", "lime",
        ):
            assert f": {forbidden}" not in text, (
                f"saturated color name {forbidden!r} in template -- "
                f"AC-5 / artifact §F forbids color-only differentiation"
            )


# ---------------------------------------------------------------------------
# AC-7: state variants render cleanly
# ---------------------------------------------------------------------------


class TestStateVariants:
    def test_no_outliers_state_renders_banner(self):
        rows = _make_six_v2_rows(
            player_id="p1",
            per_position_zones={},  # no zones populated
            bip_count=60, last_name="Aaron", jersey_number="3",
        )
        html = render_report(_make_minimal_data(rows))
        # Banner text per artifact §C IM-1 / UXD M-4.
        assert "No outliers this opponent" in html

    def test_zero_coverage_state_renders_message(self):
        rows = _make_six_v2_rows(
            player_id="p1",
            per_position_zones={"LF": "A"},
            direction_deviation=-1, depth_deviation=-1,
            bip_count=10,  # below 15-BIP threshold
            last_name="Patel", jersey_number="9",
        )
        html = render_report(_make_minimal_data(rows))
        # Per AC-7: dominant "Not enough spray data" message.
        assert "Not enough spray data" in html

    def test_full_state_with_outliers_renders_sidebar_rows(self):
        rows = _make_six_v2_rows(
            player_id="p1",
            per_position_zones={"LF": "A"},
            direction_deviation=-1, depth_deviation=-1,
            bip_count=60, last_name="Ramirez", jersey_number="7",
        )
        html = render_report(_make_minimal_data(rows))
        # Jersey + truncated name + zone letter appear in the sidebar.
        assert "#7" in html
        assert "RAMIRE" in html
        # Zone letter A appears in the LF sidebar.
        assert ">A<" in html


# ---------------------------------------------------------------------------
# AC-9: sheet-2 slots 3 + 4 (compass key + opponent context card)
# ---------------------------------------------------------------------------


class TestSheet2ExtraSlots:
    def test_compass_key_card_renders_on_sheet_2(self):
        html = render_report(_make_minimal_data())
        # Compass-key card header text per artifact §D slot 3.
        assert "Compass Key" in html
        assert "8-zone field compass" in html

    def test_opponent_context_card_renders_on_sheet_2(self):
        html = render_report(_make_minimal_data())
        # Position-name slot text per artifact §D slot 4.
        assert "Opponent context" in html
        # Cut-and-keep legend per artifact §D.
        assert "cut and keep with the call sheet" in html


# ---------------------------------------------------------------------------
# AC-10 + AC-11: grep ACs
# ---------------------------------------------------------------------------


class TestGrepACs:
    """AC-10 + AC-11 enforce that retired v1 tokens are gone from the
    listed files. These tests catch regressions where a future change
    re-introduces a retired symbol."""

    _RETIRED_TOKENS = (
        "POSITIONING_CALL_WORDS",
        "POSITIONING_CELL_SHORT_FORMS",
        "POSITIONING_COLUMN_ORDER",
        "POSITIONING_POSITION_LABELS",
        "call_state",
        "team_state_call",
        "direction_shade",
        "depth_shade",
        "zone_concentration",
    )

    def test_ac10_renderer_py_clean(self):
        """AC-10: none of the retired v1 tokens appear in
        src/reports/renderer.py."""
        renderer_path = (
            Path(__file__).parent.parent
            / "src" / "reports" / "renderer.py"
        )
        text = renderer_path.read_text()
        for token in self._RETIRED_TOKENS:
            assert token not in text, (
                f"retired token {token!r} still present in renderer.py "
                f"-- E-229-05 AC-10 grep AC violated"
            )

    def test_ac11_no_e229_05_xfail_markers_remain(self):
        """AC-11: no @pytest.mark.xfail with reason citing E-229-05 remains
        in test_report_renderer.py or test_report_generator.py."""
        for test_file in (
            "test_report_renderer.py",
            "test_report_generator.py",
        ):
            test_path = Path(__file__).parent / test_file
            text = test_path.read_text()
            # Find xfail markers. The pattern is `@pytest.mark.xfail(...)`
            # with `reason="..."` in the kwargs. Match `xfail` + nearby
            # `E-229-05` within a reasonable character window.
            import re
            for match in re.finditer(r"xfail\b[\s\S]{0,500}?\)", text):
                block = match.group(0)
                # An xfail block citing E-229-05 violates AC-11.
                assert "E-229-05" not in block, (
                    f"AC-11 violation: xfail marker citing E-229-05 "
                    f"in {test_file}: {block[:120]}..."
                )
