# E-216: Cross-Perspective Game Dedup in the Scouting Pipeline

## Status
`READY`

## Overview
When two tracked teams play each other, the GameChanger public games API returns different game IDs for the same real-world game depending on which team's perspective is queried. The scouting loader inserts both as separate `games` rows, inflating batting and pitching stats. This epic adds a pre-load dedup check that prevents duplicate game rows from being created, and post-load data validation that verifies the loaded data matches expectations before it's used.

## Background & Context
**Trigger**: Grand Island Varsity (team 471) vs Lincoln High Varsity (team 476) on 2026-03-19. The same 11-1 game appeared as two different game_ids (`b2313a7a` from one perspective, `676e023a` from the other), inflating Ian Arends from 9 GP / 36 PA to 10 GP / 40 PA.

**Root cause**: `ScoutingLoader._build_games_index()` (`src/gamechanger/loaders/scouting_loader.py`:287-288) reads the public games endpoint's `id` field and uses it as both `event_id` and `game_stream_id` in the `GameSummaryEntry`. When team A is scouted, a game gets ID X. When team B is scouted later for the same game, it gets ID Y. Both flow through `GameLoader.load_file()` -> `_upsert_game(game_id=summary.event_id, ...)` and create separate `games` rows because they have different primary keys.

**The member-team path does not have this problem**: The authenticated `game-summaries` endpoint returns stable `event_id` and `game_stream_id` values regardless of perspective. Only the public games endpoint (`GET /public/teams/{public_id}/games`) returns perspective-specific IDs.

**Systemic problem**: This project has repeatedly shipped bad data (player dupes, game dupes, inflated stats) and then built cleanup utilities after the fact (`bb data dedup-players`, `bb data repair-opponents`). This epic breaks that pattern: prevent bad data at insert time and validate it's correct after loading — don't build more cleanup tools.

## Goals
- Prevent duplicate game rows from being created when two tracked teams share a matchup (pre-load check)
- Validate post-load data integrity: game counts and roster counts match what was crawled
- Catch data corruption immediately at load time, not after coaches see wrong stats

## Non-Goals
- Adding a DB-level UNIQUE constraint on natural key columns (application-level dedup is sufficient; NULL `start_time` makes a constraint fragile)
- Changing how the public games API is called or how crawlers write files (the API behavior is fixed; raw crawled files are correct per-perspective)
- Deduplicating games across the member-team and scouting paths (member-team games use authenticated event_ids which are already stable)
- Addressing cross-perspective player UUID duplicates (already handled by E-215)
- Building another cleanup CLI command (the pre-load check + validation should prevent the problem; if they don't, we fix the root cause)

## Success Criteria
- The known duplicate (Grand Island vs Lincoln High, 2026-03-19) does not recur on the next `bb data scout` run
- Running `bb data scout` for two tracked teams that share a matchup produces exactly one `games` row per real-world game
- After loading, the scouting loader validates that game count and roster count match expectations and warns on mismatch
- Season aggregates (batting and pitching) reflect correct game counts
- No FK integrity violations

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-216-01 | Add pre-load game dedup check to GameLoader | TODO | None | - |
| E-216-02 | Add post-load data validation to scouting loader | TODO | E-216-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Natural Key for Game Dedup

A game is uniquely identified by: `game_date` + the unordered pair of `{home_team_id, away_team_id}`. The home/away assignment may differ between perspectives (one API response says team A is home, another says team A is away for the same game), so the dedup check must be **order-insensitive** on team IDs.

**Doubleheader edge case**: Two teams can play each other twice on the same date. To distinguish doubleheader games:
1. If both rows have non-NULL `start_time` and the times differ, they are distinct games (not duplicates).
2. If `start_time` is NULL on either side, fall back to score matching: if `home_score + away_score` totals differ, they are distinct games.
3. If neither `start_time` nor score can distinguish them, do not dedup (insert/keep both) to avoid false-positive merges. Log a warning.

### Dedup Query Pattern

The pre-load check queries for existing games matching a natural key:

```sql
SELECT game_id, home_team_id, away_team_id, home_score, away_score, start_time
FROM games
WHERE game_date = ?
  AND status = 'completed'
  AND (
    (home_team_id = ? AND away_team_id = ?)
    OR (home_team_id = ? AND away_team_id = ?)
  )
```

The caller passes `(team_a, team_b, team_b, team_a)` to cover both orderings. If multiple rows match, apply the doubleheader tiebreakers described above.

### Data Loading Paths Covered

Three code paths call `ScoutingLoader.load_team()` -> `GameLoader.load_file()` and could produce cross-perspective game duplicates:

1. **`bb data scout` (CLI)** -- `src/cli/data.py` -> scouting pipeline for tracked opponents
2. **`run_scouting_sync` (web)** -- `src/pipeline/trigger.py` -> background scouting pipeline (admin-triggered)
3. **`bb report generate` (standalone reports)** -- `src/reports/generator.py` -> ad-hoc scouting for any public_id

The pre-load check (E-216-01) covers ALL three paths because it fires inside `GameLoader.load_file()`, which all paths share. The post-load validation (E-216-02) fires inside `ScoutingLoader.load_team()`, which all three paths also share.

### Pre-Load Check (E-216-01)

A new method on `GameLoader` queries for an existing game matching the natural key before `_upsert_game_and_stats()` is called. When a match is found, `load_file()` substitutes the existing `game_id` into the summary so all stat upserts use the canonical ID. The existing `_upsert_game()` call proceeds with `ON CONFLICT(game_id) DO UPDATE` which merges metadata. Per-player stat rows also use `ON CONFLICT ... DO UPDATE` and merge cleanly.

### Post-Load Data Validation (E-216-02)

After the scouting loader finishes loading data for a team, it validates the results against expected counts from the crawled data:

1. **Game duplicate check**: Query for any `(game_date, unordered team pair)` groups with `COUNT(*) > 1` among completed games involving this team. Log WARNING if duplicates found. This directly detects the problem without false positives from cross-team loading (where other teams' scouting runs legitimately add games involving this team).
2. **Roster count validation**: Compare expected roster count (from `roster.json` player count) to actual DB count of players in `team_rosters` for this team and season. Warn only if DB count exceeds expected (player dedup may legitimately reduce count).

These checks run inside `ScoutingLoader.load_team()` after `_load_boxscores()` and `_load_roster_section()`, before `_compute_season_aggregates()`. They are non-fatal (WARNING only, pipeline continues) but provide immediate visibility into data integrity issues.

The game count query scopes to games where this team is home OR away, with `status = 'completed'` and matching `season_id`. The roster count query counts distinct players in `team_rosters` for this `(team_id, season_id)`.

**Roster validation timing**: Roster validation runs immediately after `_load_roster_section()`, before boxscores are loaded. This is important because `GameLoader.load_file()` can insert additional players from boxscore data that aren't in `roster.json` — validating after boxscores would produce false warnings.

**Edge case -- cross-season_id**: If two tracked teams sharing a game have different `season_id` values (unlikely — e.g., `spring-hs` vs. `spring-legion`), the `ON CONFLICT DO UPDATE` in `_upsert_game()` overwrites `season_id` with the last writer's value. The validation query filtering on Team A's `season_id` could miss this game, producing a false warning. This is pre-existing behavior and unlikely at HS level — noted for implementer awareness.

### Files Modified Across Stories

| File | E-216-01 | E-216-02 |
|------|----------|----------|
| `src/gamechanger/loaders/game_loader.py` | X | |
| `tests/test_game_loader.py` or `tests/test_game_dedup.py` | X | |
| `src/gamechanger/loaders/scouting_loader.py` | | X |
| `tests/test_scouting_loader.py` or `tests/test_post_load_validation.py` | | X |

No file conflicts between stories.

## Open Questions
- None (resolved during discovery)

## History
- 2026-04-07: Created (DRAFT). SE consulted (pre-load prevention). DE consulted (post-load sweep). User redirected approach: validation over cleanup tools. Revised to prevention (E-216-01) + post-load validation (E-216-02). Dropped global merge sweep, `bb data dedup-games` CLI, and `src/db/game_dedup.py`. Existing duplicate (Grand Island vs Lincoln High, 2026-03-19) manually resolved prior to epic creation.
- 2026-04-07: Set to READY after 2 internal review iterations. Codex validation deferred to separate server.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit (v1) | 7 | 0 | 7 |
| Internal iteration 1 — PM holistic | 5 | 3 | 2 |
| Internal iteration 1 — SE/DE discovery | 6 | 0 | 6 |
| Internal iteration 2 — CR spec audit (v4) | 3 | 1 | 2 |
| Internal iteration 2 — PM holistic (v4) | 2 | 2 | 0 |
| Internal iteration 2 — SE/DE holistic (v4) | 14 | 0 | 14 |
| **Total** | **37** | **6** | **31** |
