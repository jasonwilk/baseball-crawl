# E-204: Starter vs. Relief Appearance Tracking

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Add `appearance_order` to `player_game_pitching` so the system can distinguish starters from relievers. This unlocks a combined GS/GR (Games Started / Games Relieved) column on all pitching season surfaces (per TN-4), appearance-order sorting on game boxscores, and lays the foundation for future role-split analytics and probable starter identification.

## Background & Context
The boxscore JSON from GameChanger lists pitchers in appearance order (starter first, then relievers), but the game loader currently discards this order. The reconciliation engine (`src/reconciliation/engine.py`) already parses pitcher order via `_parse_pitching_order()` for its own purposes -- this is a reference implementation.

Coach consultation confirmed that GS is the single most actionable pitching stat for understanding a staff composition ("Martinez has 8 starts in 10 appearances -- he is your ace"). Workload interpretation also depends on role context: a starter at 85 pitches is normal, a reliever at 85 is a red flag. Member teams already have `player_season_pitching.gs` populated from the GC season-stats API endpoint; scouting/tracked teams do not -- they need GS computed from `appearance_order`.

**Expert consultation completed**: baseball-coach (coaching priorities and display preferences), data-engineer (schema design, backfill strategy, migration approach), software-engineer (loader modification, display surface inventory, scouting loader delegation).

## Goals
- Store pitcher appearance order for every game pitching row (new loads and backfilled historical data)
- Display a combined GS/GR column (e.g., `8/5`) on all pitching season surfaces (per TN-4) with delivery parity (dashboard + reports)
- Sort game boxscore pitching lines by appearance order instead of alphabetically

## Non-Goals
- **Role-split analytics** (ERA/K9/BB9 as starter vs. reliever separately) -- future epic after this foundation is in place
- **Probable starter identification** for opponent scouting (e.g., "who started their last 3 games?") -- future epic, requires `appearance_order` foundation from this epic
- **Different workload flag thresholds** for starters vs. relievers -- future enhancement
- **Cross-season role tracking** (player moved from reliever to starter across seasons) -- longitudinal feature, deferred
- **Denormalized `is_starter` column** -- derived at query time as `appearance_order = 1`; no separate stored column
- **Middle reliever vs. closer distinction** (GS/GMR/GC) -- over-fitting for HS level; GS/GR is sufficient

## Success Criteria
- All new game loads (member, scouting, standalone reports) populate `appearance_order` on `player_game_pitching`
- Existing historical rows are backfillable from cached boxscore JSON via a CLI command
- A combined GS/GR column (e.g., `8/5`) appears on all pitching season surfaces (per TN-4) with correct values derived from `appearance_order`
- Game boxscore pitching lines are sorted by appearance order (starter first, then relievers in order)
- Zero values display explicitly (`0/5` for a pure reliever, `8/0` for a pure starter) -- zero is data, not a gap

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-204-01 | Schema + Loader Forward-Fill | TODO | None | - |
| E-204-02 | Backfill Existing Rows | TODO | E-204-01 | - |
| E-204-03 | GS/GR Display + Appearance-Order Sorting | TODO | E-204-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Boxscore Pitcher Ordering
The boxscore JSON `stats` array under each team's `pitching` group is ordered by appearance (starter first). This is confirmed by the reconciliation engine's `_parse_pitching_order()` at `src/reconciliation/engine.py` lines 964-1005, which navigates `boxscore["groups"]` -> pitching section -> `section["stats"]` to extract `player_id` in order.

The game loader's `_load_pitching_group()` at `src/gamechanger/loaders/game_loader.py` line 823 already iterates this array in order but currently discards the index. Adding `enumerate(..., start=1)` captures the appearance order with no structural changes.

### TN-2: Scouting Loader Delegation
The scouting loader (`src/gamechanger/loaders/scouting_loader.py`) delegates per-game loading to `GameLoader.load_file()`. Any change to `_load_pitching_group()` and `_upsert_pitching()` automatically flows through to scouting loads. No separate scouting loader modification is needed for the INSERT path.

### TN-3: GS Data Sources by Team Type
- **Member teams**: `player_season_pitching.gs` is already populated from the GC season-stats API endpoint (`defense.get("GS")`). This is the authoritative source. No change needed for member season GS.
- **Scouting/tracked teams**: The season-stats endpoint returns Forbidden for non-owned teams. GS must be computed from `appearance_order` in `_compute_pitching_aggregates()` at `src/gamechanger/loaders/scouting_loader.py`. After backfill, re-running `bb data scout` (scouting load phase) recomputes aggregates including GS.

### TN-4: Display Surface Inventory
Three independent query sites need `gs` added to their SELECT lists:

| Surface | Query/Code Location | Change Type |
|---------|-------------------|-------------|
| Dashboard team pitching | `src/api/db.py` `get_team_pitching_stats()` | Add `gs` to SELECT (not currently included) |
| Dashboard opponent detail | `src/api/db.py` `get_opponent_scouting_report()` | Add `gs` to pitching SELECT (not currently included) |
| Dashboard opponent print | `src/api/db.py` `get_opponent_scouting_report()` (same function) | Same |
| Dashboard game detail | `src/api/db.py` `get_game_box_score()` | Sort by `appearance_order NULLS LAST` |
| Standalone report pitching | `src/reports/generator.py` `_query_pitching()` | Add `gs` to SELECT (not currently included) |
| Standalone report rendering | `src/reports/renderer.py` + `src/api/templates/reports/scouting_report.html` | Include GS/GR in rendered output |
| Dashboard templates (3) | `team_pitching.html`, `opponent_detail.html`, `opponent_print.html` | Add GS/GR column / th+td |
| Dashboard game template | `game_detail.html` | Appearance-order sort reflected |

### TN-5: Backfill Path Resolution
Cached boxscore JSON lives at two path patterns:
- Member teams: `data/raw/{season_id}/teams/{gc_uuid}/games/{game_id_or_stream_id}.json`
- Scouting teams: `data/raw/{season_id}/scouting/{public_id}/boxscores/{game_stream_id}.json`

The reconciliation engine's `_extract_pitcher_order()` at lines 895-952 already handles this path resolution logic (tries member path first, falls back to scouting path). The backfill story should reuse this logic.

### TN-6: Idempotency
The backfill script should only UPDATE rows where `appearance_order IS NULL`. This makes it safe to re-run and allows incremental backfill as more cached boxscores become available.

### TN-7: GS/GR Display Format
The display column uses a combined `GS/GR` format showing starts and relief appearances as a single value:
- **Header**: `GS/GR`
- **Value**: `{starts}/{relief}` (e.g., `8/5` = 8 starts, 5 relief appearances)
- **Derivation**: GS = `player_season_pitching.gs` (from GC API for member teams, from `appearance_order` aggregation for scouting teams); GR = `g - gs`
- **Placement**: After G (games), before IP. Column order: `G | GS/GR | IP | ...`
- **Zero handling**: Always show explicit zeros (`0/5` for pure reliever, `8/0` for pure starter). Zero is information, not missing data. Never use `—` or blank for zero.
- **NULL handling**: If `gs IS NULL` (no data available for this pitcher), display `—` to indicate unknown. Otherwise display `{gs}/{g - gs}`. For scouting teams, `gs` may be undercounted if backfill is incomplete -- this resolves after running the backfill (E-204-02) and re-aggregating.

This format was refined from an initial GS-only proposal through user iteration (GS/GMR/GC was too complex for HS level).

### TN-8: Post-Deployment Operational Sequence
After all three stories ship, the operator runs the backfill and re-aggregation in order:
1. Deploy E-204-01 (schema + loader) and E-204-03 (display + scouting aggregation)
2. Run `bb data backfill-appearance-order` (E-204-02) to populate historical rows
3. Run `bb data scout` to recompute scouting season aggregates (picks up GS from backfilled `appearance_order`)

Step 3 is necessary because `player_season_pitching.gs` for tracked teams is computed at scouting-load time from `appearance_order` (per TN-3). Without step 3, tracked teams show stale GS values until the next scouting sync.

## Open Questions
- None (all resolved during discovery)

## History
- 2026-04-03: Created. Expert consultation: baseball-coach (coaching priorities), data-engineer (schema + backfill), software-engineer (loader + display surfaces). Display format refined through user iteration: GS-only -> GS/GMR/GC -> GS/GR. Coach validated GS/GR format and placement.
- 2026-04-03: Set to READY after review and refinement.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 8 | 7 | 1 |
| Internal iteration 1 — Coach holistic | 3 | 1 | 2 |
| Internal iteration 1 — PM self-review | 3 | 2 | 1 |
| Internal iteration 1 — SE holistic | 5 | 3 | 2 |
| Internal iteration 1 — DE holistic | 0 | 0 | 0 |
| Codex iteration 1 | 5 | 3 | 2 |
| **Total (deduplicated)** | **16** | **12** | **4** |

Key fixes from review: wrong function name (`get_game_boxscore` → `get_game_box_score`), GR derivation standardized to `g - gs`, opponent query surface corrected (`get_opponent_scouting_report()` not `get_team_pitching_stats()`), report template added to file list, ORDER BY team_id grouping specified, post-backfill re-aggregation contracted in AC-5 and TN-8.
