"""Headless-Chromium expand+print regression test for the Outings Breakdown (E-266-04).

This is the automated backstop for the browser-only rendering bug class that
every string-level gate missed: the E-265 print-blank defect passed a
print-CSS-string assertion (``tests/test_outings_render.py``) while the rendered
page was blank (epic Background smoking-gun). String presence cannot see real
visibility; a real browser can.

Mechanism (epic TN-6): render the flag-ON report from SYNTHETIC fixture data via
the app's own Jinja env (on-the-fly -- no committed HTML, so no PII and no
golden-drift), write it to a temp file, load it in headless Chromium via
``file://``, and assert the three-state behavior that proves E-266-01's layout:

* collapsed on screen  -> click/Space expands it on screen  -> print collapses it,
* the accordion (one detail row open at a time),
* and the Game-cell opponent-name alignment across differing score widths.

The strongest form: this test would FAIL against the pre-fix E-265 template (the
detail row could not open on screen, or print did not collapse it) and PASSES
against E-266-01 -- it catches the bug class, not just the current render.

FAIL-CLOSED (AC-3): on the scoped dev/main environment this test ALWAYS attempts
to launch Chromium and HARD-FAILS if the binary is absent -- it can never
silently no-op to green. The ONLY skip path is the explicit opt-OUT env var
``SKIP_BROWSER_TESTS`` (set to any non-empty value) for a legitimately
chromium-less contributor environment.

Operator step (one-time, live container): see the "Footgun 1" section of
``.claude/rules/devcontainer.md`` -- the single source of truth (do not restate).
"""

from __future__ import annotations

import os

import pytest

from src.reports.pitcher_outings import Outing, PitcherOutings, SeasonSummary
from src.reports.renderer import render_report
from tests.test_report_rendering import _base_data

_SKIP_ENV = "SKIP_BROWSER_TESTS"


# ── Synthetic, PII-safe fixture (fake team / players / opponents) ──────


def _season(**overrides) -> SeasonSummary:
    base = dict(
        ip_outs=54, games=6, games_started=6, er=8, so=40, bb=10, h=30, bf=120,
        era=3.11, whip=1.20, fps_pct=0.62, k_per_bf=0.33, bb_per_inn=0.55,
        k_per_bb=4.0, h_per_bf=0.25, small_sample=False, low_bb=False,
        zero_bb=False,
    )
    base.update(overrides)
    return SeasonSummary(**base)


def _outing(**overrides) -> Outing:
    base = dict(
        game_id="g1", game_date="2026-03-10", opponent="North Ridge Academy",
        outcome="W", score="7-1", start_relief="S", ip_outs=18, bf=22, h=4,
        xbh_allowed=2, hr_allowed=1, bb=2, so=6, r=1, pitches=85, strike_pct=0.62,
        fps_pct=0.75, charted_pa=20, era=2.5, appearance_order=1,
    )
    base.update(overrides)
    return Outing(**base)


def _pitching_row(player_id: str, name: str) -> dict:
    return dict(
        player_id=player_id, name=name, jersey_number="21", throws="R",
        era="3.11", k9="9.0", whip="1.20", games=6, gs=6, ip_outs=54, h=30,
        er=8, bb=10, so=40, pitches=400, strike_pct="62%", innings_per_game=7,
    )


def _render_report_html() -> str:
    """Render the flag-ON report from synthetic data (AC-1).

    Two pitchers WITH outings (needed for the accordion single-open check), and
    the FIRST pitcher carries both a single-digit-score row ("W 7-1") and a
    double-digit-score row ("W 13-11") so the Game-cell alignment backstop
    (AC-2 d) has two differing-width result spans to compare.
    """
    p1 = PitcherOutings(
        player_id="p1", name="Alex Rivera", jersey_number="21", season=_season(),
        outings=[
            # Same opponent both rows -> the ONLY variable is the score width,
            # isolating the ~50px result-span min-width alignment guarantee.
            _outing(game_id="g1", outcome="W", score="7-1",
                    opponent="North Ridge Academy"),
            _outing(game_id="g2", game_date="2026-03-14", outcome="W",
                    score="13-11", opponent="North Ridge Academy"),
        ],
    )
    p2 = PitcherOutings(
        player_id="p2", name="Sam Carter", jersey_number="14", season=_season(),
        outings=[
            _outing(game_id="g3", game_date="2026-03-12", outcome="L", score="2-5",
                    opponent="East Lake HS", start_relief="R", appearance_order=2),
        ],
    )
    data = _base_data(
        show_pitcher_outings=True,
        pitcher_outings=[p1, p2],
        pitching=[_pitching_row("p1", "Alex Rivera"), _pitching_row("p2", "Sam Carter")],
    )
    return render_report(data)


# ── Fixture: fail-closed Chromium page over the rendered report ────────


@pytest.fixture
def report_page(tmp_path):
    """Yield a Chromium page loaded with the flag-ON report via ``file://``.

    FAIL-CLOSED: the only skip path is the ``SKIP_BROWSER_TESTS`` opt-out. With
    it unset, a missing ``playwright`` package (ImportError) or a missing
    chromium binary (launch error) is a HARD failure, never a skip -- so the test
    can never silently no-op to green (AC-3).
    """
    if os.environ.get(_SKIP_ENV):
        pytest.skip(f"{_SKIP_ENV} set -- browser test opted out (chromium-less env)")

    # Imported AFTER the opt-out check so opt-out works without playwright, but
    # NOT guarded by importorskip -- an absent package here is a hard failure.
    from playwright.sync_api import sync_playwright

    html = _render_report_html()
    report_file = tmp_path / "report.html"
    report_file.write_text(html, encoding="utf-8")

    with sync_playwright() as pw:
        browser = pw.chromium.launch()  # hard-fails if the binary is absent
        page = browser.new_page(viewport={"width": 1100, "height": 900})
        page.goto(report_file.as_uri())
        try:
            yield page
        finally:
            browser.close()


# ── AC-2 (a-f): the three-state + accordion + alignment regression check ─


def test_outings_expand_click_print(report_page):
    from playwright.sync_api import expect

    page = report_page
    row1 = page.locator('tr.pitcher-row[aria-controls="det-1"]')
    row2 = page.locator('tr.pitcher-row[aria-controls="det-2"]')
    table1 = page.locator("#det-1 table.outing-log-table")
    table2 = page.locator("#det-2 table.outing-log-table")

    # (a) collapsed on screen BEFORE activation -- not visible / no box.
    expect(table1).to_be_hidden()
    assert table1.bounding_box() is None
    expect(row1).to_have_attribute("aria-expanded", "false")

    # (b) click the pitcher row -> the detail table BECOMES visible on screen,
    # aria-expanded flips to "true" (auto-retrying wait absorbs the toggle race).
    row1.click()
    expect(table1).to_be_visible()
    expect(row1).to_have_attribute("aria-expanded", "true")

    # (d) Game-cell alignment backstop: across the single-digit ("W 7-1") and
    # double-digit ("W 13-11") score rows, the opponent-name element starts at
    # the SAME x within <=1px -- proves the ~50px result-span min-width + the
    # specificity-qualified left-justify hold in a REAL browser (E-266-01 AC-5).
    opps = page.locator("#det-1 .outing-opp")
    assert opps.count() == 2
    x0 = opps.nth(0).bounding_box()["x"]
    x1 = opps.nth(1).bounding_box()["x"]
    assert abs(x0 - x1) <= 1, f"opponent-name x misaligned: {x0} vs {x1}"

    # collapse again (click) -> hidden + aria-expanded "false".
    row1.click()
    expect(table1).to_be_hidden()
    expect(row1).to_have_attribute("aria-expanded", "false")

    # (e) Space on a focused pitcher row ALSO expands (parity with click/Enter),
    # and aria-expanded toggles back to "true".
    row1.focus()
    row1.press("Space")
    expect(table1).to_be_visible()
    expect(row1).to_have_attribute("aria-expanded", "true")

    # (f) accordion single-open: activating the SECOND row collapses the first --
    # at most one detail row visible on screen at a time.
    row2.click()
    expect(table2).to_be_visible()
    expect(table1).to_be_hidden()
    expect(row1).to_have_attribute("aria-expanded", "false")
    expect(row2).to_have_attribute("aria-expanded", "true")

    # (c) print = collapsed ALWAYS: row2 is expanded on screen, but under print
    # media every detail row is display:none -- the INVERSE of the E-265 "print
    # shows expanded" behavior, and the direct proof the P0 cannot recur.
    page.emulate_media(media="print")
    expect(table2).to_be_hidden()
    expect(table1).to_be_hidden()
    assert table2.bounding_box() is None

    # ...AND the collapsed Pitching table itself STAYS VISIBLE in print. The
    # actual E-265 P0 was a BLANK print -- a regression that hid the whole
    # Pitching section would still pass the detail-hidden checks above, so assert
    # the print-safe content survives: the pitcher rows (the collapsed table) are
    # dropped ONLY of their detail rows, not the table.
    expect(row1).to_be_visible()
    expect(row2).to_be_visible()
    assert row1.bounding_box() is not None
