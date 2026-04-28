# E-230: Matchup engine v2 -- coaching tunables

## Status
`DRAFT`

## Overview
After E-228 v1 ships and a coach has used the matchup report in 2+ real games, this epic codifies the deterministic engine refinements that v1 deliberately deferred until real-use feedback exists. Adds the 4-template TL;DR slot-2 priority tree, the recent-form arrow overlay (last-7G window with Unicode ↑↔↓ at 0.100 OBP swing), the `decision_unknown` 6th loss bucket + `plays_loaded_per_game` data-completeness surfacing, and the ~14-constant tuning framework. Optionally reframes the dropped three-gate G1/G2/G3 starter prediction as "match eligible LSB pitchers to recipe profile" (surfacing matches as a list, NOT picking one).

## Background & Context
E-228 v1 (2026-04-28 refinement) cut substantial deterministic-engine scope to avoid over-fitting thresholds before real-use feedback. The cuts captured here represent locked discovery decisions from the original 2026-04-27 planning sessions -- the engine logic was fully designed, just deferred until the coach can validate the threshold values in actual game-prep workflow.

**Discovery decisions locked (from E-228 planning 2026-04-27, coach P2-T resolution):**

### 4-Template TL;DR Slot-2 Priority Tree
Per coach P2-T resolution after Phase 3 review:
- **T1 "Pitch around"** -- `bb_pct > 0.12 AND slg > 0.500` (dangerous + patient)
- **T2 "Make earn it"** -- `bb_pct > 0.12 AND slg ≤ 0.500` (patient table-setter)
- **T3 "Attack early"** -- `fps_swing_rate > 0.50 OR bb_pct < 0.05` (free hitter)
- **T4 "Expand on"** -- `k_pct > 0.22 AND 0.05 ≤ bb_pct ≤ 0.12` (chaser)
- **Priority tie-breaker**: T1 → T2 → T3 → T4
- **Default fallback**: T3
- **25-char hard constraint** on directive string (engine truncates name to last-name on overflow)
- **Missing-data fallback**: skip T3 + T4 when `fps_swing_rate` unavailable

### Recent-Form Arrow Overlay
- **Window**: last-7-games, NOT calendar days, per project data philosophy ("coaches think in games, not sync timestamps") and Coach S-4 review.
- **Arrow rendering**: Unicode ↑↔↓ at `|season_obp - recent_obp| >= 0.100`. Smaller swings render no arrow.
- **PA badges integral**: never omitted (they communicate sample size).
- **Implementation**: dedicated helper `get_player_recent_form(conn, player_id, season_id, *, last_n_games=7, perspective_team_id) -> RecentForm`. The `RecentForm` dataclass surfaces `games_in_window` so the renderer can show "Last 7G" or fewer if the player has < 7 games.
- **Display format** (from original UX delivery): `Season X (PA) / Last 7G Y (PA) [arrow]`. Sparkline rejected (unreadable at 9pt print). Delta-only rejected (hides absolute values).

### `decision_unknown` 6th Loss Bucket + Data-Completeness Surfacing
Per DE E and DE F2:
- When `player_game_pitching.decision IS NULL` for an opponent loss, engine emits a `decision_unknown` bucket entry AND a `data_notes` flag. Engine NEVER guesses pitcher of record; the narrative layer surfaces the gap to coach.
- New `data_completeness` block on `MatchupAnalysis` carries: `opponent_games_with_own_perspective_count`, `opponent_games_total`, `games_missing_opponent_perspective` (list per game_id), `scouting_last_run_at` (ISO timestamp from `scouting_runs.completed_at`), `plays_loaded_per_game` (dict game_id → bool).
- Pre-flight gate in input builder: when `game_perspectives` opponent-perspective coverage falls below `_MIN_OPPONENT_PERSPECTIVE_COVERAGE` (default 0.5), builder refuses to construct full inputs and a `data_notes` flag explains the refusal; engine returns `confidence="suppress"`.
- Narrative layer surfaces gaps to coach (e.g., "scouting last refreshed 4 days ago"; "12 of 18 games have plays data"; "loss-recipe analysis based on 14 of 18 losses").

### Tunable Constants Framework (~14 module-level constants)
Per Post-Ship Tuning Plan in original E-228 epic:
- `_PITCH_AROUND_BB_PCT = 0.12` (T1 patience trigger)
- `_PITCH_AROUND_SLG = 0.500` (T1 power floor)
- `_MAKE_EARN_BB_PCT = 0.12` (T2 patience trigger)
- `_ATTACK_EARLY_FPS_SWING = 0.50` (T3 first-pitch-swing trigger)
- `_ATTACK_EARLY_BB_PCT = 0.05` (T3 alternative trigger)
- `_EXPAND_K_PCT = 0.22` (T4 chaser threshold)
- `_TLDR_DIRECTIVE_MAX_CHARS = 25` (hard truncation constraint)
- `_AVOID_WALK_BB_PCT_THRESHOLD = 0.10` (TL;DR slot 3 threshold)
- `_RECENT_FORM_ARROW_THRESHOLD = 0.100` (OBP swing for arrow)
- `_RECENT_FORM_GAME_COUNT_DEFAULT = 7` (window size)
- `_PULL_SHIFT_THRESHOLD = 0.55` (HS-calibrated pull-tendency threshold)
- `_RECIPE_K_PER_BB_TOLERANCE = 0.30` (K/BB matching for recipe match)
- `_TOP_HITTER_PA_FLOOR = 10` (filter pinch-hitters)
- `_MIN_OPPONENT_PERSPECTIVE_COVERAGE = 0.5` (pre-flight gate)

Each documented in code with post-ship tuning windows.

### Reframed "Match Eligible Pitchers to Recipe Profile" (Optional)
Per user feedback 2026-04-28, the original three-gate G1/G2/G3 logic that picked **THE** LSB starter is deprecated. The reframed scope is "show coach which eligible pitchers' profiles match the loss-recipe pattern" -- a list, not a recommendation. The K/BB recipe matching (target = mean K/BB of opposing-team's-loss-pitchers; tolerance = 30%) becomes a sortable signal in the eligible LSB pitchers list, NOT a gate.

**Decision deferred to v2 planning**: whether this still belongs in v2 or gets dropped. The user steered v1 to "don't focus on one pitcher" -- if the reframed list view doesn't add coaching value over the existing eligible-pitchers list (which already shows rest math + workload), it may not survive planning.

**Promotion trigger**: After E-228 v1 ships AND coach uses the matchup report in 2+ real games AND provides feedback on (a) which signals were noisy, (b) which signals were missing, (c) which thresholds felt wrong. The whole epic is deliberately gated on real-use validation -- threshold values in code without coach feedback are a fishing expedition.

## Goals
- The 4-template TL;DR slot-2 priority tree codifies one of {Pitch around, Make earn it, Attack early, Expand on} per top hitter, with HS-calibrated thresholds and a 25-char directive cap.
- The recent-form arrow overlay shows last-7G OBP delta with PA badges, replacing or supplementing v1's plain stat display.
- The `decision_unknown` bucket + `data_completeness` surfacing make data-coverage gaps visible to coach without guessing.
- Tunable constants framework: every threshold value is a named module-level constant with documented tuning windows.
- Optionally: reframed "match eligible pitchers to recipe profile" surfaces a list of LSB pitchers whose K/BB profile matches the loss-recipe pattern.

## Non-Goals
- Re-introducing the three-gate G1/G2/G3 starter prediction that picks THE starter (user steered v1 away from this; reframed-as-list is the v2 evolution if it survives planning).
- Re-introducing the LSB starter override input field (user steered v1 away).
- Re-introducing the LSB lineup card (coach makes the lineup).
- Re-introducing head-to-head sidebar (don't play same team enough times at HS level).
- Visual polish (print stylesheet, mobile, AVOID inline sub-bullet typography) -- that's E-231.
- Dashboard parity -- that's E-232.
- Any work that would land before E-228 v1 ships and is used in 2+ real games.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| | To be written during planning | | | |

## Dispatch Team
- data-engineer
- software-engineer
- baseball-coach (consulting)

## Technical Notes

### Threshold Calibration Sources
All threshold defaults above are HS-calibrated per coach review during E-228 planning. They are starting-point values; v2 planning establishes which constants get tuned per `OPENROUTER_*`-style env var override vs. hardcoded with code-change-required-to-tune.

### Recent-Form Helper Implementation
`get_player_recent_form(conn, player_id, season_id, *, last_n_games=7, perspective_team_id, db=None) -> RecentForm` runs at query time over `player_game_batting WHERE player_id = ? AND perspective_team_id = ? ORDER BY game_date DESC LIMIT N`. The `perspective_team_id` filter is REQUIRED per perspective-provenance rule. Returns aggregated `pa, ab, h, bb, hbp, obp, slg, games_in_window`.

### Directive String Construction (T1-T4)
The engine assembles directive strings via templates with the player's last name (truncating to last name only if total exceeds 25 chars):
- T1: "Pitch around {name}"
- T2: "Make {name} earn it"
- T3: "Attack {name} early"
- T4: "Expand on {name}"

The engine emits the directive string + `cue_kind` enum + supporting stats; the renderer (E-231 may revisit visual treatment) preserves the directive verbatim and adds the inline citation parenthetical.

### A/B Comparison
v2 planning may include a story to A/B compare:
- v1 LLM-only narrative (deterministic engine + LLM prose)
- v2 deterministic+LLM hybrid (4-template directives + LLM prose for elaboration)

The comparison is over coach-judged usefulness, not algorithmic accuracy.

## Open Questions
1. **Which constants get exposed via env var vs. hardcoded?** v2 planning decides per-constant. Operational reasoning: thresholds the coach might want to override per-team (e.g., for Legion vs. HS) → env var. Thresholds that are universal HS-calibration → hardcoded.
2. **Does the reframed "match eligible pitchers to recipe profile" ship at all in v2?** Depends on coach feedback after v1 ships. If the existing eligible-pitchers list (rest + workload) is sufficient for the matchup workflow, the recipe-match sortable column may not add value.
3. **A/B comparison methodology**: how does v2 planning compare v1 narrative against v2 deterministic+LLM hybrid? Side-by-side on a single fixture? Multi-fixture pairwise? Coach-judged single rubric? Planning decides.
4. **`scouting_runs.completed_at` vs `teams.last_synced` for freshness**: per DE H-1, per-scout-run timestamp is more accurate (a partial scout updates `last_synced` but the coverage gap may persist). v2 planning confirms the source-of-truth for the freshness UX.

## Promotion Triggers
This epic is gated on real-use validation:
1. **E-228 v1 has shipped** (status COMPLETED, archived).
2. **Coach has used the matchup report in at least 2 real games** in real game-prep workflow.
3. **Coach provides feedback** on (a) signals that felt noisy, (b) signals that were missing, (c) thresholds that felt wrong, (d) whether the directive language ("Pitch around X") matches mental cue ergonomics.

If trigger 2 or 3 is not met within ~6 months of v1 shipping, the epic is reviewed for relevance -- if v1 is producing sufficient coaching value as-is, v2 may DEFERRED or DISCARDED.

## History
- 2026-04-28: Created as DRAFT stub during E-228 v1 refinement. Discovery context preserved from E-228 planning sessions (2026-04-27 -- coach P2-T resolution, DE F/H, original UX layout). Original scope was distributed across stories E-228-05 (engine), E-228-09 (renderer), and E-228-04 (data layer); promoted to its own epic because the deterministic engine refinements are tightly coupled and depend on real-use validation that doesn't exist yet.
