---
name: league-pitch-rules
description: Per-league pitch count rules for the probable-starter eligibility gate — NSAA Varsity/Sub-Varsity/season-phase tables, Legion table, NRBL table, hard/guideline flags. Keyed by league x competition-level x season-phase; season is ALSO a classification AXIS (spring→NSAA family, summer→Legion/NRBL family, E-272) that helps select which row applies — a selection signal, not a fourth table dimension.
metadata:
  type: reference
---

# League Pitch Count Rules

Reference data for the [[probable-starter-model]] eligibility gate.

**Scope UPDATE 2026-07-18 — Legion is now LIVE, not proactive.** As of the 2026-07-18 summer scouting runs, American Legion Senior (18U) and Junior (17U) opponents are the CURRENT live opponent reality (E-263 Deep Scout epic). Two Legion teams were scouted that day ("Norfolk Motor Company Seniors 18U" → Legion Senior; "Columbus 1 Nebraska Jr Blues" → Legion Junior). The Legion table (30/45/60/80/105) is now EXERCISED, not recorded proactively. NSAA HS spring remains the other live reality (sequential seasons: HS spring, then Legion summer — no overlap). USSSA/youth tables remain proactive/future.

**What this exposed — CORRECTED 2026-07-18 (verified against `src/reports/starter_prediction.py`).** The engine is NOT NSAA-Varsity-only. The rest-table constants all existed as of that date (`NSAA_SUBVARSITY`, `LEGION`, `PITCH_SMART_15_18`) — see the 2026-07-25 update below for the current, NRBL-inclusive set. `_is_excluded(profile, reference_date, rules)` is table-parameterized (takes the rule set as an argument), and `get_rules_for_league()` selects among them. The REAL gap (as of that date) was that league selection was **INFERRED**, not chosen: the generator resolved the league via `detect_league_level(ngb, age_group, team_name)`, which for NSAA disambiguated Varsity-vs-SubVarsity from team-name keywords only. Where NSAA and Legion diverge — **46–50p, 61–70p, 81–90p** — a mis-inferred league still mis-rests arms; that day's slate agreed on every verdict by schedule luck, not because inference was safe.

**UPDATED 2026-07-25 (E-272) — the 2026-07-18 claim that no rest-table constants needed adding (since removed from the paragraph above when this file was revised, quoted here so it is not reasserted: "No rest-table constants need adding.") is now FALSE, and the inference gap is now materially IMPROVED, not merely diagnosed.** A new constant, `NRBL`, was added (rule-identical to `LEGION` today, kept distinct on purpose — NRBL and American Legion are separately-governed bodies that currently agree, so a future Legion-only change must not silently move NRBL, nor vice versa). The full rest-table constant set is now `NSAA_PRE_APRIL`, `NSAA_POST_APRIL`, `NSAA_SUBVARSITY`, `LEGION`, `NRBL`, `PITCH_SMART_15_18` — six constants grouping into five rule sets (`.claude/rules/pitch-rules.md`'s count), since the two NSAA Varsity constants share one rule set split only by season-phase. Selection also changed: `detect_league_level()` (`src/reports/starter_prediction.py`) now takes a `season` keyword too, and its sole `src/` call site — `_ReportGeneration._query_render_save` in `src/reports/generator.py` — passes it (two out-of-scope research scripts under `.project/research/` also call it directly). The `_nsaa_level_from_name` / `_NAME_KEYWORDS` flat team-name-keyword lookup this paragraph originally cited no longer exists in that form: `_NAME_KEYWORDS` was replaced wholesale by a numeric pre-keyword age-bracket ladder (`_league_from_age_bracket`) plus a season-aware level-word resolver (`_league_from_level_word`, driven by `_LEVEL_WORD_PATTERNS`); `_nsaa_level_from_name` survives only for the narrower `ngb=nsaa` disambiguation path (Priority 2), which stays season-blind on purpose (an explicit `ngb=nsaa` means NSAA regardless of season). See the "Season × Level → League Classification Model" section below for the full model, and "Implementation Status" below for how this relates to the operator's later pick (E-263).

**Prior stale claim, now retracted:** an earlier version of this file (and PM's early E-263 framing) said `_is_excluded` "encodes ONLY the NSAA Varsity table" / "the Legion table is missing." Both are FALSE as of the 2026-07-18 code read. Do not reassert either — the tables exist; INFERENCE, not tables, was the historical gap, and E-272 has since improved inference materially (see above).

## Operator-Selected Gate — Future Override Layer (E-263), Not Today's Selection Mechanism (RECONCILED 2026-07-25, E-272)

**Reconciliation note (E-272, "Both, E-272 first" operator ruling, 2026-07-21).** The bullets below record the operator's settled decision for a FUTURE, not-yet-shipped mechanism: an explicit operator-picked level at report-submission time (E-263 story E-263-02c, READY, not dispatched as of this writing). They do NOT describe what ships today. As of E-272 (2026-07-25), selection is handled by IMPROVED INFERENCE — the season × level → league classification model above, plus the mapped age-bracket ladder and NRBL — and that inference is the current, durable mechanism, including on the unattended `bb report morning-run` cron path (no operator at the keyboard, so it always infers). When E-263-02c ships, read "NO inference" below as "no inference WHEN a level is explicitly picked" — the operator pick becomes authoritative whenever set, and E-272's inference becomes the UNSET fallback, not a mechanism being retired. See "Implementation Status" below for the SELECTION-vs-MAPPING decomposition that makes the two layers compatible.

The operator's settled product decision for the picked-level FUTURE mechanism (2026-07-18 decision, SETTLED for when E-263-02c ships):
- **Accurate, no inference, once a level is explicitly picked.** The pick itself will not parse league/level from the team name. Team names like "...Seniors 18U" or "...Jr Blues" will not be trusted as gate inputs FOR A PICKED LEVEL — but inference (which DOES read the team name, age bracket, and season, per the classification model above) remains the fallback whenever no pick is made.
- **The operator explicitly PICKS the competition level at report-submission time** — a dropdown on the report-submission form and/or a flag on `bb report generate`. "If I need to choose the level at the time I submit the report to get an accurate report, that's fine."
- **Season phase is DERIVED from the known game date, not picked.** The game date is a fact at generation time, so NSAA-Varsity pre-/post-April-1 is computed automatically — never a second dropdown. (This is the season-**PHASE** concept — do not confuse it with E-272's season-**AXIS**, a different signal; see the classification model above.) See [[probable-starter-model]] for the coach-legible selector design.
- **Unset default = the improved inference (E-272), not automatically a badged guideline.** If the level is not explicitly picked (notably the cron-driven morning-run path), the engine falls to `detect_league_level()` per the classification model above. That inference resolves to a BINDING league (NSAA, Legion, or NRBL) whenever a recognized `ngb`, a mapped age bracket, or a level-word + season signal is present. Only two narrower cases still land on a guideline/suppress path: an unmapped bracket or free-text age-range (≤14U, or "13-18") resolves to the Pitch Smart 15-18 GUIDELINE (`youth_travel`, `is_estimate=True`); and a genuinely unresolved signal (`unknown`, or a recognized-but-unsupported `ngb` like `usssa`/`perfect_game`) is suppressed with a warning rather than rendering any rest call. This supersedes the pre-E-272 framing that ANY unset level meant a badged-guideline banner across the board.

This supersedes the "Open design question" list in the "Implementation Status" section below (team-name parsing as the SOLE mechanism is rejected for the picked-level future state; team-name-driven INFERENCE, refined by E-272, remains the current and future fallback). The stricter-when-ambiguous default still applies WITHIN NSAA if Varsity-vs-SubVarsity is somehow unresolved via the `ngb=nsaa` name-disambiguation path, but the operator-pick mechanism (once it ships) makes that case rare.

---

## Corrected Structural Conclusion (Implementing Epic Anchor)

**CORRECTION 2026-06-27 — prior conclusion retracted.** An earlier version of this file concluded "two age-bracket rows, league is just a daily-max overlay." That was wrong. See retraction note below.

**Correct conclusion:** The hard gate is keyed by **(LEAGUE x COMPETITION LEVEL x SEASON-PHASE)**, not by age bracket.

NSAA uses different breakpoints (30/50/70/90/110) than Legion, NRBL, and Pitch Smart (30/45/60/80/105). NSAA also splits by competition level: Sub-Varsity (JV, Reserve, Freshman) is stricter than Varsity by exactly one rest day at every tier. A single "15-18 age bracket" curve does not exist.

Real gate rows needed:
- NSAA Varsity — pre-April 1
- NSAA Varsity — April 1 through State
- NSAA Sub-Varsity — all season
- Legion Senior (18U) = Legion Junior (17U) — all season
- NRBL — all season (rule-identical to Legion today, separately governed; E-272)
- (USSSA/youth — future, out of current scope)

**Retraction note:** The prior conclusion was based on observing that Legion Senior's published rest curve matches Pitch Smart 15-18 and inferring that NSAA would also match. The NSAA 2022 rule book (nsaahome.org) refutes this. NSAA has its own breakpoints and a level split that Pitch Smart does not have. Do not reassert the "two rows" simplification anywhere.

---

## Season × Level → League Classification Model (E-272)

**Season is a classification AXIS, not a fourth table dimension.** The tables below (NSAA Varsity, NSAA Sub-Varsity, Legion, NRBL) are unchanged by this section — season decides WHICH table a given team maps to, never how any row's rest-day math works. This refines the "(LEAGUE x COMPETITION LEVEL x SEASON-PHASE)" keying above rather than contradicting it: season-**PHASE** (the pre-/post-April-1 date split, 90→110 cap) is a pre-existing pitch-CAP concept that applies ONLY within NSAA Varsity; season-**AXIS** (spring vs. summer) is the newer, orthogonal signal that picks the league FAMILY before any table row is chosen. Do not conflate the two.

**The general rule (operator HARDEN ruling, 2026-07-21, coach-validated): season picks the family for EVERY NSAA level word, not just Reserve.** Lincoln's own roster is the concrete case — a Varsity, JV, Reserve, or Freshman player plays NSAA ball in spring and (for the ~80% who carry over) Legion or NRBL ball in summer under the same level word. The full mapping:

| Level word | Spring | Summer | Season-absent |
|---|---|---|---|
| Varsity | `nsaa_varsity` | `legion` | `nsaa_varsity` (spring default) |
| JV / Junior Varsity / Reserve / Reserves / Freshman / Frosh / Sophomore | `nsaa_subvarsity` | `nrbl` | `nsaa_subvarsity` (spring default) |
| Legion / American Legion / Post N / Seniors / Juniors (no age bracket) | `legion` | `legion` (season-independent — already Legion-explicit) | `legion` |

The tier collapse mirrors the leagues' own structure: Legion is the varsity-equivalent top summer tier, NRBL is the reserve/sub-varsity summer tier — NSAA treats JV, Reserve, and Freshman as one undifferentiated sub-varsity tier, so all three collapse uniformly to NRBL in summer too.

**A mapped age bracket is dispositive ahead of every level word and ignores season entirely.** 17U and up maps to Legion-age; 15U–16U maps to NRBL-age; 14U and below stays the youth/Pitch-Smart estimate. So "16U Reserve" resolves to NRBL via the bracket, NOT NSAA Sub-Varsity via "Reserve"; "14U Juniors" resolves to the youth estimate via the bracket, NOT Legion via "Juniors." Only when NO bracket is present does the level-word + season table above apply.

**Why this is safe.** Legion and NRBL are byte-identical rest curves today (both 30/45/60/80/105, both max 105), so a within-summer Legion-vs-NRBL mis-assignment can never produce a wrong rest-day call — only a display-label mismatch (see the Authoritative Tables NRBL entry below). The one load-bearing boundary is spring-vs-summer (NSAA vs. {Legion, NRBL}), and Lincoln's seasons are strictly sequential with no overlap (NSAA sanctions zero summer play), so routing every confirmed-summer level word off the NSAA tables is unambiguously safe.

**Documented assumption — NRBL binding rests on an in-state/Nebraska context.** An empty-`ngb`, bracket-mapped 15U/16U summer opponent resolves to NRBL as a BINDING call (`is_estimate=False`), not a guideline estimate. That binding confidence assumes the opponent is a Nebraska team: NRBL is Nebraska's dominant reserve-tier summer league, and Lincoln's opponent population (sequential in-state seasons, no cross-state travel in scope today) makes an untagged 15U/16U summer opponent very likely genuinely NRBL. This is a documented assumption, not a certainty — an out-of-state or otherwise unidentifiable 15U/16U summer opponent would be over-claimed as binding NRBL when it might not actually run NRBL rules. **Revisit trigger:** out-of-state summer opponents entering scope. (The rest-day NUMBERS are unaffected either way — NRBL, Legion, and the youth Pitch Smart estimate are byte-identical curves today, so this assumption only affects the binding-vs-estimate BADGE, never the rest-day call itself.)

---

## Authoritative Tables

**NSAA source:** 2022 NSAA Baseball Rule Book (nsaahome.org) — this file's original, historical attribution, kept for continuity. **Canonical citation (TN-10, verbatim, used identically by `.claude/rules/pitch-rules.md` so the two files do not drift):** NSAA 2022 Pitch Count Regulations — `https://nsaahome.org/wp-content/uploads/2022/02/2022-Pitch-Counts.pdf` (one source covers both Varsity and Sub-Varsity). Note: whether the "2022 NSAA Baseball Rule Book" and this PDF are the same underlying document is NOT confirmed here — treat them as two attributions for the same rules, not an assertion of document identity, until verified.
**Legion source:** ALB 2026 National Baseball Rule Book. Senior and Junior confirmed identical (2026-06-27).
**NRBL source:** nrbl.net — "NRBL adopts standard ALB pitching regulations." Its own citation, not inherited from the Legion source line above: NRBL and Legion are separately-governed bodies that currently agree, so this must be re-verified independently if either body's rules change.

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

### NRBL — Nebraska Reserve Baseball League, All Season
Daily max: **105 pitches**. Follows standard American Legion pitching regulations (nrbl.net) — **rule-identical to the Legion table above today.** Kept as its OWN table/constant on purpose: NRBL and Legion are separately-governed bodies that merely agree right now, so a future Legion-only rule change must not silently apply to NRBL, and vice versa. NRBL is a SUMMER league (Nebraska's reserve/sub-varsity-tier summer competition — see the Season × Level → League Classification Model above).

| Pitches in appearance | Required rest days |
|-----------------------|--------------------|
| 1–30                  | 0 days             |
| 31–45                 | 1 day              |
| 46–60                 | 2 days             |
| 61–80                 | 3 days             |
| 81–105                | 4 days             |

NRBL's live in-game "finish the current batter then exit at the cap" rule is NOT a rest/availability signal and is out of scope for the prediction engine (same treatment as any other in-game cap enforcement).

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
| NRBL all season (Nebraska Reserve Baseball League) | 30 / 45 / 60 / 80 / 105 | 105 | **HARD** (ALB regs via nrbl.net) | CURRENT — E-272, distinct constant (`NRBL` implemented) |
| USA Baseball Pitch Smart 15-18 | 30 / 45 / 60 / 80 / 105 | 105 | **GUIDELINE** (recommended, not binding) | Soft prior for unknown leagues |
| USSSA / travel ball           | Pitch Smart by age  | Per-age   | **GUIDELINE in practice** (tournament director enforcement inconsistent) | Future |

---

## Implementation Status — Tables Present, Selection Improved by Inference (E-272), Operator-Pick Layers Later (E-263)

**RESOLVED 2026-07-18 (was "Implementation Gap — Sub-Varsity"; corrected against `starter_prediction.py`).** The old claim here — that `_is_excluded` "encodes only the NSAA Varsity table" and "has no sub-varsity branch" — is FALSE. A sub-varsity branch exists: `NSAA_SUBVARSITY` / `get_subvarsity_rules()` are wired through `get_rules_for_league("nsaa_subvarsity")`, and `_is_excluded` is table-parameterized. The rest-table math is correct for all tables (NSAA Varsity/Sub-Varsity, Legion, NRBL, Pitch Smart).

**RECONCILED 2026-07-25 (E-272) — "league/level SELECTION is inferred, not chosen" is no longer framed as only a gap awaiting removal; E-272 shipped a materially improved inference.** The engine picks the table via `detect_league_level(*, program_type, classification, ngb, age_group, team_name, season)` (`src/reports/starter_prediction.py`). For an untracked scouting opponent (no DB `program_type`/`classification`), the resolution order is now: a recognized `ngb` still wins outright; failing that, a mapped `\d+U` age bracket (17U+→Legion-age, 15U–16U→NRBL-age) is dispositive ahead of every name keyword; failing that, an NSAA/Legion level word is disambiguated by the season axis per the classification model above — rather than defaulting blind to Varsity, as the pre-E-272 keyword-only lookup did. This is now the SELECTION mechanism, not a placeholder standing in for one — including on the unattended `bb report morning-run` cron path, which always infers (no operator at the keyboard).

**SELECTION vs. MAPPING — the E-263 relationship.** E-263-02c (READY, not yet dispatched) adds an operator-PICKED level at report-submission time — a later layer, not a replacement for the model above (see "Operator-Selected Gate" above). The two decompose cleanly: "which level applies" is SELECTION (today: E-272's inference; later: the operator's pick when set); "which league's rest table a level + season maps to" is MAPPING (E-272's classification model, durable across the SELECTION change — a level word like "Reserve" still maps to a different league by season regardless of how the level was chosen). When E-263-02c ships, the operator pick is authoritative WHENEVER SET; E-272's inference remains the UNSET fallback, so `bb report morning-run` keeps resolving leagues exactly as it does today.

**Residual conservative default (still valid, narrow scope):** if the level is genuinely unresolved WITHIN NSAA (NSAA known but Varsity-vs-SubVarsity ambiguous via the `ngb=nsaa` name-disambiguation path), apply Sub-Varsity (the stricter table) — safer to over-rest than under-rest. (Distinct from the whole-league-unset default, described in the "Operator-Selected Gate" section above.)

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
