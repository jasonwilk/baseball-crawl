# IDEA-057: Eliminate Orphan Team Stubs from Report Generation Flow

## Status
`CANDIDATE`

## Summary
The report generation flow creates orphan team rows for every opponent encountered in boxscores. A report for a team with 56 games creates ~30 stub team rows named with UUIDs (e.g., `521a249b-528c-4db5-b43d-ec893b07ad02`). These stubs serve the opponent scouting flow but are unnecessary noise for standalone reports.

## Why It Matters
- **Data hygiene**: The teams table accumulates junk rows (UUID-named stubs with no public_id, no human-readable name, no purpose in the reports context). Lincoln Sox 12U report created ~30 orphan teams. Each new report adds more.
- **Confusion risk**: These stubs can interfere with `ensure_team_row` name matching for future operations. The North Star Reserve report (team 35) was a case where a prior stub's gc_uuid (from a stale GC registration) caused 404s on the spray endpoint because `ensure_team_row` matched on name to the wrong team row.
- **No value for reports**: The report flow uses game rows for W/L record and recent form, but the opponent team identity is cosmetic (opponent name in recent-form display). The full opponent team row with gc_uuid is not needed.

## Root Cause Analysis

Two code paths create the stubs during report generation:

1. **GameLoader._ensure_team_row()** (`src/gamechanger/loaders/game_loader.py:1160`): Called for every boxscore to create `games` rows. The `games` table requires `home_team_id` and `away_team_id` as FK references to `teams(id)`. The GameLoader must have a team row for both teams to insert the game row.

2. **ScoutingLoader._record_uuid_from_boxscore_path()** (`src/gamechanger/loaders/scouting_loader.py:523`): A "safety net" that iterates UUID keys in every boxscore and calls `ensure_team_row`. Docstring says "The GameLoader already creates stubs during load_file(), so this is a safety net."

Both are called from `ScoutingLoader._load_boxscores()` (line 200-222), which runs during `ScoutingLoader.load_team()` -- the same method used by both the opponent scouting flow and the report generator flow.

The report generator calls `ScoutingLoader.load_team()` at `src/reports/generator.py:527`. There's no way to tell the loader "don't create opponent team rows" -- the FK constraints on the `games` table force it.

## Possible Fix Approaches

**Approach A: Report-specific lightweight loader**
Create a `ReportLoader` that extracts only what the report needs (batting/pitching aggregates, roster, spray charts) without creating game rows or opponent team stubs. The report's W/L record and recent form could be computed directly from boxscore data without the `games` table intermediary.
- Pro: Cleanest separation, zero orphan stubs
- Con: Duplicates extraction logic, two code paths to maintain

**Approach B: Conditional stub creation flag**
Add a parameter to `ScoutingLoader.load_team()` (e.g., `create_opponent_teams=True`) that, when False, skips the `_record_uuid_from_boxscore_path` call and passes a flag to `GameLoader` to skip opponent team creation. Game rows would use a sentinel value or NULL for the opponent team_id.
- Pro: Minimal code change, reuses existing loader
- Con: Requires schema relaxation (nullable FK or sentinel team), and game rows without real opponent IDs are partially useful

**Approach C: Accept stubs, add cleanup**
Keep creating stubs but add a cleanup step that deletes team rows created by the report flow that have no `opponent_links`, no scouting data, and no reports pointing to them. Run as a post-report-generation cleanup or a periodic maintenance task.
- Pro: Zero loader changes
- Con: Doesn't prevent the North Star name-collision problem, just cleans up after it

**Approach D: Report flow bypasses game table entirely**
Compute W/L record and recent form directly from boxscore JSON files instead of loading into the `games` table. The report generator already has the boxscore files on disk after the scouting crawl. Parse them directly for scores and dates.
- Pro: No DB writes for game rows = no opponent FK requirement = no stubs
- Con: Duplicates score extraction logic that `GameLoader` already handles

## Related Issues

### North Star Reserve team identity mismatch (E-186 evaluation)
Team 35 ("Lincoln North Star Reserve 26'") was created by the opponent scouting flow with `gc_uuid=822cc0a7` (a stale GC registration with 0 games). When the user generated a report for `public_id=LHIYRnPoo8DC` (correct gc_uuid `dc590640`), `ensure_team_row` matched by name to team 35. The wrong gc_uuid caused all spray endpoint calls to 404. The report generator doesn't backfill `public_id` onto name-matched teams, and E-186-02's `_resolve_gc_uuid` skips when an existing gc_uuid is present (even if it's wrong).

This is a symptom of the same underlying problem: stubs created in one flow pollute the teams table for another flow.

### Lincoln Sox stale spray files (E-186 evaluation)
The E-176 broken fallback created spray files with opponent UUIDs. These files block re-crawling with the correct UUID. One-time manual cleanup (`rm -rf data/raw/2025-spring-hs/scouting/0kfqCjpbDcSH/spray/`). Not directly related to stubs, but part of the same "prior flow pollution" pattern.

## Scope If Promoted

An epic from this idea would likely include:
- A story to decouple the report flow from opponent team stub creation (whichever approach is chosen)
- A story to address the gc_uuid mismatch problem (generator should validate/update gc_uuid when it doesn't match the public_id's search result)
- A story to backfill public_id onto the team row when the generator has it but the row doesn't
- A cleanup story for existing orphan stubs (SQL cleanup of UUID-named teams with no links)
- Probably 4-5 stories total

## Dependencies & Blockers
- [x] E-186 (spray chart fix) -- complete
- [x] E-187 (threshold calibration) -- in progress, no conflict
- [ ] Decision on approach (A/B/C/D) -- requires SE + PM consultation

## Open Questions
- Is the `games` table even needed for reports? The report queries `_query_record()`, `_query_recent_games()`, `_query_freshness()` -- all join the `games` table. Could these be computed from boxscore JSON directly?
- Should the generator validate gc_uuid against POST /search even when one already exists? This would catch the North Star case but adds an API call per report.
- How many orphan stubs exist currently? (Quick audit: `SELECT COUNT(*) FROM teams WHERE name LIKE '%-%-%-%-%' AND source = 'scouting'`)

## Notes
- The opponent scouting flow (dashboard) legitimately needs these team rows. Any fix must not break `bb data scout` or the admin opponent resolution workflow.
- Vision signal 2026-03-25 ("combine teams" feature) is related -- an admin merge tool would help clean up stubs, but doesn't prevent their creation.
- The `ensure_team_row` conservative backfill rules (no gc_uuid/public_id on name-only matches) were designed to prevent misidentification, but they also prevent the generator from correcting a wrong match.

---
Created: 2026-03-29
Last reviewed: 2026-03-29
Review by: 2026-06-27
