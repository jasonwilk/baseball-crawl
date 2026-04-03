"""Tests for dashboard pitching availability columns (E-196-04).

Tests the enrichment function, display formatting, and template rendering.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from src.api.helpers import format_avg, format_date, ip_display

from src.api.routes.dashboard import _enrich_pitchers_with_workload, _format_short_date


# ---------------------------------------------------------------------------
# _format_short_date
# ---------------------------------------------------------------------------


class TestFormatShortDate:
    def test_formats_date(self) -> None:
        assert _format_short_date("2025-04-26") == "Apr 26"

    def test_single_digit_day(self) -> None:
        assert _format_short_date("2025-03-05") == "Mar 5"

    def test_invalid_date_returns_input(self) -> None:
        assert _format_short_date("not-a-date") == "not-a-date"


# ---------------------------------------------------------------------------
# _enrich_pitchers_with_workload — dashboard (days-ago format)
# ---------------------------------------------------------------------------


class TestEnrichDashboardFormat:
    """Dashboard format: rest_display as 'Xd' or 'Today'."""

    def test_pitcher_with_recent_outing(self) -> None:
        pitchers = [{"player_id": "p1", "name": "Ace"}]
        workload = {
            "p1": {
                "last_outing_date": "2025-04-24",
                "last_outing_days_ago": 2,
                "pitches_7d": 85,
                "span_days_7d": 3,
            }
        }
        _enrich_pitchers_with_workload(pitchers, workload)

        assert pitchers[0]["rest_display"] == "2d"
        assert pitchers[0]["p7d_display"] == "85/3d"
        assert pitchers[0]["workload_subline"] == "Last: 2d ago \u00b7 85/3d"

    def test_pitcher_outing_today(self) -> None:
        pitchers = [{"player_id": "p1", "name": "Ace"}]
        workload = {
            "p1": {
                "last_outing_date": "2025-04-26",
                "last_outing_days_ago": 0,
                "pitches_7d": 90,
                "span_days_7d": 1,
            }
        }
        _enrich_pitchers_with_workload(pitchers, workload)

        assert pitchers[0]["rest_display"] == "Today"
        assert pitchers[0]["p7d_display"] == "90/1d"
        assert pitchers[0]["workload_subline"] == "Last: Today \u00b7 90/1d"

    def test_pitcher_no_appearances(self) -> None:
        """Pitcher not in workload dict at all."""
        pitchers = [{"player_id": "p1", "name": "Ace"}]
        _enrich_pitchers_with_workload(pitchers, {})

        assert pitchers[0]["rest_display"] == "\u2014"
        assert pitchers[0]["p7d_display"] == "\u2014"
        assert pitchers[0]["workload_subline"] == "No recent outings"

    def test_pitcher_appearances_outside_7d(self) -> None:
        """Has appearances but none in 7d window: pitches_7d=0, span=None."""
        pitchers = [{"player_id": "p1", "name": "Ace"}]
        workload = {
            "p1": {
                "last_outing_date": "2025-04-10",
                "last_outing_days_ago": 16,
                "pitches_7d": 0,
                "span_days_7d": None,
            }
        }
        _enrich_pitchers_with_workload(pitchers, workload)

        assert pitchers[0]["rest_display"] == "16d"
        assert pitchers[0]["p7d_display"] == "\u2014"
        assert pitchers[0]["workload_subline"] == "Last: 16d ago \u00b7 \u2014"

    def test_null_pitch_counts_shows_question_mark(self) -> None:
        """All pitch counts NULL in 7d window: pitches_7d=None, span has value."""
        pitchers = [{"player_id": "p1", "name": "Ace"}]
        workload = {
            "p1": {
                "last_outing_date": "2025-04-25",
                "last_outing_days_ago": 1,
                "pitches_7d": None,
                "span_days_7d": 2,
            }
        }
        _enrich_pitchers_with_workload(pitchers, workload)

        assert pitchers[0]["p7d_display"] == "?/2d"

    def test_multiple_pitchers_enriched(self) -> None:
        pitchers = [
            {"player_id": "p1", "name": "Ace"},
            {"player_id": "p2", "name": "Relief"},
        ]
        workload = {
            "p1": {
                "last_outing_date": "2025-04-24",
                "last_outing_days_ago": 2,
                "pitches_7d": 80,
                "span_days_7d": 1,
            }
        }
        _enrich_pitchers_with_workload(pitchers, workload)

        assert pitchers[0]["rest_display"] == "2d"
        # p2 not in workload
        assert pitchers[1]["rest_display"] == "\u2014"
        assert pitchers[1]["workload_subline"] == "No recent outings"


# ---------------------------------------------------------------------------
# _enrich_pitchers_with_workload — print format (formatted date)
# ---------------------------------------------------------------------------


class TestEnrichPrintFormat:
    """Print format: rest_display as 'Mar 28'."""

    def test_print_uses_formatted_date(self) -> None:
        pitchers = [{"player_id": "p1", "name": "Ace"}]
        workload = {
            "p1": {
                "last_outing_date": "2025-04-24",
                "last_outing_days_ago": 2,
                "pitches_7d": 85,
                "span_days_7d": 3,
            }
        }
        _enrich_pitchers_with_workload(pitchers, workload, use_formatted_date=True)

        assert pitchers[0]["rest_display"] == "Apr 24"
        # p7d is same format on all surfaces
        assert pitchers[0]["p7d_display"] == "85/3d"

    def test_print_no_appearances(self) -> None:
        pitchers = [{"player_id": "p1", "name": "Ace"}]
        _enrich_pitchers_with_workload(pitchers, {}, use_formatted_date=True)

        assert pitchers[0]["rest_display"] == "\u2014"
        assert pitchers[0]["p7d_display"] == "\u2014"

    def test_print_null_last_outing(self) -> None:
        """days_ago is None (no appearances at all) -- should show em dash."""
        pitchers = [{"player_id": "p1", "name": "Ace"}]
        workload = {
            "p1": {
                "last_outing_date": None,
                "last_outing_days_ago": None,
                "pitches_7d": 0,
                "span_days_7d": None,
            }
        }
        _enrich_pitchers_with_workload(pitchers, workload, use_formatted_date=True)

        assert pitchers[0]["rest_display"] == "\u2014"


# ---------------------------------------------------------------------------
# AC-6: Template rendering with workload data
# ---------------------------------------------------------------------------


class TestTemplateRendering:
    """AC-6: Verify Rest and P(7d) columns appear in rendered HTML."""

    @pytest.fixture()
    def jinja_env(self) -> Environment:
        templates_dir = Path(__file__).resolve().parents[1] / "src" / "api" / "templates"
        env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)
        env.filters["ip_display"] = ip_display
        env.filters["format_avg"] = format_avg
        env.filters["format_date"] = format_date
        return env

    def _make_pitcher(self) -> dict:
        return {
            "player_id": "p1",
            "name": "Ace Pitcher",
            "name_unresolved": False,
            "jersey_number": "21",
            "throws": "R",
            "games": 5,
            "ip_outs": 30,
            "h": 10,
            "er": 4,
            "bb": 3,
            "so": 20,
            "hr": 1,
            "pitches": 300,
            "total_strikes": 200,
            "era": "3.60",
            "k9": "18.0",
            "bb9": "2.7",
            "whip": "1.30",
            "k_bb_ratio": "6.7",
            "avg_pitches": "60",
            "strike_pct": "66.7%",
            "rest_display": "Apr 24",
            "p7d_display": "85/3d",
            "workload_subline": "Last: Apr 24 \u00b7 85/3d",
            "_heat": {"era": 0, "k9": 0, "whip": 0, "thr": 0},
            "_thr_score": 0.0,
            "_small_sample": False,
        }

    def _render_print(self, env: Environment, pitchers: list[dict]) -> str:
        """Render opponent_print.html (standalone, no base.html dependency)."""
        template = env.get_template("dashboard/opponent_print.html")
        return template.render(
            scouting_report={"pitching": pitchers, "batting": []},
            opponent_team_id=1,
            last_meeting=None,
            active_team_id=1,
            season_id="2025-spring-hs",
            year=None,
            team_batting={"has_data": False},
            empty_state="full_stats",
            print_date="April 26, 2025",
            player_spray_bip_counts={},
            tendency_stats={},
            coverage_text=None,
        )

    def test_last_and_p7d_columns_in_print_table(self, jinja_env: Environment) -> None:
        pitcher = self._make_pitcher()
        html = self._render_print(jinja_env, [pitcher])

        assert ">Last<" in html
        assert ">P (7d)<" in html

    def test_workload_values_rendered_in_print(self, jinja_env: Environment) -> None:
        pitcher = self._make_pitcher()
        html = self._render_print(jinja_env, [pitcher])

        assert "Apr 24" in html
        assert "85/3d" in html

    def test_em_dash_in_print_when_no_workload(self, jinja_env: Environment) -> None:
        pitcher = self._make_pitcher()
        pitcher["rest_display"] = "\u2014"
        pitcher["p7d_display"] = "\u2014"
        html = self._render_print(jinja_env, [pitcher])

        assert "\u2014" in html
