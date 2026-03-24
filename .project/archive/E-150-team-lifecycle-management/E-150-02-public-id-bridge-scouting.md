# E-150-02: Public ID Bridge Resolution in Scouting

## Epic
[E-150: Team Lifecycle Management](epic.md)

## Status
`DONE`

## Description
After this story is complete, the scouting pipeline will attempt to resolve `public_id` for opponents that have `gc_uuid` but no `public_id` before filtering them out. Opponents whose `public_id` is successfully resolved via the forward bridge are written to the database and included in the scouting run. Opponents where resolution fails (403) are logged with a clear warning so the operator knows which need manual attention.

## Context
`scout_all()` in `src/gamechanger/crawlers/scouting.py` queries `opponent_links WHERE public_id IS NOT NULL`, silently skipping opponents that only have a gc_uuid. The forward bridge function (`resolve_uuid_to_public_id` in `src/gamechanger/bridge.py`) can resolve UUIDs to public_id slugs but returns 403 for teams not on the authenticated account. This story wires the bridge as a best-effort enrichment step: it will work for any opponents that happen to be on the user's account and gracefully skip the rest with clear logging.

## Acceptance Criteria
- [ ] **AC-1**: Given an opponent in `opponent_links` whose resolved team has `teams.gc_uuid IS NOT NULL` and `opponent_links.public_id IS NULL`, when `bb data scout` runs (without `--team`), then the bridge resolution step attempts to resolve the public_id via `resolve_uuid_to_public_id` before the main scouting query executes.
- [ ] **AC-2**: Given a successful bridge resolution (no 403) and no existing teams row with the resolved public_id, when the public_id is returned, then both `teams.public_id` and `opponent_links.public_id` are updated in the database for that opponent (teams row first to prevent duplicate row creation by `_ensure_team_row`), along with `opponent_links.resolved_at` and `opponent_links.resolution_method = 'bridge'`, and the opponent is no longer filtered out by `scout_all()` for missing public_id.
- [ ] **AC-3**: Given a `BridgeForbiddenError` (403) from the bridge, then the opponent is skipped with a WARNING-level log message that includes the opponent's `teams.gc_uuid` and `teams.name`, and scouting continues for remaining opponents.
- [ ] **AC-4**: Given a `CredentialExpiredError` or `ConfigurationError` from the bridge, then the entire bridge resolution step is aborted with a WARNING-level log (not the full scouting run -- scouting proceeds with whatever public_ids are already populated), and the error is logged.
- [ ] **AC-5**: Given no opponents have `teams.gc_uuid IS NOT NULL` with `opponent_links.public_id IS NULL`, then the bridge resolution step is a no-op (no API calls made, no log noise).
- [ ] **AC-6**: Tests verify the bridge resolution step: successful resolution updates both `teams.public_id` and `opponent_links.public_id` (plus `resolved_at` and `resolution_method`), 403 is handled gracefully, credential errors abort bridge step but not scouting, no-op case produces no API calls, and UNIQUE constraint collision (existing stub row with same public_id) skips the update with a WARNING log that includes gc_uuid, resolved public_id, and conflicting teams.id, and does not modify either table for that opponent.

## Technical Approach
Add a pre-step in the scouting pipeline (before the main `scout_all()` query) that queries for opponents needing resolution, calls the bridge for each, and writes successful results to the database. The pre-step should be a separate function callable from the CLI path (`_scout_live` / `_run_scout_pipeline`). The bridge is called per-opponent with individual error handling so one failure doesn't block others.

The candidate query joins `opponent_links` to `teams` via `resolved_team_id` to access `teams.gc_uuid`, using `DISTINCT` on `resolved_team_id` to avoid redundant bridge API calls for opponents tracked by multiple member teams (note: `opponent_links` has no `gc_uuid` column; `root_team_id` is a GC internal registry key, NOT a canonical UUID).

On success, update both tables: `teams.public_id` first (to prevent `_ensure_team_row` from creating a duplicate team row), then `opponent_links.public_id` plus `resolved_at` and `resolution_method` columns keyed on `resolved_team_id`. If the `teams.public_id` update would violate the partial unique index (another teams row already has that public_id), skip the update for this opponent per TN-3 (log WARNING, do not update `opponent_links`, continue to next candidate).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/crawlers/scouting.py` -- add bridge resolution pre-step function, call it before `scout_all()`
- `src/cli/data.py` -- wire bridge resolution into `_scout_live()` before crawler call
- `tests/test_scouting_bridge_resolution.py` -- new test file for bridge resolution logic

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The forward bridge returns 403 for opponent teams not on the authenticated account (confirmed by reading `src/gamechanger/bridge.py`). This is expected behavior, not a bug. The story handles it gracefully.
- CLAUDE.md describes the bridge as working for "any team UUID" -- this is misleading. A CLAUDE.md correction is out of scope for this epic but should be tracked.
- The `gc_uuid` lives on the `teams` table, NOT on `opponent_links`. The join path is `opponent_links.resolved_team_id -> teams.id -> teams.gc_uuid`. The `opponent_links.root_team_id` column is a GC internal registry key, not a canonical UUID -- it must NOT be used for bridge calls.
