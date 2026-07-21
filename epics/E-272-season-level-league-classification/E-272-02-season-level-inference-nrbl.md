# E-272-02: Season × level → league inference + NRBL league

## Epic
[E-272: Season × Level → League Classification (+ NRBL)](epic.md)

## Status
`TODO`

## Description
After this story is complete, `detect_league_level()` resolves an opponent's league from the season × level model (season picks the league family; age/level picks the tier), the Nebraska Reserve Baseball League (NRBL) is a supported pitch-count league, and the live bug — a scouted 18U American Legion opponent rendering the youth Pitch Smart estimate instead of the Legion rules — is fixed. The report applies the correct rest table for spring NSAA, summer Legion, and summer NRBL opponents without an operator having to intervene.

## Context
This is the core of the epic. It fixes the two failing detection paths (Technical Notes TN-1), implements the full precedence model (TN-2), adds the NRBL engine wiring (TN-3), and threads the season signal through the generator (TN-4). It depends on E-272-01 (the corrected `NSAA_SUBVARSITY` table it selects for spring sub-varsity). The precedence model and test strategy are the authoritative specs — implement against TN-2 and TN-7, not against the current cascade shape. This story deliberately does NOT add an operator-pick input or override of detection (that is E-263-02c; see Non-Goals and TN-6).

## Acceptance Criteria
- [ ] **AC-1 (bug fixed)**: Given a scouted 18U opponent with an empty `ngb`, no DB `program_type`/`classification`, and a team name containing "Legion"/"Senior", when a report is generated, then `detect_league_level` resolves `legion`, the Legion rest rules are applied, and the youth Pitch Smart estimate banner is NOT rendered. A test covers the resolution; the render-side outcome is covered per the existing report-generation test surface.
- [ ] **AC-2 (season × level precedence)**: `detect_league_level` implements the precedence in Technical Notes TN-2, including the `season: str | None = None` keyword. Tests cover each mapped bracket (18U→legion, 17U→legion, 16U→nrbl, 15U→nrbl), an unmapped bracket staying `youth_travel` (14U), and the free-text range form staying `youth_travel` (unchanged).
- [ ] **AC-3 (hardened season × level-word matrix — the general rule)**: `detect_league_level` maps every NSAA level word by season per TN-2 §4c (season picks the family across ALL level words; no level word drops to `unknown`). Tests cover the full matrix as concrete verification hooks: summer Varsity→legion; summer JV/Reserve/Freshman→nrbl; the spring counterparts (Varsity→nsaa_varsity, sub-varsity words→nsaa_subvarsity); and the season-absent NSAA defaults — with the summer-vs-spring-vs-absent Reserve case as the multi-scope discriminator anchor (a single-season fixture would hide the season axis). Season matching is case-insensitive, treating any non-summer / unknown / absent value as the NSAA default (TN-4).
- [ ] **AC-4 (recognized ngb wins over bracket)**: A recognized `ngb` still wins over the age-bracket mapping per TN-2 — a test covers `ngb=usssa` + 15U resolving to `usssa` (NOT `nrbl`), and `test_ngb_unrecognized` (present-but-unrecognized ngb → `unknown`) stays green.
- [ ] **AC-5 (NRBL engine wiring)**: A distinct `NRBL` `PitchCountRules` constant (equal to `LEGION`'s tiers today, distinct object per TN-3), an `nrbl` league id, and a `get_rules_for_league("nrbl", …)` arm are added. Tests cover: `get_rules_for_league("nrbl")` returns the NRBL constant with max 105; NRBL is a distinct object from `LEGION` with equal tiers (mirror `test_pitch_smart_is_distinct_constant_from_legion`); and NRBL renders as binding (`is_estimate=False`, not suppressed, no estimate banner).
- [ ] **AC-6 (season threading)**: The generator captures `team_season.season` and passes it into the `detect_league_level(...)` call per TN-4, with no schema change and no new crawling. The report still generates for an opponent `public_id` with and without a season present.
- [ ] **AC-7 (regressions + observability)**: The regression guards in TN-7 stay green (14U-beats-keyword ordering, no-bracket seniors/juniors → legion, range-form → youth_travel, `test_reserve_in_name` under the Q3 default with its new explicit-season sibling added). A data-quality log line fires when a mapped bracket and the season string actively disagree (TN-2), verified by a test. The `starter_prediction` importer set (TN-7) plus story-scoped tests pass; the full suite is green.

## Technical Approach
Restructure `detect_league_level()` to add the `season` keyword and the TN-2 precedence (recognized-ngb before the new empty-ngb region; mapped-bracket ladder shared between the age_group and team-name paths; season-disambiguated level words; conservative NSAA default). Add the `NRBL` constant, `nrbl` id, and `get_rules_for_league` arm per TN-3. Thread `team_season.season` through the generator per TN-4 (the `ts` object is already read for `.year`). Add and reconcile tests per TN-7 — the multi-scope Reserve spring-vs-summer discriminator is the critical test (a single-season fixture hides the season axis). Do NOT add an operator-pick input, a level flag, or any override of detection (TN-6 / Non-Goals). Do NOT reorder mapped-bracket ahead of recognized ngb (TN-2 rationale). The mapped-bracket ladder, tier numbers, and season vocabulary are behavior specs in TN-2/TN-4 — implement the behavior; the internal structure (helper extraction, matching style) is the implementer's call.

## Dependencies
- **Blocked by**: E-272-01 (shares `src/reports/starter_prediction.py` and `tests/test_league_detection.py`; needs the corrected `NSAA_SUBVARSITY` table)
- **Blocks**: E-272-04 (the pitch-rules.md doc documents the shipped behavior + supplies the frontmatter file list)

## Files to Create or Modify
- `src/reports/starter_prediction.py` (modify — `detect_league_level` restructure + `season` kwarg; `NRBL` constant; `nrbl` id + `get_rules_for_league` arm; the mapped-`\d+U`-bracket ladder must run AHEAD of ALL name keywords per TN-2 §4a — a granular pre-keyword bracket check, NOT a simple reorder of the flat `\d+U`→`youth_travel` entry within `_NAME_KEYWORDS`, which would break `test_14u_juniors_is_youth_travel`)
- `src/reports/generator.py` (modify — capture `self.season_from_api = ts.get("season")` at the existing `team_season` read; pass `season=` into the `detect_league_level(...)` call; add the `season_from_api` init default alongside the other `*_from_api` attrs)
- `tests/test_league_detection.py` (modify — add the mapped-bracket, multi-scope season-discriminator, NRBL-distinct-constant, recognized-ngb-wins, season-case-insensitivity, name-bracket, and disagreement-log tests; add the explicit-season sibling for `test_reserve_in_name`; verify regression guards stay green)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-272-04**: the shipped season-axis behavior and NRBL league id that `pitch-rules.md` documents, and the confirmed list of files that read `season` for league selection (for the frontmatter `paths:` AC) — `src/reports/generator.py` is confirmed; report any additional season-reading site.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] No new migration; no new crawling; no operator-pick input added

## Notes
The multi-scope Reserve spring-vs-summer discriminator is the highest-value test in the epic — it is the only one that exercises the season axis end to end, and a single-season fixture would silently hide the entire feature. api-scout confirmed (OQ-1, resolved) that `team_season.season` carries lowercase `"summer"` as its sole observed token, so the implementation matches on `"summer"` (normalized) and treats every other value (an unconfirmed `"spring"`, unknown, or absent) as the conservative NSAA sub-varsity default per TN-4. The U-suffix mapped-bracket constraint in TN-2 (only single `\d+U` brackets map; the range form stays `youth_travel`) is load-bearing for keeping the IDEA-126 range tests green.

AC-1's youth-estimate-banner check is satisfied by the existing string/DOM report-generation test surface — it is `is_estimate`-bool-driven conditional inclusion, not a layout/print/disclosure/responsive change, so per `.claude/rules/browser-render-testing.md`'s self-limiting test the headless-Chromium rule is NOT triggered and a DOM/string assertion suffices (SE-MINOR-1). Do not demand a Playwright test for it.
