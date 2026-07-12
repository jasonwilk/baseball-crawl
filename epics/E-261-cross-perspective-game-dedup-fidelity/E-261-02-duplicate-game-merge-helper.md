# E-261-02: Canonical duplicate-game merge helper (`merge_duplicate_game`)

## Epic
[E-261: Cross-Perspective Game-Dedup Fidelity](./epic.md)

## Status
`TODO`

## Description
After this story, a single canonical helper merges a duplicate `games` row into its canonical twin: all six FK child tables are re-pointed or unioned, ambiguous (non-disjoint-perspective) pairs are refused rather than guessed, and the losing row is deleted. The helper is the shared foundation for the in-pipeline twin merge (E-261-03b) and the operator repair pass (E-261-04).

## Context
The dedup redirect collapses future writes onto the canonical `game_id` but never merges an already-persisted twin row, so duplicate pairs are permanent once created (epic Background, Defect A second half). Two consumers need identical merge semantics; per the "de-dup the dedup" precedent (`plan_player_dedup`/`execute_collapse` shared by load-path sweep and CLI), the merge logic lives in exactly one place.

## Acceptance Criteria
- [ ] **AC-1**: Given a twin pair with disjoint perspectives across the six child tables per Technical Notes TN-3 (`game_perspectives`, `player_game_batting`, `player_game_pitching`, `plays` with `play_events` following their parents, `spray_charts`, `reconciliation_discrepancies`), when `merge_duplicate_game(conn, source_game_id, canonical_game_id)` runs, then every child row of the source is re-pointed to the canonical `game_id` (perspectives unioned), the source `games` row is deleted, and no FK or UNIQUE violation occurs (FKs ON in the test connection).
- [ ] **AC-2**: Given a pair where BOTH rows carry child rows for the SAME `perspective_team_id` (not a cleanly mergeable twin), when the helper runs, then it refuses: no rows are modified, and a structured refusal is reported to the caller (mirroring the player-dedup fork-refusal principle per TN-3). The refusal is decided by PRE-classification (intersect the source vs canonical child-row `perspective_team_id` sets, or read `game_perspectives`, BEFORE any write) — NOT by catching a mid-merge `IntegrityError`; a refusal leaves zero rows modified, never a half-applied merge (Phase-3 finding DE-2).
- [ ] **AC-3**: The helper does NOT commit — the caller owns the transaction boundary. Its rollback guarantee has a stated PRECONDITION: the caller must hold an OPEN (non-autocommit) transaction, since under `isolation_level=None` each statement self-commits and no rollback-able transaction exists. Given an explicit open transaction with `foreign_keys=ON`, a mid-merge failure leaves the transaction rollback-able with no partial merge visible after rollback (per the shared-connection partial-commit footgun rule). The unit test proves this with an explicit transaction + `foreign_keys=ON` (Phase-3 finding DE-3).
- [ ] **AC-4**: Given a source row with zero child rows (bare duplicate `games` row), when the helper runs, then the source row is deleted and the canonical row is untouched.
- [ ] **AC-5**: Unit tests cover AC-1 through AC-4 against the real schema using the FULL current migration set (through 011) — NOT 001+008+010, which omits the migration-009 `spray_charts` UNIQUE rebuild (`event_gc_id, perspective_team_id, chart_type`) that the merge re-points spray against (Phase-3 finding I). At least one case has `play_events` children, one has rows in all six child tables, and at least one includes a `spray_charts` row so the spray re-point path is exercised (spray identity is `event_gc_id`; `game_id` is nullable — Phase-3 finding CR LOW-6).

## Technical Approach
New `src/db/game_merge.py`, pure connection-in/dataclass-out (no commit), following `merge_player_pair(manage_transaction=False)` and `reload_game_plays` conventions. Detection of WHICH pairs to merge is NOT this story's job — callers (03b, 04) decide; this story only executes a merge decision. The helper docstring must state the no-cascade reality: every `games` FK child is a plain `REFERENCES` (no `ON DELETE CASCADE`), so the losing `games` row is deleted LAST — a premature delete aborts loudly on the FK rather than silently cascading child loss (Phase-3 finding DE-1). Check the Cleanup-Detection Mirror Invariant (`.claude/rules/data-model.md`) when finalizing the child list.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-261-03a (offline predicate lands in `game_merge.py`), E-261-03b (invokes `merge_duplicate_game`), E-261-04

## Files to Create or Modify
- `src/db/game_merge.py` (create)
- `tests/test_game_merge.py` (create)

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-261-03b**: `merge_duplicate_game()` call signature + refusal result shape, invoked at the redirect site when a source-event twin row exists.
- **Produces for E-261-03a / E-261-04**: `game_merge.py` as the neutral low-layer home for the reusable OFFLINE same-game predicate (03a factors it here; 04 imports it) — see epic finding-J resolution.
- **Produces for E-261-04**: the same helper as the execute step of the CLI merge plan.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Verified UNIQUE shapes (`migrations/001_initial_schema.sql`, 2026-07-12): `plays` is `UNIQUE(game_id, play_order, perspective_team_id)` (line 489 — perspective-scoped; the abbreviated `UNIQUE(game_id, play_order)` in `.claude/rules/data-model.md` prose is incomplete), stat tables are `UNIQUE(game_id, player_id, perspective_team_id)`, spray is `UNIQUE(event_gc_id, perspective_team_id)` (+ `chart_type` after migration 009). So a disjoint-perspective twin pair cannot collide on ANY child table's UNIQUE key — the AC-2 refusal path exists for the non-disjoint case only. `reconciliation_discrepancies` and `plays_boxscore_checks`-style run-scoped tables: re-point by `game_id` and rely on their run-scoped keys; verify each against the schema during implementation.
