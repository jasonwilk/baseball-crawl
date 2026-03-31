# E-195: Plays Data Ingestion Pipeline -- FPS% and QAB

## Status
`READY`

## Overview
Build the play-by-play data ingestion pipeline from the GameChanger plays endpoint, storing parsed play and pitch event data in the database. First derived stats: FPS% (first pitch strike percentage) for pitchers and QAB (quality at-bat) for batters. This unlocks advanced analytics that are currently unavailable for opponents (season-stats API returns 403 for non-owned teams) and adds per-game granularity for own teams.

## Background & Context
The GC plays endpoint (`GET /game-stream-processing/{event_id}/plays`) provides the richest data source in the API -- full pitch-by-pitch sequences per plate appearance for both own and opponent games. The endpoint is CONFIRMED (2026-03-26), not ownership-gated, and well-documented at `docs/api/endpoints/get-game-stream-processing-event_id-plays.md` with a comprehensive developer reference at `docs/api/flows/plays-ingestion.md`.

**What exists today**: Own teams already have FPS and QAB as season aggregates via the season-stats API (`player_season_pitching.fps`, `player_season_batting.qab`). Opponents have neither -- the plays pipeline is the ONLY path to these stats for scouting. Sample data exists at `data/raw/game-plays-fresh.json`.

**Data exploration** (2026-03-31): api-scout analyzed 165 games / 9,398 plays across 4 teams. Key findings: 24 distinct outcome types confirmed, 486 unique `final_details` patterns observed, "Intentional Walk" is a distinct outcome (IBB detectable), "Sacrifice Bunt" and "Sacrifice Fly" are explicit outcomes. Full report at `data/raw/plays-exploration/FINDINGS.md`.

**Expert consultations completed**:
- **Baseball-coach**: Confirmed FPS% and QAB definitions with edge cases (see Technical Notes)
- **Data-engineer**: Recommended two-table schema (`plays` + `play_events`) with pre-computed boolean flags
- **Software-engineer**: Assessed parsing complexity, recommended separating parser from loader for testability

Promotes from IDEA-041 (Play-by-Play Stat Compilation Pipeline) -- this epic covers the foundational ingestion layer. Broader analytics (situational hitting, baserunning, count splits) are captured in `.project/ideas/plays-pipeline-analytics.md` for future epics.

## Goals
- Crawl and cache plays JSON for all completed games (own teams)
- Store parsed play data with batter/pitcher linkage, pitch counts, and event classification
- Compute FPS% and QAB flags per play with accuracy matching GC's own definitions
- Validate derived stats against GC season-stats API values for own teams
- Expose plays crawling and loading via the `bb` CLI

## Non-Goals
- Opponent/scouting pipeline integration (future epic -- same endpoint, different event_id discovery path)
- Dashboard display of FPS%/QAB stats (future epic -- needs query layer + template work)
- Advanced analytics beyond FPS%/QAB (situational hitting, baserunning, count splits -- see IDEA-041)
- Play-by-play display or game replay features
- Spray chart correlation with plays data

## Success Criteria
- Pipeline processes all completed own-team games and stores play + event data
- Derived FPS count per pitcher matches GC season-stats within 5% tolerance (scorekeeper dependency)
- Derived QAB count per batter matches GC season-stats within 5% tolerance
- Re-running the pipeline produces zero duplicate rows (idempotent)
- `bb data crawl --crawler plays` and `bb data load --loader plays` work end-to-end

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-195-01 | Plays Crawler | TODO | None | SE |
| E-195-02 | Plays Schema and Parser | TODO | None | SE |
| E-195-03 | Plays Loader | TODO | E-195-02 | SE |
| E-195-04 | CLI Integration and Pipeline Wiring | TODO | E-195-01, E-195-03 | SE |
| E-195-05 | Own-Team FPS/QAB Validation | TODO | E-195-04 | SE |
| E-195-06 | Plays Endpoint Doc Vocabulary Update | TODO | None | api-scout |

## Dispatch Team
- software-engineer
- api-scout

## Technical Notes

### TN-1: FPS% Definition (from baseball-coach)

**First-pitch strike** = the first pitch event in `at_plate_details` (skipping baserunner and substitution events) is any of:
- "Strike 1 looking"
- "Strike 1 swinging"
- "Foul"
- "Foul tip"
- "In play"

**`is_first_pitch_strike` computation**: Compute this flag accurately for ALL plate appearances, including HBP and IBB outcomes. The flag records what actually happened on the first pitch. FPS% exclusions are applied at query time, not at parse time.

**FPS% query-time exclusions** (exclude from denominator):
- HBP plate appearances: `outcome = 'Hit By Pitch'`
- Intentional walks: `outcome = 'Intentional Walk'` (pitcher is not trying to throw strikes)
- Incomplete/abandoned plate appearances: already excluded from the `plays` table (parser skips them per TN-7)
- Query pattern: `WHERE outcome NOT IN ('Hit By Pitch', 'Intentional Walk')`

**FPS% is a pitching stat**: credited to the pitcher who threw pitch 1, even if a mid-PA pitching change occurs.

### TN-2: QAB Definition (from baseball-coach)

**Quality at-bat** = any ONE of these 7 conditions is met:

| Condition | Detection Method |
|-----------|-----------------|
| **2S+3**: 3+ pitches after reaching 2-strike count | Count pitches after the second strike event (see below) |
| **6+**: 6 or more total pitches in the PA | Count pitch events (exclude baserunner/substitution events) |
| **XBH**: Extra-base hit (2B, 3B, HR) | `outcome` in ("Double", "Triple", "Home Run") |
| **HHB**: Hard-hit ball (line drive or hard ground ball) | Any `final_details` template contains "line drive" OR "hard ground ball" |
| **BB**: Walk (regular, not intentional) | `outcome` == "Walk" |
| **SAC Bunt**: Successful sacrifice bunt | `outcome` == "Sacrifice Bunt" |
| **SAC Fly**: Successful sacrifice fly | `outcome` == "Sacrifice Fly" |

**2S+3 clarification**: "Pitches after 2 strikes" includes ALL pitches after the batter reaches a 2-strike count, including the terminal pitch (the one that ends the PA -- strikeout, hit, out, etc.). A "Foul" on a 2-strike count counts as a pitch seen after 2 strikes but does NOT advance the strike count (can't strike out on a foul). Minimum total pitches for 2S+3: 5 (reach 2-strike count in 2 pitches, then see 3 more).

**QAB exclusions** (these outcomes are explicitly NOT quality at-bats):
- Intentional Walk (batter did nothing -- distinct from regular "Walk")
- Dropped 3rd Strike (batter struck out, only reached due to fielding play)
- Catcher's Interference

### TN-3: Schema Design (from data-engineer)

Two tables in migration `009_plays_play_events.sql`:

**`plays`** -- one row per plate appearance:
- `game_id` (FK to games), `play_order` (0-indexed), `inning`, `half`
- `season_id` (FK to seasons -- denormalized for query convenience)
- `batting_team_id` (FK to teams -- the team at bat for this PA)
- `batter_id` (FK to players), `pitcher_id` (FK to players, nullable)
- `outcome` (name_template.template value: Walk, Single, Strikeout, etc.)
- `pitch_count` (total pitches, excluding non-pitch events)
- `is_first_pitch_strike` (0/1 boolean)
- `is_qab` (0/1 boolean)
- `home_score`, `away_score`, `did_score_change`, `outs_after`, `did_outs_change`
- Idempotency key: `UNIQUE(game_id, play_order)`

**`play_events`** -- one row per event within a plate appearance:
- `play_id` (FK to plays), `event_order` (0-indexed within PA)
- `event_type` enum: `pitch`, `baserunner`, `substitution`, `other`
- `pitch_result` enum (nullable, only for pitch events): `ball`, `strike_looking`, `strike_swinging`, `foul`, `foul_tip`, `in_play`
- `is_first_pitch` (0/1 boolean -- only one event per play has this set)
- `raw_template` (original template string for debugging/reprocessing)
- Idempotency key: `UNIQUE(play_id, event_order)`

**Indexes** (in migration, after table creation):
- `CREATE INDEX IF NOT EXISTS idx_plays_game_id ON plays(game_id)` -- game-scoped queries
- `CREATE INDEX IF NOT EXISTS idx_plays_batter_id ON plays(batter_id)` -- per-batter QAB aggregation
- `CREATE INDEX IF NOT EXISTS idx_plays_pitcher_id ON plays(pitcher_id)` -- per-pitcher FPS% aggregation
- `CREATE INDEX IF NOT EXISTS idx_plays_fps ON plays(pitcher_id, is_first_pitch_strike) WHERE outcome NOT IN ('Hit By Pitch', 'Intentional Walk')` -- partial index for efficient FPS% queries

### TN-4: Template Classification Rules

**Pitch events** (count toward pitch_count): Templates matching any of:
- `Ball [1-4]`
- `Strike [1-3] looking`
- `Strike [1-3] swinging`
- `Foul` (exact match)
- `Foul tip` (exact match)
- `In play` (exact match)
- `Foul bunt` (exact match -- foul ball off a bunt attempt, classified as `foul`)

**Baserunner events**: Templates containing `${uuid}` AND any of: "advances to", "scores on", "steals", "remains at", "Pickoff attempt", "caught stealing", "picked off". Note: fielding chains in pickoff/CS events can reference up to 7 fielders with variable-length patterns.

**Substitution events**: Templates starting with "Lineup changed:" or "(Play Edit)" or containing "in for pitcher" or "Courtesy runner"

**Outcome vocabulary** (`name_template.template` values confirmed from 9,398 plays across 165 games):
```
Walk              Single            Double            Triple
Home Run          Strikeout         Fly Out           Ground Out
Pop Out           Line Out          Hit By Pitch      Error
Fielder's Choice  Runner Out        Sacrifice Bunt    Sacrifice Fly
Dropped 3rd Strike  Infield Fly     Intentional Walk  Double Play
Batter Out        Inning Ended      FC Double Play    Catcher's Interference
${uuid} at bat    <- incomplete/abandoned (skip -- see TN-7)
```

**QAB outcome detection** (using the confirmed vocabulary above):
- XBH: `outcome` in ("Double", "Triple", "Home Run")
- BB: `outcome` == "Walk" (distinct from "Intentional Walk")
- SAC: `outcome` in ("Sacrifice Bunt", "Sacrifice Fly")
- HHB: any `final_details` template contains "line drive" OR "hard ground ball" (case-insensitive substring match)

**`final_details` parsing**: 486 unique patterns observed across 9,398 plays. These are NOT enumerable as a fixed vocabulary. The parser uses regex-based pattern matching to extract batter ID (first `${uuid}`), pitcher ID (when "pitching" suffix present), contact quality ("hard", "line drive"), and fielder references. Unknown patterns are handled gracefully (no crash).

### TN-5: Pitcher Identification Strategy

The batter is always the first `${uuid}` in the first `final_details` template. The pitcher requires game-state tracking:

1. Maintain two state variables: `current_pitcher_top` and `current_pitcher_bottom`, both initialized to NULL at game start
2. On substitution events matching "in at pitcher" or "in for pitcher" in `at_plate_details`, update the appropriate pitcher state variable based on the current half-inning (substitution in a "top" half updates `current_pitcher_top`; "bottom" updates `current_pitcher_bottom`)
3. For each play, select the pitcher from the matching half's state: top-half plays use `current_pitcher_top`, bottom-half plays use `current_pitcher_bottom`
4. Walks/strikeouts/HBP final_details templates often include the pitcher explicitly ("${uuid} pitching") -- use this as ground truth when available, overriding the tracked state. Note: this explicit reference is present in most but not all K/BB/HBP plays (~45 instances without across 9,398 plays). The tracked state is the fallback.
5. Pitcher state persists across innings within the same half (top/bottom) until changed by a substitution event

Pitcher ID may be NULL for edge cases where no pitching change was recorded and no explicit pitcher reference exists. This is acceptable -- NULL pitcher_id means "unidentifiable" rather than silently wrong.

### TN-6: Event ID Chain

```
games.game_id = event_id (from game-summaries top-level field)
  -> GET /game-stream-processing/{event_id}/plays
```

The `event_id` equals `game_stream.game_id`. NEVER use `game_stream.id` (different UUID, causes HTTP 500). The game loader already stores `event_id` as `games.game_id`.

### TN-7: Edge Cases and Idempotency

- **Abandoned plate appearances**: Skip plays where `final_details` is empty (name_template = "${uuid} at bat"). These are excluded from parser output entirely.
- **Scorekeeper dependency**: Play data quality varies by scorekeeper. Some games may have incomplete or missing plays data.
- **team_players asymmetric keys**: Own team uses public_id slug, opponent uses UUID. Build a flat player lookup dict across both teams.
- **FK-safe player handling**: Unknown player_ids get stub rows inserted before play rows (existing project pattern).
- **Whole-game idempotency**: Before processing a game, check if any `plays` row exists for that `game_id`. If yes, skip the entire game (all plays + events already loaded). This avoids the parent-child re-insertion problem where `INSERT OR IGNORE` on an existing `plays` row returns no `play_id` for child `play_events` rows. Never delete-and-reinsert.
- **Game FK guard**: The loader must verify that `game_id` exists in the `games` table before inserting plays. If the game has not been loaded by the game loader yet, skip with a warning.

### TN-8: File Layout

```
src/gamechanger/crawlers/plays.py          -- PlaysCrawler
src/gamechanger/parsers/plays_parser.py    -- PlaysParser (pure function, no DB)
src/gamechanger/loaders/plays_loader.py    -- PlaysLoader (thin DB writer)
migrations/009_plays_play_events.sql       -- Schema migration
data/raw/{season}/teams/{gc_uuid}/plays/{event_id}.json  -- Cached raw data
```

### TN-9: Validation Approach

Compare derived stats against GC season-stats for own teams:
- FPS%: `SUM(is_first_pitch_strike) per pitcher WHERE outcome NOT IN ('Hit By Pitch', 'Intentional Walk')` vs `player_season_pitching.fps`
- QAB: `SUM(is_qab) per batter` vs `player_season_batting.qab`

Tolerance: 5% deviation is acceptable due to scorekeeper data quality and potential edge-case differences. Discrepancies above 5% require investigation and root-cause documentation.

The validation should also report plays data coverage: what percentage of completed games have plays data, and flag any games with zero plays as potential scorekeeper gaps.

## Open Questions
- Are there additional `at_plate_details` template patterns beyond the documented vocabulary? Parser should handle unknown templates gracefully (classify as `other` event type). Data exploration confirmed 486 unique `final_details` patterns -- regex-based parsing is required.

## History
- 2026-03-31: Created. Expert consultations completed with baseball-coach (FPS%/QAB definitions), data-engineer (schema design), software-engineer (parsing complexity assessment).
- 2026-03-31: Iteration 1 review. 20 findings accepted from PM, CR, DE, SE, and coach. Key fixes: pitcher state tracking (persist per-half across innings), HBP FPS% handling (compute accurately, exclude at query time), whole-game idempotency strategy, added season_id/batting_team_id columns and indexes, 2S+3 counting clarification.
- 2026-03-31: Data exploration (165 games, 9,398 plays). Key findings: "Intentional Walk" is a distinct outcome (IBBs detectable and excludable from FPS%/QAB), "Sacrifice Bunt"/"Sacrifice Fly" are explicit outcomes (no heuristic needed), 24 outcome types and 486 final_details patterns confirmed. SAC Open Question resolved.
- 2026-03-31: Codex spec review. 5 of 6 findings accepted: "Foul bunt" pitch event pattern, LoadResult field alignment, pipeline orchestrator files (crawl.py/load.py), test_migrations.py, fixture adequacy for AC-11. Agent routing mismatch dismissed (migration too simple to split).
- 2026-03-31: Added E-195-06 (Plays Endpoint Doc Vocabulary Update, api-scout) and AC-13 (unknown template logging) per user gaps.
- 2026-03-31: Set to READY.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 (PM + CR + DE + SE + Coach) | 30 | 20 | 10 |
| Codex iteration 1 | 6 | 5 | 1 |
| **Total** | **36** | **25** | **11** |

Key review milestones:
- Critical fix: TN-5 pitcher state tracking (persist per-half across innings)
- Data exploration: 165 games / 9,398 plays resolved SAC and IBB open questions
- Codex catch: "Foul bunt" pitch event pattern, pipeline orchestrator file gaps
