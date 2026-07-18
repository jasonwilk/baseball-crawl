---
name: league-pitch-rules
description: Per-league pitch count rules for the probable-starter eligibility gate — NSAA Varsity/Sub-Varsity/season-phase tables, Legion table, hard/guideline flags, implementation gap. Keyed by league x competition-level x season-phase, NOT by age bracket.
metadata:
  type: reference
---

# League Pitch Count Rules

Reference data for the [[probable-starter-model]] eligibility gate.

**Scope UPDATE 2026-07-18 — Legion is now LIVE, not proactive.** As of the 2026-07-18 summer scouting runs, American Legion Senior (18U) and Junior (17U) opponents are the CURRENT live opponent reality (E-263 Deep Scout epic). Two Legion teams were scouted that day ("Norfolk Motor Company Seniors 18U" → Legion Senior; "Columbus 1 Nebraska Jr Blues" → Legion Junior). The Legion table (30/45/60/80/105) is now EXERCISED, not recorded proactively. NSAA HS spring remains the other live reality (sequential seasons: HS spring, then Legion summer — no overlap). USSSA/youth tables remain proactive/future.

**What this exposed — CORRECTED 2026-07-18 (verified against `src/reports/starter_prediction.py`).** The engine is NOT NSAA-Varsity-only. The rest-table constants ALL exist (`NSAA_SUBVARSITY`, `LEGION`, `PITCH_SMART_15_18`), `_is_excluded(profile, reference_date, rules)` is table-parameterized (takes the rule set as an argument), and `get_rules_for_league()` selects among them. **No rest-table constants need adding.** The REAL gap is that league selection is currently **INFERRED**, not chosen: the generator resolves the league via `detect_league_level(ngb, age_group, team_name)` (generator.py ~2335), which for NSAA disambiguates Varsity-vs-SubVarsity from **team-name keywords** (`_nsaa_level_from_name` / `_NAME_KEYWORDS`). That inference is exactly what the operator wants to replace with an explicit operator-picked level (the E-263 gate). Where NSAA and Legion diverge — **46–50p, 61–70p, 81–90p** — a mis-inferred league still mis-rests arms; today's slate agreed on every verdict by schedule luck, not because inference is safe.

**Prior stale claim, now retracted:** an earlier version of this file (and PM's early E-263 framing) said `_is_excluded` "encodes ONLY the NSAA Varsity table" / "the Legion table is missing." Both are FALSE as of the 2026-07-18 code read. Do not reassert either — the tables exist; INFERENCE is the gap.

## Operator-Selected Gate — No Inference From Team Name (2026-07-18 decision, SETTLED)

The operator's settled product decision for how the engine picks the right gate table:
- **Accurate, NO inference.** Do NOT parse league/level from the team name (retires the earlier "team-name signal parsing" option below). Team names like "...Seniors 18U" or "...Jr Blues" are NOT trusted as gate inputs.
- **The operator explicitly PICKS the competition level at report-submission time** — a dropdown on the report-submission form and/or a flag on `bb report generate`. "If I need to choose the level at the time I submit the report to get an accurate report, that's fine."
- **Season phase is DERIVED from the known game date, not picked.** The game date is a fact at generation time, so NSAA-Varsity pre-/post-April-1 is computed automatically — never a second dropdown. See [[probable-starter-model]] for the coach-legible selector design.
- **Unset default = badged guideline, never a silent HARD pick.** If the level is not picked (notably the cron-driven morning-run path, which has no human at the keyboard), fall back to the Pitch Smart 15-18 GUIDELINE table with a visible "level not set — general guideline, may be inexact" badge. This preserves "no inference": we are not guessing a specific league, we are openly declaring the level unknown.

This supersedes the "Open design question" list in the Sub-Varsity implementation-gap section below (team-name parsing is explicitly rejected). The stricter-when-ambiguous default still applies WITHIN NSAA if Varsity-vs-SubVarsity is somehow unresolved, but the operator-pick mechanism makes that case rare.

---

## Corrected Structural Conclusion (Implementing Epic Anchor)

**CORRECTION 2026-06-27 — prior conclusion retracted.** An earlier version of this file concluded "two age-bracket rows, league is just a daily-max overlay." That was wrong. See retraction note below.

**Correct conclusion:** The hard gate is keyed by **(LEAGUE x COMPETITION LEVEL x SEASON-PHASE)**, not by age bracket.

NSAA uses different breakpoints (30/50/70/90/110) than Legion and Pitch Smart (30/45/60/80/105). NSAA also splits by competition level: Sub-Varsity (JV, Reserve, Freshman) is stricter than Varsity by exactly one rest day at every tier. A single "15-18 age bracket" curve does not exist.

Real gate rows needed:
- NSAA Varsity — pre-April 1
- NSAA Varsity — April 1 through State
- NSAA Sub-Varsity — all season
- Legion Senior (18U) = Legion Junior (17U) — all season
- (USSSA/youth — future, out of current scope)

**Retraction note:** The prior conclusion was based on observing that Legion Senior's published rest curve matches Pitch Smart 15-18 and inferring that NSAA would also match. The NSAA 2022 rule book (nsaahome.org) refutes this. NSAA has its own breakpoints and a level split that Pitch Smart does not have. Do not reassert the "two rows" simplification anywhere.

---

## Authoritative Tables

**NSAA source:** 2022 NSAA Baseball Rule Book (nsaahome.org)
**Legion source:** ALB 2026 National Baseball Rule Book. Senior and Junior confirmed identical (2026-06-27).

### NSAA Varsity — Pre-April 1
Daily max: **90 pitches**

| Pitches in appearance | Required rest days |
|-----------------------|--------------------|
| 1–30                  | 0 days             |
| 31–50                 | 1 day              |
| 51–70                 | 2 days             |
| 71–90                 | 3 days             |

### NSAA Varsity — April 1 through State
Daily max: **110 pitches** (adds the 91–110 tier)

| Pitches in appearance | Required rest days |
|-----------------------|--------------------|
| 1–30                  | 0 days             |
| 31–50                 | 1 day              |
| 51–70                 | 2 days             |
| 71–90                 | 3 days             |
| 91–110                | 4 days             |

### NSAA Sub-Varsity — All Season
Applies to: JV, Reserve, Freshman. Daily max: **90 pitches**.
**Stricter than Varsity by exactly one rest day at every tier.**

| Pitches in appearance | Required rest days |
|-----------------------|--------------------|
| 1–30                  | 1 day              |
| 31–50                 | 2 days             |
| 51–70                 | 3 days             |
| 71–90                 | 4 days             |

### American Legion — Senior (18U) and Junior (17U), identical
Daily max: **105 pitches**. Senior and Junior confirmed identical (same rest curve, same daily max).
**This IS the USA Baseball Pitch Smart 15-18 curve.** Different breakpoints from NSAA — do not conflate.

| Pitches in appearance | Required rest days |
|-----------------------|--------------------|
| 1–30                  | 0 days             |
| 31–45                 | 1 day              |
| 46–60                 | 2 days             |
| 61–80                 | 3 days             |
| 81–105                | 4 days             |

---

## Universal NSAA Rules (Apply Across All Three NSAA Tables)

- **Consecutive-appearance limit**: No pitcher may appear in more than 2 games in any consecutive 3-day period
- **Doubleheader pitch summation**: Pitches from both games count together for the day; rest is computed from the day's total
- **Midnight rule**: Eligibility is keyed off the game's START calendar day
- **Ambidextrous pitchers**: Pitch counts from both arms are combined

---

## Summary Metadata

| Gate context                   | Breakpoints         | Daily max | Hard or guideline  | Scope        |
|-------------------------------|---------------------|-----------|--------------------|--------------|
| NSAA Varsity pre-April 1      | 30 / 50 / 70 / 90   | 90        | **HARD** (NSAA enforcement — forfeit/suspension) | CURRENT |
| NSAA Varsity April 1→State    | 30 / 50 / 70 / 90 / 110 | 110  | **HARD**           | CURRENT      |
| NSAA Sub-Varsity all season   | 30 / 50 / 70 / 90   | 90        | **HARD** (+1 day vs Varsity at every tier) | CURRENT — branch implemented (`NSAA_SUBVARSITY`) |
| Legion Senior 18U = Junior 17U | 30 / 45 / 60 / 80 / 105 | 105 | **HARD** (ALB national) | CURRENT — live opponent reality 2026-07-18 (`LEGION` implemented) |
| USA Baseball Pitch Smart 15-18 | 30 / 45 / 60 / 80 / 105 | 105 | **GUIDELINE** (recommended, not binding) | Soft prior for unknown leagues |
| USSSA / travel ball           | Pitch Smart by age  | Per-age   | **GUIDELINE in practice** (tournament director enforcement inconsistent) | Future |

---

## Implementation Status — Tables Present, Selection Is the Gap

**RESOLVED 2026-07-18 (was "Implementation Gap — Sub-Varsity"; corrected against `starter_prediction.py`).** The old claim here — that `_is_excluded` "encodes only the NSAA Varsity table" and "has no sub-varsity branch" — is FALSE. A sub-varsity branch exists: `NSAA_SUBVARSITY` / `get_subvarsity_rules()` are wired through `get_rules_for_league("nsaa_subvarsity")`, and `_is_excluded` is table-parameterized. The rest-table math is correct for all tables (NSAA Varsity/Sub-Varsity, Legion, Pitch Smart).

**The real, still-open gap = league/level SELECTION is inferred, not chosen.** The engine picks the table from `detect_league_level(program_type, classification, ngb, age_group, team_name)`. For an untracked scouting opponent (no DB `program_type`/`classification`), it falls to NGB + team-name keyword inference — so the RIGHT table can be selected from the WRONG signal (a name that omits "JV"/"Reserve" defaults to Varsity; a Legion team typed manually can miss its NGB). That mis-selection, not a missing table, is what under-rests arms at the divergent tiers.

**The operator's fix (see the "Operator-Selected Gate" section above):** replace the team-name inference with an explicit operator-picked level at report-submission time. The three earlier "open design question" options (team-name parsing / explicit field / conservative default) are superseded — team-name parsing is explicitly rejected, and the operator pick IS the explicit-field mechanism.

**Residual conservative default (still valid, narrow scope):** if the level is genuinely unresolved WITHIN NSAA (NSAA known but Varsity-vs-SubVarsity ambiguous), apply Sub-Varsity (the stricter table) — safer to over-rest than under-rest. The operator pick makes this case rare. (Distinct from the whole-league-unset default, which is the badged Pitch Smart guideline per the Operator-Selected Gate section.)

---

## Hard Gate vs. Soft Prior — The Conceptual Split

**Hard gate (HARD rows in metadata above):**
- `days_rest < required_rest_days` per the applicable gate row → mark pitcher UNAVAILABLE. Binary. Never override.
- Daily max also enforced as an in-game cap (relevant for data validation, not prediction).
- A coach who starts a pitcher in violation faces NSAA forfeit/suspension or ALB national sanctions.

**Soft prior (GUIDELINE rows, and preferred-rest discount):**
- Published guidelines shape the initial likelihood ranking but do not gate eligibility.
- An arm that clears the hard gate but sits inside the preferred-rest window gets downweighted, not disqualified.
- **Backtesting-derived actual team behavior beats any published table for the soft prior by mid-season.** Learn their actual rest cadence from game history.
- Transition rule: use published guideline as prior for games 1–6; weight observed behavior equally by game 7; observed behavior dominates from game 10 onward.
