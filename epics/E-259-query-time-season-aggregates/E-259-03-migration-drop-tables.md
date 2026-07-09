# E-259-03: Migration 011 — drop the tables with a refuse-on-member-row preflight

## Epic
[E-259: Query-Time Season Aggregates](epic.md)

## Status
`TODO`

## Description
After this story is complete, migration `011` drops `player_season_batting` and `player_season_pitching` — but only after a preflight confirms neither table holds a row with `stat_completeness IN ('full','supplemented')`. If any such row exists, the migration **refuses**: it aborts and leaves the tables intact rather than destroying non-re-derivable member data.

## Context
The live DB has zero member rows (DE survey: batting `[('boxscore_only', 67)]`, pitching `[('boxscore_only', 48)]`), so no archive/export table is built. The preflight mechanizes that observation as a standing guard: a resurrected member row means a writer we believed deleted has come back, and the correct response is to stop and understand that, not to silently drop it. See Technical Notes §3. The migration runner is transactional as of E-253, so a refused migration rolls back cleanly. Migration numbering confirmed by glob: `010` is the last existing migration, so this is **011**.

## Acceptance Criteria
- [ ] **AC-1**: Given migration `011`, when it runs against a DB with zero `full`/`supplemented` rows in both season tables, then it drops `player_season_batting` and `player_season_pitching` and records itself in `_migrations`.
- [ ] **AC-2**: Given migration `011`, when it runs against a DB where **either** season table holds ≥1 row with `stat_completeness IN ('full','supplemented')`, then it **refuses** — aborts with an operator-visible message naming the offending table, leaves both tables intact, and does NOT record itself as applied (so a later corrected run can proceed).
- [ ] **AC-3**: Given the transactional migration runner (E-253), when `011` refuses, then the abort rolls back cleanly with no partial schema state.
- [ ] **AC-4**: Given a test suite for the migration, when this story is complete, then there is a failing-input test (a seeded member row → refusal) AND a clean-input test (zero member rows → drop), each asserting the post-state (tables gone vs. tables intact + not-recorded).
- [ ] **AC-5**: Given the migration number, when this story is implemented, then the implementer **re-globs `migrations/` at implement time and uses the next free sequential number** rather than trusting the `011` recorded here — per the standing "verify by glob, never trust memory" rule (a migration landing between planning and dispatch would make `011` collide). Throughout this story `011` is a **placeholder for "the next free number"**; the satisfaction condition is that the migration file carries that number. Reconciling the story's own `011` references is NOT part of completion — the artifact is the correctly-numbered migration, not an edited spec.

## Technical Approach
DE chooses the preflight **mechanism** — a SQL guard, a Python check in the migration runner, or a pre-migration gate — this story specifies the outcome (refuse-and-preserve on any member row), not the code. Note that plain SQLite `RAISE` is only valid inside triggers; if a pure-`.sql` conditional abort is awkward, the runner-level Python preflight is a legitimate choice. Whatever the mechanism, AC-2's "not recorded as applied" is essential so a corrected DB can re-run the migration.

**Leaf-table status (DE-verified, live DB):** nothing FK-references `player_season_batting`/`player_season_pitching`, and no view or trigger reads them — so the DROP cannot fail on a dangling dependency (that was migration 011's one runtime failure mode, and it is clean). Record this in the migration's header comment so a future reader knows the leaf status was checked, not assumed.

**Test blast-radius reference:** consult `.claude/agent-memory/data-engineer/schema_drop_test_blast_radius.md` — it is the DE checklist of what a column/table DROP breaks in the test suite beyond INSERT sites (SELECTs, tuple asserts, expected-tables sets, FK-violation vehicles). It is live guidance, NOT a stale reference to evict (E-259-05 keeps it for exactly this reason). Use it to scope the test updates this DROP requires.

## Dependencies
- **Blocked by**: E-259-02 (nothing may write the tables when they drop)
- **Blocks**: E-259-04 (parity apparatus queries these tables; it must go once they are gone)

## Files to Create or Modify
- `migrations/011_drop_season_aggregate_tables.sql` (or the runner-preflight form DE selects)
- Possibly `migrations/apply_migrations.py` (if the preflight is runner-level)
- A migration test file (failing-input + clean-input, AC-4)

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-259-04**: the dropped tables, after which `aggregate_parity.py` and `verify-aggregates` query nothing and must be deleted.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (both migration paths)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
No frozen archive, no export — a frozen archive is "a stale-data trap dressed as safety" (DE). The refusal IS the safety mechanism.
