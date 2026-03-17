# E-117: Loader Stat Population — Full Endpoint Coverage

## Status
`READY`

## Overview
Expand game_loader, season_stats_loader, and scouting_loader to populate all stat columns that the E-100 schema supports and the respective API endpoints provide. Currently ~80+ schema columns remain permanently NULL because the loaders only map a legacy subset. This epic closes the gap between schema capability and actual data flow.

## Dependencies
- **E-116** (E-100 Codex Review Bug Fixes): COMPLETED (archived 2026-03-17). The YAML `TeamRef(id=0)` fix has shipped. E-117 is unblocked.

## Background & Context
E-100 (Team Model Overhaul) created the DDL with complete stat columns per endpoint but explicitly deferred population as a Non-Goal: "New stat columns... added to the DDL but NOT populated by any E-100 story. Population is follow-up epic scope." Post-dev Codex review (2026-03-16) confirmed the gap. SE and DE investigation classified the missing columns and confirmed the DDL is correct — all fixes are in Python loader code, zero schema changes.

Promoted from IDEA-028 (Loader Stat Population). Expert consultation with SE and DE completed during triage (2026-03-16).

**Full data re-seed planned.** After E-117 ships, the user will re-crawl all data from scratch. This means E-117 doesn't need to worry about migrating existing rows or backward compatibility with stale data — fresh data will flow through the expanded loaders.

**Member vs. opponent team distinction:** The season-stats API endpoint (`GET /teams/{team_id}/season-stats`) returns Forbidden for non-owned (opponent) teams. E-117-02 and E-117-03 (season stats expansion) apply only to member teams. Opponents get season stats via the scouting pipeline (E-117-04), which aggregates boxscore data — not the season-stats API.

**Expert consultation (SE, 2026-03-16):** game_stream_id threading is small (two extra lines + one parameter); game_loader batting+pitching should be one story (same file, same code paths); season_stats_loader should split batting/pitching (75-column PR is unreviable); scouting cascade is a separate dependent story; test fixtures should expand existing fixtures with full column assertions; bats/throws data source is unknown — defer.

**Expert consultation (DE, 2026-03-16):** Column counts confirmed (6+6 game, 37 season batting, 15+23 season pitching). Unconfirmed pitching columns (23) should be included optimistically via dict.get() — marginal cost zero, columns already in DDL. No migration needed. stat_completeness should be set to 'full' for season_stats_loader (API-sourced rows), left as default 'boxscore_only' for game_loader and scouting_loader. Structural columns (batting_order, positions_played, is_primary, decision) require different logic (text parsing, array-position tracking) — keep out of scope.

## Goals
- game_loader populates all 12 stat columns available from the boxscore endpoint (6 batting + 6 pitching) plus threads `game_stream_id` to the games table
- season_stats_loader populates all confirmed batting columns (~37) and all confirmed + optimistic pitching columns (~38) from the season-stats endpoint
- season_stats_loader sets `stat_completeness = 'full'` for API-sourced rows (accurate provenance)
- Scouting loader aggregate queries sum the newly populated game-level columns
- Stale "not in schema" comments in game_loader are corrected
- Loader tests cover every newly populated column with explicit value assertions

## Non-Goals
- **Structural boxscore columns**: `batting_order`, `positions_played`, `is_primary` (player_game_batting) and `decision` (player_game_pitching) require array-position tracking and text parsing — different logic pattern than stat dict mapping. Separate follow-up.
- **bats/throws on players**: Data source endpoint unknown. Requires api-scout confirmation before loader work can be scoped.
- **L/R split data population**: Covered by IDEA-029. Separate data sourcing challenge.
- **Spray chart ingestion**: Covered by IDEA-009. Different API endpoint entirely.
- **Stat blending logic**: Covered by IDEA-031. This epic writes `'full'` or `'boxscore_only'` — it does not produce the `'supplemented'` state.
- **Fielding, catcher, pitch type tables**: Covered by IDEA-030. No tables or loaders exist yet.

## Success Criteria
- `player_game_batting` rows include non-NULL values for `r`, `tb`, `hbp`, `shf`, `cs`, `e` when the boxscore provides them
- `player_game_pitching` rows include non-NULL values for `r`, `wp`, `hbp`, `pitches`, `total_strikes`, `bf` when the boxscore provides them
- `games` rows include `game_stream_id` from the boxscore file stem
- `player_season_batting` rows include all 37 confirmed endpoint columns when the API provides them
- `player_season_pitching` rows include all 15 confirmed + 23 optimistic endpoint columns mapped via `defense.get()` — populated when the API provides them, NULL when absent (including `gp`, which lives in `general` not `defense`)
- Season stat rows sourced from the API have `stat_completeness = 'full'`
- Scouting-derived season stat rows aggregate the newly populated game-level columns
- All stale "not in schema" comments in game_loader are corrected or removed
- Loader tests assert specific values for every newly populated column
- All existing tests pass

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-117-01 | Game loader: full boxscore stat coverage + game_stream_id | TODO | None | - |
| E-117-02 | Season stats loader: batting column expansion (member teams) | TODO | None | - |
| E-117-03 | Season stats loader: pitching column expansion (member teams) | TODO | E-117-02 | - |
| E-117-04 | Scouting loader: aggregate query expansion (opponent teams) | TODO | E-117-01 | - |

## Dispatch Team
- software-engineer (E-117-01, E-117-02, E-117-03, E-117-04)

## Technical Notes

### Column Inventory

Source: E-100 Technical Notes "Complete Stat Column Reference" cross-referenced with DE investigation (2026-03-16).

#### player_game_batting — 6 missing columns (all in boxscore endpoint)

| Column | Category | Current loader disposition | Fix |
|--------|----------|--------------------------|-----|
| `r` | Main stat (always present) | `_BATTING_SKIP_DEBUG` — logged and dropped | Move to mapping dict |
| `tb` | Extra stat (sparse) | `_BATTING_SKIP_DEBUG` + `_BATTING_EXTRAS_SKIP_DEBUG` | Move to mapping dict |
| `hbp` | Extra stat (sparse) | `_BATTING_EXTRAS_SKIP_DEBUG` | Move to mapping dict |
| `shf` | Extra stat (sparse) | Not referenced — silently dropped | Add to mapping dict |
| `cs` | Extra stat (sparse) | `_BATTING_EXTRAS_SKIP_DEBUG` | Move to mapping dict |
| `e` | Extra stat (sparse) | `_BATTING_EXTRAS_SKIP_DEBUG` | Move to mapping dict |

Note: `r` and `tb` have stale "not in schema" comments — these are incorrect (E-100-01 added the columns).

**SHF boxscore discrepancy:** The glossary's Boxscore Column Groups (from JS bundle) lists SHF in BATTING_EXTRA, but the boxscore endpoint doc (`docs/api/endpoints/get-game-stream-processing-game_stream_id-boxscore.md`) does not list SHF in the observed batting extras — it lists E there instead (glossary puts E under FIELDING_EXTRA). The `dict.get()` approach handles both correctly: if SHF appears in the response, it gets saved; if not, NULL. Same for E. The SE should use `dict.get()` for both and not assume either will always be present.

#### player_game_pitching — 6 missing columns (all in boxscore endpoint)

| Column | Category | Current loader disposition | Fix |
|--------|----------|--------------------------|-----|
| `r` | Main stat (always present) | `_PITCHING_SKIP_DEBUG` — logged and dropped | Move to mapping dict |
| `wp` | Extra stat (sparse) | `_PITCHING_EXTRAS_SKIP_DEBUG` | Move to mapping dict |
| `hbp` | Extra stat (sparse) | `_PITCHING_EXTRAS_SKIP_DEBUG` | Move to mapping dict |
| `pitches` (#P) | Extra stat (sparse) | `_PITCHING_EXTRAS_SKIP_DEBUG` | Move to mapping dict |
| `total_strikes` (TS) | Extra stat (sparse) | `_PITCHING_EXTRAS_SKIP_DEBUG` | Move to mapping dict |
| `bf` | Extra stat (sparse) | `_PITCHING_EXTRAS_SKIP_DEBUG` | Move to mapping dict |

Note: `hr` is correctly excluded — E-100 Technical Notes confirm "HR allowed is not in the boxscore pitching extras."

#### games — 1 missing column

| Column | Source | Current disposition | Fix |
|--------|--------|--------------------|----|
| `game_stream_id` | `GameSummaryEntry.game_stream_id` (file stem) | Value exists in loader but not threaded to `_upsert_game()` | Add parameter + INSERT column |

#### player_season_batting — 37 missing confirmed columns

**Standard batting (22):** pa, singles, r, sol, hbp, shb, shf, gidp, roe, fc, ci, pik, cs, tb, xbh, lob, three_out_lob, ob, gshr, two_out_rbi, hrisp, abrisp

**Advanced batting (15):** qab, hard, weak, lnd, flb, gb, ps, sw, sm, inp, full, two_strikes, two_s_plus_3, six_plus, lobb

Currently populated (10): gp, ab, h, doubles, triples, hr, rbi, bb, so, sb

#### player_season_pitching — 38 missing columns

**Confirmed-in-endpoint (15):** gs, bf, bk, wp, hbp, svo, sb, cs, go, ao, loo, zero_bb_inn, inn_123, fps, lbfpn

**Expected-in-API / optimistic (23):** gp, w, l, sv, bs, r, sol, lob, pik, total_balls, lt_3, first_2_out, lt_13, bbs, lobb, lobbs, sm, sw, weak, hard, lnd, fb, gb

Currently populated (9): gp_pitcher, ip_outs, h, er, bb, so, hr, pitches, total_strikes

**Optimistic mapping approach (DE recommendation):** All 23 "expected but not confirmed" columns are already in the DDL as nullable. Use `defense.get("KEY")` — if the API omits a field, `None` → NULL. Correct behavior either way. No reason to write a second story later for 23 more `dict.get()` calls.

**CRITICAL — TB pitching context:** In the defense (pitching) section of the season-stats response, `TB` means "Total Balls" (not "Total Bases"). The schema column is `total_balls` in `player_season_pitching`. The glossary note at line 426 confirms: "TB has two distinct meanings depending on context: Total Bases in batting stats, and Total Balls in pitching stats." Map `defense.get("TB")` → `total_balls`. See IDEA-040 for api-scout investigation of which optimistic pitching columns the API actually returns.

**GP vs GP:P ambiguity:** The optimistic 23 list includes `gp` (schema: "games played, all roles" — `player_season_pitching` line 325). This is distinct from `gp_pitcher` (schema: "games pitched" — line 301, already mapped from `defense.get("GP:P")`). However, `GP` (games played) appears in the `general` section of the API response (`stats_data.players.<uuid>.stats.general`), NOT in `defense`. Using `defense.get("GP")` will likely return None — this is acceptable under the optimistic mapping approach (nullable column, NULL is correct). The implementing SE should be aware that `gp` may always be NULL in pitching season stats until a future mapping revision sources it from `general.GP`. This is not a bug — it's expected optimistic behavior.

### API Field Name Mapping

The season-stats API response uses abbreviation keys (e.g., `"GP"`, `"AB"`, `"2B"`) that may differ from schema column names (e.g., `gp`, `ab`, `doubles`). The authoritative mapping is in `docs/gamechanger-stat-glossary.md` (API field name mapping table). The implementing agent must consult this glossary to map API keys to schema column names correctly.

### stat_completeness Provenance (DE Recommendation)

- **season_stats_loader**: Set `stat_completeness = 'full'` for rows sourced from the season-stats API endpoint. These rows represent authoritative aggregate data, not boxscore derivations.
- **game_loader**: Leave default `'boxscore_only'` unchanged. Per-game rows are always sourced from boxscores.
- **scouting_loader**: Leave default `'boxscore_only'` unchanged. Scouting season stats are derived from aggregating boxscore data.
- The `'supplemented'` state is IDEA-031 (Stat Blending Logic) scope — not this epic.

### Future Enrichment Path (Architectural Principle)

E-117 establishes the first layer of the stat compilation pyramid. The game_loader owns row creation (INSERT) for per-game stat tables. A future play-by-play compilation pipeline (IDEA-041) would own row enrichment (UPDATE) — adding advanced stats derived from play-by-play data and updating `stat_completeness` from `'boxscore_only'` to `'supplemented'`.

**Critical constraint for E-117-01:** `stat_completeness` must NOT appear in the game_loader's INSERT or ON CONFLICT UPDATE clauses. The schema default (`'boxscore_only'`) handles the INSERT correctly. Omitting it from ON CONFLICT UPDATE means re-running the boxscore loader after play-by-play enrichment will update counting stats (which the boxscore is authoritative for) without overwriting the `stat_completeness` value or any enriched columns not in the boxscore loader's column list. The ON CONFLICT UPDATE is column-scoped — only columns listed in the SET clause are overwritten.

This same principle applies to the scouting_loader (E-117-04): do not explicitly set `stat_completeness` — let the schema default handle it.

### Scouting Loader Cascade

`scouting_loader.py` computes season aggregates from `player_game_batting` and `player_game_pitching` rows via `_compute_batting_aggregates` and `_compute_pitching_aggregates`. After E-117-01 populates new game-level columns, these aggregate queries must be expanded to SUM the new columns. The aggregated results are written to `player_season_batting` and `player_season_pitching` — the same tables that season_stats_loader writes to (but for opponent teams via boxscore derivation rather than API data).

Cascade columns:
- **Batting**: r, tb, hbp, shf, cs (5 of the 6 new game-level columns — `e` has no corresponding column in `player_season_batting`, so it is NOT aggregated)
- **Pitching**: r, wp, hbp, pitches, total_strikes, bf

**NULL handling for sparse aggregates:** Use plain `SUM(col)` (not `COALESCE`). NULL season total = "no data" (stat never recorded). 0 = "zero confirmed occurrences." SQL `SUM()` correctly returns NULL when all inputs are NULL.

**Boxscore-only limitation:** Scouting aggregates can only include basic counting stats that appear in the boxscore response. Advanced stats (QAB, pitches seen per batter, contact quality, swing metrics, etc.) are NOT in boxscores — they require play-by-play parsing. This means scouting-derived opponent season stats will have fewer populated columns than member team season stats (which come from the season-stats API, where GC has already compiled advanced stats). Achieving full stat parity for opponents requires a future play-by-play compilation pipeline (see IDEA-041).

### Test Strategy (SE Recommendation)

- Expand existing test fixtures with new fields (non-zero values for each new column)
- **Test fixtures should use realistic data** shaped from actual GameChanger API response structures. Reference the API endpoint docs at `docs/api/endpoints/` for response shapes: `get-game-stream-processing-game_stream_id-boxscore.md` for E-117-01 fixtures, `get-teams-team_id-season-stats.md` for E-117-02/03 fixtures. The user has offered a data dump if needed.
- Assert exact values for every newly added column on at least one representative player
- For nullable sparse extras: include at least one test case with non-zero values and one with zero/absent
- No blanket NULL sweep needed — schema enforces NOT NULL for structural columns; new stat columns are nullable by design

## Expert Consultation Notes
- **api-scout not consulted (intentional).** The SHF boxscore discrepancy and optimistic pitching column availability are API behavior questions that would normally trigger api-scout consultation. However, the `dict.get()` approach makes these questions non-blocking: if a field is present, it gets saved; if absent, NULL. The correct behavior is the same regardless of the answer. Actual API field verification is deferred to IDEA-040 (post-E-117 investigation) rather than blocking this epic on live API probing.

## Open Questions
- **bats/throws data source**: Which endpoint returns player handedness? Roster, season-stats, player-stats, or none? Needs api-scout confirmation before a loader story can be scoped. Not blocking this epic — captured separately.
- ~~**shf and e in scouting aggregates**~~: **RESOLVED.** `shf` IS in `player_season_batting` (DDL line 246) — include in aggregation. `e` is NOT in `player_season_batting` (only in `player_game_batting` at line 176) — exclude from aggregation. E-117-04 updated: 5 batting cascade columns (r, tb, hbp, shf, cs), not 6.

## History
- 2026-03-16: Created. Promoted from IDEA-028. Expert consultation with SE and DE completed during E-100 Codex review triage session. Column inventories confirmed, story structure agreed.
- 2026-03-16: User approved initial scope.
- 2026-03-16: Refinement pass. Incorporated user decisions: E-116 as hard prerequisite (TeamRef fix must ship first); full data re-seed planned (no migration concerns); opponent season stats confirmed as boxscore-aggregation-only (season-stats API is Forbidden for opponents); 23 optimistic pitching columns approved with dict.get(); test fixtures should use realistic data from API response shapes. Noted SHF boxscore discrepancy (glossary vs endpoint doc). Added TB pitching-context disambiguation. Created IDEA-040 for optimistic pitching column API investigation. Reverted to DRAFT pending user review.
- 2026-03-16: SE+DE consultation during refinement. DE caught critical error: `e` (errors) has NO column in `player_season_batting` — only in `player_game_batting`. Corrected E-117-04 AC-1 from 6 to 5 batting cascade columns (r, tb, hbp, shf, cs). SE confirmed all API key→column mappings and flagged that `TS` (total_strikes) may not appear in season-stats defense response (not in endpoint doc, though glossary lists it). Existing loader already maps it — pre-existing behavior, not E-117 scope. IDEA-040 should verify.
- 2026-03-16: User insight on boxscore-only limitation. Added Non-Goals section to E-117-04 explicitly scoping it to boxscore-available counting stats only — advanced stats (QAB, contact quality, swing metrics, etc.) require play-by-play parsing. Added boxscore-only limitation note to epic Technical Notes (Scouting Loader Cascade). Created IDEA-041 (Play-by-Play Stat Compilation Pipeline) — the user's vision for achieving full stat parity between owned and opponent teams via play-by-play parsing and compilation.
- 2026-03-16: Final refinement pass. Added "Future Enrichment Path" architectural principle to Technical Notes — documents boxscore-INSERT / play-by-play-UPDATE ownership model and stat_completeness preservation constraint. Added AC-12 to E-117-01 requiring stat_completeness NOT be in INSERT/ON CONFLICT UPDATE (preserves future enrichment). Updated E-117-04 AC-3 with same principle. Flagged GP vs GP:P mapping ambiguity in Technical Notes and E-117-03 — `GP` (games played all roles) is in `general` section, not `defense`; `defense.get("GP")` will return None (acceptable under optimistic approach). Verified no missing ideas or uncaptured vision signals.
- 2026-03-17: Refinement pass. E-116 completed and archived — all blocking dependencies resolved, updated all story dependency sections. Added AC-13 to E-117-01: remove dead `_PlayerPitching.hr` field (no schema column, never used in upsert). Renumbered AC-14 (was AC-13: all existing tests pass). Verified all column inventories against current schema DDL — 6+6 game, 37 season batting, 15+23 season pitching all match. Verified all file paths and test file paths exist. Confirmed no file conflicts with E-120. Set status to READY.
- 2026-03-17: Codex spec review triage (2 findings). P1 E-117-04 ON CONFLICT UPDATE omission: FIX — updated AC-1/AC-2 to require columns in SELECT, INSERT, and ON CONFLICT UPDATE (not just SELECT and INSERT). Updated Technical Approach to call out the three-place requirement. Added AC-6 (rerun idempotency test), renumbered AC-7 (was AC-6: all existing tests pass). P2 E-117-03 optimistic column test weakness: FIX — strengthened AC-7 to require exact value assertions for optimistic columns (same standard as confirmed), not just generic present/absent checks. Epic Success Criteria already says "assert specific values for every newly populated column" — consistent, no epic change needed.
- 2026-03-16: Codex spec review triage (5 findings). P1 gp sourcing conflict: FIX — updated E-117-03 AC-2 to acknowledge gp will be NULL (defense.get returns None), explicitly prohibit cross-section mapping (follow-up scope), updated epic Success Criteria. P2 TB mapping not tested: FIX — added E-117-03 AC-8 requiring specific TB→total_balls test. P2 NULL vs zero ambiguity: FIX — specified plain SUM() (not COALESCE) in E-117-04 Technical Approach and epic TN, added NULL-specific test cases to AC-4/AC-5. P2 api-scout consultation: DISMISS — dict.get() makes API behavior questions non-blocking; deferred to IDEA-040. P3 column list duplication: DISMISS — intentional for story self-containment; drift risk low (stories written together).
