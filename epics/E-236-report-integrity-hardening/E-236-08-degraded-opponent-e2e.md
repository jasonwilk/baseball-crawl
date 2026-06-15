# E-236-08: Degraded-opponent acceptance & negative-path E2E (both surfaces)

## Epic
[E-236: Report Self-Reporting Integrity Hardening](epic.md)

## Status
`TODO`

## Description
After this story is complete, a single end-to-end test will generate a report against a deliberately-degraded opponent — a MIX of games so a real report still RENDERS (some games charted → N>0) while being degraded (at least one scored-but-empty game → N<M; all plays-fetches failing; spray-less) — and assert that BOTH integrity surfaces tell the truth: the run record shows honest per-stage statuses/counts, the coach footer shows honest coverage severity, and there is NO false alarm on the clean parts. This is the strong test that proves the epic's unifying invariant.

## Context
This is the acceptance test the epic is built to satisfy (epic Technical Notes TN-9). It runs transport-only on the E-234 respx harness in a sibling `tests/fixtures/e2e_degraded/`, leaving the golden e2e oracle untouched. **The scenario must keep N>0** (some games carry full boxscore data) so a full report with a footer trust-block renders — a pure N==0 scenario produces the `no_games` page (no footer), which is covered by story 05, not here. The "scored-but-empty" boxscore is the api-scout-confirmed **sub-case A** shape (TN-9): both team-key envelopes present (own = `public_id` slug / no dashes, opp = UUID / with dashes), per-team `groups` present but per-player `stats` arrays EMPTY → games row + final score written, zero stat rows, `LoadResult.errors=0` → `load_status="completed"`. api-scout confirmed sub-case A 2026-06-14 (evidence: real partial-empty capture `data/raw/2026-spring-hs/scouting/LHIYRnPoo8DC/boxscores/03c21843-...json` + SE's structural proof). The fixture's scored-but-empty boxscore MUST be the SAME shape story 09 uses.

## Acceptance Criteria
- [ ] **AC-1**: A new `tests/fixtures/e2e_degraded/` with its own `manifest.json` drives the E-234 respx harness; the existing golden e2e oracle/fixtures are NOT modified.
- [ ] **AC-2**: The degraded scenario has M completed games (M ≥ 3) where: at least one game carries FULL boxscore data (charted → contributes to N, so a report renders), at least one game is a sub-case A scored-but-empty boxscore (counts toward M but not N → `0 < N < M`); ALL plays-fetches → 403/500; ALL spray → `spray_chart_data: null`. The scored-but-empty boxscore is built from the api-scout-confirmed sub-case A skeleton (see Notes) and is the SAME shape story 09 uses.
- [ ] **AC-3**: One test runs `generate_report` and asserts the `report_generation_runs` row (SELECT by `report_id`): `crawl_status == "completed"` (all boxscore fetches succeed with valid dict bodies → `games_crawled == M`), `load_status == "completed"` (full + sub-case-A-empty loads, `errors=0`), `plays_status == "failed"` (all-403 plays), `spray_status == "completed"` (spray-null-no-error is NOT a failure — error-driven status per TN-1/TN-7 spray note; must NOT be `"partial"`/`"failed"`), M (`completed_games`) > 0, `0 < N (completed_games_with_data) < M`, K (`plays_games_covered`) == 0, the new count columns (incl. `spray_games_with_data == 0`), and `overall_status == "completed"`. The derived operator-"degraded" flag is true (overall completed + plays_status failed).
- [ ] **AC-4**: The SAME test reads the rendered report (N>0 → a full report renders) and asserts the coach surface is honest: coverage severity reflects N-of-M (per the existing E-235 severity bands), "No pitch-detail data" appears (K==0 → the existing E-235 branch at renderer.py:596 + template :875-879 — a regression guard, not new behavior), spray shows "unavailable", and the coach degraded-confidence line does NOT fire on the clean identity (no false alarm).
- [ ] **AC-5**: A negative-path assertion confirms the charted games' stats render correctly (the degradation does not corrupt the data that IS present).
- [ ] **AC-6**: Both surfaces are asserted in ONE test so they cannot drift independently (Technical Notes TN-9).

## Technical Approach
Reuse the E-234 respx transport harness; add the sibling degraded fixture set + manifest with the mixed-games scenario (charted + sub-case-A-empty boxscores). Mock plays → 403/500 (no fixture needed); spray → null payload. The full/charted boxscore(s) can adapt sanitized shapes from the existing e2e harness; the scored-but-empty boxscore uses the api-scout sub-case A skeleton (Notes). Drive the real `generate_report()` and assert against both the DB run record and the rendered HTML/trust-block. Do not modify the golden oracle.

## Dependencies
- **Blocked by**: E-236-01, E-236-02, E-236-03, E-236-04, E-236-05, E-236-06, E-236-07, E-236-09. (The api-scout scored-but-empty boxscore shape is CONFIRMED sub-case A — TN-9 — so no external blocker remains; the fixture is built from the skeleton in Notes.)
- **Blocks**: None

## Files to Create or Modify
- `tests/fixtures/e2e_degraded/` (create — manifest + sanitized payloads: at least one charted boxscore + at least one sub-case A scored-but-empty boxscore; the empty one shared in shape with story 09)
- New E2E test (create — e.g. `tests/test_report_e2e_degraded.py`)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
SE S4. **api-scout CONFIRMED sub-case A (2026-06-14):** a real GC scored-but-empty boxscore has both team-key envelopes present (own = `public_id` slug / no dashes, opp = UUID / with dashes), `groups` present per team, per-player `stats` arrays EMPTY → `LoadResult.errors=0` → `load_status="completed"`, `crawl_status="completed"`. Sub-case B (keyless body → `errors=1`) carries NO final-score games row, so it is NOT the scored-but-empty case and is NOT needed for this E2E.

**Sub-case A fixture skeleton** (byte-confirmed by api-scout's live capture 2026-06-14 on 2 real LSB Varsity empty boxscores — `08e8658e`, `ab05fce5`, both HTTP 200; shared in shape with story 09):
```
{
  "<ownSlugNoDashes>": { "players":[],
    "groups":[ {"category":"lineup","team_stats":{<all-zeroed>},"extra":[],"stats":[]},
               {"category":"pitching","team_stats":{<all-zeroed>},"extra":[],"stats":[]} ] },
  "<oppUUIDwithDashes>": { "players":[<~20 full roster entries>],
    "groups":[ {"category":"lineup","team_stats":{<all-zeroed>},"extra":[],"stats":[]},
               {"category":"pitching","team_stats":{<all-zeroed>},"extra":[],"stats":[]} ] }
}
```
Fixture-author notes (api-scout, byte-confirmed): KEEP the asymmetric keys (own = slug no-dashes, opp = UUID with-dashes) — `_detect_team_keys` relies on this. **`groups` is NEVER `[]` in the wild — it is a length-2 list with BOTH `lineup` and `pitching` categories present, each `{category, team_stats: all-zeroed, extra:[], stats:[]}`** (this was the one detail we couldn't pin from disk; now pinned). `players` is variable: own team had `players:[]`, opponent had a FULL roster (~20) even with empty stats — the loader tolerates either. `team_stats` is all-zeroed and does not affect the loader. **Pair the boxscore with a NON-ZERO final score on the games-row side** — faithful, since the score is summary-sourced, not boxscore-sourced. (The loader also tolerates `groups:[]` defensively via `group.get("stats") or []`, but the real shape is categories-present + empty-stats — use that.) Conclusion unchanged: sub-case A → `errors=0` → `load_status="completed"`, `crawl_status="completed"`.
