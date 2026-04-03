# E-202: Fix Report Generator Team Deduplication Bug

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Fix a team deduplication bug where the report generator and scouting crawler independently resolve team identity, creating duplicate team rows. The generator matches an existing team via name+season_year (step 3) but does not backfill `public_id`; the crawler then fails to find that team by `public_id` alone and creates a duplicate. Reports query the original team and find no scouting data.

## Background & Context
**Observed failure (Waverly Vikings)**:
- Team 93: Waverly Vikings Varsity 2026, gc_uuid set, public_id = NULL. Has spray data from own boxscores.
- Team 383: Unknown, public_id = Xj9LlYlJklcl, source=scouting. Created by crawler during report generation. Has scouting_runs but zero loaded data.
- Report linked to team 93 -> shows "No data available" for batting/pitching.

**Root cause chain**:
1. `generate_report()` calls `ensure_team_row(public_id='Xj9LlYlJklcl', name='Waverly Vikings Varsity 2026', season_year=2026)`.
2. Step 2 (public_id match) misses -- no team has that public_id.
3. Step 3 (name+season_year+tracked) matches team 93 and returns it. No public_id backfill (by design).
4. Report row created with team_id=93.
5. `ScoutingCrawler.scout_team('Xj9LlYlJklcl')` on a different DB connection calls `ensure_team_row(public_id='Xj9LlYlJklcl')` with no name.
6. Steps 1-3 all miss. Step 4 INSERTs team 383 (duplicate).
7. Crawler writes data to team 383. Report queries team 93. Empty results.

**Expert consultation**: SE assessed two fix approaches (2026-04-03). Approach A (pass `team_id` through to crawler) is backward-compatible but is a workaround that skips dedup. Approach B (generator backfills `public_id` after step-3 match) fixes the root cause in a single file with ~2 lines, and all downstream code benefits. SE recommends Approach B. See Technical Notes for details.

No expert consultation required for baseball-coach (no coaching data changes), api-scout (no API changes), data-engineer (no schema changes), or claude-architect (no context-layer changes).

## Goals
- Eliminate duplicate team creation when the report generator processes a team already known by name but missing `public_id`
- Ensure the scouting crawler finds the correct existing team row during report generation

## Non-Goals
- Data repair utility or CLI command for existing duplicates (user will repair manually)
- Changes to the conservative backfill policy in `ensure_team_row` step 3
- Refactoring `ensure_team_row` or the scouting crawler interface
- Handling the edge case where the public API call fails (pre-existing degraded-state path, not new risk)

## Success Criteria
- Generating a report for a team that already exists by name+season_year (but lacks `public_id`) no longer creates a duplicate team row
- The scouting crawler writes data to the same team row the report references
- Reports for such teams show scouting data instead of "No data available"
- Existing callers of `ensure_team_row` and `scout_team` are unaffected

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-202-01 | Backfill public_id in report generator after step-3 match | TODO | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Fix Approach: Caller-Side public_id Backfill

The fix adds a `public_id` backfill near the existing force-update block in `generate_report()` (`src/reports/generator.py`, search for `UPDATE teams SET name = ?`). This block already unconditionally updates `name` and `season_year` when the public API call succeeds. The `public_id` backfill must use a separate UPDATE statement (or conditional SQL) so that the `AND public_id IS NULL` guard does not interfere with the unconditional name/season_year update. The backfill is safe because:

1. The generator has high confidence in the association: it fetched the team name from `GET /public/teams/{public_id}` and `ensure_team_row` matched that name to an existing row.
2. The `AND public_id IS NULL` guard prevents overwriting a `public_id` set through a more authoritative path.
3. The backfill happens inside the `if team_name_from_api:` guard, meaning it only fires when the public API call succeeded -- we only trust the association when we have the profile data.
4. Once `public_id` is on the row, the crawler's `_ensure_team_row(public_id=...)` hits step 2 of the dedup cascade and returns the existing row. No duplicate.

**Why not Approach A (pass `team_id` to crawler)?** It is a workaround that skips the dedup cascade in the crawler for the report path only. Approach B fixes the root cause (missing `public_id` on the team row) so ALL downstream code benefits, not just the report generator's crawler call.

**Why not modify `ensure_team_row`?** The conservative backfill policy (no `public_id`/`gc_uuid` on name-only matches) exists to prevent irreversible misidentification across all callers. The report generator is a special case -- it has verified the association via the public API. The backfill belongs in the caller that has the verification context, not in the shared utility.

### Blast Radius

- **Changed files**: `src/reports/generator.py` (production fix), `tests/test_report_generator.py` (new test coverage)
- **Unchanged**: `src/db/teams.py`, `src/gamechanger/crawlers/scouting.py`, `src/pipeline/trigger.py`, `src/cli/data.py`
- **`scout_team()` callers**: 4 total (generator, trigger.py, cli/data.py, scout_all internal). None affected. A 5th reference exists but is a docstring example, not a call site.

## Open Questions
- None (all questions resolved during SE consultation)

## History
- 2026-04-03: Created. SE consultation completed -- Approach B (caller-side backfill) selected.
- 2026-04-03: READY. 14 review findings triaged (10 accepted, 4 dismissed). Epic refined through 3 review passes.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 4 | 2 | 2 |
| Internal iteration 1 -- Holistic team (PM + SE) | 6 | 4 | 2 |
| Codex iteration 1 | 4 | 4 | 0 |
| **Total** | **14** | **10** | **4** |
