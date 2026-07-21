# E-273-01: Reclamation pass core — `reclaim_orphan_reference_data` + single-source invariant-count helper

## Epic
[E-273: Reclaim Orphaned Reference Data After Report Deletion](epic.md)

## Status
`TODO`

## Description
After this story is complete, `src/reports/lifecycle.py` exposes `reclaim_orphan_reference_data(conn) -> ReclaimResult`: a reachability-based terminal pass that removes unreachable `teams`, `players`, and `team_rosters` in DAG order (team tier then player tier), reclaiming all three root causes, and a single-source invariant-count helper that both this pass and downstream stories use to assert the ownership invariant. This is the heart of the epic; wiring, the atomicity refactor, the batch test, and the one-time backlog run all build on it.

## Context
The reclamation pass is the one function that answers the GLOBAL reachability question the per-report cascades cannot (epic Background). It must be an ADDITIVE pass that does not touch `cascade_delete_team` semantics (TN-4), scope every teams-facing predicate to `membership_type='tracked'` (TN-2), never predicate on the dead `is_active` guard (TN-2), include the `plays` table in the player predicate (TN-3 — the correction that prevents a real deletion bug), treat `opponent_links` / `user_team_access`-referenced teams as excluded roots (TN-7), and carry the reap-then-gate concurrency guard inside itself so no caller can forget it (TN-5). The invariant-count helper is the single source of the orphan queries consumed by E-273-04 and E-273-05 (TN-8).

## Acceptance Criteria
- [ ] **AC-1**: Given a set of `tracked` orphan teams (no `reports` row, no `games` row) and their roster/scouting/team-scoped rows, when `reclaim_orphan_reference_data(conn)` runs, then those teams and their team-scoped pins (`team_rosters`, `scouting_runs`, `crawl_jobs`, `coaching_assignments`, `scheduled_report_runs`) are deleted and the returned `ReclaimResult` reports the counts, per TN-1/TN-2/TN-4.
- [ ] **AC-2**: Given a SYNTHETICALLY-constructed team referenced ONLY via a surviving game's `perspective_team_id` / `team_id` / `plays.batting_team_id` stat row — never via `home_team_id`/`away_team_id` (a state the real loader cannot produce; construct it by inserting a stat row with a non-participant perspective) — when the pass runs, then (a) that team is NOT reclaimed, and (b) a WARNING is logged naming the team id + the referencing table ("excluded from reclamation despite no games — possible orphaned stat row, operator backfill"). The belt-and-suspenders clause spans `team_id`+`perspective_team_id` on `player_game_batting`/`player_game_pitching`/`spray_charts`/`reconciliation_discrepancies` and `batting_team_id`+`perspective_team_id` on `plays`, lives INSIDE `_orphan_team_ids`, and is vacuously true on real data. Per TN-2.
- [ ] **AC-3**: Given a `member` team with zero reports and zero games, when the pass runs, then it is NOT reclaimed (member teams are never orphans, TN-2).
- [ ] **AC-4**: Given three seeded survivors — (a) a tracked orphan-candidate team as an `opponent_links.resolved_team_id` target, (b) a tracked orphan-candidate team as an `opponent_links.our_team_id` owner (a SYNTHETIC shape — by convention `our_team_id` is a member team; constructed like AC-2 so the `our_team_id`-root exclusion is proven to fire IN ISOLATION, which a member fixture could not, since tracked-scoping would mask which mechanism saved it), and (c) a team carrying a `user_team_access` grant — when the pass runs, then NONE of those teams is reclaimed, NO `opponent_links` row is deleted, NO `resolved_team_id` is NULLed, and NO `user_team_access` grant is deleted, per TN-7. All three survivors MUST be seeded and asserted — each of the three destructive columns has its OWN explicit root-exclusion (Option B: `resolved_team_id`-root, `our_team_id`-root, `user_team_access`-root), so a test seeding only the `resolved_team_id` shape leaves the other two exclusions untested.
- [ ] **AC-5**: Given orphan players — including a player reachable ONLY via `plays.batter_id` or `plays.pitcher_id` — when the pass runs AFTER the team tier, then all orphan players (no roster-of-a-surviving-team and no stat rows across `player_game_batting`/`player_game_pitching`/`plays`/`spray_charts`) are deleted, and the plays-only player is NOT falsely deleted while genuinely-orphan players ARE, per TN-3.
- [ ] **AC-6**: Given orphan teams whose deleted rosters transitively orphan ~N roster-only players, when the pass runs, then those players are reclaimed in the same invocation (the player tier reads post-team-deletion roster state; the two-phase fixed point of TN-1). A terminate-after-zero-delta self-assertion confirms no third pass deletes anything.
- [ ] **AC-7**: Given a live `generating` report exists, when the pass runs, then it REFUSES (no deletions) after first calling `reap_stale_generating_reports`, and returns a `ReclaimResult` with `deferred=True`; given no live generating report remains after the reap, the pass proceeds and returns `deferred=False`. The gate-check, the orphan-set compute, and the DELETEs run in ONE transaction on ONE connection — the pass takes `conn` and OWNS the full `BEGIN…COMMIT` internally (the named exception to caller-owns-the-transaction; NOT caller-owns-no-commit); a test proves a generation committing an opponent stub on another connection MID-sweep does not lose that stub (the TOCTOU regression). Per TN-5.
- [ ] **AC-8**: The pass's DELETE targeting AND the invariant COUNT derive from ONE shared id-set source — `_orphan_team_ids(conn)` and `_orphan_player_ids(conn)` — so the delete-set and the count cannot drift; `count_orphan_reference_data(conn)` returns the three counts as `len()` of those same sets plus the orphan-held roster-row count, INCLUDING the `plays` predicate and the roots exclusion by construction. Unit tests cover each of the three predicates and the exclude-roots logic. Per TN-8.
- [ ] **AC-9**: The two behavior-pinning tests `test_cascade_delete_team_preserves_games_row_when_other_perspective_remains` and `test_cascade_delete_team_drops_games_row_when_last_perspective` remain GREEN (the pass is additive; it does not modify `cascade_delete_team`), per TN-4.
- [ ] **AC-10**: The two-phase ordering runs within the single transaction per TN-1 — `_orphan_team_ids` is read PRE-delete (same point as the gate), the team tier is deleted, THEN `_orphan_player_ids` is read POST-team-delete (so transitively-orphaned roster-only players fall out). A test confirms a player orphaned ONLY by a deleted orphan team's roster is reclaimed in the same invocation (not missed by an up-front snapshot).

## Technical Approach
Implement `reclaim_orphan_reference_data(conn) -> ReclaimResult`, the shared id-set producers `_orphan_team_ids(conn)` / `_orphan_player_ids(conn)`, and `count_orphan_reference_data(conn) -> OrphanCounts` in `src/reports/lifecycle.py` (the client-free seam per TN-4). Follow TN-8 (the pass's DELETE targeting and the COUNT both derive from the shared producers — never two hand-written copies), TN-1 (single transaction with the pre-delete team read → team delete → post-team-delete player read → player delete ordering; single transaction YES, single up-front snapshot NO), TN-2 (orphan-team predicate: tracked-only, no `is_active`, belt-and-suspenders stat clause INSIDE `_orphan_team_ids` with WARN-on-fire), TN-3 (orphan-player predicate INCLUDING `plays` batter+pitcher), TN-5 (reap-then-gate guard inside the pass; the pass takes `conn` and OWNS the transaction — gate-check + compute + deletes in one transaction; `ReclaimResult.deferred` on refusal), and TN-7 (exclude the `opponent_links`/`user_team_access` roots).

**Reuse vs tailored (TN-4, binding guardrail):** RECOMMENDED — a TAILORED team-tier cleanup that deletes only the innocuous pins (`team_rosters`, `scouting_runs`, `crawl_jobs`, `coaching_assignments`, `scheduled_report_runs`) and the team row, never touching `opponent_links`/`user_team_access` (mild preference — CLEANER, not safer). Reusing `_delete_team_scoped_data` WHOLESALE is EQUALLY SAFE under Option B: the predicate excludes all three destructive-column roots (`resolved_team_id`, `our_team_id`, `user_team_access`), so its `opponent_links`/`user_team_access` clauses no-op (AC-4's three-column guard test verifies this). Either way you MUST NOT modify `_delete_team_scoped_data` to skip clauses — it is shared with `cascade_delete_team` + `cleanup_orphan_teams` and editing it breaks those live paths. `_delete_team_scoped_data` does NOT touch `players`; the player tier is separate.

**SQLite (TN-8):** use a correlated `NOT EXISTS (SELECT 1 FROM teams ot WHERE ot.id = r.team_id AND <orphan-team predicate>)` for the surviving-team test, not a Python-materialized `NOT IN (:ids)` (the orphan set can exceed SQLite's 999-variable limit; the correlated form also keeps ONE predicate). `player_id` is TEXT. Do NOT re-inline orphan queries anywhere but the producers. See `/workspaces/baseball-crawl/orphaned-reference-data-handoff.md` §7.4/§13/§15 for the problem framing and `.claude/rules/data-model.md` for the FK/perspective semantics.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-273-02 (wiring), E-273-04 (batch test consumes the helper), E-273-05 (one-shot consumes the pass + helper)

## Files to Create or Modify
- `src/reports/lifecycle.py` (add `reclaim_orphan_reference_data`, `_orphan_team_ids`, `_orphan_player_ids`, `ReclaimResult` (with the `deferred` field), `OrphanCounts`, `count_orphan_reference_data`)
- `tests/test_orphan_reclamation.py` (NEW dedicated file — unit tests for the pass, the three predicates, exclude-roots, belt-and-suspenders + WARN, the single-transaction/TOCTOU regression, and deferral. A new file avoids the shared-file collision with stories 02/03/04 per TN-15. Do NOT edit `tests/test_report_generator.py`; run test-scope discovery for `src/reports/lifecycle.py` per `.claude/rules/testing.md` so the existing cascade/cleanup tests there run as a no-regression check for AC-9, without modifying that file.)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-273-02**: `reclaim_orphan_reference_data(conn)` for wiring into the deletion paths.
- **Produces for E-273-04**: the single-source invariant-count helper the batch test asserts against.
- **Produces for E-273-05**: the pass + helper the one-shot imports and calls.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (unit-level per-predicate + exclude-roots coverage, not just an integration test)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests (run test-scope discovery for `src/reports/lifecycle.py`)

## Notes
The `plays` inclusion in the player predicate (TN-3/AC-5) is the single correction most likely to prevent a real deletion bug — a plays-only stub falsely counted dead. Do not drop it during refactoring.
