# E-261-03b: In-pipeline twin merge + redirect-site error handling

## Epic
[E-261: Cross-Perspective Game-Dedup Fidelity](./epic.md)

## Status
`TODO`

## Description
After this story, the redirect site merges an already-persisted source-event twin row into the canonical row via `merge_duplicate_game()` (completing Defect A), and does so with correct error handling so a merge failure never bleeds partial writes into the next game's commit. The dedup path becomes self-healing: regenerating a report on a DB carrying a historical duplicate pair collapses the pair instead of erroring or perpetuating it, and re-running is idempotent.

## Context
Defect A second half (epic Background): the redirect never merges the twin row an earlier dedup miss left behind, so pairs are permanent and (pre-E-261-01) erroring. The tolerant same-game decision and the redirect-site plumbing come from E-261-03a; the merge helper contract (and its refusal shape) come from E-261-02. The shared-connection partial-commit footgun and the `replace()`-rewrites-`event_id` ordering trap are the two correctness hazards this story must handle.

## Acceptance Criteria
- [ ] **AC-1**: Given the TN-2 Defect A seeded state (canonical row + un-merged source-event twin), when the own-perspective payload loads, then after the load exactly ONE `games` row remains for the real game, all child rows re-pointed per `merge_duplicate_game`, and `LoadResult.errors == 0`.
- [ ] **AC-2**: Given a twin the merge helper REFUSES (non-disjoint perspectives per E-261-02 AC-2), when the load runs, then the loader does not guess: it logs the refusal at WARNING, leaves both rows intact, and the game still loads without error under the canonical id.
- [ ] **AC-3**: Redirect-site error handling (finding F): when `merge_duplicate_game()` RAISES `sqlite3.Error`, the loader catches it, calls `conn.rollback()` so no partial merge writes remain pending on the shared connection (they must not be silently committed by the next game's commit), and returns `LoadResult(errors=1)` for that game rather than propagating uncaught out of `_load_boxscore_data` (per the shared-connection partial-commit footgun rule).
- [ ] **AC-4**: The twin existence check captures the ORIGINAL source `event_id` BEFORE `replace()` rewrites `summary.event_id` to the canonical id (`game_loader.py:387-388`); the check for "does a `games` row already exist for the source event id" uses that captured original, not the post-`replace` canonical value (finding CR LOW-5).
- [ ] **AC-5**: End-to-end idempotency (finding B, full path): loading the same payload twice on a healed DB produces no further merges, no errors, and no new rows (exercises the real twin merge plus E-261-03a's uniform candidate-loop guard).

## Technical Approach
At the redirect site, after E-261-03a resolves the canonical id, check for an existing `games` row whose `game_id` equals the CAPTURED original source `event_id` (captured before `replace()`), and invoke `merge_duplicate_game(conn, source_game_id, canonical_game_id)` before the upsert. Wrap the merge in `try/except sqlite3.Error` → `conn.rollback()` → return `LoadResult(errors=1)`. Honor the helper's structured refusal (E-261-02 AC-2) by logging a WARNING and leaving both rows intact — the game still loads under the canonical id. Extend the TN-2 Defect A fixture with the twin-merge assertion (one surviving row) and add an idempotency test.

## Dependencies
- **Blocked by**: E-261-03a (same file `game_loader.py` — serial; consumes the resolved canonical id + redirect site), E-261-02 (merge helper)
- **Blocks**: E-261-04 (shared offline predicate + the healed-state contract)

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py` (modify — redirect-site twin-merge invocation + error handling)
- `tests/test_loaders/test_game_dedup.py` (modify — twin-merge, refusal, error-path, idempotency tests)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-261-04**: the healed-DB end state (one row per real game, child rows re-pointed) that the offline repair pass must converge to, and the confirmation that the in-pipeline path self-heals any regenerated team.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Preserve the E-244 `redirect_map` contract exactly: fetch stays keyed by SOURCE event id; only DB-facing keys become canonical. The error-path AC (AC-3) is a MUST per the error-path testing rule (`.claude/rules/testing.md`) — a merge failure must surface as `errors=1`, never a silent skip.
