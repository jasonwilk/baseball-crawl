# E-266-04: Headless-Chromium expand+print test for the Outings Breakdown

## Epic
[E-266: Pitcher Outings Breakdown — Expand-in-Place & Print](epic.md)

## Status
`TODO`

## Description
After this story is complete, a pytest headless-Chromium test renders the flag-ON report, loads it in Chromium via `file://`, and asserts the expand-in-place + print-collapsed behaviors that string-level gates cannot see: the outing detail row is hidden on screen until its pitcher row is activated, a click/keypress makes it visible on screen, and under print media the detail rows are `display:none`. This is the automated backstop for the browser-only rendering bug class that every string-level gate missed (epic Background smoking-gun).

## Context
The E-265 defects were invisible to string-presence tests (`tests/test_outings_render.py:293-296` asserts a print-CSS string and PASSES while the render was blank — epic Background). claude-architect ruled the mechanism (epic TN-6): Python Playwright, a deterministic test over fixture-rendered HTML loaded via `file://`, asserting real visibility. The expand-in-place pivot changed WHAT is asserted (screen-collapsed → click-visible → print-collapsed) vs. the original draft's "print shows expanded" — this story verifies E-266-01's layout and locks in the regression backstop.

## Acceptance Criteria
- [ ] **AC-1**: A pytest test renders the flag-ON report HTML from synthetic fixture data containing **≥2 pitchers WITH outings** (≥1 is needed so `tr.outing-detail-row` exists and the test isn't vacuously green; ≥2 is needed for the AC-2(f) accordion single-open check), **at least one of which has both a single-digit-score outing row and a double-digit-score row** (for the AC-2(d) alignment backstop); the test loads the render in headless Chromium via `file://`. Per epic TN-6 (software-engineer), an **on-the-fly Jinja render is preferred** (reusing the app's Jinja env for the custom filters `ip_display`/`rate2`/`pct`/`rate`/`format_date` and the `pitching`/`pitcher_outings`/`era_basis` shapes) — it eliminates both the committed-PII concern and golden-drift; if a committed golden HTML is used instead it MUST use synthetic/redacted data (fake team + players, never a real opponent — doc-PII byte-gate, `.claude/rules/pii-safety.md`) AND carry an explicit "regenerate when the outings markup changes" note.
- [ ] **AC-2** (three-state assertion — the real regression check): on the first outing detail row's per-outing table (`tr.outing-detail-row table.outing-log-table`, first), the test asserts, per epic TN-6:
  - **(a)** BEFORE activating its pitcher row, the table is NOT visible on screen (`bounding_box()` is `None` / the detail row carries `hidden`);
  - **(b)** AFTER clicking the pitcher row (or dispatching Enter on it), the table BECOMES visible on screen AND the pitcher row's `aria-expanded` becomes `"true"` — using an auto-retrying wait (`expect(locator).to_be_visible()`) to absorb the toggle/reflow race before asserting;
  - **(c)** AFTER `page.emulate_media(media="print")`, the detail rows are NOT visible / `display:none` (the print-collapsed rule — the INVERSE of the old "print shows expanded" assertion).
  - **(d)** (Game-cell alignment backstop — UXD-F2/CR-F3): within an expanded outing-log table, across two outing rows whose Outcome+Score differ in width (a single-digit-score row, e.g. "W 7-1", and a double-digit-score row, e.g. "W 13-11"), the **opponent-name element's bounding-box `x` is equal within ≤1px** (sub-pixel rounding tolerance; not a loose "close enough"). This proves the ~50px result-span `min-width` + the specificity-qualified left-justify (E-266-01 AC-5) actually hold in a real browser — cheap insurance against a future CSS "simplification" dropping either (the alignment bug that broke twice). The Playwright harness is already present for (a)-(c), so this is one added assertion.
  - **(e)** (interaction completeness — Cat 11): pressing **Space** on a focused pitcher row ALSO expands it (parity with click/Enter — the E-266-01 accordion binds Enter AND Space), and the row's `aria-expanded` toggles `"true"`↔`"false"` in sync when it collapses again.
  - **(f)** (accordion single-open — Cat 11): after expanding one pitcher row, activating a SECOND pitcher row collapses the first — at most one detail row is visible on screen at a time (per epic TN-1 / E-266-01 AC-3). The fixture therefore needs ≥2 pitchers with outings.
  A single-state assertion does NOT satisfy this AC (it would pass even if the section were always-visible or always-hidden). `page.pdf()` + text-extraction is NOT required (an optional secondary smoke may be added but stays out of the required ACs).
- [ ] **AC-3** (non-vacuous — load-bearing, FAIL-CLOSED per epic TN-6): the test is fail-closed — on the scoped dev/main environment it always attempts to launch Chromium and hard-FAILS (error, not skip) if the binary is absent, so it can never silently no-op to green. The only skip path is an explicit OPT-OUT escape-hatch env var — the exact literal `SKIP_BROWSER_TESTS` (per epic TN-6, the same token E-266-03's `devcontainer.md` documents — cross-story pin) — for a legitimately chromium-less contributor environment; it is NOT an opt-IN marker that must be set for the test to run. Closure verification confirms the test EXECUTED (pytest reports skips distinctly), not skipped-and-passed.
- [ ] **AC-4** (operator step — Footgun 1, single source of truth): the one-time live-container operator action required for the closure gate to run this test green (`pip install -r requirements-dev.txt && playwright install --with-deps chromium`) is documented AUTHORITATIVELY in `.claude/rules/devcontainer.md` by E-266-03 (AC-3, Footgun 1) — this story does NOT restate it. To avoid two drifting copies (Codex Cat 12), the test module carries only a **one-line pointer** to that devcontainer.md section so the closure operator finds it. Per epic TN-7 Footgun 1.
- [ ] **AC-5**: `python -m pytest tests/` is green with chromium installed (the operator step performed).

## Technical Approach
Follow epic TN-6. Render the flag-ON report from synthetic fixture data (on-the-fly Jinja render preferred), write to a temp file, and drive Chromium via Python Playwright: `file://` load, then the three-state assertion on the first outing detail row's table — hidden on screen → click the pitcher row → visible on screen (auto-retrying wait) → `emulate_media(media="print")` → not visible. Keep the test deterministic — no live DB, credentials, or server. The strongest form reproduces the class of failure: it would FAIL against a template where the detail row cannot open on screen (or where print does not collapse) and PASS against E-266-01's implementation.

## Dependencies
- **Blocked by**: E-266-01 (the expand-in-place layout + print-collapsed CSS must be in so the test passes against the fixed template), E-266-02 (the `playwright` PACKAGE must be importable — AC-1/AC-5 depend on it), E-266-03 (chromium binary installed)
- **Blocks**: E-266-05 (codifies the mechanism this story establishes)

## Files to Create or Modify
- `tests/test_outings_browser.py` (new — the headless-Chromium expand+print test; final filename implementer's choice)
- a committed HTML/fixture artifact if the implementer chooses the golden-file approach (optional per AC-1)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-266-05**: the concrete, real headless-Chromium render+print test mechanism that `.claude/rules/browser-render-testing.md` codifies as the discipline (cited illustratively, not hard-named — epic TN-8).

## Definition of Done
- [ ] The two-state screen assertion (collapsed → click-visible) AND the print-collapsed assertion (AC-2 a-c) pass in a real headless-Chromium run
- [ ] Space activation + `aria-expanded` sync + accordion single-open (AC-2 e-f) verified; Game-cell opponent-`x` alignment equal within ≤1px across a single- and a double-digit-score row (AC-2 d) verified
- [ ] The test is FAIL-CLOSED — it hard-FAILS (not skips) when chromium is absent; the ONLY skip path is the `SKIP_BROWSER_TESTS` opt-out (AC-3)
- [ ] Fixture is synthetic/PII-safe with ≥2 pitchers with outings (one having both a single- and double-digit-score row); on-the-fly Jinja render preferred (AC-1)
- [ ] The one-line operator-step pointer to `devcontainer.md` is present (AC-4) — no second copy of the step
- [ ] `python -m pytest tests/` is green with chromium installed and the test EXECUTED (not skipped) in the run (AC-5)

## Notes
AC-3 is the load-bearing one: a skip-when-absent test that never runs defeats the whole epic (epic TN-6). The strongest form of AC-2 is a test that would FAIL against a template that can't open the detail row on screen OR doesn't collapse it in print, and PASSES against E-266-01's layout — that proves the test catches the bug class, not just that the current template renders.
