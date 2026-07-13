# E-262-03: Live Source Bugs

## Epic
[E-262: Post-Program Housekeeping](epic.md)

## Status
`DONE`

## Description
After this story is complete, two code-verified live bugs are fixed: `detect_league_level` recognizes GameChanger's free-text `age_group` range form, and the report generator no longer stamps a false-positive "name-only match" wrong-team badge on the first report of a pre-scouted opponent.

## Context
Two live bugs re-verified in code during the post-program ledger triage. (IDEA-122 was originally in this story but was RE-SCOPED to story 06 during review — see the note below.)
- **IDEA-126 (league-level range form, code half):** `detect_league_level` (`src/reports/starter_prediction.py:302-304` region) only matches the `\d+U` bracket form in its `age_group` branch. GameChanger also returns a free-text range form (`"Between 13 - 18"`), which falls through to `unknown` → suppress, killing the "Most Likely Arms" projection and Tier-2 Scouting Analysis for summer HS-age travel opponents with no NGB. The intended path is `youth_travel` → `PITCH_SMART_15_18` labeled estimate (already built in E-243-02). This story fixes the detection code only; the companion `age_group` field-doc note lives in story 09 (api-scout, `docs/api/`).
- **IDEA-127 (name-only badge false positive):** The report generator stamps `report_generation_runs.identity_match_method='name_only'` in `_ensure_team_row` (`src/reports/generator.py` ~`:1609-1657`; SE verified the stamp is at `:1627`, the public_id back-fill at `:1642-1646`, the run record written later at `:1677-1679`; identity cascade `src/db/teams.py:119-176`) BEFORE it back-fills the team's `public_id`/`gc_uuid` anchors within the same run. So the first direct report of any game-loader-created opponent stub (NULL `public_id` at cascade) always shows the operator "name-only match" wrong-team-risk badge even though the team is fully resolvable and self-heals. Sequencing bug — no stats are misattributed — but it erodes the badge's credibility for the real wrong-team case.

**Re-scoped in review (SE finding, IDEA-122):** the `bb creds check` false-green was originally an item in this story targeting `src/cli/creds.py`. SE + CA verified there is NO correct command-side fix: `creds.py:604` (single-profile) and `:610-611` (multi-profile all-dead) already exit non-zero; the ONLY false-green is the MIXED multi-profile case (web dead + mobile alive → `any_valid` → exit 0), and the "any valid = usable" contract must NOT be broken. Since the reports flow uses the WEB profile, the correct fix is skill-side — the Step 1d preflight calls `bb creds check --profile web` — which is **story 06's** file (`implement/SKILL.md`). IDEA-122 moved entirely to story 06; this story no longer touches `src/cli/creds.py`.

## Acceptance Criteria
- [ ] **AC-1**: Given a team whose GameChanger `age_group` is the free-text range form (e.g. `"Between 13 - 18"`) and no NGB, when a report is generated, then `detect_league_level` resolves it to the HS-age travel level (routing to the existing `PITCH_SMART_15_18` labeled-estimate path) rather than `unknown`/suppress; the existing `\d+U` bracket handling is unchanged.
- [ ] **AC-2**: Given the first direct report of a team that already exists as a name-only opponent stub which the run fully resolves (anchors back-filled), when the run completes, then `identity_match_method` reflects the resolved anchor (not `name_only`), so the operator wrong-team badge does not fire on a correctly-resolved team; a genuinely unresolved name-only match still records `name_only`. The downgrade MUST be guarded on a real anchor being established (per Technical Approach), not on UPDATE rowcount alone.
- [ ] **AC-3**: Tests cover both behaviors.

## Technical Approach
Two independent fixes in `src/reports/starter_prediction.py` (extend the `age_group` branch to the range form — the band-ambiguity caveat for mapping a 13-18 bracket to the 15-18 curve is documented in IDEA-126 and warrants a code comment) and `src/reports/generator.py` + `src/db/teams.py` (reorder or re-evaluate the identity-match stamp relative to the anchor back-fill so a resolved anchor is not mislabeled `name_only`). IDEA-127 open question lists three candidate fix shapes (back-fill public_id before stamping / re-stamp after back-fill / pass resolved gc_uuid into the cascade) — the implementer chooses.

**IDEA-127 guard (SE finding — MUST):** the public_id back-fill at `generator.py:1643` is `WHERE id=? AND public_id IS NULL`; if `self.public_id` is itself None, the UPDATE sets NULL→NULL with `rowcount=1` but establishes NO real anchor. The badge downgrade MUST guard on `self.public_id IS NOT NULL AND rowcount > 0`, not `rowcount` alone — otherwise AC-2's "genuinely unresolved name-only still records name_only" breaks (a NULL-public_id stub would be silently downgraded despite never resolving an anchor).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/reports/starter_prediction.py`
- `src/reports/generator.py`
- `src/db/teams.py`
- `tests/test_league_detection.py`, `tests/test_starter_prediction.py` (IDEA-126)
- `tests/test_report_generator.py`, `tests/test_ensure_team_row.py`, `tests/test_admin_reports.py` (IDEA-127)
- (Test Scope Discovery: the enumerated test files are the verifiable floor; the implementer greps `tests/` for any additional importer of the changed modules per `.claude/rules/testing.md` — false-negatives are the risk.)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-262-09**: IDEA-126's companion `age_group` range-form doc note is api-scout's; this story fixes only the detection code. No shared file — story 09 can proceed independently.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Sources: IDEA-126 (code half), IDEA-127 — both re-verified in code during the 2026-07-12 triage. IDEA-122 was RE-SCOPED out of this story to story 06 (skill-side Step 1d preflight) after SE+CA confirmed there is no correct `creds.py` fix — see the Context note and story 06.

**SE holistic review (2026-07-12) incorporated:** IDEA-122 re-scoped to story 06 (`creds.py` dropped from this story); IDEA-127 NULL-public_id guard added (downgrade only on `self.public_id IS NOT NULL AND rowcount > 0`) + anchors refreshed to `_ensure_team_row` ~`:1609-1657` (stamp `:1627`). IDEA-126 confirmed implementable as-is.
