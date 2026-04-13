# E-221 Checkpoint Handoff

**Status**: 4 of 7 stories DONE + story 05 partially complete (admin.py fix applied, test fixture amendments pending).

**Written by**: main session on 2026-04-13 before a planned session restart due to agent coordination breakdown (multiple SE instances, silent completions, cross-message provenance disputes). The WORK is sound; the AGENTS are flaky. A fresh session should pick up from this commit cleanly.

## What's done (committed in this checkpoint)

### Stories DONE and staged

- **E-221-01** — Shared real-schema fixture helper. `tests/conftest.py::load_real_schema(conn)` + `tests/test_conftest_helper.py`. Loads `migrations/001_initial_schema.sql` with `PRAGMA foreign_keys=ON;` prepended. CR and PM both approved.
- **E-221-02** — Migrated 7 inline-fixture test files to `load_real_schema(db)`. Files: `test_report_generator.py`, `test_e211_report_generator.py`, `test_game_ordering.py`, `test_gc_uuid_resolver.py`, `test_pitching_workload.py`, `test_player_dedup.py`, `test_reconciliation.py`. Fixed schema-parity hygiene bugs surfaced by FK enforcement. 1 test deleted (`test_null_opponent_name_fallback` — unreachable under `teams.name NOT NULL`), 1 added (`test_empty_opponent_name_fallback` — same code path via empty string). Net test count stable. CR and PM both approved.
- **E-221-03** — CI guardrail `tests/test_no_inline_schemas.py` (43 lines, substring check with `# noqa: fixture-schema` pragma exception) + 15-file classification beyond the original scope (PM-v2 enumerated 15 additional drift files mid-dispatch; user chose Option A "inspect-classify-migrate-or-pragma per file"). **Classification**: 5 legitimate exceptions pragma-exempted (`test_api_health.py`, `test_auth.py`, `test_backup.py`, `test_migrations.py`, `test_trigger.py`), 10 drift files migrated to `load_real_schema`. One scoped `PRAGMA foreign_keys=OFF/ON` wrap in `test_season_id_derivation.py::test_program_row_missing_but_program_id_set` for a degraded-state code path. CR and PM both approved.
- **E-221-04** — RED test `test_delete_team_cascade_preserves_other_perspective_rows` in `tests/test_admin_delete_cascade.py::TestCascadePreservesOtherPerspectiveRows`. Deliberately failing test that catches R8-P1-1 (Phase 1a unscoped DELETE) and a newly-surfaced Phase 2 bug (unconditional games DELETE in admin cascade). CR and PM both approved. **Baseline at close**: 74F/4256P/16E (the 74th failure is this intentional RED test).

### E-221-05 partial work applied (but not completed)

- **admin.py production fix** — Phase 1a DELETEs scoped by `perspective_team_id` across 6 sites (plays, spray_charts, player_game_batting, player_game_pitching, reconciliation_discrepancies, and game_perspectives — the last is a scope expansion SE added as defense-in-depth; see "Open questions" below). Phase 2 games-row DELETE gained `NOT EXISTS (SELECT 1 FROM game_perspectives gp2 WHERE gp2.game_id = games.game_id)` guard. Verified on disk; CR-approved the production fix.
- **Story file updated** — `E-221-05.md` now documents the Phase 2 scope expansion, includes AC-6 for the Phase 2 guard, has an updated Technical Approach.
- **Epic history** — `epic.md` has a 2026-04-12 entry recording the scope expansion and the user's Option C decision.
- **IDEA-068** (main-session behaviors codification) — CANDIDATE idea file in `.project/ideas/IDEA-068-evaluate-main-session-dispatch-behaviors.md`. Also stashed in main-session memory at `/home/vscode/.claude/projects/-workspaces-baseball-crawl/memory/pending_idea_main_session_behaviors.md`. Original draft from claude-architect during active dispatch.
- **IDEA-069** (cascade consolidation refactor) — CANDIDATE idea file in `.project/ideas/IDEA-069-consolidate-cascade-delete-logic.md`. Captures the follow-up refactor to delegate the admin cascade to the canonical helper in `src/reports/generator.py::_delete_game_scoped_data_for_perspectives`. Deferred per user's Option C choice.

## What's pending (for the fresh session to complete)

### E-221-05 remaining work

**The admin.py fix is correct but the E-221-04 RED test currently FAILS** with a Phase 4 FK violation. Empirical evidence:

```
>           conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))
E           sqlite3.IntegrityError: FOREIGN KEY constraint failed
src/api/routes/admin.py:1052: IntegrityError
FAILED tests/test_admin_delete_cascade.py::TestCascadePreservesOtherPerspectiveRows::test_delete_team_cascade_preserves_other_perspective_rows
```

**Diagnosis**: Schema fact: `player_game_batting.team_id INTEGER NOT NULL REFERENCES teams(id)` has **no `ON DELETE` clause anywhere in `migrations/001_initial_schema.sql`** (verify with `grep ON DELETE migrations/001_initial_schema.sql` → zero matches). Default SQLite FK is `NO ACTION` (RESTRICT on immediate).

The E-221-04 RED test fixture seeds team B's perspective rows with `team_id = team_a_id, perspective_team_id = team_b_id`. Pre-fix (unscoped Phase 1a), this worked because Phase 1a cleaned everything. Post-fix (perspective-scoped Phase 1a), team B's row correctly survives Phase 1a and Phase 1b (its perspective is team B, not team A), then Phase 4's `DELETE teams WHERE id = team_a_id` fires the FK constraint.

**Semantic root cause**: `team_id` on perspective-tagged stat rows is the **FK anchor** ("which team's directory owns this row"), not "which team the player batted for." The correct seeding for team B's scouting record of a game team A played is:
- `team_id = team_b_id` (team B's directory owns this scouting record)
- `perspective_team_id = team_b_id` (team B's API call produced the data)
- `player_id = batter_a_id` (the player being described)

E-221-04's fixture put `team_id = team_a_id`, which is a latent semantic bug that E-221-05's perspective scoping exposed.

### The Option A fixture amendments (user-authorized as part of E-221-05's scope)

User chose Option A for the blocker resolution: amend `tests/test_admin_delete_cascade.py` as part of E-221-05's diff. This is NOT regressing E-221-04 — it's fixing a fixture bug that E-221-05's correct perspective scoping surfaced.

**Three amendments needed** in `tests/test_admin_delete_cascade.py`:

#### Amendment 1: `TestCascadePreservesOtherPerspectiveRows::test_delete_team_cascade_preserves_other_perspective_rows` (the RED test, around lines 1025-1253)

Find the fixture seeds for team B's perspective rows in `player_game_batting`, `player_game_pitching`, `plays`, `spray_charts`, and `reconciliation_discrepancies`. Each row has a parameter tuple that includes `team_id` and `perspective_team_id`. The team B rows currently use `team_id = team_a_id`; change them to `team_id = team_b_id`.

Example (actual line 1147, player_game_batting insert):
```python
# BEFORE (buggy)
(game_id, batter_a, team_a_id, team_b_id),  # player_id=batter_a, team_id=team_a_id (BUG), perspective_team_id=team_b_id

# AFTER (correct)
(game_id, batter_a, team_b_id, team_b_id),  # player_id=batter_a, team_id=team_b_id (FK-safe), perspective_team_id=team_b_id
```

`player_id` stays as the original player (`batter_a`, `pitcher_a`). The semantic meaning is "team B's scouting records about the game team A played" — anchored to team B's directory. Apply the same fix across all 5 stat tables' team B seed rows.

#### Amendment 2: `test_cascade_deletes_plays_and_children`

Check the fixture and assertions. If the test seeds two `game_perspectives` entries (team being deleted + another perspective), the new NOT EXISTS guard will preserve the games row (because the other perspective still owns it). Two options:

- **Option 1 (preferred)**: Update the assertion to expect the games row to SURVIVE. This tests the new NOT EXISTS preservation semantics and is strictly better coverage.
- **Option 2**: Remove the second `game_perspectives` seed so only the team being deleted has a perspective. The NOT EXISTS guard then lets the games delete through as before, preserving the original test intent.

Pick based on reading the test's name and docstring — does it intend to test "game cleanup in single-perspective case" or "cascade behavior in multi-perspective case"?

#### Amendment 3: `test_delete_team_proceeds_with_cross_perspective_confirmation`

This test also seeds rows with mixed anchoring (`team_id = deleted_team, perspective_team_id = other_team`) and asserts they're deleted. Under corrected semantics, the row should either:
- Use `team_id = other_team, perspective_team_id = other_team` (consistent anchoring to surviving team) → assertion flips to "row survives", OR
- Use `team_id = deleted_team, perspective_team_id = deleted_team` (consistent anchoring to deleted team) → assertion stays "row is deleted".

Pick whichever better preserves the test's original intent.

### After the amendments

1. Run the RED test via `rtk proxy python -m pytest tests/test_admin_delete_cascade.py::TestCascadePreservesOtherPerspectiveRows -v --timeout=30`. Both assertion loops (Phase 1a survival + Phase 2 games-row preservation) should pass.
2. Run the other two fixed tests to confirm no regression.
3. Run the full suite `rtk proxy python -m pytest tests/ -v --timeout=30`. Target: **73F/4257P/16E** (pre-checkpoint was 74F/4256P/16E; the RED test flips from fail→pass, net -1F +1P).
4. Route to CR and PM for re-verification (per the session-local 3-way verification policy — see below).
5. Main session stages the amendments via `git add -A` in the worktree after both gates approve.
6. PM marks E-221-05 DONE.
7. Proceed to E-221-06, then E-221-07.

### E-221-06 — R8-P1-2 Phase 1b reconciliation_discrepancies cleanup

Small story: add `DELETE FROM reconciliation_discrepancies WHERE perspective_team_id = ?` to `_delete_team_cascade` Phase 1b (it currently cleans 5 tables there; add the 6th). RED test needed before the fix lands per TN-9 discipline. See `E-221-06.md` for the full spec.

### E-221-07 — R8-P1-3 `bb data reconcile --game-id` perspective plumb

SE must consult DE on Option A (iterate perspectives in CLI handler) vs Option B (add `--perspective-team-id` flag). RED test needed. See `E-221-07.md` for the full spec.

## Open questions for the fresh session

### 1. Should the Phase 1a `game_perspectives` DELETE stay?

SE added `DELETE FROM game_perspectives WHERE perspective_team_id = ? AND game_id IN (...)` to Phase 1a (around `admin.py:987-990`). There's ALSO an existing unbounded `DELETE FROM game_perspectives WHERE perspective_team_id = ?` in Phase 1b (around `admin.py:1019-1022`). The Phase 1a version is a strict subset of what Phase 1b catches. CR flagged this as SHOULD FIX (remove for spec compliance and minimalism) with the note that it's functionally harmless and matches the canonical pattern in `src/reports/generator.py::_delete_game_scoped_data_for_perspectives`.

**Recommended resolution**: Either (a) remove the Phase 1a version for minimalism, OR (b) keep it as defense-in-depth and document the reasoning in a code comment. Fresh session's call. Either is defensible.

### 2. Phase 1b's scope: is it really untouched?

CR Phase 1b regression check confirmed Phase 1b (admin.py:998-1022) is byte-identical to pre-story state. AC-5 holds.

### 3. AC-4 cites a non-existent test name

PM-v2 discovered that the story file's AC-4 cites `test_cascade_delete_team_preserves_games_row_when_other_perspective_remains` but that test does not exist as a separate function in `tests/test_admin_delete_cascade.py`. The coverage described by AC-4 is folded INTO the RED test. Fresh session should either (a) update the AC-4 text to reference the actual test location, or (b) add the separate test function if missing. Minor story-file hygiene.

## Known agent flakiness patterns (for the fresh session's situational awareness)

- **In-process agents die with the parent session.** If your CC session crashes, the team's subagent processes (backendType: in-process in team config) all terminate. The worktree and staged work survive on disk; the agent runtime does not.
- **Silent completion pattern.** Agents occasionally complete work on disk but their text completion reports are silently dropped (never delivered as `<teammate-message>` to the main session). Workaround: verify disk state directly (`git status`, `git diff`) rather than waiting for text confirmation.
- **Same-name agent collision.** If you respawn an agent with the same name after a crash, you may get two instances sharing one name, and messages route randomly. Workaround: spawn with versioned names (`software-engineer-v2`, `product-manager-v2`).
- **PM-v2 Anti-Pattern 7 compliance.** The PM agent definition has an Anti-Pattern 7 requiring explicit `## Input Acknowledgment` header with 3-5 body-specific paraphrase bullets on any relay >500 chars. Initial PM instance in this dispatch required 4 reminders to honor the explicit format; their substantive compliance (body-citing) was always good, but the format ceremony was consistently skipped. A candidate rule revision is captured in IDEA-068.
- **CR's predictive traces can miss FK chains.** During E-221-05 review, CR traced Phase 1a → Phase 1b → Phase 2 and concluded the RED test would pass, but missed the Phase 3/4 FK cascade that actually causes the test to fail. Always run pytest empirically when the story involves FK semantics.

## Session-local policy the fresh session should continue (unless revised)

**3-way verification with verbose reporting**, scoped to THIS epic's remaining dispatch per the user's request on 2026-04-12:

1. **Verbose implementer reporting**: SE/DE completion reports include explicit AC-by-AC self-verification with line-number citations and verbatim pytest output (not summaries).
2. **Independent CR verification**: CR reads actual files, quotes line numbers, runs asserted grep/count checks directly. Does not just "review the diff."
3. **Independent PM AC verification**: PM reads actual worktree files for each AC and cites specific line numbers. Does not rely on SE's self-report alone.
4. **Main-session triangulation**: Before advancing the staging boundary, main session verifies disk state directly via `git diff` and file reads, cross-checking SE/CR/PM reports against empirical state. If any source disagrees, investigate before proceeding.

This policy was introduced because of the silent-completion pattern and the CR FK-chain miss. It's session-scoped, not a permanent context-layer change (the user explicitly said "at least for this session"). If the fresh session sees the policy paying off, consider capturing it in IDEA-068 for post-E-221 evaluation.

## Key commits on main

```
c8ead59  chore(recovery): codify E-220 lessons as minimal context-layer edits  (Phase 1 recovery)
76a7f89  chore(recovery): abandon E-222, drop E-221-08, capture trust signal   (Phase 0 recovery)
24d2cd3  feat(E-220): perspective-aware data architecture                      (E-220 ship)
```

This checkpoint commit will land on top of `c8ead59`.

## Files of interest

- `/workspaces/baseball-crawl/epics/E-221-perspective-residuals-and-fixture-audit/` — epic directory (still in `/epics/`, not archived, because E-221 is not yet complete)
- `/workspaces/baseball-crawl/tests/test_admin_delete_cascade.py` — where the Option A amendments need to land
- `/workspaces/baseball-crawl/src/api/routes/admin.py::_delete_team_cascade` — the production fix (lines 939-1053 or so; fix is already applied and verified correct)
- `/workspaces/baseball-crawl/.project/ideas/IDEA-068-evaluate-main-session-dispatch-behaviors.md` — the behaviors idea (CANDIDATE)
- `/workspaces/baseball-crawl/.project/ideas/IDEA-069-consolidate-cascade-delete-logic.md` — the cascade consolidation follow-up idea (CANDIDATE)
- `/home/vscode/.claude/projects/-workspaces-baseball-crawl/memory/pending_idea_main_session_behaviors.md` — main-session memory stash of the IDEA-068 content, created before the `.project/ideas/` file existed
- `/workspaces/baseball-crawl/.claude/agent-memory/product-manager/MEMORY.md` — PM memory; "Next available idea number" should be IDEA-070 after this checkpoint
- `/workspaces/baseball-crawl/.project/ideas/IDEA-068-consolidate-cascade-delete-logic.md` — **orphan stub file** from PM-v2's numbering reassignment. Contents are a 7-line redirect stub pointing at IDEA-069. Not actively misleading. Can be `git rm`'d at epic closure or carried as-is; fresh session's call.

## How to resume (for the fresh session)

1. Read this handoff doc first
2. `git log --oneline -5` to confirm the checkpoint commit is the HEAD
3. Create a fresh epic worktree: `git worktree add -b epic/E-221-continuation /tmp/.worktrees/baseball-crawl-E-221`
   - Note: the branch name differs from the old `epic/E-221` to avoid collision (old branch was deleted during checkpoint cleanup)
4. Create a fresh team: `TeamCreate` with name `E-221-dispatch-continuation` or similar
5. Spawn a fresh team (SE, DE, PM, CR) with recovery context pointing at this handoff doc
6. Route SE to apply the Option A fixture amendments per the spec in this doc
7. Run the 3-way verification pattern, stage, DONE E-221-05
8. Proceed to E-221-06 and E-221-07 normally

---

**Written on 2026-04-13. Checkpoint commit immediately follows.**
