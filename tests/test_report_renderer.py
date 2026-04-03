"""Tests for the standalone scouting report renderer (E-172-01, E-185-01)."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from src.reports.renderer import (
    render_report,
    _BATTING_HEAT_TIERS,
    _PITCHING_HEAT_TIERS,
    _compute_batting_enrichments,
    _compute_batting_heat,
    _compute_key_players,
    _compute_pa,
    _compute_pitching_heat,
    _build_spray_player_stats,
    _format_pct,
    _format_plays_batting,
    _format_plays_pitching,
    _format_rate,
    _max_heat_for_depth,
    _percentile_rank,
    _percentile_to_level,
    _safe_div,
)


def _make_pitcher(
    name: str = "John Smith",
    jersey_number: int | None = 12,
    ip_outs: int = 60,
    **overrides,
) -> dict:
    """Build a pitcher stat dict with sensible defaults."""
    base = {
        "name": name,
        "jersey_number": jersey_number,
        "era": "2.50",
        "k9": "9.0",
        "whip": "1.10",
        "games": 8,
        "ip_outs": ip_outs,
        "h": 20,
        "er": 5,
        "bb": 10,
        "so": 30,
        "pitches": 400,
        "strike_pct": "62%",
    }
    base.update(overrides)
    return base


def _make_batter(
    name: str = "Jane Doe",
    jersey_number: int | None = 7,
    ab: int = 50,
    player_id: int = 100,
    **overrides,
) -> dict:
    """Build a batter stat dict with sensible defaults."""
    base = {
        "player_id": player_id,
        "name": name,
        "jersey_number": jersey_number,
        "games": 12,
        "ab": ab,
        "h": 15,
        "bb": 8,
        "hbp": 1,
        "shf": 0,
        "doubles": 3,
        "triples": 1,
        "hr": 2,
        "rbi": 10,
        "so": 12,
        "sb": 4,
        "cs": 1,
    }
    base.update(overrides)
    return base


def _make_full_data(**overrides) -> dict:
    """Build a complete report data dict."""
    base = {
        "team": {
            "name": "Test Tigers",
            "season_year": 2026,
            "record": {"wins": 15, "losses": 5},
        },
        "generated_at": "2026-03-28T12:00:00Z",
        "expires_at": "2026-04-11T12:00:00Z",
        "freshness_date": "2026-03-25",
        "game_count": 20,
        "recent_form": [
            {"result": "W", "our_score": 7, "their_score": 3,
             "opponent_name": "Rival", "is_home": True},
            {"result": "L", "our_score": 2, "their_score": 4,
             "opponent_name": "Other", "is_home": False},
            {"result": "W", "our_score": 5, "their_score": 1,
             "opponent_name": "Third", "is_home": True},
        ],
        "pitching": [_make_pitcher()],
        "batting": [_make_batter()],
        "spray_charts": {},
        "roster": [
            {"jersey_number": 7, "name": "Jane Doe", "position": "SS"},
            {"jersey_number": 12, "name": "John Smith", "position": "P"},
        ],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# AC-9(a): Renderer produces valid HTML containing expected sections
# ---------------------------------------------------------------------------


class TestCompleteReport:
    """Test renderer output with complete data."""

    def test_produces_html_with_all_sections(self):
        data = _make_full_data()
        html = render_report(data)

        assert "<!DOCTYPE html>" in html
        assert "Test Tigers" in html
        assert "Scouting Report" in html
        # Header meta
        assert "2026" in html
        assert "15-5" in html
        # Executive summary
        assert "20 games" in html
        assert "Mar 25" in html
        # Recent form chips
        assert "Recent Form:" in html
        assert "W 7-3" in html
        assert "L 2-4" in html
        assert "Rival" in html  # opponent name in chip
        # Sort annotations
        assert "Sorted by innings pitched" in html
        assert "Sorted by plate appearances" in html
        # Pitching section
        assert "Pitching" in html
        assert "John Smith" in html
        assert "2.50" in html  # ERA
        # Batting section
        assert "Batting" in html
        assert "Jane Doe" in html
        # Heat map CSS classes
        assert "heat-" in html
        # Roster
        assert "Roster" in html
        assert "#7" in html
        assert "SS" in html
        # Footer
        assert "Generated 2026-03-28" in html
        assert "bbstats.ai" in html

    def test_html_is_self_contained_no_external_urls(self):
        data = _make_full_data()
        html = render_report(data)

        # No external CSS/JS/image links
        assert "http://" not in html
        assert "https://" not in html
        assert "<link" not in html.lower()
        assert '<script src' not in html.lower()

    def test_print_css_rules_present(self):
        data = _make_full_data()
        html = render_report(data)

        assert "@media print" in html
        assert "page-break-inside: avoid" in html
        assert "size: landscape" in html

    def test_mobile_css_rules_present(self):
        data = _make_full_data()
        html = render_report(data)

        assert "@media screen and (max-width: 640px)" in html

    def test_print_button_present(self):
        data = _make_full_data()
        html = render_report(data)

        assert "Print / Save as PDF" in html
        assert "screen-only" in html

    def test_pitching_columns_match_redesign(self):
        """Verify pitching table has the expected column headers per TN-4."""
        data = _make_full_data()
        html = render_report(data)

        for col in ["THR", "ERA", "K/9", "WHIP", "GP", "IP", "H", "ER", "BB", "SO", "#P", "Strike%"]:
            assert f">{col}<" in html or f">{col}</th>" in html

    def test_batting_columns_match_redesign(self):
        """Verify batting table has the expected column headers per TN-3."""
        data = _make_full_data()
        html = render_report(data)

        for col in ["THR", "OBP", "AVG", "SLG", "K%", "BB%", "GP", "PA", "AB", "H", "XBH", "HR", "RBI", "BB", "SO", "SB-CS", "HBP"]:
            assert f">{col}<" in html or f">{col}</th>" in html


# ---------------------------------------------------------------------------
# AC-9(b): Spray charts appear as base64 data URIs
# ---------------------------------------------------------------------------


class TestSprayCharts:
    """Test spray chart rendering and embedding."""

    def test_spray_charts_as_base64_data_uris(self):
        """AC-9(b): Spray charts embedded as data:image/png;base64."""
        batter = _make_batter(player_id=42)
        events = [
            {"x": 150.0, "y": 200.0, "play_result": "single", "play_type": "line_drive"}
            for _ in range(12)
        ]
        data = _make_full_data(
            batting=[batter],
            spray_charts={42: events},
        )

        # Mock render_spray_chart to avoid matplotlib rendering in tests.
        # src.charts.spray has a top-level matplotlib import, so inject a
        # mock module into sys.modules before patching the function.
        from src.charts.spray import classify_field_zone, contact_type_label
        fake_png = b"\x89PNG_FAKE_DATA"
        mock_spray_mod = MagicMock()
        mock_spray_mod.render_spray_chart = MagicMock(return_value=fake_png)
        mock_spray_mod.classify_field_zone = classify_field_zone
        mock_spray_mod.contact_type_label = contact_type_label
        with patch.dict("sys.modules", {"src.charts.spray": mock_spray_mod}):
            html = render_report(data)

        assert "data:image/png;base64," in html
        # The base64-encoded fake PNG should be present
        import base64
        expected_b64 = base64.b64encode(fake_png).decode("ascii")
        assert expected_b64 in html

    def test_spray_charts_below_threshold_excluded(self):
        """Players with fewer than 3 BIP have no spray chart."""
        batter = _make_batter(player_id=42)
        events = [
            {"x": 150.0, "y": 200.0, "play_result": "single", "play_type": "ground_ball"}
            for _ in range(2)  # Below 3 BIP threshold
        ]
        data = _make_full_data(
            batting=[batter],
            spray_charts={42: events},
        )

        html = render_report(data)

        assert "data:image/png;base64," not in html
        assert "Batter Tendencies" not in html


# ---------------------------------------------------------------------------
# AC-9(c): Missing spray chart data => section omitted
# ---------------------------------------------------------------------------


class TestMissingSprayCharts:
    """Test behavior when spray chart data is absent."""

    def test_no_spray_charts_key(self):
        data = _make_full_data()
        del data["spray_charts"]
        html = render_report(data)

        assert "Batter Tendencies" not in html
        assert "data:image/png;base64," not in html

    def test_empty_spray_charts(self):
        data = _make_full_data(spray_charts={})
        html = render_report(data)

        assert "Batter Tendencies" not in html

    def test_spray_charts_none(self):
        data = _make_full_data(spray_charts=None)
        html = render_report(data)

        assert "Batter Tendencies" not in html


# ---------------------------------------------------------------------------
# AC-9(d): Missing stats produce "No data available"
# ---------------------------------------------------------------------------


class TestMissingStats:
    """Test graceful handling of missing stat data."""

    def test_empty_pitching_shows_no_data(self):
        data = _make_full_data(pitching=[])
        html = render_report(data)

        # The pitching section header should be present
        assert "Pitching" in html
        assert "No data available" in html

    def test_empty_batting_shows_no_data(self):
        data = _make_full_data(batting=[])
        html = render_report(data)

        assert "Batting" in html
        assert "No data available" in html

    def test_none_pitching_shows_no_data(self):
        data = _make_full_data(pitching=None)
        html = render_report(data)

        assert "No data available" in html

    def test_none_batting_shows_no_data(self):
        data = _make_full_data(batting=None)
        html = render_report(data)

        assert "No data available" in html

    def test_missing_schedule_omits_recent_form(self):
        """AC-8: If schedule data is absent, recent form section is omitted."""
        data = _make_full_data(recent_form=None)
        html = render_report(data)

        assert "Recent Form:" not in html

    def test_empty_recent_form_omits_section(self):
        data = _make_full_data(recent_form=[])
        html = render_report(data)

        assert "Recent Form:" not in html


# ---------------------------------------------------------------------------
# AC-9(e): Data freshness line appears in header
# ---------------------------------------------------------------------------


class TestFreshnessLine:
    """Test the data freshness line in the header."""

    def test_freshness_date_appears(self):
        data = _make_full_data(freshness_date="2026-03-25", game_count=20)
        html = render_report(data)

        assert "Mar 25" in html
        assert "20 games" in html

    def test_freshness_date_none_omits_through(self):
        data = _make_full_data(freshness_date=None, game_count=5)
        html = render_report(data)

        # No "through <date>" when freshness_date is None
        assert "through Mar" not in html
        assert "5 games" in html

    def test_zero_games_no_freshness(self):
        data = _make_full_data(freshness_date=None, game_count=0)
        html = render_report(data)

        # Exec summary should not render when no data
        assert "0 games" not in html


# ---------------------------------------------------------------------------
# AC-9(f): Small sample indicator for low-PA/IP players
# ---------------------------------------------------------------------------


class TestNoSuppression:
    """E-187: Verify suppression artifacts are removed."""

    def test_no_dimming_class_on_any_row(self):
        """AC-16: No batting or pitching row has the small-sample CSS class."""
        # Include a low-IP pitcher and a low-PA batter
        pitcher = _make_pitcher(ip_outs=10, name="Low IP Pitcher")
        batter = _make_batter(ab=1, bb=0, hbp=0, shf=0, name="Low PA Batter")
        data = _make_full_data(pitching=[pitcher], batting=[batter])
        html = render_report(data)

        assert 'class="small-sample"' not in html
        assert "tr.small-sample" not in html

    def test_no_asterisk_on_any_player_name(self):
        """AC-17: No player name contains an asterisk between name and badge."""
        pitcher = _make_pitcher(ip_outs=10, name="Low IP Pitcher")
        batter = _make_batter(ab=1, bb=0, hbp=0, shf=0, name="Low PA Batter")
        data = _make_full_data(pitching=[pitcher], batting=[batter])
        html = render_report(data)

        # No asterisk anywhere between player name and depth badge
        assert "Low IP Pitcher *" not in html
        assert "Low PA Batter *" not in html
        # Also check the generic patterns
        assert " *<" not in html
        assert " * <span" not in html

    def test_no_footnote_div(self):
        """AC-18: No footnote div containing 'Small sample size' is present."""
        pitcher = _make_pitcher(ip_outs=10, name="Low IP Pitcher")
        batter = _make_batter(ab=1, bb=0, hbp=0, shf=0, name="Low PA Batter")
        data = _make_full_data(pitching=[pitcher], batting=[batter])
        html = render_report(data)

        assert "Small sample size" not in html
        assert "fewer than" not in html
        assert "small-sample-footnote" not in html

    def test_low_ip_pitcher_still_displays(self):
        """Pitcher below threshold is still displayed at full weight."""
        pitcher = _make_pitcher(ip_outs=10, name="Low IP Pitcher")
        data = _make_full_data(pitching=[pitcher])
        html = render_report(data)

        assert "Low IP Pitcher" in html

    def test_low_pa_batter_still_displays(self):
        """Batter below threshold is still displayed at full weight."""
        batter = _make_batter(ab=1, bb=0, hbp=0, shf=0, name="Low PA Batter")
        data = _make_full_data(batting=[batter])
        html = render_report(data)

        assert "Low PA Batter" in html


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test edge cases and robustness."""

    def test_missing_team_record(self):
        data = _make_full_data()
        data["team"]["record"] = None
        html = render_report(data)

        assert "Test Tigers" in html
        # Should not crash

    def test_missing_season_year(self):
        data = _make_full_data()
        data["team"]["season_year"] = None
        html = render_report(data)

        assert "Test Tigers" in html

    def test_empty_roster(self):
        data = _make_full_data(roster=[])
        html = render_report(data)

        # The roster section header should not appear (CSS class names will)
        assert ">Roster<" not in html

    def test_pitcher_missing_pitches(self):
        pitcher = _make_pitcher(pitches=None, strike_pct=None)
        data = _make_full_data(pitching=[pitcher])
        html = render_report(data)

        # Should render mdash for missing values, not crash
        assert "John Smith" in html

    def test_spray_chart_render_failure_is_non_fatal(self):
        """If spray chart rendering raises, the chart is skipped."""
        batter = _make_batter(player_id=42)
        events = [
            {"x": 150.0, "y": 200.0, "play_result": "single", "play_type": "line_drive"}
            for _ in range(12)
        ]
        data = _make_full_data(batting=[batter], spray_charts={42: events})

        from src.charts.spray import classify_field_zone, contact_type_label
        mock_spray_mod = MagicMock()
        mock_spray_mod.render_spray_chart = MagicMock(side_effect=RuntimeError("render failed"))
        mock_spray_mod.classify_field_zone = classify_field_zone
        mock_spray_mod.contact_type_label = contact_type_label
        with patch.dict("sys.modules", {"src.charts.spray": mock_spray_mod}):
            html = render_report(data)

        # Should not crash; spray section should be omitted
        assert "Batter Tendencies" not in html
        assert "<!DOCTYPE html>" in html

    def test_single_game_count_singular(self):
        data = _make_full_data(game_count=1)
        html = render_report(data)
        assert "1 game" in html
        assert "1 games" not in html


# ===========================================================================
# E-185-01: New enrichment tests
# ===========================================================================


# ---------------------------------------------------------------------------
# _compute_pa
# ---------------------------------------------------------------------------


class TestComputePa:
    def test_basic(self):
        assert _compute_pa({"ab": 50, "bb": 10, "hbp": 2, "shf": 1}) == 63

    def test_missing_fields(self):
        assert _compute_pa({}) == 0

    def test_none_fields(self):
        assert _compute_pa({"ab": None, "bb": None, "hbp": None, "shf": None}) == 0


# ---------------------------------------------------------------------------
# Batting enrichments: K%, BB%, XBH, SB-CS
# ---------------------------------------------------------------------------


class TestBattingEnrichments:
    def _player(self, **overrides):
        base = {
            "ab": 50, "bb": 10, "hbp": 2, "shf": 1,
            "h": 15, "so": 12, "sb": 5, "cs": 2,
            "doubles": 3, "triples": 1, "hr": 2,
            "rbi": 10, "games": 20,
        }
        base.update(overrides)
        return base

    def test_k_pct(self):
        batting = [self._player()]
        _compute_batting_enrichments(batting)
        # so=12, pa=63 -> 19.0%
        assert batting[0]["_k_pct"] == "19.0%"

    def test_bb_pct(self):
        batting = [self._player()]
        _compute_batting_enrichments(batting)
        # bb=10, pa=63 -> 15.9%
        assert batting[0]["_bb_pct"] == "15.9%"

    def test_xbh(self):
        batting = [self._player()]
        _compute_batting_enrichments(batting)
        # doubles=3 + triples=1 + hr=2 = 6
        assert batting[0]["_xbh"] == 6

    def test_sb_cs(self):
        batting = [self._player()]
        _compute_batting_enrichments(batting)
        assert batting[0]["_sb_cs"] == "5-2"

    def test_zero_pa(self):
        batting = [self._player(ab=0, bb=0, hbp=0, shf=0)]
        _compute_batting_enrichments(batting)
        assert batting[0]["_k_pct"] == "-"
        assert batting[0]["_bb_pct"] == "-"
        assert batting[0]["_small_sample"] is True

    def test_small_sample_flag(self):
        batting = [self._player(ab=2, bb=1, hbp=0, shf=0)]  # PA=3 < 5
        _compute_batting_enrichments(batting)
        assert batting[0]["_small_sample"] is True

    def test_large_sample_flag(self):
        batting = [self._player()]  # PA=63 >= 5
        _compute_batting_enrichments(batting)
        assert batting[0]["_small_sample"] is False

    def test_boundary_pa_5_is_qualified(self):
        """AC-3: PA=5 is exactly at threshold -- NOT small sample."""
        batting = [self._player(ab=3, bb=1, hbp=1, shf=0)]  # PA=5
        _compute_batting_enrichments(batting)
        assert batting[0]["_small_sample"] is False

    def test_boundary_pa_4_is_small_sample(self):
        """PA=4 is below threshold -- IS small sample."""
        batting = [self._player(ab=3, bb=1, hbp=0, shf=0)]  # PA=4
        _compute_batting_enrichments(batting)
        assert batting[0]["_small_sample"] is True


# ---------------------------------------------------------------------------
# Heat-level computation
# ---------------------------------------------------------------------------


class TestPercentileRank:
    def test_single_value(self):
        assert _percentile_rank(5.0, [5.0]) == 1.0

    def test_all_same(self):
        assert _percentile_rank(3.0, [3.0, 3.0, 3.0]) == 1.0

    def test_ordered(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert _percentile_rank(3.0, vals) == 0.6  # 3 of 5

    def test_empty(self):
        assert _percentile_rank(5.0, []) == 0.0


class TestPercentileToLevel:
    def test_top(self):
        assert _percentile_to_level(0.85) == 4

    def test_mid_high(self):
        assert _percentile_to_level(0.55) == 3

    def test_mid_low(self):
        assert _percentile_to_level(0.25) == 2

    def test_bottom(self):
        assert _percentile_to_level(0.10) == 1

    def test_boundary_70(self):
        assert _percentile_to_level(0.70) == 4

    def test_boundary_40(self):
        assert _percentile_to_level(0.40) == 3

    def test_boundary_20(self):
        assert _percentile_to_level(0.20) == 2

    def test_boundary_0(self):
        assert _percentile_to_level(0.0) == 1


class TestBattingHeat:
    def _player(self, ab, h, bb, hbp, shf, doubles=0, triples=0, hr=0, so=0, **kw):
        p = {
            "ab": ab, "h": h, "bb": bb, "hbp": hbp, "shf": shf,
            "doubles": doubles, "triples": triples, "hr": hr,
            "so": so, "sb": 0, "cs": 0, "rbi": 0, "games": 10,
        }
        p.update(kw)
        return p

    def test_small_sample_all_zero(self):
        batting = [self._player(ab=4, h=2, bb=0, hbp=0, shf=0)]  # PA=4 < 5
        _compute_batting_enrichments(batting)
        _compute_batting_heat(batting)
        assert batting[0]["_heat"] == {"avg": 0, "obp": 0, "slg": 0, "thr": 0}
        assert batting[0]["_thr_score"] == 0.0

    def test_single_qualified_player_depth_cap(self):
        """A single qualified player: depth cap = 0 (1 qualified < 3), so heat-0."""
        batting = [self._player(ab=50, h=15, bb=5, hbp=2, shf=1, doubles=3)]
        _compute_batting_enrichments(batting)
        _compute_batting_heat(batting)
        heat = batting[0]["_heat"]
        # Only 1 qualified player: below the minimum tier of 3 -> cap=0
        assert heat == {"avg": 0, "obp": 0, "slg": 0, "thr": 0}

    def test_mixed_small_and_large_sample(self):
        """Small sample player gets 0 heat, large sample constrained by depth cap."""
        large = self._player(ab=50, h=15, bb=5, hbp=2, shf=1)
        small = self._player(ab=2, h=1, bb=0, hbp=0, shf=0)  # PA=2 < 5
        batting = [large, small]
        _compute_batting_enrichments(batting)
        _compute_batting_heat(batting)
        assert batting[1]["_heat"] == {"avg": 0, "obp": 0, "slg": 0, "thr": 0}
        # Only 1 qualified: depth cap is 0
        assert batting[0]["_heat"] == {"avg": 0, "obp": 0, "slg": 0, "thr": 0}

    def test_all_same_value_players_9_qualified(self):
        """When 9+ qualified players have identical stats, all get level 4 (full cap)."""
        batting = [
            self._player(ab=50, h=15, bb=5, hbp=2, shf=1)
            for _ in range(9)
        ]
        _compute_batting_enrichments(batting)
        _compute_batting_heat(batting)
        for p in batting:
            assert p["_heat"]["avg"] == 4
            assert p["_heat"]["thr"] == 4

    def test_multiple_qualified_players_ranked(self):
        """Better hitters should get higher THR scores (3 qualified -> cap=1)."""
        weak = self._player(ab=50, h=5, bb=2, hbp=0, shf=0)   # .100 AVG
        strong = self._player(ab=50, h=20, bb=10, hbp=3, shf=1, doubles=5, hr=3)
        mid = self._player(ab=50, h=12, bb=5, hbp=1, shf=0)   # .240 AVG
        batting = [weak, strong, mid]
        _compute_batting_enrichments(batting)
        _compute_batting_heat(batting)
        # Strong should have higher THR score than weak
        assert batting[1]["_thr_score"] > batting[0]["_thr_score"]
        # 3 qualified -> cap=1, heat levels capped at 1
        for p in batting:
            assert all(v <= 1 for v in p["_heat"].values())

    def test_no_internal_raw_fields_leaked(self):
        batting = [self._player(ab=50, h=15, bb=5, hbp=2, shf=1)]
        _compute_batting_enrichments(batting)
        _compute_batting_heat(batting)
        assert "_avg_raw" not in batting[0]
        assert "_obp_raw" not in batting[0]
        assert "_slg_raw" not in batting[0]


class TestPitchingHeat:
    def _pitcher(self, ip_outs, er=0, so=0, bb=0, h=0, **kw):
        p = {
            "ip_outs": ip_outs, "er": er, "so": so, "bb": bb, "h": h,
            "games": 5, "pitches": 0, "total_strikes": 0,
            "era": "-", "k9": "-", "whip": "-", "strike_pct": "-",
        }
        p.update(kw)
        return p

    def test_small_sample_all_zero(self):
        pitching = [self._pitcher(ip_outs=10)]  # 10 outs < 18
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 18
        _compute_pitching_heat(pitching)
        assert pitching[0]["_heat"] == {"era": 0, "k9": 0, "whip": 0, "thr": 0}

    def test_single_qualified_pitcher_depth_cap(self):
        """Single qualified pitcher: depth cap 0 (1 < 2), so heat-0."""
        pitching = [self._pitcher(ip_outs=60, er=5, so=40, bb=10, h=20)]
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 18
        _compute_pitching_heat(pitching)
        heat = pitching[0]["_heat"]
        # 1 qualified < 2 -> cap=0
        assert heat == {"era": 0, "k9": 0, "whip": 0, "thr": 0}

    def test_era_inverted(self):
        """Lower ERA should get higher heat (inverted). 2 qualified -> cap=1."""
        good = self._pitcher(ip_outs=60, er=2, so=30, bb=5, h=15)
        bad = self._pitcher(ip_outs=60, er=20, so=10, bb=20, h=30)
        pitching = [good, bad]
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 18
        _compute_pitching_heat(pitching)
        # 2 qualified -> cap=1; good pitcher still >= bad pitcher
        assert pitching[0]["_heat"]["era"] >= pitching[1]["_heat"]["era"]

    def test_no_internal_raw_fields_leaked(self):
        pitching = [self._pitcher(ip_outs=60, er=5, so=30)]
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 18
        _compute_pitching_heat(pitching)
        assert "_era_raw" not in pitching[0]
        assert "_k9_raw" not in pitching[0]
        assert "_whip_raw" not in pitching[0]


# ---------------------------------------------------------------------------
# Key players
# ---------------------------------------------------------------------------


class TestKeyPlayers:
    def _batter(self, name, ab, h, bb, hbp=0, shf=0, **kw):
        p = {
            "name": name, "ab": ab, "h": h, "bb": bb,
            "hbp": hbp, "shf": shf, "so": 5,
            "doubles": 0, "triples": 0, "hr": 0,
            "sb": 0, "cs": 0, "rbi": 0, "games": 10,
        }
        p.update(kw)
        return p

    def _pitcher(self, name, ip_outs, er=5, so=20, **kw):
        p = {
            "name": name, "ip_outs": ip_outs, "er": er, "so": so,
            "bb": 5, "h": 15, "games": 5,
            "pitches": 100, "total_strikes": 60,
            "era": "3.00", "k9": "9.0", "whip": "1.20", "strike_pct": "60.0%",
        }
        p.update(kw)
        return p

    def test_top_pitcher_by_ip(self):
        batting = [self._batter("Hitter", ab=50, h=15, bb=5)]
        _compute_batting_enrichments(batting)
        pitching = [
            self._pitcher("Ace", ip_outs=60),   # 20 IP
            self._pitcher("Relief", ip_outs=18), # 6 IP (boundary)
        ]
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 18
        result = _compute_key_players(batting, pitching)
        assert result["top_pitcher"]["name"] == "Ace"
        assert result["top_pitcher"]["ip"] == "20.0"

    def test_top_batter_by_obp(self):
        batting = [
            self._batter("Low", ab=50, h=5, bb=2),     # OBP ~.135
            self._batter("High", ab=50, h=20, bb=10),   # OBP ~.500
        ]
        _compute_batting_enrichments(batting)
        pitching = [self._pitcher("P", ip_outs=60)]
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 18
        result = _compute_key_players(batting, pitching)
        assert result["top_batter"]["name"] == "High"

    def test_no_qualified_pitcher(self):
        batting = [self._batter("B", ab=50, h=15, bb=5)]
        _compute_batting_enrichments(batting)
        pitching = [self._pitcher("P", ip_outs=15)]  # < 18 outs
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 18
        result = _compute_key_players(batting, pitching)
        assert result["top_pitcher"] is None

    def test_no_qualified_batter(self):
        batting = [self._batter("B", ab=2, h=1, bb=1)]  # PA=3 < 5
        _compute_batting_enrichments(batting)
        pitching = [self._pitcher("P", ip_outs=60)]
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 18
        result = _compute_key_players(batting, pitching)
        assert result["top_batter"] is None

    def test_empty_rosters(self):
        result = _compute_key_players([], [])
        assert result["top_pitcher"] is None
        assert result["top_batter"] is None

    def test_top_batter_includes_pa(self):
        batting = [self._batter("B", ab=50, h=15, bb=5, hbp=2, shf=1)]
        _compute_batting_enrichments(batting)
        pitching = [self._pitcher("P", ip_outs=60)]
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 18
        result = _compute_key_players(batting, pitching)
        assert result["top_batter"]["pa"] == 58


# ---------------------------------------------------------------------------
# Spray player stats
# ---------------------------------------------------------------------------


class TestSprayPlayerStats:
    def _lookup(self, **overrides):
        base = {
            "h": 10, "ab": 30, "bb": 5, "hbp": 1, "shf": 0,
            "doubles": 2, "triples": 1, "hr": 1, "_pa": 36,
            "jersey_number": "24",
        }
        base.update(overrides)
        return base

    def _events(self, n=5):
        """Create n events with distinct play_types and coordinates."""
        types = ["ground_ball", "line_drive", "fly_ball", "popup", "bunt"]
        return [
            {"x": 100.0 + i * 30, "y": 100.0, "play_result": "single",
             "play_type": types[i % len(types)]}
            for i in range(n)
        ]

    def test_basic_fields(self):
        spray = {"p1": self._events(5)}
        lookup = {"p1": self._lookup()}
        result = _build_spray_player_stats(spray, lookup)
        assert result["p1"]["bip_count"] == 5
        assert result["p1"]["pa"] == 36
        assert result["p1"]["avg"] == ".333"
        assert result["p1"]["jersey_number"] == "24"

    def test_obp_slg_computation(self):
        # h=10, bb=5, hbp=1, shf=0 -> OBP = 16/36 = .444
        # tb = 10 + 2 + 2*1 + 3*1 = 17, ab=30 -> SLG = 17/30 = .567 (rounds to .567)
        spray = {"p1": self._events(3)}
        lookup = {"p1": self._lookup()}
        result = _build_spray_player_stats(spray, lookup)
        assert result["p1"]["obp"] == ".444"
        assert result["p1"]["slg"] == ".567"

    def test_zone_counts(self):
        spray = {"p1": self._events(5)}
        lookup = {"p1": self._lookup()}
        result = _build_spray_player_stats(spray, lookup)
        zones = result["p1"]["zones"]
        assert set(zones.keys()) == {"left", "center", "right"}
        assert sum(zones.values()) == 5  # all events have x,y

    def test_contact_counts(self):
        spray = {"p1": self._events(5)}
        lookup = {"p1": self._lookup()}
        result = _build_spray_player_stats(spray, lookup)
        contacts = result["p1"]["contacts"]
        assert set(contacts.keys()) == {"gb", "ld", "fb", "pu", "bu"}
        # 5 events cycling through types: 1 each
        assert contacts["gb"] == 1
        assert contacts["ld"] == 1
        assert contacts["fb"] == 1
        assert contacts["pu"] == 1
        assert contacts["bu"] == 1

    def test_missing_batter(self):
        spray = {"p2": [{"x": 1.0, "y": 1.0, "play_result": "single", "play_type": "ground_ball"}] * 3}
        result = _build_spray_player_stats(spray, {})
        assert result["p2"]["avg"] == "-"
        assert result["p2"]["obp"] == "-"
        assert result["p2"]["slg"] == "-"
        assert result["p2"]["pa"] == 0
        assert result["p2"]["bip_count"] == 3
        assert result["p2"]["jersey_number"] is None

    def test_empty_events(self):
        spray = {"p1": []}
        lookup = {"p1": self._lookup()}
        result = _build_spray_player_stats(spray, lookup)
        assert result["p1"]["bip_count"] == 0
        assert result["p1"]["zones"] == {"left": 0, "center": 0, "right": 0}
        assert result["p1"]["contacts"] == {"gb": 0, "ld": 0, "fb": 0, "pu": 0, "bu": 0}

    def test_none_coords_excluded_from_zones(self):
        events = [
            {"x": None, "y": None, "play_result": "single", "play_type": "ground_ball"},
            {"x": 160.0, "y": 100.0, "play_result": "single", "play_type": "ground_ball"},
        ]
        spray = {"p1": events}
        lookup = {"p1": self._lookup()}
        result = _build_spray_player_stats(spray, lookup)
        assert sum(result["p1"]["zones"].values()) == 1

    def test_unmapped_play_type_excluded_from_contacts(self):
        events = [
            {"x": 160.0, "y": 100.0, "play_result": "single", "play_type": "unknown_type"},
            {"x": 160.0, "y": 100.0, "play_result": "single", "play_type": None},
            {"x": 160.0, "y": 100.0, "play_result": "single", "play_type": "ground_ball"},
        ]
        spray = {"p1": events}
        lookup = {"p1": self._lookup()}
        result = _build_spray_player_stats(spray, lookup)
        assert sum(result["p1"]["contacts"].values()) == 1  # only ground_ball

    def test_zero_ab_returns_dash_for_avg_slg(self):
        spray = {"p1": self._events(3)}
        lookup = {"p1": self._lookup(ab=0, h=0)}
        result = _build_spray_player_stats(spray, lookup)
        assert result["p1"]["avg"] == "-"
        assert result["p1"]["slg"] == "-"

    def test_baseball_formatting_convention(self):
        # 3/3 = 1.000 (not .999 or similar)
        spray = {"p1": self._events(3)}
        lookup = {"p1": self._lookup(h=3, ab=3, bb=0, hbp=0, shf=0, doubles=0, triples=0, hr=0)}
        result = _build_spray_player_stats(spray, lookup)
        assert result["p1"]["avg"] == "1.000"


# ---------------------------------------------------------------------------
# Recent form backward compatibility
# ---------------------------------------------------------------------------


class TestRecentFormBackwardCompat:
    """Verify that recent_form_str is built correctly from enriched dicts."""

    def test_format_with_opponent_fields(self):
        """recent_form_str uses only result/score, ignoring opponent_name/is_home."""
        data = _make_full_data()
        # Mock the template render to capture context
        with patch("src.reports.renderer._build_jinja_env") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<html></html>"
            mock_env.return_value.get_template.return_value = mock_template
            render_report(data)

            call_kwargs = mock_template.render.call_args[1]
            assert call_kwargs["recent_form_str"] == "W 7-3, L 2-4, W 5-1"
            assert call_kwargs["has_recent_form"] is True
            # Structured recent_form also passed
            assert len(call_kwargs["recent_form"]) == 3
            assert call_kwargs["recent_form"][0]["opponent_name"] == "Rival"
            assert call_kwargs["recent_form"][0]["is_home"] is True

    def test_context_includes_key_players(self):
        data = _make_full_data()
        with patch("src.reports.renderer._build_jinja_env") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<html></html>"
            mock_env.return_value.get_template.return_value = mock_template
            render_report(data)
            call_kwargs = mock_template.render.call_args[1]
            assert "key_players" in call_kwargs
            assert "top_pitcher" in call_kwargs["key_players"]
            assert "top_batter" in call_kwargs["key_players"]

    def test_context_includes_runs_avg(self):
        data = _make_full_data(runs_scored_avg=8.2, runs_allowed_avg=3.5)
        with patch("src.reports.renderer._build_jinja_env") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<html></html>"
            mock_env.return_value.get_template.return_value = mock_template
            render_report(data)
            call_kwargs = mock_template.render.call_args[1]
            assert call_kwargs["runs_scored_avg"] == "8.2"
            assert call_kwargs["runs_allowed_avg"] == "3.5"

    def test_context_runs_avg_none(self):
        data = _make_full_data()  # no runs_scored_avg/runs_allowed_avg
        with patch("src.reports.renderer._build_jinja_env") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<html></html>"
            mock_env.return_value.get_template.return_value = mock_template
            render_report(data)
            call_kwargs = mock_template.render.call_args[1]
            assert call_kwargs["runs_scored_avg"] is None
            assert call_kwargs["runs_allowed_avg"] is None

    def test_context_includes_team_spray_uri(self):
        """team_spray_uri passed to context (None when below threshold)."""
        data = _make_full_data(spray_charts={})
        with patch("src.reports.renderer._build_jinja_env") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<html></html>"
            mock_env.return_value.get_template.return_value = mock_template
            render_report(data)
            call_kwargs = mock_template.render.call_args[1]
            assert call_kwargs["team_spray_uri"] is None

    def test_context_includes_spray_player_stats(self):
        data = _make_full_data(spray_charts={})
        with patch("src.reports.renderer._build_jinja_env") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<html></html>"
            mock_env.return_value.get_template.return_value = mock_template
            render_report(data)
            call_kwargs = mock_template.render.call_args[1]
            assert "spray_player_stats" in call_kwargs

    def test_batting_has_heat_and_enrichments(self):
        """Verify batting dicts get enriched before template."""
        data = _make_full_data()
        with patch("src.reports.renderer._build_jinja_env") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<html></html>"
            mock_env.return_value.get_template.return_value = mock_template
            render_report(data)
            call_kwargs = mock_template.render.call_args[1]
            batter = call_kwargs["batting"][0]
            assert "_heat" in batter
            assert "_thr_score" in batter
            assert "_k_pct" in batter
            assert "_bb_pct" in batter
            assert "_xbh" in batter
            assert "_sb_cs" in batter
            assert "_pa" in batter

    def test_pitching_has_heat(self):
        data = _make_full_data()
        with patch("src.reports.renderer._build_jinja_env") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<html></html>"
            mock_env.return_value.get_template.return_value = mock_template
            render_report(data)
            call_kwargs = mock_template.render.call_args[1]
            pitcher = call_kwargs["pitching"][0]
            assert "_heat" in pitcher
            assert "_thr_score" in pitcher


# ===========================================================================
# E-187-02: PA/IP badge rendering
# ===========================================================================


class TestDepthBadge:
    """AC-9, AC-10, AC-11, AC-15: Depth badges on every player row."""

    def test_batting_pa_badge_renders(self):
        """AC-15: PA badge span renders in every batting row."""
        high_pa = _make_batter(ab=50, name="High PA", player_id=1)
        low_pa = _make_batter(ab=1, bb=0, hbp=0, shf=0, name="Low PA", player_id=2)
        data = _make_full_data(batting=[high_pa, low_pa])
        html = render_report(data)

        # Both players get a badge
        assert 'class="depth-badge"' in html
        assert "59 PA" in html   # 50+8+1+0
        assert "1 PA" in html    # 1+0+0+0

    def test_pitching_ip_badge_renders(self):
        """AC-10: IP badge span renders in every pitching row."""
        high_ip = _make_pitcher(ip_outs=60, name="Ace")
        low_ip = _make_pitcher(ip_outs=3, name="Mop Up")
        data = _make_full_data(pitching=[high_ip, low_ip])
        html = render_report(data)

        assert 'class="depth-badge"' in html
        assert "20.0 IP" in html   # 60 outs
        assert "1.0 IP" in html    # 3 outs

    def test_badge_css_class_in_style(self):
        """AC-9: .depth-badge CSS class is defined in the template."""
        data = _make_full_data()
        html = render_report(data)

        assert ".depth-badge" in html


# ===========================================================================
# E-187-02: Graduated heat intensity (TN-2a)
# ===========================================================================


class TestMaxHeatForDepth:
    """AC-19: _max_heat_for_depth helper tests."""

    def test_batting_tier_boundaries(self):
        assert _max_heat_for_depth(0, _BATTING_HEAT_TIERS) == 0
        assert _max_heat_for_depth(2, _BATTING_HEAT_TIERS) == 0
        assert _max_heat_for_depth(3, _BATTING_HEAT_TIERS) == 1
        assert _max_heat_for_depth(4, _BATTING_HEAT_TIERS) == 1
        assert _max_heat_for_depth(5, _BATTING_HEAT_TIERS) == 2
        assert _max_heat_for_depth(6, _BATTING_HEAT_TIERS) == 2
        assert _max_heat_for_depth(7, _BATTING_HEAT_TIERS) == 3
        assert _max_heat_for_depth(8, _BATTING_HEAT_TIERS) == 3
        assert _max_heat_for_depth(9, _BATTING_HEAT_TIERS) == 4
        assert _max_heat_for_depth(15, _BATTING_HEAT_TIERS) == 4

    def test_pitching_tier_boundaries(self):
        assert _max_heat_for_depth(0, _PITCHING_HEAT_TIERS) == 0
        assert _max_heat_for_depth(1, _PITCHING_HEAT_TIERS) == 0
        assert _max_heat_for_depth(2, _PITCHING_HEAT_TIERS) == 1
        assert _max_heat_for_depth(3, _PITCHING_HEAT_TIERS) == 2
        assert _max_heat_for_depth(4, _PITCHING_HEAT_TIERS) == 3
        assert _max_heat_for_depth(5, _PITCHING_HEAT_TIERS) == 3
        assert _max_heat_for_depth(6, _PITCHING_HEAT_TIERS) == 4
        assert _max_heat_for_depth(10, _PITCHING_HEAT_TIERS) == 4


class TestGraduatedHeatIntegration:
    """AC-12, AC-13, AC-19: Graduated heat in compute functions."""

    def _batter(self, ab, h, bb=5, hbp=1, shf=0, **kw):
        p = {
            "ab": ab, "h": h, "bb": bb, "hbp": hbp, "shf": shf,
            "doubles": 1, "triples": 0, "hr": 1, "so": 5,
            "sb": 0, "cs": 0, "rbi": 0, "games": 10,
        }
        p.update(kw)
        return p

    def _pitcher(self, ip_outs, er=5, so=20, bb=5, h=15, **kw):
        p = {
            "ip_outs": ip_outs, "er": er, "so": so, "bb": bb, "h": h,
            "games": 5, "pitches": 100, "total_strikes": 60,
            "era": "3.00", "k9": "9.0", "whip": "1.20", "strike_pct": "60.0%",
        }
        p.update(kw)
        return p

    def test_batting_3_qualified_cap_1(self):
        """3 qualified batters -> max heat 1."""
        batting = [
            self._batter(ab=50, h=20),
            self._batter(ab=40, h=10),
            self._batter(ab=30, h=5),
        ]
        _compute_batting_enrichments(batting)
        _compute_batting_heat(batting)
        for p in batting:
            assert all(v <= 1 for v in p["_heat"].values())
            # At least one should be non-zero (they're qualified)
        assert any(v > 0 for p in batting for v in p["_heat"].values())

    def test_batting_5_qualified_cap_2(self):
        """5 qualified batters -> max heat 2."""
        batting = [self._batter(ab=50 - i * 5, h=15 - i) for i in range(5)]
        _compute_batting_enrichments(batting)
        _compute_batting_heat(batting)
        for p in batting:
            assert all(v <= 2 for v in p["_heat"].values())

    def test_batting_9_qualified_full_gradient(self):
        """9 qualified batters -> max heat 4 (full gradient)."""
        batting = [self._batter(ab=50 - i * 3, h=15 - i) for i in range(9)]
        _compute_batting_enrichments(batting)
        _compute_batting_heat(batting)
        # At least one player should have heat-4
        assert any(v == 4 for p in batting for v in p["_heat"].values())

    def test_unqualified_always_heat_0(self):
        """AC-13: Players below per-player threshold always get heat-0."""
        qualified = [self._batter(ab=50, h=15) for _ in range(9)]
        unqualified = self._batter(ab=2, h=1, bb=0, hbp=0, shf=0)  # PA=2
        batting = qualified + [unqualified]
        _compute_batting_enrichments(batting)
        _compute_batting_heat(batting)
        assert batting[-1]["_heat"] == {"avg": 0, "obp": 0, "slg": 0, "thr": 0}

    def test_pitching_2_qualified_cap_1(self):
        """2 qualified pitchers -> max heat 1."""
        pitching = [
            self._pitcher(ip_outs=60, er=2, so=40),
            self._pitcher(ip_outs=45, er=10, so=15),
        ]
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 18
        _compute_pitching_heat(pitching)
        for p in pitching:
            assert all(v <= 1 for v in p["_heat"].values())

    def test_pitching_6_qualified_full_gradient(self):
        """6 qualified pitchers -> max heat 4 (full gradient)."""
        pitching = [
            self._pitcher(ip_outs=60 - i * 5, er=2 + i, so=40 - i * 3)
            for i in range(6)
        ]
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 18
        _compute_pitching_heat(pitching)
        assert any(v == 4 for p in pitching for v in p["_heat"].values())

    def test_pitching_unqualified_always_heat_0(self):
        """AC-13: Pitchers below threshold always get heat-0."""
        qualified = [self._pitcher(ip_outs=60, er=3, so=30) for _ in range(6)]
        unqualified = self._pitcher(ip_outs=10, er=5, so=2)
        pitching = qualified + [unqualified]
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 18
        _compute_pitching_heat(pitching)
        assert pitching[-1]["_heat"] == {"era": 0, "k9": 0, "whip": 0, "thr": 0}

    def test_boundary_pa_5_with_3_qualified_gets_heat(self):
        """AC-3: PA=5 boundary player gets non-zero heat when 3+ qualified."""
        batting = [
            self._batter(ab=3, h=2, bb=1, hbp=1, shf=0),  # PA=5, boundary
            self._batter(ab=50, h=15),
            self._batter(ab=40, h=10),
        ]
        _compute_batting_enrichments(batting)
        _compute_batting_heat(batting)
        # PA=5 player is qualified, 3 qualified -> cap=1
        assert batting[0]["_small_sample"] is False
        assert any(v > 0 for v in batting[0]["_heat"].values())

    def test_boundary_ip_18_with_2_qualified_gets_heat(self):
        """AC-4: ip_outs=18 boundary pitcher gets non-zero heat when 2+ qualified."""
        pitching = [
            self._pitcher(ip_outs=18, er=3, so=10),   # boundary
            self._pitcher(ip_outs=60, er=5, so=30),
        ]
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 18
        _compute_pitching_heat(pitching)
        # ip_outs=18 is qualified, 2 qualified -> cap=1
        assert pitching[0]["_small_sample"] is False
        assert any(v > 0 for v in pitching[0]["_heat"].values())


# ===========================================================================
# E-199-02: Plays-derived stats formatting and rendering
# ===========================================================================


class TestFormatHelpers:
    """AC-5: Formatting helpers produce correct output."""

    def test_format_pct_normal(self):
        assert _format_pct(0.625) == "62.5%"

    def test_format_pct_zero(self):
        assert _format_pct(0.0) == "0.0%"

    def test_format_pct_one(self):
        assert _format_pct(1.0) == "100.0%"

    def test_format_pct_none(self):
        assert _format_pct(None) == "\u2014"

    def test_format_rate_normal(self):
        assert _format_rate(3.82) == "3.8"

    def test_format_rate_zero(self):
        assert _format_rate(0.0) == "0.0"

    def test_format_rate_none(self):
        assert _format_rate(None) == "\u2014"


class TestFormatPlaysPitching:
    """AC-1: Pitching table gets formatted FPS% and P/BF."""

    def test_formats_fps_and_pbf(self):
        pitching = [{"fps_pct": 0.625, "pitches_per_bf": 3.82}]
        _format_plays_pitching(pitching)
        assert pitching[0]["_fps_pct"] == "62.5%"
        assert pitching[0]["_pitches_per_bf"] == "3.8"

    def test_missing_plays_data_shows_dash(self):
        """AC-3: No plays data -> em dash."""
        pitching = [{"fps_pct": None, "pitches_per_bf": None}]
        _format_plays_pitching(pitching)
        assert pitching[0]["_fps_pct"] == "\u2014"
        assert pitching[0]["_pitches_per_bf"] == "\u2014"

    def test_missing_keys_shows_dash(self):
        """AC-3: Keys not present at all -> em dash."""
        pitching = [{"name": "Test Pitcher"}]
        _format_plays_pitching(pitching)
        assert pitching[0]["_fps_pct"] == "\u2014"
        assert pitching[0]["_pitches_per_bf"] == "\u2014"


class TestFormatPlaysBatting:
    """AC-2: Batting table gets formatted QAB% and P/PA."""

    def test_formats_qab_and_ppa(self):
        batting = [{"qab_pct": 0.45, "pitches_per_pa": 4.2}]
        _format_plays_batting(batting)
        assert batting[0]["_qab_pct"] == "45.0%"
        assert batting[0]["_pitches_per_pa"] == "4.2"

    def test_missing_plays_data_shows_dash(self):
        """AC-3: No plays data -> em dash."""
        batting = [{"qab_pct": None, "pitches_per_pa": None}]
        _format_plays_batting(batting)
        assert batting[0]["_qab_pct"] == "\u2014"
        assert batting[0]["_pitches_per_pa"] == "\u2014"

    def test_missing_keys_shows_dash(self):
        """AC-3: Keys not present at all -> em dash."""
        batting = [{"name": "Test Batter"}]
        _format_plays_batting(batting)
        assert batting[0]["_qab_pct"] == "\u2014"
        assert batting[0]["_pitches_per_pa"] == "\u2014"


class TestRenderReportPlaysIntegration:
    """AC-4, AC-7: Executive summary and column rendering in full render."""

    @pytest.fixture()
    def plays_data(self) -> dict:
        """Data dict with plays stats for render_report."""
        return {
            "team": {"name": "Test Team", "season_year": 2026, "record": {"wins": 5, "losses": 3}},
            "generated_at": "2026-04-01T00:00:00Z",
            "expires_at": "2026-04-15T00:00:00Z",
            "freshness_date": "2026-03-30",
            "game_count": 10,
            "pitching": [
                {
                    "player_id": "p1", "name": "Ace Pitcher", "jersey_number": "12",
                    "games": 5, "ip_outs": 30, "h": 10, "er": 4, "bb": 3, "so": 25,
                    "pitches": 300, "total_strikes": 200, "throws": "R",
                    "era": "2.80", "k9": "16.9", "whip": "0.87", "strike_pct": "66.7%",
                    "fps_pct": 0.625, "pitches_per_bf": 3.8,
                },
            ],
            "batting": [
                {
                    "player_id": "b1", "name": "Star Batter", "jersey_number": "7",
                    "games": 8, "ab": 30, "h": 10, "doubles": 2, "triples": 0,
                    "hr": 1, "rbi": 5, "bb": 4, "so": 6, "sb": 2, "cs": 1,
                    "hbp": 1, "shf": 0,
                    "qab_pct": 0.45, "pitches_per_pa": 4.2,
                },
            ],
            "spray_charts": {},
            "roster": [],
            "runs_scored_avg": 5.0,
            "runs_allowed_avg": 3.0,
            "team_fps_pct": 0.625,
            "team_pitches_per_pa": 4.2,
            "has_plays_data": True,
            "plays_game_count": 8,
        }

    def test_pitching_columns_rendered(self, plays_data: dict):
        """AC-1: FPS% and P/BF appear in pitching table."""
        html = render_report(plays_data)
        assert "62.5%" in html
        assert "FPS%" in html
        assert "P/BF" in html

    def test_batting_columns_rendered(self, plays_data: dict):
        """AC-2: QAB% and P/PA appear in batting table."""
        html = render_report(plays_data)
        assert "45.0%" in html
        assert "QAB%" in html
        assert "P/PA" in html

    def test_exec_summary_with_plays(self, plays_data: dict):
        """AC-4: Team FPS% and P/PA in executive summary."""
        html = render_report(plays_data)
        assert "62.5% FPS" in html
        assert "4.2 P/PA" in html

    def test_exec_summary_partial_coverage(self, plays_data: dict):
        """AC-7: Partial coverage shows game count context."""
        html = render_report(plays_data)
        # plays_game_count=8, game_count=10 -> "(8 of 10 games)"
        assert "8 of 10 games" in html

    def test_exec_summary_full_coverage_no_annotation(self, plays_data: dict):
        """AC-7: Full coverage omits game count annotation."""
        plays_data["plays_game_count"] = 10
        html = render_report(plays_data)
        assert "of 10 games" not in html

    def test_no_plays_data_no_exec_plays_stats(self, plays_data: dict):
        """AC-3: No plays data -> exec summary omits FPS/P/PA."""
        plays_data["has_plays_data"] = False
        plays_data["plays_game_count"] = 0
        plays_data["team_fps_pct"] = None
        plays_data["team_pitches_per_pa"] = None
        plays_data["pitching"][0]["fps_pct"] = None
        plays_data["pitching"][0]["pitches_per_bf"] = None
        plays_data["batting"][0]["qab_pct"] = None
        plays_data["batting"][0]["pitches_per_pa"] = None

        html = render_report(plays_data)
        assert "Test Team" in html
        # Exec summary should NOT contain "FPS" before the pitching section
        exec_section = html.split("Pitching")[0]
        assert "FPS" not in exec_section

    def test_render_without_plays_keys(self):
        """AC-8: Data dict without plays keys renders successfully."""
        data = {
            "team": {"name": "Basic Team"},
            "generated_at": "2026-04-01T00:00:00Z",
            "expires_at": "2026-04-15T00:00:00Z",
            "game_count": 5,
            "pitching": [
                {
                    "player_id": "p1", "name": "Pitcher", "jersey_number": "1",
                    "games": 3, "ip_outs": 9, "h": 5, "er": 2, "bb": 1, "so": 8,
                    "pitches": 100, "total_strikes": 60, "throws": None,
                    "era": "4.67", "k9": "18.0", "whip": "1.33", "strike_pct": "60.0%",
                },
            ],
            "batting": [
                {
                    "player_id": "b1", "name": "Batter", "jersey_number": "2",
                    "games": 5, "ab": 15, "h": 4, "doubles": 1, "triples": 0,
                    "hr": 0, "rbi": 2, "bb": 2, "so": 3, "sb": 1, "cs": 0,
                    "hbp": 0, "shf": 0,
                },
            ],
            "spray_charts": {},
            "roster": [],
        }
        html = render_report(data)
        assert "Basic Team" in html
        assert "FPS%" in html  # column header still present
