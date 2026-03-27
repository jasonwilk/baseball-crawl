# E-165: Fix Scouting Spray Chart Team Misattribution

## Status
`READY`

## Overview
The scouting spray chart loader guesses team assignment when a player cannot be resolved via roster lookup, resulting in 46.4% of scouting spray chart rows (1,275 of 2,745) assigned to the wrong team. This epic eliminates the guessing -- unresolvable players are skipped instead of misattributed -- and cleans up existing bad data.

## Background & Context
When scouting an opponent, we fetch their entire season's spray chart data. That includes games against teams we don't track. Players from those non-tracked teams aren't in `team_rosters`, so `_resolve_player_team_id` falls back to `fallback_team_id` (the opponent team ID). This silently assigns spray events to the wrong team -- some rows are even misattributed to Standing Bear.

The user's position: "We should not guess and assign things to teams that we aren't sure about. That's just irresponsible."

The root cause is in `ScoutingSprayChartLoader._resolve_player_team_id` (`src/gamechanger/loaders/scouting_spray_loader.py`). When the roster query returns no match, it returns the fallback team ID instead of signaling "unknown."

**Expert consultation**: SE consulted on fix approach, cleanup strategy, and log level. DE consulted on cleanup query correctness. Key findings incorporated into Technical Notes.

## Goals
- Eliminate team-assignment guessing: unresolvable players produce a skip, not a wrong assignment
- Remove the ~1,275 existing misattributed rows from the database
- Reduce log noise from per-player WARNING to a per-game DEBUG summary

## Non-Goals
- Fixing the identical `_resolve_player_team_id` fallback pattern in the member `SprayChartLoader` (`src/gamechanger/loaders/spray_chart_loader.py`) -- same bug, different context; address separately if needed
- Improving roster coverage to reduce the number of unresolvable players (upstream data problem)
- Adding a dedicated data quality report or new `LoadResult` fields beyond the existing `skipped` counter
- Changing spray chart display thresholds or dashboard rendering

## Success Criteria
- Zero spray chart rows exist where `team_id` was assigned by guessing
- Re-running the scouting spray loader on existing raw JSON produces only correctly-attributed rows (unresolvable players skipped)
- Scouting spray loader logs show a per-game DEBUG summary of skipped events rather than per-player WARNINGs

Note: success criteria are fully met after the code fix is deployed AND the operator runs the documented cleanup procedure from TN-3.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-165-01 | Stop guessing team assignment and clean up bad data | TODO | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: The guessing mechanism
`_resolve_player_team_id` queries `team_rosters` for the player against both home and away team IDs scoped by season. When no match is found, it returns `fallback_team_id` (the opponent team ID passed by the caller). The caller uses this return value directly as `team_id` for the spray chart row -- no indication that it was a guess. The method is private and called only from `_load_game_file` (line 274).

### TN-2: Why scouting is worse than member loading
For member teams, both home and away rosters are typically in `team_rosters` (we crawl rosters for our own teams and their opponents). For scouting, we fetch an opponent's full season -- including games against teams we've never seen. Those third-party players have no roster entries at all.

### TN-3: Cleanup strategy (from DE consultation)
Delete misattributed rows using a roster-join query that targets the actual definition of a bad row -- a player not found in `team_rosters` for either the home or away team in that game:

```sql
DELETE FROM spray_charts
WHERE id IN (
    SELECT sc.id FROM spray_charts sc
    JOIN games g ON g.game_id = sc.game_id
    WHERE NOT EXISTS (
        SELECT 1 FROM team_rosters tr
        WHERE tr.player_id = sc.player_id
          AND tr.team_id IN (g.home_team_id, g.away_team_id)
          AND tr.season_id = sc.season_id
    )
);
```

This query is loader-agnostic (catches bad rows from both member and scouting loaders), idempotent, and precisely matches only guessed rows. No re-load is required after this DELETE -- it removes only bad rows, preserving correctly-attributed data. Document as an operator step.

A `membership_type`-based DELETE (`WHERE team_id IN (SELECT id FROM teams WHERE membership_type = 'tracked')`) is insufficient: if the opponent played Standing Bear, misattributed rows have `team_id` = Standing Bear's id (membership_type = 'member') and would be missed.

### TN-4: Log level (from SE consultation)
"Player not in opponent roster" is expected and normal for scouting data. Log at DEBUG, not INFO or WARNING. Aggregate per game: collect skipped player count during game processing, emit one DEBUG line after all sections are processed (e.g., "Game {game_id}: skipped {N} events for {M} unresolvable players"). Emit only when at least one player was unresolvable -- no log line for clean games. This replaces the current per-player WARNING.

### TN-5: Idempotency after fix
The loader uses `INSERT OR IGNORE` on `event_gc_id`. Previously-inserted bad rows will NOT be corrected by re-running (the INSERT is ignored because `event_gc_id` already exists). The cleanup DELETE (TN-3) must happen BEFORE any re-loading. However, the roster-join cleanup query in TN-3 only deletes bad rows, so re-loading is optional -- it is only needed if the operator wants to re-populate rows that were correctly skipped (e.g., after roster data improves).

### TN-6: Existing test updates
11 existing tests in `tests/test_scouting_spray_loader.py` require changes due to the behavioral shift. After the fix, unresolvable players are skipped at the player-loop level (before `_insert_event` is ever called), so `_ensure_stub_player` is never reached for those players. Unresolvable players produce zero inserts -- no stub player row, no spray rows.

**7 tests need `_seed_roster()` added to setup** (they seed players in `players` but not in `team_rosters`; without roster entries, the fix skips their events):
1. `test_defensive_chart_type_is_stored`
2. `test_reloading_same_file_produces_zero_new_inserts`
3. `test_empty_defenders_stored_with_null_coords`
4. `test_multi_game_across_season`
5. `test_season_id_inferred_from_path`
6. `test_load_all_processes_all_opponents`
7. `test_load_all_with_public_id_filter`

**2 tests need full rewrites** (their purpose changes from testing fallback to testing skip):
- `test_unknown_player_gets_stub_row` -- must assert: no spray rows, no stub player row, `result.skipped == len(events)`
- `test_unknown_player_logs_warning` -- must assert: no per-player WARNING emitted for unresolvable players

**2 tests need roster entries so the actual code path under test is exercised** (without roster entries, these tests pass for the wrong reason -- the player is skipped at the roster level rather than at the event-validation level):
- `test_defender_missing_location_skipped` -- add roster entry so the player reaches `_insert_event`, where missing x/y triggers the skip
- `test_event_missing_id_field_is_skipped` -- add roster entry so the player reaches `_insert_event`, where missing `id` field triggers the skip

## Open Questions
- None

## History
- 2026-03-27: Created. SE consulted on fix approach, cleanup strategy, and log level. DE consulted on cleanup query correctness.
- 2026-03-27: Internal review iteration 1. 8 findings accepted: TN-6 expanded to 11 tests (from 2), cleanup query replaced with roster-join (DE), Non-Goals wording narrowed, AC-3/AC-4/AC-5 clarified, operator cleanup command specified.
- 2026-03-27: Internal review iteration 2. 1 finding accepted: operator note expanded for member chart recovery. Codex spec review: 3 findings accepted: Success Criteria clarified as post-deployment+operator, member reload suggestion removed (member loader has same bug), AC-5 decomposed (test churn moved to DoD). Codex iteration 2: 3 findings dismissed (baseball-coach consultation not needed for loader bug fix; member note deliberately reverted; AC-5 sub-clauses are tightly related). Set to READY.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 3 | 3 | 0 |
| Internal iteration 1 -- Holistic team | 6 | 6 | 0 |
| Internal iteration 2 -- CR spec audit | 1 | 1 | 0 |
| Internal iteration 2 -- Holistic team | 0 | 0 | 0 |
| Codex iteration 1 | 3 | 3 | 0 |
| Codex iteration 2 | 3 | 0 | 3 |
| **Total** | **16** | **13** | **3** |

Note: Internal iteration 1 CR-2 and H-3 overlap, so 8 unique findings from 9 raw. Total unique accepted: 12.
