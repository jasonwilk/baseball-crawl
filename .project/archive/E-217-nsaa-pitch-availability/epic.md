# E-217: NSAA Pitch Count Availability Rules

## Status
`COMPLETED`

## Overview
Replace the ad-hoc pitch count exclusion heuristics in the starter prediction engine with NSAA (Nebraska) pitch count rules, filter the bullpen order by availability, and codify the rules in the context layer for LLM and future-feature consumption. The current engine has both over-restriction errors (blocking legal arms) and under-restriction errors (clearing ineligible ones), producing misleading scouting reports for coaches.

## Background & Context
The starter prediction engine (`src/reports/starter_prediction.py`) uses two ad-hoc exclusion functions:
- `_is_excluded_within_1_day()`: Excludes any pitcher whose last appearance was within 1 calendar day. But NSAA says 1-30 pitches = 0 days rest (can pitch next day) -- so this **over-restricts** low-pitch-count relievers.
- `_is_excluded_high_pitch_short_rest()`: Excludes if 75+ pitches AND < 4 days rest. But NSAA thresholds are tiered (31-50 = 1 day, 51-70 = 2 days, 71-90 = 3 days pre-April; different post-April). A pitcher who threw 76 needs 3 days (not 4) under NSAA pre-April rules. This **over-restricts** in some cases and **under-restricts** in others (missing the 31-50 / 1-day tier entirely).

Additionally, the bullpen order (`_build_bullpen_order()`) is a pure frequency ranking with NO availability filtering. A pitcher who threw 76 pitches yesterday appears as a bullpen option, which is misleading.

The engine also has NO consecutive-days rule. NSAA says no player may make more than 2 appearances as pitcher in any consecutive 3-day period -- this fires regularly during tournament weekends and late-season schedule compression.

**Expert consultations (2026-04-07):**
- **baseball-coach**: Coaches use a two-pass mental model -- compliance first (binary: eligible or not), then effectiveness. Consecutive-days rule is MUST HAVE. Bullpen should show all pitchers with unavailable ones marked (not hidden). Season phase label is SHOULD HAVE.
- **software-engineer**: Frozen dataclasses for rule data at module level. Pass excluded set to bullpen function. Consecutive-days rule is low-moderate complexity (appearance data already available). ~10 tests rewritten, ~5-10 new, ~50 unchanged.
- **claude-architect**: New dedicated rule file `.claude/rules/pitch-rules.md` (not extending key-metrics). Scoped to reports + API paths. Two reference tables (pre/post April 1) + constraints section.

## Goals
- Starter prediction and bullpen order reflect NSAA-compliant availability (correct rest tiers, consecutive-days rule, season phase awareness)
- Bullpen order shows all bullpen-ranked pitchers with unavailable ones clearly marked with reason
- All known league pitch count/innings rules codified in the context layer as structured reference data for agents and the LLM Tier 2 prompt (NSAA, American Legion, USSSA, Perfect Game)
- key-metrics.md updated to reference the rule file instead of informal heuristics

## Non-Goals
- Multi-league engine implementation (only NSAA rules are implemented in code; Legion, USSSA, and Perfect Game are documented in the context layer for future implementation)
- Dashboard pitching workload section changes (the workload 4-field model is unchanged; this epic modifies the bullpen display only)
- Season phase label display in reports (SHOULD HAVE per coach, but out of scope for this engine-focused epic -- capture as idea if needed)
- "Days until eligible" badge on bullpen entries (SHOULD HAVE per coach, separate from core availability)
- Effectiveness assessment (Pass 2 in coach's model -- this epic covers Pass 1: compliance only)
- Catcher-pitcher restriction (real NSAA rule but out of scope for pitch count availability -- captured as idea)
- Fall/summer season support for April 1 boundary (NSAA HS is spring season only; the April 1 boundary is scoped to spring HS)

## Success Criteria
- A pitcher who threw 1-30 pitches yesterday is NOT excluded (NSAA allows 0-day rest)
- A pitcher who threw 76 pitches 2 days ago IS excluded pre-April 1 (NSAA requires 3 days for 71-90)
- A pitcher who appeared twice in the last 3 calendar days IS excluded (consecutive-days rule)
- The bullpen order includes unavailable pitchers marked with the specific unavailability reason
- The Tier 2 LLM prompt has access to the active NSAA rest table
- All existing tests pass (with appropriate updates) plus new NSAA-specific test coverage

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-217-01 | NSAA availability engine + bullpen filtering | DONE | None | software-engineer |
| E-217-02 | Context-layer pitch rules codification | DONE | None | claude-architect |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### NSAA Rest Requirements

**Pre-April 1 (Early Season)** -- Max 90 pitches/game:

| Pitches Thrown | Required Calendar Days Rest |
|---------------|----------------------------|
| 1-30          | 0 (may pitch next day)     |
| 31-50         | 1                          |
| 51-70         | 2                          |
| 71-90         | 3                          |

**April 1 and After** -- Max 110 pitches/game:

| Pitches Thrown | Required Calendar Days Rest |
|---------------|----------------------------|
| 1-30          | 0 (may pitch next day)     |
| 31-50         | 1                          |
| 51-70         | 2                          |
| 71-90         | 3                          |
| 91-110        | 4                          |

**Consecutive-days rule**: No player may make more than 2 pitching appearances in any consecutive 3-day period, regardless of pitch count. This counts individual appearances, not distinct calendar days -- a pitcher who appears in both games of a doubleheader has 2 appearances on that day. For prediction purposes, the relevant 3-day window is {reference_date-2, reference_date-1, reference_date}. Since reference_date hasn't happened yet, count prior appearances on reference_date-2 and reference_date-1. If there are already 2+ appearances in that window, pitching on reference_date would create a 3rd in the same 3-day period = violation = excluded.

**Calendar days**: Rest is counted in calendar days, not hours. Pitching Monday evening = 1 rest day = available Wednesday.

**Doubleheader pitch aggregation**: For the rest-tier check, pitch counts from all appearances on the same calendar day are combined (e.g., 25 pitches in game 1 + 30 in game 2 = 55 total → 51-70 tier → 2-day rest required). For the consecutive-days check, each game appearance counts individually (doubleheader = 2 appearances on 1 day).

**Null pitch count**: When any appearance on the pitcher's most recent game date has a null pitch count, the system treats the pitcher as unavailable with reason "pitch count unavailable -- cannot verify eligibility." This covers both single-game null and the doubleheader edge case (one game has data, the other doesn't -- the day's aggregate is unreliable). Conservative behavior prevents clearing an ineligible pitcher.

### Multi-League Landscape

The platform serves teams across multiple leagues, each with different pitching rules:

| League | Unit | Rule Type | Team Classifications |
|--------|------|-----------|---------------------|
| NSAA (Nebraska HS) | Pitch count | Rest tiers + consecutive-days | freshman, reserve, jv, varsity |
| American Legion | Pitch count | Rest tiers + consecutive-days + same-day limit | legion |
| USSSA (Youth travel) | Innings | Max innings/day + rest if >3 IP | 7U-18U |
| Perfect Game | Outs + pitches | Daily max + tournament caps | 7U-14U |

**Structural implication**: NSAA and Legion use the same data model (pitch count → rest days). USSSA and Perfect Game use fundamentally different units (innings, outs) that would need structural extension to the engine. Adding Legion support is a data change; adding USSSA/PG support is a code change.

**E-217 scope**: Only NSAA is implemented in code. E-217 defaults to NSAA varsity rules for all teams. League/level detection is deferred to a future epic (IDEA-066 in the ideas backlog). All league rule sets are documented in the context-layer rule file (E-217-02) as reference data for agents and the LLM Tier 2 prompt. The LLM Tier 2 prompt can use the team name to infer level and reference the appropriate rule set from the context-layer documentation.

### Non-NSAA League Rules (Reference Data for E-217-02)

**American Legion (Senior & Junior)**:
- Max 105 pitches/day
- Rest: 0-30/0d, 31-45/1d, 46-60/2d, 61-80/3d, 81+/4d
- Consecutive days: max 2 appearances in 3-day period
- Same-day limit: if >45 pitches in game 1, cannot pitch in game 2 same day
- Day defined as 8am to 8am

**USSSA (Youth travel, 7U-18U)** -- innings-based, not pitch counts:
- Max to pitch next day: 3 innings
- 1-day max: 6 innings (7U-12U), 7 innings (13U-14U)
- 3-day max varies by age group
- Mandatory rest if >3 innings in a day

**Perfect Game (7U-14U)** -- both outs and pitch counts:
- Daily max pitches: 50 (7U-8U) to 95 (13U-14U)
- 2 days mandatory rest if >9 outs in a day
- No 3 consecutive days pitching
- Tournament limits: 100 pitches over 2-4 days, 140 over 5+ days

### Rule Data Structure

NSAA rules should be expressed as frozen dataclasses at module level in `starter_prediction.py`:
- `RestTier(min_pitches, max_pitches, rest_days)` -- a single pitch-count-to-rest mapping
- `PitchCountRules(max_pitches, rest_tiers)` -- a complete rule set for one season phase
- `NSAA_PRE_APRIL` and `NSAA_POST_APRIL` constants
- `get_nsaa_rules(reference_date) -> PitchCountRules` selector function
- April 1 boundary parameterized by year for cross-season use

The same dataclass pattern works for Legion (pitch-count-based, different thresholds). USSSA/PG would need different dataclass types (innings-based, outs-based) -- that's future structural work, not E-217 scope.

### Availability Function Design

Replace the two ad-hoc exclusion functions with a single `_is_nsaa_excluded(profile, reference_date) -> tuple[bool, str | None]` that returns `(excluded, reason)`. The reason string (e.g., "0 days rest -- needs 2 (threw 55 pitches on Apr 5)") is passed through to bullpen display. The function checks:
1. Null pitch count: if ANY appearance on the most recent game date has null pitches, return excluded with "pitch count unavailable" reason. This covers the doubleheader edge case where one game has data and the other doesn't -- the day's aggregate is unreliable.
2. Doubleheader aggregation: sum pitches across all appearances on the most recent game date before doing the rest-tier lookup
3. Rest-tier compliance: aggregated pitch count → required rest (from active rule set) → compare to actual calendar days rest
4. Consecutive-days: count individual appearances on reference_date-2 and reference_date-1. If ≥ 2, pitching on reference_date would create a 3rd in the {ref-2, ref-1, ref} window = excluded.

The main engine loop builds `excluded: dict[str, str]` (player_id → reason) instead of the current `set[str]`, so reasons can be passed to the bullpen function. The loop must check ALL pitchers (starters and relievers), not just starters -- the current code (lines 584-586) skips relievers with `total_starts == 0`, but NSAA compliance applies to all pitchers regardless of role.

### Bullpen Order Enhancement

Pass the excluded dict (player_id → reason) into `_build_bullpen_order()`. The suppress path (fewer than 4 games) suppresses the starter *prediction* but must still compute NSAA exclusions -- compliance is binary and valid even with 1-3 games of data. A pitcher who threw 80 pitches yesterday is ineligible regardless of how many team games have been played. Available bullpen-ranked pitchers sort first (by frequency), unavailable ones sort after (also by frequency). Each bullpen entry gains an `available: bool` and `unavailability_reason: str | None` field. "Bullpen-ranked" means pitchers tracked by the existing first-relief-appearance frequency logic (appearance_order=2); starters are already covered in the rest table.

Template rendering must visually distinguish unavailable pitchers. Affected templates: `src/api/templates/reports/scouting_report.html`, `src/api/templates/dashboard/opponent_detail.html`, `src/api/templates/dashboard/opponent_print.html`.

### LLM Prompt Update

Inject the active NSAA rest table (based on reference_date) into the Tier 2 system prompt in `src/reports/llm_analysis.py`, so the LLM can flag compliance concerns in its narrative. Format as a compact reference table, not prose.

## Open Questions
- None (all resolved via expert consultation)

## History
- 2026-04-07: Created. Expert consultations with baseball-coach, software-engineer, claude-architect completed.
- 2026-04-07: READY. 3 internal review iterations + 3 Codex spec review passes (48 findings, 36 accepted, 12 dismissed). Key fixes: NSAA rest tiers replacing ad-hoc heuristics, doubleheader pitch aggregation, consecutive-days window correction ({ref-2, ref-1, ref} not {ref-1, ref-2, ref-3}), null pitch count handling, all-pitcher exclusion (not just starters), bullpen availability filtering with reasons, multi-league landscape documented (NSAA/Legion/USSSA/PG), suppress-path runs compliance checks. Two ideas captured: IDEA-066 (league detection), IDEA-067 (catcher-pitcher restriction).

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 7 | 5 | 2 |
| Internal iteration 1 -- Holistic team (PM + coach + SE + CA) | 16 | 16 | 0 |
| Internal iteration 2 -- CR spec audit | 5 | 5 | 0 |
| Internal iteration 2 -- Holistic team (PM + SE + CA) | 3 | 3 | 0 |
| Internal iteration 3 -- CR spec audit | 2 | 0 | 2 |
| Internal iteration 3 -- Holistic team (PM) | 0 | 0 | 0 |
| Codex iteration 1 | 4 | 3 | 1 |
| Codex iteration 2 | 5 | 4 | 1 |
| Codex iteration 3 | 6 | 0 | 6 |
| **Total** | **48** | **36** | **12** |

- 2026-04-08: COMPLETED. Both stories DONE. E-217-01: NSAA availability engine replaced ad-hoc exclusion functions with frozen dataclass rule structures, tiered rest compliance (pre/post April 1), consecutive-days rule, doubleheader pitch aggregation, null pitch count handling, all-pitcher exclusion, bullpen available/unavailable sorting with reasons, LLM rest table injection. 87 new/updated tests, 153 targeted passed. E-217-02: Context-layer pitch rules codification in `.claude/rules/pitch-rules.md` covering NSAA, Legion, USSSA, Perfect Game with engine usage guidance and league-to-classification mapping. key-metrics.md updated to reference rule file.

### Dispatch Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-217-01 | 3 | 2 | 1 |
| Per-story CR -- E-217-02 | 0 | 0 | 0 |
| CR integration review | 0 | 0 | 0 |
| Codex code review | 5 | 0 | 5 |
| **Total** | **8** | **2** | **6** |

### Documentation Assessment
Trigger 1 (new feature): YES -- pitcher availability now uses NSAA-compliant rules instead of ad-hoc heuristics; bullpen order now shows availability status with reasons. However, this changes internal engine behavior and report rendering. No user-facing workflows changed (no new CLI commands, no new pages, no deployment changes). The existing coaching docs do not document the starter prediction engine internals. No `docs/admin/` or `docs/coaching/` files cover this area. **No documentation impact** -- the changes are internal engine behavior and template rendering, not user-facing workflows or operational procedures.

### Context-Layer Assessment
1. **New convention, pattern, or constraint?** NO -- The frozen dataclass pattern for rule data is a standard Python pattern, not a project convention. E-217-02 already codified the rules in `.claude/rules/pitch-rules.md` (part of the epic scope, not a post-hoc finding).
2. **Architectural decision with ongoing implications?** NO -- The rule engine replacement is self-contained within `starter_prediction.py`. The pattern for adding Legion (data change) vs USSSA/PG (code change) is already documented in `pitch-rules.md` (delivered by E-217-02).
3. **Footgun, failure mode, or boundary discovered?** NO -- No unexpected failures or gotchas emerged during implementation.
4. **Change to agent behavior, routing, or coordination?** NO -- No agent definitions, routing, or dispatch patterns changed.
5. **Domain knowledge discovered?** NO -- All NSAA domain knowledge was captured during planning consultations and codified in E-217-02's deliverable (`pitch-rules.md`). No new domain knowledge emerged during implementation.
6. **New CLI command, workflow, or operational procedure?** NO -- No new `bb` subcommands, scripts, or workflows added.

All six triggers: NO. No context-layer codification required beyond what E-217-02 already delivered.

### Ideas Backlog Review
- **IDEA-066** (League/Level Detection): Already PROMOTED to E-218 during E-217 planning. No change.
- **IDEA-067** (Catcher-Pitcher Restriction): E-217 completion clears one of two blockers (E-217 completion). Still blocked on catching innings data availability. Status unchanged (CANDIDATE).

### Vision Signals
31 unprocessed signals in `docs/vision-signals.md` (last curation: 2026-03-13). Advisory: consider scheduling a "curate the vision" session. This does not block archival.
