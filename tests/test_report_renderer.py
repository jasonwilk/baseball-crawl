"""Tests for the standalone scouting report renderer (E-172-01, E-185-01)."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from src.reports.renderer import (
    render_report,
    _compute_batting_enrichments,
    _compute_batting_heat,
    _compute_key_players,
    _compute_pa,
    _compute_pitching_heat,
    _build_spray_player_stats,
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
        fake_png = b"\x89PNG_FAKE_DATA"
        mock_spray_mod = MagicMock()
        mock_spray_mod.render_spray_chart = MagicMock(return_value=fake_png)
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


class TestSmallSampleFlags:
    """Test small sample size asterisk indicators."""

    def test_pitching_small_sample_asterisk(self):
        """Pitcher with < 15 IP (45 outs) gets asterisk."""
        pitcher = _make_pitcher(ip_outs=30, name="Low IP Pitcher")  # 10 IP
        data = _make_full_data(pitching=[pitcher])
        html = render_report(data)

        assert "Low IP Pitcher" in html
        assert " *" in html  # asterisk present somewhere for small sample
        assert "Small sample size" in html
        assert "fewer than 15 IP" in html

    def test_pitching_no_asterisk_above_threshold(self):
        """Pitcher with >= 15 IP (45 outs) has no asterisk."""
        pitcher = _make_pitcher(ip_outs=60, name="High IP Pitcher")  # 20 IP
        data = _make_full_data(pitching=[pitcher])
        html = render_report(data)

        # Footnote should not appear if no small samples
        assert "fewer than 15 IP" not in html

    def test_batting_small_sample_asterisk(self):
        """Batter with < 20 PA gets asterisk."""
        batter = _make_batter(ab=10, name="Low PA Batter")
        # PA = ab + bb + hbp + shf = 10 + 8 + 1 + 0 = 19 < 20
        data = _make_full_data(batting=[batter])
        html = render_report(data)

        assert "Low PA Batter" in html
        assert " *" in html
        assert "Small sample size" in html
        assert "fewer than 20 PA" in html

    def test_batting_no_asterisk_above_threshold(self):
        """Batter with >= 20 PA has no asterisk."""
        batter = _make_batter(ab=50, name="High PA Batter")
        # PA = 50 + 8 + 1 + 0 = 59 >= 20
        data = _make_full_data(batting=[batter])
        html = render_report(data)

        assert "fewer than 20 PA" not in html

    def test_mixed_sample_sizes_only_flags_small(self):
        """Only players below threshold get the asterisk."""
        small = _make_batter(ab=5, name="Small Sample", player_id=1)
        # PA = 5 + 8 + 1 + 0 = 14 < 20
        large = _make_batter(ab=50, name="Large Sample", player_id=2)
        # PA = 50 + 8 + 1 + 0 = 59 >= 20
        data = _make_full_data(batting=[small, large])
        html = render_report(data)

        assert "Small Sample" in html
        assert "fewer than 20 PA" in html


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

        mock_spray_mod = MagicMock()
        mock_spray_mod.render_spray_chart = MagicMock(side_effect=RuntimeError("render failed"))
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
        batting = [self._player(ab=10, bb=2, hbp=0, shf=0)]  # PA=12 < 20
        _compute_batting_enrichments(batting)
        assert batting[0]["_small_sample"] is True

    def test_large_sample_flag(self):
        batting = [self._player()]  # PA=63 >= 20
        _compute_batting_enrichments(batting)
        assert batting[0]["_small_sample"] is False


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
        batting = [self._player(ab=5, h=2, bb=0, hbp=0, shf=0)]  # PA=5
        _compute_batting_enrichments(batting)
        _compute_batting_heat(batting)
        assert batting[0]["_heat"] == {"avg": 0, "obp": 0, "slg": 0, "thr": 0}
        assert batting[0]["_thr_score"] == 0.0

    def test_single_qualified_player(self):
        """A single qualified player should get level 4 (100th percentile)."""
        batting = [self._player(ab=50, h=15, bb=5, hbp=2, shf=1, doubles=3)]
        _compute_batting_enrichments(batting)
        _compute_batting_heat(batting)
        heat = batting[0]["_heat"]
        assert heat["avg"] == 4
        assert heat["obp"] == 4
        assert heat["slg"] == 4
        assert heat["thr"] == 4
        assert batting[0]["_thr_score"] > 0

    def test_mixed_small_and_large_sample(self):
        """Small sample player gets 0 heat, large sample gets assigned heat."""
        large = self._player(ab=50, h=15, bb=5, hbp=2, shf=1)
        small = self._player(ab=5, h=2, bb=0, hbp=0, shf=0)
        batting = [large, small]
        _compute_batting_enrichments(batting)
        _compute_batting_heat(batting)
        assert batting[1]["_heat"] == {"avg": 0, "obp": 0, "slg": 0, "thr": 0}
        assert all(v > 0 for v in batting[0]["_heat"].values())

    def test_all_same_value_players(self):
        """When all qualified players have identical stats, all get level 4."""
        batting = [
            self._player(ab=50, h=15, bb=5, hbp=2, shf=1)
            for _ in range(5)
        ]
        _compute_batting_enrichments(batting)
        _compute_batting_heat(batting)
        for p in batting:
            assert p["_heat"]["avg"] == 4
            assert p["_heat"]["thr"] == 4

    def test_multiple_qualified_players_ranked(self):
        """Better hitters should get higher THR scores."""
        weak = self._player(ab=50, h=5, bb=2, hbp=0, shf=0)   # .100 AVG
        strong = self._player(ab=50, h=20, bb=10, hbp=3, shf=1, doubles=5, hr=3)
        mid = self._player(ab=50, h=12, bb=5, hbp=1, shf=0)   # .240 AVG
        batting = [weak, strong, mid]
        _compute_batting_enrichments(batting)
        _compute_batting_heat(batting)
        # Strong should have higher THR score than weak
        assert batting[1]["_thr_score"] > batting[0]["_thr_score"]

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
        pitching = [self._pitcher(ip_outs=10)]  # 10 outs < 45
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 45
        _compute_pitching_heat(pitching)
        assert pitching[0]["_heat"] == {"era": 0, "k9": 0, "whip": 0, "thr": 0}

    def test_single_qualified_pitcher(self):
        pitching = [self._pitcher(ip_outs=60, er=5, so=40, bb=10, h=20)]
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 45
        _compute_pitching_heat(pitching)
        heat = pitching[0]["_heat"]
        assert heat["era"] == 4
        assert heat["k9"] == 4
        assert heat["whip"] == 4
        assert heat["thr"] == 4

    def test_era_inverted(self):
        """Lower ERA should get higher heat (inverted)."""
        good = self._pitcher(ip_outs=60, er=2, so=30, bb=5, h=15)
        bad = self._pitcher(ip_outs=60, er=20, so=10, bb=20, h=30)
        pitching = [good, bad]
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 45
        _compute_pitching_heat(pitching)
        # Good pitcher (lower ERA) should have higher ERA heat than bad pitcher
        assert pitching[0]["_heat"]["era"] >= pitching[1]["_heat"]["era"]

    def test_no_internal_raw_fields_leaked(self):
        pitching = [self._pitcher(ip_outs=60, er=5, so=30)]
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 45
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
            self._pitcher("Relief", ip_outs=45), # 15 IP
        ]
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 45
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
            p["_small_sample"] = (p.get("ip_outs") or 0) < 45
        result = _compute_key_players(batting, pitching)
        assert result["top_batter"]["name"] == "High"

    def test_no_qualified_pitcher(self):
        batting = [self._batter("B", ab=50, h=15, bb=5)]
        _compute_batting_enrichments(batting)
        pitching = [self._pitcher("P", ip_outs=30)]  # < 45 outs
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 45
        result = _compute_key_players(batting, pitching)
        assert result["top_pitcher"] is None

    def test_no_qualified_batter(self):
        batting = [self._batter("B", ab=10, h=3, bb=2)]  # PA=12 < 20
        _compute_batting_enrichments(batting)
        pitching = [self._pitcher("P", ip_outs=60)]
        for p in pitching:
            p["_small_sample"] = (p.get("ip_outs") or 0) < 45
        result = _compute_key_players(batting, pitching)
        assert result["top_batter"] is None

    def test_empty_rosters(self):
        result = _compute_key_players([], [])
        assert result["top_pitcher"] is None
        assert result["top_batter"] is None

    def test_top_batter_includes_pa(self):
        batting = [self._batter("B", ab=50, h=15, bb=5, hbp=2, shf=1)]
        _compute_batting_enrichments(batting)
        result = _compute_key_players(batting, [])
        assert result["top_batter"]["pa"] == 58


# ---------------------------------------------------------------------------
# Spray player stats
# ---------------------------------------------------------------------------


class TestSprayPlayerStats:
    def test_basic(self):
        spray = {"p1": [{"x": 1, "y": 1}] * 5}
        lookup = {"p1": {"h": 10, "ab": 30, "_pa": 35}}
        result = _build_spray_player_stats(spray, lookup)
        assert result["p1"]["bip_count"] == 5
        assert result["p1"]["pa"] == 35
        assert result["p1"]["avg"] == ".333"

    def test_missing_batter(self):
        spray = {"p2": [{"x": 1, "y": 1}] * 3}
        result = _build_spray_player_stats(spray, {})
        assert result["p2"]["avg"] == "-"
        assert result["p2"]["pa"] == 0
        assert result["p2"]["bip_count"] == 3

    def test_empty_events(self):
        spray = {"p1": []}
        lookup = {"p1": {"h": 5, "ab": 20, "_pa": 25}}
        result = _build_spray_player_stats(spray, lookup)
        assert result["p1"]["bip_count"] == 0


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
