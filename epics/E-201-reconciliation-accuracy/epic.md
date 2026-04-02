# E-201: Close Reconciliation Accuracy Gaps

## Status
`READY`

## Overview
Close every actionable accuracy gap in the plays-vs-boxscore reconciliation engine. Five targeted fixes in `src/reconciliation/engine.py` raise all cross-source reconciliation signals (pitcher and batter stats) to 99%+ match rates and convert two unreliable game-level signals (`game_runs`, `game_pa_count`) to data-availability checks. ~35 lines of code changes. This unblocks E-199 (plays-derived stats in standalone reports), which depends on reconciliation being accurate before integrating it into the report pipeline.

## Background & Context
E-198 built the reconciliation engine and BF-boundary correction algorithm. An 8-round investigation (`.project/research/E-198-accuracy-gaps.md`) by Claude and Codex identified root causes and designed fixes for every remaining gap:

- **Pitcher pitch count (88.1%)**: The plays endpoint systematically omits HBP terminal pitches and Runner Out pitch sequences. Rather than fixing each per-PA gap, the boxscore `#P` and `TS` values are authoritative when pitcher attribution is confirmed correct (BF + SO + BB all match = 97.1% of pitchers).
- **Pitcher BB (97.5%)**: `Intentional Walk` is a distinct outcome not included in the BB outcome set. GC boxscore BB stat includes IBB.
- **Batter BB (99.5%)**: Same IBB root cause as pitcher BB.
- **Game runs (93.1%)**: Two root causes -- courtesy runners score runs not in any player's batting R stat, and abandoned PAs have score changes not captured in the plays table.
- **Game PA count (99.0%)**: Abandoned final PAs counted in boxscore BF but discarded by the plays parser.

**Irreducible floor**: 2 gaps from scorekeeper Error→Hit corrections in one game. These cannot be fixed algorithmically.

No expert consultation required for domain experts beyond the research already completed in E-198. The research doc contains 8 rounds of validated findings with SQL verification against the live database.

**Expert consultations completed:**
- **Software-engineer**: Confirmed all 5 fix locations are correct. Confirmed Fix 2+3 are one code change (shared `_BB_OUTCOMES` constant). Confirmed 1 story is right sizing (~35 lines, single file). Clarified Fix 1 is detection-layer only (supplements plays-side value in discrepancy records, does NOT write back to `plays` table). Fix 4 needs `home_score`/`away_score` passed to `_check_game_level_signals()` as params.
- **Data-engineer**: Confirmed no schema changes needed. All columns already exist. Validated `games.home_score`/`away_score` is the correct approach for game_runs. Confirmed `reconciliation_discrepancies` table is sufficient as variance log. Note: `home_score`/`away_score` are nullable -- handle NULL gracefully.
- **Baseball-coach**: 99%+ accuracy targets approved -- exceeds all coaching thresholds (90%+ for FPS%, 95%+ for pitch counts, 80%+ for development context). Variance log is an operator/developer tool, not coaching output -- coaches don't need to see it. Boxscore supplement for pitcher totals is the right approach -- coaches trust the official scorebook. Irreducible scorekeeper correction gaps (2 total) are acceptable as documented data-source limitations.

## Goals
- All cross-source reconciliation signals (pitcher and batter stats) at 99%+ match rate
- Two game-level signals (`game_runs`, `game_pa_count`) converted from unreliable cross-source comparisons to data-availability checks using the authoritative `games` table -- these become tautological (always MATCH when data is present) and are no longer cross-source reconciliation signals
- Enriched variance log: boxscore-supplemented signals include `correction_detail` recording original plays-derived values for transparency (the engine already writes every discrepancy row; this epic enriches the detail for supplemented signals)
- No schema changes or new migrations
- No parser changes (HBP per-PA fix deferred -- boxscore supplement makes it non-urgent for totals)

## Non-Goals
- Per-PA pitch count fixes (HBP +1, Runner Out recovery) -- deferred to future work; boxscore supplement addresses totals
- Raw game-stream events endpoint exploration -- captured as future investigation path in research doc
- Parser changes to `plays_parser.py` -- not needed for this epic
- Reconciliation confidence gating in reports -- E-199 handles this (reconciliation always runs as part of pipeline)
- Fixing the 2 irreducible scorekeeper correction gaps

## Success Criteria
- `bb data reconcile --summary` shows all cross-source reconciliation signals (pitcher and batter stats) at 99%+ match rate
- `game_runs` and `game_pa_count` are data-availability checks (always MATCH when data is present) -- not counted as cross-source reconciliation
- Boxscore-supplemented discrepancy rows include `correction_detail` with original plays-derived values
- Existing reconciliation tests pass; new tests cover all 5 fixes
- E-199 can depend on reconciliation accuracy for report pipeline integration

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-201-01 | Implement five reconciliation accuracy fixes | TODO | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Five Fixes in `_check_pitcher_signals()` and `_check_game_level_signals()`

All production code changes are in `src/reconciliation/engine.py`. New tests are added to `tests/test_reconciliation.py`.

**Fix 1 -- Boxscore `#P`/`TS` supplement for high-confidence pitchers** (in `_check_pitcher_signals()`):

After building the raw plays-side aggregates per pitcher (`plays_pitchers` dict), evaluate a high-confidence gate per pitcher: BF, SO, and BB deltas are all zero (values match between boxscore and plays). For pitchers passing the gate, replace `plays_pitchers[pid]["pitches"]` and `plays_pitchers[pid]["total_strikes"]` with the boxscore values from `box_pitchers[pid]["pitches"]` and `box_pitchers[pid]["total_strikes"]`. Emit the supplemented values in the discrepancy rows (status = MATCH since plays-side now equals boxscore). Record the original plays-derived values in `correction_detail` so the supplement is transparent.

**Scope**: This is a detection-layer change only -- it supplements the plays-side value used for *comparison* in discrepancy records. It does NOT write boxscore values back to the `plays` table or modify any per-PA data. The per-PA pitch counts in `plays` remain as-is (plays-endpoint-derived).

The gate passes for 97.1% of pitchers in the 101-game dataset. The remaining 2.9% keep raw plays-derived values (lower confidence, but still logged).

**Fix 2 -- Add `Intentional Walk` to pitcher BB outcomes** (module-level constant):

Change `_BB_OUTCOMES = frozenset({"Walk"})` to `frozenset({"Walk", "Intentional Walk"})`. This fixes pitcher_bb.

**Fix 3 -- IBB in batter BB signal** (same code change as Fix 2):

`_BB_OUTCOMES` is shared by both `_check_pitcher_signals()` and `_check_batter_signals()`. The single constant change in Fix 2 fixes both pitcher_bb and batter_bb signals. No additional code needed -- this is listed as a separate fix for traceability against the research doc but is the same 1-line change.

**Fix 4 -- Use `games.home_score`/`away_score` for game_runs** (in `_check_game_level_signals()`):

The current boxscore source `SUM(player_game_batting.r)` undercounts when courtesy runners score runs not attributed to any individual batter. The current plays source (final play's `home_score`/`away_score`) misses runs scored on abandoned final PAs.

Fix: use `games.home_score`/`games.away_score` for BOTH sides. The `reconcile_game()` function already queries the `games` table for metadata; add `home_score` and `away_score` to the SELECT and pass them to `_check_game_level_signals()`. This converts game_runs from a cross-source reconciliation to a **data-availability check** (tautological -- same source for both sides, always MATCH when data is present). This is appropriate because runs are a game-level fact already captured authoritatively in the games table, and neither the plays-derived nor the batting-sum source is reliable (courtesy runners, abandoned PAs). Note: `home_score` and `away_score` are nullable INTEGER columns. When either is NULL, skip the `game_runs` signal entirely (no discrepancy row emitted). NULLs are rare on completed games but defensive handling is required (per DE consultation).

**Fix 5 -- Use boxscore BF sum for game_pa_count** (in `_check_game_level_signals()`):

The current plays source `len(pitching_plays)` misses abandoned final PAs that the boxscore BF counts. Fix: use `SUM(player_game_pitching.bf)` for BOTH sides (the boxscore BF sum is already computed as `box_pa`). This converts game_pa_count to a **data-availability check** (tautological -- same source for both sides, always MATCH when data is present), consistent with the game_runs approach.

### TN-2: Variance Log

The existing `reconciliation_discrepancies` table (migration 012) already captures the full variance log: `signal_name`, `boxscore_value`, `plays_value`, `delta`, `status`, and `correction_detail`. The `correction_detail` field is used to record supplementation details (e.g., "boxscore_supplement: plays_pitches=31, boxscore_pitches=38, gate=BF+SO+BB match").

No new columns or tables needed. Every discrepancy row (including MATCHes) is already written to this table by the engine.

### TN-3: Projected Accuracy After All Fixes

| Signal | Current | After Fixes | Fix |
|--------|---------|-------------|-----|
| pitcher_pitches | 88.1% | 99.2% | Boxscore `#P` supplement |
| pitcher_total_strikes | 93.8% | 99.6% | Boxscore `TS` supplement |
| pitcher_bb | 97.5% | 99.6% | IBB in `_BB_OUTCOMES` |
| batter_bb | 99.5% | 100% | IBB in `_BB_OUTCOMES` (shared constant) |
| game_runs | 93.1% | 100%* | `games.home_score`/`away_score` (availability check) |
| game_pa_count | 99.0% | 100%* | Boxscore BF sum for both sides (availability check) |
| pitcher_bf | 99.2% | 99.2% | Already above threshold |
| pitcher_h | 99.6% | 99.6% | Already above threshold |
| pitcher_so | 100% | 100% | Closed |
| pitcher_hbp | 100% | 100% | Closed |
| batter_ab/h/so/hbp | 99.5-100% | 99.5-100% | Already above threshold |

*\* Tautological -- same source for both sides. These are data-availability checks, not cross-source reconciliation.*

**Irreducible floor**: 2 gaps from scorekeeper Error→Hit corrections in game `0bf3b9e3`. Cannot be fixed algorithmically.

### TN-4: Test Matrix

| ID | Fix | Test Case | Type |
|----|-----|-----------|------|
| (a) | Fix 1 | High-confidence pitcher (BF+SO+BB match): `plays_value` = boxscore value, `correction_detail` has original | Positive |
| (b) | Fix 1 | Gate fails (BF/SO/BB mismatch): `plays_value` = raw plays-derived value | Negative |
| (c) | Fix 2 | Intentional Walk counted in `pitcher_bb` signal | Positive |
| (d) | Fix 3 | Intentional Walk counted in `batter_bb` signal | Positive |
| (e) | Fix 4 | `game_runs` uses `games.home_score`/`away_score` | Positive |
| (f) | Fix 5 | `game_pa_count` uses boxscore BF sum for both sides | Positive |
| (g) | Fix 4 | `game_runs` skipped when `home_score` or `away_score` is NULL | Edge |
| (h) | Fix 1 | Partial gate failure (e.g., BF matches but SO doesn't): supplement not applied | Edge |
| (i) | Fix 1 | Pitcher with zero plays (UNCORRECTABLE): supplement not applied | Edge |

## Open Questions
None -- all design decisions locked from 8 rounds of research investigation.

## History
- 2026-04-02: Created. Based on `.project/research/E-198-accuracy-gaps.md` (8 rounds of Claude/Codex investigation). Expert consultation completed with SE (implementation locations, complexity, story sizing), DE (schema confirmation, game_runs approach, variance log sufficiency), and coach (accuracy targets, variance log audience, boxscore supplement approval). IDEA-063 captured for `/dump-game` diagnostic skill.
- 2026-04-02: PM self-review -- 3 issues fixed (fix numbering mismatch, NULL handling in story Notes, verified accuracy numbers). CR spec audit iteration 1 -- 4 findings accepted (NULL behavior in AC-4, AC-5 qualifier, AC-7 test expansion, AC-1 plays_value clarification), 3 dismissed (intentional design, low-risk plumbing). Codex spec review iteration 1 -- 3 findings accepted (variance log scope narrowed, TN-1 source/test clarification, AC-7 test matrix moved to TN-4). Codex spec review iteration 2 -- 3 findings accepted (game_runs/game_pa_count distinguished as availability checks not cross-source reconciliation, high-confidence gate NULL/zero language fixed, IDEA-063 README date corrected). **Status → READY.**

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 7 | 4 | 3 |
| Internal iteration 1 -- PM self-review | 3 | 3 | 0 |
| Codex iteration 1 | 3 | 3 | 0 |
| Codex iteration 2 | 3 | 3 | 0 |
| **Total** | **16** | **13** | **3** |
