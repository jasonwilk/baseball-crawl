---
paths:
  - "src/reports/starter_prediction.py"
  - "src/reports/generator.py"
  - "src/reports/llm_analysis.py"
  - "src/api/db.py"
  - "src/api/templates/reports/**"
---

# Pitching Availability Rules by League

This file is the authoritative reference for pitching rest and availability rules across all leagues the platform serves. Agents implementing pitching features and the LLM Tier 2 prompt should reference this file for rule values.

## League-to-Classification Mapping

| League | Season (E-272) | `programs.program_type` | `teams.classification` values | Rule Unit |
|--------|----------------|------------------------|-------------------------------|-----------|
| NSAA Varsity (Nebraska HS) | spring (the same level word maps to Legion in summer) | `hs` | varsity | Pitch count |
| NSAA Sub-Varsity | spring (the same level words map to NRBL in summer) | `hs` | freshman, reserve, jv | Pitch count |
| American Legion | any (season-independent) | `legion` | legion | Pitch count |
| NRBL (Nebraska Reserve Baseball League) | summer (or any, via a 15U-16U bracket) | *(inference-resolved -- no DB field)* | *(inference-resolved -- no DB field)* | Pitch count |
| USSSA (Youth travel) | any | `usssa` | 7U-18U | Innings |
| Perfect Game | any | *(not yet represented in schema)* | 7U-14U | Outs + pitches |

The Season column describes the INFERENCE path only (the ngb-empty region of `detect_league_level`, reached when a team has no DB `program_type`/`classification` and no recognized `ngb`) -- the DB-field columns are season-blind, and NRBL and the summer flips have no DB representation at all. See "Season as a Classification Axis" below.

## Season as a Classification Axis (E-272)

Season selects the league FAMILY (spring -> NSAA; summer -> Legion/NRBL); the level word or age bracket picks the tier within it. It changes only which table a team maps to, never any table's rest-day math. The signal is the public-API `team_season.season` field, read in `src/reports/generator.py` and passed to `detect_league_level(..., season=...)` in `src/reports/starter_prediction.py`. Precedence, strongest first (authoritative spec: E-272 Technical Notes TN-2):

1. **DB `program_type` / `classification`** -- season-blind.
2. **A recognized `ngb`** (`american_legion`, `usssa`, `perfect_game`, `nsaa`/`nfhs`) -- authoritative over both the age bracket and the season, so a genuine `ngb=usssa` 15U team stays `usssa` rather than becoming NRBL.
3. **Any single `\d+U` age bracket, mapped or not** -- bracket PRESENCE is what outranks a name keyword, so a bracket is dispositive over EVERY level word and ignores season: 17U and above -> `legion`; 15U-16U -> `nrbl`; 14U and below -> `youth_travel`. The UNMAPPED half outranks level words too -- "Lincoln 14U Reserve" resolves `youth_travel`, NOT `nsaa_subvarsity` (E-272's only change in the less-strict direction; that outcome is labeled an estimate, `is_estimate=True`). The free-text age-RANGE form ("13-18") carries no `U` suffix, so it is not a bracket at all -- an `age_group` range resolves to `youth_travel` by its own path.
4. **An NSAA/Legion level word, disambiguated by season** -- Varsity -> spring `nsaa_varsity` / summer `legion`; JV, Junior Varsity, Reserve(s), Freshman, Frosh, Sophomore -> spring `nsaa_subvarsity` / summer `nrbl`; Legion-explicit words (Legion, American Legion, Post N, Seniors, Juniors) -> `legion` season-independently.
5. **No matching signal** -> `unknown`, card suppressed.

An absent or unrecognized season falls back to the spring/NSAA family (Varsity -> `nsaa_varsity`; the sub-varsity words -> `nsaa_subvarsity`). For the sub-varsity words that default is also the conservative one: `NSAA_SUBVARSITY` (90 max, 1/2/3/4) demands at least as much rest as `NRBL` at every pitch count up to its cap, so an ambiguous season over-rests rather than under-rests. The Varsity default is *spring-is-likelier*, NOT strictly-stricter -- NSAA Varsity and Legion cross over in the middle tiers (a 50-pitch outing needs 1 rest day under NSAA Varsity but 2 under Legion), so do not read "default to NSAA" as a blanket safety margin. The full season x level matrix and its coaching rationale live in the baseball-coach model doc (`.claude/agent-memory/baseball-coach/league-pitch-rules.md`, "Season × Level → League Classification Model"), which keys the gate by (league x competition level x season-phase) and records that NRBL's binding claim rests on an in-state/Nebraska opponent assumption.

**AXIS is not PHASE.** The season AXIS above picks a league family. The pre/post-April-1 date split is a season PHASE -- a pitch-CAP concept scoped to NSAA **Varsity only** (90 -> 110); NSAA Sub-Varsity is flat 90 year-round, and every summer league is flat 105 year-round with Legion Junior = Legion Senior = NRBL.

## Structural Note

NSAA (Varsity and Sub-Varsity), Legion, and NRBL are all pitch-count-based (same data model: pitch count -> rest days) and are **implemented** in the engine as frozen `PitchCountRules` rule sets. USSSA and Perfect Game use fundamentally different units (innings, outs) that would require **structural engine extension** (a code change, not just new thresholds) and are **not yet implemented**.

---

## NSAA (Nebraska High School)

**Applicability**: Nebraska HS varsity teams (`programs.program_type = 'hs'`, `classification = 'varsity'` or unset). NSAA **Sub-Varsity** (freshman, reserve, jv) is a distinct, stricter rule set -- see the Sub-Varsity subsection below.

**Status**: Implemented in engine (`NSAA_PRE_APRIL` / `NSAA_POST_APRIL` in `src/reports/starter_prediction.py`, selected via `get_rules_for_league('nsaa_varsity')`).

*Source:* NSAA 2022 Pitch Count Regulations -- https://nsaahome.org/wp-content/uploads/2022/02/2022-Pitch-Counts.pdf (one source covers both Varsity and Sub-Varsity).

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

**Status**: Implemented in engine (`NSAA_SUBVARSITY` / `get_subvarsity_rules()` in `src/reports/starter_prediction.py`, selected via `get_rules_for_league('nsaa_subvarsity')`). It is a distinct 90-pitch, year-round rule set (no post-April 1 bump to 110). The authoritative per-tier rest curve is maintained in the baseball-coach model doc (`.claude/agent-memory/baseball-coach/league-pitch-rules.md`, heading "NSAA Sub-Varsity — All Season") -- reference it for the exact breakpoints, and reconcile any engine change against it.

*Source:* NSAA 2022 Pitch Count Regulations -- https://nsaahome.org/wp-content/uploads/2022/02/2022-Pitch-Counts.pdf (the same source as Varsity above).

The universal NSAA constraints above (consecutive-days rule, calendar-day counting, doubleheader pitch aggregation, null pitch count) apply identically to Sub-Varsity.

---

## American Legion (Senior & Junior)

**Applicability**: Legion teams (`programs.program_type = 'legion'`). Senior (18U) and Junior (17U) share this identical curve.

**Status**: Implemented in engine (`LEGION` rule set in `src/reports/starter_prediction.py`, selected via `get_rules_for_league('legion')`).

*Source:* American Legion Baseball official Senior/Junior pitch-count regulations (ALB National Baseball Rule Book -- no stable public PDF, so the governing body is cited rather than a link).

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

## NRBL (Nebraska Reserve Baseball League) (E-272)

**Applicability**: Nebraska's reserve/sub-varsity-tier SUMMER league. No `programs.program_type` value represents NRBL -- it is **inference-resolved** only, via a 15U-16U mapped age bracket or a summer sub-varsity level word (see "Season as a Classification Axis" above).

**Status**: Implemented in engine (`NRBL` rule set in `src/reports/starter_prediction.py`, selected via `get_rules_for_league('nrbl')`). It is a distinct 105-pitch, year-round rule set with no date split, and it renders as BINDING (`is_estimate=False`) -- never the youth-estimate banner and never the suppress path. The authoritative per-tier rest curve is maintained in the baseball-coach model doc (`.claude/agent-memory/baseball-coach/league-pitch-rules.md`, heading "NRBL — Nebraska Reserve Baseball League, All Season") -- reference it for the exact breakpoints, and reconcile any engine change against it.

`NRBL` is a *distinct* constant from `LEGION` on purpose -- mirroring the `PITCH_SMART_15_18` note below -- even though the two curves are identical today: NRBL and American Legion are separately governed bodies that merely agree right now, so a future Legion-only change must not silently move NRBL, nor an NRBL-only change move Legion.

*Source:* nrbl.net -- NRBL adopts standard American Legion pitching regulations. This is NRBL's own cite, not inherited from ALB above; re-verify it independently if either body changes its rules.

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

The engine in `src/reports/starter_prediction.py` uses frozen dataclasses (`RestTier`, `PitchCountRules`) and ships **five** pitch-count rule sets: NSAA Varsity (`NSAA_PRE_APRIL` / `NSAA_POST_APRIL`), NSAA Sub-Varsity (`NSAA_SUBVARSITY`), Legion (`LEGION`), NRBL (`NRBL`, E-272), and the youth/travel Pitch Smart 15-18 estimate (`PITCH_SMART_15_18`). The table-parameterized `_is_excluded(profile, reference_date, rules)` function checks rest-tier compliance, consecutive-days violations, and null pitch counts against **any** rule set, returning `(excluded, reason)` for each pitcher. `get_rules_for_league(league, reference_date)` selects the rule set and `detect_league_level(...)` resolves the league. (`_is_nsaa_excluded()` survives only as a thin NSAA convenience wrapper delegating to `_is_excluded`.)

NSAA Sub-Varsity, Legion, and NRBL are already implemented via this pattern (pitch-count-based, distinct threshold constants). USSSA and Perfect Game remain **unimplemented** -- they would need new dataclass types for innings-based and outs-based rules; `get_rules_for_league()` returns `None` for `usssa` / `perfect_game` / `unknown` and the card is suppressed with softened copy.

**Forward direction (E-263) -- SELECTION vs MAPPING (reconciled with E-272)**: the two epics change different things and are complementary, not competing. E-263-02c changes level **SELECTION** -- how the level is chosen, moving from an inferred guess to an OPERATOR-PICKED level at report-submission time. E-272 changes level+season -> league **MAPPING** -- which league's table a given level resolves to -- and that axis is durable across the E-263 transition, because "Reserve" still means NSAA Sub-Varsity in spring and NRBL in summer no matter how the level was chosen. The documented seam: the operator pick is authoritative WHEN SET, and the unset case DELEGATES to `detect_league_level` rather than forcing the Pitch Smart estimate. Inference is therefore not superseded -- the unattended `bb report morning-run` path has no operator at the keyboard and always infers, so E-272's improved inference is the sole league resolver there. The rule tables above are unchanged by either epic.

**Youth/travel fallback (E-243-02; narrowed by E-272)**: A team whose competition level resolves to `youth_travel` (an UNMAPPED age bracket -- 14U and below -- or the free-text age-range form, with no recognized NGB; mapped 15U+ brackets now resolve to `nrbl`/`legion` instead) has no binding league rule unit, so `get_rules_for_league()` routes it to the USA Baseball Pitch Smart 15-18 curve (the `PITCH_SMART_15_18` constant: max 105, tiers 30/45/60/80/105 -- a *distinct* constant from Legion on purpose, even though the tiers match today, so a future Legion-only change cannot silently move the estimate) instead of suppressing the card. The prediction is flagged `is_estimate=True` and the report banners it as a directional, non-binding read. This is consistent with the baseball-coach model doc's "soft prior for unknown leagues" guidance (`.claude/agent-memory/baseball-coach/league-pitch-rules.md`). Truly unsupported levels (`usssa`, `perfect_game`, `unknown`) still return `None` and suppress with softened copy -- so the `usssa` program_type and the age-pattern `youth_travel` classification are NOT the same path.

### Tier 2: LLM Prompt Injection (Agent Reference)

The LLM Tier 2 prompt (`src/reports/llm_analysis.py`) injects the active league's rest table (selected by league + reference_date, as resolved in Tier 1) so the LLM can flag compliance concerns in its narrative. This rule file is agent reference data -- it is not read at runtime by the application.

### Display

Show the league-required rest alongside actual rest in the bullpen/availability UI. The exclusion reason string (e.g., "0 days rest -- needs 2 (threw 55 pitches on Apr 5)") is passed through from the engine to the display layer.
