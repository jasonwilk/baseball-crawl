# E-263-06: Their Hitters & Defense section (SIG-007/008)

## Epic
[E-263: Deep Scout v1 — Opponent-Intelligence Report Sections](epic.md)

## Status
`TODO`

## Description
After this story is complete, the report renders a "Their Hitters & Defense" section (Technical Notes TN-5 Section 3) that turns spray data into an actionable defensive-alignment directive per hitter (SIG-007) and an error-map of the opponent's defense that names bunt/pressure targets (SIG-008) — both computed as pure SQL over `spray_charts`, no new parser.

## Context
Per api-scout and SE, the alignment and error-map signals read `spray_charts` (already-persisted `fielder_position`, `x`/`y`, `play_result`, `play_type`), NOT `final_details` (confirmed not persisted; moot for v1). Per Technical Notes TN-2, alignment needs a 15 BIP directional floor. SIG-008 carries a specific attribution caveat: a defensive error-map query was previously caught counting the WRONG team, so the `team_id`/perspective filter MUST be verified before any error-map fact ships (Technical Notes TN-3 perspective-scoping applies). SIG-007 is the ONE signal with a player-safe carve-out (a hitter may be referenced by number for alignment, per Technical Notes TN-8). Placement of the error-map (own sub-section vs a Game Plan bullet) is resolved by the E-263-01 layout spec (OQ3).

## Acceptance Criteria
- [ ] **AC-1**: The report renders a Their Hitters & Defense section per Technical Notes TN-5 (Section 3), placed per the E-263-01 layout spec (OQ3 RESOLVED: SIG-008 error-map is its OWN subsection here, not folded into the Game Plan). It fills the pre-created hitters-defense stub module + partial from E-263-02a. **Graceful-dark (gc_uuid-gated, api-scout-F1):** SIG-007/008 read `spray_charts`, which only populates when the opponent's `gc_uuid` resolves; when it doesn't (unindexed opponents) OR the scorekeeper recorded no defensive spray, the WHOLE section renders a clean, clearly-labeled `no_data` state (per E-263-01), NOT a broken/empty card, while the plays-derived sections still populate.
- [ ] **AC-2**: SIG-007 alignment directive is computed per hitter as GB% + pull/oppo side → a positioning INSTRUCTION ("shade 3B/SS, guard the 5-6 gap" / "infield in" at ≥50% GB / "OF deep" at ≥45% FB), from `spray_charts` rows filtered per Technical Notes TN-3: `chart_type='offensive'` AND `team_id = X` AND `perspective_team_id = X` (X's hitters' batted balls). Per Technical Notes TN-2's stat-vs-directive distinction: below the 15 BIP directional floor the DIRECTIVE (the recommendation) is withheld with an "insufficient sample for a directive" state, while the raw spray counts are STILL shown — the data is never hidden, only the projection is.
- [ ] **AC-3**: SIG-008 error-map is computed as errors / fielding chances per position from `spray_charts` rows filtered per Technical Notes TN-3: `chart_type='defensive'` AND `team_id = X` AND `perspective_team_id = X` AND `error=1`, grouped by `fielder_position`. **`chart_type='defensive'` is MANDATORY and IS the wrong-team fix, NOT `team_id`** (DE ruling): on the OFFENSIVE chart, `defenders[0].error` is the OPPONENT's fielder but is stored under `team_id = X` (the batter is X's), so an error-map built off the offensive chart counts the OPPONENT's errors mislabeled as X's — the observed wrong-team bug. **The test MUST seed an opponent error on the OFFENSIVE chart under `team_id = X` and prove it is NOT counted in the error-map.** Below the **~10-chances-per-position floor** (Technical Notes TN-2) no directive issues (raw counts only). Defensive-spray coverage is scorekeeper-dependent (confirm it is actually populated for scouted opponents), so the `no_data` path is COMMON and is exercised in tests.
- [ ] **AC-4**: Every rollup in this section applies BOTH the perspective (dedup) filter `spray_charts.perspective_team_id = X` AND the role/team-selection filter `team_id = X` + the `chart_type` discriminator per Technical Notes TN-3 (spray carries its own columns; no plays join). A test using the shared twin-game fixture (E-263-02a) proves no double-count.
- [ ] **AC-5**: SIG-007's player-safe carve-out is honored per Technical Notes TN-8 — a hitter may be referenced by number for alignment purpose with no weakness language; the fact carries the player-safe ethics tier (distinct from the coach-only signals).

## Technical Approach
Fill the pre-created hitters-defense stub module under `src/reports/deep_scout/` (from E-263-02a) computing SIG-007 (all `spray_charts` rows) and SIG-008 (`chart_type='defensive'` + `error`) as pure SQL over `spray_charts`, filtered directly on `spray_charts.perspective_team_id`. The SIG-008 attribution verification is the correctness core — the previously-observed wrong-team error-map means the offensive-vs-defensive row split + the perspective filter are not optional. Fill the Their Hitters & Defense stub partial, reusing the shared trust-surface partial; ensure the whole-section `no_data` graceful-dark state per AC-1. Read design-doc §8b-ii for the alignment-directive framing (GB% + side → instruction).

## Dependencies
- **Blocked by**: E-263-01 (layout spec), E-263-02a (fact-sheet framework + hitters-defense stub + partial)
- **Blocks**: None

## Files to Create or Modify
- `src/reports/deep_scout/<hitters module>.py` (modify — fill the SIG-007/008 builder stub from E-263-02a)
- `src/api/templates/reports/deep_scout/<hitters-defense partial>.html` (modify — fill the Their Hitters & Defense stub partial from E-263-02a)
- `tests/test_deep_scout_hitters_defense.py` (new — alignment directive thresholds, 15 BIP floor, SIG-008 ~10-chances floor + correct-team defensive attribution, gc_uuid/no-spray graceful-dark, perspective-scoping via the shared twin-game fixture)

Does NOT edit `scouting_report.html` or the assembler — E-263-02a owns those seams per Technical Notes TN-9.

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Pure SQL over `spray_charts` — no parser dependency. Parallel-safe with E-263-04/05 (different builder module) once the foundation lands. The SIG-008 wrong-team attribution guard is the load-bearing regression test.
