# E-263-02a: Fact-sheet framework + wiring skeleton

## Epic
[E-263: Deep Scout v1 — Opponent-Intelligence Report Sections](epic.md)

## Status
`TODO`

## Description
After this story is complete, the Deep Scout package exists with a typed fact-sheet contract, the floor-enforcing constructor, the shared trust-surface template partial, and the FULLY PRE-WIRED skeleton — 4 stub group modules, a pre-wired assembler that calls all four, and the template include mechanism with 4 stub partials — so the four section-builder stories (E-263-04/05/06/07) can fill their own stub module + partial without editing any shared file, and the existing report renders unchanged in the meantime. This is the spine that closes the Phase-3 blocking wiring gap (CR MUST-1/MUST-2 ≡ SE-F1).

## Context
CR + SE found a blocking gap in the original single-foundation design: "the assembler composes each builder's group module" contradicted "no builder edits the assembler," so nothing would wire the group modules → the four sections would render empty; and `scouting_report.html` is a 909-line monolith with ZERO `{% include/block/macro %}` and no partials dir, so an `{% include %}` of a not-yet-created partial would `TemplateNotFound` and break the existing report. The resolution (SE option (c), per Technical Notes TN-9) is to pre-create the entire wiring skeleton here so builders only fill stubs. This story is split from the original E-263-02 (the SIG-001 fact moved to E-263-02b) because the skeleton adds enough scope to warrant its own session (CR SHOULD-1).

## Acceptance Criteria
- [ ] **AC-1**: A new `src/reports/deep_scout/` package exists with a code-canonical fact-sheet schema module (per Technical Notes TN-1) defining the fact type `{value, n, status ∈ {ok, thin, no_data}, ethics_tier ∈ {coach_facing, player_safe}}` + an optional `vs` block (defined but unused in v1), and a floor-enforcing constructor helper per Technical Notes TN-2 with the crisp status semantics (matching TN-2, no conflation): a fact with a PRESENT value whose `n` is below its floor → `thin` (the value is still carried, never blanked); a fact whose computation is STRUCTURALLY undefined (e.g. zero valid denominator, no data at all) → `no_data` (carries the raw count if any, never a blank); everything at/above floor → `ok`. Unit tests prove a below-floor value yields `thin` with the value still present, a zero-denominator yields `no_data`, and the `ethics_tier` field is required on every fact.
- [ ] **AC-2**: The shared trust-surface template partial/macro is added under `src/api/templates/reports/deep_scout/` per the E-263-01 layout spec and Technical Notes TN-2 — `ok`/`thin` render at identical full visual weight (badge-only differentiation, no dimming/no distinct thin style), `no_data` shows the raw count never a blank. It is the single idiom the four builder stories reuse.
- [ ] **AC-3**: Four stub group modules exist under `src/reports/deep_scout/` (pitching, running/battery, hitters-defense, blueprint), each an empty builder function with the agreed signature, and a pre-wired assembler calls all four and composes their output into the fact sheet (per Technical Notes TN-9). A test asserts the assembler invokes all four group builders.
- [ ] **AC-4**: The template include mechanism is introduced into `scouting_report.html` (the SOLE edit to that file, per Technical Notes TN-9) with the four section include-slots in the E-263-01 placement order, and four stub partials are created under `src/api/templates/reports/deep_scout/` (or `{% include ... ignore missing %}` is used). The four partial filenames are pinned here (matching the E-263-01 spec).
- [ ] **AC-5**: The existing report renders UNCHANGED — generating a report with only the skeleton present (no section facts yet) does not raise `TemplateNotFound` and produces the same output as before plus empty section slots. A test covers this (the existing report-render path is green).
- [ ] **AC-6**: The fact-sheet builder is invoked from the pipeline seam (`_query_render_save` in `generator.py`, per Technical Notes TN-9), its output placed into the report `data` dict. v1 adds NO new command flags (opponent-only per Technical Notes TN-10).
- [ ] **AC-7**: A shared twin-game test fixture/helper (conftest-level) is landed here supporting BOTH the dedup and role-filter tests per Technical Notes TN-3: it seeds ONE game under two `perspective_team_id`s (the double-count case) AND carries BOTH teams' rows across `plays`/`play_events` (both `batting_team_id` directions), `player_game_batting` (both `team_id` directions), `player_game_pitching`, and `spray_charts` with BOTH `chart_type='offensive'` and `'defensive'` rows — including an opponent error on the OFFENSIVE chart stored under the scouted team's `team_id` (the wrong-team fixture E-263-06 AC-3 needs). Every builder story's no-double-count + role-filter test reuses it rather than hand-rolling divergent fixtures.

## Technical Approach
Create the `src/reports/deep_scout/` package with the schema module (canonical fact-sheet home, code-canonical per the E-257 `recon_scoreboard.py` precedent), the floor helper, the assembler with four stub group-builder calls, and four stub group modules. Introduce a minimal include mechanism into `scouting_report.html` and create four stub partials + the shared trust-surface partial per the E-263-01 layout spec. Wire the builder into the generator seam. The load-bearing constraint is that after this story the report is unchanged-but-wired: the skeleton is inert (stubs produce no facts) yet the includes and assembler are in place so builders only fill bodies.

## Dependencies
- **Blocked by**: E-263-01 (the trust-surface idiom, section placement, and the four pinned partial filenames)
- **Blocks**: E-263-02b, E-263-04, E-263-05, E-263-06, E-263-07

## Files to Create or Modify
- `src/reports/deep_scout/__init__.py` (new)
- `src/reports/deep_scout/<schema module>.py` (new — code-canonical fact type + floor helper; SE names it)
- `src/reports/deep_scout/<assembler>.py` (new — pre-wired 4-call assembler; SE names it)
- `src/reports/deep_scout/<4 stub group modules>.py` (new — pitching, running, hitters-defense, blueprint stubs)
- `src/api/templates/reports/scouting_report.html` (modify — SOLE editor: include mechanism + 4 section slots, per Technical Notes TN-9)
- `src/api/templates/reports/deep_scout/` (new — shared trust-surface partial + 4 stub section partials)
- `src/reports/generator.py` (modify — invoke the builder at the `_query_render_save` seam)
- `tests/test_deep_scout_fact_sheet.py` (new — floor enforcement, ethics_tier required, assembler calls all 4, existing report unchanged)
- `tests/conftest.py` or a shared fixture module (modify/new — the twin-game fixture per AC-7)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-263-02b**: the fact-sheet schema + floor helper + assembler; 02b adds the SIG-001 fact.
- **Produces for E-263-04/05/06/07**: the schema, floor helper, shared trust-surface partial, the four pre-created stub group modules + stub partials each builder fills, and the shared twin-game fixture.
- **Produces for E-263-08**: the schema module path (for the code-canonical pointer) and the fact that v1 adds no new command flags.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests (the existing report renders unchanged — AC-5)

## Notes
This is the heaviest foundational story (the wiring skeleton). Keeping the schema module + partial filenames stable is critical — the four builder stories depend on them not churning.
