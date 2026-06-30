"""Tests for standalone report pitching availability columns (E-196-05, E-210-01).

Tests the renderer's workload enrichment and template output for
Last/Pitches(7d) columns, CSS classes, data attributes, JS snippet, and
key-player workload sub-line.
"""

from __future__ import annotations

import pytest

from src.api.helpers import format_date
from src.reports.renderer import (
    _enrich_pitchers_workload,
    render_report,
)


# ---------------------------------------------------------------------------
# Rest-display date formatting (E-247-06: renderer now uses the shared
# api.helpers.format_date; _format_short_date was removed as a duplicate).
# These pin the same outputs the removed helper produced for valid ISO dates.
# ---------------------------------------------------------------------------


def _removed_format_short_date(iso_date: str) -> str:
    """Verbatim reproduction of the removed renderer._format_short_date.

    Used only to PROVE format_date is byte-identical for the reachable input
    domain (valid ISO dates -- the call site passes MAX(game_date), guarded by
    truthiness, so it is always a valid ``YYYY-MM-DD`` string).
    """
    import datetime as _dt

    try:
        d = _dt.datetime.strptime(iso_date, "%Y-%m-%d")
        return f"{d.strftime('%b')} {d.day}"
    except (ValueError, TypeError):
        return iso_date


class TestFormatShortDate:
    def test_formats_date(self) -> None:
        assert format_date("2025-04-26") == "Apr 26"

    def test_single_digit_day(self) -> None:
        assert format_date("2025-03-05") == "Mar 5"

    def test_byte_identical_to_removed_helper_over_valid_dates(self) -> None:
        """AC-3: format_date == the removed _format_short_date for every valid
        ISO date (all months, single/double-digit days, leap day, year bounds)."""
        import datetime as _dt

        d = _dt.date(2024, 1, 1)  # 2024 is a leap year -> exercises Feb 29
        end = _dt.date(2025, 12, 31)
        checked = 0
        while d <= end:
            iso = d.isoformat()
            assert format_date(iso) == _removed_format_short_date(iso), (
                f"date formatter diverged on {iso}"
            )
            d += _dt.timedelta(days=1)
            checked += 1
        assert checked == 731  # 2024 (366) + 2025 (365)


# ---------------------------------------------------------------------------
# _enrich_pitchers_workload
# ---------------------------------------------------------------------------


class TestEnrichPitchersWorkload:
    def test_pitcher_with_workload(self) -> None:
        pitching = [{"player_id": "p1", "name": "Ace"}]
        workload = {
            "p1": {
                "last_outing_date": "2025-04-24",
                "last_outing_days_ago": 2,
                "pitches_7d": 85,
                "span_days_7d": 3,
                "appearances_7d": 2,
            }
        }
        _enrich_pitchers_workload(pitching, workload)

        assert pitching[0]["_rest_date"] == "2025-04-24"
        assert pitching[0]["_rest_display"] == "Apr 24"
        assert pitching[0]["_p7d_display"] == "85p (2g)"
        assert "Last: Apr 24" in pitching[0]["_workload_subline"]

    def test_pitcher_no_workload(self) -> None:
        pitching = [{"player_id": "p1", "name": "Ace"}]
        _enrich_pitchers_workload(pitching, {})

        assert pitching[0]["_rest_date"] == ""
        assert pitching[0]["_rest_display"] == "\u2014"
        assert pitching[0]["_p7d_display"] == "\u2014"
        assert pitching[0]["_workload_subline"] == "No recent outings"

    def test_null_pitch_counts(self) -> None:
        pitching = [{"player_id": "p1", "name": "Ace"}]
        workload = {
            "p1": {
                "last_outing_date": "2025-04-25",
                "last_outing_days_ago": 1,
                "pitches_7d": None,
                "span_days_7d": 2,
                "appearances_7d": 2,
            }
        }
        _enrich_pitchers_workload(pitching, workload)

        assert pitching[0]["_p7d_display"] == "?p (2g)"

    def test_zero_pitches_recorded_shows_0p(self) -> None:
        """AC-4: pitches_7d=0 with appearances shows '0p (1g)', not em-dash."""
        pitching = [{"player_id": "p1", "name": "Ace"}]
        workload = {
            "p1": {
                "last_outing_date": "2025-04-25",
                "last_outing_days_ago": 1,
                "pitches_7d": 0,
                "span_days_7d": 1,
                "appearances_7d": 1,
            }
        }
        _enrich_pitchers_workload(pitching, workload)

        assert pitching[0]["_p7d_display"] == "0p (1g)"

    def test_no_7d_appearances(self) -> None:
        pitching = [{"player_id": "p1", "name": "Ace"}]
        workload = {
            "p1": {
                "last_outing_date": "2025-04-10",
                "last_outing_days_ago": 16,
                "pitches_7d": 0,
                "span_days_7d": None,
                "appearances_7d": None,
            }
        }
        _enrich_pitchers_workload(pitching, workload)

        assert pitching[0]["_p7d_display"] == "\u2014"
        assert pitching[0]["_rest_display"] == "Apr 10"


# ---------------------------------------------------------------------------
# render_report — HTML output validation
# ---------------------------------------------------------------------------


def _minimal_report_data(
    pitching: list[dict] | None = None,
    workload: dict | None = None,
) -> dict:
    """Build minimal data dict for render_report."""
    return {
        "team": {"name": "Test Team", "season_year": 2025, "record": None},
        "generated_at": "2025-04-26T12:00:00Z",
        "expires_at": "2025-05-10T12:00:00Z",
        "freshness_date": "2025-04-25",
        "game_count": 10,
        "recent_form": [],
        "pitching": pitching or [],
        "batting": [],
        "spray_charts": {},
        "roster": [],
        "runs_scored_avg": None,
        "runs_allowed_avg": None,
        "has_plays_data": False,
        "plays_game_count": 0,
        "team_fps_pct": None,
        "team_pitches_per_pa": None,
        "pitching_workload": workload or {},
        "generation_date": "2025-04-26",
    }


class TestReportHTMLOutput:
    """AC-2, AC-3, AC-4, AC-5, AC-6, AC-7: HTML output contains expected elements."""

    def _make_pitcher(self, player_id: str = "p1", name: str = "Ace Pitcher") -> dict:
        return {
            "player_id": player_id,
            "name": name,
            "jersey_number": "21",
            "games": 5,
            "gs": 2,
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
            "whip": "1.30",
            "strike_pct": "66.7%",
            "fps_pct": None,
            "pitches_per_bf": None,
        }

    def test_last_outing_header_class(self) -> None:
        pitcher = self._make_pitcher()
        workload = {
            "p1": {
                "last_outing_date": "2025-04-24",
                "last_outing_days_ago": 2,
                "pitches_7d": 85,
                "span_days_7d": 3,
                "appearances_7d": 2,
            }
        }
        html = render_report(_minimal_report_data([pitcher], workload))

        # Pin the actual rendered <th> element class attribute, not a bare
        # "last-outing-header" substring -- that token also appears inside the
        # inline JS selector (querySelectorAll('.last-outing-header')), so a
        # substring check would pass even if the <th> markup class were removed.
        # The template renders the header with an extra responsive class
        # (``mob-hide-extra``); assert that exact element class string.
        assert '<th class="last-outing-header mob-hide-extra">' in html

    def test_last_outing_cell_class_and_data_date(self) -> None:
        pitcher = self._make_pitcher()
        workload = {
            "p1": {
                "last_outing_date": "2025-04-24",
                "last_outing_days_ago": 2,
                "pitches_7d": 85,
                "span_days_7d": 3,
                "appearances_7d": 2,
            }
        }
        html = render_report(_minimal_report_data([pitcher], workload))

        # Pin the actual rendered <td> element class attribute, not a bare
        # "last-outing-cell" substring -- that token also appears inside the
        # inline JS selector (querySelectorAll('.last-outing-cell')), so a
        # substring check would pass even if the <td> markup class were removed.
        # The template renders the cell with an extra responsive class
        # (``mob-hide-extra``) plus the data-date attribute; assert that exact
        # element opening tag.
        assert '<td class="last-outing-cell mob-hide-extra" data-date="2025-04-24">' in html

    def test_p7d_column_present(self) -> None:
        pitcher = self._make_pitcher()
        workload = {
            "p1": {
                "last_outing_date": "2025-04-24",
                "last_outing_days_ago": 2,
                "pitches_7d": 85,
                "span_days_7d": 3,
                "appearances_7d": 2,
            }
        }
        html = render_report(_minimal_report_data([pitcher], workload))

        assert "Pitches (7d)" in html
        assert "85p (2g)" in html

    def test_pitching_annotation_class(self) -> None:
        pitcher = self._make_pitcher()
        html = render_report(_minimal_report_data([pitcher]))

        assert "pitching-annotation" in html
        assert "Generated" in html

    def test_js_snippet_present(self) -> None:
        pitcher = self._make_pitcher()
        html = render_report(_minimal_report_data([pitcher]))

        assert "<script>" in html
        assert "last-outing-cell" in html
        assert "last-outing-header" in html
        assert "pitching-annotation" in html

    def test_js_uses_var_not_let_const(self) -> None:
        pitcher = self._make_pitcher()
        html = render_report(_minimal_report_data([pitcher]))

        # Extract the JS block
        start = html.index("<script>")
        end = html.index("</script>") + len("</script>")
        js_block = html[start:end]
        assert "var " in js_block
        assert " let " not in js_block
        assert " const " not in js_block

    def test_no_workload_shows_em_dash(self) -> None:
        pitcher = self._make_pitcher()
        html = render_report(_minimal_report_data([pitcher]))

        # pitcher with no workload data: em dash in Last column
        assert "\u2014" in html

    def test_key_player_workload_subline(self) -> None:
        """AC-9: Key pitcher callout includes workload sub-line."""
        pitcher = self._make_pitcher()
        workload = {
            "p1": {
                "last_outing_date": "2025-04-24",
                "last_outing_days_ago": 2,
                "pitches_7d": 85,
                "span_days_7d": 3,
                "appearances_7d": 2,
            }
        }
        html = render_report(_minimal_report_data([pitcher], workload))

        # Key player callout should have a last-outing-cell with data-date
        assert "key-player-stats last-outing-cell" in html
        assert "85p (2g)" in html

    def test_graceful_fallback_no_js(self) -> None:
        """AC-6: Without JS, formatted dates and 'Last'/'Generated' headers remain."""
        pitcher = self._make_pitcher()
        workload = {
            "p1": {
                "last_outing_date": "2025-04-24",
                "last_outing_days_ago": 2,
                "pitches_7d": 85,
                "span_days_7d": 3,
                "appearances_7d": 2,
            }
        }
        html = render_report(_minimal_report_data([pitcher], workload))

        # Server-rendered: "Apr 24" for last outing
        assert "Apr 24" in html
        # Server-rendered: "Last" header (not "Rest")
        assert ">Last<" in html
