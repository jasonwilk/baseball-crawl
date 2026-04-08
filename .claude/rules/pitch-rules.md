---
paths:
  - "src/reports/starter_prediction.py"
  - "src/reports/llm_analysis.py"
  - "src/api/db.py"
  - "src/api/routes/dashboard.py"
  - "src/api/templates/dashboard/opponent_detail.html"
  - "src/api/templates/dashboard/opponent_print.html"
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

NSAA and Legion are both pitch-count-based (same data model: pitch count -> rest days). Adding Legion support to the engine is a **data change** -- different thresholds, same structure. USSSA and Perfect Game use fundamentally different units (innings, outs) that would require **structural engine extension** (a code change, not just new thresholds).

---

## NSAA (Nebraska High School)

**Applicability**: All Nebraska HS teams -- freshman, reserve, jv, varsity (`programs.program_type = 'hs'`).

**Status**: Implemented in engine (`src/reports/starter_prediction.py`).

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

## American Legion (Senior & Junior)

**Applicability**: Legion teams (`programs.program_type = 'legion'`).

**Status**: Reference data only -- not yet implemented in engine.

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

Currently NSAA only. The engine in `src/reports/starter_prediction.py` uses frozen dataclasses (`RestTier`, `PitchCountRules`) with `NSAA_PRE_APRIL` and `NSAA_POST_APRIL` constants. The `_is_nsaa_excluded()` function checks rest-tier compliance, consecutive-days violations, and null pitch counts, returning `(excluded, reason)` for each pitcher.

Adding Legion would follow the same pattern (pitch-count-based, different threshold constants). USSSA and Perfect Game would need new dataclass types for innings-based and outs-based rules.

### Tier 2: LLM Prompt Injection (Agent Reference)

The LLM Tier 2 prompt (`src/reports/llm_analysis.py`) injects the active NSAA rest table based on reference_date so the LLM can flag compliance concerns in its narrative. For non-NSAA teams, agents should inject the correct league's rest table based on team classification. This rule file is agent reference data -- it is not read at runtime by the application.

### Display

Show NSAA-required rest alongside actual rest in the bullpen/availability UI. The exclusion reason string (e.g., "0 days rest -- needs 2 (threw 55 pitches on Apr 5)") is passed through from the engine to the display layer.
