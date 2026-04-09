# E-221: Test Fixture Schema Parity Audit + Post-E-220 Perspective Residuals

## Status
`READY`

## Overview
Land the three residual perspective-awareness fixes that Codex round 8 surfaced on E-220's dispatched work, then eliminate the test-infrastructure drift that allowed the whole round-by-round discovery cascade to happen in the first place. E-221 is the deliberate landing spot for "ship E-220 with known residuals" — it catches what we chose not to grind further on, and it hardens the test safety net so the next cross-cutting invariant epic does not repeat this pattern.

## Background & Context
E-220 made `perspective_team_id` a first-class NOT NULL concept on four stat tables. Eight rounds of post-dispatch Codex review uncovered cross-cutting integration gaps — helpers that took `game_id`/`team_id` without knowing the new perspective dimension. Rounds 1-7 fixed them. Round 8 surfaced three more residuals (cluster 3 Phase 1a incompleteness, Phase 1b missing reconciliation cleanup, `bb data reconcile --game-id` not plumbing perspective) plus a deeper finding: the test safety net itself is lying.

The user chose to ship E-220 with residuals captured as E-221 rather than grind an additional round. This decision was right: diminishing returns were clear by round 7, round 8 regression (round 6's own cluster 2 fix introduced the P1-1 FK violation) showed that continuing to patch was risking new bugs, and the fixture drift explains why so many rounds were needed — per-story CR reviewed diffs against fixtures that did not enforce the very invariants E-220 was establishing.

**Round 8 P1 findings** (all accepted for E-221 scope):
- **R8-P1-1** — `src/api/routes/admin.py::_delete_team_cascade` Phase 1a cascades by `game_id IN (...)` without scoping to the deleted team's perspective. When cross-perspective games exist, the admin delete wipes other participants' rows. Round 6 cluster 3 added the informed-consent UI but never scoped Phase 1a; round 7 added Phase 1b scoped by `perspective_team_id = T` on 5 tables but did not backfill Phase 1a.
- **R8-P1-2** — `_delete_team_cascade` Phase 1b is incomplete. It cleans 5 tables scoped by `perspective_team_id = T` but omits the newly-NOT-NULL `reconciliation_discrepancies.perspective_team_id` from round 7. Team delete fails with a FK violation when the deleted team owns reconciliation rows. Same silent-catch pattern as round 7 P1-1 pre-fix.
- **R8-P1-3** — `src/cli/data.py::bb data reconcile --game-id X` calls `reconcile_game(conn, game_id, dry_run=...)` with no `perspective_team_id` kwarg. Round 6 cluster 4 made `reconcile_all` iterate perspectives but left the single-game CLI path on the default. Cross-perspective games silently miss half the data. The "helper knows, caller doesn't" pattern.

**Round 7 fixture evidence** (expanded here as formal scope):
- 7 test files currently define `games` tables inline with columns that do not enforce production FK constraints: `test_report_generator.py`, `test_e211_report_generator.py`, `test_game_ordering.py`, `test_gc_uuid_resolver.py`, `test_pitching_workload.py`, `test_player_dedup.py`, `test_reconciliation.py`
- 22+ other test files already load `migrations/001_initial_schema.sql` via `executescript` — the correct pattern exists but there is no shared helper and no CI guardrail
- `test_report_generator.py`'s inline `reconciliation_discrepancies` fixture is severely drifted (missing `boxscore_value`, `plays_value`, `delta`, `correction_detail`, UNIQUE, and FKs) — round 7 applied a minimum-viable single-column add to unblock the bonus bugfix but left the rest for this epic
- `test_admin_delete_cascade.py::test_cascade_delete_team_preserves_games_row_when_other_perspective_remains` only asserts own-team rows disappear; it does not assert that the other participant's perspective-tagged rows survive. Had it, R8-P1-1 would have been caught in round 6.

E-220's History records the full 7-round remediation arc and the structural miss that drove this epic.

## Goals
- R8-P1-1, R8-P1-2, R8-P1-3 fixed with RED tests demonstrating the bug before the fix
- All 7 inline-fixture test files migrated to a shared real-schema helper with FK enforcement
- A lint/CI guardrail prevents new inline `CREATE TABLE` statements in `tests/`
- `test_admin_delete_cascade.py` gains cross-perspective preservation assertions (other participant survives)
- Full test suite baseline matches or improves on E-220 close state (72F/4254P/16E after E-220 round 8)

## Non-Goals
- Adding new E-220-style invariants or perspective dimensions — this epic consolidates what E-220 started, it does not extend it
- Re-opening E-220's bonus bugfix in `generator.py` — that landed in round 7
- Building a generic test-fixture generator or ORM layer — the shared helper is a thin `executescript` wrapper, nothing more
- Fixing the 72 pre-existing test failures or 16 pre-existing errors — those predate E-220 and are out of scope
- Migrating the inline `reconciliation_discrepancies` fixture in `test_report_generator.py` to real schema via the shared helper in a single sweep — the shared helper migration (Story 05) handles the whole file atomically, not column-by-column

## Success Criteria
- R8-P1-1: admin delete of a team that shares games with other perspectives leaves other participants' rows intact (plays, spray_charts, player_game_batting, player_game_pitching, reconciliation_discrepancies). RED test added that exercises the cross-perspective case and fails before the fix.
- R8-P1-2: admin delete of a team with reconciliation_discrepancies rows succeeds without FK violation. RED test added.
- R8-P1-3: `bb data reconcile --game-id X` processes all loaded perspectives for the game, not just one. RED test added that loads two perspectives and asserts discrepancies from both land in the database.
- Shared helper `tests/conftest.py::load_real_schema(conn)` exists, is used by all 7 former-inline files, and enables `PRAGMA foreign_keys=ON` via prepended PRAGMA per `.claude/rules/migrations.md`.
- Grep audit: zero `CREATE TABLE` statements in files under `tests/` except in `tests/conftest.py` itself (if applicable) or explicit fixture helpers marked with a pragma comment.
- CI guardrail: a test or lint step fails when a PR introduces an inline `CREATE TABLE` in `tests/`.
- `test_admin_delete_cascade.py` has at least one test that asserts cross-perspective rows survive a single-team delete under the informed-consent path.
- Full suite: 72F/4254P/16E matched or improved (net zero regression, new tests pass).

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-221-01 | Shared real-schema fixture helper | TODO | None | - |
| E-221-02 | Migrate 7 inline-fixture test files to helper | TODO | E-221-01 | - |
| E-221-03 | CI guardrail: forbid inline CREATE TABLE in tests/ | TODO | E-221-02 | - |
| E-221-04 | Cross-perspective preservation test coverage | TODO | E-221-02 | - |
| E-221-05 | R8-P1-1 Phase 1a perspective scoping | TODO | E-221-04 | - |
| E-221-06 | R8-P1-2 Phase 1b reconciliation_discrepancies cleanup | TODO | E-221-02 | - |
| E-221-07 | R8-P1-3 `bb data reconcile --game-id` perspective plumb | TODO | E-221-02 | - |
| E-221-08 | CA context-layer codification for E-220 lessons | TODO | None | - |

## Dispatch Team
- software-engineer
- data-engineer
- claude-architect

## Technical Notes

### TN-1: Shared fixture helper (Story 01)
Create `tests/conftest.py` (or extend existing) with a `load_real_schema(conn: sqlite3.Connection) -> None` helper. It reads `migrations/001_initial_schema.sql` from the repo root (use `Path(__file__).resolve().parents[1] / "migrations" / "001_initial_schema.sql"` — repo-root-relative resolution per CLAUDE.md architecture rules), prepends `PRAGMA foreign_keys=ON;\n` to the SQL string, and calls `conn.executescript(...)`.

Per `.claude/rules/migrations.md`: "A `PRAGMA foreign_keys=ON` set on the connection before `executescript()` has no effect on the SQL it runs. If a script needs FK enforcement, prepend `PRAGMA foreign_keys=ON;\n` to the SQL string passed to `executescript()`." This is the load-bearing detail — setting the pragma on the connection alone does not work.

Keep the helper under 30 lines. No pytest fixtures, no parameterization, no environment flags. If a test wants a different schema state, it applies its own modifications after calling the helper.

### TN-2: Fixture migration strategy (Story 02)
The 7 files each have inline schema definitions for subsets of tables. For each file:
1. Replace the inline `CREATE TABLE` block with `load_real_schema(db)`.
2. Walk every INSERT in the file and verify columns referenced exist in real schema. If the old fixture omitted columns the real schema requires as NOT NULL, the INSERT must supply a value.
3. Expected breakage class: hardcoded sentinel values (like `team_id=999`) that were never seeded into `teams`. Fix by seeding a real opponent team with `_seed_team()` helpers if they exist in the file, or create minimal per-file seed helpers.
4. Run each file's tests in isolation before moving on. Do NOT batch all 7 then run the suite — the failure attribution becomes impossible.

**`test_report_generator.py` is the largest** (41 inline CREATE TABLE statements) and the most likely to surface cascading assertion failures. Land it last in the migration sequence, after the other 6 are green, so any issues it surfaces can be isolated.

### TN-3: CI guardrail (Story 03)
Add a pytest test in `tests/test_no_inline_schemas.py` (or equivalent) that:
1. Walks every file under `tests/` matching `test_*.py`
2. Greps each for `CREATE TABLE` outside of allowed locations (the shared helper itself, or files marked with a pragma comment like `# noqa: fixture-schema` for legitimate exceptions)
3. Fails with a clear message listing any violations

Alternative implementation: a pre-commit hook or a CI shell script. Pytest-based is preferred because it runs in the same test harness and is harder to skip.

### TN-4: Cross-perspective preservation test coverage (Story 04)
Before fixing R8-P1-1 (Story 05), Story 04 adds the test that catches it. The test:
1. Loads a game from perspective A and perspective B via GameLoader with different `perspective_team_id` values
2. Calls `_delete_team_cascade` on team A with the informed-consent confirmation
3. Asserts that perspective A's stat rows are deleted
4. Asserts that perspective B's stat rows for the SAME game_id are still present
5. Asserts the `games` row itself is still present (via round 6 cluster 2's preservation logic)

This test will FAIL before Story 05 lands and PASS after. Story 05 cannot be marked DONE without this test passing.

### TN-5: R8-P1-1 Phase 1a scoping (Story 05)
`src/api/routes/admin.py::_delete_team_cascade` Phase 1a currently cascades scoped rows by `game_id IN (...)`. The fix: scope by `perspective_team_id = T` (or the equivalent filter) on every DELETE in Phase 1a that touches perspective-carrying tables (`plays`, `spray_charts`, `player_game_batting`, `player_game_pitching`, `reconciliation_discrepancies`).

The game-level cleanup (delete `game_perspectives` rows for T's perspective, then conditionally delete `games` row if no perspectives remain) was already correct from round 6 cluster 2 — do NOT regress that. The fix is at the stat-table layer only.

Consult DE if the SQL shape is unclear — the existing `_delete_game_scoped_data_for_perspectives` helper at `src/reports/generator.py:1306-1389` may be directly reusable. Investigate whether Phase 1a should call the same helper rather than duplicating the logic.

### TN-6: R8-P1-2 Phase 1b reconciliation cleanup (Story 06)
`_delete_team_cascade` Phase 1b cleans 5 tables by `perspective_team_id = T`. Add `reconciliation_discrepancies` as the 6th. One line of SQL: `DELETE FROM reconciliation_discrepancies WHERE perspective_team_id = ?`.

RED test: insert reconciliation rows tagged with team T's perspective, then call `_delete_team_cascade` on T, assert the rows are gone (and the cascade succeeded — no FK violation). Must be tested under FK enforcement (the shared helper from Story 01 provides that).

### TN-7: R8-P1-3 CLI perspective plumbing (Story 07)
`src/cli/data.py::bb data reconcile --game-id X` calls `reconcile_game(conn, game_id, dry_run=...)`. The fix has two options, and **SE must consult DE** before implementing:

**Option A**: Inside the CLI handler, query `game_perspectives` for the given game_id and iterate all perspectives, calling `reconcile_game` once per `(game_id, perspective_team_id)` pair. Mirrors `reconcile_all`'s per-pair iteration from round 6 cluster 4.

**Option B**: Add a `--perspective-team-id N` flag to `bb data reconcile --game-id X`. When omitted, use Option A's iteration. When supplied, reconcile only that one perspective.

Option A alone is sufficient for correctness. Option B is a UX improvement for operator debugging. DE calls which (or both) given the reconcile CLI's operator context.

RED test: load a game from two perspectives, call the CLI path for that game_id, assert both perspectives' discrepancies land in `reconciliation_discrepancies` (distinguishable by the 6-column UNIQUE from E-220 round 7).

### TN-8: Dispatch order and serialization
Stories execute serially during dispatch (one story at a time in the epic worktree). The dependency chain is:
- E-221-01 first (shared helper must exist before migrations)
- E-221-02 next (migrations depend on the helper)
- E-221-03 after 02 (the guardrail check runs against the post-migration state)
- E-221-04 after 02 (cross-perspective test requires real schema via the helper)
- E-221-05 after 04 (fix lands after the RED test is in place)
- E-221-06 and E-221-07 parallel-safe logically but still serial in dispatch; they depend on 02 for FK-enforced tests
- E-221-06 and E-221-07 may run in either order after 05
- E-221-08 is independent (context-layer only, no code dependency). It can run in parallel with any other story or as a dedicated final story — claude-architect's judgment on ordering during dispatch.

### TN-9: RED-test discipline per E-220 round 7 precedent
Every bug-fix story (05, 06, 07) MUST add its RED test BEFORE the fix, run the suite to see it fail, then land the fix and see it pass. This is the round 7 pattern that proved the fix addresses the bug and not a symptom. Code-reviewer will verify the commit graph shows this sequence.

### TN-10: Test baseline expectations
Pre-close E-220 baseline was 72F/4254P/16E. This epic's final run should be 72F/(4254+N)P/16E where N is the number of new tests added (at minimum 4 — one per bug, one cross-perspective assertion expansion). Any REGRESSION (new failures beyond the 72, or previously-passing tests now failing) is a blocker.

## Open Questions
- None — E-220 round 8 findings are fully specified, and the fixture audit scope is enumerated. If Story 02 migration surfaces additional drift that was not in the round 7 audit, capture as round-8 follow-up on the epic, do not block.

## History
- 2026-04-09: Created. Scope absorbed from E-220 round 8 Codex findings (3 P1s) plus the test fixture drift problem that enabled the round-by-round discovery cascade. User chose to ship E-220 with residuals rather than grind a round 9; E-221 is the deliberate landing.
- Expert consultations: none required for planning — all technical decisions already made during E-220 round 7-8 (DE on schema, SE on fixture strategy, Codex on bug surface). Any new decisions during dispatch (Option A vs B in TN-7) route to DE.
- 2026-04-09: E-221-08 added per user direction at E-220 close. Scope: claude-architect codifies the 8 E-220 lessons-learned into durable context-layer artifacts. User explicitly required CA use `.claude/skills/context-fundamentals/SKILL.md` as the procedural guide. Story is independent of E-221-01 through E-221-07 (no implementation dependency) and may run in parallel or last. Dispatch Team updated to include claude-architect.
