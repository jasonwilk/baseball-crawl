# E-246-01: Delete dead 3-tier gc_uuid resolver and its test

## Epic
[E-246: Dead-Code Removal & Low-Risk Consolidation](epic.md)

## Status
`DONE`

## Description
After this story is complete, the dead 3-tier gc_uuid resolver module and its test will be removed from the codebase. The resolver has zero importers (grep-confirmed) and its Tier-1/2 read paths depended on data removed in E-239, so it is unreachable dead code.

## Context
The sweep's H3 finding: the entire 343-line `src/gamechanger/resolvers/gc_uuid_resolver.py` (plus its ~900-line test) has zero importers, and the data its Tier-1/Tier-2 tiers read was removed in E-239 (member-sync/opponents surface). This is the deletion half of H3; the live search→public_id-filter consolidation (the same finding's "consol" half) is scoped to E-247, not here. Pre-existing idea IDEA-046 is effectively promoted into this work.

Because this is a large deletion, the implementer must re-confirm the dead status with a fresh grep before deleting — do not rely solely on the report's claim (per the clean-reread discipline in Technical Notes).

## Acceptance Criteria
- [ ] **AC-1**: Given the resolver is claimed dead, when the implementer greps `src/` and `tests/` for any import of `gc_uuid_resolver` (module path and any symbol it exports), then the only matches are the resolver file itself and its own test file (zero external importers). The grep result is recorded in the completion report.
- [ ] **AC-2**: Given zero external importers are confirmed, when the story completes, then `src/gamechanger/resolvers/gc_uuid_resolver.py` and its corresponding test file are deleted.
- [ ] **AC-3**: Given the deletion, when any now-empty package scaffolding (e.g. an `__init__.py` that only existed to export the resolver) is left behind, then it is cleaned up if and only if it has no other purpose; otherwise it is left intact.
- [ ] **AC-4**: Given the deletion, when a grep confirms no surviving file under `tests/` imports the deleted module, then none does — no dangling test reference remains. (The full-suite-green check across `tests/` is the epic-level closure gate, not a per-story AC — it is only authoritative in the merged main checkout, not the worktree.)

## Technical Approach
Report locations (re-verify before acting): `src/gamechanger/resolvers/gc_uuid_resolver.py:1-343` and its test (~900 lines). Confirm zero importers via grep across the whole repo, including any dynamic/string-based imports, before deletion. This is a pure deletion — no replacement code is introduced in this story.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/resolvers/gc_uuid_resolver.py` (delete)
- `tests/test_gc_uuid_resolver.py` (delete — the resolver's ~900-line test; confirmed to exist)
- `src/gamechanger/resolvers/__init__.py` (modify only if it exports the deleted module and has no other purpose)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Grep re-confirmation recorded in completion report
- [ ] No regressions in existing tests
- [ ] Code follows project style (see CLAUDE.md)

## Notes
Deletion is CONFIRMED by the user (epic Open Questions, resolved 2026-06-29) — git history retains the code. The AC-1 fresh-grep re-confirmation remains the pre-delete safety check.
