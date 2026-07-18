---
paths:
  - "src/reports/starter_prediction.py"
  - "src/reports/llm_analysis.py"
  - "src/api/db.py"
  - "src/api/templates/reports/**"
---

# Pitching Availability Rules by League

This file is the authoritative reference for pitching rest and availability rules across all leagues the platform serves. Agents implementing pitching features and the LLM Tier 2 prompt should reference this file for rule values.

## League-to-Classification Mapping

| League | `programs.program_type` | `teams.classification` values | Rule Unit |
|--------|------------------------|-------------------------------|-----------|
| NSAA (Nebraska HS) | `hs` | freshman, reserve, jv, varsity | Pitch count |
| American Legion | `legion` | legion | Pitch count |
| USSSA (Youth travel) | `usssa` | 7U-18U | Innings |
| Perfect Game | *(not yet represented in schema)* | 7U-14U | Outs + pitches |

## Structural Note

NSAA (Varsity and Sub-Varsity) and Legion are all pitch-count-based (same data model: pitch count -> rest days) and are **implemented** in the engine as frozen `PitchCountRules` rule sets. USSSA and Perfect Game use fundamentally different units (innings, outs) that would require **structural engine extension** (a code change, not just new thresholds) and are **not yet implemented**.

---

## NSAA (Nebraska High School)

**Applicability**: Nebraska HS varsity teams (`programs.program_type = 'hs'`, `classification = 'varsity'` or unset). NSAA **Sub-Varsity** (freshman, reserve, jv) is a distinct, stricter rule set -- see the Sub-Varsity subsection below.

**Status**: Implemented in engine (`NSAA_PRE_APRIL` / `NSAA_POST_APRIL` in `src/reports/starter_prediction.py`, selected via `get_rules_for_league('nsaa_varsity')`).

### Rest Requirement Tables

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

### Additional Constraints

**Consecutive-days rule**: No player may make more than 2 pitching appearances in any consecutive 3-day period, regardless of pitch count. This counts **individual appearances**, not distinct calendar days -- a pitcher who appears in both games of a doubleheader has 2 appearances on that day. For prediction, the relevant 3-day window is {reference_date-2, reference_date-1, reference_date}. Since reference_date hasn't happened yet, count prior appearances on reference_date-2 and reference_date-1. If there are already 2+ appearances in that window, pitching on reference_date would create a 3rd = violation = excluded.

**Calendar-day counting**: Rest is counted in calendar days, not hours. Pitching Monday evening = 1 rest day = available Wednesday.

**Doubleheader pitch aggregation**: For the **rest-tier check**, pitch counts from all appearances on the same calendar day are combined (e.g., 25 pitches in game 1 + 30 in game 2 = 55 total -> 51-70 tier -> 2-day rest required). For the **consecutive-days check**, each game appearance counts individually (doubleheader = 2 appearances on 1 day).

**Null pitch count**: When any appearance on the pitcher's most recent game date has a null pitch count, the system treats the pitcher as unavailable with reason "pitch count unavailable -- cannot verify eligibility." This covers both single-game null and the doubleheader edge case (one game has data, the other doesn't -- the day's aggregate is unreliable).

---

## NSAA Sub-Varsity (Freshman, Reserve, JV)

**Applicability**: Nebraska HS sub-varsity teams (`programs.program_type = 'hs'`, `classification` in `freshman` / `reserve` / `jv`). Stricter than Varsity.

**Status**: Implemented in engine (`NSAA_SUBVARSITY` / `get_subvarsity_rules()` in `src/reports/starter_prediction.py`, selected via `get_rules_for_league('nsaa_subvarsity')`). It is a distinct 90-pitch, year-round rule set (no post-April 1 bump to 110). The authoritative per-tier rest curve is maintained in the baseball-coach model doc (`.claude/agent-memory/baseball-coach/league-pitch-rules.md`, sourced from the 2022 NSAA Baseball Rule Book) -- reference it for the exact breakpoints, and reconcile any engine change against it.

The universal NSAA constraints above (consecutive-days rule, calendar-day counting, doubleheader pitch aggregation, null pitch count) apply identically to Sub-Varsity.

---

## American Legion (Senior & Junior)

**Applicability**: Legion teams (`programs.program_type = 'legion'`). Senior (18U) and Junior (17U) share this identical curve.

**Status**: Implemented in engine (`LEGION` rule set in `src/reports/starter_prediction.py`, selected via `get_rules_for_league('legion')`).

### Rest Requirement Table

Max 105 pitches/day:

| Pitches Thrown | Required Calendar Days Rest |
|---------------|----------------------------|
| 0-30          | 0 (may pitch next day)     |
| 31-45         | 1                          |
| 46-60         | 2                          |
| 61-80         | 3                          |
| 81+           | 4                          |

### Additional Constraints

- **Consecutive days**: Max 2 appearances in any 3-day period (same structure as NSAA).
- **Same-day limit**: If a pitcher throws >45 pitches in game 1, they cannot pitch in game 2 on the same day.
- **Day definition**: 8am to 8am (not midnight to midnight).

---

## USSSA (Youth Travel, 7U-18U)

**Applicability**: USSSA travel ball teams (`programs.program_type = 'usssa'`).

**Status**: Reference data only -- not yet implemented in engine. Would require structural extension (innings-based, not pitch-count-based).

### Rules (Innings-Based)

- **Max to pitch next day**: 3 innings
- **1-day max**: 6 innings (7U-12U), 7 innings (13U-14U)
- **3-day max**: Varies by age group
- **Mandatory rest**: Required if >3 innings in a day

---

## Perfect Game (7U-14U)

**Applicability**: Perfect Game tournament teams. Not yet represented in schema (no `program_type` value exists for PG tournaments).

**Status**: Reference data only -- not yet implemented in engine. Would require structural extension (outs + pitch count dual-unit system).

### Rules (Outs + Pitches)

- **Daily max pitches**: 50 (7U-8U) to 95 (13U-14U)
- **Mandatory rest**: 2 days if >9 outs in a day
- **Consecutive days**: No 3 consecutive days pitching
- **Tournament limits**: 100 pitches over 2-4 days, 140 over 5+ days

---

## How the Engine Should Use These Rules

### Tier 1: Deterministic Lookup (Python Code)

The engine in `src/reports/starter_prediction.py` uses frozen dataclasses (`RestTier`, `PitchCountRules`) and ships **four** pitch-count rule sets: NSAA Varsity (`NSAA_PRE_APRIL` / `NSAA_POST_APRIL`), NSAA Sub-Varsity (`NSAA_SUBVARSITY`), Legion (`LEGION`), and the youth/travel Pitch Smart 15-18 estimate (`PITCH_SMART_15_18`). The table-parameterized `_is_excluded(profile, reference_date, rules)` function checks rest-tier compliance, consecutive-days violations, and null pitch counts against **any** rule set, returning `(excluded, reason)` for each pitcher. `get_rules_for_league(league, reference_date)` selects the rule set and `detect_league_level(...)` resolves the league. (`_is_nsaa_excluded()` survives only as a thin NSAA convenience wrapper delegating to `_is_excluded`.)

NSAA Sub-Varsity and Legion are already implemented via this pattern (pitch-count-based, distinct threshold constants). USSSA and Perfect Game remain **unimplemented** -- they would need new dataclass types for innings-based and outs-based rules; `get_rules_for_league()` returns `None` for `usssa` / `perfect_game` / `unknown` and the card is suppressed with softened copy.

**Forward direction (E-263)**: league/level selection is moving from INFERENCE (`detect_league_level`, which for NSAA disambiguates Varsity-vs-Sub-Varsity partly from team-name keywords) to an OPERATOR-PICKED level at report-submission time (E-263-02c). The rule tables above are unchanged by that work -- only how the engine chooses among them changes.

**Youth/travel fallback (E-243-02)**: A team whose competition level resolves to `youth_travel` (e.g. a `\d+U` age-bracket name with no recognized NGB) has no binding league rule unit, so `get_rules_for_league()` routes it to the USA Baseball Pitch Smart 15-18 curve (the `PITCH_SMART_15_18` constant: max 105, tiers 30/45/60/80/105 -- a *distinct* constant from Legion on purpose, even though the tiers match today, so a future Legion-only change cannot silently move the estimate) instead of suppressing the card. The prediction is flagged `is_estimate=True` and the report banners it as a directional, non-binding read. This is consistent with the baseball-coach model doc's "soft prior for unknown leagues" guidance (`.claude/agent-memory/baseball-coach/league-pitch-rules.md`). Truly unsupported levels (`usssa`, `perfect_game`, `unknown`) still return `None` and suppress with softened copy -- so the `usssa` program_type and the age-pattern `youth_travel` classification are NOT the same path.

### Tier 2: LLM Prompt Injection (Agent Reference)

The LLM Tier 2 prompt (`src/reports/llm_analysis.py`) injects the active league's rest table (selected by league + reference_date, as resolved in Tier 1) so the LLM can flag compliance concerns in its narrative. This rule file is agent reference data -- it is not read at runtime by the application.

### Display

Show the league-required rest alongside actual rest in the bullpen/availability UI. The exclusion reason string (e.g., "0 days rest -- needs 2 (threw 55 pitches on Apr 5)") is passed through from the engine to the display layer.
