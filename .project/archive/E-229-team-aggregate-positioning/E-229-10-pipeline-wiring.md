# E-229-10: Pipeline wiring — standalone path + scouting path + dashboard link

## Epic
[E-229: Team-Aggregate Defensive Positioning](epic.md)

## Status
`DONE`

## Description
After this story is complete, the E-229 bundle is wired into three pipeline surfaces: (a) `bb report generate <public_id>` (standalone path) triggers the full recompute + bundle generation for the target public_id; (b) `run_scouting_sync` + `bb data scout` (scouting path) auto-generates the E-229 bundle for tracked opponents (B Pre-generate, preserved from E-228); (c) the opponent dashboard "Defensive Positioning" link card resolves to the most-recent `ready` E-229 bundle. Tier 2 LLM rationale integrates per E-229-09's contract.

## Context
E-228 wired all three surfaces in stories E-228-03, E-228-06, and E-228-07. Per user lock during round-1 user input ("let's do it right"), E-229 re-implements these wirings fresh rather than cherry-picking from E-228's commit `2d6be06`. SE may opt to cherry-pick at implementation time IF it saves substantial effort — but the default and contracted path is fresh implementation, and any cherry-pick must be reviewed against the E-229 engine output shape (categorical references must NOT survive).

DE round-1 recommended this as a single story rather than three because the three surfaces are tightly coupled (they all invoke `generate_report()` and read from `team_position_aggregate` + `batter_positioning`). DE estimated ~390 lines across ~6 files for the rewiring.

Per epic TN-1 mandatory-branch-implementation: this is the closure-adjacent work. After this story completes, all stories are DONE, the implement skill performs closure, and the work waits for user dev validation on the combined E-228+E-229 branch HEAD.

## Acceptance Criteria
- [ ] **AC-1**: `bb report generate <public_id>` (standalone path) executes the E-229 recompute (engine writes `team_position_aggregate` + `batter_positioning` rows for the opponent) followed by bundle generation (the 4-page mixed-orientation PDF from E-229-08). The standalone path works for any GC `public_id` (no `team_opponents` link required). Behavior matches E-228's standalone-path shape modulo the new output content.
- [ ] **AC-2**: `run_scouting_sync` and `bb data scout` (scouting paths) auto-generate the E-229 bundle for tracked opponents as part of the scouting pipeline. The auto-bundle step (B Pre-generate from E-228) runs after the positioning recompute and before scout completes. Failure of the bundle step is non-fatal (mirrors E-228's `_compute_team_state_call` non-fatal pattern): WARNING log + scout continues. Tracked-team flow and standalone flow produce identical artifacts for the same opponent (parity check).
- [ ] **AC-3**: The opponent dashboard "Defensive Positioning" link card (in `src/api/routes/dashboard.py` or wherever the card is rendered) resolves to the most-recent `ready` E-229 bundle for the opponent. CX-2 reuse pattern preserved: the standalone bundle IS the tracked-opponent surface (no separate per-tracked-team rendering). Link target: `/reports/{slug}`.
- [ ] **AC-4**: The dashboard link card's empty state (no `ready` report exists) reads as the transitional / failure-recovery case per E-228 (B) Pre-generate framing — under E-229 the auto-bundle should keep the dashboard non-empty for any actively-scouted opponent.
- [ ] **AC-5**: Pipeline parity test: same opponent (real or fixture) through both pipeline paths (standalone + scouting) produces identical `batter_positioning` + `team_position_aggregate` rows when projected onto data columns (excluding `computed_at`, which differs by timestamp between two runs per CR I5). Verified by a test that runs both paths against the same input and compares the resulting database rows with `computed_at` excluded from the equality check.
- [ ] **AC-6**: E-228's categorical-model code paths in pipeline wiring (e.g., references to `call_state`, `team_state_call`, vocabulary block) are fully retired in the new wiring. A `grep` AC: no surviving references to retired columns/constants in pipeline files (`src/cli/`, `src/pipeline/`, `src/api/routes/`).
- [ ] **AC-7**: **Fresh re-implementation only** per user lock ("let's do it right" — Phase 1 Q-4). SE may consult E-228 commits as REFERENCE PATTERNS (read-only) but MUST NOT cherry-pick code from `2d6be06`. The wiring is written fresh against the E-229 engine output shape. Verified by `git log --oneline` or commit-by-commit review during dispatch — implementer's commits are net-new code, not cherry-picked.

(Prior draft's AC-5 covering LLM rationale integration was REMOVED during Phase 4 iteration 2 per DE P1.2 — the LLM render-time threading is wholly owned by E-229-08 AC-7 + AC-8 now; pipeline just calls `generate_report(public_id)` and the bundle's internal render path handles the LLM call. No separate `_run_tier2_rationale(opponent_id)` function in this story.)

## Technical Approach

**Three pipeline surfaces to wire** (per E-228 precedent, fresh implementations):

1. **Standalone path** (`bb report generate <public_id>`):
   - Entry: `src/cli/report.py` or wherever the `bb report generate` command lives
   - Flow: `compute_positioning(conn, public_id)` (E-229-02) → `generate_report(public_id)` (E-229-08; bundle assembly internally calls `generate_rationale()` per flagged batter for the Tier 2 LLM rationale, per E-229-08 AC-7).
   - **No separate Tier 2 step** in this pipeline — the LLM call lives inside bundle assembly per DE P1.2 lock. The non-fatal contract is wholly owned by E-229-09 + E-229-08; pipeline doesn't need its own try/except wrapper for it.

2. **Scouting path** (`run_scouting_sync` + `bb data scout`):
   - Entry: `src/pipeline/trigger.py` (where `run_scouting_sync` is defined; verified via `git grep run_scouting_sync main -- 'src/'` per DE B-6) and `src/cli/data.py` (where `bb data scout` is wired)
   - Flow: existing 7-stage pipeline + new positioning recompute stage + auto-bundle stage (mirrors E-228's two-stage addition in E-228-06)
   - Same call pattern as standalone but bulk-iterated over all tracked opponents

3. **Dashboard link card** (opponent dashboard):
   - Entry: `src/api/routes/dashboard.py` or wherever the opponent dashboard route lives
   - Behavior: query for most-recent `ready` E-229 bundle for the opponent's `public_id`; render card with link to `/reports/{slug}`
   - Empty state: per AC-4 the auto-bundle should keep this non-empty, but the empty state still needs a "no report yet" message

**LLM integration is fully owned by E-229-08** (per DE P1.2 lock during Phase 4 iteration 2): the Tier 2 call sits INSIDE the bundle render step in `generate_report()`. The bundle assembler iterates over flagged batters and threads the rationale directly into the template context; there is no separate "run Tier 2" step that writes to the database and no `_run_tier2_rationale(opponent_id)` function in this pipeline-wiring story. This story's pipeline flow is simply:
```python
def generate_e229_artifacts(conn, public_id):
    compute_positioning(conn, public_id)  # E-229-02 (engine writes both tables atomically)
    return generate_report(conn, public_id)  # E-229-08 (bundle render; internally calls generate_rationale() per flagged batter, threading the Optional[str] result into template context — no DB writes)
```

**Parity test**: a single test in `tests/test_pipeline_e229.py` runs both paths against a small fixture opponent and asserts `batter_positioning` rows + `team_position_aggregate` rows are identical between the two paths' resulting databases when projected onto data columns (excluding `computed_at`, which differs by timestamp between runs per CR I5).

**No cherry-pick policy**: per user's "let's do it right" lock (Phase 1 Q-4) and DE I-8 review tightening, this story implements fresh against the E-229 engine output shape. SE may READ E-228's commit `2d6be06` for reference patterns (e.g., to understand the E-228 pipeline wiring shape) but MUST NOT cherry-pick code from it. Verified during dispatch via commit-by-commit review.

## Dependencies
- **Blocked by**: E-229-08 (bundle generation must work), E-229-09 (LLM contract must be locked)
- **Blocks**: None (this is the final story; closure follows)

## Files to Create or Modify
- `src/cli/report.py` — modify (standalone path wiring)
- `src/cli/data.py` — modify (`bb data scout` scouting path wiring)
- `src/pipeline/trigger.py` — modify (`run_scouting_sync` auto-bundle hook on the scouting flow; path corrected per DE B-6 from the prior draft's incorrect `src/scouting/run_scouting_sync.py`)
- `src/api/routes/dashboard.py` — modify (link card resolution)
- `src/api/templates/dashboard.html` or relevant partial — modify, optional (link card empty state if not already there)
- `src/reports/generator.py` — modify (combined `generate_e229_artifacts` helper if useful for both paths; the LLM render-time threading inside `generate_report()` is OWNED by E-229-08, not this story)
- `tests/test_pipeline_e229.py` — create (parity test; LLM render-time integration is tested in E-229-08's test file, not here)

## Agent Hint
software-engineer

## Handoff Context
This story closes the E-229 implementation. After it completes, all stories are DONE; the implement skill performs closure (per epic TN-1, closure pulls into the E-228 branch HEAD, NOT into main). User dev validation gates the eventual merge of the combined E-228+E-229 stack to main.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
SE may consult E-228's commit `2d6be06` for pipeline-wiring patterns that survive the engine/render rewrites (e.g., the `generate_report()` call sites, the dashboard link card template structure, the `is_llm_available()` pattern). Cherry-picks are an SE optimization, not a contract — the default path is fresh re-implementation per user lock.

### Audit-based completion record (per E-229-10 closure 2026-05-18)

**Verdict**: PASS (audit-based completion per user-accepted SE reasoning, parallel to E-229-05 AC-8 transitive-validation precedent).

**Substantive deliverable**: `_load_bundle_snapshot(slug)` helper in `src/api/routes/dashboard.py` (line 1002) + bundle-snapshot-driven cue rendering wired into `positioning_report_context` (lines 1752-1789), closing the E-228 Phase 4b coverage-cue degradation that previously dropped the `(N games)` count from the dashboard link. Tests at `tests/test_pipeline_e229.py` (4 tests): 3 engine-determinism parity tests in `TestPipelineParity` (lines 148/181/197) + 1 grep AC enforcement test `TestAC6NoV1ReferencesInPipelineFiles.test_no_retired_v1_tokens_in_pipeline_dirs` (line 244).

**Pipeline files NOT modified** (per SE audit): `src/cli/report.py`, `src/cli/data.py`, `src/pipeline/trigger.py`, `src/reports/generator.py`. These call `generate_report(public_id)` directly, which was retargeted to v2 in E-229-08 R2 (via `_write_positioning_bundle()` → `generate_positioning_bundle()`). The CLI/pipeline call chains auto-retargeted because they consume upstream modules whose contents changed, not whose names changed. Adding no-op marker changes would be churn that future readers misinterpret as load-bearing.

**Verification**: `TestPipelineParity` proves both paths (standalone `bb report generate` and scouting `bb data scout` / `run_scouting_sync`) produce identical artifacts via engine determinism — the parity property the audit thesis depends on. `TestAC6NoV1ReferencesInPipelineFiles` enforces zero v1 vocabulary (`call_state`, `team_state_call`, `direction_shade`, `depth_shade`, `zone_concentration`, `POSITIONING_CALL_WORDS`, `POSITIONING_CELL_SHORT_FORMS`, `POSITIONING_COLUMN_ORDER`, `POSITIONING_POSITION_LABELS`) in `src/cli/`, `src/pipeline/`, `src/api/routes/` at CI time.

**Future calibration**: any regression that reintroduces v1 vocabulary in pipeline files or breaks the parity property is caught by the test suite. The audit-based completion is durable, not a snapshot in time.

**Date**: 2026-05-18
