---
name: league-pitch-rules
description: Per-league pitch count rules for the probable-starter eligibility gate — NSAA Varsity/Sub-Varsity/season-phase tables, Legion table, hard/guideline flags, implementation gap. Keyed by league x competition-level x season-phase, NOT by age bracket.
metadata:
  type: reference
---

# League Pitch Count Rules

Reference data for the [[probable-starter-model]] eligibility gate.
Current scope (2026): NSAA HS spring opponents only. Legion and USSSA tables are recorded proactively but NOT exercised yet — live DB has 0 LSB rows and ~4-5 opponent seasons of NSAA boxscore_only data as of 2026-06-27.

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
| NSAA Sub-Varsity all season   | 30 / 50 / 70 / 90   | 90        | **HARD** (+1 day vs Varsity at every tier) | CURRENT — see implementation gap |
| Legion Senior 18U = Junior 17U | 30 / 45 / 60 / 80 / 105 | 105 | **HARD** (ALB national) | Future — not yet exercised |
| USA Baseball Pitch Smart 15-18 | 30 / 45 / 60 / 80 / 105 | 105 | **GUIDELINE** (recommended, not binding) | Soft prior for unknown leagues |
| USSSA / travel ball           | Pitch Smart by age  | Per-age   | **GUIDELINE in practice** (tournament director enforcement inconsistent) | Future |

---

## Implementation Gap — Sub-Varsity (Correctness Issue in Current Code)

`starter_prediction.py::_is_excluded` currently encodes **only the NSAA Varsity table**. It has no sub-varsity branch.

**Effect:** Sub-varsity opponent pitchers (JV, Reserve, Freshman) are under-rested by exactly one day at every tier. A pitcher who threw 31–50 pitches requires 2 days rest under the Sub-Varsity rule but only 1 day under the Varsity rule currently in the code — the model will incorrectly mark them AVAILABLE when they are not.

**This is not hypothetical.** The live DB already contains sub-varsity opponents (e.g., Elkhorn North "Reserve").

**Open design question for the epic:** How does the code determine an opponent's competition level to select the right gate? Options:
- Team-name signal parsing ("JV", "Reserve", "Freshman" substrings in team name)
- Explicit `competition_level` field on the team record
- Default to Sub-Varsity (more conservative) when level is unknown

**Recommended default when level is ambiguous:** Apply Sub-Varsity (the stricter table). It is always safer to treat an arm as requiring more rest than to under-rest and mispredict.

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
