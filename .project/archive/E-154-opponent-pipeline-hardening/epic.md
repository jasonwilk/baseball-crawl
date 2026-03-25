# E-154: Opponent Resolution Pipeline Hardening

## Status
`COMPLETED`

## Overview
Fix the critical data-flow break in the opponent discovery → resolution → scouting pipeline where `OpponentResolver._ensure_opponent_team_row()` writes `gc_uuid` to the `teams` table but never writes `public_id`, even though `public_id` is available from the same API call. This causes admin UI scouting to fail for auto-resolved opponents and leaves dead bridge-resolution code that can never succeed for opponent teams.

## Background & Context
Discovered 2026-03-25 while investigating why tracked opponent teams had `teams.public_id = NULL` despite being auto-resolved. The resolver correctly stores `public_id` in `opponent_links` but omits it from the `teams` row. The downstream `resolve_missing_public_ids` method was designed to backfill this gap via the bridge endpoint (`GET /teams/{gc_uuid}/public-team-profile-id`), but the bridge returns 403 for non-managed teams — confirmed by api-scout. This makes the bridge resolution permanently dead code for opponent teams.

Two scouting paths exist with different `public_id` sources:
- **CLI** (`bb data scout` → `scout_all()`): Queries `opponent_links.public_id` — works because the resolver writes `public_id` there.
- **Admin UI** (`POST /admin/teams/{id}/sync` → `run_scouting_sync()`): Reads `teams.public_id` — **broken** because it's NULL.

DB state observed 2026-03-25 (Standing Bear Freshman Grizzlies, team_id=89): 25 opponent_links rows, 6 resolved with `public_id` in `opponent_links` but NULL in `teams`, 19 unresolved (no progenitor_team_id). Manual SQL fix was applied to copy `public_id` to `teams` for the 6 resolved opponents.

Expert consultation: api-scout confirmed `public_id` is NOT nullable in the GC team detail spec. The `GET /teams/{progenitor_team_id}` response also includes `season_year` and other fields capturable at zero extra API cost. DE recommended `teams.public_id` as single source of truth with a backfill migration to document healing intent.

## Goals
- Auto-resolved opponents have `teams.public_id` populated immediately upon resolution
- Admin UI scouting works for all resolved opponents (no NULL `public_id` gap)
- Dead bridge-resolution code is removed from the scouting pipeline
- Existing data inconsistencies are healed via idempotent migration
- `season_year` is opportunistically captured from the team detail API response during resolution

## Non-Goals
- Resolving null-progenitor opponents (`resolve_unlinked` flow) — E-146 domain, experimental
- Normalizing `opponent_links.public_id` away (schema refactor) — future consideration
- Capturing `competition_level`/`age_group` from the API — nice-to-have but not load-bearing
- Functional/behavioral changes to the scouting crawler or loader — those stages work correctly (dead code removal in E-154-02 is cleanup, not a behavioral change)
- Admin UI changes beyond what's needed for correct data flow
- Removing `_heal_season_year_scouting` from `trigger.py` — it is still needed for tracked teams scouted via admin UI before opponent resolution runs (resolution happens during member sync, not scouting sync)

## Success Criteria
- Running `OpponentResolver.resolve()` populates both `opponent_links.public_id` AND `teams.public_id` for auto-resolved opponents
- Admin UI sync button successfully triggers scouting for resolved opponents
- `resolve_missing_public_ids` method and its call site are removed
- A migration backfills `teams.public_id` from `opponent_links.public_id` for any existing resolved opponents missing it
- No regressions in existing pipeline tests

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-154-01 | Fix resolver to write public_id and season_year to teams | DONE | None | - |
| E-154-02 | Remove dead resolve_missing_public_ids bridge code | DONE | None | - |
| E-154-03 | Backfill migration for teams.public_id | DONE | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: `_ensure_opponent_team_row` signature change
The method currently accepts `(gc_uuid, team_name)`. It needs to also accept `public_id` and `season_year` from the team detail API response. Two code paths must both include the new columns:

- **New row (INSERT succeeds, `cursor.rowcount > 0`)**: The INSERT column list must include `public_id` and `season_year` alongside the existing `name`, `membership_type`, `gc_uuid`, `is_active`.
- **Existing row (INSERT OR IGNORE fires, SELECT fallback)**: UPDATE `public_id` and `season_year` only when the existing row has NULL values for those columns. If the existing row already has a non-NULL `public_id` (whether matching or different from the fetched value), preserve it unchanged. This "only write when NULL" pattern matches the existing UUID-stub name logic (line 381: `if existing_name == gc_uuid`).

### TN-2: UNIQUE collision handling for teams.public_id
`teams.public_id` has a UNIQUE constraint. When writing `public_id` to a team row matched by `gc_uuid`, check first whether another `teams` row already has that `public_id`. If so, this indicates a duplicate team row (likely one created by the admin UI add-team flow before resolution linked it). Log a WARNING with both team IDs and skip the `public_id` write for that opponent — manual row reconciliation is needed.

### TN-3: Defensive public_id extraction
Replace `team_data["public_id"]` with `team_data.get("public_id")` and add a null check. If `public_id` is None/missing, log a WARNING and continue resolution without `public_id` — the opponent gets a `teams` row with `gc_uuid` only, and `opponent_links` gets no `public_id`. This is a partial resolve, better than crashing.

### TN-4: Backfill migration SQL
Idempotent UPDATE query per DE recommendation, with UNIQUE collision guard and deterministic ordering:
```sql
UPDATE teams SET public_id = (
    SELECT ol.public_id FROM opponent_links ol
    WHERE ol.resolved_team_id = teams.id
      AND ol.public_id IS NOT NULL
    ORDER BY ol.resolved_at DESC, ol.id DESC
    LIMIT 1
)
WHERE public_id IS NULL
  AND id IN (
    SELECT resolved_team_id FROM opponent_links
    WHERE public_id IS NOT NULL
  )
  AND (
    SELECT ol2.public_id FROM opponent_links ol2
    WHERE ol2.resolved_team_id = teams.id
      AND ol2.public_id IS NOT NULL
    ORDER BY ol2.resolved_at DESC, ol2.id DESC
    LIMIT 1
  ) NOT IN (
    SELECT t2.public_id FROM teams t2
    WHERE t2.public_id IS NOT NULL
  );
```
The final clause prevents UNIQUE constraint violations by skipping rows where the target `public_id` already exists on a different `teams` row. The `ORDER BY ol.resolved_at DESC, ol.id DESC` ensures deterministic selection when multiple `opponent_links` rows point to the same team (the `id` tiebreaker handles rows with NULL `resolved_at`). This heals any existing data and is safe to re-run. Next available migration number must be determined at implementation time by checking existing migration files.

### TN-5: resolve_missing_public_ids removal scope
Remove from `src/gamechanger/crawlers/scouting.py`:
- The `resolve_missing_public_ids` method
- The imports it uses: `BridgeForbiddenError`, `resolve_uuid_to_public_id` from `src.gamechanger.bridge`, and `ConfigurationError` from the client (verify these aren't used elsewhere in the file first)

Remove from `src/cli/data.py`:
- The `crawler.resolve_missing_public_ids()` call

Remove/update tests:
- `tests/test_scouting_bridge_resolution.py` — entire file is dedicated to this method
- `tests/test_cli_scout.py` — remove the `resolve_missing_public_ids` assertion

## Open Questions
None remaining — all resolved during discovery.

## History
- 2026-03-25: Created from discovery of teams.public_id NULL bug in opponent resolution pipeline
- 2026-03-25: Set to READY after 4 review passes (2 internal, 2 Codex)

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 4 | 4 | 0 |
| Internal iteration 1 — Holistic team (PM+SE+DE) | 6 | 5 | 1 |
| Internal iteration 2 — CR spec audit | 2 | 2 | 0 |
| Internal iteration 2 — PM self-review | 2 | 2 | 0 |
| Codex iteration 1 | 5 | 3 | 2 |
| Codex iteration 2 | 1 | 0 | 1 |
| **Total** | **20** | **16** | **4** |

Key dismissed findings: DE-2 (E-154-02 dependency on E-154-01 — bridge was already non-functional), Codex-3 (admin integration AC — AC-1 already covers the data contract), Codex-4 (routing mismatch — trivial migration doesn't warrant DE agent), Codex-4 repeat (iteration 2).

- 2026-03-25: All 3 stories DONE. Implementation dispatch complete.
- 2026-03-25: COMPLETED after implementation review chain (4 CR passes + 4 Codex passes).

### Implementation Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR — E-154-01 (2 rounds) | 2 | 2 | 0 |
| Per-story CR — E-154-02 (2 rounds) | 1 | 1 | 0 |
| Per-story CR — E-154-03 | 0 | 0 | 0 |
| CR integration review | 0 | 0 | 0 |
| PM holistic review | 0 | 0 | 0 |
| CR second pass | 0 | 0 | 0 |
| Codex iteration 1 | 3 | 2 | 1 |
| Codex iteration 2 | 1 | 1 | 0 |
| Codex iteration 3 | 1 | 1 | 0 |
| Thorough CR review | 1 | 1 | 0 |
| Codex iteration 4 | 2 | 0 | 2 |
| **Total** | **11** | **8** | **3** |

Key findings: Per-story CR caught test scope gaps and new-row INSERT collision path. Codex iteration 1 caught cross-story data integrity bug (collision-skipped public_id still written to opponent_links). Codex iteration 2 caught migration batch-duplicate UNIQUE violation. Codex iteration 3 caught wrong fix (arbitrary MIN(id) assignment). Thorough CR confirmed all fixes correct. Codex iteration 4 clean (only worktree artifacts and low-severity test hardening).

### Documentation Assessment
No documentation impact — no new user-facing features, no API changes, no new CLI commands.

### Context-Layer Assessment
- New agent capabilities or tools: No
- New rules or conventions: No
- New skills or workflows: No
- CLAUDE.md updates needed: No — describes pipeline at correct abstraction level
- Agent memory updates needed: Yes — PM memory updated separately
- Hook changes: No
