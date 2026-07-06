# E-253-06: Ingestion Integrity Guards — Stat-Key Drift Canary + 0-0 Coercion

## Epic
[E-253: Data-Integrity & Deletion Safety](epic.md)

## Status
`DONE`

## Description
After this story is complete, a GameChanger field rename that silently zeroes a stat for every player will surface as a load ERROR instead of passing verification, and missing game-summary scores will no longer be coerced to 0-0 in a way that lets a scoreless doubleheader collapse into one game. Both are ingestion-integrity guards in the game loader.

## Context
See epic Technical Notes **TN-7** (canary) and the audit LOW finding for score coercion.
- **Stat-key drift canary** (`game_loader.py:932`): a GC field rename silently zeroes a stat for every player on both teams; `verify-aggregates` passes because both sides share the corrupted source. The canary must ERROR when a core key is absent from ALL rows of a non-empty group — the group-grain that survives into the future E-245 scoreboard as a hard-fail signal ("align, don't build").
- **0-0 coercion** (`game_loader.py:500`): missing game-summary scores coerced to 0-0 lets a scoreless doubleheader collapse into a single game (the natural-key dedup treats both as the same 0-0 game).

## Acceptance Criteria
- [ ] **AC-1** (canary fire rule): Given a NON-EMPTY stat group of a type in scope, when a core key in that type's canary set is absent from the per-row `stats` dict of ALL rows in the group (simulating a GC field rename), then the loader records ONE group-grain ERROR (`LoadResult.errors += 1`, per TN-7 — group-grain, NOT per-row) rather than silently loading zeros. The canary core sets (verified invariant across 46 real boxscores):
  - **Batting** (`category="lineup"` group): `AB, R, H, RBI, BB, SO` — the existing `_BATTING_MAIN` keys (`game_loader.py:68`), read from each row's `stats` dict.
  - **Pitching** (`category="pitching"` group): `H, R, ER, BB, SO` **plus `IP`** — the existing `_PITCHING_MAIN` keys (`game_loader.py:97`) plus the separately-read `IP` literal (IP is converted to `ip_outs`, so it is not in the dict but IS always present per row and must be included).
  Proven by a failing-input test that renames one core key in ALL rows of a group.
- [ ] **AC-2** (canary no-fire rule + scope): Given a core key present in ≥1 row of the group, no canary error is raised. **Extras are NOT canary keys**: batting extras (`2B, 3B, HR, SB, TB, HBP, CS, SHF, E`) and pitching extras (`WP, HBP, #P, TS, BF`) live in a SEPARATE `extra` array (not the per-row `stats` dict) and are optionally-absent by design — an extra absent from all rows (e.g., no doubles all game → `2B` absent everywhere) MUST NOT fire the canary. The canary is strictly the per-row `stats`-dict main set. **Groups in scope: batting (`lineup`) + pitching (`pitching`) ONLY** — fielding/catcher groups are OUT OF SCOPE because the loader never parses them (`game_loader.py:875-878`), so nothing is silently zeroed there. Proven by a test where an extra is absent from all rows → no error.
- [ ] **AC-3**: Given a game whose summary is missing score data, when the loader inserts the game, then the missing scores are NOT coerced to 0-0 in a way that collapses distinct games — a genuinely scoreless doubleheader remains two `games` rows.
- [ ] **AC-4**: The canary's group-grain and error surfacing are designed scoreboard-compatible per TN-7 (the ERROR is a hard-fail signal the future E-245 scoreboard can consume) — this story does NOT build the scoreboard.

## Technical Approach
See epic Technical Notes **TN-7**. Two independent guards in `game_loader.py`. The implementing agent owns the exact detection and the missing-score representation (e.g., NULL vs. a sentinel) so long as it does not collapse distinct games. Keep the canary at group-grain, not per-row.

**Canary core-key source (SE, robustness)**: source the canary's core-key set from the existing `_BATTING_MAIN` / `_PITCHING_MAIN` dicts (`game_loader.py:68` / `:97`) plus the `IP` literal for pitching — NOT a fresh parallel hardcoded list. This single-sources "core keys" with the parse contract, so adding/removing a main key makes the canary track it automatically. Deterministic rule, stated plainly: **the canary core keys are the keys the loader reads out of each row's `stats` dict** (plus the always-present `IP` for pitching). Verified invariant across 46 real boxscores (941 batting rows, 207 pitching rows).

**Test-validates-spec**: the failing-input test mocks a group where one `_BATTING_MAIN` / `_PITCHING_MAIN` key is renamed in ALL rows → assert ERROR; a normal group → assert no error; an extra absent from all rows → assert no error. Mock field names come from the real boxscore shape + `docs/gamechanger-stat-glossary.md`, not invented (per `.claude/rules/testing.md` Test-Validates-Spec).

## Dependencies
- **Blocked by**: E-253-04 (also modifies `src/gamechanger/loaders/game_loader.py`; run E-253-04 first to isolate per-story diffs)
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py` (canary site ~line 932; score-coercion site ~line 500)
- `tests/` — canary failing-input test + 0-0 coercion / scoreless-doubleheader test

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Cross-reference: `.claude/rules/data-model.md` (Game-ordering convention — doubleheaders), `.claude/rules/testing.md` (Test-Validates-Spec — canary test mocks must match the authoritative field names).
