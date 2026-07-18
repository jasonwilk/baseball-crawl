# E-263-02c: SIG-001 eligibility level gate (operator-selected competition level)

## Epic
[E-263: Deep Scout v1 — Opponent-Intelligence Report Sections](epic.md)

## Status
`TODO`

## Description
After this story is complete, the competition level that drives SIG-001's pitch-count eligibility gate is chosen by the OPERATOR at report-submission time — a dropdown on the admin report-submission form and a flag on `bb report generate` — never inferred from the opponent's team name. The selected level picks the correct rest-rule table (NSAA Varsity / NSAA Sub-Varsity / American Legion); an unset level falls back to the loudly-badged Pitch Smart 15-18 guideline so the unattended morning-run path never breaks. This closes the correctness gap the 2026-07-18 live Legion runs exposed (Legion arms mis-rested on the NSAA table at the 46–50 / 61–70 / 81–90 pitch margins).

## Context
Per Technical Notes TN-11 (the authoritative gate spec) and TN-4, SIG-001 conditions the whole game plan on the expected arm, so a wrong rest table poisons every downstream section for a Legion opponent. **This is NOT a missing-table problem** — the engine (`src/reports/starter_prediction.py`) already carries every table (`NSAA_PRE_APRIL`/`NSAA_POST_APRIL`, `NSAA_SUBVARSITY`, `LEGION`, `PITCH_SMART_15_18`), selects among them by a `league` id via `get_rules_for_league(league, reference_date)`, and `_is_excluded(profile, reference_date, rules)` is table-parameterized. The generator already passes a `league` resolved by `detect_league_level(ngb, age_group, team_name)` at its starter block. The gap is purely the operator-selected INPUT and its override of that detection: for a cold scouting opponent the DB level fields are unpopulated, so detection would otherwise fall back to team-name keyword parsing, which the operator has ruled out as an accuracy source.

Selector shape and copy are baseball-coach's authoritative design (recorded in `.claude/agent-memory/baseball-coach/league-pitch-rules.md` and `probable-starter-model`). This story is the input + plumbing; E-263-04 renders the coach-facing accuracy sentence in the Who's Pitching section from the availability-basis fact this story produces.

## Acceptance Criteria
- [ ] **AC-1**: `bb report generate` accepts an operator-selected competition-level input, and the admin report-submission form (`src/api/routes/reports_admin.py` + `src/api/templates/admin/reports.html`) presents a matching dropdown, offering exactly the three picks plus an unset default per Technical Notes TN-11: "High School — Varsity", "High School — JV, Reserve, or Freshman", "American Legion (Senior or Junior)", and an unset/"level not set" default. Parity: both surfaces expose the same choices.
- [ ] **AC-2**: The selected level is plumbed through `generate_report()` (`src/reports/generator.py`) and OVERRIDES `detect_league_level()` at the starter-prediction call site, so the operator's pick is authoritative: "High School — Varsity" → the NSAA Varsity rules, "High School — JV, Reserve, or Freshman" → the NSAA Sub-Varsity rules, "American Legion (Senior or Junior)" → the Legion rules (all via the existing `get_rules_for_league`). The competition level is NEVER inferred from the opponent's team name — a Legion-named opponent explicitly submitted as "High School — Varsity" uses the NSAA Varsity table, and an NSAA-named opponent submitted as "American Legion" uses the Legion table. A test covers each of the three picks selecting the correct table AND the operator pick overriding a conflicting team-name signal.
- [ ] **AC-3**: The season phase (NSAA Varsity pre/post April-1) is DERIVED automatically from the game/reference date, not a second dropdown (the engine's `get_rules_for_league(..., reference_date)` already does this) — a test confirms a pre-April-1 and an on/after-April-1 date select the 90- vs 110-pitch NSAA Varsity table for the same "High School — Varsity" pick.
- [ ] **AC-4**: When the level is UNSET (including the unattended `bb report morning-run` / cron path, which has no operator at the keyboard), the gate falls back to the Pitch Smart 15-18 GUIDELINE table via the engine's existing `is_estimate` path — never a silent hard pick and never a suppressed card. The report surfaces this loudly (reusing the existing `is_estimate` guideline banner mechanism). A test covers the unset path yielding the guideline table with the estimate/badged state set.
- [ ] **AC-5**: The story produces an availability-basis fact in the fact sheet (per the Technical Notes TN-1 contract from E-263-02a, `ethics_tier = coach_facing`) carrying the level label and set/unset state plus the coach-facing accuracy copy from Technical Notes TN-11 — SET → "Availability is calculated from the official [level] pitch-count rules — these calls are exact."; UNSET → "Level not set — availability uses a general youth-arm guideline (USA Baseball Pitch Smart) and may be off by a day at the margins." (E-263-04 renders it in the Who's Pitching section; this story does not render a partial.)
- [ ] **AC-6**: No new crawling and no schema change — the change is an input parameter + gate table-selection only (the epic's read-only v1 posture, TN-11). A test or the existing suite confirms the report still generates for an opponent `public_id` with and without the level set, and no migration is added.
- [ ] **AC-7** (Sub-Varsity rest-table correctness fix): the `NSAA_SUBVARSITY` rest tiers in `src/reports/starter_prediction.py` are corrected. They currently encode rest days **0/1/2/3** at the 1–30/31–50/51–70/71–90 pitch breakpoints — byte-identical to `NSAA_PRE_APRIL` (NSAA Varsity) — but the authoritative NSAA Sub-Varsity curve is **stricter than Varsity by exactly one rest day at every tier** → **1/2/3/4** at those same breakpoints, per `.claude/rules/pitch-rules.md` and baseball-coach's `.claude/agent-memory/baseball-coach/league-pitch-rules.md` (sourced from the 2022 NSAA Baseball Rule Book). Without this fix the "High School — JV, Reserve, or Freshman" pick under-rests sub-varsity opponent arms by a day at every tier (marking an arm AVAILABLE when the rule says it is not) — which would make this story's SET accuracy sentence ("these calls are exact") false for sub-varsity. A test asserts a sub-varsity arm requires one more rest day than a varsity arm at each tier (e.g., an arm that threw 31–50 pitches needs 2 rest days under Sub-Varsity vs 1 under Varsity). Per `.claude/rules/testing.md` test-scope discovery, any existing engine test that encodes the old 0/1/2/3 Sub-Varsity curve is stale and MUST be brought to the corrected curve in the same change.

## Technical Approach
Add the operator-selected competition-level input to the `bb report generate` command (`src/cli/report.py`) and the admin submission form (`src/api/routes/reports_admin.py` + `src/api/templates/admin/reports.html`), thread it through `generate_report()` (`src/reports/generator.py`), and use it to override the `league` that the generator currently resolves via `detect_league_level(...)` at the starter-prediction block — mapping the three operator picks to the existing `league` identifiers the engine already understands and the unset case to the engine's guideline/estimate path. Reuse `starter_prediction.py`'s existing tables, `get_rules_for_league`, and `is_estimate` banner mechanism — do NOT add new rest-rule constants (they already exist) and do NOT change `starter_prediction.py`'s defaults. Carry the availability-basis fact through the fact-sheet contract from E-263-02a so E-263-04 can render the accuracy sentence. Season phase stays date-derived. Read Technical Notes TN-11 for the authoritative selector, copy, and rationale; `.claude/rules/pitch-rules.md` and baseball-coach's `.claude/agent-memory/baseball-coach/league-pitch-rules.md` are the authoritative rule-table references.

## Dependencies
- **Blocked by**: E-263-02a (the fact-sheet framework — the availability-basis fact rides its contract)
- **Blocks**: E-263-02b (SIG-001 consumes the operator-selected league), E-263-04 (renders the accuracy sentence)

## Files to Create or Modify
- `src/cli/report.py` (modify — add the operator-selected level input to `bb report generate`)
- `src/api/routes/reports_admin.py` (modify — accept the level from the submission form POST and pass it to `generate_report()`)
- `src/api/templates/admin/reports.html` (modify — add the level dropdown to the report-submission form)
- `src/reports/generator.py` (modify — `generate_report()` gains the level param; resolve the operator pick → `league`/guideline and override `detect_league_level` at the starter block; emit the availability-basis fact)
- `src/reports/starter_prediction.py` (modify — correct the `NSAA_SUBVARSITY` rest tiers from 0/1/2/3 to the authoritative 1/2/3/4 per AC-7; do NOT touch the other rule-table constants or the engine's defaults)
- `tests/test_deep_scout_level_gate.py` (new — each pick selects the right table, operator pick overrides team-name signal, season phase date-derived, unset → guideline/estimate, Sub-Varsity stricter-by-one-day per AC-7, no-migration/no-crawl)
- Any existing `starter_prediction` test file that encodes the old 0/1/2/3 Sub-Varsity curve (modify — bring to the corrected 1/2/3/4 curve; discover via `.claude/rules/testing.md` test-scope discovery)

Does NOT edit `scouting_report.html`, the deep_scout section partials, or another builder's group module — E-263-02a owns the template include seam (TN-9) and E-263-04 renders the accuracy sentence.

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-263-02b**: the operator-selected `league` (authoritative, overriding team-name inference) that SIG-001's eligibility computation consumes.
- **Produces for E-263-04**: the availability-basis fact (level label + set/unset + coach-facing accuracy copy) rendered in the Who's Pitching section.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] No new migration; no new crawling

## Notes
The correctness win is exact eligibility for the current live opponents (American Legion). Because the engine already carries the tables, this story is deliberately scoped to the input + override, not an engine rebuild. Keep the CLI flag and the admin dropdown at parity — the operator named both surfaces explicitly.

AC-7 folds in a pre-existing engine correctness bug that CA surfaced while reconciling `.claude/rules/pitch-rules.md` to the code (2026-07-18): `NSAA_SUBVARSITY` was byte-identical to NSAA Varsity pre-April, so it silently under-rested sub-varsity arms by a day at every tier. It is folded here because the "High School — JV/Reserve/Freshman" pick this story adds routes directly to that constant — a correct selection into a wrong table is a hollow correctness win, and the SET "these calls are exact" copy would be false for sub-varsity. The fix ALSO corrects the existing Most Likely Arms card for sub-varsity opponents (the bug is independent of Deep Scout, but 02c is its natural home).
