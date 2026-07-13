# E-263-05: Running Game & Battery section / catching card (SIG-002/003)

## Epic
[E-263: Deep Scout v1 — Opponent-Intelligence Report Sections](epic.md)

## Status
`TODO`

## Description
After this story is complete, the report renders a "Running Game & Battery" section (Technical Notes TN-5 Section 4) — the operator's catching-stats ask — combining the steal light (SIG-003: opponent battery run-control, SB% and WP+PB) with the battery-control card (SIG-002: catcher CS%, backpicks as raw counts, pitcher pickoffs, plus the first-and-third bait-play call). Every stat is attributed strictly by `player_id`/UUID and perspective-scoped, and the card is framed as plays-derived.

## Context
This is the catching-stats section the operator explicitly confirmed for v1. Per Technical Notes TN-3, the correctness rules are hard: roll up by the `${uuid}` actor token (never name — a name-keyed rollup silently merges players across teams) and scope to a single `perspective_team_id` (join `play_events → plays`, filter `plays.perspective_team_id = ?`) so an un-merged cross-perspective twin game does not double-count steals/backpicks — this is what makes the section correct independent of E-261. Per TN-7, there is no official catcher line in the non-owned boxscore, so the card is plays-derived with no reconciliation target and must be framed distinct from the boxscore-reconciled batting/pitching stats. Per TN-8, the steal light (named opposing catcher) is the sharpest ethics risk and is coach-facing ONLY. It consumes the E-263-03 battery-events parser.

## Acceptance Criteria
- [ ] **AC-1**: The report renders a Running Game & Battery section per Technical Notes TN-5 (Section 4), placed per the E-263-01 layout spec.
- [ ] **AC-2**: SIG-002 battery-control card is computed from the E-263-03 parser over the opponent-on-DEFENSE plays per the Technical Notes TN-3 role filter (`plays.perspective_team_id = X` AND `plays.batting_team_id != X`), keyed strictly by the `${uuid}` per Technical Notes TN-3. Specifics (DE ruling):
  - **CS% is a TEAM-battery ratio, NOT per-catcher** — `CS_events / (CS_events + SB_events)` over the opponent's defensive PAs (the design-doc §8 "90/103 vs their battery" number). A clean steal names no catcher, so a per-catcher CS% is not computable; per catcher, show RAW CS COUNTS only.
  - **Single-source guard**: both CS_events and SB_events (SB_events = the E-263-03 `stolen_base` sub-type) come from `play_events` — NEVER mix plays-CS with boxscore-SB (they can disagree and yield CS% > 100%).
  - **Zero denominator** (CS+SB = 0 vs the opponent all season) renders `no_data` ("no steal attempts vs their battery, n=0"), never 0/0.
  - Catcher backpick putouts as RAW COUNTS never a rate (flag "STRONG BACKPICK ARM" at 2+ per Technical Notes TN-2); pitcher pickoffs per arm (`plays.pitcher_id` cross-checks); WP+PB shown as a RAW COUNT always, plus optionally a per-opponent-defensive-game rate (denominator = distinct games with `batting_team_id != X`), `no_data` only if games = 0. Pickoff-attempt frequency reads as a trend only at **≥5 games** (Technical Notes TN-2). A battery event the parser flagged actor-unknown (E-263-03 AC-7) is counted in the TEAM-level tally but EXCLUDED from per-player attribution — never mis-attributed to another catcher.
- [ ] **AC-3**: SIG-003 steal light is the opponent battery's SB-allowed success rate — the success of the OPPOSING runners facing the opponent's battery, per the Technical Notes TN-3 role filter (**`team_id != X`** in `player_game_batting`, perspective = X; NOT `team_id = X`, which would be the opponent's OWN runners / an offense signal). It may equivalently be computed from the same `play_events` `stolen_base`/`caught_stealing` events on `batting_team_id != X` PAs used by AC-2 (single-source preferred). Below 5 attempts the rate renders `thin` (raw count still shown — "3-for-5 caught" — never dimmed, per the TN-2 idiom); a zero-attempt battery renders `no_data`. v1 ships NO green/red "should WE run" pairing overlay — that requires the `--vs` matchup context deferred to v2 (Technical Notes TN-10).
- [ ] **AC-4**: Every rollup in this section applies BOTH the perspective (dedup) filter AND the role (team-selection) filter per Technical Notes TN-3 — battery stats: `plays.perspective_team_id = X` AND `plays.batting_team_id != X` (via the `play_events → plays` join); steal light: `perspective_team_id = X` AND `team_id != X`. A test using the shared twin-game fixture (E-263-02a) proves steals/backpicks/pickoffs AND the SB/CS denominator are NOT double-counted, AND that flipping the role filter's direction changes the result (guarding against a missing/inverted role guard).
- [ ] **AC-8**: Actor names for the battery card come from a LEFT JOIN of the parsed actor UUID → `players`; on a miss (a parsed UUID with no `players` row — design-doc §8d saw a non-locatable backpick actor) the card degrades to the stub/"Unknown" convention for display and NEVER drops or errors on the event (DE-F2).
- [ ] **AC-5**: When a backpick tendency is flagged, the card surfaces the first-and-third bait-play call as OUR edge (dual-use per design-doc §8d), not only a defensive warning.
- [ ] **AC-6**: The section is framed as plays-DERIVED and visibly distinct from the boxscore-reconciled batting/pitching stats per Technical Notes TN-7 (no implication of official/byte-identical fidelity).
- [ ] **AC-7**: The steal light and any named opposing catcher render coach-facing ONLY per Technical Notes TN-8 (the fact carries the coach-only ethics tier).

## Technical Approach
Fill the pre-created running stub module under `src/reports/deep_scout/` (from E-263-02a) — consume the E-263-03 `battery_events` parser over the opponent's perspective-scoped `play_events` (joined through `plays`), plus `player_game_batting` (SB/CS per `player_id`, filtered on its OWN `perspective_team_id` per Technical Notes TN-3) for the steal light. The per-table perspective filter and UUID keying are the correctness core — write them as explicit query constraints, not incidental. Fill the Running Game & Battery stub partial, reusing the shared trust-surface partial. Read design-doc §8c (concentration) and §8d (battery-control parse forms + dual-use bait play) for the coaching framing.

## Dependencies
- **Blocked by**: E-263-01 (layout spec), E-263-02a (fact-sheet framework + running stub + partial), E-263-03 (battery-events parser)
- **Blocks**: None

## Files to Create or Modify
- `src/reports/deep_scout/<running module>.py` (modify — fill the SIG-002/003 builder stub from E-263-02a)
- `src/api/templates/reports/deep_scout/<running-battery partial>.html` (modify — fill the Running Game & Battery stub partial from E-263-02a)
- `tests/test_deep_scout_running.py` (new — UUID-keyed rollup, per-table role+perspective scoping via the shared twin-game fixture, backpick raw-count flag, actor-unknown team-level count, LEFT-JOIN Unknown degrade, steal-light thin/no_data state)

Does NOT edit `scouting_report.html` or the assembler — E-263-02a owns those seams per Technical Notes TN-9.

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
This is the section most exposed to the attribution and perspective-scoping footguns (Technical Notes TN-3) — the twin-game no-double-count test is the load-bearing regression guard. Parallel-safe with E-263-04 (different builder module) once the foundation and parser land.
