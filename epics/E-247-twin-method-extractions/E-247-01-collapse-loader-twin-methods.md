# E-247-01: Collapse loader in-memory vs disk twin methods

## Epic
[E-247: Twin-Method & Duplicated-Block Extractions](epic.md)

## Status
`TODO`

## Description
After this story is complete, the near-identical in-memory and disk loading paths in the scouting loader and scouting spray loader will share a single payload-processing core, with each disk variant reduced to a thin JSON-read+validate wrapper that delegates to it. This fixes the already-drifted spray copies.

## Context
The sweep's H2 finding: `scouting_loader` (`load_team` vs `_load_team_from_disk` plus 3 builder pairs) and `scouting_spray_loader` (`_load_game_data` vs `_load_game_file`) each duplicate ~50-80 lines of orchestration. The spray copies have already drifted — one logs on non-list events, the other silently skips. The project already solved this pattern in `plays_loader._load_game` / `GameLoader._load_boxscore_data`, where the disk path is a thin wrapper over an in-memory payload core. This story brings the two holdout loaders in line with that established pattern.

## Acceptance Criteria
- [ ] **AC-1**: Given the scouting loader's in-memory and disk paths duplicate orchestration, when the story completes, then the disk path (`_load_team_from_disk` and its builder pairs) is a thin JSON-read+validate wrapper delegating to the in-memory payload core (the ~50-80 lines of shared orchestration exist once).
- [ ] **AC-2**: Given the spray loader's `_load_game_data` vs `_load_game_file` duplicate orchestration and have drifted, when the story completes, then both route through one shared core and the non-list-event handling is unified to a single, intentional behavior (resolving the drift).
- [ ] **AC-3**: Given the unified spray non-list-event handling, when the story completes, then the single chosen behavior (log vs silently skip) is (a) implemented as one intentional code path, (b) documented in a code comment at the unified handler stating which behavior was kept and why, and (c) asserted by a test in `tests/test_scouting_spray_loader.py`. The drift-resolution choice is called out in the story handoff for **code-reviewer** sign-off (the named approver) — code-reviewer confirms the deliberate choice during the per-story review, not an unnamed "acceptable."
- [ ] **AC-4**: Given the consolidation (HARD GATE — stats integrity, per epic Technical Notes), when a golden-fixture/characterization `pytest` test loads representative in-memory and disk inputs, then the loaded stat rows are byte-identical to the pre-story output for both paths (in-memory byte-identical; the disk path matches the in-memory path on the same payload). The test pins pre-change output and passes against post-change code — not visual inspection. If equivalence cannot be proven, the story is cut/deferred, not shipped.
- [ ] **AC-5**: Given the consolidation, when the loader test modules (`tests/test_scouting_loader.py`, `tests/test_scouting_spray_loader.py`), including the AC-4 golden-fixture/characterization test, run, then they pass. (The full-suite-green check across `tests/` is the epic-level closure gate — Technical Notes "Closure Gate (blocking)" — not a per-story AC, because the whole-suite run is only authoritative in the merged main checkout, not the worktree.)

## Technical Approach
Report locations (re-verify before acting): `src/gamechanger/loaders/scouting_loader.py:77-248`, `:330-446`, `:513-549`; `src/gamechanger/loaders/scouting_spray_loader.py:214-308`, `:370-497`. Follow the `plays_loader._load_game` / `GameLoader._load_boxscore_data` pattern: collapse each disk variant to a thin JSON-read+validate wrapper, extract the shared orchestration (the sweep suggests a `_finish_load(...)` extraction — illustrative). The spray non-list-event drift must be resolved to one behavior; surface the choice for review.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/scouting_loader.py`
- `src/gamechanger/loaders/scouting_spray_loader.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Spray non-list-event drift resolved to one path, documented in a code comment + test, and signed off by code-reviewer (per AC-3)
- [ ] In-memory and disk paths produce equivalent output (verified)
- [ ] No regressions in existing tests
- [ ] Code follows project style (see CLAUDE.md)

## Notes
The spray drift (AC-2/AC-3) is the "consolidate before it bites" case — the two copies currently disagree, so picking the right unified behavior matters.
