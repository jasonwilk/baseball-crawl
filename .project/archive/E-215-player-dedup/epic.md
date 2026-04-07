# E-215: Fix Player-Level Duplicates from Cross-Perspective Boxscore Loading

## Status
`COMPLETED`

## Overview
Fix same-team duplicate player entries caused by GameChanger's cross-perspective UUID mismatch. The scouting pipeline creates duplicate players when the same human appears with different `player_id` UUIDs and name formats across boxscores viewed from different team perspectives. This splits stats across two entries in reports and dashboards, understating player performance.

## Background & Context
GameChanger assigns different `player_id` UUIDs to the same physical player depending on which team's boxscore is being viewed. When the scouting pipeline crawls boxscores for a scouted team (e.g., Lincoln High), it encounters:

1. **The team's own roster/boxscore**: Returns player_id `X` with first name as initial only (e.g., "O Holbein")
2. **Another team's boxscore** (where the scouted team is the opponent): Returns player_id `Y` with full first name (e.g., "Oliver Holbein")

Both get inserted as separate `players` rows because they have different `player_id` values. This creates duplicate entries in `team_rosters`, game-level stats, season aggregates, plays, spray charts, and reconciliation data.

**Cross-perspective mechanism**: Duplicates arise when two tracked teams play each other and both are scouted. Team A's boxscores list Team B's players with one set of UUIDs; Team B's boxscores list the same players with a different set of UUIDs. The game_loader processes BOTH sides of every boxscore, so both UUID sets get inserted for the same players. The roster endpoint for each team returns yet another set of UUIDs (with initial-only first names).

**Member teams are NOT affected**: Zero duplicate pairs exist for member teams. Member teams use authenticated endpoints with consistent UUIDs. This bug is scouting/tracked-team only.

**User-reported trigger**: Jason opened a standalone report for Lincoln High and saw "O Holbein 29 PA" and "Oliver Holbein 3 PA" as separate entries -- same person, same team, split stats.

**Measured impact** (production DB):
- 120 duplicate pairs where both IDs are rostered to the same team
- 527 total duplicate pairs across the database (includes cross-team pairs that are out of scope for this epic; the merge targets the 120 same-team pairs)
- 2,932 player_game_batting rows + 703 player_game_pitching rows referencing initial-only player IDs
- 5,191 plays (batter_id) + 4,972 plays (pitcher_id) referencing initial-only IDs
- 4,513 spray_chart rows + 24,285 reconciliation_discrepancy rows affected

**Compounding bug**: The scouting loader's `_upsert_roster_player()` and roster loader's `_upsert_player()` use UNCONDITIONAL name overwrites -- they can downgrade "Oliver" back to "O" on re-runs. The game loader's `_ensure_player()` is better (only upgrades from "Unknown") but won't upgrade "O" to "Oliver".

**Expert consultation** (2026-04-06):
- **DE**: Runtime CLI merge (not migration), delete-then-update for UNIQUE conflicts, one transaction per pair, season stats recomputed after merge
- **SE**: Shared `ensure_player_row()` function with LENGTH-based name preference, prefix-matching detection, post-load dedup for prevention
- **Coach**: Simple consolidation correct (no coaching value in split stats), prefer full names always, canonical ID = roster-linked with more stat rows as tiebreaker

## Goals
- Prevent new same-team player duplicates from being created by the scouting pipeline
- Fix name-preference logic so initials never overwrite full names in any loader path
- Merge existing 120+ same-team duplicate player pairs, consolidating all stat rows under one canonical player_id
- Both opponent flow (dashboard) and reports flow (standalone) show clean, deduplicated player data

## Non-Goals
- Cross-team player identity (linking the same person across different teams/programs) -- that is E-104 / IDEA-052 territory
- Populating `gc_athlete_profile_id` -- depends on E-104 probe results
- Fixing the 256 initial-only players with no full-name counterpart (no merge target exists; acceptable per coach consultation)
- The 28 players with initial-only both first AND last name (no data quality action possible without API enrichment)
- Admin UI for player merge (the `bb data` CLI is sufficient for this operator-driven fix)
- Member team player dedup (member teams use authenticated endpoints with consistent UUIDs -- zero duplicate pairs exist for member teams; this is a scouting/tracked-team-only bug)

## Success Criteria
- Running `bb data dedup-players --dry-run` reports zero same-team duplicate pairs on a database where the merge has been executed
- No player appears twice on the same team's report or dashboard page
- Re-running the scouting pipeline on a team produces clean, deduplicated data -- the post-load sweep (E-215-04) automatically re-detects and re-merges any duplicates from cross-perspective crawl data before aggregation (merge-every-run cycle per TN-9)
- Player names show full first names where available (never downgraded to initials)
- No stat rows are silently lost through the merge -- every duplicate row is either reassigned to canonical or intentionally deleted as a UNIQUE conflict; season aggregates are recomputed from game-level data
- Season aggregates are recomputed correctly after merge (reflect the combined game-level data)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-215-01 | Canonical player upsert with name-preference logic | DONE | None | - |
| E-215-02 | Duplicate player detection query and CLI | DONE | None | - |
| E-215-03 | Player merge function and CLI execution | DONE | E-215-01, E-215-02 | - |
| E-215-04 | Post-load dedup prevention in scouting pipeline | DONE | E-215-01, E-215-02, E-215-03 | - |
| E-215-05 | Context-layer update for player dedup patterns | DONE | E-215-04 | - |

## Dispatch Team
- software-engineer
- data-engineer
- claude-architect

## Technical Notes

### TN-1: Name-Preference Rule
Update a name component only if the incoming value is strictly longer than the stored value, with "Unknown" treated as length 0. This handles all transitions correctly:
- "Unknown" -> "O" (upgrade)
- "O" -> "Oliver" (upgrade)
- "Oliver" -> "O" (no-op, preserved)
- "Oliver" -> "Oliver" (no-op)
- "Oliver" -> "Unknown" (no-op)

**`bats`/`throws` columns**: The `players` table has `bats` and `throws` columns but NO loader currently writes to them. The shared `ensure_player_row()` function does NOT need `bats`/`throws` parameters. These columns remain NULL until a future epic populates them (likely via E-104 athlete profile data).

### TN-2: Duplicate Detection Signal
Same-team duplicates are identified by:
- Both `player_id` values appear in `team_rosters` for the same `(team_id, season_id)`
- `last_name` matches (case-insensitive)
- One `first_name` is a prefix of the other (e.g., "O" is prefix of "Oliver")
- The player_id with the longer `first_name` is the canonical (keep) ID

The shorter first_name must have `LENGTH > 0` to guard against empty/blank strings matching everything as a prefix. This is safe at the HS roster scale (12-15 players per team) -- false positives from two different players with the same last name and one's first name being a prefix of the other's on the same team are vanishingly unlikely.

### TN-3: Canonical ID Selection
The player_id with the longer (fuller) first_name is canonical. If first_name lengths are equal, the player_id with more total stat rows across all tables is canonical. If still tied, the lower-sorting player_id (alphabetical) wins for determinism.

### TN-4: Merge Transaction Pattern
Each (canonical_id, duplicate_id) pair is merged in a single `BEGIN IMMEDIATE` transaction following FK-safe order. The merge function must accept a `manage_transaction` parameter (default True). When True, it opens/commits its own transaction (CLI use). When False, it uses `SAVEPOINT`/`RELEASE`/`ROLLBACK TO` for per-pair isolation within the caller's implicit transaction -- this allows individual pair failures to roll back without affecting other pairs or the caller's transaction. For tables with UNIQUE constraints that include `player_id`, use the delete-or-update pattern: check if a canonical row already exists for the same UNIQUE key; if yes, delete the duplicate's row (canonical wins -- these are the same at-bats from two perspectives, NOT additive stats); if no, UPDATE `player_id` to canonical.

**Sentinel guard**: The `reconciliation_discrepancies` table uses a sentinel `player_id = '__game__'` for game-level (non-player) discrepancies. The merge must filter `player_id != '__game__'` when updating this table to avoid corrupting sentinel rows.

**Tables with UNIQUE constraints (delete-or-update)**:
| Table | UNIQUE constraint | Conflict key | Conflict resolution |
|-------|------------------|--------------|---------------------|
| player_game_batting | (game_id, player_id) | game_id | Keep row with better `stat_completeness` (full > supplemented > boxscore_only); if tied, keep canonical |
| player_game_pitching | (game_id, player_id) | game_id | Keep row with better `stat_completeness`; if tied, keep canonical |
| player_season_batting | (player_id, team_id, season_id) | (team_id, season_id) | Delete BOTH rows; recompute from game-level data (per TN-5) |
| player_season_pitching | (player_id, team_id, season_id) | (team_id, season_id) | Delete BOTH rows; recompute from game-level data (per TN-5) |
| team_rosters | PK(team_id, player_id, season_id) | (team_id, season_id) | Keep canonical row, delete duplicate |
| reconciliation_discrepancies | (run_id, game_id, team_id, player_id, signal_name) | (run_id, game_id, team_id, signal_name) | Keep canonical row, delete duplicate |

**Tables with FK but no player UNIQUE (simple UPDATE)**:
| Table | Columns to update |
|-------|------------------|
| plays | batter_id, pitcher_id |
| spray_charts | player_id, pitcher_id |

### TN-5: Season Aggregate Recomputation
After merging game-level rows, season aggregate tables (`player_season_batting`, `player_season_pitching`) for affected player+team+season combos must be recomputed from game-level data. The merge deletes both canonical and duplicate season rows for affected combos; a follow-up recomputation rebuilds them. The recomputation logic must be self-contained in `src/db/player_dedup.py` or a shared utility -- do NOT import from `src/gamechanger/loaders/scouting_loader.py` (circular dependency risk). The recomputation queries aggregate from `player_game_batting`/`player_game_pitching` directly.

### TN-6: Merge Execution Order (within one transaction)
1. `plays` -- UPDATE batter_id, pitcher_id
2. `spray_charts` -- UPDATE player_id, pitcher_id
3. `reconciliation_discrepancies` -- delete-or-update
4. `player_game_batting` -- delete-or-update
5. `player_game_pitching` -- delete-or-update
6. `player_season_batting` -- delete (for recomputation)
7. `player_season_pitching` -- delete (for recomputation)
8. `team_rosters` -- delete-or-update
9. `DELETE FROM players WHERE player_id = ?` (the duplicate)

### TN-7: Existing Patterns to Follow
- Team merge: `src/db/merge.py` -- atomic transaction, preview/execute split, delete-conflicts-then-reassign
- Team dedup: `src/db/merge.py:find_duplicate_teams()` + `src/cli/data.py` CLI wrappers
- Canonical entity creation: `src/db/teams.py:ensure_team_row()` -- shared function, all loaders call it

### TN-8: Loader Paths to Migrate
All paths that write to the `players` table must use the shared `ensure_player_row()`:
1. `src/gamechanger/loaders/roster.py:_upsert_player()` -- UNCONDITIONAL overwrite (bug)
2. `src/gamechanger/loaders/scouting_loader.py:_upsert_roster_player()` -- UNCONDITIONAL overwrite (bug)
3. `src/gamechanger/loaders/game_loader.py:_ensure_player()` -- conditional but too conservative
4. `src/gamechanger/loaders/plays_loader.py:_ensure_player_stub()` -- stub-only
5. `src/gamechanger/loaders/spray_chart_loader.py:_ensure_stub_player()` -- stub-only
6. `src/gamechanger/loaders/season_stats_loader.py:_ensure_player_row()` -- stub-only
7. `src/gamechanger/loaders/scouting_spray_loader.py:_ensure_stub_player()` -- stub-only

### TN-9: Two-Hook Prevention Architecture
The scouting pipeline has multiple stages that create player rows, running in sequence:
1. `ScoutingLoader.load_team()` -- roster + boxscore loading (creates the primary duplicates)
2. gc_uuid resolution (no player writes)
3. Spray chart crawl + load (creates player stubs via `_ensure_stub_player()`)

A single dedup hook inside `load_team()` is insufficient because the spray loader runs afterward and can re-create deleted duplicate player stubs from cross-perspective spray data. Two hooks are needed:

**Hook 1** (inside `ScoutingLoader.load_team()`): Runs after boxscore loading, before season aggregate computation. Uses `manage_transaction=False`. Ensures aggregates are computed on deduplicated data.

**Hook 2** (in pipeline orchestrators): Runs after spray load completes in both `_scout_live()` (`src/cli/data.py`) and `run_scouting_sync()` (`src/pipeline/trigger.py`). Uses `manage_transaction=True`. Catches spray-introduced stubs.

**Spray stub orphan behavior**: When the spray loader encounters a cross-perspective player_id that was deleted by Hook 1, `ensure_player_row()` re-creates it as an "Unknown/Unknown" stub. This stub has NO `team_rosters` entry (the spray loader does not write to team_rosters). Without a roster entry, TN-2's detection query would not find it. However, Hook 2 runs the detection query again after spray load, and if both the stub and the canonical player are rostered to the same team, the pair is detected and merged. If the stub has no roster entry at all, it remains as an orphan player row referenced only by `spray_charts` -- harmless for coaching purposes (spray chart display would show "Unknown" for that player's name on those events).

The plays pipeline (`bb data crawl --crawler plays` + `bb data load --loader plays`) runs independently of `bb data scout` -- it is NOT wired into these orchestrators. Plays-introduced stubs are cleaned up by the next `bb data scout` run or by manual `bb data dedup-players --execute`.

## Open Questions
- None -- expert consultation resolved all open questions.

## History
- 2026-04-06: Created. Triggered by user-reported duplicate player entries on Lincoln High standalone report. Expert consultation with DE, SE, and Coach completed same day.
- 2026-04-06: Set to READY after spec review and refinement.
- 2026-04-07: Dispatch started. E-215-05 (context-layer) added after initial DRAFT based on user requirement. Plays/spray pipeline re-contamination gap discovered during post-internal-review investigation and addressed in E-215-04 revision (two-hook architecture).
- 2026-04-07: All 5 stories implemented and reviewed. CR integration review clean. Codex code review skipped (epic branch not accessible to Codex sandbox). Epic COMPLETED.

### Spec Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 8 | 4 | 4 |
| Internal iteration 1 -- Holistic team (PM) | 6 | 5 | 1 |
| Internal iteration 1 -- Holistic team (SE) | 8 | 5 | 3 |
| Internal iteration 1 -- Holistic team (DE) | 4 | 2 | 2 |
| Internal iteration 1 -- Holistic team (Coach) | 4 | 3 | 1 |
| Post-review deep investigation (plays/spray gap) | 1 | 1 | 0 |
| Codex iteration 1 | 7 | 5 | 2 |
| Codex iteration 2 | 5 | 3 | 2 |
| **Total** | **43** | **28** | **15** |

### Implementation Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-215-01 | 1 | 0 | 1 |
| Per-story CR -- E-215-02 | 1 | 1 | 0 |
| Per-story CR -- E-215-03 | 0 | 0 | 0 |
| Per-story CR -- E-215-04 | 1 | 1 | 0 |
| CR integration review | 0 | 0 | 0 |
| **Total** | **3** | **2** | **1** |

(E-215-05 was context-layer only -- PM verified, no CR. Codex code review skipped.)

### Documentation Assessment
- Trigger 1 (new feature ships): **Yes** -- new `bb data dedup-players` CLI command and player dedup pipeline.
- Trigger 2 (architecture/deployment changes): No.
- Trigger 3 (agent changes): No.
- Trigger 4 (schema changes): No (no new migrations; runtime merge only).
- Trigger 5 (epic changes how system works): **Yes** -- scouting pipeline now includes automatic post-load dedup.
- **Verdict**: Triggers 1 and 5 fire. However, the relevant documentation is all context-layer (CLAUDE.md Commands, data-model.md) which was already updated by E-215-05. No `docs/admin/` or `docs/coaching/` files require updates -- the dedup CLI is an operator tool (documented in CLAUDE.md), not a coaching-facing feature. No docs-writer dispatch needed.

### Context-Layer Assessment
Context-layer impact addressed by E-215-05. Per-trigger verdicts:
1. **New convention/pattern**: Yes -- `ensure_player_row()` canonical upsert pattern. Codified in CLAUDE.md Architecture (E-215-05 AC-1).
2. **Architectural decision**: Yes -- cross-perspective UUID duality is permanent API property; two-hook dedup architecture. Codified in data-model.md (E-215-05 AC-3, AC-5).
3. **Footgun/failure mode**: Yes -- merge-every-run cycle, plays pipeline dedup gap. Codified in data-model.md (E-215-05 AC-5, AC-6).
4. **Agent behavior change**: No.
5. **Domain knowledge**: Yes -- `gc_athlete_profile_id` unpopulated status. Codified in data-model.md (E-215-05 AC-4).
6. **New CLI command**: Yes -- `bb data dedup-players`. Codified in CLAUDE.md Commands (E-215-05 AC-2).
- **Verdict**: 5 of 6 triggers fire. All addressed by E-215-05. No additional claude-architect dispatch needed.

### Ideas Backlog Review
Reviewed `/.project/ideas/README.md`. No ideas are directly unblocked by E-215. IDEA-052 (Familiar Faces Indicator) touches cross-team player identity but depends on E-104, not E-215. IDEA-043 (Fuzzy Duplicate Team Detection) is team-level, not player-level. No promotions or status changes triggered.

### Vision Signals Check
`docs/vision-signals.md` has unprocessed signals (last entry 2026-04-02). No new signals from E-215 to add. The user may want to "curate the vision" at a convenient pause point.
