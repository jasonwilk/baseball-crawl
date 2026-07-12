# E-262-02: Cosmetic Hygiene Sweep

## Epic
[E-262: Post-Program Housekeeping](epic.md)

## Status
`TODO`

## Description
After this story is complete, three low-severity hygiene residuals are cleared: seven docstrings (five loaders + two crawlers) no longer model a banned DB-connection pattern, the empty `tests/test_crawlers/` package is deleted, and the stale docker-compose comment is corrected.

## Context
Three LOW-severity platform-audit residuals ratified into this epic (sweep §1, `.project/research/2026-07-12-program-endgame-sweep.md`). (Audit #6 was DROPPED during review — see the note below.)
- **#4 (scope corrected in review):** Seven docstrings model the banned cwd-relative `sqlite3.connect("./data/app.db")` pattern. SE verified the exact set: FIVE in `src/gamechanger/loaders/` (`scouting_loader.py:23`, `plays_loader.py:22`, `plays_reload.py:55`, `game_loader.py:27`, `scouting_spray_loader.py:72`) and TWO in `src/gamechanger/crawlers/` (`scouting.py:33`, `scouting_spray.py:34`) — the "seven" total is right but two are in `crawlers/`, not `loaders/`. Docstrings that model a banned pattern train the wrong habit; they should show the canonical path (repo-root-relative resolution / `resolve_db_path()`) or drop the example.
- **#7:** `tests/test_crawlers/` is an empty package (only `__init__.py` + `__pycache__`; audit quick-win: delete it, `__pycache__` too).
- **#8 (premise corrected in review):** A `docker-compose.yml` comment (`:38-39`) references the gitignored `docker-compose.override.yml` AND names "8180:8080 dashboard." SE verified the `8180:8080` port is the LIVE Traefik dashboard (per `.claude/rules/devcontainer.md`), NOT a deleted surface — E-239 removed the APP coaching dashboard, not the Traefik admin dashboard. So the audit's "deleted dashboard port" framing is FALSE. The REAL staleness is the override-file reference: the committed `docker-compose.override.yml.example` contains only a cloudflared profile and NO port mappings, so the comment's claim that dev-only ports "are in docker-compose.override.yml" is stale. Reword the comment to describe the current override accurately; do NOT treat `8080` as deleted.

**Dropped in review (SE finding):** Audit #6 (test_no_inline_schemas.py "whole-file pragma") was DROPPED. SE verified the live file has NO degrading whole-file pragma — it has `_SELF_EXEMPT = {"test_no_inline_schemas.py"}` (`:17`, used at `:24`), which is NECESSARY: the guard file contains the literal `_FORBIDDEN = "CREATE TABLE"` (`:15`) and would flag ITSELF without the self-exemption. Narrowing/removing it would make the test fail on itself. The audit premise was stale/mischaracterized; there is no actionable defect.

## Acceptance Criteria
- [ ] **AC-1**: Given the seven flagged docstrings (five in `src/gamechanger/loaders/`, two in `src/gamechanger/crawlers/`), when they are read, then none models the banned cwd-relative `sqlite3.connect("./data/app.db")` form; each either shows the canonical path-resolution approach or omits the connection example.
- [ ] **AC-2**: Given the repository tree, when `tests/test_crawlers/` is checked, then the empty package no longer exists and the test suite still collects/passes.
- [ ] **AC-3**: Given the `docker-compose.yml` comment (`:38-39`), when it is read, then it accurately describes the current override file (which carries no port mappings) and does NOT mislabel the live Traefik dashboard port `8180:8080` as deleted; the comment reflects current compose reality.

## Technical Approach
Purely cosmetic/hygiene edits across the seven docstring files (five `loaders/`, two `crawlers/`), the `tests/test_crawlers/` directory (delete), and `docker-compose.yml`. The implementer confirms the docstring set via a grep for the banned `sqlite3.connect("./data/app.db")` form (SE's verified list is in Context) and confirms the current override-file contents before rewriting the compose comment — the comment must not present `8180:8080` as a deleted port (it is the live Traefik dashboard).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/scouting_loader.py`, `plays_loader.py`, `plays_reload.py`, `game_loader.py`, `scouting_spray_loader.py` (five loader docstrings)
- `src/gamechanger/crawlers/scouting.py`, `scouting_spray.py` (two crawler docstrings)
- `tests/test_crawlers/` (delete the empty package + its `__pycache__`)
- `docker-compose.yml`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Source: endgame sweep §1 residuals #4, #7, #8 (residual #6 DROPPED in review — mischaracterized; see Context). All LOW-severity cosmetic/hygiene — separated from behavioral fixes (story 01) so a reviewer can fast-path them.

**SE holistic review (2026-07-12) incorporated:** #4 scope corrected (2 of the 7 docstrings are in `crawlers/`, not `loaders/` — both added to Files + the epic file-isolation table; SE verified no collision with stories 03/04); #6 DROPPED (the `_SELF_EXEMPT` it flagged is a necessary self-exemption, not a degrading pragma); #8 reworded off the false "deleted dashboard port" premise (8180:8080 is the live Traefik dashboard) to target the real override-file staleness.
