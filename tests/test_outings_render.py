"""Render tests for the expand-in-place Outings section (E-266-01).

Exercises ``render_report`` + ``scouting_report.html`` for the pivot from the
E-265 standalone ``<details>`` section to an expand-in-place detail row inside
the Pitching table:

* flag-off byte-identical + the AC-10 negative assertion over EVERY addition
  vector (the ungated-script trap a byte flag-off-vs-no-key test cannot catch);
* the interleave-by-``player_id`` correlation and the no-outings ``.get()->None``
  guard (AC-1);
* the collapsed-identical a11y attrs + ``pitcher-row`` class (AC-2), the accordion
  ``<script>`` (AC-3), the expanded-block contents/order (AC-4);
* the 15-column Treatment-B layout with the load-bearing Game-cell CSS-specificity
  selector + result-span ``min-width`` (AC-5), the widened XBH caveat (AC-6);
* template-side green removal with ``.depth-badge-strong`` PRESERVED (AC-7);
* print-collapsed rule + old-machinery absence (AC-8); mobile padding (AC-12).

The rendered-in-a-real-browser expand/print proof is E-266-04 (headless
Chromium); these are string-level assertions only.

None-handling: the "unknown" per-outing fields store ``None`` at the data layer
(E-266-06) and render as em-dash here, exactly as ``opponent`` already does.
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
        outcome="W",
        score="7-3",
        start_relief="S",
        ip_outs=18,
        bf=22,
        h=4,
        xbh_allowed=2,
        hr_allowed=1,
        bb=2,
        so=6,
        r=2,
        pitches=85,
        strike_pct=0.62,
        fps_pct=0.75,
        charted_pa=20,
        era=2.5,
        appearance_order=1,
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


def _pitching_row(player_id: str = "p1", name: str = "Ace Smith", **overrides) -> dict:
    """A Pitching-table row dict as ``render_report`` enriches it.

    Carries ``player_id`` -- the interleave join key correlating this row to its
    ``PitcherOutings`` detail row (E-266-01 TN-5).
    """
    base = dict(
        player_id=player_id,
        name=name,
        jersey_number="22",
        throws="R",
        era="3.11",
        k9="9.0",
        whip="1.20",
        games=6,
        gs=6,
        ip_outs=54,
        h=30,
        er=8,
        bb=10,
        so=40,
        pitches=400,
        strike_pct="62%",
        innings_per_game=7,
    )
    base.update(overrides)
    return base


def _render(show, outings, pitching=None) -> str:
    """Render flag-on/off with a Pitching row per outing pitcher by default.

    The interleave attaches each detail row to the matching Pitching row by
    ``player_id``, so a flag-ON render needs a Pitching row whose ``player_id``
    matches the ``PitcherOutings`` -- the default wires one per pitcher.
    """
    if pitching is None:
        pitching = [_pitching_row(player_id=p.player_id, name=p.name) for p in outings]
    data = _base_data(
        show_pitcher_outings=show, pitcher_outings=outings, pitching=pitching
    )
    return render_report(data)


# ── AC-9 / AC-10: flag-off byte-identical + negative assertion ─────────


class TestFlagGate:
    def test_flag_off_no_key_omits_interleave(self):
        # A no-key render (older callers) emits none of the expand-in-place
        # markup -- neither the interleaved rows nor the outing table.
        html = render_report(_base_data(pitching=[_pitching_row()]))
        assert 'class="outing-detail-row"' not in html
        assert "outing-log-table" not in html
        assert "computed from charted play data" not in html

    def test_flag_off_byte_identical_to_no_key(self):
        # AC-9: with the flag OFF, the render is byte-identical to the no-key
        # render of the SAME pitching data -- every E-266 addition is gated.
        pitching = [_pitching_row()]
        outings = [_pitcher()]
        flag_off = render_report(
            _base_data(
                show_pitcher_outings=False, pitcher_outings=outings, pitching=pitching
            )
        )
        no_key = render_report(_base_data(pitching=pitching))
        assert flag_off == no_key

    def test_flag_off_omits_every_addition_vector(self):
        # AC-10 (load-bearing): the byte flag-off-vs-no-key test CANNOT catch an
        # ungated addition (both sides are flag-off). This positive-absence
        # assertion over EVERY addition vector is what makes "all gated"
        # verifiable -- the accordion script is the sharpest trap.
        html = render_report(
            _base_data(
                show_pitcher_outings=False,
                pitcher_outings=[_pitcher()],
                pitching=[_pitching_row()],
            )
        )
        for token in (
            "outing-detail-row",
            "pitcher-row",                          # class + focus-outline CSS
            'role="button"',
            "tabindex",
            "aria-controls",
            "aria-expanded",
            "querySelectorAll('tr.pitcher-row')",   # the accordion script token
            "outing-game-bundle",
            "outing-log-table",
            "Game-by-game outing log",
        ):
            assert token not in html, f"flag-off leaked addition vector: {token!r}"

    def test_flag_on_includes_outings_css_and_markup(self):
        html = _render(True, [_pitcher()])
        assert "outing-log-table" in html
        assert "depth-badge-strong" in html           # PRESERVED (AC-7)
        assert 'class="outing-detail-row"' in html


# ── AC-1: interleave-by-player_id + no-outings .get()->None guard ──────


class TestInterleave:
    def test_detail_row_after_matching_pitcher(self):
        html = _render(True, [_pitcher(player_id="p1")])
        # Exactly one detail row, correlated to the p1 Pitching row (loop.index 1).
        assert html.count('class="outing-detail-row"') == 1
        assert 'aria-controls="det-1"' in html
        assert 'id="det-1"' in html
        # The detail row sits AFTER its pitcher row in source order.
        row_idx = html.index('aria-controls="det-1"')
        detail_idx = html.index('id="det-1"')
        assert row_idx < detail_idx

    def test_no_detail_row_for_pitcher_without_outings_entry(self):
        # p2 has a Pitching row but NO PitcherOutings entry -> explicit
        # .get()->None guard -> no detail row, and p2's row stays non-interactive.
        html = render_report(
            _base_data(
                show_pitcher_outings=True,
                pitcher_outings=[_pitcher(player_id="p1")],
                pitching=[
                    _pitching_row(player_id="p1"),
                    _pitching_row(player_id="p2", name="No Log"),
                ],
            )
        )
        assert html.count('class="outing-detail-row"') == 1
        assert 'aria-controls="det-1"' in html       # p1 (index 1) is interactive
        assert 'aria-controls="det-2"' not in html   # p2 (index 2) is not

    def test_no_detail_row_when_no_matching_pitching_row(self):
        # A PitcherOutings whose player_id matches NO Pitching row is dropped --
        # the interleave correlates strictly by player_id (not by list position).
        html = render_report(
            _base_data(
                show_pitcher_outings=True,
                pitcher_outings=[_pitcher(player_id="pX")],
                pitching=[_pitching_row(player_id="p1")],
            )
        )
        assert 'class="outing-detail-row"' not in html


# ── AC-2: collapsed-identical a11y attrs + pitcher-row class ───────────


class TestCollapsedContract:
    def test_interactive_pitcher_row_carries_a11y_attrs(self):
        html = _render(True, [_pitcher()])
        assert 'class="pitcher-row"' in html
        assert 'role="button"' in html
        assert 'tabindex="0"' in html
        assert 'aria-expanded="false"' in html
        assert 'aria-controls="det-1"' in html

    def test_pitcher_row_adds_no_cursor_pointer(self):
        # HARD contract: no mouse-visible affordance. The feature adds NO
        # cursor:pointer -- differential against flag-off, since the pre-existing
        # .print-btn legitimately carries one in both renders.
        on = _render(True, [_pitcher()])
        off = render_report(_base_data(pitching=[_pitching_row()]))
        assert on.count("cursor: pointer") == off.count("cursor: pointer")
        assert on.count("cursor:pointer") == off.count("cursor:pointer")

    def test_focus_outline_css_present(self):
        html = _render(True, [_pitcher()])
        assert "tr.pitcher-row:focus-visible td:first-child" in html
        assert "outline: 2px solid #1e3a5f" in html


# ── AC-3: accordion toggle script ──────────────────────────────────────


class TestAccordionScript:
    def test_script_present_and_targets_pitcher_rows(self):
        html = _render(True, [_pitcher()])
        assert "querySelectorAll('tr.pitcher-row')" in html
        # Toggles hidden + keeps aria-expanded in sync.
        assert "aria-expanded" in html
        assert "detail.hidden" in html


# ── AC-4: expanded-block contents & order ──────────────────────────────


class TestExpandedBlock:
    def test_block_contents_in_order(self):
        html = _render(True, [_pitcher()])
        # Anchor inside the detail-row MARKUP (the CSS block also names these
        # classes earlier in the <style>, so search from the detail row start).
        body = html[html.index('class="outing-detail-row"'):]
        hint = body.index("Game-by-game outing log")
        season = body.index("K/BF")
        caveat = body.index("FPS%, HR, and XBH")
        table = body.index('<table class="outing-log-table">')
        assert hint < season < caveat < table

    def test_hint_reports_appearance_count(self):
        html = _render(True, [_pitcher(outings=[_outing(), _outing(game_id="g2")])])
        assert "Game-by-game outing log &mdash; 2 appearances this season" in html

    def test_season_rate_line_labels(self):
        html = _render(True, [_pitcher()])
        # The detail season line carries ONLY the K-rate set (IP/G/ERA/WHIP/FPS%
        # live on the collapsed Pitching row, not duplicated here).
        for label in ("K/BF", "BB/INN", "K/BB", "H/BF"):
            assert label in html

    def test_zero_bb_strength_badge_preserved(self):
        html = _render(True, [_pitcher(season=_season(
            zero_bb=True, k_per_bb=None, bb=0,
        ))])
        assert '<span class="depth-badge depth-badge-strong">0 BB</span>' in html
        assert "&mdash; K/BB" not in html

    def test_low_bb_count_badge(self):
        html = _render(True, [_pitcher(season=_season(
            low_bb=True, zero_bb=False, k_per_bb=6.0, bb=3,
        ))])
        assert "6.0 K/BB" in html
        assert "3 BB" in html

    def test_genuine_no_data_k_per_bb_em_dash(self):
        html = _render(True, [_pitcher(season=_season(
            k_per_bb=None, zero_bb=False, low_bb=False,
        ))])
        assert "&mdash; K/BB" in html
        assert '<span class="depth-badge depth-badge-strong">' not in html


# ── AC-5: 15-column Treatment-B layout + Game cell ─────────────────────


class TestColumns:
    def _thead(self, html: str) -> str:
        start = html.index('<table class="outing-log-table">')
        return html[start:html.index("</thead>", start)]

    def test_fifteen_column_headers_present_in_order(self):
        thead = self._thead(_render(True, [_pitcher()]))
        # Each header cell is `<th ...>LABEL<` except ERA, whose text carries the
        # basis suffix ("ERA (7-inn)"), so it is matched by its opening token.
        order = ["Date", "Game", "S/R", "IP", "BF", "H", "XBH", "HR", "BB",
                 "K", "R", "#P", "S%", "FPS%"]
        positions = [thead.index(f">{h}<") for h in order]
        positions.append(thead.index(">ERA ("))
        assert positions == sorted(positions), "column headers out of order"

    def test_opp_and_wl_not_standalone_headers(self):
        # Treatment B bundles opponent into the Game cell; "Opp" is not a header,
        # and "W/L" is NOT a column header (kills the pitcher-decision collision).
        thead = self._thead(_render(True, [_pitcher()]))
        assert ">Opp<" not in thead
        assert ">W/L<" not in thead

    def test_game_cell_bundle_and_result_span(self):
        html = _render(True, [_pitcher(outings=[_outing(outcome="W", score="7-3")])])
        assert 'class="outing-game-bundle"' in html
        assert 'class="outing-result form-chip-w"' in html
        assert "W 7-3" in html                 # result + score together
        assert "Rival High" in html            # opponent name

    def test_result_coloring_reuses_form_chip_tokens(self):
        html = _render(True, [_pitcher(outings=[
            _outing(outcome="W", score="7-3"),
            _outing(game_id="g2", outcome="L", score="2-5"),
            _outing(game_id="g3", outcome="T", score="4-4"),
        ])])
        assert "form-chip-w" in html
        assert "form-chip-l" in html
        assert "form-chip-t" in html

    def test_none_outcome_renders_em_dash_no_chip(self):
        html = _render(True, [_pitcher(outings=[_outing(outcome=None, score=None)])])
        assert '<span class="outing-result">&mdash;</span>' in html
        # No result chip color token appears in the per-outing table body.
        body = html.split("outing-log-table", 1)[1]
        assert "form-chip-" not in body

    def test_game_cell_left_justify_out_specifies_base(self):
        # UXD-F1 (load-bearing): the left-justify MUST be applied via the
        # table-qualified selector (0,2,3) so it BEATS the base center rule
        # `table.outing-log-table tbody td` (0,1,3). A bare `td.outing-game-bundle`
        # (0,1,1) would lose and silently re-center.
        html = _render(True, [_pitcher()])
        assert "table.outing-log-table tbody td.outing-game-bundle" in html
        assert "table.outing-log-table tbody td {" in html  # the base center rule

    def test_result_span_min_width_present(self):
        # Fixed min-width so opponent names align across single/double-digit + W/L
        # rows (load-bearing). 56px floors the widest 2-by-2-digit score; E-266-04's
        # Chromium alignment backstop measures the opponent-x delta at 0.0px
        # (50px left a ~1px spill on double-digit scores).
        html = _render(True, [_pitcher()])
        assert "min-width: 56px" in html

    def test_new_per_outing_values_render(self):
        html = _render(True, [_pitcher(outings=[_outing(
            start_relief="R", xbh_allowed=3, pitches=91, strike_pct=0.6,
        )])])
        assert ">R<" in html          # S/R
        assert ">3<" in html          # XBH
        assert ">91<" in html         # #P
        assert "60.0%" in html        # S% via pct filter

    def test_none_per_outing_fields_render_em_dash(self):
        html = _render(True, [_pitcher(outings=[_outing(
            start_relief=None, bf=None, h=None, xbh_allowed=None, hr_allowed=None,
            bb=None, so=None, r=None, pitches=None, strike_pct=None, fps_pct=None,
            era=None,
        )])])
        assert "&amp;mdash;" not in html   # em-dash via | safe, not double-escaped
        assert "&mdash;" in html

    def test_strike_pct_legit_zero_renders_percent_not_dash(self):
        # S% == 0.0 (all-balls wildness) is a real 0%, NOT an em-dash.
        html = _render(True, [_pitcher(outings=[_outing(strike_pct=0.0)])])
        assert "0.0%" in html


# ── AC-6: widened XBH caveat ───────────────────────────────────────────


class TestCaveat:
    def test_caveat_widened_to_include_xbh(self):
        html = _render(True, [_pitcher()])
        assert (
            "FPS%, HR, and XBH below are computed from charted play data, "
            "not GameChanger's boxscore."
        ) in html


# ── AC-7: template-side green removal (depth-badge-strong PRESERVED) ───


class TestGreenRemoval:
    def test_green_outing_markup_gone(self):
        html = _render(True, [_pitcher(outings=[_outing()])])
        assert "outing-strong" not in html
        assert "is_strong" not in html
        assert "outing-log-flag" not in html      # the season ● dot
        assert "&#9679;" not in html

    def test_depth_badge_strong_preserved(self):
        # False friend: despite the -strong name, .depth-badge-strong is the
        # zero-walk "0 BB" command badge, unrelated to the removed green.
        html = _render(True, [_pitcher(season=_season(
            zero_bb=True, k_per_bb=None, bb=0,
        ))])
        assert "depth-badge-strong" in html


# ── AC-8: print = collapsed always ─────────────────────────────────────


class TestPrintCollapsed:
    def test_single_print_collapse_rule(self):
        html = _render(True, [_pitcher()])
        assert "tr.outing-detail-row { display: none !important; }" in html

    def test_old_print_machinery_absent(self):
        # The entire E-265 all-expanded-in-print machinery is GONE (TN-4).
        html = _render(True, [_pitcher()])
        assert "matchMedia" not in html
        assert "beforeprint" not in html
        assert "afterprint" not in html
        assert "table.outing-log-table { page-break-inside: auto; }" not in html


# ── AC-12: mobile-padding polish ───────────────────────────────────────


class TestMobilePadding:
    def test_outing_log_table_mobile_padding_tightened(self):
        html = _render(True, [_pitcher()])
        # Inside the ≤640px query the nested table gets the tighter padding that
        # matches the outer table (the desktop 3px 5px otherwise persists).
        assert "table.outing-log-table tbody td { padding: 2px 2px" in html


# ── Opponent escaping (external GC data) ───────────────────────────────


class TestOpponentEscaping:
    def test_special_chars_escaped_not_raw_not_double(self):
        opp = 'Smith & <b>Sons</b> "JV"'
        html = _render(True, [_pitcher(outings=[_outing(opponent=opp)])])
        assert "Smith &amp; " in html
        assert "&lt;b&gt;Sons&lt;/b&gt;" in html
        assert "<b>Sons</b>" not in html
        assert "&amp;amp;" not in html
        assert "&amp;lt;" not in html

    def test_none_opponent_renders_em_dash(self):
        html = _render(True, [_pitcher(outings=[_outing(opponent=None)])])
        assert "&amp;mdash;" not in html


# ── Empty-data non-crash (flag ON, no pitchers) ────────────────────────


class TestEmptyData:
    def test_flag_on_no_pitchers_no_crash(self):
        # Flag on but no pitching rows / no outings -> no detail rows, no crash.
        html = render_report(
            _base_data(show_pitcher_outings=True, pitcher_outings=[], pitching=[])
        )
        assert 'class="outing-detail-row"' not in html
