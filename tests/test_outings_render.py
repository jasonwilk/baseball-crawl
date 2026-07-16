"""Render tests for the flag-gated Outings Breakdown section (E-265-02).

Exercises ``render_report`` + ``scouting_report.html``: the flag-on/flag-off
pair (AC-1 byte-identical proof), the green strong-outing treatment + summary
indicator (AC-4), the inline season line with its badge states (AC-5), the
section-level plays-derived note (AC-3), None-renders-as-em-dash (AC-4/AC-6),
the empty-data non-crash path (AC-6), and the print-pagination override (AC-7).
"""

from __future__ import annotations

from src.reports.pitcher_outings import Outing, PitcherOutings, SeasonSummary
from src.reports.renderer import render_report
from tests.test_report_rendering import _base_data


# ── Factories ──────────────────────────────────────────────────────────


def _outing(**overrides) -> Outing:
    base = dict(
        game_id="g1",
        game_date="2026-03-10",
        opponent="Rival High",
        ip_outs=18,
        bf=22,
        h=4,
        hr_allowed=1,
        bb=2,
        so=6,
        r=2,
        fps_pct=0.75,
        charted_pa=20,
        era=2.5,
        appearance_order=1,
        is_strong=False,
    )
    base.update(overrides)
    return Outing(**base)


def _season(**overrides) -> SeasonSummary:
    base = dict(
        ip_outs=54,
        games=6,
        games_started=6,
        er=8,
        so=40,
        bb=10,
        h=30,
        bf=120,
        era=3.11,
        whip=1.20,
        fps_pct=0.62,
        k_per_bf=0.33,
        bb_per_inn=0.55,
        k_per_bb=4.0,
        h_per_bf=0.25,
        small_sample=False,
        low_bb=False,
        zero_bb=False,
    )
    base.update(overrides)
    return SeasonSummary(**base)


def _pitcher(**overrides) -> PitcherOutings:
    base = dict(
        player_id="p1",
        name="Ace Smith",
        jersey_number="22",
        season=_season(),
        outings=[_outing()],
    )
    base.update(overrides)
    return PitcherOutings(**base)


def _render(show, outings):
    data = _base_data(show_pitcher_outings=show, pitcher_outings=outings)
    return render_report(data)


# ── AC-1: flag-off byte-identical / flag-on renders ────────────────────


class TestFlagGate:
    def test_flag_off_no_key_omits_section(self):
        # render_report called WITHOUT the key (mirrors older callers) -> no
        # BODY markup. (Flag-off also emits no outings CSS -- both the section
        # markup and the CSS are gated on the flag; test_flag_off_omits_outings_css
        # below covers the CSS side. This test asserts on the body tags.)
        html = render_report(_base_data())
        assert '<h2 class="section-header">Outings Breakdown</h2>' not in html
        assert '<div class="outings-section">' not in html
        assert "computed from charted pitch-by-pitch play data" not in html

    def test_flag_off_explicit_false_byte_identical_to_no_key(self):
        baseline = render_report(_base_data())
        # Even with a populated outings list, an explicit False renders nothing
        # and is byte-identical to the no-key baseline (the flag, not the data,
        # gates the section).
        flagged_off = _render(False, [_pitcher()])
        assert flagged_off == baseline

    def test_flag_off_omits_outings_css(self):
        # The outings CSS is now gated on the same flag (PM ruling): flag-off
        # emits ZERO outings CSS, so a flag-off report is byte-identical to a
        # pre-feature render. Assert the outings-specific class rules are absent.
        html = render_report(_base_data())
        for css in (
            ".outings-section", ".outing-log", ".outing-log-summary",
            ".outing-log-flag", ".outing-season-line", ".outing-opp",
            ".outing-strong", ".outing-log-table", ".depth-badge-strong",
        ):
            assert css not in html

    def test_flag_on_includes_outings_css(self):
        html = _render(True, [_pitcher()])
        assert ".outing-log-table" in html
        assert ".depth-badge-strong" in html

    def test_flag_on_renders_section(self):
        html = _render(True, [_pitcher()])
        assert "Outings Breakdown" in html
        assert 'class="outings-section"' in html
        assert "Ace Smith" in html

    def test_flag_on_shows_outing_table_row(self):
        html = _render(True, [_pitcher(outings=[_outing(opponent="Rival High")])])
        assert "Rival High" in html
        assert "outing-log-table" in html


# ── AC-3: section-level plays-derived note ─────────────────────────────


class TestPlaysDerivedNote:
    def test_section_level_note_present(self):
        html = _render(True, [_pitcher()])
        assert "computed from charted pitch-by-pitch play data" in html

    def test_note_absent_when_flag_off(self):
        html = render_report(_base_data())
        assert "computed from charted pitch-by-pitch play data" not in html


# ── AC-4: green treatment + summary indicator ──────────────────────────


class TestGreenTreatment:
    def test_strong_outing_row_class(self):
        html = _render(True, [_pitcher(outings=[_outing(is_strong=True)])])
        assert "outing-strong" in html

    def test_summary_indicator_when_any_strong(self):
        html = _render(True, [_pitcher(outings=[
            _outing(is_strong=False),
            _outing(game_id="g2", is_strong=True),
        ])])
        assert "outing-log-flag" in html
        assert "&#9679;" in html  # the green dot

    def test_no_summary_indicator_when_none_strong(self):
        html = _render(True, [_pitcher(outings=[_outing(is_strong=False)])])
        assert '<span class="outing-log-flag"' not in html

    def test_no_red_exploit_accent(self):
        html = _render(True, [_pitcher(outings=[_outing(is_strong=True)])])
        assert "outing-exploit" not in html


# ── AC-4/AC-6: None renders as em-dash, not 0 / not double-escaped ─────


class TestNoneRendering:
    def test_none_boxscore_fields_render_em_dash(self):
        html = _render(True, [_pitcher(outings=[_outing(
            bf=None, h=None, bb=None, so=None, r=None, hr_allowed=None,
        )])])
        # The mdash literal is emitted with | safe -> NOT double-escaped.
        assert "&amp;mdash;" not in html
        assert "&mdash;" in html

    def test_none_rate_fields_render_em_dash(self):
        html = _render(True, [_pitcher(outings=[_outing(fps_pct=None, era=None)])])
        # pct/rate2 filters emit the em-dash char on None.
        assert "—" in html

    def test_none_opponent_renders_em_dash(self):
        html = _render(True, [_pitcher(outings=[_outing(opponent=None)])])
        assert "&amp;mdash;" not in html


class TestOpponentEscaping:
    """Opponent is external GC data -> rendered via ``| e`` + autoescape.

    Locks the escaping in: special chars/markup in the opponent name must be
    HTML-escaped (no raw markup executes) and must NOT be double-escaped.
    """

    def test_special_chars_escaped_not_raw_not_double(self):
        opp = 'Smith & <b>Sons</b> "JV"'
        html = _render(True, [_pitcher(outings=[_outing(opponent=opp)])])
        # Escaped forms present (cell body AND the title attribute).
        assert "Smith &amp; " in html
        assert "&lt;b&gt;Sons&lt;/b&gt;" in html
        # Raw markup must NOT appear (would execute / break the table).
        assert "<b>Sons</b>" not in html
        # No double-escaping of the ampersand or the angle brackets.
        assert "&amp;amp;" not in html
        assert "&amp;lt;" not in html


# ── AC-5: inline season line + badge states ────────────────────────────


class TestSeasonLine:
    def test_inline_season_line_not_a_table_row(self):
        html = _render(True, [_pitcher()])
        assert "outing-season-line" in html
        # Full context set + rate set labels.
        for label in ("IP", "G (", "ERA", "WHIP", "FPS%", "K/BF", "BB/INN", "K/BB", "H/BF"):
            assert label in html

    def test_rate_formatting(self):
        html = _render(True, [_pitcher(season=_season(fps_pct=0.75, era=3.5, whip=1.2))])
        assert "75.0%" in html   # pct filter
        assert "3.50 ERA" in html  # rate2 filter (2-decimal)
        assert "1.20 WHIP" in html

    def test_small_sample_ip_badge(self):
        html = _render(True, [_pitcher(season=_season(small_sample=True, ip_outs=30))])
        # IP figure wrapped in a depth-badge (fact, not a warning label). Assert
        # the BODY span (the base render has empty pitching, so no other
        # depth-badge span appears) plus that the pitcher block rendered.
        assert '<span class="depth-badge">' in html
        assert "Ace Smith" in html

    def test_zero_bb_strength_badge(self):
        html = _render(True, [_pitcher(season=_season(
            zero_bb=True, k_per_bb=None, bb=0,
        ))])
        assert '<span class="depth-badge depth-badge-strong">0 BB</span>' in html
        # Must NOT render a genuine-no-data dash for K/BB in this case.
        assert "&mdash; K/BB" not in html

    def test_low_bb_count_badge(self):
        html = _render(True, [_pitcher(season=_season(
            low_bb=True, zero_bb=False, k_per_bb=6.0, bb=3,
        ))])
        assert "6.0 K/BB" in html
        assert "3 BB" in html  # raw BB count badge

    def test_none_games_started_renders_em_dash(self):
        # All-NULL appearance_order -> games_started is None -> "—" GS, NOT
        # "None GS" and NOT "0 GS" (which would falsely claim pure reliever).
        html = _render(True, [_pitcher(season=_season(games=4, games_started=None))])
        assert "&mdash; GS" in html
        assert "None GS" not in html
        assert "0 GS" not in html

    def test_games_started_zero_renders_zero(self):
        html = _render(True, [_pitcher(season=_season(games=4, games_started=0))])
        assert "0 GS" in html

    def test_genuine_no_data_k_per_bb_em_dash(self):
        html = _render(True, [_pitcher(season=_season(
            k_per_bb=None, zero_bb=False, low_bb=False,
        ))])
        assert "&mdash; K/BB" in html
        assert '<span class="depth-badge depth-badge-strong">' not in html


# ── AC-6: empty-data non-crash (flag ON, no pitchers) ──────────────────


class TestEmptyData:
    def test_flag_on_empty_list_renders_h2_and_empty_state(self):
        html = _render(True, [])
        assert "Outings Breakdown" in html          # section is genuinely "on"
        assert "computed from charted pitch-by-pitch play data" in html
        assert "No data available" in html          # honest empty state
        # No per-pitcher disclosure rendered (assert the body <summary>, not the
        # always-present CSS rule).
        assert '<summary class="outing-log-summary">' not in html


# ── AC-7: print-pagination override present ────────────────────────────


class TestPrintPagination:
    def test_outings_table_page_break_override(self):
        html = _render(True, [_pitcher()])
        assert "table.outing-log-table { page-break-inside: auto; }" in html
        assert "table.outing-log-table tr { page-break-inside: avoid; }" in html
