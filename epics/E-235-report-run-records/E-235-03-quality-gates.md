# E-235-03: Three quality gates (no-games abort, season-fallback flag, identity flag)

## Epic
[E-235: Report Run Records, Trust Signals & Quality Gates](../E-235-report-run-records/epic.md)

## Status
`TODO`

## Description
After this story is complete, a generation with zero completed games produces an explicit named outcome instead of a silent empty "ready" report; a report whose season was derived via the current-year fallback is flagged in the run record; and a report whose team was matched by name only (no GC anchor) is flagged in the run record. These are the only behavior changes Epic B introduces to the pipeline.

## Context
Three verified silent-failure modes (ROADMAP §2): the ready-but-empty report (the E-234-04 before-anchor), the silent wrong-season fallback, and the silent wrong-team name match. This story converts each into an explicit signal. Gate (a) aborts to a named outcome; gates (b) and (c) flag without aborting. The gate definitions, slot points, the M=0-vs-N=0 distinction, the terminal-state shape, and the footer-data producer contract are in **epic Technical Notes §TN-3** (footer content in §TN-7). This story also threads the footer's trust inputs into the render data so story 07 stays renderer-only.

## Acceptance Criteria
- [ ] **AC-1**: Gate (a) — a crawl/load yielding zero completed games produces an explicit no-games outcome (NOT an empty "ready" report). The run record distinguishes `completed_games == 0` (no games played yet) from `completed_games > 0 AND completed_games_with_data == 0` (games played, none loaded). Per §TN-3.
- [ ] **AC-2**: The no-games outcome is shareable, not a 404 — `generate_report()` sets `reports.status = 'no_games'` (a distinct value, NOT `failed`; `reports.status` is free-text TEXT so no migration is needed) and writes a minimal explanatory HTML page to `data/reports/{slug}.html` carrying the coach-facing message from §TN-7 (`No completed games found for {Team Name} this season...`). The public serve route reads that file from disk, so the shared link renders the message instead of 404ing. (Story 06's admin badge handling must recognize the `no_games` status — noted in §TN-3.)
- [ ] **AC-3**: Gate (b) — when `derive_season_id_for_team()` resolves via the current-year/year-only fallback, the run record sets `season_fallback = 1` and records `season_id_used`; generation continues normally. Per §TN-3.
- [ ] **AC-4**: Gate (c) — `identity_match_method` is set to `name_only` when the team row was matched/attached by name+season with no `gc_uuid`/`public_id` anchor, else `anchor`; generation continues normally. The method is determined at the step-2 `ensure_team_row` call (before the run row exists) and DEFERRED-written — stashed in the generation context and written when the run row is created (§TN-1/§TN-3, SE-F3). Per §TN-3.
- [ ] **AC-5**: The render `data` dict consumed by story 07 carries the footer inputs: M (`completed_games` = distinct completed games on the schedule), N (`completed_games_with_data` = distinct completed games WITH data = the `_query_freshness` count, NOT `load_result.loaded` — §TN-2 SE-F2), K (`plays_game_count`), spray availability, generated date, and a derived `degraded_confidence` boolean (`season_fallback OR identity_match_method == 'name_only'`). Per §TN-3/§TN-6. This story makes the only `generator.py` change needed for the footer; story 07 touches no generator code.
- [ ] **AC-6**: The E-234-04 no-completed-games characterization test is updated from "asserts current empty-ready behavior" to "asserts the explicit no-games outcome." All other E-234-04 negative paths remain unchanged and green. New tests cover gates (b) and (c) setting their flags.
- [ ] **AC-7**: The flag sources are obtained per §TN-3's committed mechanism — `derive_season_id_for_team()` is extended to additively signal the fallback (single source of truth), and the identity match-method comes from the extended `ensure_team_row()` return this story introduces (the same extension carries the insert-vs-match signal story 04 consumes — §TN-4; the extension is required regardless because story 04 needs insert-vs-match). No fallback/identity logic is re-derived where it would drift. The SE+DE alignment settles the extension's exact return SHAPE (tuple vs. small result object, field names), not whether to extend.

## Technical Approach
Add the gate checks at the slot points in §TN-3 (post-load for no-games; at `derive_season_id_for_team()` for season fallback; at the `ensure_team_row` match site for identity, deferred-written). The canonical functions do not expose these signals today (SE-F1): extend `derive_season_id_for_team()` (`src/gamechanger/loaders/__init__.py`) to additively return the fallback signal, and extend `ensure_team_row()` (`src/db/teams.py`) to return its match-method AND insert-vs-match status (the latter consumed by story 04 — introduce it ONCE here). Both are additive; update the canonical functions' callers + tests to unpack the new returns (discover callers per `.claude/rules/testing.md` test-scope discovery). The `ensure_team_row` extension is required regardless (story 04 needs insert-vs-match), so it is the committed path — the SE+DE alignment settles its exact return shape, not whether to extend. Write flags through the run-record handle from story 02. For the no-games terminal state, set `reports.status = 'no_games'` and write the minimal explanatory page (per AC-2). Thread the footer inputs into the existing render `data` dict. Do not recompute aggregates or change any stat value — gates flag/abort only (§TN-8).

## Dependencies
- **Blocked by**: E-235-02
- **Blocks**: E-235-04 (consumes the `ensure_team_row` insert-vs-match signal introduced here), E-235-06, E-235-07

## Files to Create or Modify
- `src/reports/generator.py` (gate logic; run-record flag writes; deferred identity write; render-data threading)
- `src/gamechanger/loaders/__init__.py` (extend `derive_season_id_for_team()` to signal the fallback — additive)
- `src/db/teams.py` (extend `ensure_team_row()` return with match-method + insert-vs-match — additive; introduced here, consumed by story 04)
- Callers + tests of the two canonical functions (additive-return unpack updates; discover via test-scope discovery)
- `tests/test_report_generator.py` (gate tests; updated no-games expectation)
- Possibly `src/reports/renderer.py` only if a minimal no-games page needs a render path (keep footer rendering in story 07)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-235-04**: the extended `ensure_team_row()` return carrying the insert-vs-match signal story 04's in-memory created-set consumes (introduced once here so `src/db/teams.py` is edited only on the 04←03 chain, never concurrently).
- **Produces for E-235-06**: the populated `season_fallback` / `identity_match_method` operator flags the admin list surfaces.
- **Produces for E-235-07**: the render `data` dict footer inputs (M/N/K, spray availability, generated date, `degraded_confidence`) and the no-games coach message.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests (E-234 guards green except the intended E-234-04 no-games update)

## Notes
The no-games gate update to E-234-04 is the ONE intended negative-path behavior change in this epic (ROADMAP §6: gates are the only new behavior). Every other preserved path must stay green.

**SE+DE alignment precedes this story freezing** (shared with story 04, per §TN-3/§TN-4): the exact shape of the `ensure_team_row()` return extension (match-method + insert-vs-match), the `derive_season_id_for_team()` fallback-signal extension, and whether identity falls back to local derivation if the canonical change is too invasive. This is a process gate, not an AC. SE offered to draft the corrected file-scope lines.
