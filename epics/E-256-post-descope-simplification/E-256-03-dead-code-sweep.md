# E-256-03: Dead-code sweep — bridge, discover_opponents, ghost dirs, utcnow

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`TODO`

## Description
After this story is complete, the descope's dead-code residue is gone: the `bridge.py` module (implements the endpoint the rules ban for opponents), the test-only `discover_opponents` dead code, three ghost package directories carrying only stale pre-E-239 bytecode, and the two divergent `_utcnow_iso` implementations — consolidated into a single public `utcnow_iso` helper.

## Context
**api-scout consultation not required (rationale, per the epic's Consultation Triggers):** although this story deletes GameChanger endpoint-pattern code (`bridge.py`, `discover_opponents`), that code is **DEAD** — `bridge.py` is an E-239 deletion-set survivor implementing the opponent-bridge endpoint the rules already BAN (`.claude/rules/gc-uuid-bridge.md`), and `discover_opponents` is test-only dead code from the removed discovery surface. No LIVE API behavior is exercised or changed, so there is no api-scout question to answer; the deletion is a pure dead-code removal.

Each item is an independent E-239 deletion-set survivor. The two `_utcnow_iso` implementations (`generator.py:225` vs `scouting.py:466`) format-invert lexical ordering same-second and one is imported cross-module by underscore name. Publicizing to `utcnow_iso` and consolidating kills the cross-module underscore imports at `morning_run.py:52` and `reports_admin.py:541` — which is also a prerequisite for story 04's lifecycle extraction (Technical Notes §13). A present-tense docstring references `src.pipeline.trigger`; the ghost dirs (`src/pipeline/` etc.) contain only bytecode.

## Acceptance Criteria
- [ ] **AC-1**: Given `bridge.py`, when this story is complete, then the module and any import of it are removed, and no code path issues the banned opponent-bridge endpoint.
- [ ] **AC-2**: Given `discover_opponents` (`src/gamechanger/team_resolver.py:160`) and its test-only callers, when this story is complete, then both are removed.
- [ ] **AC-3**: Given the three ghost package directories (`src/pipeline/` and the two others) and the present-tense docstring referencing `src.pipeline.trigger`, when this story is complete, then the directories are removed and no docstring or comment references them.
- [ ] **AC-4**: Given the two `_utcnow_iso` implementations, when this story is complete, then there is exactly one public `utcnow_iso` helper, the cross-module underscore imports at `morning_run.py:52` and `reports_admin.py:541` import the public name, and no second implementation remains.
- [ ] **AC-5**: Given the full suite, when this story is complete, then it is green.

## Technical Approach
Locate the single natural home for `utcnow_iso` (a small time helper both `reports` and `gamechanger` layers can import without inverting the layering — e.g. `src/util/`). Delete the ghost dirs including their `.pyc`. The `bridge.py` endpoint ban is documented in `.claude/rules/gc-uuid-bridge.md` (BANNED PATH section) — deleting the module is consistent with it; do not edit that rule here (it already bans the path).

## Dependencies
- **Blocked by**: None
- **Blocks**: E-256-04 (the lifecycle split depends on the single public `utcnow_iso`); E-256-15 (eviction sweep)

## Files to Create or Modify
- `src/.../bridge.py` (delete)
- `src/gamechanger/team_resolver.py` (remove `discover_opponents`)
- `src/pipeline/` and the two other ghost dirs (delete)
- The `utcnow_iso` home module (create or select)
- `src/reports/generator.py`, `src/gamechanger/crawlers/scouting.py` (remove duplicate `_utcnow_iso`)
- `src/reports/morning_run.py` (`:52`), `src/api/routes/reports_admin.py` (`:541`) (import the public name)
- Any test files referencing the deleted symbols

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-256-04**: the single public `utcnow_iso` name and location, which the lifecycle split consumes.
- **Produces for E-256-15**: the deleted symbol set (`bridge`, `discover_opponents`, `src.pipeline.*`) for the eviction sweep.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests updated and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
None.
