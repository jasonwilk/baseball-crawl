# E-228: Matchup Strategy Report

## Status
`DRAFT`

## Overview
Automate the production of game-day matchup strategy reports that combine opponent scouting + LSB context into a prescriptive, citation-backed analysis a head coach can read in 10 minutes the morning of a game. The matchup section extends the standalone report flow with an opt-in "matchup" checkbox + "us team" dropdown; when both are provided, generation runs a fresh scout for the LSB team and renders a coach-voice prescriptive section using the existing two-tier (deterministic engine + LLM Tier 2) pattern established by predicted-starter. Existing single-team scouting reports remain unchanged when the matchup option is unselected.

## Background & Context

LSB coaches currently produce game-day matchup strategy by hand -- opening GameChanger tabs, copying stats, comparing across opponent and own-team data, and synthesizing recommendations into a one-page bench card. Today's manual prototype (LSB vs Westside Warriors, 2026-04-28) took ~45 minutes and the artifact disappears the moment the game ends. This epic automates that artifact.

The architectural reference is the predicted-starter pattern: pure-function deterministic engine in `src/reports/starter_prediction.py` (returns a typed dataclass) + Tier 2 LLM narrative wrapper in `src/reports/llm_analysis.py` (calls OpenRouter, returns enriched dataclass). The matchup section follows the same shape and slots into `src/reports/generator.py` parallel to the predicted-starter block.

**Discovery consultations (2026-04-27):**
- **baseball-coach**: Locked v1 must-haves and the "argument not stat sheet" voice. Provenance is per-recommendation inline parenthetical, not footnote. Anti-patterns ("avoid") are inline-only, paired with positive instructions. Failure mode is "never suppress, show with explicit data-depth badges" except for the structural no-LSB-context case where the whole matchup section is hidden but the scouting report still renders.
- **api-scout**: 99% of inputs already in DB. API ceilings: pitch type / velocity / zone / defensive alignment / pitcher repertoire are NOT exposed by GC. Plays exposes outcome-based pitch tendencies (first-pitch swing, count-based outcomes, batted-ball type) but no pitch type. Plays NOT auto-run in `bb data scout` -- needs wiring for tracked-team pipeline parity.
- **software-engineer**: Path C (additive opt-in) is the lowest-risk architectural lift -- 1-line schema migration + optional generator parameter + single conditional template section. Engine should follow pure-function discipline (all DB lookups in `build_matchup_inputs()`, `compute_matchup()` is pure). LLM prompt mirrors `llm_analysis.py` (ASCII-table grounding, strict JSON output, hallucination ban). Test layers: pure-engine fixture tests, multi-scope DB fixture tests for input builder, mocked OpenRouter for LLM wrapper.
- **claude-architect**: Light context-layer impact -- closure-time edits to `key-metrics.md` (matchup signal definitions if they stabilize) and `architecture-subsystems.md` (extend "Two-Tier Enrichment Pattern" to list matchup as second instance). No new rules, skills, agents, or hooks.

**User scope decisions (2026-04-27):**
- Path C (additive opt-in) -- single template, single generator entry point, optional `our_team_id`. Backward-compatible.
- One epic, not sibling epics. Pitcher-prediction-as-checkbox is a story inside this epic (admin-page UI change), generation infrastructure ships with the matchup engine.
- Fresh-on-demand always. When matchup is checked + "us" team selected, run a fresh `bb data scout` for the LSB team during generation. No caching threshold logic.
- "Us teams" source: `teams WHERE membership_type = 'member'`.
- LSB starter prediction: optional user-input field; if absent, system predicts only when all three gates pass (rest cleared, ≥2 GS this season, K/BB profile matches winning-recipe pitcher from opponent's losses); silence > weak suggestion.
- Handedness DROPPED from v1. Pitch-attack notes ship without L/R logic. Captured as follow-on idea.
- Plays in `bb data scout` is a v1 story (verified missing from both `run_scouting_sync` and `_scout_live`).
- Inning-by-inning game plan, repertoire matching, dashboard parity, multi-season head-to-head all deferred to follow-on epic / ideas.

## Goals
- A coach generating a report for tomorrow's opponent can check "Matchup" + pick their LSB level and receive a prescriptive coach-voice game-plan section alongside the existing scouting content
- The matchup section combines opponent scouting (loss recipe, top hitters with recent form, opposing pitching availability + bullpen pattern, defensive shifts) with LSB-aware content (head-to-head sidebar, recommended lineup card, optional starter suggestion, LSB-pitcher-specific pitch-attack notes)
- Every prescriptive recommendation in the three coach-locked categories (pitcher choice, pitch-attack per hitter, defensive shifts) cites supporting data points inline
- The deterministic engine produces a typed dataclass that the LLM Tier 2 narrative wraps without introducing player names or statistics not present in the input
- Existing single-team scouting reports continue to generate identically when the matchup option is unselected
- Scouting pipeline parity is preserved: plays auto-run in both `run_scouting_sync` (web) and `_scout_live` (CLI)

## Non-Goals
- Inning-by-inning game-plan narrative (judgment-heavy, deferred to v2 follow-on epic per coach)
- LSB pitcher repertoire matching ("matches the winning-recipe profile" full inference) -- API ceiling on pitch-type metadata
- Pitcher / batter handedness data wiring -- captured as follow-on idea (operator-entered fallback path)
- Dashboard parity (lighter matchup version on opponent dashboard) -- captured as follow-on idea per architect's recommendation
- Multi-season historical matchups in head-to-head sidebar -- v1 is current-season only
- Pitch-type / zone / velocity tendencies -- API ceiling, permanent
- Defensive alignment observed from opposing teams -- API ceiling, permanent
- Multi-LSB-team head-to-head (when an opponent appears under multiple member teams' `team_opponents` rows) -- v1 silently skips the sidebar in that case; full handling deferred
- "What to avoid" as a standalone section -- coach explicitly rejected; inline-only
- Two-team report architectural rename ("Scouting Report" → "Matchup Report") -- Path C preserves the existing identity; the section is additive

## Success Criteria
- A coach checks "Matchup" + selects "LSB Varsity" + provides an opponent GC URL, and receives a generated report with both the existing scouting content AND a new matchup section containing: head-to-head sidebar (when available), top-hitter threat list with recent form, opposing pitching availability + bullpen pattern, pitch-attack notes per dangerous hitter (LSB-pitcher-aware when starter is provided), defensive shift calls, recommended LSB lineup card, optional LSB starter suggestion (when three-gate criteria met), loss-recipe narrative
- Every prescriptive recommendation for pitcher choice, pitch-attack per hitter, and defensive shifts includes an inline data citation (e.g., "Attack first pitch (2 BB / 91 PA)") in the rendered output
- The LLM Tier 2 narrative does NOT name any player not present in the deterministic dataclass; verified by structured tests
- Generating a report WITHOUT the matchup option produces identical output to today (backward-compat regression test passes)
- `bb data scout` for any tracked opponent runs plays crawl + load + reconcile after the spray load step; verified by integration test
- The existing predicted-starter section continues to render correctly with both matchup-on and matchup-off paths
- The matchup section gracefully degrades with per-component data-depth badges when opponent data is thin (e.g., "3 games / 12 PA"), and silently skips entirely when no LSB context can be associated with the report
- A coach can read `docs/coaching/matchup-report.md` and understand what the matchup section delivers; an operator can read `docs/admin/matchup-report-generation.md` and generate a report end-to-end without help
- Every story's test ACs are reviewer-meaningful (not "tests pass") and include the test files named for execution
- The byte-identical backward-compat baseline test passes throughout the epic (proves no regression in existing single-team scouting reports)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-228-01 | Reports Path C lift: schema + generator parameter + admin checkbox + CLI flag | TODO | None | - |
| E-228-02 | Wire plays into `bb data scout` (CLI + web parity) | TODO | None | - |
| E-228-03 | Pitcher prediction: convert always-on to opt-in checkbox | TODO | E-228-01 | - |
| E-228-04 | Matchup data layer: query helpers in `src/api/db.py` | TODO | E-228-02 | - |
| E-228-05 | Deterministic matchup engine: dataclasses + `compute_matchup()` | TODO | E-228-04 | - |
| E-228-06 | Matchup input builder: `build_matchup_inputs()` + perspective-aware queries | TODO | E-228-04, E-228-05 | - |
| E-228-07 | LLM Tier 2 wrapper: `enrich_matchup()` with hallucination guardrails | TODO | E-228-05 | - |
| E-228-08 | Generator orchestration: wire matchup into `generate_report()` flow | TODO | E-228-01, E-228-02, E-228-03, E-228-06, E-228-07 | - |
| E-228-09 | Renderer + Jinja2 template section with inline citations and data-depth badges | TODO | E-228-08 | - |
| E-228-10 | User-facing documentation: coaching guide + admin guide | TODO | E-228-09 | - |
| E-228-11 | Context-layer closure pass (architect): rule updates | TODO | E-228-10 | - |

## Dispatch Team
- software-engineer
- data-engineer
- docs-writer
- claude-architect

## Technical Notes

### Architectural Path: C (Additive Opt-In)

**Schema change (one column, nullable for backward compat):**
```sql
ALTER TABLE reports ADD COLUMN our_team_id INTEGER REFERENCES teams(id);
```
Existing rows have `our_team_id IS NULL`; the renderer hides the matchup section in that case. New migration: `migrations/002_add_our_team_id_to_reports.sql` (next available number per `.claude/rules/migrations.md` — 001 is the consolidated post-E-220 schema rewrite).

**Generator entry point:**
`generate_report()` in `src/reports/generator.py` accepts an optional `our_team_id: int | None = None` parameter. When present and matchup section is enabled, the generator:
1. Resolves the LSB team's `public_id` from `teams.id`
2. Triggers a fresh in-memory scout for the LSB team (mirrors the existing opponent scout invocation, just with the LSB `public_id`)
3. Builds matchup inputs via `build_matchup_inputs()` after reconciliation has run
4. Calls `compute_matchup()` (deterministic Tier 1)
5. Optionally calls `enrich_matchup()` (Tier 2, non-fatal try/except mirroring lines 1186-1209 of generator.py)

When `our_team_id` is `None`, the matchup section block is skipped entirely; the report renders as today.

**Admin generation form (per UX delivery, 2026-04-27, vertical-stack layout):**
- Container: existing `bg-gray-50 border border-gray-200 rounded p-4`; "Sections" group label `text-xs text-gray-600 mb-1`
- "Include pitcher predictions" checkbox (defaults: ON, backward-compat) — ships in E-228-03
- "Include matchup section" checkbox (defaults: OFF) — ships in E-228-01
- **Decision B (user override of UX recommendation, 2026-04-27)**: Both checkboxes are INDEPENDENT. NO mutual exclusion. NO auto-disable. NO inline absorption annotation. When both checked, both sections render in the report (Predicted Starter + Game Plan). Possible duplication of opposing-pitching analysis is accepted as the cost of user control.
- When matchup is checked, vanilla-JS reveal (~4 lines) shows: a `<select>` populated from `SELECT id, name FROM teams WHERE membership_type='member' ORDER BY name` with `w-full border border-gray-300 rounded px-3 py-2 text-sm` styling and help text "Stats from this team will be used to build the matchup section (head-to-head, pitcher availability, recommended lineup)."; AND an optional text input "LSB starting pitcher (optional, leave blank for system suggestion)".
- Conditional dropdown wrapper: indented `pl-6` (`pl-3` at `sm:` breakpoint) under the matchup checkbox. Indent is the only nesting indicator (no border, no background-color change).
- Empty member-team edge case: when zero `membership_type='member'` rows exist, the matchup checkbox is rendered with `disabled` AND a help text "Add a member team in /admin/teams to enable matchup analysis." Route handler passes `has_member_teams: bool` to template context.
- Server-side validation: matchup checked but dropdown empty → form re-renders with the existing red error flash pattern.
- Mobile (375px): vertical stack works; submit button is `w-full sm:w-auto`.

**CLI surface:**
`bb report generate <gc_url>` gains optional flags:
- `--our-team <id-or-public_id>` -- enables matchup section (with `--starter` optional)
- `--starter <player_id-or-name>` -- pre-selects an LSB starting pitcher; when omitted, the three-gate prediction logic runs

Omitting `--our-team` preserves today's exact behavior. The flag accepts either a numeric `teams.id` or a `public_id` slug; the implementer chooses the resolution scheme (recommend public_id for symmetry with the existing `gc_url` arg).

### Engine Architecture (Mirrors Predicted-Starter)

**File layout:**
- `src/reports/matchup.py` -- deterministic engine + dataclass definitions + `build_matchup_inputs()` input builder. The engine `compute_matchup()` is a pure function (no DB, no HTTP). `build_matchup_inputs()` does ALL DB queries.
- `src/reports/llm_matchup.py` -- Tier 2 LLM wrapper, mirrors `src/reports/llm_analysis.py` exactly: `_format_*_table()` helpers, `_build_user_prompt()`, `enrich_matchup()`, system prompt template constant.
- New query helpers in `src/api/db.py` -- per-component DB queries (loss recipe, recent form, head-to-head, hitter pitch tendencies, opponent pitching workload, top-hitter ranking).

**Pure-function discipline:**
`compute_matchup(inputs: MatchupInputs) -> MatchupAnalysis` takes ALL data pre-resolved (jersey numbers, names, spray points, loss recipes already structured). No DB calls inside the engine. This mirrors `compute_starter_prediction()` (lines 844-1073 of `starter_prediction.py`) and is what makes engine tests fast and DB-free.

### MatchupInputs / MatchupAnalysis Dataclass Shape

`MatchupInputs` is the input contract -- everything the engine needs, pre-resolved:

```python
@dataclass
class MatchupInputs:
    opponent: TeamProfile           # name, record, season aggregates summary
    opponent_top_hitters: list[HitterProfile]   # top N ranked, with season + recent_form + spray + pitch_tendencies
    opponent_pitching: list[PitcherProfile]     # workload, role, rest math
    opponent_bullpen_pattern: list[ReliefPattern]  # ordered list of typical bullpen entries
    opponent_losses: list[LossRecipe]   # per-loss: pitcher of record, score, classification bucket, run-distribution-by-inning
    lsb_team: TeamProfile | None    # None when no our_team_id
    lsb_pitching: list[PitcherProfile] | None   # for starter prediction logic
    lsb_top_hitters: list[HitterProfile] | None  # for lineup card
    lsb_starter_override: str | None    # player_id when user provided one
    head_to_head: list[GameSummary] | None   # current-season prior matchups
    starter_prediction: StarterPrediction | None  # the existing predicted-starter dataclass; used for LLM consistency check
    reference_date: datetime.date
    data_completeness: DataCompleteness   # populated by input builder; per DE H-1
```

`HitterProfile` carries the per-hitter signals the engine consumes for ranking + TL;DR slot 3 + AVOID logic. Required fields:

```python
@dataclass
class HitterProfile:
    player_id: str
    name: str
    jersey_number: int | None
    pa: int
    obp: float
    slg: float
    bb_pct: float                    # required for TL;DR slot 3 (avoid-walk detection)
    k_pct: float
    fps_swing_rate: float | None     # first-pitch-swing rate from get_hitter_pitch_tendencies; None if no plays data
    pull_pct: float | None           # from spray_charts; None if no spray data
    recent_form: RecentForm | None   # last-N-games rolling stats; None if no recent games
```

`DataCompleteness` carries the data-coverage signals the narrative layer surfaces to coach:

```python
@dataclass
class DataCompleteness:
    opponent_games_with_own_perspective_count: int
    opponent_games_total: int
    games_missing_opponent_perspective: list[str]   # per DE-F2; per-game ID list, narrative says "loss-recipe based on N of M losses"
    scouting_last_run_at: str | None                # ISO timestamp from scouting_runs.completed_at
    plays_loaded_per_game: dict[str, bool]          # game_id → has plays rows
```

`MatchupAnalysis` is the engine's output:

```python
@dataclass
class MatchupAnalysis:
    confidence: str    # "high" | "moderate" | "low" | "suppress"
    threat_list: list[ThreatHitter]  # each carries supporting_stats: list[StatCitation]
    pitcher_recommendation: PitcherPick | None  # populated only when three-gate passes OR override provided
    defensive_shifts: list[ShiftRecommendation]  # each carries supporting_stats
    lineup_card: list[LineupSlot] | None    # None when no LSB context
    loss_recipes: list[LossRecipeOutput]   # one of 5 buckets (starter_blew_up / pitching_duel_lost_late / bullpen_burn / got_blasted / close_loss) OR decision_unknown fallback when player_game_pitching.decision IS NULL
    bullpen_pattern: BullpenPatternSummary
    head_to_head_summary: HeadToHeadSummary | None
    tldr_directives: list[str]   # 0-3 deterministic directive strings, joined with middot at render time; survives LLM failure
    data_notes: list[DataDepthBadge]   # per-component thin-data warnings
    data_completeness: DataCompleteness   # passed through from inputs; rendered in narrative
    suppress_section: bool   # True when no LSB context AND coach scoped components require it
```

### Suppress Semantics (Two Distinct Cases)

Per coach's discovery rule "never suppress, show with badges" combined with the structural no-LSB-context case:

| Case | Behavior |
|------|----------|
| `our_team_id` is NULL | The matchup section as a whole is NOT rendered. The existing scouting report renders identically to today. This is the structural-skip case -- no LSB context, no matchup. |
| `our_team_id` is set, opponent has 0 games | `confidence="suppress"`. Matchup section renders a single placeholder block ("Insufficient opponent data for matchup analysis -- 0 games played") and skips component sub-sections. |
| `our_team_id` is set, opponent has thin data on some components (e.g., 3 games, no spray, no losses) | `confidence` is "low" or "moderate". Each component renders with a data-depth badge ("3 games / 12 PA", "no spray data", "no losses in dataset -- recipe not available"). NO whole-section hide. |
| `our_team_id` is set, all components have adequate data | `confidence="high"`, normal rendering. |

The LLM Tier 2 wrapper is invoked only when `confidence != "suppress"`. When suppressed, the renderer shows the deterministic data-depth message without invoking OpenRouter (saves cost + prevents inventing content from thin data).

### Three-Gate Starter Prediction Logic

When `lsb_starter_override` is None AND `our_team_id` is set, the engine attempts to suggest an LSB starting pitcher. ALL THREE gates must pass:

| Gate | Check |
|------|-------|
| **G1: Rest cleared** | The candidate pitcher is NOT in the league-aware excluded set. Reuses the existing `_is_excluded()` logic from `starter_prediction.py`. |
| **G2: Established starter** | The candidate has `total_starts >= 2` in the current season. Reuses `total_starts` from `build_pitcher_profiles()`. |
| **G3: Recipe match** | The candidate's K/BB ratio is closer to the average winning-pitcher profile from opponent's losses than the median rotation member's profile. Specifically: compute `target_k_per_bb = mean(K/BB ratio of opposing-team's-loss-pitchers from `loss_recipes`)`. The candidate's K/BB ratio must be within 30% of `target_k_per_bb`. **Note**: K/BB (strikeouts-per-walk) is the canonical command-efficiency metric used here, NOT K/9 (strikeouts-per-9-innings). K/9 would penalize starters who pitch fewer innings; K/BB measures pure command. |

If any gate fails, `pitcher_recommendation` is None and the section component skips. When `lsb_starter_override` IS provided, all gates are bypassed -- the override pitcher is used as-is.

When `pitcher_recommendation` is non-None, the LLM narrative leads with a 3-sentence reasoning paragraph citing all three gates, and labels the suggestion as "Suggested" (not "Recommended"), with a closing line: "You know your staff -- override as needed."

### Provenance: Inline Citation Pattern

Per coach's locked rule, the three categories below MUST emit inline citations in the rendered prose. Each `Recommendation` dataclass field carries a `supporting_stats: list[StatCitation]` field with `(label, value, sample_size)` tuples. The LLM prompt instructs the model to weave these into the prose as parentheticals:

| Recommendation Type | Citation Examples |
|--------------------|-------------------|
| Pitcher choice | "Suggested: Von Seggern (5d rest, 24 IP / 38 K, K/BB profile matches losses)" |
| Pitch-attack per hitter | "Attack first pitch on Shockey (2 BB / 91 PA)" |
| Defensive shifts | "Shift to pull side on Schleifer (21/43 BIP to LF)" |

Coach explicitly EXEMPTED universal/mechanical baseball calls ("slide step with runners on first") and NSAA compliance reminders from the citation requirement. The system prompt must list these exceptions explicitly so the model doesn't over-cite.

### Anti-Patterns: Inline-Only Pairing

Per coach's rule, "what to avoid" content is paired with the corresponding positive instruction in the SAME prose paragraph -- not a separate section. The LLM prompt instructs:

> For each pitch-attack note, when the hitter has a high-OBP profile (>.450) where the pitcher's instinct is to nibble, append an inline "Do not" clause to the positive instruction. For pitcher-management decisions with hard thresholds (e.g., "exit by 80 pitches"), state the threshold inline. Maximum 2-3 inline avoid notes per hitter; do NOT restate the negative when the positive instruction already implies it.

### LLM Prompt Design (Mirrors `llm_analysis.py`)

**System prompt** structure (mirroring `_SYSTEM_PROMPT_TEMPLATE` in `llm_analysis.py:40-68`):
- Identity: "high school baseball coaching analyst producing matchup-strategy intelligence"
- Embed `format_nsaa_rest_table()` output verbatim (matchup pitching availability claims depend on these rules)
- Output schema: strict JSON with named fields (`game_plan`, `hitter_notes`, `shift_notes`, `lineup_recommendation`, `loss_recipe_narrative`, `bullpen_pattern_narrative`)
- **Hallucination ban**: "Do NOT invent statistics, names, or game results not present in the structured data above. Every claim must trace to a specific row of the input tables."
- **Voice rules from coach**: "It is not a data display; it is an argument. Lead with the recommendation, support with evidence in parenthetical. Direct, decisive, conclusion-first."
- **Citation requirement**: "For every recommendation in [pitcher choice, pitch-attack per hitter, defensive shifts], embed an inline parenthetical citing the supporting data point. Do NOT cite for universal baseball calls or NSAA compliance reminders."
- **Avoid-clause rule**: as described above.

**User prompt** (mirroring `_build_user_prompt`):
- Render `MatchupInputs` as ASCII tables: top hitters with all stats + spray + tendencies, opposing pitching with rest math, loss recipes table, head-to-head summary, LSB pitching table (when present), starter prediction summary (when present)
- Include the predicted-starter dataclass output verbatim so the matchup narrative cannot contradict the predicted-starter section

**OpenRouter call parameters:**
- `model = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-haiku-4-5-20251001")` (mirrors line 230 of llm_analysis.py)
- `max_tokens=1500` (bumped from 512 -- matchup produces more sections; cost still <$0.01/call)
- `temperature=0.3` (same as predicted-starter -- natural variation atop deterministic core)
- Single-pass JSON response. Parse with `json.loads()`. Validate every required field is present and a string. Raise `LLMError` on any structural failure (mirrors lines 252-275 of llm_analysis.py).

### Hallucination Guardrail: Player-Name Round-Trip

The Tier 2 LLM may NEVER name a player not present in the deterministic dataclass. Tests enforce this:
- Prompt-construction snapshot test asserts the user prompt contains exactly the names from `MatchupInputs.opponent_top_hitters`, `MatchupInputs.opponent_pitching`, `MatchupInputs.lsb_pitching` (when present)
- Renderer test: render with a stubbed LLM response that injects an unknown name; assert the renderer either filters the unknown name or rejects the response (failure mode TBD by SE -- recommend fail-loud during dev, fail-graceful in prod)

### Plays in `bb data scout` (Story E-228-02)

Per `scouting-data-flows.md` and `architecture-subsystems.md`, scouting pipeline parity requires both `run_scouting_sync` (web) and `_scout_live` (CLI) to produce equivalent data artifacts. Today neither path includes plays crawl/load. Story E-228-02 wires:

- After step 5 (post-spray dedup sweep) in both paths: invoke plays crawl + plays load + `reconcile_game()` for each game in the scout result.
- Whole-game idempotency: the plays loader already enforces `SELECT 1 FROM plays WHERE game_id = ? AND perspective_team_id = ? LIMIT 1` (per perspective-provenance rule). Re-running scout is safe.
- Auth-expiry handling: mirror the report-flow pattern (lines 1099-1110 of generator.py). `CredentialExpiredError` is caught and logged; the plays stage is non-fatal to scout overall.
- `crawl_jobs` row updates a new `plays_crawled` / `plays_loaded` step OR carries them in the existing step counters (SE judgment).

Note: the standalone reports flow ALREADY runs plays inline (lines 1091-1110 of generator.py), so this story is about parity for the dashboard/tracked-team path.

### Data Layer (Per DE Consultation, 2026-04-27)

The matchup data layer REUSES five existing helpers in `src/api/db.py` (cite by line for implementer reference) and ADDS only three new helpers. Loss-recipe classification and close-game filtering live in the ENGINE (E-228-05), not as separate query helpers, per DE's "queries fetch facts; engine derives narratives" principle.

**Reused existing helpers (no code change, story documents them as matchup consumers):**
- `get_team_games(team_id, season_id)` at `src/api/db.py:328` — opponent's full game log; engine derives W/L/margin/close-game in Python
- `get_pitching_history(team_id, season_id)` + `build_pitcher_profiles(history)` at `src/api/db.py:2663` / `2748` — every pitching appearance with `decision`, `appearance_order`, `rest_days`, `team_game_number`; covers loss-recipe attribution AND bullpen burn classification. Hard-pinned to own-perspective; the input builder enforces a coverage pre-flight gate.
- `get_pitching_workload(team_id, season_id, reference_date)` at `src/api/db.py:219` — already accepts generic `team_id`; called twice (opponent + LSB)
- `get_player_spray_events(player_id, season_id)` + batch variant `get_players_spray_events_batch` at `src/api/db.py:2506` / `2564` — hitter spray tendencies
- `get_opponent_scouting_report` at `src/api/db.py:799` — significant overlap with matchup assembly; input builder reuses pieces, does not reimplement

**New helpers (3 total):**
- `get_top_hitters(team_id, season_id, limit, min_pa)` — joins `player_season_batting` + `players` + `team_rosters`; OPS computed in SQL per the verbatim formula in E-228-04 AC-6
- `get_hitter_pitch_tendencies(player_id, season_id)` — player-level aggregates: `total_pa_with_plays`, `fps_seen`, `two_strike_pa`, `full_count_pa`, swing rate by count, chase signals from `play_events.pitch_result`
- `get_pitcher_fps_pct(team_id, season_id)` — per-pitcher FPS% from `plays.is_first_pitch_strike`; query MUST include `WHERE outcome NOT IN ('Hit By Pitch', 'Intentional Walk')` to match the existing `idx_plays_fps` partial index predicate

**Conditional index:**
`idx_play_events_play_first_pitch ON play_events(play_id, is_first_pitch)` is added in `migrations/017_play_events_first_pitch_index.sql` ONLY if `EXPLAIN QUERY PLAN` on the production-scale fixture shows table-scan on the `get_hitter_pitch_tendencies` query. Otherwise the index is deferred. Decision recorded in story PR description with EXPLAIN output.

### Cross-Perspective Traps (Per DE D)

Three perspective traps the input builder MUST handle correctly:

1. **`get_pitching_history` is hard-pinned to own-perspective** (`team_id = perspective_team_id`). Computing matchup against an opponent requires the opponent's own-perspective boxscore data to be loaded. Pre-flight gate in the input builder (E-228-06 AC-6): when `game_perspectives` opponent-perspective coverage falls below `_MIN_OPPONENT_PERSPECTIVE_COVERAGE` (default 0.5), the builder refuses to construct full inputs and a `data_notes` flag explains the refusal; engine returns `confidence="suppress"`.
2. **Cross-perspective player UUIDs in head-to-head plays.** The same opponent batter has different `player_id` UUIDs in LSB's plays vs the opponent's plays. Pick ONE perspective and stay in it. Default: LSB perspective on head-to-head games (the input builder's choice; documented in the docstring).
3. **`player_season_batting` aggregates have NO `perspective_team_id` column.** Perspective is filtered at compute time. The `get_top_hitters` helper does NOT take a `perspective_team_id` parameter. Documented in the helper's docstring; verified by an explicit test in E-228-06 AC-T5c.

### Top-Hitter Ranking Signal

Default ranking signal: **OPS computed on the fly in SQL** per DE G — verbatim formula in E-228-04 AC-6. Sort descending. Limit to top 5 hitters with `pa >= min_pa` (default 10) to filter pinch-hitters.

### Loss-Recipe Classification (Engine -- E-228-05, Not Query Layer)

The engine classifies opponent losses by joining `get_team_games(opponent_team_id, season_id)` with `get_pitching_history(opponent_team_id, season_id)` outputs in memory. Five buckets per DE F:

| Bucket | Heuristic |
|--------|-----------|
| `starter_blew_up` | starter `ip_outs < 12` AND starter `er >= 4` AND `decision = 'L'` on starter |
| `pitching_duel_lost_late` | starter `ip_outs >= 18` AND starter `er <= 2` AND `decision = 'L'` on a reliever |
| `bullpen_burn` | starter `ip_outs >= 12` AND `COUNT(DISTINCT pitchers) >= 3` AND total pen `er >= 3` |
| `got_blasted` | total team `er >= 6` OR `abs(margin) >= 6` |
| `close_loss` | `abs(margin) <= 2` AND none of the above match |

**Sixth fallback bucket: `decision_unknown`** -- when `player_game_pitching.decision IS NULL` for an opponent loss, the engine classifies as `decision_unknown` AND emits a `data_notes` flag per DE E. Engine MUST NOT guess pitcher of record; the narrative layer surfaces the gap to coach.

**Thresholds are HS-calibrated** (per Coach S-1, S-2 review): `bullpen_burn` uses `>= 3 distinct pitchers` (NOT `>= 4` MLB-norm; HS reality has starter+2-relievers as the bullpen-burn pattern). `got_blasted` uses `>= 6` (NOT `>= 8`; 5-run loss is a HS blowout). Threshold values are coach-tunable -- module-level constants -- and may be refined post-ship. Same pattern as `_PRIMARY_STARTER_GS_RATIO` in `starter_prediction.py`.

### Data Completeness Block (Per DE H-1)

`MatchupAnalysis.data_completeness` is populated with these fields:
- `opponent_games_with_own_perspective_count: int` — count of opponent games with rows in `game_perspectives` for opponent-perspective coverage
- `opponent_games_total: int` — total game count for the opponent's season (from `get_team_games`)
- `games_missing_opponent_perspective: list[str]` — list of game_ids without opponent-perspective coverage (per DE-F2; allows narrative honesty: "loss-recipe based on 14 of 18 losses")
- `scouting_last_run_at: str | None` — ISO timestamp from `scouting_runs.completed_at` for the most recent completed run for `(team_id = opponent_team_id, season_id, status = 'completed')`. Per-scout-run timestamp is more accurate than `teams.last_synced` because a partial scout updates `last_synced` but the coverage gap may persist. Source: `SELECT MAX(completed_at) FROM scouting_runs WHERE team_id = ? AND season_id = ? AND status = 'completed'`.
- `plays_loaded_per_game: dict[str, bool]` — game_id → whether `plays` table has rows for that game

The narrative layer surfaces gaps to coach (e.g., "scouting last refreshed 4 days ago"; "12 of 18 games have plays data"; "loss-recipe analysis based on 14 of 18 losses — 4 games lack opponent-perspective coverage"). This is the operator-and-coach-facing freshness UX that mitigates the workload-staleness risk DE flagged in H-3 and the partial-coverage trap DE flagged in F2.

### Recent Form Overlay (Per Coach S-4: Last N Games, Not Last N Days)

For each top hitter, render BOTH season-aggregate stats AND last-N-games rolling stats side-by-side. **Window is by GAME COUNT, not calendar days** -- per project data philosophy ("coaches think in games, not sync timestamps") and Coach S-4 review. HS schedules cluster around school calendars (double-headers, weekend tournaments), making calendar-day windows misleading.

Default window: **last 7 games** (constant `_RECENT_FORM_GAME_COUNT_DEFAULT = 7`). The recent-form computation runs at query time over `player_game_batting WHERE player_id = ? AND perspective_team_id = ? ORDER BY game_date DESC LIMIT N`. The `perspective_team_id` filter is REQUIRED per perspective-provenance rule -- recent form is per-perspective.

Implementation lives in a dedicated helper `get_player_recent_form(conn, player_id, season_id, *, last_n_games=7, perspective_team_id, db=None) -> RecentForm` (added in E-228-04 per DE-F5). Returns aggregated `pa, ab, h, bb, hbp, obp, slg, games_in_window`. The `RecentForm` dataclass surfaces `games_in_window` so the renderer can show `Last 7G` (or fewer if season has played less than 7 games for the player) and the data-depth badge can flag thin samples.

Display format per UX (E-228-09 AC-14): `Season X (PA) / Last 7G Y (PA) [arrow]` where arrow ↑↔↓ renders at `|season_obp - recent_obp| >= _RECENT_FORM_ARROW_THRESHOLD` (default 0.100).

### Head-to-Head Sidebar

Per SE follow-up (2026-04-27), head-to-head ships in v1 as opportunistic via `team_opponents` lookup:

```sql
-- Step 1: Resolve LSB team (when our_team_id is provided, this is direct)
-- Step 2: Pull current-season head-to-head games
SELECT g.game_date, g.home_team_id, g.away_team_id, g.home_score, g.away_score, g.game_id
FROM games g
WHERE g.season_id = ?
  AND ((g.home_team_id = :lsb_id AND g.away_team_id = :opp_id)
       OR (g.home_team_id = :opp_id AND g.away_team_id = :lsb_id))
  AND g.home_score IS NOT NULL
  AND g.away_score IS NOT NULL
ORDER BY g.game_date DESC;
```

When `our_team_id` is provided, this is the LSB team directly. When `our_team_id` is NOT provided AND a unique LSB team can be resolved from `team_opponents WHERE opponent_team_id = :report_team_id`, head-to-head still renders. When `our_team_id` is NOT provided AND zero or multiple matches exist in `team_opponents`, the sidebar is silently absent.

Per SE finding: ~5-15% of opponents have multiple `team_opponents` rows (when an opponent plays multiple LSB levels). For v1, the sidebar silently skips in that case rather than guess. Captured in Open Questions for follow-up.

### Perspective-Provenance Compliance

All matchup queries that read per-player stat tables (`player_game_batting`, `player_game_pitching`, `spray_charts`, `plays`) MUST filter by `perspective_team_id`. The standalone reports flow uses the opponent's team_id as the perspective for opponent stats. For LSB stats (when `our_team_id` is set), the perspective is the LSB team's id.

Reuse the existing `_query_plays_*` helpers in `src/reports/generator.py` for plays-derived signals (FPS%, QAB%, count-based outcomes). New helpers added in E-228-04 must follow the same pattern.

### Feature Flag

`FEATURE_MATCHUP_ANALYSIS` env var gates the new section, mirroring `FEATURE_PREDICTED_STARTER`. When unset or false, the admin checkbox is hidden, the CLI flag emits a "feature disabled" warning, and `generate_report()` ignores `our_team_id`. Default: enabled in dev, controlled by ops in prod.

### Game Plan Section UX (Per UX Layout, 2026-04-27)

**Section title**: "Game Plan" (three syllables, fits at 11pt header without wrapping at 375px). Field language, not meeting language. Distinct from "Predicted Starter" (data prediction) — Game Plan signals prescriptive intent.

**Section placement** when enabled (verbatim section order per UX HIGH-1):
```
Header → Exec summary → Game Plan → Recent form chips → Key players → Predicted Starter (when also enabled) → Pitching → Batting → Spray → Roster → Footer
```
Game Plan is inserted between exec summary and recent form chips. Predicted Starter (when enabled per user decision B) is pushed DOWN past Recent Form chips and Key Players to its post-Game-Plan position. The two sections coexist without mutual exclusion. When Game Plan is OFF, Predicted Starter renders in its current position (between exec summary and recent form chips) -- no other section reorders.

**Sub-section order** (six fixed sub-sections):
1. **Head-to-Head banner** — full-width strip styled like `.exec-summary` (NOT a sidebar; sidebars don't print well at 9pt with ~2.5in column). Omitted entirely when no prior matchups (no empty placeholder).
2. **Opposing Pitching** — predicted-starter-card-style + bullpen-entry callout + rest table.
3. **Dangerous Hitters** — per-hitter pitch-attack notes with recent-form overlay.
4. **Defensive Shifts** — per pull-tendency hitter, spray-driven.
5. **LSB Lineup card + LSB starter "last 3 exits" workload note** (italic at end).
6. **Loss Recipe** (2-3 sentence prose) + **Matchup Analysis** (LLM narrative in `.starter-narrative-style` block).

**TL;DR line** at top of section (BELOW section header, ABOVE head-to-head banner):
- 10pt bold, single line, three slots joined by middots (`·`).
- **DETERMINISTIC, NOT LLM-generated** — built from the same `MatchupAnalysis` dataclass that drives sub-sections, to guarantee coherence with the directives below. If LLM Tier 2 fails, TL;DR still renders.
- Slot 1: LSB starter recommendation directive (e.g., "Pitch Von Seggern"). Omitted when `pitcher_recommendation is None` (TL;DR has 2 directives, not 3).
- Slot 2: Top hitter to attack from threat tier 1 (e.g., "Attack Fredrick early").
- Slot 3: Top hitter to avoid walking from highest BB% threat (e.g., "Avoid walking Shockey"). Populated when `threat_list` has at least one hitter with `bb_pct >= _AVOID_WALK_BB_PCT_THRESHOLD` (default 0.10).

**Provenance citations**: inline italic gray parenthetical immediately after the directive, lowercase, same font size (8.5pt italic). NO badges, NO tooltips, NO separate column. Examples: `(.700 SLG vs FB)`, `(1-for-12)`, `(21/43)`. For very short directives where citation IS the directive (e.g., "Shift LF (21/43)"), the citation is part of the directive text — engine handles in prose, renderer preserves verbatim.

**Recent-form overlay**: format `Season X (PA) / Last 7G Y (PA) [arrow]`. Unicode arrow ↑↔↓ rendered when `|season_obp - recent_obp| >= _RECENT_FORM_ARROW_THRESHOLD` (default 0.100). Smaller swings render no arrow. PA badges integral — never omitted (they communicate sample size). Sparkline rejected (unreadable at 9pt print). Delta-only rejected (hides absolute values). Example: `TAGGE  #7    Season .512 OBP (82 PA)  /  Last 7G .312 OBP (8 PA)  ↓`

**Inline AVOID treatment**: indented sub-bullet under the positive directive. "AVOID:" prefix in 7pt small caps bold. Body text in 8.5pt regular. NO color, NO icon, NO border (color-free differentiation that survives B&W printing). Example:
```
SHOCKEY  #14
Attack the zone — he chases off-speed away (2 BB in 91 PA).
  AVOID: Don't fall behind. He's .680 OBP when ahead in count
  (47 PA after 1-0 or 2-1).
```

**Visual hierarchy** (font sizes/weights):
| Element | Style |
|---------|-------|
| Section header `GAME PLAN` | 11pt small caps |
| TL;DR line | 10pt bold, single line, middot-joined |
| Sub-section header | 10pt small caps + horizontal rule above |
| Hitter/pitcher name | 9pt bold |
| Body prose | 8.5pt regular |
| Citations | 8.5pt italic gray |
| AVOID prefix | 7pt small caps bold, indented |
| LLM narrative | 8.5pt regular, left border (`.starter-narrative-style`) |

**Print mechanics**:
- Game Plan uses the existing stats-page named page (landscape).
- Each sub-section: `break-inside: avoid`.
- Per-hitter blocks within Dangerous Hitters: `break-inside: avoid` individually (positive + AVOID don't split across pages).
- TL;DR: `break-after: avoid` (keeps adjacent to head-to-head banner).

**Mobile (375px viewport)**: vertical stack. Recent-form line wraps via `flex-wrap`. Lineup card stays 1-column. Head-to-head banner remains full-width. AVOID indent reduces from `pl-6` to `pl-3` at `sm:` breakpoint.

### Test Strategy (Quality Bar: WELL Tested)

The user established WELL-tested-and-documented as a hard quality gate. Each story has explicit test ACs naming what's tested AND how a reviewer verifies meaningfulness. The test surface is layered:

**Pure-engine tests** (`tests/test_matchup.py`, E-228-05):
Hand-built `MatchupInputs` fixtures, no DB. Mirror `tests/test_starter_prediction.py`. Cover golden-path, structural-suppress, top-hitter ranking + tie-break, ALL 8 G1×G2×G3 truth-table combinations for the LSB starter prediction (parameterized), shift-threshold edge cases, lineup truncation, loss-recipe per-bucket, data-depth badges, citation round-trip. Includes a code-level purity assertion (engine has no `sqlite3` / `httpx` / file imports).

**Input-builder + DB-query tests** (`tests/test_matchup_inputs.py` E-228-06, `tests/test_db_matchup_queries.py` E-228-04):
Multi-scope fixture DB (2+ seasons, 2+ teams, cross-perspective rows) seeded by a shared `_seed_multiscope_db()` function. EVERY helper has a paired `test_<helper>_filters_by_team_id_and_season_id` assertion -- catching the cross-scope-contamination bug class is the load-bearing requirement here.

**LLM wrapper tests** (`tests/test_llm_matchup.py`, E-228-07):
Mirror `tests/test_llm_analysis.py`. Mocked `query_openrouter` throughout (NEVER hits real API per testing.md rule). Cover golden-path response parsing, prompt-construction snapshot (player-name round-trip), system-prompt rules verbatim, JSON parsing error paths, suppress short-circuit (LLM not called), hallucination guardrail in BOTH `FEATURE_MATCHUP_STRICT` modes, error-path propagation, OpenRouter parameters pinned (model + temp + max_tokens).

**Generator orchestration tests** (`tests/test_generator_matchup.py`, E-228-01/03/08):
End-to-end at the `generate_report()` boundary. Mocked GC client + mocked OpenRouter. Cover Tier 1 + Tier 2 success, Tier 2 unavailable, Tier 2 error swallowed, suppress short-circuit, LSB-scout error, auth-expiry mid-LSB-scout, sequencing assertion (matchup runs after reconciliation), title update, and the LOAD-BEARING regression: byte-identical HTML to baseline when `our_team_id is None`.

**Pipeline parity tests** (`tests/test_cli_data_scout_plays.py` + `tests/test_pipeline_scouting_sync_plays.py`, E-228-02):
The `test_cli_and_web_paths_produce_equivalent_artifacts` test runs both `_scout_live` AND `run_scouting_sync` against identical fixture inputs and asserts equivalent DB outcomes -- this is the parity invariant in CLAUDE.md made executable. Plus per-game error isolation, auth-expiry resilience, idempotency.

**CLI tests** (`tests/test_cli_report_matchup.py`, E-228-01):
Subprocess smoke test (`subprocess.run(["bb", "report", "generate", "--help"], ...)`) per testing.md to catch packaging/import errors that in-process Typer test runners mask. Plus in-process `CliRunner` tests for flag parsing, error-path tests for orchestration (unknown team value surfaces to operator).

**Renderer tests** (`tests/test_renderer_matchup.py`, E-228-09):
Snapshot tests against checked-in expected-output fixtures (`expected_game_plan_section.html`, `baseline_scouting_report.html`). The visual-regression catch is bracketed: matchup-on output AND matchup-off output. Plus citation preservation (catches over-zealous Jinja escape filters), data-depth badges, existing-sections-unchanged, print-stylesheet rules.

**Test-validates-spec compliance** (per testing.md):
Mocks for plays JSON, OpenRouter responses, and DB fixtures mirror authoritative specs (`docs/api/endpoints/get-game-stream-processing-event_id-plays.md`, `src/llm/openrouter.py` docstring, `migrations/001_initial_schema.sql` enum values) -- NOT copied implementation behavior. Reviewer verifies by opening source-of-truth side-by-side.

**Backward-compat regression (P0):**
The byte-identical baseline test (`tests/fixtures/baseline_scouting_report.html`) is the single most important test in the epic. ANY change that breaks existing single-team scouting reports is a P0 regression. This fixture is created in E-228-01 and re-used by E-228-08 and E-228-09.

**Hallucination guardrail (NEVER ship a hallucinated player name):**
Two-layer defense: the wrapper's post-parse name validation (E-228-07) AND the prompt-construction snapshot test (asserts every name in the input appears in the user prompt). Documented policy: `FEATURE_MATCHUP_STRICT=1` raises `LLMError` (fail-loud); unset filters the offending recommendation (fail-graceful).

**Test Scope Discovery (per testing.md):**
Every story's DoD includes: grep `tests/` for any test importing from modified source modules; run discovered tests in addition to story-scoped tests. This catches cross-file dependencies that story-scoped test lists miss (the E-085 failure mode).

### Documentation Strategy (Quality Bar: WELL Documented)

Documentation is story work, not closure deferral:

- **Code-level documentation** (docstrings, inline comments): scoped to the story that implements the code. Each story's documentation ACs name what gets a docstring and the reviewer-meaningfulness criterion ("a reader unfamiliar with this epic can ...").
- **User-facing documentation**: consolidated in E-228-10 (docs-writer) AFTER all code stories complete. Coach-voice page in `docs/coaching/`, operator-voice page in `docs/admin/`, optional dev page in `docs/api/flows/`. Audience-appropriate language is verified by a non-author reviewer.
- **Context-layer documentation**: bundled in E-228-11 (claude-architect closure). Rule extensions to `key-metrics.md` (matchup signals if stabilized), `architecture-subsystems.md` (Two-Tier Enrichment Pattern second instance), `scouting-data-flows.md` (one-sentence matchup example), conditional CLAUDE.md canonical-helper line.

The two ordering invariants:
1. User-facing docs ship AFTER code (so docs reflect actual shipped behavior, not original spec)
2. Context-layer codification ships AFTER user-facing docs (so rule edits reference the documented surface)

### Dispatch Sequencing

Stories execute serially per the dispatch pattern. Dependency ordering:

```
E-228-01 (Path C lift) ──┬──→ E-228-03 (pitcher checkbox) ──┐
                          └──→ E-228-08 (generator wire) <───┤
E-228-02 (plays in scout) ──┬──→ E-228-04 (query helpers) ──→ E-228-05 (engine) ──→ E-228-06 (input builder)
                              │                                                                              │
                              └────────────────────────────────────────────────────────→ E-228-08 ←──────────┤
                                                                                                              │
                                                          E-228-05 ──────────→ E-228-07 (LLM wrapper) ───────┤
                                                                                                              ▼
                                                                                                          E-228-08 ──→ E-228-09 (renderer)
                                                                                                                                  └──→ E-228-10 (docs-writer)
                                                                                                                                                  └──→ E-228-11 (architect closure)
```

Critical paths: E-228-01 → 08 (architectural lift gates everything user-facing); E-228-04 → 05 → 06 → 08 (data layer feeds engine); **E-228-02 → 08 (plays-in-scout wiring required for LSB-side scout in E-228-08 per api-scout HIGH-2 — three-gate G2 + loss-recipe depend on reconciled plays); E-228-03 → 08 (file conflict on `generator.py` predicted-starter block per CR F-08-1)**. E-228-02 (plays in scout) is independent of E-228-01/03 and can ship in parallel. E-228-10 (docs-writer) ships AFTER all code complete so docs reflect actual shipped behavior, BEFORE E-228-11 (closure) so context-layer rule edits reference the documented surface.

### Files Touched (Cross-Story Reference)

This list helps detect file-level conflicts between stories. Each story's "Files to Create or Modify" must agree.

| File | Stories That Touch It |
|------|-----------------------|
| `migrations/002_add_our_team_id_to_reports.sql` | E-228-01 (creates) |
| `migrations/003_play_events_first_pitch_index.sql` (CONDITIONAL) | E-228-04 (creates only if EXPLAIN justifies) |
| `src/reports/generator.py` | E-228-01 (parameter), E-228-08 (matchup orchestration) |
| `src/cli/report.py` | E-228-01 (CLI flag), E-228-03 (pitcher flag) |
| `src/cli/data.py` | E-228-02 (`_scout_live`) |
| `src/pipeline/trigger.py` | E-228-02 (`run_scouting_sync`) |
| `src/api/routes/admin.py` | E-228-01 (form fields), E-228-03 (pitcher checkbox) |
| `src/api/templates/admin/reports.html` | E-228-01 (checkboxes + dropdown), E-228-03 (pitcher checkbox), E-228-09 (warning text) |
| `src/api/db.py` | E-228-04 (3 new helpers + docstring updates on 5 reused helpers) |
| `src/reports/matchup.py` (new) | E-228-01 (minimal `is_matchup_enabled()`), E-228-04 (input dataclasses for new-helper returns), E-228-05 (engine + analysis dataclasses), E-228-06 (input builder + pre-flight gate) |
| `src/reports/llm_matchup.py` (new) | E-228-07 |
| `src/gamechanger/pipelines/plays_stage.py` (new -- per SE-C4) | E-228-02 (creates the shared helper for plays crawl + load + reconcile, called by `_scout_live`, `run_scouting_sync`, and refactored `generator.py`) |
| `src/reports/renderer.py` | E-228-09 |
| `src/api/templates/reports/scouting_report.html` | E-228-09 (matchup section) |
| `tests/fixtures/baseline_scouting_report.html` (new) | E-228-01 (creates per AC-4 deterministic substitution); E-228-09 (regenerates if `scouting_report.html` is modified per SE-M6) |
| `tests/fixtures/seed_baseline_db.py` (new -- per AC-4a / SE-C2) | E-228-01 (fixture-DB seed function for byte-equality regression test) |
| `tests/fixtures/README.md` (new) | E-228-01 (documents fixture-DB seed recipe + regeneration) |
| `scripts/regenerate_baseline_fixture.py` (new -- per AC-4b / SE-C2) | E-228-01 (regeneration script for the byte-equality baseline fixture) |
| `tests/fixtures/plays_response_sample.json` (new) | E-228-02 |
| `tests/fixtures/matchup_analysis_golden.py` (new) | E-228-09 |
| `tests/fixtures/expected_game_plan_section.html` (new) | E-228-09 |
| `tests/test_migration_002.py` (new) | E-228-01 |
| `tests/test_generator_matchup.py` (new) | E-228-01, E-228-03 (extend), E-228-08 (extend) |
| `tests/test_admin_reports_matchup.py` (new) | E-228-01, E-228-03 (extend) |
| `tests/test_cli_report_matchup.py` (new) | E-228-01, E-228-03 (extend) |
| `tests/test_cli_data_scout_plays.py` (new) | E-228-02 |
| `tests/test_pipeline_scouting_sync_plays.py` (new) | E-228-02 |
| `tests/test_db_matchup_queries.py` (new) | E-228-04 |
| `tests/test_matchup.py` (new) | E-228-05 |
| `tests/test_matchup_inputs.py` (new) | E-228-06 |
| `tests/test_llm_matchup.py` (new) | E-228-07 |
| `tests/test_renderer_matchup.py` (new) | E-228-09 |
| `CLAUDE.md` | E-228-11 (parity invariant text + Two-Tier Enrichment Pattern reference + optional canonical-helper line; moved out of E-228-02 per routing-precedence rule) |
| `.claude/rules/architecture-subsystems.md` | E-228-11 (Scouting Pipeline section + Two-Tier Enrichment Pattern; moved out of E-228-02 per routing-precedence rule) |
| `.claude/rules/key-metrics.md` | E-228-11 (matchup signals if stabilized) |
| `.claude/rules/scouting-data-flows.md` | E-228-11 (one-sentence matchup example) |
| `docs/api/flows/opponent-scouting.md` | E-228-02 (review/update if plays in flow), E-228-10 (verification) |
| `docs/coaching/matchup-report.md` (new) | E-228-10 |
| `docs/admin/matchup-report-generation.md` (new) | E-228-10 |
| `docs/coaching/README.md` (extend if exists) | E-228-10 |
| `docs/admin/README.md` (extend if exists) | E-228-10 |

### Post-Ship Tuning Plan

These constants are starting-point values codified in code as module-level constants. Each is coach-tunable post-ship. None block READY.

| Constant | Default | Story | Coach validates |
|----------|---------|-------|-----------------|
| Loss-recipe thresholds (5 buckets, HS-calibrated per Coach S-1/S-2) | starter_blew_up: ip_outs<12 AND er>=4 / pitching_duel_lost_late: ip_outs>=18 AND er<=2 AND L on reliever / bullpen_burn: ip_outs>=12 AND distinct_pitchers>=3 AND pen er>=3 / got_blasted: team er>=6 OR abs(margin)>=6 / close_loss: abs(margin)<=2 | E-228-05 AC-8 | After first real-game use |
| `_TOP_HITTER_PA_FLOOR` | 10 | E-228-04 AC-6 | After season sample established (may rise to 30) |
| `_MIN_OPPONENT_PERSPECTIVE_COVERAGE` | 0.5 | E-228-06 AC-6 | Threshold doesn't fire too aggressively in practice |
| `_AVOID_WALK_BB_PCT_THRESHOLD` | 0.10 | E-228-05 AC-12 | Yields meaningful TL;DR slot 3 directives |
| `_RECENT_FORM_ARROW_THRESHOLD` | 0.100 (OBP swing) | E-228-09 AC-15 | Arrow density (smaller = noisier; larger = under-signaling) |
| `_RECENT_FORM_GAME_COUNT_DEFAULT` | 7 | E-228-04 (recent-form helper) | Window size feels right for HS schedule density |
| `_PULL_SHIFT_THRESHOLD` | 0.55 | E-228-05 AC-6 | HS-calibrated; may need recalibration for higher-level play |
| `_RECIPE_K_PER_BB_TOLERANCE` | 0.30 | E-228-05 AC-5 (G3) | K/BB matching tolerance for three-gate recipe match |
| `_PITCH_AROUND_BB_PCT` | 0.12 | E-228-05 AC-12 (Slot 2 Template 1) | "Pitch around" trigger -- HS-calibrated patience signal at 80-100 PA per season |
| `_PITCH_AROUND_SLG` | 0.500 | E-228-05 AC-12 (Slot 2 Template 1) | "Pitch around" power floor -- combined with patience triggers most-dangerous bucket |
| `_MAKE_EARN_BB_PCT` | 0.12 | E-228-05 AC-12 (Slot 2 Template 2) | "Make earn it" trigger -- patient table-setter, no power threat |
| `_ATTACK_EARLY_FPS_SWING` | 0.50 | E-228-05 AC-12 (Slot 2 Template 3) | "Attack early" first-pitch-swing trigger |
| `_ATTACK_EARLY_BB_PCT` | 0.05 | E-228-05 AC-12 (Slot 2 Template 3) | "Attack early" free-hitter alternative trigger (low walk rate) |
| `_EXPAND_K_PCT` | 0.22 | E-228-05 AC-12 (Slot 2 Template 4) | "Expand on" K-rate trigger -- HS-calibrated chaser threshold |
| `_TLDR_DIRECTIVE_MAX_CHARS` | 25 | E-228-05 AC-12 (hard constraint) | Max chars in any TL;DR directive string including name; engine truncates name to last-name on overflow |

## Open Questions

1. **Multi-LSB-team head-to-head fallback**: When an opponent appears under multiple member teams' `team_opponents` rows AND `our_team_id` is not provided, the sidebar silently skips. Should v2 add a UI affordance ("you've played them under both Varsity and JV -- pick which") or accept "user provides `--our-team`" as the answer? Captured for follow-up; not blocking v1.
2. **Hallucination guardrail policy**: When the LLM returns a player name not in `MatchupInputs`, the wrapper applies the policy chosen via `FEATURE_MATCHUP_STRICT` env var: when set, raise `LLMError` (fail-loud); when unset, filter the offending recommendation field while preserving the rest (fail-graceful). Default chosen: fail-loud during dev (with `FEATURE_MATCHUP_STRICT=1` env), fail-graceful in prod. Codified in E-228-07 AC-7. Decision is locked, not deferred — flagged here for traceability only.

## History
- 2026-04-27: Created. Promoted from in-session matchup-strategy planning prompted by user. Discovery consultations with baseball-coach, api-scout, software-engineer, claude-architect, data-engineer (relayed shortly after Phase 2 began), ux-designer (relayed during Phase 2 refinement). User scope decisions locked: Path C, one epic, fresh-on-demand scout, member-table dropdown, three-gate starter prediction, handedness dropped, plays-in-scout added.
- 2026-04-27: Quality-bar revision. User established "WELL tested and documented" as a hard gate, not a suggestion. All story ACs reorganized into Behavior / Test Coverage / Documentation sections with reviewer-meaningfulness criteria. New E-228-10 docs-writer story added (coaching guide + admin guide); old E-228-10 architect-closure renumbered to E-228-11. Story spine grew from 10 to 11 stories. Test ACs hardened: LSB starter prediction now covers all 8 G1×G2×G3 truth-table combinations (parameterized); CLI changes include subprocess smoke tests per testing.md; orchestration code (CLI, generator) includes explicit error-path tests; mocks mirror authoritative specs per testing.md Test-Validates-Spec rule. Files Touched matrix expanded from 17 entries to 35 to include new test files, doc files, and fixture files.
- 2026-04-27: Data-engineer refinement. DE's discovery response (relayed by team-lead) materially reshaped the data layer scope: E-228-04 reduced from 8 new helpers to 3 (`get_top_hitters`, `get_hitter_pitch_tendencies`, `get_pitcher_fps_pct`); five existing helpers are documented as matchup consumers rather than rebuilt (`get_team_games`, `get_pitching_history`, `get_pitching_workload`, `get_player_spray_events`, `get_opponent_scouting_report` -- all cited by `src/api/db.py:line`). `get_loss_recipes` and `get_close_games` dropped from the helper layer per "queries fetch facts; engine derives narratives" -- moved to engine logic in E-228-05. Loss-recipe classification expanded from 3 buckets to 5 + a `decision_unknown` fallback (engine flags, never guesses, when `player_game_pitching.decision IS NULL`). New `data_completeness` block on `MatchupAnalysis` (per DE H-1) carries opponent-perspective coverage, scouting freshness, plays-loaded-per-game; surfaced by narrative layer for coach. New pre-flight gate in E-228-06 input builder: refuses to build full inputs when `game_perspectives` opponent-perspective coverage falls below `_MIN_OPPONENT_PERSPECTIVE_COVERAGE` (default 0.5). Conditional new index `idx_play_events_play_first_pitch` (migration 003) -- created only if EXPLAIN QUERY PLAN evidence justifies, decision recorded in PR. OPS computation moved into SQL helper per DE G. Cross-perspective traps documented in epic Technical Notes per DE D.
- 2026-04-27: UX layout incorporation + user decision B. UX delivered the full v1 report layout AND generation-screen design. **User decision B (override of UX's mutual-exclusion recommendation)**: Pitcher Predictions and Matchup are independent checkboxes; both can render together; NO auto-disable, NO mutual exclusion, NO inline absorption annotation. Possible duplication of opposing-pitching analysis is the accepted cost of user control. **E-228-09 (renderer)** rewritten with UX's full Game Plan spec: section title "Game Plan" (3 syllables, prescriptive language); placement immediately after exec summary, BEFORE Predicted Starter; six fixed sub-sections (head-to-head banner, opposing pitching, dangerous hitters, defensive shifts, lineup + workload note, loss recipe + LLM narrative); deterministic TL;DR line (NOT LLM-generated, three middot-joined directive slots); inline italic gray parenthetical provenance citations (no badges/tooltips/columns); recent-form overlay with Unicode arrow at ≥.100 OBP swing threshold, PA badges integral; AVOID inline sub-bullet treatment (7pt small caps bold, no color/icon/border, B&W print survives); head-to-head banner full-width (NOT sidebar); visual hierarchy table (font sizes/weights documented); print mechanics (`break-inside: avoid` per sub-section + per-hitter block, `break-after: avoid` between TL;DR and head-to-head); mobile responsive at 375px. **E-228-01 (gen-screen)** revised with UX's vertical-stack form layout: existing `bg-gray-50 border border-gray-200 rounded p-4` container; "Sections" group with two independent native HTML checkboxes; conditional dropdown indented `pl-6` under matchup checkbox with help text "Stats from this team will be used to build the matchup section..."; ~4-line vanilla JS reveal (NO auto-disable per decision B); empty member-team edge case (matchup checkbox `disabled` with help text); server-side validation when matchup checked + dropdown empty; mobile responsive. **E-228-03 (pitcher-predictions checkbox)** updated to slot into the established "Sections" group with the explicit decision-B note (independent of matchup checkbox, no JS interaction). New Open Questions added (#7 pitcher-predictions default, #8 last-used persistence, #9 avoid-walk BB% threshold, #10 recent-form arrow threshold). Last-used persistence captured for follow-on idea capture after DRAFT final.
- 2026-04-27: Phase 3 holistic review + triage. Three concurrent review tracks: CR spec audit (47 findings; verdict NOT READY), six domain expert reviews (coach 9, api-scout 7, DE 7, UX 6, SE 22, architect 5), PM-perspective holistic (11). Total 114 raw findings, 70 unique after dedup. PM consolidated triage: 56 ACCEPT (14 P1 + 24 P2 + 18 P3), 14 DISMISS with reasons. User approved all 56. Key P1 fixes incorporated: dataclass shape gaps (`data_completeness`, `tldr_directives`, `bb_pct` field on ThreatHitter, decision_unknown bucket reference); migration renumbering 016/017 → 002/003 (PM memory was stale; rule says next is 002 per E-220 schema rewrite); routing-precedence fix (CLAUDE.md + architecture-subsystems.md edits moved from E-228-02 → E-228-11 to avoid worktree-guard hook collision); `scouting_runs.completed_at` corrected from nonexistent `created_at`; 5-bucket loss-recipe names corrected in E-228-11 AC-1 (was 3 wrong names); K/9 → K/BB nomenclature fix in three-gate G3; bullpen_burn ≥4 → ≥3 (HS-calibrated per Coach S-1); got_blasted ≥8 → ≥6 (HS-calibrated per Coach S-2); per-day → last-N-games window with new `get_player_recent_form` helper; section placement verbatim ordering (resolves UX-flagged ambiguity); E-228-08 dependency on E-228-02 added; `our_team_id` resolution layer specified (CLI + admin handler); backward-compat fixture determinism with substitution scheme + regen script; HTML sanitization in E-228-07 wrapper for XSS protection. Open Questions reduced from 10 to 3 (post-ship tuning thresholds moved to dedicated section). Coach escalation (P2-T TL;DR slot 2 directive enumeration) sent during incorporation.
- 2026-04-27: Coach P2-T resolution incorporated. Coach answered Option B with 4 directive templates + priority tie-breaker (1→2→3→4) + 25-char hard constraint + missing-data fallback (skip Templates 3+4 when fps_swing_rate unavailable). Templates: T1 "Pitch around" (bb_pct>0.12 AND slg>0.500 — dangerous + patient), T2 "Make earn it" (bb_pct>0.12 AND slg≤0.500 — patient table-setter), T3 "Attack early" (fps_swing_rate>0.50 OR bb_pct<0.05 — free hitter), T4 "Expand on" (k_pct>0.22 AND 0.05≤bb_pct≤0.12 — chaser). Default fallback: T3. HS-calibrated thresholds. E-228-05 AC-12 now codifies the 4-template selection with explicit priority. E-228-05 AC-T13a/T13b/T13c added: parameterized 6-case template selection + priority tie-breaker + missing-data fallback + 25-char truncation. New module constants added to Post-Ship Tuning Plan: _PITCH_AROUND_BB_PCT (0.12), _PITCH_AROUND_SLG (0.500), _MAKE_EARN_BB_PCT (0.12), _ATTACK_EARLY_FPS_SWING (0.50), _ATTACK_EARLY_BB_PCT (0.05), _EXPAND_K_PCT (0.22), _TLDR_DIRECTIVE_MAX_CHARS (25). Open Question #3 (TL;DR enumeration) removed from epic.md — resolved.
