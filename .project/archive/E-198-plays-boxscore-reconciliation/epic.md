# E-198: Plays-vs-Boxscore Reconciliation Engine

## Status
`COMPLETED`

## Overview
Build a reconciliation engine that cross-checks plays-derived aggregates against boxscore ground truth, detects pitcher attribution errors, and corrects them -- raising FPS% accuracy from ~55% to 90%+ at the per-pitcher level. The boxscore endpoint provides definitive per-pitcher and per-batter aggregates; the plays endpoint provides pitch-by-pitch granularity. Where they disagree on pitcher attribution, the boxscore wins and the engine reassigns plays accordingly.

## Background & Context
E-195 delivered the plays ingestion pipeline (plays + play_events tables, FPS% and QAB flags). Production validation revealed:
- **55.6% FPS match rate** (15 of 27 pitchers within 5% tolerance)
- **53.8% QAB match rate** (14 of 26 batters within 5% tolerance)
- **BF per pitcher off by up to 35 PAs** for individual pitchers
- Root cause: the plays endpoint doesn't always announce pitching changes via substitution events; the parser's pitcher state tracking drifts

The boxscore endpoint (already crawled and loaded into `player_game_pitching`) contains per-pitcher aggregates: BF, SO, BB, IP, H, pitches, strikes, HBP, WP, and pitching order (array position). These serve as checksums against plays-derived counts.

**Expert consultation completed:**
- **baseball-coach**: Pitcher attribution is the #1 priority. 90%+ accuracy needed for FPS%/pitch counts before surfacing on dashboards. 80% is useful for development context. Batter-side is secondary (already higher baseline). Defer RBI inference, ER attribution, fielding.
- **data-engineer**: Single `reconciliation_discrepancies` table with JSON detail columns. In-place UPDATE with discrepancy row as audit trail. Per-game scope, `reconcile_game(conn, game_id)` signature. Migration 012.
- **software-engineer**: ~800-1000 lines total. MVP is BF + SO detection/correction covering ~90% of pitcher boundary errors. Detection-only story first to see actual discrepancy distribution. Separate detection from correction (dry-run support).

Promoted from IDEA-062.

## Goals
- Detect pitcher attribution errors by comparing plays-derived aggregates against boxscore ground truth for 11 pitcher signals (BF, SO, BB, IP, H, pitch count, strikes, HBP, WP, starter ID, pitching order; R/ER deferred)
- Detect batter attribution discrepancies (AB, H, SO, BB, HBP per batter) to validate the batter-side baseline and explain the 53.8% QAB gap (detection only, no corrections)
- Correct pitcher attribution errors by reassigning `plays.pitcher_id` using boxscore pitcher order and BF boundary detection
- Log all discrepancies (matched, correctable, corrected, ambiguous, uncorrectable) for pattern analysis and future heuristic evolution
- Provide a CLI command (`bb data reconcile`) with dry-run and execute modes
- Run retroactively against all existing games and incrementally on new games
- Raise per-pitcher FPS% accuracy from ~55% to 90%+

## Non-Goals
- Batter attribution **correction** (batter ID is already reliable; detection-only validation is in scope to explain the QAB gap)
- R/ER per pitcher reconciliation (requires inherited runner tracking not present in plays data; deferred to Phase 2)
- RBI inference from plays data (probabilistic; deferred)
- Fielding signal reconciliation (putouts/assists not in boxscore endpoint; deferred)
- LLM-driven heuristic evolution feedback loop (deferred to Phase 2+)
- Automatic post-load integration (reconciliation is a separate quality pass for now)
- Lineup/substitution signal validation beyond pitcher appearance order (deferred)

## Success Criteria
- All existing games with plays data (~101+) have reconciliation discrepancy records in the database
- Pitcher attribution corrections applied to games with detectable boundary errors
- Per-pitcher FPS% match rate improves from ~55% to 90%+ (validated by re-running E-195 validation query)
- `bb data reconcile` (bare command = dry-run mode) shows discrepancy distribution without modifying data
- `bb data reconcile --execute` applies corrections and reports summary statistics
- No regressions in existing plays data for games where pitcher attribution was already correct

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-198-01 | Reconciliation detection engine + schema | DONE | None | - |
| E-198-02 | Pitcher attribution correction + execute mode | DONE | E-198-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Reconciliation Architecture

**Per-game scope**: The engine processes one game at a time via `reconcile_game(conn, game_id)`. It loads boxscore data from `player_game_pitching` / `player_game_batting` and plays data from `plays` / `play_events`, compares aggregates per signal, and writes discrepancy records.

**Module location**: `src/reconciliation/` package. Separate from `src/gamechanger/` because reconciliation reads from DB (not raw API data) and operates as a post-load quality pass. Auto-discovered by `pyproject.toml`'s `[tool.setuptools.packages.find]` with `include = ["src*"]`.

**Detection vs correction separation**: The engine has two modes:
1. **Dry-run** (default): Detects discrepancies, logs them, reports summary. No data modifications.
2. **Execute**: Detects discrepancies, applies corrections for high-confidence cases, logs everything.

**Games without plays data**: When a game has boxscore data but no rows in the `plays` table, skip it with a warning log. Do not create discrepancy records for games with no plays data.

### Schema: reconciliation_discrepancies table (migration 012)

```
reconciliation_discrepancies:
  id              INTEGER PRIMARY KEY AUTOINCREMENT
  game_id         TEXT NOT NULL REFERENCES games(game_id)
  run_id          TEXT NOT NULL          -- UUID generated once per CLI invocation (batch); all games processed in that invocation share the same run_id
  team_id         INTEGER NOT NULL REFERENCES teams(id)  -- which team's perspective (home or away)
  player_id       TEXT NOT NULL          -- player UUID for player-level signals; '__game__' sentinel for game-level signals
  signal_name     TEXT NOT NULL          -- e.g., 'pitcher_bf', 'pitcher_so', 'game_pa_count'
  category        TEXT NOT NULL          -- 'pitcher', 'batter', 'game_level'
  boxscore_value  INTEGER               -- the ground truth value
  plays_value     INTEGER               -- the plays-derived value
  delta           INTEGER               -- boxscore_value - plays_value
  status          TEXT NOT NULL CHECK(status IN ('MATCH', 'CORRECTABLE', 'CORRECTED', 'AMBIGUOUS', 'UNCORRECTABLE'))
  correction_detail TEXT                 -- JSON: what was changed (e.g., play_order range, old/new pitcher_id)
  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
  UNIQUE(run_id, game_id, team_id, player_id, signal_name)
```

**team_id column**: Every discrepancy row is scoped to one team. For pitcher signals, `team_id` is the pitcher's team. For batter signals, the batter's team. For game-level signals, one row per team (home and away get separate rows). This resolves the per-team uniqueness problem -- the boxscore has separate stat groups for each team, and the UNIQUE constraint needs `team_id` to allow both teams' signals in the same game.

**Status lifecycle**: Detection writes `MATCH`, `CORRECTABLE`, `AMBIGUOUS`, or `UNCORRECTABLE`. The correction pass (story 02, execute mode) upgrades `CORRECTABLE` → `CORRECTED` after applying the fix. If post-correction verification fails, status becomes `AMBIGUOUS` instead of `CORRECTED`.

**player_id sentinel**: Game-level signals (4A-runs, 4A-hits, 4C) use the literal string `'__game__'` as `player_id` instead of NULL. This ensures the UNIQUE constraint works correctly (SQLite treats NULLs as distinct). No FK on `player_id` because the sentinel value is not a real player.

The `correction_detail` JSON column serves as the audit trail for in-place corrections. It records the original pitcher_id, the corrected pitcher_id, and the play_order range affected.

### Pitcher Signals (Phase 1 scope)

11 of 12 pitcher attribution signals from IDEA-062 are in scope for **detection** (1J R/ER deferred to Phase 2):

| Signal | Boxscore Source | Plays Derivation | Confidence |
|--------|----------------|------------------|------------|
| 1A. Starter ID | First entry in pitching stats array (from cached boxscore JSON) | First pitcher_id in plays sequence | DEFINITIVE |
| 1B. BF per pitcher | Pitching extra `BF` | COUNT(*) plays per pitcher_id | DEFINITIVE |
| 1C. IP/Outs per pitcher | Pitching stats `IP` (as ip_outs in DB) | Count of plays where `did_outs_change = 1` per pitcher | PROBABILISTIC → status AMBIGUOUS (did_outs_change undercounts: misses caught stealing, appeal outs, and other non-PA outs; detect only, do not use for correction) |
| 1D. SO per pitcher | Pitching stats `SO` | Count of `outcome IN ('Strikeout', 'Dropped 3rd Strike')` per pitcher_id | DEFINITIVE (verify empirically on first run -- outcome strings must match exactly) |
| 1E. BB per pitcher | Pitching stats `BB` | Count of `outcome = 'Walk'` per pitcher_id (excluding Intentional Walk) | DEFINITIVE |
| 1F. HBP per pitcher | Pitching extra `HBP` | Count of `outcome = 'Hit By Pitch'` per pitcher_id | DEFINITIVE |
| 1G. Pitch count per pitcher | Pitching extra `#P` | SUM(pitch_count) per pitcher_id | DEFINITIVE |
| 1H. Total strikes per pitcher | Pitching extra `TS` | Count of `play_events` with `pitch_result IN ('strike_looking', 'strike_swinging', 'foul', 'foul_tip', 'in_play')` joined to plays via `play_id`, grouped by plays.pitcher_id | DEFINITIVE |
| 1I. Hits allowed per pitcher | Pitching stats `H` | Count of `outcome IN ('Single', 'Double', 'Triple', 'Home Run')` per pitcher_id | DEFINITIVE |
| ~~1J. R/ER per pitcher~~ | ~~Pitching stats `R`, `ER`~~ | ~~Score change attribution~~ | **DEFERRED** -- requires inherited runner tracking not present in plays data; no implementable plays_value contract. Move to Phase 2. |
| 1K. WP per pitcher | Pitching extra `WP` | Count of `play_events` with `raw_template` matching wild pitch patterns (e.g., `"advances to * on wild pitch"`, `"scores on wild pitch"`) per current pitcher | PROBABILISTIC → status AMBIGUOUS (template coverage incomplete; detect only, no correction) |
| 1L. Pitching order | Pitching stats array order from cached boxscore JSON + `player_text` decision tags (W/L/SV) | Sequence of unique pitcher_ids as they first appear in plays ordered by play_order | DEFINITIVE |

### Batter Detection Signals (detection only, no correction)

Batter attribution is more reliable (batter UUID is always in `final_details`) but validating against boxscore explains the 53.8% QAB gap and confirms the batter-side baseline. All batter signals are **detection only** -- no corrections applied.

| Signal | Boxscore Source | Plays Derivation | Confidence |
|--------|----------------|------------------|------------|
| 2A. AB per batter | Batting stats `AB` | COUNT(*) plays per batter_id WHERE outcome NOT IN ('Walk', 'Hit By Pitch', 'Sacrifice Fly', 'Sacrifice Bunt', 'Catcher''s Interference', 'Intentional Walk') | DEFINITIVE |
| 2B. H per batter | Batting stats `H` | Count of `outcome IN ('Single', 'Double', 'Triple', 'Home Run')` per batter_id | DEFINITIVE |
| 2C. SO per batter | Batting stats `SO` | Count of `outcome IN ('Strikeout', 'Dropped 3rd Strike')` per batter_id | DEFINITIVE |
| 2D. BB per batter | Batting stats `BB` | Count of `outcome = 'Walk'` per batter_id (excluding Intentional Walk) | DEFINITIVE |
| 2E. HBP per batter | Batting extra `HBP` | Count of `outcome = 'Hit By Pitch'` per batter_id | DEFINITIVE |

### Game-Level Sanity Checks

- **4A-runs. Team runs**: `SUM(player_game_batting.r)` for the team vs plays-derived runs (final play's `home_score`/`away_score` for the game, attributed to the appropriate team). Signal name: `game_runs`. One discrepancy row per team.
- **4A-hits. Team hits**: `SUM(player_game_batting.h)` for the team vs plays-derived hits (count of hit outcomes per batting team). Signal name: `game_hits`. One discrepancy row per team.
- ~~**4A-errors. Team errors**~~: **DROPPED from Phase 1.** Boxscore errors are fielding-perspective (defensive mistakes); plays errors are batting-perspective ("reaches on error"). No clean cross-check between perspectives.
- **4C. Total PA count**: `SUM(player_game_pitching.bf)` for the team's pitchers vs total plays count for that team's half-innings (plays where the team is pitching). Signal name: `game_pa_count`. Must match -- if they don't, plays were skipped or double-counted.

**Boxscore source for game-level signals**: Use DB aggregates (`SUM()` of per-player stats from `player_game_batting` / `player_game_pitching`) rather than parsing cached JSON for `team_stats`. Simpler, avoids file I/O for game-level checks, and the per-player data is already in the DB.

### Pitcher Order Extraction

**Do NOT rely on `player_game_pitching.id` AUTOINCREMENT for pitcher appearance order.** Insertion order is an implementation artifact of the game_loader, not a contractual guarantee.

Instead, extract pitcher order from the **cached boxscore JSON file**. The pitching group's `stats` array is ordered by appearance (first entry = starter, subsequent = relievers). This is the authoritative source.

**File location** (verified against crawler code 2026-04-01):
- **Member teams**: `data/raw/{season}/teams/{gc_uuid}/games/{event_id}.json` -- filename is `event_id` (= `games.game_id` in DB). Written by `GameStatsCrawler._game_path()`.
- **Scouting teams**: `data/raw/{season}/scouting/{public_id}/boxscores/{game_stream_id}.json` -- filename is `game_stream_id`. Written by `ScoutingCrawler._fetch_boxscores()`.

**Path resolution join chain**: The engine needs `season_id`, `gc_uuid`/`public_id`, and `game_id`/`game_stream_id` to construct file paths. These come from joining `games` → `teams` (via `home_team_id` or `away_team_id`): `games.game_id` for the member filename, `games.game_stream_id` for the scouting filename, `games.season_id` for the `{season}` path segment, `teams.gc_uuid` for the member path, `teams.public_id` for the scouting path.

The engine should:
1. Look up the game's `game_id`, `game_stream_id`, `season_id`, and both teams' `gc_uuid` and `public_id` from the DB
2. Try the member team path first: `data/raw/{season_id}/teams/{gc_uuid}/games/{game_id}.json`
3. If not found at that path, try `{game_stream_id}.json` in the same directory (the game_loader's dual-key index supports both naming conventions for backward compatibility)
4. If still not found, try the scouting path: `data/raw/{season_id}/scouting/{public_id}/boxscores/{game_stream_id}.json`
3. Parse the pitching group `stats` array to extract player_id order
4. If the cached JSON is missing, fall back to `player_game_pitching` ordered by `id` with a warning

### Correction Algorithm (Story 02)

The primary correction is pitcher boundary reassignment. The algorithm:

1. **Extract boxscore pitcher order**: Read cached boxscore JSON (per Pitcher Order Extraction section above). If JSON is missing, fall back to `player_game_pitching` ordered by `id` with a warning. Extract the ordered list of pitcher player_ids with their BF counts from the pitching group.
2. **Walk plays in order**: Read `plays` rows ordered by `play_order`. Assign the first `BF[pitcher_1]` plays to pitcher_1, the next `BF[pitcher_2]` plays to pitcher_2, etc. This naturally handles starter mismatches, mid-game boundary drift, and any combination of pitcher changes -- no separate starter-correction rule needed.
3. **Reassign**: For any play whose current `pitcher_id` differs from the BF-derived assignment, `UPDATE plays SET pitcher_id = ? WHERE game_id = ? AND play_order BETWEEN ? AND ?`.
4. **Verify**: After correction, re-check BF, SO, and BB counts per pitcher to confirm improvement. If post-correction BF still mismatches, mark as AMBIGUOUS.

**Edge cases**:
- Multiple pitcher changes in one inning: handled by processing pitchers in boxscore appearance order
- Mid-PA substitutions: rare at HS level; log as AMBIGUOUS if detected
- Pitcher re-entry: possible in HS baseball; detect via duplicate pitcher_id in boxscore order; log as AMBIGUOUS

### CLI Integration

```
bb data reconcile              # dry-run all games with plays data (default)
bb data reconcile --execute    # apply corrections
bb data reconcile --game-id X  # single game
bb data reconcile --summary    # show aggregate stats across ALL reconciliation records
```

### Idempotency and Execute Mode Semantics

- **`--execute` is self-contained**: Each `--execute` invocation runs fresh detection AND correction in a single pass with its own `run_id`. It does NOT consume a prior dry-run's records. There is no hidden state dependency between dry-run and execute -- they are independent operations.
- Detection is naturally idempotent (new runs get new run_ids; each run creates a complete set of discrepancy records)
- Corrections are idempotent because the same boundary logic produces the same reassignment (correcting already-correct pitcher_ids is a no-op)
- A `reconciled_at` timestamp is NOT added to the games table; instead, the presence of discrepancy records for a game_id indicates it has been reconciled.

### Accuracy Thresholds and Dashboard Suppression

**Accuracy thresholds** (from baseball-coach consultation):
- **FPS%**: 90%+ per-pitcher match rate required before surfacing on dashboards
- **Pitch count**: 95%+ accuracy required (coaches make real-time decisions based on pitch counts -- higher bar than FPS%)
- **80% is useful** for development context and early-season scouting

**Dashboard suppression advisory**: Plays-derived stats (FPS%, QAB, pitch counts) should NOT be surfaced on coaching dashboards until reconciliation confirms they meet the accuracy thresholds above. This is a downstream concern -- not implemented in this epic -- but the engine's discrepancy records provide the data for future dashboard gating. A future story should add a per-game confidence score (% of signals matching) that dashboard queries can filter on.

### Boxscore Data Availability

Confirmed: `player_game_pitching` already stores BF, pitches, total_strikes, SO, BB, IP (as ip_outs), H, R, ER, WP, HBP, and decision (W/L/SV). `player_game_batting` stores AB, R, H, RBI, BB, SO, 2B, 3B, HR, TB, HBP, SB, CS, E. No new crawling needed -- all boxscore data is already in the DB from the existing game_loader pipeline.

### Dependencies on Other Epics

- E-197 (season_id from team context, READY) ensures plays data is tagged with correct season_id. Not a hard blocker -- reconciliation operates on game_id, not season_id -- but should ship first for clean data.
- E-196 (pitching availability, READY) uses migration 010; E-197 uses migration 011. This epic uses migration 012.

## Open Questions
- None remaining. All architectural decisions locked from expert consultation.

## History
- 2026-04-01: Created (promoted from IDEA-062). Expert consultation with baseball-coach, data-engineer, and software-engineer completed.
- 2026-04-02: Set to READY after 3 review iterations (69 findings: 51 accepted, 12 dismissed, 6 duplicate/recurring).
- 2026-04-02: Set to ACTIVE, dispatch started.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 8 | 5 | 1 |
| Internal iteration 1 -- DE holistic | 7 | 5 | 0 |
| Internal iteration 1 -- Coach holistic | 4 | 4 | 0 |
| Internal iteration 1 -- SE holistic | 10 | 8 | 1 |
| Codex iteration 1 | 9 | 7 | 2 |
| Codex iteration 2 | 7 | 4 | 3 |
| Internal iteration 2 -- CR spec audit | 6 | 5 | 0 |
| Internal iteration 2 -- DE holistic | 5 | 3 | 2 |
| Internal iteration 2 -- Coach holistic | 0 | 0 | 0 |
| Internal iteration 2 -- SE holistic | 6 | 4 | 2 |
| Codex iteration 3 | 7 | 6 | 1 |
| **Total** | **69** | **51** | **12** |

### Dispatch Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-198-01 | 5 | 5 | 0 |
| Per-story CR -- E-198-02 | 3 | 3 | 0 |
| CR integration review | 1 | 1 | 0 |
| Codex code review | 4 | 3 | 1 |
| **Total** | **13** | **12** | **1** |

- 2026-04-02: All 2 stories DONE. Epic set to COMPLETED.
  - E-198-01: Reconciliation detection engine with migration 012, 11 pitcher signals, 5 batter signals, 3 game-level signals, `bb data reconcile` CLI (dry-run default).
  - E-198-02: BF-boundary pitcher attribution correction algorithm, `--execute` mode, `--summary` aggregate stats, idempotent correction, edge case handling (re-entry, single pitcher, BF mismatch).
  - Dispatch: 13 review findings (12 accepted, 1 dismissed). All corrections applied.

### Documentation Assessment
- **T1 (new feature/endpoint)**: YES -- new `bb data reconcile` CLI command with `--execute`, `--summary`, `--game-id` flags. New `src/reconciliation/` package.
- **T4 (schema changes)**: YES -- migration 012 adds `reconciliation_discrepancies` table.
- **T2, T3, T5**: No documentation impact (no architecture/deployment changes, no agent changes, no user-facing interaction changes).
- **Action**: docs-writer dispatch warranted for admin docs (`bb` CLI reference update).

### Context-Layer Assessment
- **T1 (New convention)**: YES -- reconciliation as a post-load quality pass, separate `src/reconciliation/` package outside `src/gamechanger/`. New CLI subcommand `bb data reconcile`.
- **T2 (Architectural decision)**: YES -- `src/reconciliation/` package location (reads from DB, not raw API), `reconcile_game(conn, game_id, dry_run=True)` API, detection-then-correction two-phase pattern.
- **T3 (Footgun discovered)**: NO -- dry_run=True default is safe; no unexpected pitfalls discovered.
- **T4 (Agent behavior change)**: NO -- no agent definition or skill changes.
- **T5 (Domain knowledge)**: YES -- pitcher attribution accuracy thresholds (90% FPS%, 95% pitch count), BF boundary correction algorithm, boxscore pitcher order extraction from cached JSON.
- **T6 (New CLI command)**: YES -- `bb data reconcile` with `--execute`, `--summary`, `--game-id`.
- **Action**: claude-architect dispatch warranted for T1, T2, T5, T6 (codify reconciliation architecture, CLI command, accuracy thresholds in CLAUDE.md).
