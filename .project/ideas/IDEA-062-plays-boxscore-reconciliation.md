# IDEA-062: Plays-vs-Boxscore Reconciliation Engine

## Status
`CANDIDATE`

## Summary
An exhaustive reconciliation engine that cross-checks plays-derived data (from the plays endpoint) against boxscore aggregates (from the boxscore endpoint), logs structured discrepancies, and enables iterative heuristic evolution to close gaps. The boxscore is the ground truth checksum; plays data provides the granular detail. Where they disagree, the reconciliation engine identifies correctable misattributions (primarily pitcher assignment) and logs ambiguous cases for future heuristic development.

## Why It Matters
E-195 delivered the plays ingestion pipeline, but production validation revealed:
- **55.6% FPS match rate** (15 of 27 pitchers within 5% tolerance)
- **53.8% QAB match rate** (14 of 26 batters within 5% tolerance)
- **2.6% aggregate FPS gap** due to pitcher misattribution (the plays endpoint doesn't always announce pitching changes via substitution events)
- **BF per pitcher off by up to 35 PAs** for individual pitchers
- Batter stats are more accurate (batter UUID always in `final_details`) but still have minor gaps

Without reconciliation, FPS% and pitcher workload stats derived from plays data are unreliable for coaching decisions. The boxscore endpoint provides per-pitcher and per-batter aggregate stats that can serve as definitive checksums. A reconciliation engine turns two imperfect data sources into one reliable source -- and a discrepancy log creates a feedback loop for continuously improving the parser heuristics.

## Exhaustive Reconciliation Signals

### Category 1: Pitcher Attribution Signals

These are the highest-value signals because pitcher misattribution is the dominant error mode.

#### 1A. Starter Identification
- **Boxscore field**: First entry in pitching group `stats` array (array order = pitching order)
- **Plays-derived**: Pitcher ID from the first `final_details` template (e.g., `"${batter} strikes out swinging, ${pitcher} pitching"`) or from `"Lineup changed: ${uuid} in at pitcher"` substitution event
- **Mismatch correction**: If the first pitcher in plays data differs from the boxscore starter, reassign all plays before the first substitution event to the boxscore starter. **Confidence: DEFINITIVE** -- boxscore starter identification is authoritative.

#### 1B. Batters Faced (BF) per Pitcher
- **Boxscore field**: Pitching `extra` array, `stat_name: "BF"`, per-pitcher values
- **Plays-derived**: `COUNT(*)` of plays grouped by `pitcher_id`
- **Mismatch correction**: If plays-derived BF < boxscore BF for pitcher A and plays-derived BF > boxscore BF for pitcher B, the difference likely represents plays misattributed between A and B. The boundary between their stints can be located by finding where the BF counts diverge. **Confidence: DEFINITIVE for detecting misattribution boundaries** -- BF is a hard count, not a computed stat. The total BF across all pitchers must equal total plate appearances in the game.

#### 1C. IP / Outs per Pitcher
- **Boxscore field**: Pitching `stats.IP` (float decimal innings, e.g., 3.333 = 3⅓ IP)
- **Plays-derived**: Count of out-producing plays (`did_outs_change = 1`) per pitcher, excluding runner-outs during at-bats
- **Mismatch correction**: If pitcher A has fewer outs in plays than boxscore IP implies, and pitcher B has more, the handoff boundary is wrong. Combined with BF, this localizes the exact play range where misattribution occurred. **Confidence: DEFINITIVE** -- outs are discrete and countable.

#### 1D. Strikeouts (SO) per Pitcher
- **Boxscore field**: Pitching `stats.SO`
- **Plays-derived**: Count of plays with `outcome IN ('Strikeout', 'Dropped 3rd Strike')` per `pitcher_id`
- **Mismatch correction**: Strikeouts are unambiguous outcomes. If pitcher A has 5 SO in boxscore but 3 in plays, 2 strikeouts are misattributed. Cross-reference with BF and IP to find the boundary. **Confidence: DEFINITIVE** -- each strikeout is a single play with a clear outcome.

#### 1E. Walks (BB) per Pitcher
- **Boxscore field**: Pitching `stats.BB`
- **Plays-derived**: Count of plays with `outcome = 'Walk'` per `pitcher_id` (excluding Intentional Walk, which is a separate boxscore stat if present)
- **Mismatch correction**: Same logic as SO. Walks are unambiguous outcomes tied to a single pitcher. **Confidence: DEFINITIVE**.

#### 1F. HBP per Pitcher
- **Boxscore field**: Pitching `extra` array, `stat_name: "HBP"`, per-pitcher values
- **Plays-derived**: Count of plays with `outcome = 'Hit By Pitch'` per `pitcher_id`
- **Mismatch correction**: Unambiguous outcome. **Confidence: DEFINITIVE**.

#### 1G. Pitch Count (#P) per Pitcher
- **Boxscore field**: Pitching `extra` array, `stat_name: "#P"`, per-pitcher values
- **Plays-derived**: Sum of `pitch_count` from plays grouped by `pitcher_id`
- **Mismatch correction**: Total pitch count per pitcher is a hard aggregate. If plays-derived pitch count for pitcher A exceeds boxscore by N and pitcher B is short by ~N, those N pitches' worth of plays are misattributed. **Confidence: DEFINITIVE for detecting magnitude** -- pitch count is a precise aggregate. Can narrow the boundary when combined with BF.

#### 1H. Total Strikes (TS) per Pitcher
- **Boxscore field**: Pitching `extra` array, `stat_name: "TS"`, per-pitcher values
- **Plays-derived**: Count of pitch events with `pitch_result IN ('strike_looking', 'strike_swinging', 'foul', 'foul_tip', 'in_play')` per pitcher
- **Mismatch correction**: Strike count provides additional constraint for boundary detection. **Confidence: DEFINITIVE** as an aggregate check.

#### 1I. Hits Allowed (H) per Pitcher
- **Boxscore field**: Pitching `stats.H`
- **Plays-derived**: Count of plays with `outcome IN ('Single', 'Double', 'Triple', 'Home Run')` per `pitcher_id`
- **Mismatch correction**: Hits are unambiguous outcomes tied to a single pitcher. **Confidence: DEFINITIVE**.

#### 1J. Runs (R) and Earned Runs (ER) per Pitcher
- **Boxscore field**: Pitching `stats.R` and `stats.ER`
- **Plays-derived**: Runs can be derived from `did_score_change` and score progression, but attributing them to the correct pitcher requires knowing which pitcher was responsible for the baserunner who scored (inherited runners). **Confidence: PROBABILISTIC** -- ER attribution depends on inherited runner tracking which plays data doesn't fully encode. R can be approximated but ER requires error/earned distinction not present in plays.

#### 1K. Wild Pitches (WP) per Pitcher
- **Boxscore field**: Pitching `extra` array, `stat_name: "WP"`, per-pitcher values
- **Plays-derived**: Count of `at_plate_details` events matching `"advances to * on wild pitch"` or `"scores on wild pitch"` patterns per current pitcher
- **Mismatch correction**: Wild pitches occur during a PA and are tied to the current pitcher. Useful for verifying pitcher assignment during specific PAs. **Confidence: DEFINITIVE** if pitcher is correctly tracked at that point.

#### 1L. Pitching Order / Decision (W/L/SV)
- **Boxscore field**: Pitching `stats` array order (appearance order) + `player_text` showing `"(W)"`, `"(L)"`, `"(SV)"`, or `""`
- **Plays-derived**: Pitcher appearance sequence from substitution events and `final_details` pitcher references
- **Mismatch correction**: The pitching order in the boxscore is authoritative. If plays data has pitchers in a different order, the substitution tracking is wrong. The decision tags (W/L/SV) additionally verify which pitcher was active at key game-state transitions. **Confidence: DEFINITIVE** for ordering.

### Category 2: Batter Attribution Signals

Batter attribution is more reliable (batter UUID is always in `final_details`) but still worth verifying.

#### 2A. At-Bats (AB) per Batter
- **Boxscore field**: Batting `stats.AB`
- **Plays-derived**: `COUNT(*)` of plays per `batter_id` WHERE `outcome NOT IN ('Walk', 'Hit By Pitch', 'Sacrifice Fly', 'Sacrifice Bunt', 'Catcher''s Interference', 'Intentional Walk')` (AB = PA - BB - HBP - SF - SH - CI)
- **Mismatch correction**: AB is a computed stat, so mismatches may indicate an outcome classification error rather than a batter misattribution. **Confidence: DEFINITIVE** for detecting errors, AMBIGUOUS for which specific play is wrong.

#### 2B. Hits (H, 2B, 3B, HR) per Batter
- **Boxscore field**: Batting `stats.H`; extras `2B`, `3B`, `HR`
- **Plays-derived**: Count by outcome type (`Single`, `Double`, `Triple`, `Home Run`) per `batter_id`. H = 1B + 2B + 3B + HR.
- **Mismatch correction**: If H matches but 2B/3B don't, it's a hit-type classification error. If H itself doesn't match, a play was misclassified (e.g., an error counted as a hit or vice versa). **Confidence: DEFINITIVE** for detecting, CORRECTABLE for hit-type issues.

#### 2C. BB, SO, HBP per Batter
- **Boxscore field**: Batting `stats.BB`, `stats.SO`; extra `HBP`
- **Plays-derived**: Count of `Walk`, `Strikeout`/`Dropped 3rd Strike`, `Hit By Pitch` outcomes per `batter_id`
- **Mismatch correction**: These are unambiguous outcomes. Mismatches indicate either a batter misattribution (unlikely since batter ID is in `final_details`) or an outcome parsing error. **Confidence: DEFINITIVE**.

#### 2D. SB, CS per Batter
- **Boxscore field**: Batting extras `SB`, `CS`
- **Plays-derived**: Count of `"${uuid} steals *"` baserunner events in `at_plate_details` per player UUID; CS from `"${uuid} caught stealing *"` events
- **Mismatch correction**: Steal events name the runner UUID directly. Mismatches may indicate missed baserunner event parsing. **Confidence: DEFINITIVE** -- runner UUID is in the template.

#### 2E. RBI per Batter
- **Boxscore field**: Batting `stats.RBI`
- **Plays-derived**: RBI is not directly encoded in plays data. Must be inferred from: (a) `did_score_change` on plays where the batter's action caused the score change, (b) Walk/HBP with bases loaded, (c) hit outcomes where baserunners score. But sacrifice flies, groundouts with runners scoring, and other RBI scenarios are complex. **Confidence: PROBABILISTIC** -- requires inference logic not currently in the parser.

#### 2F. Runs (R) per Batter
- **Boxscore field**: Batting `stats.R`
- **Plays-derived**: Count of `"${uuid} scores"` events in `final_details` per batter UUID. Also cross-reference with `did_score_change` and score progression. **Confidence: PROBABILISTIC** -- scoring events name the runner, but the runner isn't always the batter.

#### 2G. Total Bases (TB) per Batter
- **Boxscore field**: Batting extras `TB`
- **Plays-derived**: `SUM` of (1 for Single, 2 for Double, 3 for Triple, 4 for HR) per `batter_id`
- **Mismatch correction**: TB is deterministic from hit types. If TB mismatches but H matches, there's a hit-type misclassification. **Confidence: DEFINITIVE** -- derived from hit type.

#### 2H. Errors (E) per Fielder
- **Boxscore field**: Batting extras `E` (per fielder -- note: appears in lineup/batting extras, not pitching)
- **Plays-derived**: Count of error outcomes where the fielder UUID is extracted from `final_details` (e.g., `"reaches on an error by shortstop ${uuid}"`)
- **Mismatch correction**: Error events name the fielder. Mismatches may indicate missed error parsing or fielder UUID extraction failure. **Confidence: DEFINITIVE** when fielder UUID is present; ~50 templates omit fielder UUID.

### Category 3: Lineup and Substitution Signals

#### 3A. Positions Played
- **Boxscore field**: `player_text` in batting stats (e.g., `"(SS, P)"`, `"(CF)"`)
- **Plays-derived**: `"Lineup changed: ${uuid} in at {position}"` substitution events
- **Mismatch correction**: The boxscore shows ALL positions a player occupied. Plays data shows substitution events. If a player shows `"(SS, P)"` in the boxscore but plays data only has them as SS with no substitution to P, a substitution event was missed. **Confidence: DEFINITIVE** for detecting missed substitutions.

#### 3B. Batting Order
- **Boxscore field**: Implicit in batting `stats` array order (index 0 = leadoff). `is_primary: true/false` distinguishes starters from subs.
- **Plays-derived**: Batter sequence reconstructed from `play.order`, `play.half`, `play.inning`
- **Mismatch correction**: If the batting order reconstruction from plays diverges from boxscore array order, there may be a pinch-hitter substitution that was missed. **Confidence: DEFINITIVE** for detecting lineup discrepancies.

#### 3C. Pitcher Appearance Order
- **Boxscore field**: Pitching `stats` array order (first entry = starter, subsequent = relievers)
- **Plays-derived**: Order of unique `pitcher_id` values as they first appear in plays sequence
- **Mismatch correction**: The boxscore pitcher order is authoritative. If plays data shows a different order, the substitution tracking is wrong. **Confidence: DEFINITIVE** -- this is the strongest signal for correcting pitcher assignment.

### Category 4: Game-Level Signals

#### 4A. R/H/E Team Totals
- **Boxscore field**: `team_stats` in both lineup and pitching groups (`R`, `H` for batting; `R`, `H` for pitching-allowed)
- **Plays-derived**: Sum of all runs scored (from `did_score_change` progression), hits (from hit outcomes), errors (from error outcomes)
- **Mismatch correction**: Team totals are the ultimate consistency check. If they match, individual misattributions may cancel out but at least the aggregate is consistent. If they don't match, something fundamental is wrong with the plays parsing. **Confidence: DEFINITIVE** as a sanity check.

#### 4B. Inning-by-Inning Run Scoring
- **Boxscore field**: Not directly in boxscore, but available via public `GET /public/game-stream-processing/{game_stream_id}/details?include=line_scores` endpoint
- **Plays-derived**: Group plays by inning+half, compute runs per half-inning from score progression (`home_score`, `away_score` deltas)
- **Mismatch correction**: If a half-inning shows different run counts, plays for that half-inning have errors. **Confidence: DEFINITIVE** -- runs per inning is precise.

#### 4C. Total PA Count Consistency
- **Boxscore field**: Sum of batting `team_stats.AB + BB + HBP` (approximate PA) or sum of pitching `BF` across all pitchers
- **Plays-derived**: Total number of parsed plays (excluding `Runner Out`, `Inning Ended`, and abandoned at-bats)
- **Mismatch correction**: If total PAs disagree, plays were either skipped or double-counted. **Confidence: DEFINITIVE** -- PA count is precise.

### Category 5: Fielding Signals

#### 5A. Putouts, Assists per Fielder
- **Boxscore field**: Not in the standard boxscore endpoint fields documented (fielding stats not observed in current boxscore response). Would need separate endpoint or extended query params.
- **Plays-derived**: Fielder UUIDs in `final_details` (e.g., `"grounds out, shortstop ${uuid} to first baseman ${uuid}"` → assist to SS, putout to 1B)
- **Note**: This signal is only available if a fielding-specific boxscore section exists. Currently **NOT AVAILABLE** in the boxscore endpoint's documented fields. Fielding stats may exist in a separate endpoint or extended response. Mark as future research.

## Discrepancy Logging and Evolution System

### Structured Discrepancy Log

Each reconciliation run produces structured records:

**Per-game record:**
- `game_id`, `event_id`, reconciliation timestamp
- Overall confidence score (% of signals that agree)
- List of signal results (signal name, boxscore value, plays value, delta, status)

**Per-player-per-signal record:**
- `game_id`, `player_id`, signal category, signal name
- `boxscore_value`, `plays_value`, `delta`, `pct_delta`
- `status`: `MATCH`, `CORRECTABLE`, `AMBIGUOUS`, `UNCORRECTABLE`
- `correction_applied`: boolean (did the engine fix it?)
- `correction_detail`: what was changed (e.g., "Reassigned plays 15-22 from pitcher A to pitcher B")

### Discrepancy Categories

1. **CORRECTABLE**: Enough signal to fix automatically with high confidence. Examples:
   - BF mismatch with clear pitcher boundary (BF for A is +5, BF for B is -5, plays are contiguous)
   - Boxscore starter differs from plays-inferred starter (reassign pre-substitution plays)
   - SO/BB count mismatch localized to a specific pitcher handoff zone

2. **AMBIGUOUS**: Multiple possible corrections, or the signal isn't strong enough to act on automatically. Examples:
   - BF off by a small amount but multiple pitcher changes make boundary unclear
   - Run/ER attribution where inherited runners are involved
   - RBI inference from plays data

3. **UNCORRECTABLE**: Not enough data to determine what's wrong. Examples:
   - Plays endpoint returned fewer plays than expected (data truncation)
   - fielder UUID missing from template (~50 known cases)
   - Scorekeeper corrections (`"Outs changed to 1"`) that retroactively change game state

### Feedback Loop for Heuristic Evolution

The discrepancy log becomes training data:

1. **Pattern detection**: After N games, analyze discrepancy logs to find repeating patterns (e.g., "pitcher misattribution always occurs at the start of an inning when there's no substitution event" → heuristic: if the first play of an inning has a different pitcher in `final_details` than the tracked pitcher, trust `final_details`).

2. **Heuristic proposal**: An LLM can read discrepancy logs and propose new reconciliation rules. Each rule is a named, versioned function that takes plays + boxscore data and produces corrections.

3. **Versioned reconciliation rules**: Each rule has:
   - A name and version
   - Input: signal type + mismatch pattern
   - Output: correction operation
   - Confidence threshold for auto-apply vs. flag-for-review
   - Validation: run the rule against historical games and measure whether it reduces the gap

4. **Audit trail**: Every correction is logged with the rule that produced it, so corrections can be reviewed and rolled back if a rule is found to be wrong.

## Architecture Sketch

- **Post-load reconciliation pass**: Runs after the plays loader completes for a game, before any stats queries consume the data. Requires the boxscore to already be cached in `data/raw/`.
- **Per-game scope**: Reconciles one game at a time. Loads the boxscore JSON + plays records for the same `game_id`.
- **Correction operations**: `UPDATE plays SET pitcher_id = ? WHERE game_id = ? AND play_order BETWEEN ? AND ?` for pitcher reassignment. Other corrections are field-level updates.
- **Discrepancy storage**: Either a `reconciliation_log` table (structured, queryable) or JSON files in `data/reconciliation/` (easier for LLM consumption). Table is better for production; JSON files are better for development iteration.
- **Confidence score per game**: `(signals_matched / total_signals) * 100`. Games below a threshold (e.g., 80%) are flagged for manual review or deeper analysis.
- **CLI entry point**: `bb data reconcile` -- runs reconciliation for all games or a specific game.

## Rough Timing

**Promote when**: The user decides to invest in closing the FPS/QAB accuracy gaps. The plays pipeline (E-195) is shipped and validated. The boxscore data is already cached from existing crawl pipelines. This idea is promotable now.

**Urgency**: Medium-high. The plays pipeline is live but its derived stats (FPS%, QAB) are only ~55% accurate at the per-pitcher level. Coaches using these stats need to know they're reliable. However, the aggregate batter-level QAB is more accurate, and FPS% is a new stat not yet heavily relied upon, so there's a window before this becomes a blocker.

## Dependencies & Blockers

- [x] E-195 (plays pipeline) -- COMPLETED
- [x] Boxscore data already cached by existing crawl pipeline (`data/raw/{season}/teams/{gc_uuid}/boxscores/{event_id}.json`)
- [ ] Boxscore loader must populate enough data for per-pitcher/per-batter stat extraction. Current `game_loader.py` extracts boxscore stats -- verify it stores the `extra` stats (BF, #P, TS, HBP, WP, 2B, 3B, HR, TB, SB, CS, E) needed for reconciliation signals.
- [ ] No new API endpoints needed -- all data sources are already crawled.

## Open Questions

- **Storage format for discrepancy logs**: Table vs. JSON files? Table is better for querying patterns across games; JSON is better for LLM consumption. Could do both (table for production, JSON export for analysis).
- **Auto-correct threshold**: At what confidence level should corrections be applied automatically vs. flagged? Start conservative (only CORRECTABLE with single-candidate corrections) and loosen as heuristics prove reliable.
- **Retroactive reconciliation**: Should we reconcile all 101 existing games on first run, or only new games going forward? Retroactive gives immediate accuracy improvement but is a one-time cost.
- **Boxscore `extra` stat coverage**: The boxscore `extra` array is sparse (only non-zero values). Need to verify that all pitchers and batters with non-zero BF, #P, TS etc. are represented. If a pitcher faced 1 batter and threw 3 pitches, are those in `extra`?
- **Run attribution complexity**: R and ER per pitcher require inherited runner tracking. Is this worth building now or should it be deferred to a later iteration?
- **Fielding reconciliation**: Fielding stats (PO, A) are not in the current boxscore response. Is there a separate endpoint? This may need an api-scout investigation.

## Notes

- The E-195 validation results are at `/.project/research/E-195-validation-results.md` -- contains per-pitcher FPS diagnostics and per-batter QAB diagnostics with game-level breakdowns
- The plays parser is at `src/gamechanger/parsers/plays_parser.py` -- the reconciliation engine would be a peer module
- The plays loader is at `src/gamechanger/loaders/plays_loader.py`
- The boxscore endpoint doc is at `docs/api/endpoints/get-game-stream-processing-game_stream_id-boxscore.md`
- A boxscore sample is at `data/raw/boxscore-sample.json`
- Related ideas: IDEA-041 (play-by-play stat compilation pipeline) covers advanced analytics built on plays data; this idea provides the accuracy foundation that IDEA-041 would depend on
- Related ideas: IDEA-031 (stat blending logic) covers API vs boxscore merge strategy; this idea is a more specific and actionable subset focused on plays-vs-boxscore

---
Created: 2026-04-01
Last reviewed: 2026-04-01
Review by: 2026-06-30
