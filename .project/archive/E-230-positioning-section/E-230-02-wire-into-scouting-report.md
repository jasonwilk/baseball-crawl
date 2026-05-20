# E-230-02: Wire Chart Module Into Scouting Report; Reorder Sections; Pairing Annotation

## Epic
[E-230: Positioning Section Refactor (Scouting Reports)](./epic.md)

## Status
`DONE`

## Description

After this story is complete, the scouting report's Defensive Positioning section renders the new PNG charts from `src/charts/positioning.py` instead of the embedded SVG bundle. The duplicate-header and pill-collision bugs are gone (charts carry no text; HTML owns headers). The report's section order is `Spray Charts → Defensive Positioning` (was the reverse), and both sections carry a symmetric `Through {date} · {N} games · {M} BIP` annotation beneath their `<h2>`. The standalone bundle path at `data/reports/{slug}/index.html` preserves content-level parity per AC-9.

## Context

This story consumes the chart module produced by E-230-01 and wires it into the scouting report flow. The work is HTML/Jinja + a payload helper edit + a `chart_mode` flag on the shared partial — no Python rendering logic lives here.

The same partial `positioning_cards.html` serves two callers (the standalone bundle at `src/reports/positioning_bundle.py` and the scouting report at `src/reports/generator.py`). Per epic Technical Notes section TN-6, a `chart_mode` flag selects between inline-SVG mode (`'svg'` — bundle, unchanged) and PNG-image mode (`'image'` — scouting report, new). The bundle path receives no behavioral change.

Per epic Technical Notes section TN-1 (mandatory branch implementation), dispatch creates the worktree from `epic/E-228-defensive-positioning-cards`, not from main. Validation happens against the combined E-228 + E-229 + E-230 branch HEAD before any merge to main.

## Acceptance Criteria

- [ ] **AC-1**: `_build_scouting_report_positioning_payload` in `src/reports/generator.py` (currently at lines 1530–1655) is updated to call the new chart module per epic Technical Notes section TN-3. The helper derives `perspective_team_id` ONCE via the existing `_choose_perspective_team_id`. **If `perspective_team_id is None`, the helper short-circuits to the zero-coverage payload per AC-10 and TN-10 without calling any chart function.** Otherwise (`perspective_team_id is not None`), the helper threads the same value into the team-level chart call and all six per-position chart calls per Technical Notes section TN-4. No re-derivation of perspective per chart.
- [ ] **AC-2**: The payload dict returned by `_build_scouting_report_positioning_payload` includes a `positioning_team_chart_uri` key (string, `data:image/png;base64,...`) for the team-level chart and a `positioning_card_images` key (dict, position → data URI string) for the six per-position charts. SVG-shaped keys from the prior payload (`positioning_card_svgs`, `positioning_compass_key_svg`) are removed from the scouting-report path; the bundle's separate payload still produces them.
- [ ] **AC-3**: An encoding helper in `src/reports/renderer.py` produces `data:image/png;base64,{b64}` strings from PNG bytes, mirroring the existing spray-chart encoding pattern at lines 89–99. Implementation may be a new `_encode_position_chart` helper or a generalized `_encode_png` helper that the existing spray callers also adopt — implementer's call.
- [ ] **AC-4**: The partial `src/api/templates/reports/positioning_cards.html` reads `chart_mode` from the **nested** `positioning` context object the partial already receives (per epic Technical Notes section TN-6): `{% if positioning.chart_mode | default('svg') == 'image' %}`. Bundle's `_render_cards_template_html` sets `cards_ctx["chart_mode"] = "svg"` inside the `cards_ctx` dict that becomes `positioning` in the template render; scouting report's `_build_positioning_context` adds `"chart_mode": "image"` to its returned positioning dict. Both callers thread the flag via the NESTED `positioning` object — NOT as a top-level template var, and NOT via `{% include with %}`. When `chart_mode='svg'`, the partial renders inline SVG as it does today (bundle path — unchanged). When `chart_mode='image'`, the partial renders `<img src="{{ card.image_uri }}">` for each per-card slot and OMITS the in-card header `<div class="positioning-card-header">` block.
- [ ] **AC-5**: The scouting report template `src/api/templates/reports/scouting_report.html` reorders the two `{% include %}` blocks so that the Spray Charts section (currently at line 802 inside `{% if has_spray or team_spray_uri %}`) renders BEFORE the Defensive Positioning section (currently at line 799). After reorder, the read order is: stats-content header → batting → Spray Charts → Defensive Positioning → stats-content roster + footer.
- [ ] **AC-6**: The Defensive Positioning section's HTML emits `<h2 class="section-header">Defensive Positioning</h2>` followed by `<div class="sort-annotation">Through {freshness_date} · {game_count} games · {team_bip_count} BIP</div>` per epic Technical Notes section TN-2. The team-level chart renders immediately below the annotation, preceded by a small caption "Team alignment" (HTML, not in-chart) to disambiguate it from the per-position grid; the 3-per-row per-position grid (LF/CF/RF top row, 3B/SS/2B bottom row) renders below the team chart. Per-card label is the position name only (no categorical call text per UXD vocabulary decision option (i)).
- [ ] **AC-7**: **Sub-AC tagged "scope: existing Spray section header annotation"**. Beneath the existing Spray section's `<h2 class="section-header">Batter Tendencies</h2>` (currently `scouting_report.html:804`), a new line is added: `<div class="sort-annotation">Through {freshness_date} · {game_count} games · {team_bip_count} BIP</div>`. The format is identical to the Defensive Positioning annotation per Technical Notes section TN-2. Uses the existing `.sort-annotation` CSS class.
- [ ] **AC-8**: Print-preview verification: when a regenerated report on the E-230 branch is opened in a browser print-preview, no blank landscape page appears between the Defensive Positioning section and the subsequent roster section. If a blank page is observed, the implementer applies one of the two CSS fixes named in Technical Notes section TN-8 and re-verifies.
- [ ] **AC-9**: Bundle parity (regression check, content-level). A parameterized regression test calls `generate_positioning_bundle(conn, public_id, season_id, opponent_name, through_date, game_count)` for a fixture opponent with the generation clock frozen (so footer `generated_at`/`expires_at` strings do not drift). The test asserts the rendered HTML CONTAINS each of the following from the E-228+E-229 baseline: every per-card position label (LF/CF/RF/3B/SS/2B), the star polygon points for each populated card, the BIP-count caption strings (e.g., `(N BIP)`), the compass-letter discs A-H, and the bundle-specific compass-key card markup. The test asserts the rendered HTML does NOT contain `<img src="data:image/png;base64,` (which would prove the scouting-report's image-mode markup leaked into the bundle path). Byte-equality is NOT required and is not tested — the assertion is content-level slot-fill per `.claude/rules/testing.md`, robust to footer-timestamp drift and incidental whitespace changes. The fixture inputs are committed under `tests/fixtures/` so the test runs on any branch without external setup.
- [ ] **AC-10**: When `_choose_perspective_team_id` returns `None` (zero-coverage opponent), the Defensive Positioning section renders a single whole-section banner per epic Technical Notes section TN-10 with the section-level annotation showing `0 games · 0 BIP`. No charts attempt to render; no exceptions surface to the caller.
- [ ] **AC-11**: Template tests assert slot-fill content per `.claude/rules/testing.md`: the rendered scouting report HTML for an opponent with coverage contains seven distinct `data:image/png;base64,` prefixes inside the Defensive Positioning section (1 team chart + 6 per-position charts), contains each of the six per-position labels (literal text `LF`, `CF`, `RF`, `3B`, `SS`, `2B`) appearing in the per-position grid in reading order (LF/CF/RF top row, 3B/SS/2B bottom row), contains the literal text `Defensive Positioning` inside an `<h2>`, contains a `.sort-annotation` element under both the Spray and Defensive Positioning sections, contains the literal caption text `Team alignment` between the Defensive Positioning section annotation and the team-level chart, and renders the sections in the order Spray → Defensive Positioning.
- [ ] **AC-12**: All tests pass when run via `python -m pytest tests/ -v` (per `.claude/rules/pytest-verbose.md`).

## Technical Approach

Edit sequence (recommended order for a clean diff):

1. **`src/api/templates/reports/positioning_cards.html`**: introduce the `chart_mode` flag, read from the **nested** `positioning` context object the partial already receives (per epic TN-6). Gate per-card rendering: `{% if positioning.chart_mode | default('svg') == 'image' %}` renders `<img src="{{ card.image_uri }}">` and drops the in-card header; the `'svg'` branch (default) renders inline SVG and keeps the in-card header (existing behavior). The compass-key card (sheet 2 slot 3) and opponent-context card (sheet 2 slot 4) are bundle-specific — gate those sections to `chart_mode='svg'` only. Do NOT introduce a top-level `chart_mode` template var; do NOT use `{% include with %}`.
2. **`src/reports/renderer.py`**: add the encoding helper (or generalize the existing one). Update `_build_positioning_context` to emit `positioning_card_images` (dict) and `positioning_team_chart_uri` (string) when the scouting-report payload is shaped that way, AND add `"chart_mode": "image"` to the positioning dict it returns. Update the bundle's context-dict caller (`positioning_bundle.py::_render_cards_template_html`) in lock-step: add `cards_ctx["chart_mode"] = "svg"` inside `cards_ctx` (the dict that becomes `positioning` in `template.render(positioning=cards_ctx, ...)`).
3. **`src/reports/generator.py`**: rewrite the per-card loop in `_build_scouting_report_positioning_payload` (lines 1592–1609 today) to call the new chart functions. The team-level chart is a new addition — call `render_team_position_chart` once before the per-position loop, encode it, store under `positioning_team_chart_uri`. The per-position loop calls `render_position_chart` for each `position in COVERED_POSITIONS`, encodes each, stores under `positioning_card_images[position]`. All 7 calls receive the same `perspective_team_id` derived via `_choose_perspective_team_id` at line 1626 (per epic TN-4). The team-BIP count for TN-2 is read from `team_position_aggregate.bip_count` (already in `_query_team_aggregate`'s return — see epic TN-2 for the canonical-source rationale). No new query. The bundle's separate payload-build path (`positioning_bundle.py::generate_positioning_bundle`) is untouched in its rendering logic; only the context-dict it feeds the partial gains the explicit `chart_mode='svg'` key.
4. **`src/api/templates/reports/scouting_report.html`**: swap the two `{% include %}` blocks (line 799 and the spray block at line 802). Both includes remain parameterless — `chart_mode` is set in `_build_positioning_context`'s returned context dict (per step 2), not on the `{% include %}` line. Inject the section `<h2>` + `<div class="sort-annotation">` immediately above the include for the Defensive Positioning section. Inject the Spray section's new `<div class="sort-annotation">` beneath its existing `<h2>` (AC-7).
5. **Run the existing suite**: any test that asserted SVG-shaped output for the scouting-report path will fail and needs updating to the new image-shape assertions. Any test that asserted the bundle's output is unaffected.
6. **Print-preview verification (AC-8)**: generate one report locally on the E-230 branch worktree, open the file in a browser, view print preview. If a blank landscape page appears between positioning sheet 2 and roster, apply one of the two TN-8 fixes and re-verify.

The bundle regression test (AC-9) is the highest-leverage assurance that the bundle path is untouched. Implementation: invoke `generate_positioning_bundle` for a fixture opponent with the generation clock frozen, assert content-level slot-fill of the bundle's distinguishing markup (position labels, star polygons, BIP captions, compass letters, compass-key card) AND assert absence of `<img src="data:image/png;base64,` substring. Robust to footer-timestamp drift and incidental whitespace. Fixture inputs committed under `tests/fixtures/`.

## Dependencies

- **Blocked by**: E-230-01
- **Blocks**: None

## Files to Create or Modify

- `src/reports/generator.py` — rewrite `_build_scouting_report_positioning_payload` per AC-1, AC-2, AC-10; thread `team_bip_count` to payload from the already-fetched `team_position_aggregate` row (no new query, per epic TN-2)
- `src/reports/renderer.py` — add PNG encoding helper; update `_build_positioning_context` to consume image-shaped payload keys
- `src/api/templates/reports/positioning_cards.html` — add `chart_mode` flag; gate inline-SVG vs PNG-image rendering; omit in-card header in image mode
- `src/api/templates/reports/scouting_report.html` — swap include order (lines 799 / 802 today); inject section `<h2>` + `.sort-annotation` for Defensive Positioning; inject `.sort-annotation` beneath the Spray section's `<h2>` (line 804 today)
- `tests/reports/test_renderer.py` (or equivalent) — update existing tests that asserted SVG-shape output for the scouting-report path to assert PNG-data-URI shape instead; add slot-fill assertions per AC-11
- `tests/reports/test_bundle_parity.py` — new content-level parity test per AC-9 (slot-fill assertions with `freeze_time`; no byte-equality)

## Agent Hint

software-engineer

## Handoff Context

None — this is the terminal story in E-230.

## Definition of Done

- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes

- Worktree base reminder per epic Technical Notes section TN-1: this story executes in `/tmp/.worktrees/baseball-crawl-E-230` which branches from `epic/E-228-defensive-positioning-cards`, NOT main. All `git diff` references during dispatch (including code-reviewer) compare against the E-228 branch.
- AC-7 explicitly tags a modification to the Spray section (outside the new Defensive Positioning surface). The scope tag exists so the change is visible in the diff and not surprising to reviewers — this is the pairing-symmetry annotation that makes the two sections read as intentionally paired per Technical Notes section TN-2.
- Validation flow: after closure to the E-228 branch, the user runs `docker compose up -d --build app` (no DB action — TN-1 operator note) and exercises the new positioning section against real-opponent data. Merge to main is a separate decision after user sign-off on the combined stack.
