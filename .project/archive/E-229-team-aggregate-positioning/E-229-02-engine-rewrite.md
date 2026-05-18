# E-229-02: Engine rewrite — team-aggregate centroid + per-batter deviation + atomicity

## Epic
[E-229: Team-Aggregate Defensive Positioning](epic.md)

## Status
`DONE`

## Description
After this story is complete, `src/reports/positioning.py` computes positioning recommendations from the team-aggregate reference frame: a whole-spray centroid per opponent projected (position-scaled per epic TN-8) onto each of 6 fielder positions, producing the star position. Per-batter rows carry deviations from each position's star (NOT a per-position-subset re-evaluation). Both tables refresh atomically in a single transaction. The engine writes NO categorical columns and is the sole writer for `team_position_aggregate`.

## Context
E-228's engine produced categorical outputs (`call_state`, `team_state_call`, `direction_shade`, etc.) using a per-position responsibility-sector model that tautologically over-fired direction labels. E-229's engine is structurally different: it computes a single team-level centroid, projects to each position, and emits raw deviation + zone identity per batter. There is no per-position re-evaluation, no MIXED rule, no categorical bucket beyond the 8-zone compass.

Per epic TN-8, the projection is **position-scaled**: the centroid says "where does this opponent's contact tend to land?" and each fielder's star says "given that lean, where do I shade from MY textbook?" Scaling factors preserve directional fact while honoring position range (outfielders cover more SVG range than infielders).

Per epic TN-2, the engine is the SOLE writer for `team_position_aggregate`. Render and Tier 2 LLM consume; they never recompute.

Per epic TN-6, the engine refreshes both tables for an opponent in a single SQLite transaction. Partial state is forbidden.

## Acceptance Criteria
- [ ] **AC-1**: Given an opponent with spray_charts rows (`chart_type='offensive' AND x IS NOT NULL AND y IS NOT NULL`), when the engine runs, then for each of the 6 fielder positions (LF, CF, RF, 3B, SS, 2B) a row is upserted to `team_position_aggregate` with `(star_x, star_y)` computed per Technical Notes TN-8 (whole-spray centroid projected position-scaled from textbook `BASE_POSITION`) and `bip_count` set to the total opponent BIP count.
- [ ] **AC-2**: For each distinct `player_id` in `spray_charts` for the opponent with at least 1 BIP, the engine produces 6 `batter_positioning` rows (one per fielder position), each with `(direction_deviation, depth_deviation)` as integer ordinal buckets (`0`, `±1`, `±2`) computed against that position's team-aggregate star (NOT a per-position-subset star). The engine reads `player_id` directly from `spray_charts`; no roster JOIN is needed at the engine layer (jersey/name JOINs happen at render time per epic TN-7).
- [ ] **AC-3**: `zone_id` is assigned per epic TN-3 vocabulary by `(sign(direction_deviation), sign(depth_deviation))`; magnitude is ignored for letter assignment (the field-plot position carries magnitude per TN-5). `(0, 0)` deviation → NULL. Sign-rule mapping per epic TN-3: `(neg, neg) = A`, `(neg, 0) = B`, `(neg, pos) = C`, `(0, neg) = D`, `(0, pos) = E`, `(pos, neg) = F`, `(pos, 0) = G`, `(pos, pos) = H`. (sign convention: direction `neg = left`, `pos = right`; depth `neg = in`, `pos = deep`.) Fully deterministic.
- [ ] **AC-4**: `is_thin = 1` when the batter's **total BIP count is < 10** across the opponent's spray data; per-batter, not per-position (per epic TN-5). The same `is_thin` value is denormalized across all 6 of the batter's per-position rows (E-228 v1 pattern). `is_thin` batters STILL contribute to the team-aggregate centroid (they shape the star without earning a per-batter shift).
- [ ] **AC-5**: `is_low_confidence = 1` on `team_position_aggregate` rows when the opponent's total BIP count is `< 50`; else `0` (per epic TN-4 tier boundaries: 0–14 and 15–49 both → 1; 50+ → 0). The engine writes this flag at compute time; render decides what to display per tier.
- [ ] **AC-6**: All `team_position_aggregate` rows (6) AND all `batter_positioning` rows for the opponent are refreshed within a single SQLite transaction (per epic TN-6 atomicity). The DELETE uses `(team_id, season_id)` scope — intentionally broader than the per-perspective INSERT scope so that ALL perspectives rebuild together and a perspective that drops out between runs disappears cleanly (delete-then-insert scope rule per `.claude/rules/architecture-subsystems.md` "Delete-Then-Insert Scope"; origin: E-228 Phase 4b Codex finding that per-perspective DELETE left stale rows from dropped-out perspectives; verified by `test_clean_rebuild_wipes_stale_perspectives` in `tests/test_positioning_engine.py`).
- [ ] **AC-7**: The engine is the SOLE writer for `team_position_aggregate`. No other code path in `src/reports/` recomputes the centroid or shadow-stores deviation values (per epic TN-2). A `grep` AC: no module under `src/reports/` other than `positioning.py` issues `INSERT`/`UPDATE`/`UPSERT` against `team_position_aggregate`.
- [ ] **AC-8**: The engine writes NO retired-categorical-model columns: no `call_state`, no `team_state_call`, no `direction_shade`, no `depth_shade`, no `zone_concentration`. (Verified by code search + by E-229-01 AC-6 confirming the migration removed those columns.)
- [ ] **AC-9**: The engine does NOT execute any per-position responsibility-sector re-evaluation (the R2 logic from E-228-02 Round 2): per-batter `direction_deviation`/`depth_deviation` are computed once against the team-aggregate star, not per-position-subset.
- [ ] **AC-10**: Tests cover: (a) team-aggregate centroid math against golden data (small synthetic spray, hand-verified expected `(star_x, star_y)` per position); (b) per-batter deviation math for the 8 ordinal zones + `(0,0)` null case + the full sign-rule table from AC-3; (c) thin-gate behavior (total BIP<10 → `is_thin=1` on all 6 of the batter's rows, contributes to centroid); (d) confidence-tier behavior (0/15/50 BIP boundaries flip `is_low_confidence`); (e) **transactional atomicity test pattern (per DE I-7)**: patch the second INSERT in the persist function (or the second table's write) to raise an exception; assert that after the exception propagates, the database state matches pre-call state for both `batter_positioning` and `team_position_aggregate` (no partial writes, no stale rows from previous runs); (f) inline fixture builders that populate `batter_positioning` — `_make_positioning_row` at `tests/test_report_renderer.py:1480`, `_make_result` at `tests/test_positioning_llm.py:43`, and bare-SQL INSERT statements in `tests/test_report_generator.py` (lines ~2940, ~2956) — are updated so their *signatures* and *column lists* are v2-shape: kwargs scrubbed of retired columns (`call_state`, `team_state_call`, `direction_shade`, `depth_shade`, `zone_concentration`) and INSERTs use the v2 column set (`zone_id`, `is_thin`, `bip_count`, `hr_count`, plus `is_low_confidence` for `team_position_aggregate` writes). E-229-01 deferred this scope per the DE I-9 carve-out documented in E-229-01 AC-7; E-229-02 owns both the scrub AND the extend. **Scoping rule for assertion content** that depends on render-layer or LLM logic landing in stories 03/04/05/06/07/09: SE picks per test from one of (i) update the assertion to match the new shape if the test does not depend on later-story logic, (ii) mark `@pytest.mark.xfail(reason="re-enable in E-229-XX")` citing the specific story ID that owns the dependency, or (iii) delete the test if it is fully superseded by E-229-02's engine tests or by later stories' render tests. **Hard constraint**: after E-229-02 lands, the suite must collect cleanly and must NOT raise `sqlite3.OperationalError` on retired-column writes. A regression in test pass rate is acceptable so long as the regression is expressed as `xfail`/`skip` markers (NOT as runtime schema errors).

## Technical Approach

**Engine module restructure** (`src/reports/positioning.py`):
- New high-level entry: `compute_positioning(conn, public_id) -> None` — reads spray_charts for the opponent, computes the two table layers, persists atomically.
- New core functions:
  - `_compute_team_aggregate(spray_rows) -> dict[Position, AggregateRow]` — whole-spray centroid + position-scaled projection per TN-8
  - `_compute_batter_deviations(spray_rows, team_aggregate) -> list[BatterRow]` — per-batter deviation against each position's star; ordinal bucket quantization
  - `_quantize_to_zone(direction_dev: int, depth_dev: int) -> Optional[str]` — A-H mapping per TN-3; returns None for `(0,0)`
  - `_persist(conn, public_id, team_aggregate_rows, batter_rows) -> None` — single transaction wrapping both DELETE-by-scope and INSERTs

**Position-scaled projection (TN-8)**: per-position scaling factors are calibrated constants. Initial values come from E-228's `BASE_POSITIONS` reasoning (outfielders ~1.0 factor, middle infielders ~0.5 factor, corner infielders ~0.4 factor — tune during the first-real-opponent calibration pass per epic Rollout). Convention: each constant carries a `# RECALIBRATE after first opponent dataset` annotation until calibrated.

**Atomicity (TN-6)**: the persist function wraps both DELETE-by-scope and INSERTs in a single transaction. Use the engine-self-commit pattern from E-228's TN-6 (the engine commits its own transaction; callers do not wrap).

**Delete-then-insert scope rule** (carried forward from E-228's Phase 4b learning, now codified in `.claude/rules/architecture-subsystems.md` "Delete-Then-Insert Scope"): the DELETE scope must be at least as broad as the rebuild scope. For E-229's engine, INSERTs are per-`(team_id, season_id, perspective_team_id, position)` but the rebuild scope is per-opponent — so the DELETE uses `(team_id, season_id)` to clear ALL perspectives, allowing a perspective that drops out between runs to disappear cleanly. A per-perspective DELETE (finer than the rebuild scope) would leave stale rows from dropped-out perspectives — that was the E-228 Phase 4b bug.

**Retire E-228's R2 logic explicitly**: remove `POSITION_RESPONSIBILITY_SECTORS`, `bips_for_position()`, `_compute_position_row()`, `_compute_team_state_call()`, `ADJACENCY_LATTICE`. **The renderer-side vocabulary block (`POSITIONING_CALL_WORDS`, `POSITIONING_CELL_SHORT_FORMS`, `POSITIONING_COLUMN_ORDER`, `POSITIONING_POSITION_LABELS`) is retained by this story and deleted in E-229-05 per epic History 2026-05-17 replan resolution** (E-229-05 AC-10 owns the vocabulary-block deletion as part of the compact-card template rewrite; tests asserting v1 vocabulary semantics are `xfail`-marked citing E-229-05 in this story per AC-10(f)). The renderer's eventual legend text comes from module-level constants in the renderer, NOT from this block carried forward (see E-229-03 and epic TN-3 module-constant pattern).

**Test coverage**: model the test layout on E-228's `tests/test_positioning_engine.py` (or wherever the engine tests live now). Golden data should be small enough that a human can hand-verify the expected centroid; cover both balanced and pull-side opponent profiles.

**Supersede the v1 engine tests**: `tests/test_positioning.py` (E-228 v1, categorical-model-era) is fully superseded by the new `tests/test_positioning_engine.py` and MUST be deleted as part of this story. The v1 file references retired columns (`call_state`, `team_state_call`, `direction_shade`, `depth_shade`, `zone_concentration`) and the retired R2 responsibility-sector logic; leaving it in place will produce `sqlite3.OperationalError` on collection, violating the AC-10 hard constraint.

## Dependencies
- **Blocked by**: E-229-01 (the v2 schema must exist before the engine writes to it)
- **Blocks**: E-229-03 (the card field generator reads engine output), E-229-06 (the prep page reads engine output), E-229-07 (the call sheet reads engine output), E-229-09 (the LLM input contract describes engine output shape)

## Files to Create or Modify
- `src/reports/positioning.py` — modify (substantial rewrite; remove E-228 categorical-model code per TN-13; add team-aggregate computation, position-scaled projection, deviation computation, atomic persist)
- `tests/test_positioning_engine.py` — modify (or replace; full new test coverage per AC-10)
- `tests/test_positioning.py` — delete (E-228 v1 engine tests; superseded by `tests/test_positioning_engine.py` and incompatible with the v2 schema per Technical Approach)
- `tests/test_report_renderer.py` — modify (rewrite `_make_positioning_row` for the v2 column set per AC-10(f); update or `xfail`-mark assertion-side tests per the AC-10(f) scoping rule — assertions on render-layer logic landing in stories 03/04/05/06 may be xfail-marked citing the owning story)
- `tests/test_report_generator.py` — modify (rewrite bare-SQL INSERTs at lines ~2940 and ~2956 for the v2 column set per AC-10(f); update or `xfail`-mark assertion-side tests per the AC-10(f) scoping rule)
- `tests/test_positioning_llm.py` — modify (rewrite `_make_result` for the v2 row shape per AC-10(f); assertion-side tests that depend on the LLM input contract landing in E-229-09 may be `xfail`-marked citing E-229-09)
- `src/reports/generator.py` — modify (consumer-side SELECT scrub to v2 column set in `_query_batter_positioning`; required to satisfy AC-10(f) clean-collection constraint — discovered via the implementer surface-area trace; without this fix, the SELECT references retired columns that no longer exist on the v2 schema and raises `sqlite3.OperationalError` at collection across ~19 tests in `tests/test_report_generator.py`)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-229-03**: `team_position_aggregate` rows (6 per opponent) + per-position `batter_positioning` rows with `zone_id` + `is_thin` + (per-position) `is_low_confidence` propagation if engine elects to denormalize. E-229-03's field SVG generator reads these to place the star, decide the confidence-tier visual state, and place outlier markers.
- **Produces for E-229-07**: per-batter `zone_id` per position. E-229-07's call sheet matrix cells map to these `zone_id` values (or `·` for `zone_id IS NULL AND is_thin = 0`).
- **Produces for E-229-09**: the engine output shape per batter (jersey, name, position, zone_id, direction_deviation, depth_deviation, BIP_count, team-aggregate-star). E-229-09 locks the LLM input contract against this shape.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The position-scaled projection scaling factors (TN-8) are provisional and expected to move during the first-real-opponent calibration pass (epic Rollout). The story ships them with `# RECALIBRATE` annotations.
