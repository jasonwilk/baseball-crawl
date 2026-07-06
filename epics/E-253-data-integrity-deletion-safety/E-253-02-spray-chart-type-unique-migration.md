# E-253-02: Spray `chart_type` UNIQUE Migration (009) + Loader Accounting

## Epic
[E-253: Data-Integrity & Deletion Safety](epic.md)

## Status
`TODO`

## Description
After this story is complete, defensive spray-chart rows will persist instead of being silently discarded, and the loader will stop miscounting real UNIQUE collisions as idempotent skips. The `spray_charts` uniqueness widens to include `chart_type` so offense and defense for the same event no longer collide. Defensive coverage self-heals on the next report generation.

## Context
See epic Technical Notes **TN-3**. Today `spray_charts` has a table-level `UNIQUE(event_gc_id, perspective_team_id)` (`migrations/001_initial_schema.sql:417`). Offense and defense for one event share `event_gc_id` + `perspective_team_id`, so the second (defensive) `INSERT OR IGNORE` is silently ignored — 100% of defensive rows are dropped and counted as idempotent skips. The `.claude/rules/data-model.md` "~16% defensive coverage" claim is false at the DB layer.

## Acceptance Criteria
- [ ] **AC-1**: Migration 009 widens the `spray_charts` uniqueness to `UNIQUE(event_gc_id, perspective_team_id, chart_type)` via a table rebuild (per TN-3: create new table, `INSERT INTO ... SELECT`, drop old, rename), preserving the existing indexes and FK references. The migration is idempotent per `.claude/rules/migrations.md` and applies cleanly on a populated DB.
- [ ] **AC-2**: Given a game with both offensive and defensive spray events for the same `event_gc_id` + perspective, when the spray loader runs, then BOTH the offensive and defensive rows persist in `spray_charts` (they no longer collide).
- [ ] **AC-3**: The spray loader (`scouting_spray_loader.py`) no longer counts a real UNIQUE collision as an idempotent skip — a genuine collision is distinguished from a true no-op in the loader's accounting/logging.
- [ ] **AC-4**: Verified by REGENERATION, not backfill: a test that regenerates the spray load for a game with known defensive spray data shows the defensive rows now present (per TN-3, no backfill pass exists — self-heals on regeneration).
- [ ] **AC-5**: The migration number is confirmed by globbing `migrations/` at implementation time (expected `009`; 008 is the current live latest).
- [ ] **AC-6**: No existing rows are lost in the table rebuild: given a populated `spray_charts` fixture, the post-rebuild row count equals the pre-rebuild row count (every existing row is carried across by the `INSERT INTO ... SELECT`). This closes the classic table-rebuild silent-drop footgun (`.claude/rules/data-model.md`, E-247 twin-method lessons).

## Technical Approach
See epic Technical Notes **TN-3**. The table rebuild is required because SQLite cannot ALTER a table-level UNIQUE in place; a bare `CREATE UNIQUE INDEX` does not help (the narrow table constraint fires first). The implementing agent owns the exact rebuild SQL and the loader-accounting change.

## Dependencies
- **Blocked by**: E-253-03 (migration-runner atomicity — so the multi-statement table-rebuild migration 009 runs under the fixed atomic runner)
- **Blocks**: E-253-05 (migration numbering: 009 before 010)

## Files to Create or Modify
- `migrations/009_spray_chart_type_unique.sql` (new)
- `src/gamechanger/loaders/scouting_spray_loader.py`
- `tests/` — migration test (rebuild correctness + idempotency) and loader-accounting/regeneration test

## Agent Hint
data-engineer

## Handoff Context
- **Produces for epic closure**: the `.claude/rules/data-model.md` "~16% defensive coverage" claim becomes false-in-the-other-direction (defensive rows now persist). The rule prose correction is a context-layer edit owned by claude-architect at closure (context-layer assessment), NOT part of this story.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Cross-reference: `.claude/rules/migrations.md` (numbering, idempotency, table-rebuild), `.claude/rules/perspective-provenance.md` (UNIQUE constraints include `perspective_team_id`).
