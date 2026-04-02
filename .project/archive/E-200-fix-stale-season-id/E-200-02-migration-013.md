# E-200-02: Migration 013 — Correct Stale season_ids Across All Tables

## Epic
[E-200: Fix Stale season_id on Pre-Existing Games](epic.md)

## Status
`DONE`

## Description
After this story is complete, migration 013 will correct all stale suffixed season_ids (e.g., `"2026-spring-hs"`) to year-only values (e.g., `"2026"`) for teams without a `program_id`. This restores season aggregate joins so that opponent batting, pitching, and spray chart data becomes visible again in reports and dashboards.

## Context
E-197 changed season_id derivation to produce year-only values for teams without `program_id`, but ~200+ pre-existing opponent stub teams still have rows with old suffixed season_ids. Season aggregate queries join on the new derived season_id and find zero matching game/stat rows. This migration corrects the historical data to match the new derivation logic.

## Acceptance Criteria
- [ ] **AC-1**: Migration file exists at `/workspaces/baseball-crawl/migrations/013_fix_stale_season_ids.sql`.
- [ ] **AC-2**: Migration begins with `PRAGMA foreign_keys=ON;` per TN-4 in the epic Technical Notes.
- [ ] **AC-3**: Migration creates year-only season rows (`INSERT OR IGNORE`) as FK prerequisites before any UPDATEs.
- [ ] **AC-4**: Migration creates year-only season prerequisite rows (`INSERT OR IGNORE`) and corrects `season_id` in all six data tables listed in TN-1: games, plays, player_season_batting, player_season_pitching, team_rosters, and spray_charts.
- [ ] **AC-5**: Migration handles composite-PK deduplication per TN-3 for all three affected tables (`team_rosters`, `player_season_batting`, `player_season_pitching`): when both old and new season_id rows exist for the same `(player_id, team_id)`, the old row is deleted before the UPDATE runs. This prevents UNIQUE constraint violations.
- [ ] **AC-6**: Migration dynamically identifies affected teams (`program_id IS NULL`) per TN-5 -- no hardcoded team IDs.
- [ ] **AC-7**: Migration is idempotent per TN-2 -- all UPDATEs scope on the old suffixed value in WHERE clauses. Safe to re-run.
- [ ] **AC-8**: Migration does not affect teams that have a `program_id` (their suffixed season_ids are intentional).
- [ ] **AC-9**: Team 104 (already hotfixed) is unaffected -- its rows already have the correct season_id, so WHERE clauses match zero rows for it.

## Technical Approach
Follow the pattern in `migrations/011_fix_season_id_rebels_14u.sql` but generalized: instead of targeting a single team, target all teams where `program_id IS NULL`. For each such team, the correct season_id is `CAST(COALESCE(season_year, strftime('%Y', 'now')) AS TEXT)`. Use subqueries to dynamically build the affected-team set and derive the correct season_id per team. Process tables in dependency order: seasons (prerequisites) → games → plays (joins through games) → stat tables → team_rosters (with dedup) → spray_charts.

## Dependencies
- **Blocked by**: E-200-01 (code fix must ship before migration to prevent re-syncs from re-introducing stale values)
- **Blocks**: None

## Files to Create or Modify
- `/workspaces/baseball-crawl/migrations/013_fix_stale_season_ids.sql` — new migration file

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Migration file follows project conventions per `/.claude/rules/migrations.md`
- [ ] No regressions in existing tests

## Notes
- The migration is SQL-only (no Python). Testing is best done by verifying the SQL is syntactically valid and that the migration file follows conventions.
- Unlike migration 011 which targeted a single team with known IDs, this migration must work dynamically across all teams without `program_id`. The key challenge is that each team may have a different old season_id and a different correct season_id (based on its `season_year`).
- `scouting_runs.season_id` is NOT updated -- it is a file-discovery column per CLAUDE.md (filesystem vs DB season_id decoupling).
