# E-263-02b: SIG-001 probable-starter fact

## Epic
[E-263: Deep Scout v1 — Opponent-Intelligence Report Sections](epic.md)

## Status
`TODO`

## Description
After this story is complete, the fact sheet carries the SIG-001 probable-starter fact (eligibility + ranked probable starter(s), with a "committee" state) for the scouted opponent — the join target that E-263-04 (Who's Pitching) and E-263-07 (Game Plan) condition on. This story is data-only: it computes SIG-001 into the fact sheet and is unit-tested; it renders NO partial (E-263-04 renders SIG-001 inside the Who's Pitching partial it owns), preserving file-disjointness.

## Context
Per Technical Notes TN-4, SIG-001 is the structural join target for every pitcher/blueprint signal — the #1-miss fix. The NSAA rest-rules engine (`src/reports/starter_prediction.py`) is already team-agnostic; `get_pitching_history(team_id, season_id)` / `build_pitcher_profiles` (`src/api/db.py`) are parameterized and perspective-filtered, and `pitches` is columnar (no boxscore summing gap, per DE). v1 is opponent-only (Technical Notes TN-10): SIG-001 eligibility uses the report's existing reference-date mechanism — no `--date` flag. Split from the original E-263-02 so the framework/wiring (E-263-02a) and the first signal land as separately-sized sessions (CR SHOULD-1).

## Acceptance Criteria
- [ ] **AC-1**: SIG-001 (probable starter + eligibility) is computed into the fact sheet for the scouted opponent by reusing `src/reports/starter_prediction.py` + `get_pitching_history`/`build_pitcher_profiles`, using the report's existing reference-date mechanism. The computation is filled INTO the pre-wired pitching group stub that E-263-02a's assembler already calls (per Technical Notes TN-9) — NOT a standalone module the assembler doesn't invoke — so the SIG-001 fact is actually composed into the fact sheet. A test asserts the SIG-001 fact appears in the assembled fact sheet for a given opponent `team_id`/`season_id`.
- [ ] **AC-2**: SIG-001 emits a "committee" state (never a false-precision single pick) when two or more arms are equally rested/eligible, per Technical Notes TN-4. A test covers the equally-rested case.
- [ ] **AC-3**: The SIG-001 rollup scopes to a single `perspective_team_id` (the scouted opponent's own) per Technical Notes TN-3 — the pitching-history reader already carries both the `team_id` role filter and the `perspective_team_id` dedup filter (db.py:307-308); the AC verifies neither is bypassed. The twin-game fixture from E-263-02a proves no double-count.
- [ ] **AC-4**: SIG-001's fact carries `ethics_tier = coach_facing` per Technical Notes TN-1 (strategic rest/pitch-count data on a named opponent). This story renders NO template partial — the fact is data-only; E-263-04 renders it.
- [ ] **AC-5** (operator-decided 2026-07-13 — "honor the flag, loud-signal if off"): SIG-001 depends on `src/reports/starter_prediction.py`, gated by the false-by-default `FEATURE_PREDICTED_STARTER` env flag. E-263 does NOT promote the flag (it stays default-OFF; do NOT change `starter_prediction.py`'s default). E-263-02b HONORS the flag: (a) flag ON → SIG-001 populates the fact sheet and the starter-conditioned sections (E-263-04 Who's Pitching, E-263-07 Game Plan) render; (b) flag OFF → SIG-001 is absent and Deep Scout emits a LOUD operator signal — the starter-conditioned sections fail VISIBLY (a clear degraded/warning state on the report AND on the `report_generation_runs` record, per the existing operator-vs-coach honesty split), NEVER a silent empty section. A test covers both branches. (The promote-to-default decision is a SEPARATE, still-OPEN backlog item — audit residual #12 — that E-263 does NOT resolve.)

## Technical Approach
Fill the SIG-001 computation into the pitching group stub module from E-263-02a (the one the assembler already calls), so it is composed into the fact sheet. Reuse the existing starter-prediction engine and its reference-date mechanism rather than re-deriving eligibility. Do not render a partial here — E-263-04 owns the Who's Pitching partial that surfaces SIG-001. Per AC-5 (operator-decided), honor `FEATURE_PREDICTED_STARTER` (default-OFF, not promoted): when off, surface a loud operator signal + a visible degraded state on the starter-conditioned sections (E-263-04/07), never a silent empty section — reuse the existing report-run degraded/honesty mechanism rather than inventing a new one.

## Dependencies
- **Blocked by**: E-263-02a (the fact-sheet framework + assembler skeleton)
- **Blocks**: E-263-04, E-263-07

## Files to Create or Modify
- `src/reports/deep_scout/<pitching stub module>.py` (modify — fill the SIG-001 computation into the pre-wired pitching group stub the assembler calls, per Technical Notes TN-9; NOT a standalone unassembled module)
- `tests/test_deep_scout_sig001.py` (new — probable-starter fact, committee state, perspective-scoping via the shared twin-game fixture)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-263-04**: the SIG-001 probable-starter fact (rendered in the Who's Pitching section) and the join target for SIG-004/006/016.
- **Produces for E-263-07**: the SIG-001 fact the two-branch Game Plan conditions on.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Data-only story — its increment is a computed + tested SIG-001 fact in the fact sheet, not a visible render (E-263-04 provides the render). This keeps SIG-001 and the Who's Pitching section file-disjoint.
