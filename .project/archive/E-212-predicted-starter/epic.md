# E-212: Predicted Starter

## Status
`COMPLETED`

## Overview
Add a "Predicted Starter" section to both standalone scouting reports and the dashboard opponent detail page. Analyzes a team's pitching history and predicts who will start their next game. A deterministic rotation analysis engine (Tier 1) always produces a prediction; an optional LLM layer via OpenRouter (Tier 2) enriches it with narrative analysis in standalone reports when credentials are available. Coaches get the most actionable pre-game intelligence -- "who are we facing on the mound?" -- in both scouting surfaces.

## Background & Context
The Waverly Vikings analysis (2026-04-04) demonstrated the workflow manually: query game-by-game pitching data, identify a 4-man rotation, analyze rest patterns and pitch counts, predict the next starter with likelihood percentages and reasoning. The prediction (Nienhueser at 60%) was plausible but Lade actually started -- likely a matchup decision -- validating both the approach and the need for appropriate uncertainty. This epic operationalizes that manual workflow into the report generation pipeline.

**Expert consultation completed:**
- **baseball-coach**: HS rotations are mostly ace-plus-committee or 2-man; true 3-man at competitive varsity; 4-man rare (mostly Legion). Signal ranking: MUST HAVE = days of rest + GS/GP ratio + rotation sequence; SHOULD HAVE = pitch count last outing + season aggregates; NICE = home/away. Weight: 70% rotation sequence, 30% matchup factors. Output: named starter with plain-English reasoning (NO percentages on bench report -- percentages in expanded view only); secondary = bullpen rest table for top arms (starters + relievers). Confidence tiers: High = name starter (top 2x signal weight of next); Moderate = name with caveat + alternative; Low/committee = show options, don't name a pick. Suppress entirely below 4 games. 10+ day gap = "availability unknown". Doubleheader handling (raw consultation input, refined below): coach said "predict top two starters" but TN-2 determined this is not feasible deterministically -- no forward-looking schedule data exists. Past doubleheader patterns (same-date game pairs) are observable and may inform the LLM tier narrative only.
- **data-engineer**: One query with LAG() for rest days, DENSE_RANK for team_game_number. Include all appearances (starts + relief) for workload context. Python post-processing reshapes into two views (deterministic engine + LLM prompt). No schema changes needed.
- **ux-designer**: Card stack layout after exec summary, before Recent Form. Primary candidate gets full game log; secondary candidates condensed. GS badge for sample-size context. Additive block for LLM narrative (gray left-border, "Scouting Analysis" sub-header). Always show section even with low data.
- **software-engineer**: `src/llm/openrouter.py` (reusable client), `src/reports/starter_prediction.py` (Tier 1), `src/reports/llm_analysis.py` (Tier 2). Sequential enrichment via dataclasses. httpx directly (not openai SDK). Non-fatal fallback matching plays stage pattern.

**Two-tier architecture** (user-confirmed constraint):
- **Tier 1 (deterministic)**: Pure Python. Identifies rotation pattern, computes rest intervals, determines next-in-rotation, produces top-3 candidates with algorithmic likelihoods. Always runs. No external dependencies.
- **Tier 2 (LLM-enhanced)**: Optional OpenRouter call. Produces narrative analysis, matchup context, confidence adjustments. Graceful fallback if credentials missing or call fails. Report renders cleanly in both modes.

No expert consultation required for: api-scout (no new GC API endpoints needed), claude-architect (no context-layer changes during implementation).

## Goals
- Every standalone report AND dashboard opponent detail page includes a predicted starter section with a named prediction (or committee assessment) and a pitching staff rest/availability table
- The primary view uses plain-English reasoning without percentages (bench-report friendly); internal likelihoods drive the ranking but are not displayed by default
- The prediction works without any LLM credentials configured (Tier 1 deterministic)
- When OpenRouter credentials are available, standalone reports are enriched with narrative analysis (Tier 2)
- Coaches can prep for the opposing starter within seconds of opening either scouting surface

## Non-Goals
- Prediction accuracy tracking or historical comparison (defer to future epic)
- Caching LLM responses between report generations
- Full reliever narrative in Tier 1 (Tier 2 / LLM handles detailed bullpen analysis; Tier 1 provides a minimal deterministic bullpen order)
- Support for LLM providers other than OpenRouter
- LLM enrichment on the dashboard (latency constraint -- a 30s LLM call is unacceptable for live page loads; dashboard uses Tier 1 only)

## Success Criteria
- Both standalone reports AND the dashboard opponent detail page include a "Predicted Starter" section
- High confidence: names a starter with plain-English reasoning and no qualifier
- Moderate confidence: names a starter with a caveat and an alternative candidate
- Low confidence / committee: shows available options without naming a single pick; explicitly says "committee" when 3+ similar candidates exist
- Below 4 completed games: prediction is suppressed; section shows only the pitching staff rest/availability table
- A rest/availability table for the top arms (1-2 starters by GS + highest-appearance relievers to fill 3 slots) is always present (even when prediction is suppressed)
- The pitching history query and deterministic engine are shared between both flows (not duplicated)
- When `OPENROUTER_API_KEY` is not set, standalone reports render with Tier 1 deterministic prediction only -- no errors, no empty sections
- When `OPENROUTER_API_KEY` is set and the call succeeds, standalone reports show a "Scouting Analysis" narrative block (dashboard never uses LLM)
- When the LLM call fails (timeout, error, malformed response), the report still renders with Tier 1 prediction and a warning is logged

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-212-01 | Shared pitching history query and data extraction | DONE | None | - |
| E-212-02 | Deterministic rotation analysis engine (Tier 1) | DONE | E-212-01 | - |
| E-212-03 | OpenRouter LLM client and starter analysis (Tier 2) | DONE | E-212-02 | - |
| E-212-04 | Report generator integration and template rendering | DONE | E-212-02, E-212-03 | - |
| E-212-05 | Dashboard opponent detail integration | DONE | E-212-02 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Pitching History Query (Shared)
The pitching history query and post-processing function live in `src/api/db.py` as shared functions (`get_pitching_history()` and `build_pitcher_profiles()`), following the established shared query pattern (`get_pitching_workload()` is the precedent). Both the report generator and the dashboard opponent detail route import from here.

One SQL query extracts all pitching appearances for a team/season with computed fields:
- `LAG(game_date) OVER (PARTITION BY player_id ...)` computes rest days since each pitcher's previous appearance (any role, not just starts)
- `DENSE_RANK() OVER (ORDER BY game_date ASC, start_time ASC NULLS LAST)` computes team_game_number for rotation cycle detection (no `appearance_order` in window -- all appearances within the same game share the same team_game_number)
- Includes all appearances (starts AND relief) for workload context; `appearance_order` column lets consumers filter
- Uses game ordering convention: `ORDER BY game_date ASC, start_time ASC NULLS LAST, appearance_order ASC NULLS LAST`
- `LEFT JOIN team_rosters` for jersey_number; separate `first_name`/`last_name` columns (not concatenated); includes `bf` (batters faced, nullable -- sparse in boxscore extras) for LLM context
- Returns `list[dict]` following the existing shared query pattern in `src/api/db.py`
- Python post-processing groups by player_id and computes start-to-start rest (distinct from appearance-to-appearance rest in SQL). Does NOT compute 7-day workload -- that is sourced from the existing `get_pitching_workload()` function (reuse, not reimplement)
- The `db` parameter pattern (optional pre-existing connection) matches `get_pitching_workload()` for caller flexibility
- `get_pitching_history()` does NOT take a `reference_date` parameter -- all its computed fields (LAG rest_days, DENSE_RANK team_game_number) are relative to the data itself, not to a reference date. The `reference_date` parameter lives on `get_pitching_workload()` (which callers invoke separately for rest table workload data)

### TN-2: Deterministic Engine Algorithm
The Tier 1 engine is a pure function: structured pitching history in, `StarterPrediction` dataclass out. Key algorithm steps:

1. **Minimum data gate**: The engine is never called with 0 pitching rows -- callers check the query result and pass `starter_prediction = None` downstream when empty (the "No pitching data available" message is handled at the template layer, not the engine). When called with 1-3 completed games, return `StarterPrediction` with `confidence = "suppress"` and only the rest/availability table populated. Do not attempt rotation detection. The `data_note` should distinguish between: 1-2 games ("Rest intervals not yet available -- [N] game(s) played"), 3 games ("Rotation pattern unclear -- 3 games played, rest data accumulating").

2. **Role classification**: Classify each pitcher as `primary_starter` (GS/G >= 0.6 and GS >= 2), `spot_starter` (at least 1 GS but below primary threshold), or `reliever` (0 GS). Uses season aggregates computed from the game log.

3. **Rotation detection**: From the chronological starter sequence, detect pattern type:
   - **Ace-dominant**: One pitcher has 60%+ of starts. Common at HS level.
   - **Two-man**: Two pitchers alternate, each with 30%+ of starts.
   - **Three-man**: Three pitchers rotate, competitive varsity pattern.
   - **Committee**: No clear pattern (3+ pitchers with similar start counts, no repeating sequence). Explicitly label as "committee" -- do not force a rotation.
   - Look at the most recent 2 full cycles to handle mid-season changes. Weight rotation sequence 70%, matchup factors 30%.

4. **Rest and availability assessment**: For each starter candidate:
   - Compute days since last appearance (any role, for workload) and days since last start.
   - **Within-1-day exclusion**: A pitcher whose most recent appearance was within 1 calendar day (0 or 1 days rest) is excluded from the starter candidate list. This is a near-universal behavioral constraint -- HS coaches do not start a pitcher who threw yesterday.
   - **HS rest heuristic**: 75+ pitches with fewer than 4 days rest = nearly certainly unavailable. This is a behavioral prediction heuristic (predicting what the opposing coach will do), NOT a rules engine -- actual NFHS/state pitch count rules vary by state. The engine predicts availability based on observed coaching behavior, not regulatory compliance.
   - 10+ days since last appearance of any kind: flag "availability unknown" (not positive rest). May indicate injury, suspension, or role change.
   - Compute recent 7-day workload across ALL appearances (not just starts) -- a pitcher who relieved yesterday is unlikely to start tomorrow.
   - High pitch count last outing (relative to pitcher's own average) reduces likelihood slightly. Low pitch counts (under 50) may indicate earlier availability.

5. **Confidence tiers** (per coach domain input):
   - **High**: Top candidate has 2x the signal weight of the next candidate. Output: name the starter, no qualifier.
   - **Moderate**: Rotation pick is clear but a plausible matchup alternative exists. **Deterministic trigger**: if any other rested starter -- defined as a `primary_starter` or `spot_starter` (per step 2) who is not excluded by the within-1-day rule (step 4) or the 75+/4-day rule (step 4) -- has K/9 more than 2.0 higher than the rotation-sequence leader, flag moderate confidence and name the high-K pitcher as the alternative. Output: name with caveat + alternative.
   - **Low / Committee**: 3+ similar candidates or no clear rotation. Output: show options, do NOT name a single pick. Explicitly say "committee" when applicable. A 30% top candidate = committee.
   - **Suppress**: Fewer than 4 games or no pitching data. Output: rest table only.

6. **Rest/availability table**: Always produced, regardless of confidence tier. **Selection**: top 1-2 starters by GS + fill remaining slots (up to 3 total) with highest-total-appearance relievers. A coach needs reliever rest data too -- not just starters. Shows: name, GS count, last outing date, days since last appearance, pitch count last outing, 7-day workload. `last_outing_date`, `days_since_last_appearance`, and `workload_7d` are sourced from `get_pitching_workload()` output; `last_outing_pitches` is sourced from the pitcher's most recent appearance row in the pitching history data (E-212-01), NOT from `get_pitching_workload()`. This table is the baseline output even when the prediction itself is suppressed.

7. **Edge cases**:
   - **Ace-dominant**: High confidence on that pitcher. When GS% >= 70% (GS / total team games), flag workload in the reasoning: "Started 7 of 8 games -- heavy usage, watch for early hook or rest deviation."
   - **Spot-starting reliever**: Flag as anomalous: "Note: [Name] spot-started last game (typically a reliever) -- may return to bullpen role." Treat as unknown starter role until 2+ starts accumulated.
   - **NULL appearance_order fallback**: When `appearance_order` is NULL for all rows (common for scouted teams before backfill), two adaptations: (1) `build_pitcher_profiles()` (E-212-01) populates `starts` using the most-IP-per-game heuristic instead of `appearance_order = 1` (see E-212-01 AC-4); (2) the engine uses those inferred starts for rotation detection and role classification. Only suppress when there is genuinely no pitching data (0 rows) or fewer than 4 games. This prevents unnecessarily suppressing predictions for scouted teams that have boxscore data but lack `appearance_order`.
   - 10+ day gap for a rotation member: flag availability, adjust rotation sequence.
   - **Tournament density flag** (Tier 1): If 3+ games fall on consecutive or near-consecutive days (gaps of 0-1 days) in the last 7 days of game history, add a `data_note`: "Compressed schedule detected -- rotation predictions less reliable." This is a date-gap computation on existing data; the LLM tier (TN-3) can add narrative context.
   - **Matchup deviation ceiling**: Acknowledge that ~20-30% of predictions will be overridden by matchup decisions. The algorithm is not wrong -- the coach made an informed override. Moderate-confidence reasoning should note: "Rotation analysis predicts [Name], but matchup factors could shift the call."
   - **Doubleheader**: Not predictable from historical data (no forward-looking schedule). Past doubleheader patterns are observable (same-date game pairs) and may inform the LLM tier narrative, but the deterministic engine does not attempt to predict future doubleheaders.

8. **Bullpen order** (minimal deterministic): Rank relievers by frequency of first-relief-appearance (first pitcher to enter after the starter, based on `appearance_order = 2`). Output a ranked list of up to 3 relievers with their frequency count (e.g., "Likely bullpen order: Verkamp (entered 1st in 4 of 6 games), Dewing, Schmidt."). This gives the bench report a basic "who comes in from the pen?" answer even without LLM credentials. The LLM tier provides richer bullpen narrative when available.

9. **Reasoning string format** (per coach): Plain-English, bench-ready. Example formats:
   - High: "Likely starter: Nienhueser -- last pitched 5 days ago, leads rotation with 6 starts, averages 4.8 days rest between starts."
   - Moderate alternative: "Also possible: Lade -- best K rate on staff (11.7 K/9 in 23.1 IP), possible matchup call."
   - Committee: "Rotation unclear -- 3 pitchers with similar rest and usage. See rest table."

Output: `StarterPrediction` dataclass with:
- `confidence`: one of "high", "moderate", "low", "suppress"
- `predicted_starter`: dict with player info and reasoning (None if low/suppress)
- `alternative`: dict with player info (None if high/suppress)
- `top_candidates`: list of up to 3 dicts with player info, internal likelihood (float, not displayed by default), reasoning string, recent game log
- `rotation_pattern`: string description (e.g., "ace-dominant", "2-man rotation", "committee")
- `rest_table`: list of dicts for up to 3 arms (1-2 starters by GS + highest-appearance relievers; always populated when data exists)
- `bullpen_order`: list of up to 3 dicts for relievers ranked by first-relief-appearance frequency (name, jersey_number, frequency count, games sampled)
- `data_note`: string or None (contextual messages; granularity per step 1: 1-2 games / 3 games / tournament density; engine is never called at 0 rows -- callers pass `starter_prediction = None`)

### TN-3: OpenRouter LLM Integration
- **Client module**: `src/llm/openrouter.py` -- thin HTTP client using `httpx` directly (not openai SDK). `query_openrouter(messages, model, max_tokens, temperature) -> dict`. Uses a plain `httpx.Client()` (not `create_session()` -- documented exception to HTTP discipline rule; OpenRouter is a standard API, not GameChanger).
- **Env vars**: `OPENROUTER_API_KEY` (required for Tier 2; absence means Tier 2 is skipped silently), `OPENROUTER_MODEL` (optional, default `anthropic/claude-haiku-4-5-20251001`).
- **Timeout**: 30 seconds. No retries. Failure raises `LLMError`.
- **Analysis module**: `src/reports/llm_analysis.py` -- builds the prompt from pitching history data + Tier 1 results, calls OpenRouter, parses the response into `EnrichedPrediction` dataclass.
- **Prompt design**: Structured data (not prose) -- formatted tables of pitcher stats and game logs. Include Tier 1 prediction so the LLM can confirm, adjust, or add context. Include both teams' W-L records when available (scouted team's record always; user's team record when the report is generated in an opponent context). W-L is the only opponent-strength signal available -- we have no conference/non-conference or strength-of-schedule data from GameChanger. The LLM may note matchup-strength elevation as a possibility (e.g., "strong opponent -- ace deployment possible"), but should not overstate its predictive value; coaches' deployment decisions based on opponent strength are real (~25-30% of games at competitive HS level) but unpredictable from record alone. This belongs in the LLM narrative, not Tier 1 scoring -- the Moderate confidence tier already handles the deterministic case. Request JSON-structured output with `narrative`, `bullpen_sequence`, and optional `confidence_adjustment` fields. `confidence_adjustment` is requested to improve narrative quality but intentionally discarded -- the deterministic Tier 1 confidence tier is authoritative for rendering decisions.
- **Sequential enrichment**: Tier 1 produces `StarterPrediction`; Tier 2 wraps it in `EnrichedPrediction` with narrative fields. The renderer picks one presentation path based on which dataclass it receives.
- **Token budget**: ~2-3K input tokens for 30 games / 10 pitchers. Cost ~$0.001/report at Haiku pricing.

### TN-4: Report Template Layout
- **Placement**: After exec summary, before Recent Form. Inside `.stats-content` (landscape page).
- **Section header**: "Predicted Starter" using existing `.section-header` style.

**Four rendering modes based on confidence tier:**

- **High confidence**: Primary candidate card with blue left-border accent (`border-left: 3px solid #1e3a5f`), plain-English reasoning (e.g., "Next in 2-man rotation, 4 days rest, 67 pitches last outing"), full game log (last 3-5 starts: Date, IP, #P, K, BB, Decision). No percentage displayed. GS badge next to name.
- **Moderate confidence**: Primary candidate card (blue accent) with a caveat line (e.g., "Rotation pick, but matchup alternative possible") + secondary candidate card (standard border, condensed game log). No percentage displayed.
- **Low / Committee**: No named prediction. Text label: "Pitching staff appears to use a committee approach" or "Multiple candidates with similar likelihood." Up to 3 candidate cards at equal visual weight (no blue accent, all standard border). Each has condensed game log.
- **Suppress** (fewer than 4 games): No candidate cards. Section shows only the rest/availability table with a contextual note: "Fewer than 4 games available -- insufficient data for starter prediction."

**Rest/availability table** (always present when pitching data exists): Compact table for up to 3 arms (1-2 starters by GS + highest-appearance relievers) showing Name, GS, Last Outing (date), Days Rest, Last Outing (#P), 7-day Workload. Uses existing report table styling at 8pt. This table appears below the candidate cards (or alone when prediction is suppressed). On the dashboard, "Last Outing" date is server-rendered as relative (e.g., "5d ago") matching the existing `rest_display` pattern.

**LLM narrative block** (when `enriched_prediction` is present): Appears below cards/rest table. Sub-header "Scouting Analysis" at `.key-player-label` weight. `border-left: 3px solid #d1d5db` (gray, NOT blue). `font-size: 8.5pt; line-height: 1.5`. LLM narrative is most valuable at moderate confidence (per coach). When `enriched_prediction` is None, no trace of the narrative block exists in the HTML.

- **Disclaimer**: Always present at section bottom using `.sort-annotation` style. Text varies: "Based on rotation pattern, rest days, and recent workload. Actual starter may differ." (when `enriched_prediction` is None) vs. "Based on rotation pattern, rest days, recent workload, and AI-assisted analysis. Actual starter may differ." (when `enriched_prediction` is present).
- **Print**: `break-inside: avoid` on section container and narrative block. No dark backgrounds. Card backgrounds use `#f9fafb`.
- **Mobile**: Use the existing `mob-hide-extra` CSS class for lower-priority elements on small screens (e.g., secondary candidate game logs, rest table columns beyond Name/GS/Days Rest). The primary candidate card and its reasoning line must remain visible on mobile.
- **GS badge**: Uses existing `.depth-badge` style (e.g., `4 GS`).

### TN-5: Generator Pipeline Integration
The prediction stage runs in the existing Step 5 block of `generate_report()`, after all queries are complete and before the `data = {` dict assembly. All DB calls in this stage reuse the existing `conn` from `generate_report()` via the `db=conn` parameter:
1. Call the pitching history query function (new, added in E-212-01) with `db=conn`
2. Call the deterministic engine (E-212-02) -- always runs, produces `StarterPrediction`
3. Attempt LLM enrichment (E-212-03) -- skipped if no API key, caught if fails, produces `EnrichedPrediction` or None
4. Add both results to the `data` dict for the renderer

Follows the existing non-fatal stage pattern (like plays at line 1114-1133): `CredentialExpiredError` is not applicable here, but `LLMError` and general exceptions are caught, logged as warnings, and the report continues with Tier 1 only.

### TN-6: Dashboard Opponent Detail Integration
The dashboard opponent detail page (`/dashboard/opponents/{opponent_team_id}`) and its print variant use `get_opponent_scouting_report()` from `src/api/db.py`. The predicted starter section is added to both views:
- Both route handlers (`opponent_detail` and its print variant) call `get_pitching_history()` and `build_pitcher_profiles()` (shared, from E-212-01), then `compute_starter_prediction()` (from E-212-02)
- These calls use `run_in_threadpool` like the existing DB calls in the route. The shared functions accept `db=None` by default (creating their own connection); the dashboard route handler may pass its existing connection or let the functions manage their own -- follow whichever pattern the existing dashboard DB calls use
- The prediction result is passed to the template context
- **No LLM enrichment** on the dashboard -- Tier 1 only. The 30s LLM timeout is unacceptable for a live page load. LLM enrichment is exclusive to standalone reports.
- The dashboard template section follows the same four-mode rendering as TN-4, using the dashboard's existing CSS conventions instead of the report's. All dates in the section (game log dates AND rest table "Last Outing" dates) are server-rendered as relative (e.g., "5d ago") matching the existing `rest_display` pattern -- no client-side JS date conversion
- The print variant (`/dashboard/opponents/{opponent_team_id}/print`) includes the prediction section

### TN-7: Dependency Management
Adding `httpx` to the OpenRouter client. `httpx` is already in `requirements.in` (used by the existing HTTP layer), so no new dependency is needed for the HTTP client itself. No new packages required.

## Open Questions
- None remaining. All expert consultations complete.

## History
- 2026-04-04: Created. Expert consultations: baseball-coach (domain), data-engineer (query design), ux-designer (layout), software-engineer (architecture).
- 2026-04-04: Review iteration 3 triage -- 19 findings (5 coach, 4 PM, 10 CR). 3 changes applied: TN-3/AC-6 W-L record language refined per coordinator correction (no conference data, don't overstate predictive value), TN-6 db parameter note added (CR-8). 16 findings were already addressed in prior iterations. User requirement (W-L records for matchup-strength context) confirmed already incorporated in TN-3 and E-212-03 AC-5/AC-6.
- 2026-04-04: Epic set to READY. Expert consultations (baseball-coach, data-engineer, ux-designer, software-engineer, api-scout) during planning. 3 internal review iterations + 1 Codex validation pass. Coach domain sign-off on all confidence tiers, rest table, bullpen order, and matchup-strength handling. UXD clean sign-off on all rendering modes, mobile, and print. W-L record opponent-strength context added to LLM prompt per user request.
- 2026-04-04: All 5 stories DONE. Delivered: shared pitching history query + pitcher profiles (E-212-01), deterministic rotation analysis engine with 4 confidence tiers, rest table, bullpen order, and edge case handling (E-212-02), OpenRouter LLM client + starter analysis enrichment (E-212-03), report generator integration with 4-mode template rendering and LLM narrative block (E-212-04), dashboard opponent detail integration with Tailwind styling and server-rendered relative dates (E-212-05). First LLM integration in the project. 146 tests total (23 + 45 + 38 + 37 + 3). Both scouting surfaces now show predicted starter intelligence.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 9 | 7 | 2 |
| Internal iteration 1 -- Holistic team (PM + coach + DE + SE + UXD) | 14 | 10 | 4 |
| Internal iteration 2 -- CR spec audit | 7 | 3 | 4 |
| Internal iteration 2 -- Holistic team (PM + coach + DE + SE + UXD) | 14 | 10 | 4 |
| Codex iteration 1 | 6 | 2 | 4 |
| Internal iteration 3 -- CR spec audit | 10 | 1 | 9 |
| Internal iteration 3 -- Holistic team (PM + coach + UXD) | 9 | 3 | 6 |
| Per-story CR -- E-212-01 | 2 | 2 | 0 |
| Per-story CR -- E-212-02 | 4 | 4 | 0 |
| Per-story CR -- E-212-03 | 2 | 2 | 0 |
| Per-story CR -- E-212-04 | 4 | 4 | 0 |
| Per-story CR -- E-212-05 | 0 | 0 | 0 |
| CR integration review | 0 | 0 | 0 |
| Codex code review | 4 | 2 | 2 |
| **Total** | **85** | **50** | **35** |

Codex dismissed findings:
1. Rest anchoring divergence between engine and rest table -- by design (different perspectives for different purposes)
2. "Most recent 2 full cycles" not implemented -- TN refinement detail, correct pattern detection verified by per-story CR and PM

### Documentation Assessment
Trigger 1 (new feature ships): **YES** -- predicted starter section is a new user-facing feature on both scouting surfaces. Coaching staff need to understand what the predicted starter section shows, confidence tiers, and the rest/availability table. `docs/coaching/` should be updated.
Trigger 5 (epic changes how users interact): **YES** -- coaches now see starter predictions and rest tables on opponent detail pages and standalone reports.

**Action required**: Dispatch docs-writer to update `docs/coaching/` with predicted starter feature documentation (confidence tiers, rest table, LLM narrative when available).

### Context-Layer Assessment
1. **New convention, pattern, or constraint established**: **YES** -- OpenRouter LLM client pattern (`src/llm/openrouter.py`) is the project's first LLM integration. Future LLM features should reuse this client. The `httpx.Client()` exception to HTTP discipline is documented in the module but should be noted in CLAUDE.md. The sequential enrichment pattern (Tier 1 deterministic → Tier 2 LLM optional) establishes a convention for future LLM-enhanced features.
2. **Architectural decision with ongoing implications**: **YES** -- Two-tier architecture (deterministic always, LLM optional) is a reusable pattern. Dashboard = Tier 1 only (latency constraint); reports = Tier 1 + optional Tier 2. `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` env vars. The `src/llm/` package is a new top-level package.
3. **Footgun, failure mode, or boundary discovered**: **NO** -- No unexpected gotchas. The LLM non-fatal pattern follows the established plays stage pattern.
4. **Change to agent behavior, routing, or coordination**: **NO** -- No agent infrastructure changes.
5. **Domain knowledge discovered**: **YES** -- HS rotation patterns (ace-plus-committee most common, true 3-man at competitive varsity, 4-man rare/Legion), matchup deviation rate (~20-30%), within-1-day exclusion as near-universal HS behavioral constraint, 75+/4-day availability heuristic. These inform future pitching-related features.
6. **New CLI command, workflow, or operational procedure**: **NO** -- No new `bb` commands or skills.

**Triggers 1, 2, 5 fire**: Dispatch claude-architect to codify the LLM client pattern, two-tier architecture, env vars, and pitching domain knowledge in the context layer.
