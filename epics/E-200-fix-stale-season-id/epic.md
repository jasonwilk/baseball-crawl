# E-200: Fix Stale season_id on Pre-Existing Games

## Status
`READY`

## Overview
Fix a bug where `_upsert_game` in `game_loader.py` omits `season_id` from its ON CONFLICT UPDATE clause, leaving pre-existing game rows with stale suffixed season_ids (e.g., `"2026-spring-hs"` instead of `"2026"`). This causes season aggregate queries to return zero rows for ~200+ opponent teams, making reports and dashboard scouting show "No data available."

## Background & Context
E-197 introduced `derive_season_id_for_team()` which correctly produces year-only season_ids (e.g., `"2026"`) for teams without a `program_id`. However, the `_upsert_game` method's ON CONFLICT clause was not updated to include `season_id` in the SET list. When games that were previously loaded with the old suffixed season_id (`"2026-spring-hs"`) are re-upserted, the season_id column retains the stale value. Downstream, `_compute_season_aggregates` joins on the new derived season_id but games still carry the old value, producing empty joins and zero aggregate stats.

Team 104 was manually hotfixed. All other affected teams (~200+ auto-created opponent stubs without `program_id`) still have stale data.

No expert consultation required -- this is a pure code bug with a well-defined data correction.

## Goals
- Ensure `_upsert_game` updates `season_id` on conflict so future re-syncs correct stale values
- Correct all existing stale season_ids across all affected tables via a data migration
- Restore opponent batting, pitching, and spray chart data visibility in reports and dashboards

## Non-Goals
- Changing how `derive_season_id_for_team()` works (it is correct)
- Fixing teams that DO have a `program_id` (their suffixed season_ids are intentional)
- Backfilling any other missing data beyond season_id correction
- Auditing other loaders' ON CONFLICT clauses for similar omissions (separate investigation if needed)

## Success Criteria
- Re-syncing any affected team produces correct season aggregates (non-zero rows)
- Migration 013 is idempotent -- safe to re-run with no side effects
- All pre-existing games for teams without `program_id` have year-only season_ids after migration

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-200-01 | Add season_id to _upsert_game ON CONFLICT clause | TODO | None | - |
| E-200-02 | Migration 013: correct stale season_ids across all tables | TODO | E-200-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Affected Tables and Correction Logic
For each team where `program_id IS NULL`, the correct season_id is `str(season_year)` (or `str(current_year)` if `season_year` is also NULL). The following tables need correction:

1. **seasons** -- INSERT OR IGNORE year-only season rows as FK prerequisites
2. **games** -- `season_id` column (FK to seasons)
3. **plays** -- `season_id` column; no `team_id` -- join through `games` to identify affected rows
4. **player_season_batting** -- `season_id` is part of the composite PK `(player_id, team_id, season_id)`
5. **player_season_pitching** -- `season_id` is part of the composite PK `(player_id, team_id, season_id)`
6. **team_rosters** -- `season_id` is part of the composite PK; may have duplicate rows (both old and new season_id for the same player+team). Deduplicate by DELETE-ing the old-season_id row when a new-season_id row already exists.
7. **spray_charts** -- `season_id` column (nullable; added via ALTER TABLE in migration 006 with no FK constraint -- INSERT OR IGNORE season rows is unnecessary for this table but harmless)

### TN-2: Migration Idempotency
All UPDATEs scope on the OLD suffixed value in the WHERE clause (e.g., `WHERE season_id LIKE '%-spring-hs' OR season_id LIKE '%-summer-%'`). After the first successful run, these WHERE clauses match zero rows -- safe to re-run. Team 104 was already hotfixed and will not be affected (its rows already have the correct season_id).

### TN-3: Composite-PK Table Deduplication
Three tables have uniqueness constraints on `(player_id, team_id, season_id)`: `team_rosters` (PRIMARY KEY), `player_season_batting` (UNIQUE), and `player_season_pitching` (UNIQUE). If a team was re-synced after E-197, rows with the NEW year-only season_id may already exist alongside rows with the OLD suffixed season_id. A plain UPDATE on these tables would hit a UNIQUE constraint violation.

**Strategy**: For each of the three tables, DELETE old-season_id rows where a new-season_id row already exists for the same `(player_id, team_id)`, THEN UPDATE remaining old-season_id rows (those without a new counterpart). The new-season_id row (from re-loading after E-197) is authoritative.

**Pattern** (apply to each of the three tables):
```sql
-- Step A: DELETE old rows that have a new counterpart
DELETE FROM <table>
WHERE rowid IN (
  SELECT old.rowid FROM <table> old
  INNER JOIN <table> new_row
    ON old.player_id = new_row.player_id
    AND old.team_id = new_row.team_id
    AND new_row.season_id = <correct_season_id>
  WHERE old.season_id = <stale_season_id>
    AND old.team_id IN (<affected_teams>)
);

-- Step B: UPDATE remaining old rows (no new counterpart exists)
UPDATE <table>
SET season_id = <correct_season_id>
WHERE season_id = <stale_season_id>
  AND team_id IN (<affected_teams>);
```

### TN-4: Migration Pattern Reference
See `migrations/011_fix_season_id_rebels_14u.sql` for the established pattern: PRAGMA foreign_keys=ON first, INSERT OR IGNORE season rows, then UPDATE each table scoped by old season_id in WHERE.

### TN-5: Scope of Affected Teams
Affected teams: all rows in `teams` where `program_id IS NULL`. These are predominantly auto-created opponent stubs. The migration should dynamically identify them rather than hardcoding team IDs.

## Open Questions
- None -- the bug, fix, and migration scope are well-defined.

## History
- 2026-04-02: Created
- 2026-04-02: Set to READY after 2 review iterations (6 unique findings accepted, 0 dismissed)

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 5 | 5 | 0 |
| Internal iteration 1 — Holistic team (PM + SE) | 4 | 4 | 0 |
| **Total (deduplicated)** | **6** | **6** | **0** |

Note: CR findings 1/5 overlapped with PM-1/SE-1 (composite-PK dedup). Total unique findings: 6 accepted + 1 context-layer note (stale migrations.md numbering — not counted, not blocking).
