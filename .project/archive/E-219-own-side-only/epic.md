# E-219: Own-Side-Only Boxscore Loading

## Status
`READY`

## Overview
Stop loading opponent player stats from boxscore data. GameChanger returns different player UUIDs depending on which team's perspective a boxscore is fetched from, so loading both sides creates phantom duplicate players. After this epic, a boxscore load inserts player stats only for the team whose perspective the boxscore was fetched from. Game-level data (scores, dates, team IDs) still loads from either perspective.

## Background & Context
GameChanger's boxscore endpoint returns per-player stats for both teams, but the opponent's player UUIDs are **perspective-specific** -- they differ from the UUIDs the opponent's own boxscore uses. Currently `GameLoader._upsert_game_and_stats()` loads BOTH teams' player stats (`own_data` AND `opp_data`), inserting opponent players with wrong UUIDs. This creates duplicates that are invisible to the roster-based dedup detector (`find_duplicate_players()`) because phantom players from `opp_data` aren't on any roster.

Three prior epics attempted post-hoc fixes:
- **E-211**: UUID contamination prevention (stopped `root_team_id` from polluting `gc_uuid`, but didn't address player duplication)
- **E-215**: Player dedup merge (cleanup tool, but blind to phantom players not on rosters)
- **E-216**: Game dedup (cross-perspective game dedup, but didn't address player side)

All three treated symptoms. This epic addresses the root cause.

**User principle**: "If I scout East, I want East's record. If I scout Northeast, I want Northeast's record. I never want East's version of Northeast's players."

SE consulted for plays/spray loader assessment; CA consulted for context-layer story scope.

## Goals
- Eliminate cross-perspective player duplication at the source (GameLoader)
- Fix the member-team spray chart loader's cross-perspective insertion
- Clean up existing duplicate data caused by the bug
- Codify the own-side-only principle in the context layer to prevent regression
- Assess dedup infrastructure that was built to compensate for this bug

## Non-Goals
- Changing how game-level data (scores, dates, team rows) is loaded -- both perspectives still contribute game rows
- Modifying the scouting pipeline's crawl strategy (which teams to crawl)
- Addressing `gc_athlete_profile_id` cross-team identity (that's E-104)
- Changing the plays endpoint's pitch-by-pitch data model
- Adding new data capabilities or dashboard features

## Success Criteria
- No boxscore load inserts player stats for the opponent team's perspective
- Spray chart loader only inserts events for players on the crawling team's roster
- Cleanup tool verified against test fixtures simulating the Team 537 scenario; global scan logic tested
- Context-layer rule codifies own-side-only principle with loader guard and CR checklist
- Dedup infrastructure assessed: hooks/tools that exist only to compensate for this bug are simplified or removed
- All existing tests pass (updated where they relied on opponent-side data loading)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-219-01 | GameLoader own-side-only | TODO | None | - |
| E-219-02 | Spray chart loader own-side-only | TODO | E-219-01 | - |
| E-219-03 | Cross-perspective data cleanup | TODO | E-219-01, E-219-02 | - |
| E-219-04 | Cross-perspective safety context layer | TODO | E-219-01 | - |
| E-219-05 | Dedup simplification assessment and cleanup | TODO | E-219-01, E-219-02, E-219-03 | - |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### TN-1: Cross-Perspective UUID Behavior
GameChanger returns different `player_id` UUIDs for the same human depending on which team's boxscore is viewed. This is a permanent API property. When team A's boxscore lists team B's players, it uses different UUIDs (and often initial-only first names) than team B's own boxscore. The `UNIQUE` constraints on stat tables include `player_id`, but since each perspective produces a *different* `player_id` for the same human, the constraint doesn't prevent cross-perspective duplicates.

### TN-2: HIGH-Risk Endpoints
Three endpoint categories return per-player data with perspective-specific UUIDs:
1. **Boxscore** (`GET /game-stream-processing/{event_id}/boxscore`): batting/pitching lines per player per team. The core problem -- **fix in E-219-01**.
2. **Plays** (`GET /game-stream-processing/{event_id}/plays`): `batter_id`/`pitcher_id` per at-bat. Uses whole-game idempotency -- first perspective wins, second is skipped entirely. Phantom stubs are benign. **No code change needed** (SE assessment).
3. **Spray charts** (`GET /teams/{team_id}/schedule/events/{event_id}/player-stats`): `player_id` per ball-in-play event. Member spray loader inserts opponent events with cross-perspective UUIDs. **Fix in E-219-02**.

### TN-3: Flow Collision Pairs
Four scenarios where cross-perspective data collides:
1. **Report A + Report B**: Two standalone reports for teams that played each other.
2. **Member + Scouting**: Member team's boxscore loads own + opponent; scouting pipeline loads the opponent's own perspective.
3. **Scouting + Scouting**: Two tracked opponents that played each other.
4. **Plays + Scouting**: Plays loader runs for member team; scouting loads opponent's own perspective.

### TN-4: Plays Loader Assessment (SE Consultation)
The plays loader uses whole-game idempotency (`SELECT 1 FROM plays WHERE game_id = ? LIMIT 1`). Combined with `GameLoader._find_duplicate_game()` collapsing cross-perspective games to a single `game_id`, the second perspective is always skipped. Phantom stubs from `ensure_player_row()` are benign and cleaned by the dedup sweep. **No code change needed.** Document this assessment in the context-layer rule (E-219-04).

### TN-4a: Scouting and Reports Pipeline Impact (SE Consultation)
`ScoutingLoader` delegates boxscore loading to `GameLoader.load_file()`, so E-219-01's fix propagates to both the scouting pipeline and the reports generator automatically. Season aggregate queries (`_compute_season_aggregates`) are scoped by `WHERE team_id = ? AND season_id = ?` -- they only aggregate rows for the scouted team. Opponent per-game rows loaded via `opp_data` were dead weight (never aggregated, never displayed). Dropping `opp_data` loading eliminates phantom stubs and dead-weight rows with no functional impact. **No separate fix needed for scouting or reports.**

### TN-5: Spray Chart Loader Fix (SE Consultation)
The member-team spray loader (`spray_chart_loader.py`) iterates ALL players in both `offense` and `defense` sections. For opponent players not in `team_rosters`, it falls back to `fallback_team_id` and creates stubs via `ensure_player_row()`. The scouting spray loader already handles this correctly by skipping unresolvable players.

**Fix**: After resolving `team_id` via `_resolve_player_team_id()`, skip any player whose resolved `team_id != crawling_team_id`. This filters out opponent players regardless of whether they happen to be in `team_rosters`. The `crawling_team_id` is already available in `_load_game_file()` (resolved from `gc_uuid` at line 88/150).

### TN-6: Cleanup Strategy
Use existing `merge_player_pair()` from `src/db/player_dedup.py` for known duplicates (Team 537 Blackhawks 14U: 11 duplicate players + 1 duplicate game). Run a global scan across all teams to find additional affected teams. Cleanup is a one-time Python script exposed as a `bb data` CLI subcommand.

### TN-7: Dedup Infrastructure to Assess
The following was built to compensate for cross-perspective duplication:
- `dedup_team_players()` hook in `ScoutingLoader` (line 137-149)
- `dedup_team_players()` hook in `trigger.py` post-spray (line 752-762)
- `find_duplicate_players()` roster-based detection in `src/db/player_dedup.py`
- `bb data dedup-players` CLI command in `src/cli/data.py`

Assessment must distinguish cross-perspective cleanup (no longer needed after root cause fix) from genuine name-variant dedup (e.g., "O" vs "Oliver" -- still needed). The dedup hooks and CLI may still serve the name-variant use case.

### TN-8: Test Impact
Tests that construct boxscore fixtures with opponent data and assert opponent player rows are inserted will need updating:
- `tests/test_loaders/test_game_loader.py` -- may assert opponent batting/pitching rows
- `tests/test_uuid_contamination.py` -- tests cross-perspective handling
- `tests/test_dedup_integration.py` -- dedup test scenarios may change
- `tests/test_scouting_loader.py` -- verified unaffected (tests use own-team player data and opponent team rows, both preserved); run for regression only
- `tests/test_loaders/test_spray_chart_loader.py` -- member spray chart tests
- `tests/test_scouting_spray_loader.py` -- scouting spray chart tests (verify no regressions)

## Open Questions
- None -- problem, root cause, and fix are fully specified.

## History
- 2026-04-08: Created
- 2026-04-08: READY after 2 internal review iterations + 2 Codex spec review passes (27 findings: 21 accepted, 6 dismissed). Key fixes: test file references corrected, SQL migration → Python CLI, import boundary fixed, routing conflict resolved (AC-7 moved to CA story), E-219-03 dependency on E-219-02 added, shared CLI file dependency added, AC-2 rewritten for worktree verifiability, detection heuristic tightened (+ same team_id), duplicate game AC added, epic success criterion aligned with ACs.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 8 | 7 | 1 |
| Internal iteration 1 -- Holistic team (PM + SE) | 3 | 3 | 0 |
| Internal iteration 2 -- CR spec audit | 4 | 3 | 1 |
| Internal iteration 2 -- Holistic team (PM) | 1 | 1 | 0 |
| Codex iteration 1 | 5 | 4 | 1 |
| Codex iteration 2 | 6 | 3 | 3 |
| **Total** | **27** | **21** | **6** |
