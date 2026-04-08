# E-218: League/Level Detection for Pitch Rules

## Status
`READY`

## Overview
Add league and level detection so the starter prediction engine selects the correct pitch count rule set instead of defaulting all teams to NSAA varsity. Detection must work for both tracked teams (DB fields available) and ad-hoc reports (only GC API metadata and team name available). This epic also implements Legion pitch count rules as the first non-NSAA rule set, validating the detection-to-dispatch pipeline end-to-end.

## Background & Context
E-217 replaces ad-hoc pitch count heuristics with NSAA rules but defaults ALL teams to NSAA varsity. This is wrong for:
- **Legion teams**: Different rest tiers (0-30/0d, 31-45/1d, 46-60/2d, 61-80/3d, 81+/4d) and 105-pitch max
- **USSSA teams**: Innings-based rules (structurally different -- out of scope)
- **Perfect Game teams**: Outs + pitch count hybrid (structurally different -- out of scope)

Reports serve any `public_id` -- including non-HS teams -- so detection is needed in both the reports path and the dashboard/opponent path.

**Promoted from**: IDEA-066 (League/Level Detection for Pitch Rules)

**Expert consultations (2026-04-07):**
- **baseball-coach**: Team name keywords are reliable primary signals. `ngb` + `age_group` from GC API are even stronger. Opponent name inference is a secondary tiebreaker only (mixed-league schedules happen). Unknown league = show warning, never silently default. Sub-varsity keywords (JV, Freshman, Reserve) are reliable for NSAA level detection.
- **software-engineer**: `ngb` field available on public team endpoint (confirmed values: `"usssa"`, `"american_legion"`). Detection function belongs in `starter_prediction.py` (single consumer, simple first). Reports path: insert detection after scouting crawl/load, before `compute_starter_prediction()`. Dashboard path: query `program_type`/`classification` from DB. E-217 interface: E-218 introduces `get_rules_for_league()` dispatch + `detect_league_level()`.

## Goals
- Detect the correct league and level for any team from available signals (DB fields, GC API metadata, team name)
- Select the correct pitch count rule set based on detected league/level
- Implement Legion pitch count rules (first non-NSAA rule set, same pitch-count-based data model)
- Show a clear warning when league cannot be detected or rules are not yet implemented for the detected league
- Detection works for both tracked teams (dashboard path) and ad-hoc reports (reports path)

## Non-Goals
- USSSA innings-based rule engine (requires structural extension -- different unit type)
- Perfect Game outs+pitches rule engine (requires structural extension)
- Legion same-day limit enforcement (>45 pitches in game 1 -> cannot pitch game 2; additional constraint type beyond rest tiers)
- GC API probing to discover unknown `ngb` values (can be done ad-hoc via api-scout)
- Storing detected league/level persistently in the DB (detection runs at query time)
- Opponent name inference (secondary tiebreaker -- adds complexity for marginal value; can be added later if needed)

## Success Criteria
- A USSSA 14U team generates a report with "Pitch count rules not available for USSSA" warning instead of showing NSAA rules
- A Legion team generates a report with Legion rest tiers applied (not NSAA)
- A tracked NSAA JV team shows 90-pitch max (not 110) after April 1
- A team with no detectable league shows "League not detected" warning with raw pitch counts still visible
- Detection uses structured GC API fields (`ngb`, `age_group`) as primary signals, with team name parsing as fallback
- Both reports and dashboard paths use the same detection function

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-218-01 | League/level detection function and wiring | TODO | E-217-01 | - |
| E-218-02 | Legion pitch count rule set | TODO | E-218-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Detection Signal Priority

The detection function uses a cascading priority of signals. Higher-priority signals short-circuit lower ones.

| Priority | Signal | Source | Available For | Notes |
|----------|--------|--------|--------------|-------|
| 1 | `program_type` + `classification` | DB (`programs`, `teams`) | Tracked teams only | Direct mapping, no heuristics needed. `classification=NULL` defaults to varsity (bounded risk -- coach knows their level). |
| 2 | `ngb` + `age_group` combination | GC public API (`/public/teams/{public_id}`) | All teams | `ngb`: JSON-encoded string, double-parse required. Confirmed values: `"usssa"`, `"american_legion"`. NSAA value unknown (may be `"nsaa"`, `"nfhs"`, or empty). `age_group`: qualifier, not standalone signal (e.g., `"14U"`, `"High School"`, `"Between 13 - 18"`). If multiple `ngb` values present, use first match in priority order: state HS association > `american_legion` > `usssa` > `perfect_game` > ignore. See NGB+Age Group Interaction below. |
| 3 | Team name keywords | GC public API / DB | All teams | Fallback when `ngb` is empty and `age_group` is absent/ambiguous. See keyword table below. |
| 4 | Unknown | - | - | No signal matched. Emit warning. |

**NGB + Age Group Interaction**: `ngb` determines the governing body; `age_group` disambiguates level within it:
- `ngb=["usssa"]` → `usssa` (regardless of `age_group`)
- `ngb=["american_legion"]` → `legion`
- `ngb=["perfect_game"]` → `perfect_game`
- `ngb=["nsaa"]` or `ngb=["nfhs"]` → NSAA; use `age_group` or name keywords to determine varsity vs sub-varsity
- `ngb` contains unrecognized non-empty value (not listed above) → `unknown` (safe default for values we haven't seen yet)
- `ngb=[]` + `age_group` contains "U" suffix (e.g., `"14U"`) → `youth_travel`
- `ngb=[]` + `age_group` suggests HS (e.g., `"High School"`) → fall through to name keywords for varsity/sub-varsity level
- `ngb=[]` + `age_group` absent or ambiguous → fall through to name keywords

**`competition_level` excluded**: This field is only available on authenticated endpoints (`/me/teams`, `/teams/{team_id}`), NOT on the public endpoint used by reports. DB path already has better signals (`program_type`). Evaluated and excluded from the cascade.

### Team Name Keyword Table

| Keyword(s) | Detected League | Detected Level | Confidence |
|------------|----------------|----------------|------------|
| "Varsity" | NSAA | varsity | High |
| "JV", "Junior Varsity" | NSAA | jv | High |
| "Freshman", "Frosh" | NSAA | freshman | High |
| "Reserve" | NSAA | reserve | High |
| "Sophomore" | NSAA | jv | Medium (rare) |
| "Legion", "American Legion" | Legion | - | High |
| "Post" + number pattern | Legion | - | High |
| "Seniors" (standalone) | Legion | seniors | High |
| "Juniors" (standalone, no "U") | Legion | juniors | Medium |
| r"\d+U" (e.g., "14U", "12U") | Youth travel | age from match | High |

### Detection Output

The function returns a league/level identifier string used to dispatch to the correct rule set:

| Identifier | Meaning | Rule Set Available (after E-218) |
|------------|---------|----------------------------------|
| `nsaa_varsity` | NSAA HS varsity | Yes (E-217) |
| `nsaa_subvarsity` | NSAA HS JV/Freshman/Reserve | Yes (E-218-01 creates this rule set: 90-pitch max year-round, same rest tiers as varsity -- E-217 only provides varsity rules) |
| `legion` | American Legion (Seniors or Juniors -- rules identical for both divisions) | Yes (E-218-02) |
| `usssa` | USSSA youth travel (when `ngb` confirms org) | No -- warning |
| `perfect_game` | Perfect Game (when `ngb` confirms org) | No -- warning |
| `youth_travel` | Youth travel, org unknown (age-group match only, e.g., "14U" without `ngb`) | No -- warning |
| `unknown` | No signal matched | No -- warning |

### Warning Behavior

When rules are unavailable (unsupported league or unknown -- applies to `usssa`, `perfect_game`, `youth_travel`, `legion` (until E-218-02), and `unknown`):
- The `StarterPrediction` uses `confidence="suppress"` with the warning in `data_note` (see Warning Output Contract for full field-by-field specification)
- The `rest_table` is populated with raw workload data (last outing, 7-day counts) but no availability/exclusion assessment -- coaches still see pitch counts even without rules
- Starter prediction, alternatives, top candidates, and bullpen order are suppressed (per Warning Output Contract: `predicted_starter=None`, `alternative=None`, `top_candidates=[]`, `bullpen_order=[]`)
- The warning message identifies the detected league when known (e.g., "USSSA pitch rules not yet supported", "Youth travel league detected -- specific pitch rules not available") or notes detection failure ("League not detected -- pitch count rules cannot be applied")
- No template changes needed -- the suppress path already renders `data_note` in all three templates, and `rest_table` renders independently of `confidence`

### Warning Output Contract

When an unsupported league is detected (or detection fails), the `StarterPrediction` output must communicate the warning through the existing data structure without requiring template changes. The contract:

- **`confidence`**: Set to `"suppress"`. This is the correct semantic -- we are suppressing the prediction because we cannot apply rules. The suppress path already renders `data_note` in all three templates (opponent_detail, opponent_print, scouting_report).
- **`data_note`**: Carries the league-specific warning text (e.g., "USSSA pitch rules not yet supported") or detection-failure text ("League not detected -- pitch count rules cannot be applied").
- **`rest_table`**: Populated with raw pitch count data (last outing, 7-day counts) but WITHOUT availability/exclusion assessment. Pitchers appear in the rest table with workload data visible but no "available"/"excluded" status applied. This preserves the coaching value of seeing workload even when rules are unknown.
- **`predicted_starter`**: `None`.
- **`alternative`**: `None`.
- **`top_candidates`**: `[]` (empty list).
- **`bullpen_order`**: `[]` (empty list).

This means the suppress path shows: (1) warning text via `data_note`, (2) rest/workload table with raw data but no availability judgment. The frequency rankings (who starts most often) are part of the prediction which IS suppressed -- but the rest table's workload data is still valuable. Templates already render `rest_table` independently of `confidence`, so no template changes are needed.

### Reports Path Wiring

In `src/reports/generator.py`, the public team API response (fetched via `GET /public/teams/{public_id}` during report generation) includes `ngb`, `age_group`, and `name` fields. These fields must be extracted from the response dict and passed to `detect_league_level()` before calling `compute_starter_prediction()`. The detected league/level flows as a parameter to the prediction function.

### Dashboard Path Wiring

For tracked teams, `program_type`, `classification`, and `team_name` are queried from the DB and passed to `detect_league_level()`. The function's priority cascade means DB fields take precedence over API metadata, so tracked teams with `program_type` set get deterministic detection without heuristics. Tracked opponents that lack `program_type`/`classification` (common -- these fields are only reliably populated for member teams) fall through to the name-keyword cascade using `team_name`.

### Legion Rest Requirements (Reference)

Max 105 pitches/day. Rest tiers:

| Pitches Thrown | Required Calendar Days Rest |
|---------------|----------------------------|
| 0-30          | 0 (may pitch next day)     |
| 31-45         | 1                          |
| 46-60         | 2                          |
| 61-80         | 3                          |
| 81+           | 4                          |

Consecutive-days rule: same as NSAA (max 2 appearances in 3-day period).

**Out of scope for E-218**: Same-day limit (>45 pitches in game 1 -> cannot pitch game 2 same day). This is an additional constraint type beyond rest tiers that would require extending the availability check function.

## Open Questions
- What `ngb` value do NSAA HS teams have in the GC public API? Could be `"nsaa"`, `"nfhs"`, or empty. The detection function should handle all three possibilities (if empty, fall through to `age_group` and name parsing). This can be verified via api-scout probe of a known NSAA team's public profile.

## History
- 2026-04-07: Created. Promoted from IDEA-066. Expert consultations with baseball-coach and software-engineer completed.
- 2026-04-08: Set to READY after 2 internal review iterations + 3 Codex spec review passes (34 findings total, 30 accepted, 4 dismissed). Key refinements: detection cascade restructured (ngb+age_group merged into unified interaction table), youth_travel identifier added, perfect_game ngb mapping, subvarsity rule set ownership moved to E-218-01 (E-217 only provides varsity), Warning Output Contract pinned (confidence=suppress, field shapes specified), consecutive-days window corrected (from E-217 review), dashboard path includes team_name fallback for tracked opponents lacking program_type, dependency narrowed to E-217-01. Two ideas promoted during E-217/E-218 planning: IDEA-066 (this epic), IDEA-067 (catcher-pitcher restriction). Dismissed findings: api-scout consultation (3x -- graceful cascade handles unknown ngb values), AC restatement cosmetic (1x).

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 7 | 7 | 0 |
| Internal iteration 1 -- Holistic team (PM + coach + SE) | 7 | 7 | 0 |
| Internal iteration 2 -- CR spec audit | 3 | 3 | 0 |
| Internal iteration 2 -- Holistic team (PM) | 2 | 2 | 0 |
| Codex iteration 1 | 5 | 4 | 1 |
| Codex iteration 2 | 5 | 4 | 1 |
| Codex iteration 3 | 5 | 3 | 2 |
| **Total** | **34** | **30** | **4** |
